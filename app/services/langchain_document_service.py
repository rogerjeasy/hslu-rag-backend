# app/services/langchain_document_service.py
import os
import logging
import re
from typing import List, Dict, Any, Optional, Tuple

from langchain.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    UnstructuredExcelLoader,
    CSVLoader,
    TextLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

logger = logging.getLogger(__name__)

class LangchainDocumentService:
    """Service for loading and processing documents using LangChain"""
    
    def __init__(self):
        """Initialize document service"""
        pass
    
    async def process_document(
        self, 
        file_path: str, 
        file_type: str,
        chunk_size: int = 500,
        chunk_overlap: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Process a document: load, extract text, and split into chunks.
        
        Args:
            file_path: Path to the document
            file_type: Type of the document (pdf, docx, etc.)
            chunk_size: Size of each chunk in characters
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of dictionaries with text chunks and metadata
        """
        try:
            # Load document and extract text
            documents = await self._load_document(file_path, file_type)
            
            # Clean up text content
            cleaned_documents = self._clean_documents(documents)
            
            # Split into chunks
            chunks = await self._split_documents(cleaned_documents, chunk_size, chunk_overlap)
            
            # Convert to dictionaries
            return self._convert_to_dicts(chunks)
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}")
            raise ValueError(f"Failed to process document: {str(e)}")
    
    async def _load_document(self, file_path: str, file_type: str) -> List[Document]:
        """
        Load a document using the appropriate LangChain loader.
        
        Args:
            file_path: Path to the document
            file_type: Type of the document
            
        Returns:
            List of LangChain Document objects
        """
        try:
            # Select loader based on file type
            if file_type.lower() in ["pdf"]:
                loader = PyPDFLoader(file_path)
            elif file_type.lower() in ["docx", "doc"]:
                loader = Docx2txtLoader(file_path)
            elif file_type.lower() in ["pptx", "ppt"]:
                loader = UnstructuredPowerPointLoader(file_path)
            elif file_type.lower() in ["xlsx", "xls"]:
                loader = UnstructuredExcelLoader(file_path)
            elif file_type.lower() in ["csv"]:
                loader = CSVLoader(file_path)
            elif file_type.lower() in ["txt", "py", "js", "html", "css", "md", "json"]:
                loader = TextLoader(file_path, encoding="utf-8")
            else:
                # Default to text loader for unknown types
                logger.warning(f"Unknown file type: {file_type}, using text loader")
                loader = TextLoader(file_path, encoding="utf-8")
            
            # Load the document
            documents = loader.load()
            
            # If no documents were loaded, raise an error
            if not documents:
                raise ValueError(f"No content was extracted from {file_path}")
                
            logger.info(f"Loaded {len(documents)} document pages/sections")
            return documents
            
        except Exception as e:
            logger.error(f"Error loading document {file_path}: {str(e)}")
            raise ValueError(f"Failed to load document: {str(e)}")
    
    def _clean_documents(self, documents: List[Document]) -> List[Document]:
        """
        Clean document content to ensure proper text.
        
        Args:
            documents: List of LangChain Document objects
            
        Returns:
            List of cleaned Document objects
        """
        cleaned_docs = []
        
        for doc in documents:
            # Clean content
            cleaned_content = self._clean_text(doc.page_content)
            
            # Create new document with clean content and original metadata
            cleaned_doc = Document(
                page_content=cleaned_content,
                metadata=doc.metadata
            )
            
            # Only add if document has meaningful content
            if cleaned_content.strip():
                cleaned_docs.append(cleaned_doc)
        
        return cleaned_docs
    
    def _clean_text(self, text: str) -> str:
        """
        Clean text to ensure it's properly encoded.
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        try:
            # Force re-encoding to clean up text
            text = text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            
            # Remove non-printable characters except newlines, tabs, and spaces
            text = re.sub(r'[^\x20-\x7E\x0A\x0D\x09\xA0-\xFF]', '', text)
            
            # Replace multiple spaces with single space
            text = re.sub(r' +', ' ', text)
            
            # Replace multiple newlines with maximum two newlines
            text = re.sub(r'\n{3,}', '\n\n', text)
            
            return text.strip()
        except Exception as e:
            logger.warning(f"Error cleaning text: {str(e)}")
            return ""
    
    async def _split_documents(
        self, 
        documents: List[Document], 
        chunk_size: int, 
        chunk_overlap: int
    ) -> List[Document]:
        """
        Split documents into smaller chunks.
        
        Args:
            documents: List of Document objects
            chunk_size: Size of each chunk
            chunk_overlap: Overlap between chunks
            
        Returns:
            List of Document chunks
        """
        try:
            # Create text splitter
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n", "\n", ". ", " ", ""],
                length_function=len
            )
            
            # Split documents
            chunks = splitter.split_documents(documents)
            
            logger.info(f"Split {len(documents)} documents into {len(chunks)} chunks")
            return chunks
        except Exception as e:
            logger.error(f"Error splitting documents: {str(e)}")
            raise ValueError(f"Failed to split documents: {str(e)}")
    
    def _convert_to_dicts(self, chunks: List[Document]) -> List[Dict[str, Any]]:
        """
        Convert LangChain Document chunks to dictionaries.
        
        Args:
            chunks: List of Document chunks
            
        Returns:
            List of dictionaries with text and metadata
        """
        result = []
        
        for i, chunk in enumerate(chunks):
            # Get page number from metadata if available
            page_number = None
            if chunk.metadata and "page" in chunk.metadata:
                page_number = chunk.metadata["page"]
            
            # Clean the content again to be safe
            clean_content = self._clean_text(chunk.page_content)
            
            # Only add if chunk has content
            if clean_content.strip():
                result.append({
                    "text": clean_content,
                    "metadata": chunk.metadata,
                    "page_number": page_number,
                    "chunk_index": i
                })
        
        return result