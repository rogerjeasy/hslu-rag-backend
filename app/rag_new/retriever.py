# app/rag/retriever.py
import logging
from typing import Dict, List, Any, Optional

from app.rag_new.embdeddings import EmbeddingService

logger = logging.getLogger(__name__)

class RAGRetriever:
    """
    Service for retrieving relevant context for RAG
    """
    
    def __init__(self, embedding_service: EmbeddingService):
        """
        Initialize retriever with embedding service
        
        Args:
            embedding_service: Service for searching embeddings
        """
        self.embedding_service = embedding_service
    
    async def retrieve(
        self, 
        query: str, 
        filter: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context chunks for a query
        
        Args:
            query: User query
            filter: Optional metadata filter
            top_k: Maximum number of chunks to retrieve
            
        Returns:
            List of context chunks with metadata
        """
        try:
            # Search for similar vectors
            search_results = await self.embedding_service.search_similar(
                query=query,
                filter=filter,
                top_k=top_k
            )
            
            # Format results
            context_chunks = []
            for i, result in enumerate(search_results):
                context_chunks.append({
                    "chunk_id": result["id"],
                    "chunk_content": result["metadata"].get("chunk_text_preview", ""),
                    "score": result["score"],
                    "material_id": result["metadata"].get("material_id", ""),
                    "source_url": result["metadata"].get("source_url", ""),
                    "file_type": result["metadata"].get("file_type", ""),
                    "chunk_index": result["metadata"].get("chunk_index", 0),
                    "total_chunks": result["metadata"].get("total_chunks", 0),
                    "title": f"Source {i+1}"  # This would be replaced with actual title if available
                })
            
            return context_chunks
            
        except Exception as e:
            logger.error(f"Error retrieving context: {str(e)}")
            return []