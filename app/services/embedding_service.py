# app/services/embedding_service.py
import logging
from typing import List, Dict, Any, Optional
import asyncio

from app.rag.embeddings import EmbeddingGenerator
from app.utils.astra_db_manager import AstraDBManager

logger = logging.getLogger(__name__)

class AstraDocumentService:
    """
    Service for processing and storing documents in AstraDB with vector embeddings.
    
    This service handles the process of converting documents to vectors and 
    storing them in AstraDB for retrieval.
    """
    
    def __init__(self):
        """Initialize document service with required dependencies"""
        self.astra_manager = AstraDBManager()
        self.embedding_generator = EmbeddingGenerator()
        self.collection_name = "hslu_rag_data"  # Default collection
    
    async def process_and_store_documents(
        self,
        documents: List[Dict[str, Any]],
        collection_name: Optional[str] = None
    ) -> List[str]:
        """
        Process documents and store them in AstraDB with embeddings.
        
        Args:
            documents: List of document dictionaries with content and metadata
            collection_name: Optional name for the collection (uses default if None)
            
        Returns:
            List[str]: IDs of the inserted documents
        """
        if not collection_name:
            collection_name = self.collection_name
            
        # Connect and get/create collection
        db = self.astra_manager.connect()
        collection = self.astra_manager.get_or_create_collection(collection_name)
        
        # Prepare documents for vectorization
        vectorized_docs = await self._prepare_documents_with_vectorization(documents)
        
        # Insert documents
        result = self.astra_manager.insert_documents(collection, vectorized_docs)
        return result.inserted_ids
    
    async def _prepare_documents_with_vectorization(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Prepare documents for storage with vectorization field.
        
        Args:
            documents: Raw document dictionaries
            
        Returns:
            List[Dict[str, Any]]: Documents with vectorization field
        """
        vectorized_docs = []
        
        for doc in documents:
            # Create vectorization string based on document content
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            
            # Create vectorization text (what we want the embedding to be based on)
            vectorize_text = self._create_vectorization_text(content, metadata)
            
            # Add the vectorization field
            doc_with_vector = {
                **doc,
                "$vectorize": vectorize_text
            }
            
            vectorized_docs.append(doc_with_vector)
            
        return vectorized_docs
    
    def _create_vectorization_text(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Create text that will be converted to vector embedding.
        
        This method combines content and relevant metadata to create the
        text that will be vectorized for semantic search.
        
        Args:
            content: Document content
            metadata: Document metadata
            
        Returns:
            str: Text to be vectorized
        """
        # Get relevant metadata for context 
        course = metadata.get("course_name", "")
        title = metadata.get("title", "")
        source = metadata.get("source", "")
        
        # Combine content with relevant metadata for better semantic search
        vectorize_text = f"Title: {title}\nCourse: {course}\nSource: {source}\nContent: {content}"
        return vectorize_text
    
    # Updated method for AstraDocumentService class

    async def search_similar_documents(
        self,
        query: str,
        limit: int = 5,
        collection_name: Optional[str] = None,
        filter_condition: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for documents similar to the query text.
        Updated to handle API compatibility issues.
        
        Args:
            query: Query text to search with
            limit: Maximum number of results to return
            collection_name: Optional collection name (uses default if None)
            filter_condition: Optional filter condition based on metadata
            
        Returns:
            List[Dict[str, Any]]: List of similar documents with metadata
        """
        if not collection_name:
            collection_name = self.collection_name
            
        # Connect and get collection
        db = self.astra_manager.connect()
        collection = self.astra_manager.get_or_create_collection(collection_name)
        
        try:
            # First try the text-based vector search through our compatibility layer
            results = self.astra_manager.find_similar_by_text(
                collection=collection,
                query_text=query,
                limit=limit,
                include_value=True,
                filter_condition=filter_condition
            )
        except Exception as text_error:
            # If text-based search fails, fall back to embedding-based search
            logger.warning(f"Text-based search failed: {str(text_error)}. Falling back to embedding-based search.")
            
            # Generate embedding for query
            query_embedding = await self.embedding_generator.generate(query)
            
            # Search using vector
            results = self.astra_manager.find_similar(
                collection=collection,
                query_vector=query_embedding,
                limit=limit,
                include_value=True,
                filter_condition=filter_condition
            )
        
        return self._process_search_results(results)
        
    async def search_similar_documents_with_embedding(
        self,
        query: str,
        limit: int = 5,
        collection_name: Optional[str] = None,
        filter_condition: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for documents similar to the query by generating embedding locally.
        
        Args:
            query: Query text to search with
            limit: Maximum number of results to return
            collection_name: Optional collection name (uses default if None)
            filter_condition: Optional filter condition based on metadata
            
        Returns:
            List[Dict[str, Any]]: List of similar documents with metadata
        """
        if not collection_name:
            collection_name = self.collection_name
            
        # Connect and get collection
        db = self.astra_manager.connect()
        collection = self.astra_manager.get_or_create_collection(collection_name)
        
        # Generate embedding for query
        query_embedding = await self.embedding_generator.generate(query)
        
        # Search using vector
        results = self.astra_manager.find_similar(
            collection=collection,
            query_vector=query_embedding,
            limit=limit,
            include_value=True,
            filter_condition=filter_condition
        )
        
        return self._process_search_results(results)
    
    def _process_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process search results to standardized format.
        
        Args:
            results: Raw results from AstraDB search
            
        Returns:
            List[Dict[str, Any]]: Processed results
        """
        processed_results = []
        
        for result in results:
            # Extract relevant data
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            similarity = result.get("$similarity", 0)
            
            # Remove internal fields
            result_clean = {k: v for k, v in result.items() if not k.startswith('$')}
            
            # Add formatted result
            processed_results.append({
                "id": result.get("_id", ""),
                "content": content,
                "metadata": metadata,
                "score": similarity,
                "raw_data": result_clean
            })
            
        return processed_results