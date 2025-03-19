import logging
import io
from typing import Dict, Tuple, Any, List, Optional
import asyncio
import re

import PyPDF2
from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.layout import LAParams

from app.core.exceptions import DocumentProcessingException

logger = logging.getLogger(__name__)

class PDFProcessor:
    """
    Processes PDF documents to extract text and metadata.
    
    This class handles PDF-specific extraction, including
    page-by-page content and structural information.
    """
    
    async def process(self, file_content: bytes) -> Tuple[str, Dict[str, Any]]:
        """
        Process a PDF file to extract text and metadata.
        
        Args:
            file_content: Binary content of the PDF file
            
        Returns:
            Tuple of (extracted text, PDF metadata)
        """
        try:
            # Run extraction in a thread pool since PDF processing can be CPU-intensive
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, self._extract_pdf_content, file_content
            )
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            raise DocumentProcessingException(f"Failed to process PDF: {str(e)}")
    
    def _extract_pdf_content(self, file_content: bytes) -> Tuple[str, Dict[str, Any]]:
        """
        Extract content and metadata from a PDF file.
        
        This method uses a combination of PyPDF2 for metadata and
        pdfminer for better text extraction.
        
        Args:
            file_content: Binary content of the PDF file
            
        Returns:
            Tuple of (extracted text, PDF metadata)
        """
        pdf_file = io.BytesIO(file_content)
        
        # Extract metadata using PyPDF2
        metadata = self._extract_metadata(pdf_file)
        
        # Reset file pointer
        pdf_file.seek(0)
        
        # Extract text using pdfminer for better quality
        full_text = ""
        try:
            laparams = LAParams(
                line_margin=0.5,  # Adjust for better line detection
                char_margin=2.0,  # Adjust for better character grouping
                word_margin=0.1,  # Adjust for better word detection
                boxes_flow=0.5,   # Adjust for better text box detection
                detect_vertical=True  # Better handling of vertical text
            )
            
            # Extract text with page markers for better chunking later
            full_text = pdfminer_extract_text(pdf_file, laparams=laparams)
            
            # If pdfminer fails to extract text, try PyPDF2 as backup
            if not full_text.strip():
                full_text = self._extract_text_pypdf2(pdf_file)
            
            # Add page markers if not already present
            if "--- Page" not in full_text:
                full_text = self._add_page_markers(pdf_file, full_text)
        except Exception as e:
            logger.warning(f"Error with pdfminer, falling back to PyPDF2: {str(e)}")
            # Fallback to PyPDF2 if pdfminer fails
            full_text = self._extract_text_pypdf2(pdf_file)
        
        return full_text, metadata
    
    def _extract_metadata(self, pdf_file: io.BytesIO) -> Dict[str, Any]:
        """
        Extract metadata from a PDF file using PyPDF2.
        
        Args:
            pdf_file: BytesIO object containing the PDF
            
        Returns:
            Dictionary of metadata
        """
        reader = PyPDF2.PdfReader(pdf_file)
        
        # Basic PDF properties
        metadata = {
            "num_pages": len(reader.pages),
            "content_type": "pdf"
        }
        
        # Extract document info if available
        if reader.metadata:
            for key, value in reader.metadata.items():
                if value and isinstance(value, (str, int, float, bool)):
                    # Clean up key name (remove slash prefix)
                    clean_key = key.strip("/").lower() if isinstance(key, str) else key
                    metadata[f"pdf_{clean_key}"] = value
        
        # Get PDF outline/bookmarks if available
        outline = self._extract_outline(reader)
        if outline:
            metadata["pdf_outline"] = outline
        
        return metadata
    
    def _extract_outline(self, reader: PyPDF2.PdfReader) -> List[Dict[str, Any]]:
        """
        Extract the document outline (bookmarks) from a PDF.
        
        Args:
            reader: PyPDF2 PdfReader object
            
        Returns:
            List of outline entries (if available)
        """
        outline = []
        
        # This is a simplification; extracting the full outline structure
        # would require recursive processing of the outline tree
        try:
            # Attempt to get outline
            if hasattr(reader, "outline") and reader.outline:
                # Process outline entries
                for entry in reader.outline:
                    if isinstance(entry, dict):
                        # Basic entry
                        title = entry.get("/Title", "")
                        if title:
                            outline_entry = {"title": title}
                            
                            # Try to get page number if available
                            if "/Dest" in entry and isinstance(entry["/Dest"], list) and len(entry["/Dest"]) > 0:
                                dest_obj = entry["/Dest"][0]
                                if hasattr(dest_obj, "get_object_id"):
                                    # Try to map to page number
                                    for i, page in enumerate(reader.pages):
                                        if page.get_object_id() == dest_obj.get_object_id():
                                            outline_entry["page"] = i + 1
                                            break
                            
                            outline.append(outline_entry)
        except Exception as e:
            # Outline extraction can be tricky; don't fail the whole process
            logger.warning(f"Error extracting PDF outline: {str(e)}")
        
        return outline
    
    def _extract_text_pypdf2(self, pdf_file: io.BytesIO) -> str:
        """
        Extract text from a PDF using PyPDF2 (fallback method).
        
        Args:
            pdf_file: BytesIO object containing the PDF
            
        Returns:
            Extracted text with page markers
        """
        reader = PyPDF2.PdfReader(pdf_file)
        full_text = ""
        
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            
            # Add page marker
            if page_text.strip():
                full_text += f"\n\n--- Page {i+1} ---\n\n"
                full_text += page_text
        
        return full_text
    
    def _add_page_markers(self, pdf_file: io.BytesIO, text: str) -> str:
        """
        Add page markers to extracted text if not already present.
        
        This helps maintain page references for citation purposes.
        
        Args:
            pdf_file: BytesIO object containing the PDF
            text: Already extracted text
            
        Returns:
            Text with page markers added
        """
        try:
            # If text is empty or already has page markers, return as is
            if not text.strip() or "--- Page" in text:
                return text
            
            # First, try to identify page boundaries based on common patterns
            page_breaks = re.finditer(r'\f', text)  # Form feed character often indicates page breaks
            
            # If no form feeds found, try estimating page boundaries
            if not list(re.finditer(r'\f', text)):
                # Reset file pointer
                pdf_file.seek(0)
                reader = PyPDF2.PdfReader(pdf_file)
                
                # Get page count
                num_pages = len(reader.pages)
                
                if num_pages <= 1:
                    # Single page document, just add one marker at the beginning
                    return f"--- Page 1 ---\n\n{text}"
                
                # For multi-page documents, try to split text evenly
                # This is a rough approximation that works for some documents
                lines = text.split('\n')
                lines_per_page = max(1, len(lines) // num_pages)
                
                # Insert page markers
                result = []
                for i in range(num_pages):
                    start_line = i * lines_per_page
                    
                    # Add page marker before this section
                    result.append(f"\n\n--- Page {i+1} ---\n\n")
                    
                    # Add lines for this page
                    end_line = (i+1) * lines_per_page if i < num_pages - 1 else len(lines)
                    result.extend(lines[start_line:end_line])
                
                return '\n'.join(result)
            else:
                # Process text with form feed characters
                parts = re.split(r'\f', text)
                result = []
                
                for i, part in enumerate(parts):
                    if part.strip():
                        result.append(f"\n\n--- Page {i+1} ---\n\n")
                        result.append(part)
                
                return ''.join(result)
                
        except Exception as e:
            logger.warning(f"Error adding page markers: {str(e)}")
            # If something goes wrong, return the original text
            return text