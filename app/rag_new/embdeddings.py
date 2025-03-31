# app/rag_new/embeddings.py
import asyncio
import logging
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple
import openai
from pinecone import Pinecone, ServerlessSpec

from app.core.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Service for creating and managing vector embeddings
    """
    
    def __init__(self):
        """Initialize the embedding service with configured providers"""
        # Setup OpenAI for embeddings
        api_key = settings.OPENAI_API_KEY
        if not api_key or api_key.strip() == "":
            error_msg = "OPENAI_API_KEY is empty or not set in environment"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Log key presence (not the actual key) for debugging
        logger.info(f"OPENAI_API_KEY is present and has length: {len(api_key)}")
    
        # Setup OpenAI with explicit strip to remove any whitespace
        openai.api_key = api_key.strip()
        
        # Setup Pinecone for vector storage
        self._init_pinecone()
        
        # Model and dimension settings
        self.embedding_model = settings.EMBEDDING_MODEL_NAME
        self.embedding_dimensions = settings.EMBEDDING_DIMENSIONS
    
    def _init_pinecone(self):
        """Initialize Pinecone client and ensure index exists"""
        # Initialize Pinecone with the new API
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        
        # Check if index exists
        index_names = [index.name for index in self.pc.list_indexes()]
        
        if settings.PINECONE_INDEX_NAME not in index_names:
            logger.info(f"Creating Pinecone index: {settings.PINECONE_INDEX_NAME}")
            # Create index with the new API
            self.pc.create_index(
                name=settings.PINECONE_INDEX_NAME,
                dimension=settings.EMBEDDING_DIMENSIONS,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud='aws',  
                    region='us-east-1'  
                )
            )
        
        # Connect to index
        self.index = self.pc.Index(settings.PINECONE_INDEX_NAME)
    
    async def create_embedding(self, text: str, vector_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create embedding for text and store in vector database
        
        Args:
            text: Text to embed
            vector_id: Optional ID for the vector (generated if not provided)
            metadata: Optional metadata to store with the vector
            
        Returns:
            Vector ID
        """
        try:
            # Generate a vector ID if not provided
            if not vector_id:
                vector_id = str(uuid.uuid4())
            
            # Create embedding
            embedding = await self._get_embedding(text)
            
            # Store in Pinecone
            self.index.upsert(
                vectors=[(vector_id, embedding, metadata or {})]
            )
            
            return vector_id
            
        except Exception as e:
            logger.error(f"Error creating embedding: {str(e)}")
            raise
    
    async def search_similar(self, query: str, filter: Optional[Dict[str, Any]] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar vectors
        
        Args:
            query: Query text
            filter: Optional metadata filter
            top_k: Number of results to return
            
        Returns:
            List of similar documents with metadata and scores
        """
        try:
            # Get query embedding
            query_embedding = await self._get_embedding(query)
            
            # Search in Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                filter=filter
            )
            
            # Format results for Pinecone v3
            formatted_results = []
            for match in results.matches:
                formatted_results.append({
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching similar vectors: {str(e)}")
            raise
    
    async def delete_embeddings(self, vector_ids: List[str]) -> bool:
        """
        Delete embeddings by vector IDs
        
        Args:
            vector_ids: List of vector IDs to delete
            
        Returns:
            Success status
        """
        try:
            self.index.delete(ids=vector_ids)
            return True
        except Exception as e:
            logger.error(f"Error deleting embeddings: {str(e)}")
            return False
    
    async def delete_by_metadata(self, filter: Dict[str, Any]) -> bool:
        """
        Delete embeddings by metadata filter
        
        Args:
            filter: Metadata filter
            
        Returns:
            Success status
        """
        try:
            self.index.delete(filter=filter)
            return True
        except Exception as e:
            logger.error(f"Error deleting embeddings by metadata: {str(e)}")
            return False
    
    async def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text using configured provider
        
        Args:
            text: Text to embed
            
        Returns:
            Vector embedding
        """
        # Truncate text if too long (most models have token limits)
        text = text[:8000]  # Approximate limit
        
        try:
            # Create a client with explicitly stripped key
            client = openai.AsyncClient(api_key=settings.OPENAI_API_KEY.strip())
            
            # Use async client directly
            response = await client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            
            # Return the embedding
            return response.data[0].embedding
        except Exception as e:
            # Handle client error
            logger.error(f"Error getting embedding: {str(e)}")
            # Retry with a different model if possible, or raise the error
            raise