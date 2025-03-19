# app/utils/file_processors/code_processor.py
import logging
import os
from typing import Dict, Tuple, Any
import asyncio

from app.core.exceptions import DocumentProcessingException

logger = logging.getLogger(__name__)

class CodeProcessor:
    """
    Processes code files to extract text and metadata.
    
    This class handles code-specific extraction and adds
    language detection and structure information.
    """
    
    async def process(self, file_content: bytes, filename: str) -> Tuple[str, Dict[str, Any]]:
        """
        Process a code file to extract text and metadata.
        
        Args:
            file_content: Binary content of the code file
            filename: Name of the file
            
        Returns:
            Tuple of (extracted text, code metadata)
        """
        try:
            # Run extraction in a thread pool
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, self._extract_code_content, file_content, filename
            )
        except Exception as e:
            logger.error(f"Error processing code file: {str(e)}")
            raise DocumentProcessingException(f"Failed to process code file: {str(e)}")
    
    def _extract_code_content(self, file_content: bytes, filename: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract content and metadata from a code file.
        
        Args:
            file_content: Binary content of the code file
            filename: Name of the file
            
        Returns:
            Tuple of (extracted text, code metadata)
        """
        try:
            # Decode file content
            code_text = file_content.decode('utf-8', errors='replace')
            
            # Extract metadata
            metadata = self._extract_metadata(code_text, filename)
            
            # Add syntax highlighting markers based on language
            language = metadata.get("code_language", "")
            
            if language:
                full_text = f"```{language}\n{code_text}\n```"
            else:
                full_text = code_text
            
            return full_text, metadata
            
        except Exception as e:
            logger.error(f"Error extracting content from code file: {str(e)}")
            raise DocumentProcessingException(f"Failed to extract content from code file: {str(e)}")
    
    def _extract_metadata(self, code_text: str, filename: str) -> Dict[str, Any]:
        """
        Extract metadata from a code file.
        
        Args:
            code_text: Text content of the code file
            filename: Name of the file
            
        Returns:
            Dictionary of metadata
        """
        metadata = {
            "content_type": "code"
        }
        
        # Detect language from file extension
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".html": "html",
            ".css": "css",
            ".java": "java",
            ".cpp": "cpp",
            ".h": "cpp",
            ".c": "c",
            ".cs": "csharp",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".r": "r",
            ".sql": "sql",
            ".sh": "bash",
            ".json": "json",
            ".xml": "xml",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".md": "markdown"
        }
        
        language = language_map.get(ext, "")
        if language:
            metadata["code_language"] = language
        
        # Count lines of code
        lines = code_text.split("\n")
        metadata["code_lines"] = len(lines)
        
        # Count non-empty, non-comment lines
        code_lines = 0
        comment_lines = 0
        
        # Define comment patterns for different languages
        comment_patterns = {
            "python": ["#"],
            "javascript": ["//", "/*"],
            "typescript": ["//", "/*"],
            "java": ["//", "/*"],
            "cpp": ["//", "/*"],
            "c": ["//", "/*"],
            "csharp": ["//", "/*"],
            "go": ["//", "/*"],
            "ruby": ["#"],
            "php": ["//", "#", "/*"],
            "r": ["#"],
            "sql": ["--", "/*"],
            "bash": ["#"]
        }
        
        # Get applicable comment patterns
        patterns = comment_patterns.get(language, [])
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                continue
                
            is_comment = False
            for pattern in patterns:
                if stripped.startswith(pattern):
                    comment_lines += 1
                    is_comment = True
                    break
            
            if not is_comment:
                code_lines += 1
        
        metadata["code_non_empty_lines"] = code_lines + comment_lines
        metadata["code_comment_lines"] = comment_lines
        
        # Try to extract module/class/function information
        if language == "python":
            self._add_python_metadata(code_text, metadata)
        elif language in ["javascript", "typescript"]:
            self._add_js_metadata(code_text, metadata)
        elif language in ["java", "csharp"]:
            self._add_java_metadata(code_text, metadata)
        
        return metadata
    
    def _add_python_metadata(self, code_text: str, metadata: Dict[str, Any]) -> None:
        """
        Extract Python-specific metadata.
        
        Args:
            code_text: Python code content
            metadata: Metadata dictionary to update
        """
        import re
        
        # Find import statements
        import_pattern = r"(?:^|\n)(?:from\s+(\S+)\s+)?import\s+(.+)(?:$|\n)"
        imports = []
        
        for match in re.finditer(import_pattern, code_text):
            from_module = match.group(1)
            import_names = match.group(2)
            
            if from_module:
                imports.append(f"from {from_module} import {import_names}")
            else:
                imports.append(f"import {import_names}")
        
        if imports:
            metadata["python_imports"] = imports
        
        # Find class definitions
        class_pattern = r"(?:^|\n)class\s+(\w+)(?:\([^)]*\))?:"
        classes = []
        
        for match in re.finditer(class_pattern, code_text):
            class_name = match.group(1)
            classes.append(class_name)
        
        if classes:
            metadata["python_classes"] = classes
        
        # Find function definitions
        function_pattern = r"(?:^|\n)def\s+(\w+)\s*\("
        functions = []
        
        for match in re.finditer(function_pattern, code_text):
            function_name = match.group(1)
            # Exclude common dunder methods
            if not (function_name.startswith('__') and function_name.endswith('__')):
                functions.append(function_name)
        
        if functions:
            metadata["python_functions"] = functions
        
        # Find docstrings
        class_or_func_pattern = r'(?:def|class)\s+\w+(?:\([^)]*\))?:(?:\s*"""((?:.|[\r\n])*?)"""|\'\'\'((?:.|[\r\n])*?)\'\'\')'
        docstrings = {}
        
        for match in re.finditer(class_or_func_pattern, code_text):
            docstring = match.group(1) or match.group(2)
            if docstring:
                docstrings[len(docstrings)] = docstring.strip()
        
        if docstrings:
            metadata["python_docstrings"] = docstrings
    
    def _add_js_metadata(self, code_text: str, metadata: Dict[str, Any]) -> None:
        """
        Extract JavaScript/TypeScript specific metadata.
        
        Args:
            code_text: JS/TS code content
            metadata: Metadata dictionary to update
        """
        import re
        
        # Find import statements
        import_pattern = r"(?:^|\n)import\s+(?:{[^}]+}|\*\s+as\s+\w+|\w+)\s+from\s+['\"]([^'\"]+)['\"]"
        imports = []
        
        for match in re.finditer(import_pattern, code_text):
            module_name = match.group(1)
            imports.append(module_name)
        
        # Also find require statements
        require_pattern = r"(?:^|\n)(?:const|let|var)\s+(?:{[^}]+}|\w+)\s+=\s+require\(['\"]([^'\"]+)['\"]\)"
        
        for match in re.finditer(require_pattern, code_text):
            module_name = match.group(1)
            imports.append(module_name)
        
        if imports:
            metadata["js_imports"] = imports
        
        # Find class definitions
        class_pattern = r"(?:^|\n)class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{"
        classes = []
        
        for match in re.finditer(class_pattern, code_text):
            class_name = match.group(1)
            classes.append(class_name)
        
        if classes:
            metadata["js_classes"] = classes
        
        # Find function definitions (including arrow functions)
        function_pattern = r"(?:^|\n)(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*function|(?:const|let|var)\s+(\w+)\s*=\s*\([^)]*\)\s*=>)"
        functions = []
        
        for match in re.finditer(function_pattern, code_text):
            function_name = match.group(1) or match.group(2) or match.group(3)
            if function_name:
                functions.append(function_name)
        
        # Also find methods in classes or objects
        method_pattern = r"(?:^|\n)\s*(\w+)\s*(?:\([^)]*\)|=\s*function\s*\([^)]*\)|=\s*\([^)]*\)\s*=>)"
        
        for match in re.finditer(method_pattern, code_text):
            method_name = match.group(1)
            # Filter out keywords
            if method_name not in ["if", "for", "while", "switch", "function", "return"]:
                functions.append(method_name)
        
        if functions:
            metadata["js_functions"] = list(set(functions))  # Remove duplicates
        
        # Check for React components
        if "react" in code_text.lower() and ("jsx" in code_text.lower() or "function component" in code_text.lower() or "</" in code_text):
            metadata["is_react_component"] = True
        
        # Check for Node.js specifics
        if "process.env" in code_text or "require(" in code_text or "__dirname" in code_text or "__filename" in code_text:
            metadata["is_nodejs"] = True
    
    def _add_java_metadata(self, code_text: str, metadata: Dict[str, Any]) -> None:
        """
        Extract Java/C# specific metadata.
        
        Args:
            code_text: Java/C# code content
            metadata: Metadata dictionary to update
        """
        import re
        
        # Find package/namespace declarations
        package_pattern = r"(?:^|\n)package\s+([a-zA-Z0-9_.]+)"
        namespace_pattern = r"(?:^|\n)namespace\s+([a-zA-Z0-9_.]+)"
        
        package_match = re.search(package_pattern, code_text)
        namespace_match = re.search(namespace_pattern, code_text)
        
        if package_match:
            metadata["java_package"] = package_match.group(1)
        elif namespace_match:
            metadata["csharp_namespace"] = namespace_match.group(1)
        
        # Find import statements
        import_pattern = r"(?:^|\n)import\s+([a-zA-Z0-9_.]+(?:\*)?)"
        using_pattern = r"(?:^|\n)using\s+([a-zA-Z0-9_.]+)"
        
        imports = []
        
        for match in re.finditer(import_pattern, code_text):
            import_name = match.group(1)
            imports.append(import_name)
        
        for match in re.finditer(using_pattern, code_text):
            using_name = match.group(1)
            imports.append(using_name)
        
        if imports:
            metadata["imports"] = imports
        
        # Find class definitions
        class_pattern = r"(?:^|\n)(?:public\s+|private\s+|protected\s+|internal\s+|static\s+)*class\s+(\w+)"
        classes = []
        
        for match in re.finditer(class_pattern, code_text):
            class_name = match.group(1)
            classes.append(class_name)
        
        # Also find interfaces
        interface_pattern = r"(?:^|\n)(?:public\s+|private\s+|protected\s+|internal\s+)*interface\s+(\w+)"
        
        for match in re.finditer(interface_pattern, code_text):
            interface_name = match.group(1)
            classes.append(f"Interface: {interface_name}")
        
        if classes:
            metadata["classes"] = classes
        
        # Find method definitions
        method_pattern = r"(?:^|\n)\s+(?:public\s+|private\s+|protected\s+|internal\s+|static\s+|final\s+|virtual\s+|override\s+|abstract\s+)*(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\([^)]*\)"
        methods = []
        
        for match in re.finditer(method_pattern, code_text):
            method_name = match.group(1)
            # Exclude constructor names (same as class names)
            if method_name not in classes:
                methods.append(method_name)
        
        if methods:
            metadata["methods"] = methods
        
        # Detect if it's an Android app (Java)
        if "android.app" in code_text or "android.os" in code_text or "extends Activity" in code_text or "extends AppCompatActivity" in code_text:
            metadata["is_android_app"] = True
        
        # Detect if it's a Spring application (Java)
        if "@SpringBootApplication" in code_text or "@Controller" in code_text or "@RestController" in code_text or "SpringApplication.run" in code_text:
            metadata["is_spring_app"] = True
        
        # Detect if it's an ASP.NET application (C#)
        if "Microsoft.AspNetCore" in code_text or "[ApiController]" in code_text or "IActionResult" in code_text:
            metadata["is_aspnet_app"] = True