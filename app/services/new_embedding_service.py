# app/services/new_embedding_service.py
import logging
from openai import OpenAI
from typing import List, Dict, Any
from app.core.config import settings
from app.core.exceptions import ValidationException

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating text embeddings"""
    
    def __init__(self, model_name: str = "text-embedding-3-small"):
        """Initialize the embedding service with OpenAI API"""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model_name = model_name
    
    async def create_embedding(self, text: str) -> List[float]:
        """
        Create an embedding for a text string.
        
        Args:
            text: Text to embed
            
        Returns:
            Vector embedding
        """
        try:
            # Truncate text if too long (limit is about 8k tokens for text-embedding-3-small)
            # This is a simple character-based truncation, in production use a token-aware truncation
            if len(text) > 20000:  # Rough character limit
                text = text[:20000]
            
            # Create embedding with OpenAI
            response = self.client.embeddings.create(
                model=self.model_name,
                input=text,
                encoding_format="float"
            )
            
            # Extract embedding vector
            embedding = response.data[0].embedding
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error creating embedding: {str(e)}")
            raise ValidationException(f"Failed to create embedding: {str(e)}")
    
    async def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of vector embeddings
        """
        try:
            # Truncate texts if too long
            truncated_texts = []
            for text in texts:
                if len(text) > 20000:
                    truncated_texts.append(text[:20000])
                else:
                    truncated_texts.append(text)
            
            # Create embeddings with OpenAI
            response = self.client.embeddings.create(
                model=self.model_name,
                input=truncated_texts,
                encoding_format="float"
            )
            
            # Extract embedding vectors
            embeddings = [item.embedding for item in response.data]
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error creating embeddings batch: {str(e)}")
            raise ValidationException(f"Failed to create embeddings batch: {str(e)}")