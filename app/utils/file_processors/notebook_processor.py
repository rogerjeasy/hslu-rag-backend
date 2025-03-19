# app/utils/file_processors/notebook_processor.py
import logging
import json
from typing import Dict, Tuple, Any
import asyncio
import re

from app.core.exceptions import DocumentProcessingException

logger = logging.getLogger(__name__)

class NotebookProcessor:
    """
    Processes Jupyter Notebook documents to extract text and metadata.
    
    This class handles notebook-specific extraction, including
    code cells, markdown cells, and outputs.
    """
    
    async def process(self, file_content: bytes) -> Tuple[str, Dict[str, Any]]:
        """
        Process a Jupyter Notebook file to extract text and metadata.
        
        Args:
            file_content: Binary content of the notebook file
            
        Returns:
            Tuple of (extracted text, notebook metadata)
        """
        try:
            # Run extraction in a thread pool
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, self._extract_notebook_content, file_content
            )
        except Exception as e:
            logger.error(f"Error processing Jupyter Notebook: {str(e)}")
            raise DocumentProcessingException(f"Failed to process Jupyter Notebook: {str(e)}")
    
    def _extract_notebook_content(self, file_content: bytes) -> Tuple[str, Dict[str, Any]]:
        """
        Extract content and metadata from a Jupyter Notebook file.
        
        Args:
            file_content: Binary content of the notebook file
            
        Returns:
            Tuple of (extracted text, notebook metadata)
        """
        try:
            # Parse notebook JSON
            notebook = json.loads(file_content.decode('utf-8'))
            
            # Extract metadata
            metadata = self._extract_metadata(notebook)
            
            # Extract text
            full_text = self._extract_cells_content(notebook)
            
            return full_text, metadata
            
        except Exception as e:
            logger.error(f"Error extracting content from Jupyter Notebook: {str(e)}")
            raise DocumentProcessingException(f"Failed to extract content from Jupyter Notebook: {str(e)}")
    
    def _extract_metadata(self, notebook: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata from a Jupyter Notebook.
        
        Args:
            notebook: Parsed notebook JSON
            
        Returns:
            Dictionary of metadata
        """
        metadata = {
            "content_type": "jupyter_notebook"
        }
        
        # Extract kernel info
        if "metadata" in notebook:
            nb_metadata = notebook["metadata"]
            
            # Get kernel info
            if "kernelspec" in nb_metadata:
                kernel = nb_metadata["kernelspec"]
                if "name" in kernel:
                    metadata["notebook_kernel"] = kernel["name"]
                if "language" in kernel:
                    metadata["notebook_language"] = kernel["language"]
            
            # Get language info
            if "language_info" in nb_metadata:
                lang_info = nb_metadata["language_info"]
                if "name" in lang_info:
                    metadata["notebook_language"] = lang_info["name"]
                if "version" in lang_info:
                    metadata["notebook_language_version"] = lang_info["version"]
            
            # Get other metadata
            if "title" in nb_metadata:
                metadata["notebook_title"] = nb_metadata["title"]
            if "authors" in nb_metadata:
                metadata["notebook_authors"] = nb_metadata["authors"]
        
        # Count cells by type
        if "cells" in notebook:
            cells = notebook["cells"]
            code_cells = sum(1 for cell in cells if cell.get("cell_type") == "code")
            markdown_cells = sum(1 for cell in cells if cell.get("cell_type") == "markdown")
            
            metadata["notebook_num_cells"] = len(cells)
            metadata["notebook_code_cells"] = code_cells
            metadata["notebook_markdown_cells"] = markdown_cells
        
        return metadata
    
    def _extract_cells_content(self, notebook: Dict[str, Any]) -> str:
        """
        Extract content from notebook cells.
        
        Args:
            notebook: Parsed notebook JSON
            
        Returns:
            Extracted text content
        """
        full_text = ""
        
        if "cells" not in notebook:
            return full_text
        
        cells = notebook["cells"]
        
        for i, cell in enumerate(cells):
            cell_type = cell.get("cell_type", "")
            
            # Add cell marker
            full_text += f"\n\n--- Cell {i+1} ({cell_type}) ---\n\n"
            
            if cell_type == "markdown":
                # Extract markdown content
                source = self._get_cell_source(cell)
                full_text += source
                
            elif cell_type == "code":
                # Extract code and outputs
                source = self._get_cell_source(cell)
                full_text += f"```\n{source}\n```\n"
                
                # Extract outputs if available
                outputs = self._extract_cell_outputs(cell)
                if outputs:
                    full_text += f"\nOutputs:\n{outputs}\n"
        
        return full_text
    
    def _get_cell_source(self, cell: Dict[str, Any]) -> str:
        """
        Extract source content from a cell.
        
        Args:
            cell: Notebook cell object
            
        Returns:
            Source content as string
        """
        source = cell.get("source", "")
        
        # Handle different source formats
        if isinstance(source, list):
            return "".join(source)
        return str(source)
    
    def _extract_cell_outputs(self, cell: Dict[str, Any]) -> str:
        """
        Extract outputs from a code cell.
        
        Args:
            cell: Notebook cell object
            
        Returns:
            Extracted outputs as string
        """
        outputs_text = ""
        
        if "outputs" not in cell:
            return outputs_text
        
        for output in cell["outputs"]:
            output_type = output.get("output_type", "")
            
            if output_type == "stream":
                # Stream output (stdout/stderr)
                name = output.get("name", "stdout")
                text = output.get("text", "")
                
                if isinstance(text, list):
                    text = "".join(text)
                
                outputs_text += f"{name}: {text}\n"
                
            elif output_type in ["execute_result", "display_data"]:
                # Data output
                data = output.get("data", {})
                
                # Text/plain is most universal
                if "text/plain" in data:
                    text = data["text/plain"]
                    
                    if isinstance(text, list):
                        text = "".join(text)
                    
                    outputs_text += f"{text}\n"
                
            elif output_type == "error":
                # Error output
                ename = output.get("ename", "Error")
                evalue = output.get("evalue", "")
                outputs_text += f"Error: {ename} - {evalue}\n"
        
        return outputs_text