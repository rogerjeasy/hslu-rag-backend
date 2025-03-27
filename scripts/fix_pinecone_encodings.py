# maintenance_scripts/fix_pinecone_encodings.py

import asyncio
import logging
import os
import re
from typing import List, Dict, Any

# Import your services
from app.core.firebase import firebase
from app.services.pinecone_service import PineconeService
from app.services.cloudinary_service import CloudinaryService
from app.services.document_loader_service import DocumentLoaderService
from app.services.embedding_service import EmbeddingService

# Set up logging
logging.basicConfig(level=logging.INFO)
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
            
    async def fix_binary_chunks(self, material_id=None):
        """
        Fix binary encoded chunks for a specific material or all materials.
        
        Args:
            material_id: Optional specific material ID to fix. If None, processes all materials.
        """
        try:
            if material_id:
                # Fix specific material
                material_ids = [material_id]
            else:
                # Get all materials from Firestore
                materials_ref = self.db.collection("materials").where("status", "==", "completed")
                materials = []
                
                for doc in materials_ref.stream():
                    material_data = doc.to_dict()
                    material_data["id"] = doc.id
                    materials.append(material_data)
                
                material_ids = [m["id"] for m in materials]
                
            logger.info(f"Found {len(material_ids)} materials to process")
            
            for material_id in material_ids:
                await self._fix_material(material_id)
                
            logger.info("Completed fixing binary chunks in Pinecone")
            
        except Exception as e:
            logger.error(f"Error in fix_binary_chunks: {str(e)}")
            raise
            
    async def _fix_material(self, material_id):
        """Fix a specific material's chunks"""
        try:
            logger.info(f"Processing material: {material_id}")
            
            # Get material data from Firestore
            material_doc = self.db.collection("materials").document(material_id).get()
            if not material_doc.exists:
                logger.warning(f"Material {material_id} not found")
                return
                
            material_data = material_doc.to_dict()
            material_data["id"] = material_id
            
            # Update status to reprocessing
            self.db.collection("materials").document(material_id).update({
                "status": "reprocessing"
            })
            
            # Download file from Cloudinary
            if "file_url" not in material_data or not material_data["file_url"]:
                logger.warning(f"Material {material_id} has no file URL")
                return
                
            file_url = material_data["file_url"]
            temp_file_path = os.path.join(self.temp_dir, f"{material_id}_fix")
            
            await self.cloudinary_service.download_file(file_url, temp_file_path)
            
            if not os.path.exists(temp_file_path):
                logger.warning(f"Failed to download file for material {material_id}")
                return
            
            # Extract text properly
            file_type = material_data.get("file_type", "")
            if not file_type:
                file_type = "pdf"  # Default to PDF if file type not specified
                
            text_content = await self.document_loader.extract_text(temp_file_path, file_type)
            
            # Clean text content
            text_content = self._clean_text(text_content)
            
            # Chunk text
            chunks = self._chunk_text(text_content)
            
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
                    "file_type": file_type
                }
                
                # Store in Pinecone
                vector_id = f"{material_id}-chunk-{i}"
                await self.pinecone_service.upsert_vector(
                    vector_id=vector_id,
                    vector=embedding,
                    metadata=metadata
                )
                
                vector_ids.append(vector_id)
                
            # Update material status
            self.db.collection("materials").document(material_id).update({
                "status": "completed",
                "vector_ids": vector_ids,
                "chunk_count": len(chunks)
            })
            
            # Clean up
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
            logger.info(f"Successfully fixed {len(chunks)} chunks for material {material_id}")
            
        except Exception as e:
            logger.error(f"Error fixing material {material_id}: {str(e)}")
            # Update material status to failed
            self.db.collection("materials").document(material_id).update({
                "status": "failed",
                "processing_error": str(e)
            })
            
    def _clean_text(self, text):
        """Clean and sanitize text content"""
        if not text:
            return ""
            
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='replace')
            
        if not isinstance(text, str):
            text = str(text)
            
        # Clean text
        text = text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        text = re.sub(r'[^\x20-\x7E\x0A\x0D\x09\xA0-\xFF]', '', text)
        
        return text
        
    def _chunk_text(self, text, chunk_size=500, overlap=50):
        """Chunk text into smaller pieces"""
        if not text:
            return []
            
        # Simple chunking by paragraphs first
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) <= chunk_size:
                current_chunk += paragraph + "\n\n"
            else:
                # If current chunk is not empty, add it to chunks
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # Start new chunk with overlap
                words = current_chunk.split()
                overlap_text = " ".join(words[-overlap:]) if len(words) > overlap else ""
                current_chunk = overlap_text + paragraph + "\n\n"
                
        # Add the last chunk if not empty
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks

# Run the script
async def main():
    repair_service = PineconeRepairService()
    await repair_service.fix_binary_chunks()
    
if __name__ == "__main__":
    asyncio.run(main())