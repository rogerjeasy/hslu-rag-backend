import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Callable
import langchain
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter, 
    MarkdownTextSplitter,
    PythonCodeTextSplitter,
    LatexTextSplitter
)
from langchain.docstore.document import Document

logger = logging.getLogger(__name__)

class EnhancedTextChunker:
    """
    Enhanced service for chunking text into manageable pieces for embedding
    with LangChain integration
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
        
        # Initialize specialized text splitters
        self.general_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len
        )
        
        self.markdown_splitter = MarkdownTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        self.code_splitter = PythonCodeTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        self.latex_splitter = LatexTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    
    def chunk_text(self, text: str, file_type: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks intelligently based on document structure
        
        Args:
            text: Text to chunk
            file_type: Optional file type to influence chunking strategy
            metadata: Optional metadata to attach to each chunk
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text or len(text.strip()) == 0:
            logger.warning("Received empty text for chunking")
            return []
        
        # Normalize whitespace
        text = self._normalize_whitespace(text)
        
        # Add logging for text length
        logger.info(f"Text length: {len(text)} characters")
        logger.info(f"Chunking with size: {self.chunk_size}, overlap: {self.chunk_overlap}")
        
        # Choose the appropriate chunking strategy based on file type
        chunks = self._select_chunking_strategy(text, file_type, metadata or {})
        
        # Add logging for chunk count
        logger.info(f"Created {len(chunks)} chunks")
        
        return chunks
    
    def chunk_langchain_documents(self, text: str, metadata: Dict[str, Any], file_type: Optional[str] = None) -> List[Document]:
        """
        Split text into LangChain Document objects with appropriate chunking
        
        Args:
            text: Text to chunk
            metadata: Metadata to attach to each document
            file_type: Optional file type to influence chunking strategy
            
        Returns:
            List of LangChain Document objects
        """
        if not text or len(text.strip()) == 0:
            logger.warning("Received empty text for LangChain document chunking")
            return []
        
        # Create initial document
        doc = Document(page_content=text, metadata=metadata)
        
        # Split based on file type
        if file_type and file_type.lower() in ['md', 'markdown']:
            return self.markdown_splitter.split_documents([doc])
        elif file_type and file_type.lower() in ['py', 'js', 'ts', 'java', 'cpp', 'c']:
            return self.code_splitter.split_documents([doc])
        elif file_type and file_type.lower() in ['tex', 'latex']:
            return self.latex_splitter.split_documents([doc])
        else:
            return self.general_splitter.split_documents([doc])
    
    def _select_chunking_strategy(self, text: str, file_type: Optional[str], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Select and apply the appropriate chunking strategy based on content and file type
        
        Args:
            text: Text to chunk
            file_type: Optional file type hint
            metadata: Metadata to attach to chunks
            
        Returns:
            List of chunk dictionaries
        """
        # Detect if text is code
        is_code = self._is_code(text, file_type)
        
        # Detect if text is markdown
        is_markdown = self._is_markdown(text, file_type)
        
        # Detect if text contains mathematical notation
        has_math = self._has_mathematical_notation(text)
        
        # Choose strategy based on content type
        if is_code:
            logger.info("Using code-aware chunking strategy")
            return self._chunk_code(text, metadata)
        elif is_markdown:
            logger.info("Using markdown-aware chunking strategy")
            return self._chunk_markdown(text, metadata)
        elif has_math:
            logger.info("Using math-aware chunking strategy")
            return self._chunk_with_math_preservation(text, metadata)
        else:
            logger.info("Using semantic paragraph chunking strategy")
            return self._chunk_semantic_paragraphs(text, metadata)
    
    def _is_code(self, text: str, file_type: Optional[str]) -> bool:
        """
        Detect if text is primarily code based on content and file type
        
        Args:
            text: Text to analyze
            file_type: Optional file type hint
            
        Returns:
            Boolean indicating if text is code
        """
        # Check file extension first
        code_extensions = ['py', 'js', 'ts', 'java', 'c', 'cpp', 'php', 'rb', 'go', 'rust', 'scala', 'cs']
        if file_type and file_type.lower() in code_extensions:
            return True
        
        # Count code indicators
        code_lines = 0
        total_lines = 0
        
        # Common code patterns
        code_patterns = [
            r'^\s*def\s+\w+\s*\(.*\)\s*:',  # Python function
            r'^\s*function\s+\w+\s*\(.*\)\s*{',  # JavaScript function
            r'^\s*class\s+\w+',  # Class definition
            r'^\s*import\s+[\w\s,{}]+\s+from\s+',  # Import statement
            r'^\s*for\s+\w+\s+in\s+',  # For loop
            r'^\s*if\s+.+:',  # If statement
            r'^\s*while\s+.+:',  # While loop
            r'^\s*return\s+',  # Return statement
            r'^\s*[{}]\s*$',  # Braces on their own line
            r'^\s*public\s+static\s+void\s+',  # Java method
        ]
        
        for line in text.split('\n'):
            total_lines += 1
            if any(re.match(pattern, line) for pattern in code_patterns):
                code_lines += 1
        
        # If more than 25% of lines match code patterns, consider it code
        if total_lines > 0 and (code_lines / total_lines) > 0.25:
            return True
        
        return False
    
    def _is_markdown(self, text: str, file_type: Optional[str]) -> bool:
        """
        Detect if text is markdown
        
        Args:
            text: Text to analyze
            file_type: Optional file type hint
            
        Returns:
            Boolean indicating if text is markdown
        """
        # Check file extension first
        if file_type and file_type.lower() in ['md', 'markdown']:
            return True
        
        # Count markdown indicators
        markdown_patterns = [
            r'^#+\s+',  # Headers
            r'^\s*[-*+]\s+',  # List items
            r'^\s*\d+\.\s+',  # Numbered lists
            r'^\s*>\s+',  # Blockquotes
            r'\[.+\]\(.+\)',  # Links
            r'!\[.+\]\(.+\)',  # Images
            r'`{1,3}[^`]+`{1,3}',  # Code blocks
            r'^---\s*$',  # Horizontal rules
            r'\*\*[^*]+\*\*',  # Bold
            r'_[^_]+_',  # Italic
        ]
        
        markdown_matches = 0
        for pattern in markdown_patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            markdown_matches += len(matches)
        
        # If we have a significant number of markdown patterns, consider it markdown
        if len(text) > 0 and (markdown_matches / len(text.split('\n'))) > 0.15:
            return True
        
        return False
    
    def _has_mathematical_notation(self, text: str) -> bool:
        """
        Detect if text contains mathematical notation
        
        Args:
            text: Text to analyze
            
        Returns:
            Boolean indicating if text has math notation
        """
        # Look for LaTeX-style math delimiters
        math_patterns = [
            r'\$\$.+?\$\$',  # Display math
            r'\$.+?\$',  # Inline math
            r'\\begin\{equation\}',  # Equation environment
            r'\\begin\{align\}',  # Align environment
            r'\\frac\{',  # Fractions
            r'\\sum_\{',  # Summation
            r'\\int_\{',  # Integrals
        ]
        
        for pattern in math_patterns:
            if re.search(pattern, text, re.DOTALL):
                return True
        
        return False
    
    def _chunk_code(self, code: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk code intelligently by preserving function and class definitions
        
        Args:
            code: Code to chunk
            metadata: Metadata to attach to chunks
            
        Returns:
            List of chunk dictionaries
        """
        chunks = []
        
        # Use LangChain Python code splitter
        splitter = PythonCodeTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        
        # Create Document
        doc = Document(page_content=code, metadata=metadata)
        
        # Split
        split_docs = splitter.split_documents([doc])
        
        # Convert to chunks
        for i, doc in enumerate(split_docs):
            chunks.append({
                "text": doc.page_content,
                "metadata": {
                    **doc.metadata,
                    "chunk_index": i,
                    "total_chunks": len(split_docs),
                    "chunk_type": "code",
                    "chunk_text_preview": doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
                }
            })
        
        return chunks
    
    def _chunk_markdown(self, markdown: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk markdown intelligently by preserving headers
        
        Args:
            markdown: Markdown to chunk
            metadata: Metadata to attach to chunks
            
        Returns:
            List of chunk dictionaries
        """
        chunks = []
        
        # Use LangChain Markdown splitter
        splitter = MarkdownTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        
        # Create Document
        doc = Document(page_content=markdown, metadata=metadata)
        
        # Split
        split_docs = splitter.split_documents([doc])
        
        # Convert to chunks
        for i, doc in enumerate(split_docs):
            # Extract title from markdown if possible
            title = None
            lines = doc.page_content.split('\n')
            for line in lines:
                if line.startswith('#'):
                    title = line.strip('# ')
                    break
            
            chunks.append({
                "text": doc.page_content,
                "metadata": {
                    **doc.metadata,
                    "chunk_index": i,
                    "total_chunks": len(split_docs),
                    "chunk_type": "markdown",
                    "chunk_title": title or f"Section {i+1}",
                    "chunk_text_preview": doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
                }
            })
        
        return chunks
    
    def _chunk_with_math_preservation(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk text with mathematical notation, preserving math blocks
        
        Args:
            text: Text to chunk
            metadata: Metadata to attach to chunks
            
        Returns:
            List of chunk dictionaries
        """
        chunks = []
        
        # Use LangChain LaTeX splitter
        splitter = LatexTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        
        # Create Document
        doc = Document(page_content=text, metadata=metadata)
        
        # Split
        split_docs = splitter.split_documents([doc])
        
        # Convert to chunks
        for i, doc in enumerate(split_docs):
            chunks.append({
                "text": doc.page_content,
                "metadata": {
                    **doc.metadata,
                    "chunk_index": i,
                    "total_chunks": len(split_docs),
                    "chunk_type": "math_text",
                    "chunk_text_preview": doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
                }
            })
        
        return chunks
    
    def _chunk_semantic_paragraphs(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk general text by semantic paragraphs
        
        Args:
            text: Text to chunk
            metadata: Metadata to attach to chunks
            
        Returns:
            List of chunk dictionaries
        """
        # Split paragraphs first
        paragraphs = self._split_into_paragraphs(text)
        
        # Create chunks from paragraphs
        chunks = []
        current_chunk = ""
        current_paragraphs = []
        
        for paragraph in paragraphs:
            # If adding this paragraph would exceed chunk size, finalize the current chunk
            if len(current_chunk) + len(paragraph) > self.chunk_size and current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "metadata": {
                        **metadata,
                        "chunk_index": len(chunks),
                        "chunk_paragraphs": current_paragraphs,
                        "chunk_text_preview": current_chunk[:100] + "..." if len(current_chunk) > 100 else current_chunk
                    }
                })
                
                # Start new chunk with overlap
                # Create overlap by taking the last paragraph(s) up to overlap size
                overlap_text = ""
                overlap_paragraphs = []
                
                for p in reversed(current_paragraphs):
                    if len(overlap_text) + len(p) <= self.chunk_overlap:
                        overlap_text = p + "\n\n" + overlap_text
                        overlap_paragraphs.insert(0, p)
                    else:
                        break
                
                current_chunk = overlap_text
                current_paragraphs = overlap_paragraphs
            
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph
            
            current_paragraphs.append(paragraph)
        
        # Add the last chunk if not empty
        if current_chunk.strip():
            chunks.append({
                "text": current_chunk.strip(),
                "metadata": {
                    **metadata,
                    "chunk_index": len(chunks),
                    "chunk_paragraphs": current_paragraphs,
                    "chunk_text_preview": current_chunk[:100] + "..." if len(current_chunk) > 100 else current_chunk
                }
            })
        
        # Update total chunks
        for i, chunk in enumerate(chunks):
            chunk["metadata"]["total_chunks"] = len(chunks)
            chunk["metadata"]["chunk_type"] = "paragraph"
        
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
    
    def _get_chunk_title(self, text: str) -> str:
        """
        Extract a meaningful title from text
        
        Args:
            text: Text to analyze
            
        Returns:
            Extracted title or default
        """
        # Try to find a header or first sentence
        lines = text.split('\n')
        for line in lines:
            # Check for markdown headers
            if line.startswith('#'):
                return line.lstrip('#').strip()
            
            # Check for other heading patterns
            if line.strip() and not line.startswith('- ') and not line.startswith('* '):
                # If line is short enough to be a title
                if len(line.strip()) <= 100:
                    return line.strip()
        
        # If no header, use first sentence
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if sentences and sentences[0].strip():
            first_sentence = sentences[0].strip()
            # Truncate if too long
            if len(first_sentence) > 100:
                return first_sentence[:97] + "..."
            return first_sentence
        
        # Fallback
        return "Section"