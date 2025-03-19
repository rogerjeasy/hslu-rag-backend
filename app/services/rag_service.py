import uuid
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from app.core.firebase import firebase
from app.core.config import settings
from app.core.exceptions import RAGException, NotFoundException
from app.rag.retriever import Retriever
from app.rag.llm_connector import LLMConnector

logger = logging.getLogger(__name__)

class RAGService:
    """
    Service for handling Retrieval-Augmented Generation (RAG) operations.
    
    This service manages the core RAG pipeline:
    1. Processing user queries
    2. Retrieving relevant document chunks
    3. Generating responses using LLM
    4. Saving query history
    """
    
    def __init__(self):
        """Initialize the RAG service with required components"""
        self.db = firebase.get_firestore()
        self.retriever = Retriever()
        self.llm_connector = LLMConnector()
    
    async def process_query(
        self,
        query: str,
        user_id: str,
        course_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a user query through the RAG pipeline.
        
        Args:
            query: The user's question or request
            user_id: The ID of the current user
            course_id: Optional course ID to restrict context retrieval
            conversation_id: Optional conversation ID for continuity
            
        Returns:
            Dictionary containing the response and metadata
        """
        try:
            # Create a new conversation ID if not provided
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # Get conversation history if available
            conversation_history = []
            if conversation_id:
                conversation_history = await self._get_conversation_history(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    limit=5  # Get last 5 exchanges
                )
            
            # Retrieve relevant document chunks from vector store
            retrieved_chunks = await self.retriever.retrieve(
                query=query,
                course_id=course_id,
                limit=5  # Top 5 most relevant chunks
            )
            
            if not retrieved_chunks:
                logger.warning(f"No relevant chunks found for query: {query}")
            
            # Generate response using LLM with retrieved context
            response = await self.llm_connector.generate_response(
                query=query,
                retrieved_chunks=retrieved_chunks,
                conversation_history=conversation_history
            )
            
            # Prepare the response object
            query_response = {
                "query_id": str(uuid.uuid4()),
                "query": query,
                "response": response["content"],
                "sources": response["sources"],
                "conversation_id": conversation_id,
                "timestamp": datetime.utcnow().isoformat(),
                "course_id": course_id,
            }
            
            return query_response
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            raise RAGException(f"Failed to process query: {str(e)}")
    
    async def save_query_history(
        self,
        user_id: str,
        query: str,
        response: Dict[str, Any],
        course_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> None:
        """
        Save the query and response to the user's history.
        
        Args:
            user_id: The ID of the current user
            query: The original user query
            response: The response object returned from process_query
            course_id: Optional course ID
            conversation_id: Optional conversation ID
        """
        try:
            # Prepare history entry
            history_entry = {
                "id": response["query_id"],
                "user_id": user_id,
                "query": query,
                "response": response["response"],
                "sources": response["sources"],
                "conversation_id": conversation_id or response["conversation_id"],
                "timestamp": response["timestamp"],
                "course_id": course_id,
            }
            
            # Save to Firestore
            self.db.collection("query_history").document(response["query_id"]).set(history_entry)
            
            logger.info(f"Saved query history for user {user_id}, query_id: {response['query_id']}")
            
        except Exception as e:
            logger.error(f"Error saving query history: {str(e)}")
            # Don't raise exception, as this is a background task
    
    async def get_query_history(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
        course_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get the query history for a user.
        
        Args:
            user_id: The ID of the user
            limit: Maximum number of results to return
            offset: Number of results to skip
            course_id: Optional course ID to filter by
            conversation_id: Optional conversation ID to filter by
            
        Returns:
            List of query history entries
        """
        try:
            # Build query
            query = self.db.collection("query_history").where("user_id", "==", user_id)
            
            # Apply filters if provided
            if course_id:
                query = query.where("course_id", "==", course_id)
            
            if conversation_id:
                query = query.where("conversation_id", "==", conversation_id)
            
            # Order and paginate
            results = query.order_by("timestamp", direction="DESCENDING").limit(limit).offset(offset).stream()
            
            # Convert to list
            history = [doc.to_dict() for doc in results]
            
            return history
            
        except Exception as e:
            logger.error(f"Error retrieving query history: {str(e)}")
            raise RAGException(f"Failed to retrieve query history: {str(e)}")
    
    async def get_user_conversations(self, user_id: str) -> List[str]:
        """
        Get all conversation IDs for a user.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            List of conversation IDs
        """
        try:
            # Get distinct conversation IDs
            query = self.db.collection("query_history").where("user_id", "==", user_id)
            results = query.select(["conversation_id"]).stream()
            
            # Extract conversation IDs and remove duplicates
            conversation_ids = {doc.to_dict().get("conversation_id") for doc in results if doc.to_dict().get("conversation_id")}
            
            return list(conversation_ids)
            
        except Exception as e:
            logger.error(f"Error retrieving user conversations: {str(e)}")
            raise RAGException(f"Failed to retrieve user conversations: {str(e)}")
    
    async def delete_query(self, query_id: str, user_id: str) -> None:
        """
        Delete a specific query from history.
        
        Args:
            query_id: The ID of the query to delete
            user_id: The ID of the user (for authorization)
        """
        try:
            # Get query document
            query_doc = self.db.collection("query_history").document(query_id).get()
            
            # Check if query exists
            if not query_doc.exists:
                raise NotFoundException(f"Query with ID {query_id} not found")
            
            # Check if query belongs to user
            query_data = query_doc.to_dict()
            if query_data.get("user_id") != user_id:
                raise RAGException("Not authorized to delete this query")
            
            # Delete the query
            self.db.collection("query_history").document(query_id).delete()
            
            logger.info(f"Deleted query {query_id} for user {user_id}")
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error deleting query: {str(e)}")
            raise RAGException(f"Failed to delete query: {str(e)}")
    
    async def _get_conversation_history(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get previous exchanges in a conversation for context.
        
        Args:
            user_id: The ID of the user
            conversation_id: The ID of the conversation
            limit: Maximum number of previous exchanges to retrieve
            
        Returns:
            List of previous queries and responses
        """
        try:
            # Query history for this conversation
            query = (
                self.db.collection("query_history")
                .where("user_id", "==", user_id)
                .where("conversation_id", "==", conversation_id)
                .order_by("timestamp", direction="DESCENDING")
                .limit(limit)
            )
            
            results = query.stream()
            
            # Format for LLM context
            history = []
            for doc in results:
                data = doc.to_dict()
                history.append({
                    "query": data.get("query", ""),
                    "response": data.get("response", "")
                })
            
            # Reverse to get chronological order
            history.reverse()
            
            return history
            
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {str(e)}")
            # Return empty history rather than failing
            return []