# app/rag/chunker.py
import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class TextChunker:
    """
    Service for chunking text into manageable pieces for embedding
    """
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        """
        Initialize the chunker with customizable chunk size and overlap
        
        Args:
            chunk_size: Maximum size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks
        
        Args:
            text: Text to chunk
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text or len(text.strip()) == 0:
            return []
        
        # Normalize whitespace
        text = self._normalize_whitespace(text)
        
        # Add logging for text length
        logger.info(f"Text length: {len(text)} characters")
        logger.info(f"Chunking with size: {self.chunk_size}, overlap: {self.chunk_overlap}")
        
        # Split into paragraphs
        paragraphs = self._split_into_paragraphs(text)
        
        # Add logging for paragraph stats
        logger.info(f"Number of paragraphs: {len(paragraphs)}")
        if paragraphs:
            logger.info(f"Average paragraph length: {sum(len(p) for p in paragraphs) / max(1, len(paragraphs))}")
        
        # Create chunks
        chunks = self._create_chunks_from_paragraphs(paragraphs)
        
        # Add logging for chunk count
        logger.info(f"Created {len(chunks)} chunks")
        
        return chunks
    
    def _normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace in text
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Replace multiple newlines with double newline
        text = re.sub(r'\n+', '\n\n', text)
        
        return text.strip()
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """
        Split text into paragraphs
        
        Args:
            text: Text to split
            
        Returns:
            List of paragraphs
        """
        # Split by double newline
        paragraphs = re.split(r'\n\n', text)
        
        # Filter out empty paragraphs
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        return paragraphs
    
    def _create_chunks_from_paragraphs(self, paragraphs: List[str]) -> List[Dict[str, Any]]:
        """
        Create overlapping chunks from paragraphs
        
        Args:
            paragraphs: List of paragraphs
            
        Returns:
            List of chunk dictionaries
        """
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # If adding this paragraph would exceed chunk size, finalize the current chunk
            if len(current_chunk) + len(paragraph) > self.chunk_size and current_chunk:
                chunks.append({"text": current_chunk.strip()})
                
                # Start new chunk with overlap
                words = current_chunk.split()
                overlap_size = 0
                overlap_text = ""
                
                # Calculate overlap
                for word in reversed(words):
                    if overlap_size + len(word) + 1 > self.chunk_overlap:
                        break
                    overlap_text = word + " " + overlap_text
                    overlap_size += len(word) + 1
                
                current_chunk = overlap_text
            
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph
        
        # Add the last chunk if not empty
        if current_chunk.strip():
            chunks.append({"text": current_chunk.strip()})
        
        return chunks