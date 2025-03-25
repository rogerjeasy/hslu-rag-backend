import logging
from typing import List, Dict, Any, Optional
from app.core.exceptions import ValidationException
from app.services.pinecone_service import PineconeService
from app.services.new_embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

class RetrievalService:
    """Service for retrieving relevant context from vector database"""
    
    def __init__(self):
        """Initialize retrieval service with dependencies"""
        self.pinecone_service = PineconeService()
        self.embedding_service = EmbeddingService()
    
    async def retrieve_context(
        self, 
        query: str, 
        course_id: str,
        module_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        max_chunks: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context chunks for a query.
        
        Args:
            query: User query text
            course_id: Course ID to filter by
            module_id: Optional module ID to filter by
            topic_id: Optional topic ID to filter by
            max_chunks: Maximum number of chunks to retrieve
            
        Returns:
            List of context chunks with metadata
        """
        try:
            # Generate embedding for query
            query_embedding = await self.embedding_service.create_embedding(query)
            
            # Create filter for Pinecone query
            filter_dict = {"course_id": course_id}
            if module_id:
                filter_dict["module_id"] = module_id
            if topic_id:
                filter_dict["topic_id"] = topic_id
            
            # Query Pinecone
            search_results = await self.pinecone_service.query_vectors(
                query_vector=query_embedding,
                top_k=max_chunks,
                filter=filter_dict
            )
            
            # Extract relevant chunks with metadata
            context_chunks = []
            for match in search_results.get("matches", []):
                if match.get("metadata"):
                    context_chunks.append({
                        "chunk_content": match["metadata"].get("chunk_content", ""),
                        "material_id": match["metadata"].get("material_id", ""),
                        "course_id": match["metadata"].get("course_id", ""),
                        "module_id": match["metadata"].get("module_id"),
                        "topic_id": match["metadata"].get("topic_id"),
                        "title": match["metadata"].get("title", ""),
                        "chunk_index": match["metadata"].get("chunk_index", 0),
                        "source_page": match["metadata"].get("source_page"),
                        "score": match.get("score", 0)
                    })
            
            # If not enough context retrieved, try to expand search
            if len(context_chunks) < 2 and (module_id or topic_id):
                logger.info(f"Expanding search for query: {query}")
                expanded_filter = {"course_id": course_id}
                
                expanded_results = await self.pinecone_service.query_vectors(
                    query_vector=query_embedding,
                    top_k=max_chunks,
                    filter=expanded_filter
                )
                
                # Add new results that weren't in original search
                existing_ids = {chunk["material_id"] + "-" + str(chunk["chunk_index"]) for chunk in context_chunks}
                for match in expanded_results.get("matches", []):
                    if match.get("metadata"):
                        material_id = match["metadata"].get("material_id", "")
                        chunk_index = match["metadata"].get("chunk_index", 0)
                        chunk_id = f"{material_id}-{chunk_index}"
                        
                        if chunk_id not in existing_ids:
                            context_chunks.append({
                                "chunk_content": match["metadata"].get("chunk_content", ""),
                                "material_id": material_id,
                                "course_id": match["metadata"].get("course_id", ""),
                                "module_id": match["metadata"].get("module_id"),
                                "topic_id": match["metadata"].get("topic_id"),
                                "title": match["metadata"].get("title", ""),
                                "chunk_index": chunk_index,
                                "source_page": match["metadata"].get("source_page"),
                                "score": match.get("score", 0)
                            })
                            if len(context_chunks) >= max_chunks:
                                break
            
            # Resort by relevance score
            context_chunks.sort(key=lambda x: x["score"], reverse=True)
            
            return context_chunks
            
        except Exception as e:
            logger.error(f"Error retrieving context: {str(e)}")
            raise ValidationException(f"Failed to retrieve context: {str(e)}")
    
    async def rerank_chunks(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rerank chunks based on their relevance to the query.
        
        Args:
            query: User query text
            chunks: List of context chunks
            
        Returns:
            Reranked list of chunks
        """
        # This is a simple re-ranking based on content overlap
        # In a real implementation, you might use a more sophisticated approach
        
        # Lowercase query for comparison
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        for chunk in chunks:
            content = chunk.get("chunk_content", "").lower()
            
            # Calculate word overlap score
            content_words = set(content.split())
            overlap = len(query_words.intersection(content_words))
            
            # Calculate exact phrase match bonus
            phrase_bonus = 1.0
            if query_lower in content:
                phrase_bonus = 1.5
            
            # Update score
            chunk["rerank_score"] = chunk.get("score", 0) * phrase_bonus + (overlap * 0.1)
        
        # Sort by rerank score
        chunks.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        
        return chunks