import logging
import os
import uuid
from typing import Dict, List, Any, Tuple, BinaryIO, Optional
import mimetypes
import hashlib

from app.core.config import settings
from app.core.exceptions import DocumentProcessingException
from app.rag.chunker import Chunker
from app.utils.file_processors.pdf_processor import PDFProcessor
from app.utils.file_processors.pptx_processor import PPTXProcessor
from app.utils.file_processors.notebook_processor import NotebookProcessor
from app.utils.file_processors.code_processor import CodeProcessor
from app.services.pinecone_service import PineconeService
from app.services.new_embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """
    Handles the processing of course materials into chunks for retrieval.
    
    This class coordinates the document processing pipeline:
    1. Extract text from various document formats
    2. Chunk text into retrievable segments
    3. Add metadata to chunks
    4. Prepare chunks for embedding and storage in Pinecone
    """
    
    def __init__(self, 
                 embedding_service: Optional[EmbeddingService] = None, 
                 pinecone_index_name: Optional[str] = None):
        """
        Initialize the document processor with optional embedding and Pinecone services
        
        Args:
            embedding_service: Service to generate vector embeddings
            pinecone_index_name: Optional custom Pinecone index name
        """
        self.chunker = Chunker()
        self.embedding_service = embedding_service or EmbeddingService()
        self.pinecone_service = PineconeService(index_name=pinecone_index_name)
        
        # Initialize file processors
        self.pdf_processor = PDFProcessor()
        self.pptx_processor = PPTXProcessor()
        self.notebook_processor = NotebookProcessor()
        self.code_processor = CodeProcessor()
    
    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        metadata: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Process a document into retrievable chunks.
        
        Args:
            file_content: Binary content of the file
            filename: Name of the file
            metadata: Additional metadata about the file (course_id, etc.)
            
        Returns:
            Tuple of (list of document chunks, document metadata)
        """
        try:
            # Generate source_id based on file content hash
            file_hash = hashlib.md5(file_content).hexdigest()
            source_id = f"{file_hash}"
            
            # Determine mime type
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                # Default to plain text if can't determine
                mime_type = "text/plain"
            
            # Extract text based on file type
            extracted_text, doc_metadata = await self._extract_text(file_content, filename, mime_type)
            
            # Merge metadata
            doc_metadata.update(metadata)
            doc_metadata["source"] = filename
            doc_metadata["source_id"] = source_id
            
            # Chunk the extracted text
            chunks = await self.chunker.chunk_text(
                text=extracted_text,
                metadata=doc_metadata
            )
            
            logger.info(f"Processed document {filename} into {len(chunks)} chunks")
            return chunks, doc_metadata
            
        except Exception as e:
            logger.error(f"Error processing document {filename}: {str(e)}")
            raise DocumentProcessingException(f"Failed to process document {filename}: {str(e)}")
    
    async def process_document_for_pinecone(
        self,
        file_content: bytes,
        filename: str,
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        Process a document and store chunks directly in Pinecone.
        
        Args:
            file_content: Binary content of the file
            filename: Name of the file
            metadata: Additional metadata about the file
            collection_name: Optional name for the collection (optional, not used in Pinecone)
            
        Returns:
            Tuple of (list of vector IDs, document metadata)
        """
        try:
            # Process document to get chunks
            chunks, doc_metadata = await self.process_document(
                file_content=file_content,
                filename=filename,
                metadata=metadata
            )
            
            # Prepare vectors for Pinecone
            vectors_to_upsert = []
            for chunk in chunks:
                # Generate unique vector ID
                vector_id = chunk.get("id", str(uuid.uuid4()))
                
                # Generate embedding for the chunk
                vector = await self.embedding_service.embed_text(chunk["content"])
                
                vectors_to_upsert.append({
                    "id": vector_id,
                    "vector": vector,
                    "metadata": {
                        **chunk["metadata"],
                        "chunk_content": chunk["content"]
                    }
                })
            
            # Upsert vectors to Pinecone
            result = await self.pinecone_service.upsert_vectors(vectors_to_upsert)
            
            # Extract vector IDs (assuming they're the same as chunk IDs)
            vector_ids = [item["id"] for item in vectors_to_upsert]
            
            logger.info(f"Processed and stored document {filename} with {len(vector_ids)} vectors in Pinecone")
            return vector_ids, doc_metadata
            
        except Exception as e:
            logger.error(f"Error processing document for Pinecone {filename}: {str(e)}")
            raise DocumentProcessingException(f"Failed to process document for Pinecone {filename}: {str(e)}")
    
    async def process_directory_for_pinecone(
        self,
        directory_path: str,
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None
    ) -> List[str]:
        """
        Process all documents in a directory and store in Pinecone.
        
        Args:
            directory_path: Path to the directory containing documents
            metadata: Metadata to apply to all documents
            collection_name: Optional name for the collection (not used in Pinecone)
            
        Returns:
            List of all vector IDs
        """
        all_vector_ids = []
        
        try:
            # Walk through the directory
            for root, _, files in os.walk(directory_path):
                for filename in files:
                    # Skip hidden files and non-document files
                    if filename.startswith(".") or not self._is_supported_file(filename):
                        continue
                    
                    file_path = os.path.join(root, filename)
                    
                    # Read file content
                    with open(file_path, "rb") as file:
                        file_content = file.read()
                    
                    # Get relative path for source identification
                    rel_path = os.path.relpath(file_path, directory_path)
                    
                    # Process the document
                    file_metadata = metadata.copy()
                    file_metadata["relative_path"] = rel_path
                    
                    vector_ids, _ = await self.process_document_for_pinecone(
                        file_content=file_content,
                        filename=rel_path,  # Use relative path as filename
                        metadata=file_metadata
                    )
                    
                    all_vector_ids.extend(vector_ids)
            
            logger.info(f"Processed and stored {len(all_vector_ids)} vectors from directory {directory_path} in Pinecone")
            return all_vector_ids
            
        except Exception as e:
            logger.error(f"Error processing directory for Pinecone {directory_path}: {str(e)}")
            raise DocumentProcessingException(f"Failed to process directory for Pinecone {directory_path}: {str(e)}")
    
    async def _extract_text(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from a document based on its type.
        (This method remains the same as in the original implementation)
        """
        # Existing implementation from the original DocumentProcessor
        doc_metadata = {
            "filename": filename,
            "mime_type": mime_type
        }
        
        # Process based on file type
        if mime_type == "application/pdf":
            # Process PDF
            text, pdf_metadata = await self.pdf_processor.process(file_content)
            doc_metadata.update(pdf_metadata)
            return text, doc_metadata
            
        elif mime_type in ["application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/vnd.ms-powerpoint"]:
            # Process PowerPoint
            text, pptx_metadata = await self.pptx_processor.process(file_content)
            doc_metadata.update(pptx_metadata)
            return text, doc_metadata
            
        elif mime_type == "application/json" and filename.endswith(".ipynb"):
            # Process Jupyter Notebook
            text, notebook_metadata = await self.notebook_processor.process(file_content)
            doc_metadata.update(notebook_metadata)
            return text, doc_metadata
            
        elif mime_type in ["text/x-python", "text/javascript", "text/plain"] or any(filename.endswith(ext) for ext in [".py", ".js", ".java", ".cpp", ".sql", ".r", ".cs"]):
            # Process code files
            text, code_metadata = await self.code_processor.process(file_content, filename)
            doc_metadata.update(code_metadata)
            return text, doc_metadata
            
        else:
            # Default to treating as plain text
            try:
                text = file_content.decode("utf-8")
                return text, doc_metadata
            except UnicodeDecodeError:
                # If we can't decode as UTF-8, raise an error
                raise DocumentProcessingException(f"Unsupported file type or encoding: {filename} ({mime_type})")
    
    def _is_supported_file(self, filename: str) -> bool:
        """
        Check if a file is supported for processing.
        (Existing implementation from the original DocumentProcessor)
        """
        # List of supported extensions
        supported_extensions = [
            ".pdf", ".txt", ".md", ".pptx", ".ppt",
            ".ipynb", ".py", ".js", ".java", ".cpp", 
            ".sql", ".r", ".cs", ".html", ".csv"
        ]
        
        # Check if the file has a supported extension
        return any(filename.lower().endswith(ext) for ext in supported_extensions)