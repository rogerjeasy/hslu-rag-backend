# app/services/pinecone_repair_service.py
import os
import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.firebase import firebase
from app.services.cloudinary_service import CloudinaryService
from app.services.document_loader_service import DocumentLoaderService
from app.services.new_embedding_service import EmbeddingService
from app.services.pinecone_service import PineconeService
from app.core.exceptions import ValidationException

logger = logging.getLogger(__name__)

class PineconeRepairService:
    """Service to fix binary encoded chunks in Pinecone"""
    
    def __init__(self):
        """Initialize services"""
        self.db = firebase.get_firestore()
        self.pinecone_service = PineconeService()
        self.cloudinary_service = CloudinaryService()
        self.document_loader = DocumentLoaderService()
        self.embedding_service = EmbeddingService()
        
        # Create temp directory if it doesn't exist
        self.temp_dir = os.path.join(os.getcwd(), "temp")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
    
    async def fix_binary_chunks(self, material_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Fix binary encoded chunks for specific materials or all materials.
        
        Args:
            material_ids: Optional list of specific material IDs to fix. If None, processes all materials.
            
        Returns:
            Dictionary with results summary
        """
        results = {
            "success": [],
            "failed": [],
            "status": "completed"
        }
        
        try:
            if not material_ids:
                # Get all materials from Firestore
                materials_ref = self.db.collection("materials").where("status", "==", "completed")
                materials = []
                
                for doc in materials_ref.stream():
                    material_data = doc.to_dict()
                    material_data["id"] = doc.id
                    materials.append(material_data)
                
                material_ids = [m["id"] for m in materials]
            
            total_count = len(material_ids)
            logger.info(f"Starting to fix {total_count} materials")
            
            for i, material_id in enumerate(material_ids):
                try:
                    await self._fix_material(material_id)
                    results["success"].append(material_id)
                    logger.info(f"Progress: {i+1}/{total_count} materials processed")
                except Exception as e:
                    logger.error(f"Error fixing material {material_id}: {str(e)}")
                    results["failed"].append({
                        "id": material_id,
                        "error": str(e)
                    })
            
            logger.info(f"Completed fixing chunks. Success: {len(results['success'])}, Failed: {len(results['failed'])}")
            return results
            
        except Exception as e:
            logger.error(f"Error in fix_binary_chunks: {str(e)}")
            results["status"] = "failed"
            results["error"] = str(e)
            return results
    
    async def _fix_material(self, material_id: str) -> None:
        """
        Fix a specific material's chunks.
        
        Args:
            material_id: The ID of the material to fix
        """
        # Get material data from Firestore
        material_doc = self.db.collection("materials").document(material_id).get()
        if not material_doc.exists:
            logger.warning(f"Material {material_id} not found")
            raise ValidationException(f"Material {material_id} not found")
            
        material_data = material_doc.to_dict()
        material_data["id"] = material_id
        
        # Update status to reprocessing
        current_time = datetime.utcnow().isoformat()
        self.db.collection("materials").document(material_id).update({
            "status": "reprocessing",
            "updated_at": current_time,
            "processing_status": {
                "progress": 0.0,
                "started_at": current_time,
                "completed_at": None,
                "error_message": None
            }
        })
        
        try:
            # Download file from Cloudinary
            if "file_url" not in material_data or not material_data["file_url"]:
                raise ValidationException(f"Material {material_id} has no file URL")
                
            file_url = material_data["file_url"]
            temp_file_path = os.path.join(self.temp_dir, f"{material_id}_fix")
            
            await self.cloudinary_service.download_file(file_url, temp_file_path)
            
            if not os.path.exists(temp_file_path):
                raise ValidationException(f"Failed to download file for material {material_id}")
            
            # Update progress
            self.db.collection("materials").document(material_id).update({
                "processing_status.progress": 0.1
            })
            
            # Extract text properly
            file_type = material_data.get("file_type", "")
            if not file_type:
                file_type = "pdf"  # Default to PDF if file type not specified
                
            text_content = await self.document_loader.extract_text(temp_file_path, file_type)
            
            # Clean text content
            text_content = self._clean_text(text_content)
            
            # Update progress
            self.db.collection("materials").document(material_id).update({
                "processing_status.progress": 0.3
            })
            
            # Chunk text
            chunks = self._chunk_text(text_content)
            
            # Update progress
            self.db.collection("materials").document(material_id).update({
                "processing_status.progress": 0.5,
                "chunk_count": len(chunks)
            })
            
            # Delete existing vectors
            filter_dict = {"material_id": material_id}
            await self.pinecone_service.delete_vectors(filter=filter_dict)
            
            # Create new vectors with clean text
            vector_ids = []
            for i, chunk_text in enumerate(chunks):
                # Create embedding
                embedding = await self.embedding_service.create_embedding(chunk_text)
                
                # Create clean metadata
                metadata = {
                    "material_id": material_id,
                    "course_id": material_data.get("course_id", ""),
                    "module_id": material_data.get("module_id"),
                    "topic_id": material_data.get("topic_id"),
                    "chunk_index": i,
                    "chunk_content": chunk_text[:1000],  # Limit size
                    "title": material_data.get("title", ""),
                    "file_type": file_type,
                    "source_page": None  # Add source_page if you extract it during chunking
                }
                
                # Store in Pinecone
                vector_id = f"{material_id}-chunk-{i}"
                await self.pinecone_service.upsert_vector(
                    vector_id=vector_id,
                    vector=embedding,
                    metadata=metadata
                )
                
                vector_ids.append(vector_id)
                
                # Update progress
                progress = 0.5 + (0.4 * ((i + 1) / len(chunks)))
                self.db.collection("materials").document(material_id).update({
                    "processing_status.progress": progress
                })
            
            # Update material status to completed
            current_time = datetime.utcnow().isoformat()
            self.db.collection("materials").document(material_id).update({
                "status": "completed",
                "vector_ids": vector_ids,
                "updated_at": current_time,
                "processing_status": {
                    "progress": 1.0,
                    "completed_at": current_time,
                    "error_message": None
                }
            })
            
            # Clean up
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
            logger.info(f"Successfully fixed {len(chunks)} chunks for material {material_id}")
            
        except Exception as e:
            logger.error(f"Error fixing material {material_id}: {str(e)}")
            # Update material status to failed
            current_time = datetime.utcnow().isoformat()
            self.db.collection("materials").document(material_id).update({
                "status": "failed",
                "updated_at": current_time,
                "processing_status": {
                    "error_message": str(e),
                    "completed_at": current_time
                }
            })
            
            # Clean up
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
            raise e
    
    def _clean_text(self, text: Any) -> str:
        """
        Clean and sanitize text content.
        
        Args:
            text: Text content to clean
            
        Returns:
            Cleaned text
        """
        if text is None:
            return ""
            
        # Handle binary data
        if isinstance(text, bytes):
            try:
                text = text.decode('utf-8', errors='replace')
            except Exception as e:
                logger.error(f"Error decoding binary text: {str(e)}")
                return ""
            
        # Convert to string if not already
        if not isinstance(text, str):
            text = str(text)
            
        # Clean text
        try:
            # Force encoding/decoding to clean the text
            text = text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            
            # Remove any non-printable characters except newlines and tabs
            import re
            text = re.sub(r'[^\x20-\x7E\x0A\x0D\x09\xA0-\xFF]', '', text)
            
            return text
        except Exception as e:
            logger.error(f"Error cleaning text: {str(e)}")
            return ""
    
    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Chunk text into smaller pieces for processing.
        
        Args:
            text: Text to chunk
            chunk_size: Target size of each chunk
            overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        
        if not text:
            return []
        
        try:
            # Create text splitter
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=overlap,
                separators=["\n\n", "\n", ". ", " ", ""],
                length_function=len
            )
            
            # Split the text into chunks
            chunks = splitter.split_text(text)
            
            # Clean each chunk again to be safe
            cleaned_chunks = [self._clean_text(chunk) for chunk in chunks]
            
            # Remove empty chunks
            cleaned_chunks = [chunk for chunk in cleaned_chunks if chunk.strip()]
            
            return cleaned_chunks
        except Exception as e:
            logger.error(f"Error chunking text: {str(e)}")
            # Fall back to a simpler chunking method
            paragraphs = text.split('\n\n')
            chunks = []
            current_chunk = ""
            
            for paragraph in paragraphs:
                # If adding this paragraph would exceed chunk size, save current chunk and start new one
                if len(current_chunk) + len(paragraph) > chunk_size:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = paragraph + "\n\n"
                else:
                    current_chunk += paragraph + "\n\n"
            
            # Add the last chunk if not empty
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            return chunks