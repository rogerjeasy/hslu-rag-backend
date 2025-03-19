# app/rag/document_processor.py
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
from app.utils.astra_db_manager import AstraDBManager

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """
    Handles the processing of course materials into chunks for retrieval.
    
    This class coordinates the document processing pipeline:
    1. Extract text from various document formats
    2. Chunk text into retrievable segments
    3. Add metadata to chunks
    4. Prepare chunks for embedding and storage in AstraDB
    """
    
    def __init__(self):
        """Initialize the document processor and file handlers"""
        self.chunker = Chunker()
        self.astra_manager = AstraDBManager()
        
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
    
    async def process_document_for_astra(
        self,
        file_content: bytes,
        filename: str,
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        Process a document and store chunks directly in AstraDB.
        
        Args:
            file_content: Binary content of the file
            filename: Name of the file
            metadata: Additional metadata about the file
            collection_name: Optional name for the collection
            
        Returns:
            Tuple of (list of chunk IDs, document metadata)
        """
        try:
            # Process document to get chunks
            chunks, doc_metadata = await self.process_document(
                file_content=file_content,
                filename=filename,
                metadata=metadata
            )
            
            # Connect to AstraDB
            if not collection_name:
                collection_name = settings.ASTRA_DB_COLLECTION or "course_materials"
            
            db = self.astra_manager.connect()
            collection = self.astra_manager.get_or_create_collection(collection_name)
            
            # Prepare documents for insertion
            documents = []
            for chunk in chunks:
                content = chunk["content"]
                chunk_metadata = chunk["metadata"]
                
                # Create document structure with vectorization text
                document = {
                    "_id": chunk["id"],
                    "content": content,
                    "metadata": chunk_metadata,
                    "$vectorize": self._create_vectorization_text(content, chunk_metadata)
                }
                documents.append(document)
            
            # Insert documents
            result = self.astra_manager.insert_documents(collection, documents)
            
            logger.info(f"Processed and stored document {filename} with {len(result.inserted_ids)} chunks in AstraDB")
            return result.inserted_ids, doc_metadata
            
        except Exception as e:
            logger.error(f"Error processing document for AstraDB {filename}: {str(e)}")
            raise DocumentProcessingException(f"Failed to process document for AstraDB {filename}: {str(e)}")
    
    def _create_vectorization_text(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Create text that will be converted to vector embedding.
        
        Args:
            content: Document content
            metadata: Document metadata
            
        Returns:
            str: Text to be vectorized
        """
        # Get relevant metadata for context 
        course_name = metadata.get("course_name", "")
        course_id = metadata.get("course_id", "")
        source = metadata.get("source", "")
        heading = metadata.get("heading", "")
        chunk_type = metadata.get("chunk_type", "")
        
        # Combine content with relevant metadata for better semantic search
        vectorize_text = f"Course: {course_name} ({course_id})\nSource: {source}\nHeading: {heading}\nType: {chunk_type}\nContent: {content}"
        return vectorize_text
    
    async def _extract_text(
        self,
        file_content: bytes,
        filename: str,
        mime_type: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from a document based on its type.
        
        Args:
            file_content: Binary content of the file
            filename: Name of the file
            mime_type: MIME type of the file
            
        Returns:
            Tuple of (extracted text, document metadata)
        """
        # Initialize metadata
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
    
    async def process_directory_for_astra(
        self,
        directory_path: str,
        metadata: Dict[str, Any],
        collection_name: Optional[str] = None
    ) -> List[str]:
        """
        Process all documents in a directory and store in AstraDB.
        
        Args:
            directory_path: Path to the directory containing documents
            metadata: Metadata to apply to all documents
            collection_name: Optional name for the collection
            
        Returns:
            List of all chunk IDs
        """
        all_chunk_ids = []
        
        try:
            # Connect to AstraDB
            if not collection_name:
                collection_name = settings.ASTRA_DB_COLLECTION or "course_materials"
            
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
                    
                    chunk_ids, _ = await self.process_document_for_astra(
                        file_content=file_content,
                        filename=rel_path,  # Use relative path as filename
                        metadata=file_metadata,
                        collection_name=collection_name
                    )
                    
                    all_chunk_ids.extend(chunk_ids)
            
            logger.info(f"Processed and stored {len(all_chunk_ids)} chunks from directory {directory_path} in AstraDB")
            return all_chunk_ids
            
        except Exception as e:
            logger.error(f"Error processing directory for AstraDB {directory_path}: {str(e)}")
            raise DocumentProcessingException(f"Failed to process directory for AstraDB {directory_path}: {str(e)}")
    
    async def process_directory(
        self,
        directory_path: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Process all documents in a directory.
        
        Args:
            directory_path: Path to the directory containing documents
            metadata: Metadata to apply to all documents
            
        Returns:
            List of all document chunks
        """
        all_chunks = []
        
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
                    
                    chunks, _ = await self.process_document(
                        file_content=file_content,
                        filename=rel_path,  # Use relative path as filename
                        metadata=file_metadata
                    )
                    
                    all_chunks.extend(chunks)
            
            logger.info(f"Processed {len(all_chunks)} chunks from directory {directory_path}")
            return all_chunks
            
        except Exception as e:
            logger.error(f"Error processing directory {directory_path}: {str(e)}")
            raise DocumentProcessingException(f"Failed to process directory {directory_path}: {str(e)}")
    
    def _is_supported_file(self, filename: str) -> bool:
        """
        Check if a file is supported for processing.
        
        Args:
            filename: Name of the file
            
        Returns:
            True if the file is supported, False otherwise
        """
        # List of supported extensions
        supported_extensions = [
            ".pdf", ".txt", ".md", ".pptx", ".ppt",
            ".ipynb", ".py", ".js", ".java", ".cpp", 
            ".sql", ".r", ".cs", ".html", ".csv"
        ]
        
        # Check if the file has a supported extension
        return any(filename.lower().endswith(ext) for ext in supported_extensions)