import logging
import os
from typing import Dict, List, Any, Optional
import json
import aiohttp

from app.core.config import settings
from app.core.exceptions import RAGException

logger = logging.getLogger(__name__)

class LLMConnector:
    """
    Connects to Large Language Models for generating responses.
    
    This class handles API communication with LLMs (Claude, GPT),
    prompt construction, and response parsing.
    """
    
    def __init__(self):
        """Initialize the LLM connector with API settings"""
        self.provider = settings.LLM_PROVIDER.lower()
        self.api_key = settings.LLM_API_KEY
        
        # Default model by provider
        if self.provider == "claude":
            self.model = os.environ.get("CLAUDE_MODEL", "claude-3-sonnet-20240229")
        elif self.provider == "gpt":
            self.model = os.environ.get("GPT_MODEL", "gpt-4")
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    async def generate_response(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate a response to the user query based on retrieved context.
        
        Args:
            query: The user's question or request
            retrieved_chunks: List of relevant document chunks
            conversation_history: Optional previous conversation exchanges
            
        Returns:
            Dictionary with response content and source information
        """
        try:
            # Build prompt with retrieved context
            prompt = self._build_prompt(query, retrieved_chunks, conversation_history)
            
            # Call appropriate LLM API
            if self.provider == "claude":
                response_text = await self._call_claude_api(prompt)
            elif self.provider == "gpt":
                response_text = await self._call_openai_api(prompt)
            else:
                raise ValueError(f"Unsupported LLM provider: {self.provider}")
            
            # Extract sources for citation
            sources = self._extract_sources(retrieved_chunks)
            
            return {
                "content": response_text,
                "sources": sources
            }
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {str(e)}")
            raise RAGException(f"Failed to generate response: {str(e)}")
    
    def _build_prompt(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Build a prompt for the LLM with retrieved content and conversation history.
        
        Args:
            query: The user's question or request
            retrieved_chunks: List of relevant document chunks
            conversation_history: Optional previous conversation exchanges
            
        Returns:
            Formatted prompt string
        """
        # Start with system instruction
        system_prompt = """
        You are an educational assistant for HSLU MSc students in Applied Information and Data Science.
        Answer questions based ONLY on the provided course materials.
        If the information is not in the provided materials, say you don't know and suggest the student consult their course materials.
        Be concise, accurate, and educational in your responses.
        Always maintain a professional tone appropriate for university education.
        """
        
        # Format retrieved chunks as context
        context = ""
        if retrieved_chunks:
            context = "Here are relevant excerpts from your course materials:\n\n"
            for i, chunk in enumerate(retrieved_chunks):
                # Add source information
                source_info = chunk.get("metadata", {})
                source_name = source_info.get("source", "Unknown Source")
                course_name = source_info.get("course_name", "Unknown Course")
                
                context += f"[{i+1}] From {source_name} ({course_name}):\n"
                context += f"{chunk['content']}\n\n"
        
        # Add conversation history for context
        conversation_context = ""
        if conversation_history and len(conversation_history) > 0:
            conversation_context = "Previous conversation:\n\n"
            for exchange in conversation_history:
                conversation_context += f"Student: {exchange.get('query', '')}\n"
                conversation_context += f"Assistant: {exchange.get('response', '')}\n\n"
        
        # Final prompt construction depends on the LLM provider
        if self.provider == "claude":
            prompt = f"{system_prompt}\n\n"
            
            if conversation_context:
                prompt += f"{conversation_context}\n\n"
            
            if context:
                prompt += f"{context}\n\n"
            
            prompt += f"Student: {query}\n\nAssistant:"
            
        elif self.provider == "gpt":
            # For GPT, we'll use the chat format with roles
            # Return as JSON-like structure that will be converted in the API call
            return {
                "system": system_prompt,
                "context": context,
                "conversation_history": conversation_context,
                "query": query
            }
        
        return prompt
    
    async def _call_claude_api(self, prompt: str) -> str:
        """
        Call the Anthropic Claude API to generate a response.
        
        Args:
            prompt: The formatted prompt string
            
        Returns:
            Generated response text
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "max_tokens_to_sample": 2000,
                "temperature": 0.3,
                "top_k": 50,
                "top_p": 0.7,
            }
            
            async with session.post(
                "https://api.anthropic.com/v1/complete",
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RAGException(f"Claude API error: {error_text}")
                
                result = await response.json()
                return result.get("completion", "").strip()
    
    async def _call_openai_api(self, prompt_data: Dict[str, Any]) -> str:
        """
        Call the OpenAI API to generate a response.
        
        Args:
            prompt_data: Dictionary with prompt components
            
        Returns:
            Generated response text
        """
        # Construct messages for the chat completion API
        messages = [
            {"role": "system", "content": prompt_data["system"]}
        ]
        
        # Add context if available
        if prompt_data["context"]:
            messages.append({"role": "system", "content": prompt_data["context"]})
        
        # Add conversation history if available
        if prompt_data["conversation_history"]:
            messages.append({"role": "system", "content": prompt_data["conversation_history"]})
        
        # Add the user query
        messages.append({"role": "user", "content": prompt_data["query"]})
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 2000,
                "top_p": 0.7,
            }
            
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RAGException(f"OpenAI API error: {error_text}")
                
                result = await response.json()
                return result["choices"][0]["message"]["content"].strip()
    
    def _extract_sources(self, retrieved_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract source information from retrieved chunks for citation.
        
        Args:
            retrieved_chunks: List of relevant document chunks
            
        Returns:
            List of source information
        """
        sources = []
        seen_sources = set()
        
        for chunk in retrieved_chunks:
            metadata = chunk.get("metadata", {})
            source_id = metadata.get("source_id")
            
            # Skip duplicates
            if source_id in seen_sources:
                continue
            
            source_info = {
                "source_id": source_id,
                "source": metadata.get("source", "Unknown Source"),
                "course_id": metadata.get("course_id"),
                "course_name": metadata.get("course_name", "Unknown Course"),
                "page": metadata.get("page"),
                "section": metadata.get("section"),
            }
            
            sources.append(source_info)
            seen_sources.add(source_id)
        
        return sources