# app/services/conversation_service.py
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.core.exceptions import FirebaseException
from app.core.firebase import firebase
from app.schemas.rag_query import RAGResponse

logger = logging.getLogger(__name__)

class ConversationService:
    """
    Service for managing conversations in Firebase Firestore
    """
    
    def __init__(self):
        """Initialize the conversation service"""
        try:
            self.db = firebase.get_firestore()
        except Exception as e:
            logger.error(f"Failed to initialize ConversationService: {str(e)}")
            raise FirebaseException(f"Firebase initialization error: {str(e)}")
    
    async def create_conversation(self, user_id: str, title: str = None, course_id: Optional[str] = None, 
                           module_id: Optional[str] = None, topic_id: Optional[str] = None) -> str:
        """
        Create a new conversation in Firestore
        
        Args:
            user_id: User ID who owns the conversation
            title: Optional title for the conversation (defaults to timestamp if not provided)
            course_id: Optional associated course ID
            module_id: Optional associated module ID
            topic_id: Optional associated topic ID
            
        Returns:
            Document ID of the created conversation
        """
        try:
            # Generate a unique ID
            doc_id = str(uuid.uuid4())
            
            # Create default title if not provided
            if not title or title.strip() == "":
                title = f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            # Truncate title if too long
            if title and len(title) > 50:
                title = title[:47] + "..."
            
            # Create document data
            doc_data = {
                "id": doc_id,
                "user_id": user_id,
                "title": title,
                "course_id": course_id,
                "module_id": module_id,
                "topic_id": topic_id,
                "messages": [],
                "created_at": int(time.time()),
                "updated_at": int(time.time())
            }
            
            # Save to Firestore
            self.db.collection("conversations").document(doc_id).set(doc_data)
            
            logger.info(f"Created conversation with ID {doc_id} for user {user_id}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Error creating conversation in Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error creating conversation: {str(e)}")
    
    async def get_conversation(self, conversation_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get a conversation from Firestore
        
        Args:
            conversation_id: ID of the conversation
            user_id: Optional user ID for access control
            
        Returns:
            Conversation data if found, None otherwise
        """
        try:
            # Get document reference
            doc_ref = self.db.collection("conversations").document(conversation_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.warning(f"Conversation with ID {conversation_id} not found")
                return None
                
            # Get document data
            data = doc.to_dict()
            
            # Check user access if user_id provided
            if user_id and data.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to access conversation {conversation_id} belonging to user {data.get('user_id')}")
                return None
            
            # Convert timestamp objects to integers
            if hasattr(data.get("created_at"), "timestamp"):
                data["created_at"] = int(data["created_at"].timestamp())
            
            if hasattr(data.get("updated_at"), "timestamp"):
                data["updated_at"] = int(data["updated_at"].timestamp())
            
            return data
            
        except Exception as e:
            logger.error(f"Error retrieving conversation from Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error retrieving conversation: {str(e)}")
    
    def list_user_conversations(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List conversations for a specific user
        
        Args:
            user_id: User ID
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversation summary objects
        """
        try:
            # Query Firestore for user's conversations
            query = self.db.collection("conversations").where("user_id", "==", user_id).order_by("updated_at", direction="DESCENDING").limit(limit)
            docs = query.stream()
            
            # Convert to list of summaries
            results = []
            for doc in docs:
                data = doc.to_dict()
                
                # Convert timestamp objects to integers
                created_at = data.get("created_at", 0)
                updated_at = data.get("updated_at", 0)
                
                # Check if timestamps are Firebase DatetimeWithNanoseconds objects and convert them
                if hasattr(created_at, "timestamp"):
                    created_at = int(created_at.timestamp())
                
                if hasattr(updated_at, "timestamp"):
                    updated_at = int(updated_at.timestamp())
                
                # Calculate message count
                message_count = len(data.get("messages", []))
                
                # Get the latest message content preview if available
                latest_message = None
                if message_count > 0:
                    messages = data.get("messages", [])
                    latest_message = messages[-1]
                    if latest_message and "content" in latest_message:
                        latest_message = latest_message["content"]
                        if len(latest_message) > 30:
                            latest_message = latest_message[:27] + "..."
                
                # Create conversation summary
                results.append({
                    "id": doc.id,
                    "title": data.get("title", "Untitled Conversation"),
                    "course_id": data.get("course_id"),
                    "module_id": data.get("module_id"),
                    "topic_id": data.get("topic_id"),
                    "message_count": message_count,
                    "latest_message": latest_message,
                    "created_at": created_at,
                    "updated_at": updated_at
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error listing user conversations from Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error listing user conversations: {str(e)}")
    
    async def add_message(self, conversation_id: str, user_id: str, role: str, content: str, 
                   metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Add a message to a conversation
        
        Args:
            conversation_id: ID of the conversation
            user_id: User ID for access control
            role: Message role (user/assistant)
            content: Message content
            metadata: Optional metadata for the message
            
        Returns:
            Updated message data
        """
        try:
            # Check conversation exists and user has access
            conversation = await self.get_conversation(conversation_id, user_id)
            if not conversation:
                raise FirebaseException(f"Conversation not found or access denied: {conversation_id}")
            
            # Create message data
            message_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            message_data = {
                "id": message_id,
                "role": role,
                "content": content,
                "timestamp": timestamp
            }
            
            # Add metadata if provided
            if metadata:
                message_data["metadata"] = metadata
            
            # Get current messages and append new message
            messages = conversation.get("messages", [])
            messages.append(message_data)
            
            # Update conversation
            doc_ref = self.db.collection("conversations").document(conversation_id)
            doc_ref.update({
                "messages": messages,
                "updated_at": int(time.time())
            })
            
            logger.info(f"Added message {message_id} to conversation {conversation_id}")
            return message_data
            
        except FirebaseException:
            raise
        except Exception as e:
            logger.error(f"Error adding message to conversation: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error adding message to conversation: {str(e)}")
    
    async def add_rag_response(self, conversation_id: str, user_id: str, rag_response: RAGResponse) -> Dict[str, Any]:
        """
        Add a RAG response as a message to a conversation
        
        Args:
            conversation_id: ID of the conversation
            user_id: User ID for access control
            rag_response: RAG response object
            
        Returns:
            Added message data
        """
        try:
            # Create metadata from RAG response
            metadata = {
                "citations": rag_response.citations,
                "query_id": rag_response.query_id
            }
            
            # Add message
            return await self.add_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="assistant",
                content=rag_response.answer,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error adding RAG response to conversation: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error adding RAG response to conversation: {str(e)}")
    
    async def update_conversation_metadata(self, conversation_id: str, user_id: str, 
                                    updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update conversation metadata (title, course_id, etc.)
        
        Args:
            conversation_id: ID of the conversation
            user_id: User ID for access control
            updates: Dictionary of fields to update
            
        Returns:
            Updated conversation data
        """
        try:
            # Check conversation exists and user has access
            conversation = await self.get_conversation(conversation_id, user_id)
            if not conversation:
                raise FirebaseException(f"Conversation not found or access denied: {conversation_id}")
            
            # Filter updates to only allow certain fields
            allowed_fields = ["title", "course_id", "module_id", "topic_id"]
            filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
            
            # Add updated_at timestamp
            filtered_updates["updated_at"] = int(time.time())
            
            # Update conversation
            doc_ref = self.db.collection("conversations").document(conversation_id)
            doc_ref.update(filtered_updates)
            
            # Get updated conversation
            updated_conversation = await self.get_conversation(conversation_id)
            
            logger.info(f"Updated conversation metadata for {conversation_id}")
            return updated_conversation
            
        except FirebaseException:
            raise
        except Exception as e:
            logger.error(f"Error updating conversation metadata: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error updating conversation metadata: {str(e)}")
    
    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """
        Delete a conversation
        
        Args:
            conversation_id: ID of the conversation to delete
            user_id: User ID for access control
            
        Returns:
            Success status
        """
        try:
            # Check conversation exists and user has access
            conversation = await self.get_conversation(conversation_id, user_id)
            if not conversation:
                return False
            
            # Delete conversation
            doc_ref = self.db.collection("conversations").document(conversation_id)
            doc_ref.delete()
            
            logger.info(f"Deleted conversation {conversation_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting conversation: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error deleting conversation: {str(e)}")
    
    async def delete_all_user_conversations(self, user_id: str) -> int:
        """
        Delete all conversations for a user
        
        Args:
            user_id: User ID whose conversations should be deleted
            
        Returns:
            Number of conversations deleted
        """
        try:
            # Query for user's conversations
            query = self.db.collection("conversations").where("user_id", "==", user_id)
            docs = query.stream()
            
            # Delete each conversation
            count = 0
            for doc in docs:
                doc.reference.delete()
                count += 1
            
            logger.info(f"Deleted {count} conversations for user {user_id}")
            return count
            
        except Exception as e:
            logger.error(f"Error deleting user conversations: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error deleting user conversations: {str(e)}")