# app/services/pinecone_service.py
import logging
from typing import List, Dict, Any, Optional
from pinecone import Pinecone, ServerlessSpec

from app.core.config import settings
from app.core.exceptions import ValidationException

logger = logging.getLogger(__name__)

class PineconeService:
    """Service for managing vector storage in Pinecone"""
    
    def __init__(self, index_name: str = None):
        """Initialize Pinecone client and index"""
        # Initialize Pinecone
        self.pc = Pinecone(
            api_key=settings.PINECONE_API_KEY,
            environment=settings.PINECONE_ENVIRONMENT
        )
        
        # Set index name
        self.index_name = index_name or settings.PINECONE_INDEX_NAME
        
        # Get or create index
        if self.index_name not in [idx for idx in self.pc.list_indexes().names()]:
            # Create index if it doesn't exist
            # Note: You might need to adjust the spec parameters according to your needs
            self.pc.create_index(
                name=self.index_name,
                dimension=settings.EMBEDDING_DIMENSIONS,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud='aws',  
                    region='us-east-1' 
                )
            )
        
        # Connect to index
        self.index = self.pc.Index(self.index_name)
    
    async def upsert_vector(self, vector_id: str, vector: List[float], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert or update a vector in Pinecone.
        
        Args:
            vector_id: Unique ID for the vector
            vector: Vector embedding
            metadata: Associated metadata
            
        Returns:
            Pinecone response
        """
        try:
            # Sanitize metadata (Pinecone doesn't support nested objects)
            clean_metadata = self._sanitize_metadata(metadata)
            
            # Upsert single vector
            response = self.index.upsert(
                vectors=[(vector_id, vector, clean_metadata)]
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error upserting vector to Pinecone: {str(e)}")
            raise ValidationException(f"Failed to store vector: {str(e)}")
    
    async def upsert_vectors(self, vectors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Insert or update multiple vectors in Pinecone.
        
        Args:
            vectors: List of dictionaries with vector_id, vector, and metadata
            
        Returns:
            Pinecone response
        """
        try:
            # Format vectors for Pinecone
            formatted_vectors = []
            for item in vectors:
                clean_metadata = self._sanitize_metadata(item["metadata"])
                formatted_vectors.append((item["id"], item["vector"], clean_metadata))
            
            # Upsert vectors in batches (limit is typically 100)
            batch_size = 100
            all_responses = []
            
            for i in range(0, len(formatted_vectors), batch_size):
                batch = formatted_vectors[i:i+batch_size]
                response = self.index.upsert(vectors=batch)
                all_responses.append(response)
            
            return {"batch_responses": all_responses}
            
        except Exception as e:
            logger.error(f"Error upserting vectors to Pinecone: {str(e)}")
            raise ValidationException(f"Failed to store vectors: {str(e)}")
    
    async def query_vectors(self, query_vector: List[float], top_k: int = 5, filter: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Query vectors from Pinecone.
        
        Args:
            query_vector: Vector embedding to query with
            top_k: Number of results to return
            filter: Metadata filter criteria
            
        Returns:
            Pinecone query response
        """
        try:
            # Query the index
            response = self.index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
                filter=filter
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error querying vectors from Pinecone: {str(e)}")
            raise ValidationException(f"Failed to query vectors: {str(e)}")
    
    async def delete_vectors(self, vector_ids: List[str] = None, filter: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Delete vectors from Pinecone.
        
        Args:
            vector_ids: List of vector IDs to delete
            filter: Metadata filter for deletion
            
        Returns:
            Pinecone delete response
        """
        try:
            # Delete by ID or filter
            if vector_ids:
                response = self.index.delete(ids=vector_ids)
            elif filter:
                response = self.index.delete(filter=filter)
            else:
                raise ValidationException("Either vector_ids or filter must be provided")
            
            return response
            
        except Exception as e:
            logger.error(f"Error deleting vectors from Pinecone: {str(e)}")
            raise ValidationException(f"Failed to delete vectors: {str(e)}")
    
    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize metadata for Pinecone (flatten nested objects, convert to strings).
        
        Args:
            metadata: Original metadata dictionary
            
        Returns:
            Sanitized metadata dictionary
        """
        clean_metadata = {}
        
        for key, value in metadata.items():
            # Skip None values
            if value is None:
                continue
                
            # Convert lists, dicts, and other objects to strings
            if isinstance(value, (list, dict, set, tuple)):
                clean_metadata[key] = str(value)
            else:
                clean_metadata[key] = value
        
        return clean_metadata