import logging
import re
import uuid
from typing import Dict, List, Any, Optional

from app.core.config import settings
from app.core.exceptions import DocumentProcessingException

logger = logging.getLogger(__name__)

class Chunker:
    """
    Handles chunking of document text into retrievable segments.
    
    This class implements various chunking strategies to divide
    document text into optimal chunks for retrieval.
    """
    
    def __init__(self):
        """Initialize the chunker with configuration settings"""
        self.chunk_size = settings.CHUNK_SIZE  # Token/character size for each chunk
        self.chunk_overlap = settings.CHUNK_OVERLAP  # Overlap between chunks
    
    async def chunk_text(
        self,
        text: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Chunk text into retrievable segments.
        
        Args:
            text: The text to chunk
            metadata: Metadata to include with each chunk
            
        Returns:
            List of chunks with metadata
        """
        try:
            # Determine the best chunking strategy based on content
            if self._is_code_content(metadata):
                chunks = self._chunk_by_function(text, metadata)
            elif self._is_slide_content(metadata):
                chunks = self._chunk_by_slide(text, metadata)
            elif self._is_structured_with_headings(text):
                chunks = self._chunk_by_heading(text, metadata)
            else:
                # Default to fixed-size chunking with paragraph sensitivity
                chunks = self._chunk_by_paragraph(text, metadata)
            
            # Ensure all chunks have IDs
            for chunk in chunks:
                if "id" not in chunk:
                    chunk["id"] = str(uuid.uuid4())
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error chunking text: {str(e)}")
            raise DocumentProcessingException(f"Failed to chunk text: {str(e)}")
    
    def _is_code_content(self, metadata: Dict[str, Any]) -> bool:
        """Check if content is code based on metadata"""
        mime_type = metadata.get("mime_type", "")
        filename = metadata.get("filename", "")
        
        code_mime_types = ["text/x-python", "text/javascript", "application/json"]
        code_extensions = [".py", ".js", ".java", ".cpp", ".sql", ".r", ".cs", ".ipynb"]
        
        return (
            any(mime_type.startswith(type) for type in code_mime_types) or
            any(filename.endswith(ext) for ext in code_extensions) or
            metadata.get("content_type") == "code"
        )
    
    def _is_slide_content(self, metadata: Dict[str, Any]) -> bool:
        """Check if content is from presentation slides"""
        mime_type = metadata.get("mime_type", "")
        filename = metadata.get("filename", "")
        
        slide_mime_types = [
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint"
        ]
        slide_extensions = [".pptx", ".ppt"]
        
        return (
            any(mime_type == type for type in slide_mime_types) or
            any(filename.endswith(ext) for ext in slide_extensions) or
            metadata.get("content_type") == "slides"
        )
    
    def _is_structured_with_headings(self, text: str) -> bool:
        """Check if text has clear heading structure"""
        # Pattern to match markdown-style headings (# Heading) or numbered headings (1. Heading)
        heading_pattern = r"(?:^|\n)(?:#{1,6} |(?:\d+\.)+\s+)[A-Z]"
        
        # Count potential headings
        headings = re.findall(heading_pattern, text)
        
        # If we find multiple headings, consider it structured
        return len(headings) > 2
    
    def _chunk_by_function(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk code by function/class definitions.
        
        This method attempts to keep code functions and classes together
        in the same chunk when possible.
        """
        chunks = []
        
        # Common patterns for function/class definitions across languages
        patterns = [
            r"(?:^|\n)(?:def|class)\s+\w+\s*\([^)]*\)\s*:",  # Python
            r"(?:^|\n)(?:function|class)\s+\w+\s*\([^)]*\)\s*{",  # JavaScript
            r"(?:^|\n)(?:public|private|protected)?\s+(?:static\s+)?(?:class|interface|enum)\s+\w+",  # Java/C#
            r"(?:^|\n)(?:public|private|protected)?\s+(?:static\s+)?(?:\w+\s+)+\w+\s*\([^)]*\)\s*{",  # Java/C# methods
        ]
        
        # If no matches, fall back to paragraph chunking
        matches = []
        for pattern in patterns:
            matches.extend([(m.start(), m.group()) for m in re.finditer(pattern, text)])
        
        if not matches:
            return self._chunk_by_paragraph(text, metadata)
        
        # Sort matches by position
        matches.sort(key=lambda x: x[0])
        
        # Process each match
        current_pos = 0
        for i, (pos, match) in enumerate(matches):
            # Determine the end of the current chunk
            if i < len(matches) - 1:
                next_pos = matches[i + 1][0]
            else:
                next_pos = len(text)
            
            # Extract the chunk
            if pos > current_pos:
                # Add any text before the first match
                if i == 0 and pos > 0:
                    chunk_text = text[current_pos:pos]
                    if len(chunk_text.strip()) > 0:
                        chunks.append({
                            "id": str(uuid.uuid4()),
                            "content": chunk_text,
                            "metadata": {**metadata, "chunk_type": "code_header"}
                        })
                
                # Add the function/class definition and its body
                chunk_text = text[pos:next_pos]
                if len(chunk_text.strip()) > 0:
                    # Try to extract the function/class name for better identification
                    name_match = re.search(r"(?:def|class|function)\s+(\w+)", chunk_text)
                    chunk_type = "code_function"
                    chunk_name = name_match.group(1) if name_match else ""
                    
                    chunk_metadata = {
                        **metadata,
                        "chunk_type": chunk_type
                    }
                    
                    if chunk_name:
                        chunk_metadata["function_name"] = chunk_name
                    
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": chunk_text,
                        "metadata": chunk_metadata
                    })
            
            current_pos = next_pos
        
        # Add any remaining text
        if current_pos < len(text):
            chunk_text = text[current_pos:]
            if len(chunk_text.strip()) > 0:
                chunks.append({
                    "id": str(uuid.uuid4()),
                    "content": chunk_text,
                    "metadata": {**metadata, "chunk_type": "code_footer"}
                })
        
        return chunks
    
    def _chunk_by_slide(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk presentation slides by individual slides.
        
        Slides are typically already pre-chunked during extraction with
        clear slide markers.
        """
        chunks = []
        
        # Pattern to identify slide boundaries
        # This assumes slides are separated with a marker like "--- Slide 1 ---"
        slide_pattern = r"(?:^|\n)[-=]{3,}\s*Slide\s+(\d+)\s*[-=]{3,}"
        
        # Split by slide markers
        slide_parts = re.split(slide_pattern, text)
        
        # Process parts - first part might be header information
        if len(slide_parts) <= 1:
            # If no slide markers found, chunk by paragraphs
            return self._chunk_by_paragraph(text, metadata)
        
        # First part might be header information
        header = slide_parts[0]
        if header.strip():
            chunks.append({
                "id": str(uuid.uuid4()),
                "content": header,
                "metadata": {**metadata, "chunk_type": "slide_header"}
            })
        
        # Process slides
        for i in range(1, len(slide_parts), 2):
            if i + 1 < len(slide_parts):
                slide_num = slide_parts[i]
                slide_content = slide_parts[i + 1]
                
                if slide_content.strip():
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": slide_content,
                        "metadata": {
                            **metadata,
                            "chunk_type": "slide",
                            "slide_number": slide_num
                        }
                    })
        
        return chunks
    
    def _chunk_by_heading(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk text by headings to keep related content together.
        
        This method tries to identify document sections by headings
        and creates chunks that respect these logical divisions.
        """
        chunks = []
        
        # Pattern to match markdown-style headings (# Heading) or numbered headings (1. Heading)
        heading_pattern = r"(?:^|\n)((?:#{1,6}|\d+\.(?:\d+\.)*)\s+[^\n]+)"
        
        # Find all headings with their positions
        headings = [(m.start(), m.group()) for m in re.finditer(heading_pattern, text)]
        
        if not headings:
            return self._chunk_by_paragraph(text, metadata)
        
        # Process each section
        current_pos = 0
        current_heading = ""
        current_heading_level = 0
        
        for i, (pos, heading) in enumerate(headings):
            # Determine heading level
            if heading.startswith('#'):
                level = len(re.match(r"#+", heading).group())
            else:
                level = heading.count('.') + 1
            
            # If this is the first heading, add text before it
            if i == 0 and pos > 0:
                chunk_text = text[0:pos]
                if len(chunk_text.strip()) > 0:
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": chunk_text,
                        "metadata": {**metadata, "chunk_type": "pre_heading"}
                    })
            
            # If not the first heading, add the previous section
            elif i > 0:
                # Get section text
                section_text = text[current_pos:pos]
                
                if len(section_text.strip()) > 0:
                    # Add section with its heading
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": current_heading + "\n" + section_text,
                        "metadata": {
                            **metadata,
                            "chunk_type": "section",
                            "heading": current_heading.strip(),
                            "heading_level": current_heading_level
                        }
                    })
            
            # Update current position and heading
            current_pos = pos
            current_heading = heading
            current_heading_level = level
            
            # If heading plus section would be too large, create separate heading chunk
            if len(heading) > self.chunk_size / 2:
                chunks.append({
                    "id": str(uuid.uuid4()),
                    "content": heading,
                    "metadata": {**metadata, "chunk_type": "heading_only", "heading_level": level}
                })
                current_pos += len(heading)
                current_heading = ""
        
        # Add the last section
        if current_pos < len(text):
            final_section = text[current_pos:]
            if len(final_section.strip()) > 0:
                if current_heading:
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": current_heading + "\n" + final_section,
                        "metadata": {
                            **metadata,
                            "chunk_type": "section",
                            "heading": current_heading.strip(),
                            "heading_level": current_heading_level
                        }
                    })
                else:
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": final_section,
                        "metadata": {**metadata, "chunk_type": "final_section"}
                    })
        
        return chunks
    
    def _chunk_by_paragraph(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk text by paragraphs with a maximum chunk size.
        
        This method respects paragraph boundaries while ensuring 
        that chunks don't exceed the maximum size.
        """
        chunks = []
        
        # Split the text into paragraphs
        paragraphs = re.split(r"\n\s*\n", text)
        
        current_chunk = []
        current_chunk_size = 0
        
        for paragraph in paragraphs:
            paragraph_clean = paragraph.strip()
            if not paragraph_clean:
                continue
            
            # Rough estimate of paragraph size (characters as proxy for tokens)
            paragraph_size = len(paragraph_clean)
            
            # If adding this paragraph would exceed the chunk size,
            # and we already have content, create a new chunk
            if current_chunk_size + paragraph_size > self.chunk_size and current_chunk:
                # Join the accumulated paragraphs
                chunk_text = "\n\n".join(current_chunk)
                chunks.append({
                    "id": str(uuid.uuid4()),
                    "content": chunk_text,
                    "metadata": {**metadata, "chunk_type": "paragraph_group"}
                })
                
                # Start a new chunk, possibly with overlap
                if self.chunk_overlap > 0 and len(current_chunk) > 1:
                    # Keep the last paragraph for overlap
                    current_chunk = [current_chunk[-1]]
                    current_chunk_size = len(current_chunk[0])
                else:
                    current_chunk = []
                    current_chunk_size = 0
            
            # Handle very large paragraphs (exceeding chunk size)
            if paragraph_size > self.chunk_size:
                # If we have accumulated content, save it first
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": chunk_text,
                        "metadata": {**metadata, "chunk_type": "paragraph_group"}
                    })
                    current_chunk = []
                    current_chunk_size = 0
                
                # Split the large paragraph into fixed-size chunks
                for i in range(0, paragraph_size, self.chunk_size - self.chunk_overlap):
                    # Adjust end position, ensuring we don't go out of bounds
                    end_pos = min(i + self.chunk_size, paragraph_size)
                    
                    chunk_text = paragraph_clean[i:end_pos]
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": chunk_text,
                        "metadata": {**metadata, "chunk_type": "large_paragraph_segment"}
                    })
                    
                    # If we've covered the paragraph, break
                    if end_pos == paragraph_size:
                        break
            else:
                # Add the paragraph to the current chunk
                current_chunk.append(paragraph_clean)
                current_chunk_size += paragraph_size
        
        # Add any remaining content
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append({
                "id": str(uuid.uuid4()),
                "content": chunk_text,
                "metadata": {**metadata, "chunk_type": "paragraph_group"}
            })
        
        return chunks