import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Pinecone
from langchain.docstore.document import Document
# from langchain.chains.query_transformer.base import BaseQueryTransformer
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor

from app.core.config import settings
from app.rag_new.embdeddings import EmbeddingService

logger = logging.getLogger(__name__)

class RAGRetriever:
    """
    Advanced document retriever for RAG with query enhancement and reranking
    """
    
    def __init__(self, embedding_service: EmbeddingService):
        """
        Initialize retriever with embedding service
        
        Args:
            embedding_service: Service for searching embeddings
        """
        self.embedding_service = embedding_service
        
        # Initialize LangChain embeddings component
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL_NAME
        )
    
    async def retrieve(
        self, 
        query: str, 
        filter: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        min_relevance_score: float = 0.7,
        enable_reranking: bool = True,
        enable_query_expansion: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context chunks for a query with advanced techniques
        
        Args:
            query: User query
            filter: Optional metadata filter
            top_k: Maximum number of chunks to retrieve
            min_relevance_score: Minimum relevance score threshold
            enable_reranking: Whether to enable semantic reranking
            enable_query_expansion: Whether to enable query expansion
            
        Returns:
            List of context chunks with metadata
        """
        try:
            logger.info(f"Retrieving context for query: '{query}' with filters: {filter}")
            
            # Process the query with expansion if enabled
            processed_query = query
            if enable_query_expansion:
                processed_query = await self._expand_query(query)
                logger.info(f"Expanded query: '{processed_query}'")
            
            # Retrieve initial results
            search_results = await self.embedding_service.search_similar(
                query=processed_query,
                filter=filter,
                top_k=top_k * 2  # Retrieve more than needed for filtering/reranking
            )
            
            # Filter results by relevance score
            filtered_results = [
                result for result in search_results 
                if result["score"] >= min_relevance_score
            ]
            
            # Perform reranking if enabled and we have multiple results
            if enable_reranking and len(filtered_results) > 1:
                logger.info("Performing semantic reranking")
                reranked_results = await self._semantic_reranking(
                    query=query,
                    results=filtered_results
                )
                top_results = reranked_results[:top_k]
            else:
                # Just take top K after filtering
                top_results = filtered_results[:top_k]
            
            # Format context chunks with extracted information
            context_chunks = []
            for i, result in enumerate(top_results):
                title = self._extract_title_from_metadata(result["metadata"], i)
                
                context_chunks.append({
                    "chunk_id": result["id"],
                    "chunk_content": result["metadata"].get("chunk_text_preview", ""),
                    "full_content": result["metadata"].get("chunk_text_preview", ""),
                    "score": result["score"],
                    "material_id": result["metadata"].get("material_id", ""),
                    "source_url": result["metadata"].get("source_url", ""),
                    "file_type": result["metadata"].get("file_type", ""),
                    "source_page": result["metadata"].get("source_page", None),
                    "chunk_index": result["metadata"].get("chunk_index", 0),
                    "total_chunks": result["metadata"].get("total_chunks", 0),
                    "title": title
                })
            
            logger.info(f"Retrieved {len(context_chunks)} relevant chunks for query")
            return context_chunks
            
        except Exception as e:
            logger.error(f"Error retrieving context: {str(e)}", exc_info=True)
            return []
    
    async def _expand_query(self, query: str) -> str:
        """
        Expand the user query to improve retrieval performance
        
        Args:
            query: Original user query
            
        Returns:
            Expanded query
        """
        try:
            from app.services.llm_service import LLMService
            
            llm_service = LLMService()
            
            system_prompt = """You are an AI assistant for a Retrieval Augmented Generation system. 
Your task is to expand the user's query to improve retrieval performance. 
Create an expanded version of the query that includes:
1. Relevant synonyms
2. More specific terminology
3. Related concepts
4. Alternative phrasings

DO NOT change the meaning or intent of the original query.
Respond with ONLY the expanded query, without any explanation or formatting."""
            
            user_prompt = f"""Original query: {query}

Expanded query:"""
            
            # Generate expanded query
            response = await llm_service.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.5,
                max_tokens=200
            )
            
            expanded_query = response.get("raw_response", "").strip()
            
            # Fallback to original query if expansion failed or is too different
            if not expanded_query or len(expanded_query) < len(query)/2:
                return query
            
            return expanded_query
            
        except Exception as e:
            logger.error(f"Error expanding query: {str(e)}", exc_info=True)
            # Fallback to original query
            return query
    
    async def _semantic_reranking(
        self, 
        query: str, 
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Rerank results based on semantic relevance to the query
        
        Args:
            query: Original user query
            results: Initial search results
            
        Returns:
            Reranked results
        """
        try:
            # Convert results to document format for reranking
            documents = []
            for result in results:
                doc_text = result["metadata"].get("chunk_text_preview", "")
                if not doc_text:
                    continue
                
                documents.append({
                    "text": doc_text,
                    "result": result
                })
            
            if not documents:
                return results
            
            # Compute semantic similarity between query and each document
            query_embedding = await self._get_embedding(query)
            
            reranked_results = []
            for doc in documents:
                # Get embedding for document text
                doc_embedding = await self._get_embedding(doc["text"])
                
                # Calculate cosine similarity
                similarity = self._cosine_similarity(query_embedding, doc_embedding)
                
                # Create reranked entry with updated score
                reranked_result = doc["result"].copy()
                reranked_result["score"] = similarity
                reranked_results.append(reranked_result)
            
            # Sort by score in descending order
            reranked_results.sort(key=lambda x: x["score"], reverse=True)
            
            return reranked_results
            
        except Exception as e:
            logger.error(f"Error reranking results: {str(e)}", exc_info=True)
            # Fallback to original results
            return results
    
    async def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text
        
        Args:
            text: Text to embed
            
        Returns:
            Vector embedding
        """
        # Truncate text if too long
        text = text[:8000]  # Approximate limit
        
        try:
            # We can reuse the embedding service method
            embedding = await self.embedding_service._get_embedding(text)
            return embedding
        except Exception as e:
            logger.error(f"Error getting embedding for reranking: {str(e)}", exc_info=True)
            # Return empty embedding as fallback
            return [0.0] * settings.EMBEDDING_DIMENSIONS
    
    def _cosine_similarity(self, vector_a: List[float], vector_b: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors
        
        Args:
            vector_a: First vector
            vector_b: Second vector
            
        Returns:
            Cosine similarity score
        """
        # Convert to numpy arrays for efficient computation
        a = np.array(vector_a)
        b = np.array(vector_b)
        
        # Calculate cosine similarity
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        # Handle zero division
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def _extract_title_from_metadata(self, metadata: Dict[str, Any], index: int) -> str:
        """
        Extract or generate a title from metadata
        
        Args:
            metadata: Chunk metadata
            index: Index of the result
            
        Returns:
            Extracted title
        """
        # Check for explicitly defined title
        if "chunk_title" in metadata:
            return metadata["chunk_title"]
        
        # Try to extract from material title
        if "material_title" in metadata:
            if "chunk_index" in metadata and "total_chunks" in metadata:
                return f"{metadata['material_title']} (Part {metadata['chunk_index']+1}/{metadata['total_chunks']})"
            return metadata["material_title"]
        
        # Check for file type to customize title
        file_type = metadata.get("file_type", "").lower()
        if file_type:
            if file_type in ["pdf", "docx", "doc"]:
                return f"Document {index+1}"
            elif file_type in ["py", "js", "java"]:
                return f"Code Snippet {index+1}"
            elif file_type in ["csv", "xlsx", "xls"]:
                return f"Data File {index+1}"
            elif file_type in ["md", "markdown"]:
                return f"Documentation {index+1}"
            elif file_type in ["jpg", "png", "gif"]:
                return f"Image Description {index+1}"
        
        # Fallback
        return f"Source {index+1}"
    
    async def retrieve_langchain(
        self,
        query: str,
        filter: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> List[Document]:
        """
        Retrieve documents using LangChain for integration with LangChain pipelines
        
        Args:
            query: User query
            filter: Optional metadata filter
            top_k: Maximum number of documents to retrieve
            
        Returns:
            List of LangChain Document objects
        """
        try:
            # Retrieve regular results
            results = await self.retrieve(
                query=query,
                filter=filter,
                top_k=top_k
            )
            
            # Convert to LangChain Documents
            documents = []
            for result in results:
                documents.append(
                    Document(
                        page_content=result["chunk_content"],
                        metadata={
                            "source": result["title"],
                            "material_id": result["material_id"],
                            "chunk_id": result["chunk_id"],
                            "score": result["score"]
                        }
                    )
                )
            
            return documents
            
        except Exception as e:
            logger.error(f"Error retrieving LangChain documents: {str(e)}", exc_info=True)
            return []