# app/services/llm_service.py
import logging
import json
import openai
import asyncio
import anthropic
from typing import Dict, Any, Optional, List
from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type

from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    """
    Service for interacting with language models
    """
    
    def __init__(self):
        """Initialize the language model client based on config"""
        self.provider = settings.LLM_PROVIDER.lower()
        
        if self.provider == "claude":
            self.client = AsyncAnthropic(api_key=settings.LLM_API_KEY)
        elif self.provider == "gpt":
            openai.api_key = settings.LLM_API_KEY
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(min=1, max=20),
        retry=retry_if_exception_type((openai.APIError, anthropic.APIError))
    )
    async def generate_response(
        self, 
        system_prompt: str, 
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Generate a response from the language model
        
        Args:
            system_prompt: System prompt for the model
            user_prompt: User prompt including context
            temperature: Temperature parameter for generation
            max_tokens: Maximum tokens to generate
            
        Returns:
            Dictionary with response information
        """
        try:
            if self.provider == "claude":
                return await self._generate_claude_response(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            elif self.provider == "gpt":
                return await self._generate_gpt_response(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
        except Exception as e:
            logger.error(f"Error generating LLM response: {str(e)}")
            raise
    
    async def _generate_claude_response(
        self, 
        system_prompt: str, 
        user_prompt: str,
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Generate response using Claude API"""
        try:
            # Call Claude API
            response = await self.client.messages.create(
                model="claude-3-opus-20240229",  # Or your configured model
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Parse the response
            response_text = response.content[0].text
            
            # Try to extract JSON from the response
            try:
                # Look for JSON structure in the response
                json_match = response_text.strip()
                
                # If response contains markdown code block with JSON
                if "```json" in json_match:
                    json_match = json_match.split("```json")[1].split("```")[0].strip()
                
                # Parse JSON
                parsed_json = json.loads(json_match)
                
                return {
                    "response": parsed_json,
                    "raw_response": response_text,
                    "usage": {
                        "prompt_tokens": response.usage.input_tokens,
                        "completion_tokens": response.usage.output_tokens,
                        "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                    }
                }
            except (json.JSONDecodeError, IndexError) as e:
                logger.warning(f"Failed to parse JSON from Claude response: {str(e)}")
                # Return the raw response for further processing
                return {
                    "response": {"answer": response_text, "citations": []},
                    "raw_response": response_text,
                    "usage": {
                        "prompt_tokens": response.usage.input_tokens,
                        "completion_tokens": response.usage.output_tokens,
                        "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                    }
                }
                
        except Exception as e:
            logger.error(f"Error calling Claude API: {str(e)}")
            raise
    
    async def _generate_gpt_response(
        self, 
        system_prompt: str, 
        user_prompt: str,
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Generate response using OpenAI GPT API"""
        try:
            # Use the async client
            async_client = openai.AsyncClient(api_key=settings.OPENAI_API_KEY)
            
            # Call OpenAI API using async method
            response = await async_client.chat.completions.create(
                model="gpt-4-turbo",  # Or your configured model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            response_text = response.choices[0].message.content
            
            # Try to parse JSON response
            try:
                parsed_json = json.loads(response_text)
                
                return {
                    "response": parsed_json,
                    "raw_response": response_text,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from GPT response: {str(e)}")
                # Return the raw response for further processing
                return {
                    "response": {"answer": response_text, "citations": []},
                    "raw_response": response_text,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
                
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            raise