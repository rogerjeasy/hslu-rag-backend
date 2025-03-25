import logging
import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.core.config import settings
from app.core.exceptions import ValidationException
from app.schemas.query import QueryType
from app.core.prompt_templates import (
    get_system_prompt, 
    get_user_prompt, 
    PromptType, 
    DetailLevel, 
    Format, 
    Difficulty
)

logger = logging.getLogger(__name__)

class GenerationService:
    """Service for generating responses using LLMs"""
    
    def __init__(self):
        """Initialize generation service with OpenAI API"""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def generate_response(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        model_id: str = "gpt-4",
        query_type: QueryType = QueryType.QUESTION_ANSWERING,
        max_tokens: int = 1000,
        additional_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate response using LLM based on query and context.
        
        Args:
            query: User query text
            context_chunks: Retrieved context chunks
            model_id: ID of the LLM to use
            query_type: Type of response to generate
            max_tokens: Maximum tokens in response
            additional_params: Additional parameters for specific query types
            
        Returns:
            Generated response with citations
        """
        try:
            # Map QueryType to PromptType
            prompt_type_mapping = {
                QueryType.QUESTION_ANSWERING: PromptType.QUESTION_ANSWERING,
                QueryType.STUDY_GUIDE: PromptType.STUDY_GUIDE,
                QueryType.PRACTICE_QUESTIONS: PromptType.PRACTICE_QUESTIONS,
                QueryType.KNOWLEDGE_GAP: PromptType.KNOWLEDGE_GAP
            }
            
            prompt_type = prompt_type_mapping.get(query_type, PromptType.QUESTION_ANSWERING)
            
            # Process additional parameters based on query type
            processed_params = self._process_additional_params(query_type, additional_params)
            
            # Get system prompt from prompt_templates
            system_prompt = get_system_prompt(prompt_type, processed_params)
            
            # Get user prompt from prompt_templates
            user_prompt = get_user_prompt(
                prompt_type=prompt_type,
                query=query,
                context_chunks=context_chunks,
                additional_params=processed_params
            )
            
            # Create messages for chat completion
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Select the right model
            model = model_id if model_id else "gpt-4"
            
            # Create API call parameters, only adding response_format for models that support it
            api_params = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7
            }
            
            # List of models that support JSON response format
            json_format_models = [
                "gpt-4-turbo", 
                "gpt-4-0125-preview", 
                "gpt-4-1106-preview", 
                "gpt-4-0613", 
                "gpt-3.5-turbo-1106", 
                "gpt-3.5-turbo-0125"
            ]
            
            # Check if model supports JSON response format
            if any(supported_model in model for supported_model in json_format_models):
                api_params["response_format"] = {"type": "json_object"}
                
            # Generate response from LLM
            response = self.client.chat.completions.create(**api_params)
            
            # Extract and parse response
            response_text = response.choices[0].message.content
            
            # Try to parse as JSON, but handle non-JSON responses gracefully
            try:
                parsed_response = json.loads(response_text)
            except json.JSONDecodeError:
                # If response isn't valid JSON, create a compatible structure
                logger.warning(f"Failed to parse JSON response: {response_text}")
                parsed_response = {
                    "answer": response_text,
                    "citations": []
                }
            
            # Extract citations from response and context
            citations = self._extract_citations(parsed_response, context_chunks)
            
            return {
                "response_text": parsed_response.get("answer", ""),
                "citations": citations,
                "raw_llm_response": response_text,
                "meta": parsed_response.get("meta", {})
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise ValidationException(f"Failed to generate response: {str(e)}")
    
    def _process_additional_params(
        self, 
        query_type: QueryType, 
        additional_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process additional parameters based on query type to match expected formats"""
        params = additional_params or {}
        processed = params.copy()

        if query_type == QueryType.STUDY_GUIDE:
            # Convert string detail level to enum if needed
            if "detail_level" in processed and isinstance(processed["detail_level"], str):
                detail_level = processed["detail_level"].lower()
                if detail_level in [dl.value for dl in DetailLevel]:
                    processed["detail_level"] = detail_level
                else:
                    processed["detail_level"] = DetailLevel.MEDIUM.value
            
            # Convert string format to enum if needed
            if "format" in processed and isinstance(processed["format"], str):
                format_type = processed["format"].lower()
                if format_type in [f.value for f in Format]:
                    processed["format"] = format_type
                else:
                    processed["format"] = Format.OUTLINE.value
        
        elif query_type == QueryType.PRACTICE_QUESTIONS:
            # Convert string difficulty to enum if needed
            if "difficulty" in processed and isinstance(processed["difficulty"], str):
                difficulty = processed["difficulty"].lower()
                if difficulty in [d.value for d in Difficulty]:
                    processed["difficulty"] = difficulty
                else:
                    processed["difficulty"] = Difficulty.MEDIUM.value
            
            # Ensure question_count is an integer
            if "question_count" in processed:
                try:
                    processed["question_count"] = int(processed["question_count"])
                except (ValueError, TypeError):
                    processed["question_count"] = 5
        
        return processed
    
    def _extract_citations(
        self, 
        parsed_response: Dict[str, Any], 
        context_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract and format citations from response and context"""
        citations = []
        cited_indices = parsed_response.get("citations", [])
        
        # Convert string indices to integers if needed
        if cited_indices and isinstance(cited_indices, list):
            numeric_indices = []
            for idx in cited_indices:
                if isinstance(idx, str) and idx.isdigit():
                    numeric_indices.append(int(idx))
                elif isinstance(idx, int):
                    numeric_indices.append(idx)
            cited_indices = numeric_indices
        
        for index in cited_indices:
            if 0 <= index-1 < len(context_chunks):  # Adjust for 1-based indexing in prompt
                chunk = context_chunks[index-1]
                citation = {
                    "material_id": chunk.get("material_id", ""),
                    "title": chunk.get("title", "Unknown"),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "page_number": chunk.get("source_page"),
                    "content_preview": chunk.get("chunk_content", "")[:200] + "..."
                }
                citations.append(citation)
        
        return citations