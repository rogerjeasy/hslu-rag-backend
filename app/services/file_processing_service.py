# app/services/file_processing_service.py
import os
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, BinaryIO
from fastapi import UploadFile

from app.core.exceptions import NotFoundException, ValidationException, FirebaseException
from app.services.cloudinary_service import CloudinaryService
from app.services.new_embedding_service import EmbeddingService
from app.services.pinecone_service import PineconeService
from app.services.document_loader_service import DocumentLoaderService  # Import new service
from app.core.firebase import firebase

logger = logging.getLogger(__name__)

class FileProcessingService:
    """Service for processing uploaded files"""
    
    def __init__(self):
        """Initialize service with required dependencies"""
        self.db = firebase.get_firestore()
        self.cloudinary_service = CloudinaryService()
        self.embedding_service = EmbeddingService()
        self.pinecone_service = PineconeService()
        self.document_loader = DocumentLoaderService()  # Initialize new service
        
        # Create temp directory if it doesn't exist
        self.temp_dir = os.path.join(os.getcwd(), "temp")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
    
    async def process_file(
        self, 
        file: UploadFile, 
        course_id: str,
        user_id: str,
        module_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        file_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an uploaded file:
        1. Save to temp directory
        2. Upload to Cloudinary
        3. Extract text and create chunks
        4. Generate embeddings
        5. Store embeddings in Pinecone
        6. Save metadata in Firestore
        """
        try:
            # Generate material ID
            material_id = f"material-{uuid.uuid4().hex}"
            
            # Save file to temp directory
            temp_file_path = os.path.join(self.temp_dir, f"{material_id}-{file.filename}")
            
            with open(temp_file_path, "wb") as f:
                content = await file.read()
                f.write(content)
                file_size = len(content)
            
            # Determine file type if not provided
            if not file_type:
                file_extension = os.path.splitext(file.filename)[1].lower()
                file_type = file_extension.lstrip('.')
            
            # Set title if not provided
            if not title:
                title = os.path.splitext(file.filename)[0]
            
            # Upload to Cloudinary
            cloudinary_result = await self.cloudinary_service.upload_file(
                file_path=temp_file_path,
                folder=f"courses/{course_id}",
                public_id=material_id
            )
            
            # Create initial Firestore document
            current_time = datetime.utcnow().isoformat()
            material_data = {
                "id": material_id,
                "title": title,
                "description": description or "",
                "type": file_type,
                "course_id": course_id,
                "module_id": module_id,
                "topic_id": topic_id,
                "file_url": cloudinary_result["secure_url"],
                "file_size": file_size,
                "file_type": file_type,
                "status": "processing",
                "uploaded_at": current_time,
                "updated_at": current_time,
                "uploaded_by": user_id,
                "processing_status": {
                    "progress": 0.0,
                    "started_at": current_time,
                    "completed_at": None,
                    "error_message": None
                }
            }
            
            # Save to Firestore
            self.db.collection("materials").document(material_id).set(material_data)
            
            # Start processing asynchronously (in a background task)
            # For simplicity, we'll update the Firestore document directly here
            # In a production environment, use a task queue like Celery or similar
            await self._process_file_for_rag(
                material_id=material_id, 
                file_path=temp_file_path, 
                file_type=file_type,
                material_data=material_data
            )
            
            # Return the initial material data
            return material_data
            
        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {str(e)}")
            # Clean up temp file if it exists
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise FirebaseException(f"Error processing file: {str(e)}")
    
    async def _process_file_for_rag(
        self, 
        material_id: str, 
        file_path: str, 
        file_type: str,
        material_data: Dict[str, Any]
    ) -> None:
        """
        Process a file for RAG:
        1. Extract text
        2. Chunk text
        3. Create embeddings
        4. Store embeddings in Pinecone
        5. Update metadata in Firestore
        """
        try:
            # Update progress in Firestore
            self.db.collection("materials").document(material_id).update({
                "processing_status.progress": 0.1
            })
            
            # Extract text using the document loader service
            text_content = await self.document_loader.extract_text(file_path, file_type)
            
            # Update progress in Firestore
            self.db.collection("materials").document(material_id).update({
                "processing_status.progress": 0.3
            })
            
            # Chunk text
            chunks = await self._chunk_text(text_content, material_data)
            
            # Update progress in Firestore
            self.db.collection("materials").document(material_id).update({
                "processing_status.progress": 0.5,
                "chunk_count": len(chunks)
            })
            
            # Generate embeddings
            vector_ids = []
            for i, chunk in enumerate(chunks):
                embedding = await self.embedding_service.create_embedding(chunk["text"])
                
                # Create metadata for Pinecone
                metadata = {
                    "material_id": material_id,
                    "course_id": material_data["course_id"],
                    "module_id": material_data.get("module_id"),
                    "topic_id": material_data.get("topic_id"),
                    "chunk_index": i,
                    "chunk_content": chunk["text"][:1000],  # Store the first 1000 chars for context
                    "title": material_data["title"],
                    "file_type": material_data["file_type"],
                    "source_page": chunk.get("page_number")
                }
                
                # Store in Pinecone
                vector_id = f"{material_id}-chunk-{i}"
                await self.pinecone_service.upsert_vector(
                    vector_id=vector_id,
                    vector=embedding,
                    metadata=metadata
                )
                
                vector_ids.append(vector_id)
                
                # Update progress in Firestore (gradually from 0.5 to 0.9)
                progress = 0.5 + (0.4 * ((i + 1) / len(chunks)))
                self.db.collection("materials").document(material_id).update({
                    "processing_status.progress": progress
                })
            
            # Remove temp file
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Update Firestore with completion status
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
            
        except Exception as e:
            logger.error(f"Error in background processing for material {material_id}: {str(e)}")
            
            # Update Firestore with error status
            self.db.collection("materials").document(material_id).update({
                "status": "failed",
                "updated_at": datetime.utcnow().isoformat(),
                "processing_status": {
                    "error_message": str(e)
                }
            })
            
            # Clean up temp file if it exists
            if os.path.exists(file_path):
                os.remove(file_path)
    
    async def _chunk_text(self, text: str, material_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk text using LangChain text splitter.
        
        Returns list of chunks with metadata.
        """
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        
        # Create text splitter with optimal settings for RAG
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,  # Target chunk size of 500 tokens
            chunk_overlap=100,  # Overlap of 100 tokens
            separators=["\n\n", "\n", ". ", " ", ""],  # Custom separators
            length_function=len  # Character-based length function
        )
        
        # Split the text
        chunks = splitter.create_documents([text])
        
        # Convert to list of dictionaries with metadata
        chunk_dicts = []
        for i, chunk in enumerate(chunks):
            # Extract page number from content if available
            page_number = None
            content = chunk.page_content
            if "--- Page " in content:
                try:
                    page_line = content.split("--- Page ")[1].split("\n")[0]
                    page_number = int(page_line.strip())
                    # Remove the page marker from the content
                    content = content.replace(f"--- Page {page_number} ---\n", "")
                except:
                    pass
            
            chunk_dicts.append({
                "text": content,
                "metadata": {
                    "material_id": material_data["id"],
                    "course_id": material_data["course_id"],
                    "module_id": material_data.get("module_id"),
                    "topic_id": material_data.get("topic_id"),
                    "title": material_data["title"],
                    "chunk_index": i
                },
                "page_number": page_number
            })
        
        return chunk_dicts
    
    async def get_processing_status(self, material_id: str) -> Dict[str, Any]:
        """
        Get the processing status of a material.
        """
        try:
            material_doc = self.db.collection("materials").document(material_id).get()
            if not material_doc.exists:
                raise ValidationException(f"Material with ID {material_id} not found")
            
            material_data = material_doc.to_dict()
            
            # Safely get processing_status as a dictionary
            processing_status = material_data.get("processing_status", {})
            if processing_status is None:
                processing_status = {}
            
            # Get the current time in ISO format for default values
            current_time = datetime.utcnow().isoformat()
            
            # Prepare status response with default values for all required fields
            status_response = {
                "material_id": material_id,
                "status": material_data.get("status", "unknown"),
                # Default progress to 0 if not available
                "progress": processing_status.get("progress", 0.0),
                # Error message can be None
                "error_message": processing_status.get("error_message"),
                # Default started_at to the current time if not available
                "started_at": processing_status.get("started_at") or current_time,
                # Completed_at can be None
                "completed_at": processing_status.get("completed_at")
            }
            
            # Ensure progress is a float
            try:
                status_response["progress"] = float(status_response["progress"])
            except (TypeError, ValueError):
                status_response["progress"] = 0.0
            
            logger.info(f"Processing status for material {material_id}: {status_response}")
            return status_response
            
        except ValidationException as e:
            logger.error(f"Validation error for material {material_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting processing status for material {material_id}: {str(e)}")
            raise FirebaseException(f"Error getting processing status: {str(e)}")
                
    async def process_file_initial(
        self, 
        file: UploadFile, 
        course_id: str,
        user_id: str,
        module_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        file_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initial processing of an uploaded file (save to temp dir, upload to Cloudinary).
        
        This method handles the synchronous part of processing.
        """
        try:
            # Generate material ID
            material_id = f"material-{uuid.uuid4().hex}"
            
            # Save file to temp directory
            temp_file_path = os.path.join(self.temp_dir, f"{material_id}-{file.filename}")
            
            with open(temp_file_path, "wb") as f:
                content = await file.read()
                f.write(content)
                file_size = len(content)
            
            # Determine file type if not provided
            if not file_type:
                file_extension = os.path.splitext(file.filename)[1].lower()
                file_type = file_extension.lstrip('.')
            
            # Set title if not provided
            if not title:
                title = os.path.splitext(file.filename)[0]
            
            # Upload to Cloudinary
            cloudinary_result = await self.cloudinary_service.upload_file(
                file_path=temp_file_path,
                folder=f"courses/{course_id}",
                public_id=material_id
            )
            
            # Create initial Firestore document
            current_time = datetime.utcnow().isoformat()
            material_data = {
                "id": material_id,
                "title": title,
                "description": description or "",
                "type": file_type,
                "course_id": course_id,
                "module_id": module_id,
                "topic_id": topic_id,
                "file_url": cloudinary_result["secure_url"],
                "file_size": file_size,
                "file_type": file_type,
                "status": "processing",
                "uploaded_at": current_time,
                "updated_at": current_time,
                "uploaded_by": user_id,
                "processing_status": {
                    "progress": 0.0,
                    "started_at": current_time,
                    "completed_at": None,
                    "error_message": None
                },
                "temp_file_path": temp_file_path  # Store temp path for background processing
            }
            
            # Save to Firestore
            self.db.collection("materials").document(material_id).set(material_data)
            
            return material_data
            
        except Exception as e:
            logger.error(f"Error in initial processing of file {file.filename}: {str(e)}")
            # Clean up temp file if it exists
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise FirebaseException(f"Error processing file: {str(e)}")

    async def process_file_background(self, material_id: str) -> None:
        """
        Process a file in the background after initial upload.
        
        This method is called as a background task.
        """
        try:
            # Get material data from Firestore
            material_doc = self.db.collection("materials").document(material_id).get()
            if not material_doc.exists:
                raise ValidationException(f"Material with ID {material_id} not found")
                
            material_data = material_doc.to_dict()
            temp_file_path = material_data.get("temp_file_path")
            
            # Check if file exists
            if not temp_file_path or not os.path.exists(temp_file_path):
                raise ValidationException(f"Temporary file not found for material {material_id}")
            
            # Extract text
            self.db.collection("materials").document(material_id).update({
                "processing_status.progress": 0.1
            })
            
            # Use the document loader service for text extraction
            text_content = await self.document_loader.extract_text(temp_file_path, material_data["file_type"])
            
            # Update progress
            self.db.collection("materials").document(material_id).update({
                "processing_status.progress": 0.3
            })
            
            # Chunk text
            chunks = await self._chunk_text(text_content, material_data)
            
            # Update progress
            self.db.collection("materials").document(material_id).update({
                "processing_status.progress": 0.5,
                "chunk_count": len(chunks)
            })
            
            # Generate embeddings and store in Pinecone
            vector_ids = []
            for i, chunk in enumerate(chunks):
                embedding = await self.embedding_service.create_embedding(chunk["text"])
                
                # Create metadata for Pinecone
                metadata = {
                    "material_id": material_id,
                    "course_id": material_data["course_id"],
                    "module_id": material_data.get("module_id"),
                    "topic_id": material_data.get("topic_id"),
                    "chunk_index": i,
                    "chunk_content": chunk["text"][:1000],  # Store the first 1000 chars for context
                    "title": material_data["title"],
                    "file_type": material_data["file_type"],
                    "source_page": chunk.get("page_number")
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
            
            # Remove temp file path from Firestore and clean up
            self.db.collection("materials").document(material_id).update({
                "temp_file_path": None
            })
            
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            
            # Update completion status
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
            
        except Exception as e:
            logger.error(f"Error in background processing for material {material_id}: {str(e)}")
            
            # Update error status
            self.db.collection("materials").document(material_id).update({
                "status": "failed",
                "updated_at": datetime.utcnow().isoformat(),
                "processing_status": {
                    "error_message": str(e)
                }
            })
            
            # Clean up temp file
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                
                self.db.collection("materials").document(material_id).update({
                    "temp_file_path": None
                })
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up temp file: {str(cleanup_error)}")
                pass

    async def get_failed_materials(self, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get a list of materials that failed processing
        
        Args:
            course_id: Optional course ID filter
            
        Returns:
            List of failed materials with error info
        """
        try:
            # Fixed query to target the right field structure
            query = self.db.collection("materials").where("status", "==", "failed")
            
            if course_id:
                query = query.where("course_id", "==", course_id)
                
            docs = query.stream()
            
            failed_materials = []
            for doc in docs:
                data = doc.to_dict()
                processing_status = data.get("processing_status", {})
                if isinstance(processing_status, dict):
                    error_message = processing_status.get("error_message", "Unknown error")
                else:
                    error_message = "Unknown error"
                
                failed_materials.append({
                    "id": data.get("id", doc.id),
                    "title": data.get("title", ""),
                    "description": data.get("description", ""),
                    "file_type": data.get("file_type", ""),
                    "processing_error": error_message,
                    "uploaded_at": data.get("uploaded_at", ""),
                    "course_id": data.get("course_id", "")
                })
                
            return failed_materials
            
        except Exception as e:
            logger.error(f"Error fetching failed materials: {str(e)}")
            raise

    async def retry_material_processing(self, material_id: str) -> bool:
        """
        Retry processing a failed material
        
        Args:
            material_id: Material ID to retry
            
        Returns:
            True if retry was started
        """
        try:
            # Get material from Firestore
            material_doc = self.db.collection("materials").document(material_id).get()
            
            if not material_doc.exists:
                raise NotFoundException(f"Material with ID {material_id} not found")
                
            material_data = material_doc.to_dict()
            
            # Fixed check to match the structure in the Firestore document
            if material_data.get("status") != "failed":
                raise ValidationException("Only failed materials can be retried")
                
            # Update processing status
            current_time = datetime.utcnow().isoformat()
            self.db.collection("materials").document(material_id).update({
                "status": "processing",
                "updated_at": current_time,
                "processing_status": {
                    "progress": 0.0,
                    "started_at": current_time,
                    "completed_at": None,
                    "error_message": None
                }
            })
            
            # Check if there's an existing file URL
            file_url = material_data.get("file_url")
            
            if not file_url:
                raise ValidationException(f"No file URL found for material {material_id}")
            
            # Download the file from Cloudinary
            temp_file_path = os.path.join(self.temp_dir, f"{material_id}-retry")
            await self.cloudinary_service.download_file(file_url, temp_file_path)
            
            # Update the material with the temp file path
            self.db.collection("materials").document(material_id).update({
                "temp_file_path": temp_file_path
            })
            
            # Process the file in the background
            await self.process_file_background(material_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error retrying material {material_id}: {str(e)}")
            raise