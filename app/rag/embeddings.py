import logging
import os
from typing import List, Any
import numpy as np
import aiohttp
import json

from app.core.config import settings
from app.core.exceptions import RAGException

logger = logging.getLogger(__name__)

class EmbeddingGenerator:
    """
    Handles generation of text embeddings for documents and queries.
    
    This class abstracts the embedding generation process, supporting
    multiple embedding providers (OpenAI, Cohere, etc).
    """
    
    def __init__(self):
        """Initialize the embedding generator with API settings"""
        self.api_key = settings.LLM_API_KEY
        self.model = settings.EMBEDDING_MODEL
        self.embedding_dimension = settings.EMBEDDING_DIMENSION
    
    async def generate(self, text: str) -> List[float]:
        """
        Generate embedding for a single text string.
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            Vector representation as list of floats
        """
        if not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.embedding_dimension
        
        try:
            # Default to OpenAI embeddings
            if "text-embedding-3" in self.model or "text-embedding-ada" in self.model:
                return await self._generate_openai_embedding(text)
            else:
                raise ValueError(f"Unsupported embedding model: {self.model}")
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise RAGException(f"Failed to generate embedding: {str(e)}")
    
    async def generate_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.
        
        Args:
            texts: List of texts to generate embeddings for
            
        Returns:
            List of vector representations
        """
        if not texts:
            return []
        
        # Filter out empty texts
        non_empty_texts = [(i, text) for i, text in enumerate(texts) if text.strip()]
        indices, filtered_texts = zip(*non_empty_texts) if non_empty_texts else ([], [])
        
        try:
            # Default to OpenAI embeddings
            if "text-embedding-3" in self.model or "text-embedding-ada" in self.model:
                embeddings = await self._generate_openai_embeddings_batch(list(filtered_texts))
            else:
                raise ValueError(f"Unsupported embedding model: {self.model}")
            
            # Create result list with zero vectors for empty texts
            result = [[0.0] * self.embedding_dimension] * len(texts)
            for i, embedding in zip(indices, embeddings):
                result[i] = embedding
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {str(e)}")
            raise RAGException(f"Failed to generate batch embeddings: {str(e)}")
    
    async def _generate_openai_embedding(self, text: str) -> List[float]:
        """
        Generate embedding using OpenAI API.
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            Vector representation as list of floats
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "input": text,
                "model": self.model
            }
            
            async with session.post(
                "https://api.openai.com/v1/embeddings",
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RAGException(f"OpenAI API error: {error_text}")
                
                result = await response.json()
                return result["data"][0]["embedding"]
    
    async def _generate_openai_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts using OpenAI API.
        
        Args:
            texts: List of texts to generate embeddings for
            
        Returns:
            List of vector representations
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "input": texts,
                "model": self.model
            }
            
            async with session.post(
                "https://api.openai.com/v1/embeddings",
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RAGException(f"OpenAI API error: {error_text}")
                
                result = await response.json()
                
                # Sort by index to maintain original order
                embeddings = sorted(result["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in embeddings]