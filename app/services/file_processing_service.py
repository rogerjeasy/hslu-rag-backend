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
from app.services.langchain_document_service import LangchainDocumentService
from app.core.config import settings

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
        self.langchain_service = LangchainDocumentService()
        
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
        Process a file for RAG using LangChain:
        1. Extract text and chunk with LangChain
        2. Create embeddings
        3. Store embeddings in Pinecone
        4. Update metadata in Firestore
        """
        try:
            # Update progress in Firestore
            self.db.collection("materials").document(material_id).update({
                "processing_status.progress": 0.1
            })
            
            # Process document with LangChain
            chunks = await self.langchain_service.process_document(
                file_path=file_path, 
                file_type=file_type,
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP
            )
            
            # Update progress in Firestore
            self.db.collection("materials").document(material_id).update({
                "processing_status.progress": 0.5,
                "chunk_count": len(chunks)
            })
            
            # Generate embeddings and store in Pinecone
            vector_ids = []
            for i, chunk in enumerate(chunks):
                # Create embedding
                embedding = await self.embedding_service.create_embedding(chunk["text"])
                
                # Create metadata for Pinecone
                metadata = {
                    "material_id": material_id,
                    "course_id": material_data["course_id"],
                    "module_id": material_data.get("module_id"),
                    "topic_id": material_data.get("topic_id"),
                    "chunk_index": i,
                    "chunk_content": chunk["text"][:1000],  # Limit to 1000 chars for metadata
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
        
        # Clean input text before chunking
        # Remove any non-printable characters that might cause issues
        import re
        # Keep newlines and tabs but remove other control characters
        text = re.sub(r'[^\x09\x0A\x0D\x20-\x7E\xA0-\xFF]', '', text)
        
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
                    
            # Clean chunk content
            if content:
                # Additional validation for chunk content
                try:
                    # Make sure it's UTF-8 encoded properly
                    content = content.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                    # Remove any problematic characters again
                    content = re.sub(r'[^\x09\x0A\x0D\x20-\x7E\xA0-\xFF]', '', content)
                except Exception as e:
                    logger.warning(f"Error cleaning chunk content: {str(e)}")
                    content = "Error: Could not process this content segment"
            
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

            # Get file type from material data as an extension of the file name
            file_extension = os.path.splitext(temp_file_path)[1].lower()
            
            # Use the document loader service for text extraction
            text_content = await self.document_loader.extract_text(temp_file_path, file_extension)
            
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

    
    async def fix_encoded_chunks(self, material_ids=None):
        """
        Fix binary-encoded chunks in Pinecone.
        
        Args:
            material_ids: Optional list of material IDs to fix. If None, fix all.
            
        Returns:
            Dictionary with results
        """
        results = {
            "success": [],
            "failed": []
        }
        
        try:
            if not material_ids:
                # Query for all materials from Firestore
                materials_ref = self.db.collection("materials")
                materials = [doc.to_dict() for doc in materials_ref.stream()]
                material_ids = [material.get("id", doc.id) for doc, material in zip(materials_ref.stream(), materials)]
            
            logger.info(f"Starting to fix {len(material_ids)} materials")
            
            for material_id in material_ids:
                try:
                    # Get material data
                    material_doc = self.db.collection("materials").document(material_id).get()
                    
                    if not material_doc.exists:
                        logger.warning(f"Material {material_id} not found")
                        results["failed"].append({
                            "id": material_id,
                            "error": "Material not found"
                        })
                        continue
                        
                    material_data = material_doc.to_dict()
                    
                    # Update Firestore status to indicate reprocessing
                    self.db.collection("materials").document(material_id).update({
                        "status": "reprocessing",
                        "updated_at": datetime.utcnow().isoformat(),
                        "processing_status": {
                            "progress": 0.0,
                            "started_at": datetime.utcnow().isoformat(),
                            "completed_at": None,
                            "error_message": None
                        }
                    })
                    
                    # Delete existing vectors
                    filter_dict = {"material_id": material_id}
                    await self.pinecone_service.delete_vectors(filter=filter_dict)
                    
                    # Re-download file if needed
                    if "file_url" in material_data:
                        temp_file_path = os.path.join(self.temp_dir, f"{material_id}-fix")
                        await self.cloudinary_service.download_file(
                            material_data["file_url"], 
                            temp_file_path
                        )
                        
                        # Reprocess the file
                        await self._process_file_for_rag(
                            material_id=material_id,
                            file_path=temp_file_path,
                            file_type=material_data["file_type"],
                            material_data=material_data
                        )
                        
                        # Clean up
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                    
                    logger.info(f"Successfully reprocessed material {material_id}")
                    results["success"].append(material_id)
                    
                except Exception as e:
                    logger.error(f"Error fixing material {material_id}: {str(e)}")
                    # Update Firestore with error status
                    self.db.collection("materials").document(material_id).update({
                        "status": "failed",
                        "updated_at": datetime.utcnow().isoformat(),
                        "processing_status": {
                            "error_message": f"Error during reprocessing: {str(e)}"
                        }
                    })
                    results["failed"].append({
                        "id": material_id,
                        "error": str(e)
                    })
            
            logger.info(f"Finished fixing materials. Success: {len(results['success'])}, Failed: {len(results['failed'])}")
            return results
            
        except Exception as e:
            logger.error(f"Error in fix_encoded_chunks: {str(e)}")
            raise


    # Add to file_processing_service.py

    async def extract_text_from_pdf_robust(self, file_path: str) -> str:
        """
        Extract text from PDF using multiple methods to ensure clean text.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text as clean string
        """
        import io
        import re
        import subprocess
        
        all_text = ""
        
        # Method 1: Try pdfminer.six (most thorough)
        try:
            from pdfminer.high_level import extract_text as pdfminer_extract
            
            text = pdfminer_extract(file_path)
            if text and len(text) > 100:  # Check if meaningful text was extracted
                # Clean the text
                text = self._clean_text_thoroughly(text)
                if text.strip():
                    all_text += text + "\n\n"
                    logger.info("Successfully extracted text with pdfminer.six")
        except Exception as e:
            logger.warning(f"pdfminer.six extraction failed: {str(e)}")
        
        # Method 2: Try PyPDF2
        if not all_text or len(all_text) < 100:
            try:
                import PyPDF2
                
                with open(file_path, 'rb') as f:
                    pdf = PyPDF2.PdfReader(f)
                    text = ""
                    for page_num in range(len(pdf.pages)):
                        page = pdf.pages[page_num]
                        page_text = page.extract_text() or ""
                        text += f"\n--- Page {page_num+1} ---\n{page_text}\n\n"
                    
                    if text and len(text) > 100:  # Check if meaningful text was extracted
                        # Clean the text
                        text = self._clean_text_thoroughly(text)
                        if text.strip():
                            all_text += text + "\n\n"
                            logger.info("Successfully extracted text with PyPDF2")
            except Exception as e:
                logger.warning(f"PyPDF2 extraction failed: {str(e)}")
        
        # Method 3: Try pdf2text (external tool via subprocess)
        if not all_text or len(all_text) < 100:
            try:
                # Check if pdftotext is installed
                try:
                    subprocess.run(['pdftotext', '-v'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                    pdftotext_available = True
                except:
                    pdftotext_available = False
                
                if pdftotext_available:
                    # Use pdftotext external tool
                    output_file = file_path + '.txt'
                    subprocess.run(['pdftotext', '-layout', file_path, output_file], check=False)
                    
                    if os.path.exists(output_file):
                        with open(output_file, 'r', encoding='utf-8', errors='replace') as f:
                            text = f.read()
                        
                        # Clean up the temporary file
                        try:
                            os.remove(output_file)
                        except:
                            pass
                        
                        if text and len(text) > 100:  # Check if meaningful text was extracted
                            # Clean the text
                            text = self._clean_text_thoroughly(text)
                            if text.strip():
                                all_text += text + "\n\n"
                                logger.info("Successfully extracted text with pdftotext")
            except Exception as e:
                logger.warning(f"pdftotext extraction failed: {str(e)}")
        
        # Method 4: Try Tesseract OCR if text extraction failed
        if not all_text or len(all_text) < 100:
            try:
                import pytesseract
                from pdf2image import convert_from_path
                
                # Convert PDF to images
                images = convert_from_path(file_path)
                
                # Extract text from each image
                text = ""
                for i, image in enumerate(images):
                    page_text = pytesseract.image_to_string(image)
                    text += f"\n--- Page {i+1} ---\n{page_text}\n\n"
                
                if text and len(text) > 100:  # Check if meaningful text was extracted
                    # Clean the text
                    text = self._clean_text_thoroughly(text)
                    if text.strip():
                        all_text += text + "\n\n"
                        logger.info("Successfully extracted text with Tesseract OCR")
            except Exception as e:
                logger.warning(f"Tesseract OCR extraction failed: {str(e)}")
        
        # If we extracted text, return it
        if all_text and len(all_text) > 100:
            return all_text
        
        # Last resort: try to extract any printable characters
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Try to decode as utf-8
            try:
                text = content.decode('utf-8', errors='replace')
            except:
                # Just get printable ASCII characters
                text = ''.join(chr(c) for c in content if 32 <= c <= 126 or c in [9, 10, 13])
            
            # Clean thoroughly
            text = self._clean_text_thoroughly(text)
            
            if text and len(text) > 100:
                logger.info("Extracted text using fallback binary reading")
                return text
        except Exception as e:
            logger.warning(f"Fallback text extraction failed: {str(e)}")
        
        raise ValidationException("Failed to extract any meaningful text from the PDF file")

    def _clean_text_thoroughly(self, text: str) -> str:
        """
        Apply aggressive cleaning to ensure text is free from binary and special characters.
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        try:
            # Convert to string if not already
            if not isinstance(text, str):
                text = str(text)
            
            # Replace common encoding artifacts
            text = text.replace('\x00', '')  # Null bytes
            
            # Force UTF-8 encoding/decoding
            text = text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            
            # First pass: keep only printable ASCII, newlines, tabs
            text = ''.join(c for c in text if c.isprintable() or c in ['\n', '\t', '\r'])
            
            # Remove control characters except newlines and tabs
            import re
            text = re.sub(r'[^\x20-\x7E\x0A\x0D\x09]', '', text)
            
            # Replace multiple spaces with a single space
            text = re.sub(r' +', ' ', text)
            
            # Replace multiple newlines with at most two
            text = re.sub(r'\n{3,}', '\n\n', text)
            
            # Remove lines that are just special characters (likely garbage)
            lines = text.split('\n')
            clean_lines = []
            for line in lines:
                # If line has at least 3 alphanumeric characters, keep it
                if sum(c.isalnum() for c in line) >= 3:
                    clean_lines.append(line)
                # Or if it's a page marker
                elif "Page" in line and any(c.isdigit() for c in line):
                    clean_lines.append(line)
            
            text = '\n'.join(clean_lines)
            
            return text.strip()
        except Exception as e:
            logger.warning(f"Error in thorough text cleaning: {str(e)}")
            return ""
        

    async def reprocess_material_with_robust_extraction(self, material_id: str) -> None:
        """
        Reprocess a material with robust PDF extraction to fix binary encoding issues.
        
        Args:
            material_id: ID of the material to reprocess
        """
        temp_file_path = None
        
        try:
            # Get material data
            material_doc = self.db.collection("materials").document(material_id).get()
            if not material_doc.exists:
                raise ValidationException(f"Material {material_id} not found")
            
            material_data = material_doc.to_dict()
            
            # Update status
            self.db.collection("materials").document(material_id).update({
                "status": "reprocessing",
                "processing_status": {
                    "progress": 0.1,
                    "started_at": datetime.utcnow().isoformat(),
                    "completed_at": None,
                    "error_message": None
                }
            })
            
            # Download file
            file_url = material_data.get("file_url")
            if not file_url:
                raise ValidationException(f"Material {material_id} has no file URL")
                
            temp_file_path = os.path.join(self.temp_dir, f"{material_id}-robust")
            await self.cloudinary_service.download_file(file_url, temp_file_path)
            
            # Extract text using robust method
            file_type = material_data.get("file_type", "").lower()
            
            
            if file_type == "pdf" or temp_file_path.lower().endswith(".pdf"):
                # Use robust PDF extraction
                text_content = await self.extract_text_from_pdf_robust(temp_file_path)
            else:
                # For non-PDF files, use standard extraction
                text_content = await self.document_loader.extract_text(temp_file_path, file_type)
                # Clean it anyway
                text_content = self._clean_text_thoroughly(text_content)
        
            
            # Update progress
            self.db.collection("materials").document(material_id).update({
                "processing_status.progress": 0.3
            })
            
            # Create text splitter
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
                separators=["\n\n", "\n", ". ", " ", ""],
                length_function=len
            )
            
            # Split text into chunks
            chunks = splitter.split_text(text_content)
            
            # Update progress
            self.db.collection("materials").document(material_id).update({
                "processing_status.progress": 0.5,
                "chunk_count": len(chunks)
            })
            
            # Delete existing vectors
            filter_dict = {"material_id": material_id}
            await self.pinecone_service.delete_vectors(filter=filter_dict)
            
            # Create new vectors
            vector_ids = []
            for i, chunk_text in enumerate(chunks):
                # Clean the chunk text again
                chunk_text = self._clean_text_thoroughly(chunk_text)
                
                # Skip empty chunks
                if not chunk_text.strip():
                    continue
                    
                # Create embedding
                embedding = await self.embedding_service.create_embedding(chunk_text)
                
                # Create metadata
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
                
                # Update progress
                progress = 0.5 + (0.4 * ((i + 1) / len(chunks)))
                self.db.collection("materials").document(material_id).update({
                    "processing_status.progress": progress
                })
            
            # Update material status
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
            
            logger.info(f"Successfully reprocessed material {material_id} with robust extraction")
            
        except Exception as e:
            logger.error(f"Error reprocessing material {material_id}: {str(e)}")
            # Update status
            self.db.collection("materials").document(material_id).update({
                "status": "failed",
                "updated_at": datetime.utcnow().isoformat(),
                "processing_status": {
                    "error_message": str(e),
                    "completed_at": datetime.utcnow().isoformat()
                }
            })
        finally:
            # Clean up
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass