# app/services/firestore_service.py

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from google.cloud.firestore import Client as FirestoreClient, SERVER_TIMESTAMP
from app.core.exceptions import FirebaseException, NotFoundException, ValidationException

logger = logging.getLogger(__name__)

class FirestoreService:
    """Service for interacting with Firestore database"""
    
    def __init__(self, firestore_client: FirestoreClient):
        """Initialize with Firestore client"""
        self.db = firestore_client
    
    # Existing methods for user and course operations...
    
    # Conversation methods
    async def create_conversation(self, user_id: str, course_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new conversation.
        
        Args:
            user_id: User ID
            course_id: Course ID
            data: Conversation data
            
        Returns:
            Created conversation with ID
        """
        try:
            conversation_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            conversation_data = {
                "id": conversation_id,
                "user_id": user_id,
                "course_id": course_id,
                "module_id": data.get("module_id"),
                "topic_id": data.get("topic_id"),
                "title": data.get("title", "New Conversation"),
                "created_at": now,
                "updated_at": now,
                "messages": []
            }
            
            # Add initial message if provided
            if data.get("initial_message"):
                conversation_data["messages"] = [
                    {
                        "id": str(uuid.uuid4()),
                        "content": data["initial_message"],
                        "role": "user",
                        "timestamp": now.isoformat()
                    }
                ]
            
            # Save to Firestore
            self.db.collection("conversations").document(conversation_id).set(conversation_data)
            
            return conversation_data
            
        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}")
            raise FirebaseException(f"Failed to create conversation: {str(e)}")
    
    async def add_message_to_conversation(
        self, conversation_id: str, user_id: str, message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add a message to a conversation.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID (for authorization)
            message_data: Message data
            
        Returns:
            Added message with ID
        """
        try:
            # Get conversation
            conversation_ref = self.db.collection("conversations").document(conversation_id)
            conversation = conversation_ref.get()
            
            if not conversation.exists:
                raise NotFoundException(f"Conversation {conversation_id} not found")
            
            # Check if user owns the conversation
            conversation_data = conversation.to_dict()
            if conversation_data.get("user_id") != user_id:
                raise ValidationException("Not authorized to add messages to this conversation")
            
            # Create message
            now = datetime.utcnow()
            message_id = str(uuid.uuid4())
            message = {
                "id": message_id,
                "content": message_data["content"],
                "role": message_data.get("role", "user"),
                "timestamp": now.isoformat(),
                "metadata": message_data.get("metadata", {})
            }
            
            # Update conversation
            messages = conversation_data.get("messages", [])
            messages.append(message)
            
            # Update conversation in Firestore
            conversation_ref.update({
                "messages": messages,
                "updated_at": now
            })
            
            return message
            
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(f"Error adding message to conversation: {str(e)}")
            raise FirebaseException(f"Failed to add message to conversation: {str(e)}")
    
    async def get_conversation(self, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get a conversation by ID.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID (for authorization)
            
        Returns:
            Conversation data
        """
        try:
            conversation_ref = self.db.collection("conversations").document(conversation_id)
            conversation = conversation_ref.get()
            
            if not conversation.exists:
                raise NotFoundException(f"Conversation {conversation_id} not found")
            
            conversation_data = conversation.to_dict()
            
            # Check if user owns the conversation
            if conversation_data.get("user_id") != user_id:
                raise ValidationException("Not authorized to access this conversation")
            
            return conversation_data
            
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(f"Error getting conversation: {str(e)}")
            raise FirebaseException(f"Failed to get conversation: {str(e)}")
    
    async def get_user_conversations(self, user_id: str, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all conversations for a user, optionally filtered by course.
        
        Args:
            user_id: User ID
            course_id: Optional course ID filter
            
        Returns:
            List of conversation summaries (empty list if no conversations exist)
        """
        try:
            query = self.db.collection("conversations").where("user_id", "==", user_id)
            
            if course_id:
                query = query.where("course_id", "==", course_id)
            
            conversations = []
            for doc in query.stream():
                conversation = doc.to_dict()
                # Create a summary without all messages
                conversations.append({
                    "id": conversation.get("id"),
                    "title": conversation.get("title"),
                    "course_id": conversation.get("course_id"),
                    "module_id": conversation.get("module_id"),
                    "topic_id": conversation.get("topic_id"),
                    "created_at": conversation.get("created_at"),
                    "updated_at": conversation.get("updated_at"),
                    "message_count": len(conversation.get("messages", [])),
                    "last_message": conversation.get("messages", [])[-1] if conversation.get("messages") else None
                })
            
            # Log if no conversations found
            if not conversations:
                logger.info(f"No conversations found for user {user_id}" + 
                        (f" in course {course_id}" if course_id else ""))
            
            # Sort by updated_at (newest first)
            if conversations and len(conversations) > 1:
                conversations.sort(key=lambda x: x.get("updated_at", datetime.min), reverse=True)
            
            return conversations
            
        except Exception as e:
            logger.error(f"Error getting user conversations: {str(e)}")
            raise FirebaseException(f"Failed to get user conversations: {str(e)}")
        
    async def delete_document(self, collection: str, document_id: str) -> None:
        """
        Delete a document from a collection.
        
        Args:
            collection: Collection name
            document_id: Document ID
            
        Raises:
            NotFoundException: If document not found
            FirebaseException: For other Firebase errors
        """
        try:
            doc_ref = self.db.collection(collection).document(document_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise NotFoundException(f"Document {document_id} not found in {collection}")
            
            # Delete the document
            doc_ref.delete()
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            raise FirebaseException(f"Failed to delete document: {str(e)}")
        
    # Study Guide methods
    async def create_study_guide(self, user_id: str, course_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new study guide.
        
        Args:
            user_id: User ID
            course_id: Course ID
            data: Study guide data
            
        Returns:
            Created study guide with ID
        """
        try:
            guide_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            guide_data = {
                "id": guide_id,
                "user_id": user_id,
                "course_id": course_id,
                "module_id": data.get("module_id"),
                "topic_id": data.get("topic_id"),
                "title": data.get("title", "Study Guide"),
                "description": data.get("description"),
                "detail_level": data.get("detail_level", "medium"),
                "format": data.get("format", "outline"),
                "sections": data.get("sections", []),
                "citations": data.get("citations", []),
                "created_at": now,
                "updated_at": now
            }
            
            # Save to Firestore
            self.db.collection("study_guides").document(guide_id).set(guide_data)
            
            return guide_data
            
        except Exception as e:
            logger.error(f"Error creating study guide: {str(e)}")
            raise FirebaseException(f"Failed to create study guide: {str(e)}")
    
    async def get_study_guide(self, guide_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get a study guide by ID.
        
        Args:
            guide_id: Study guide ID
            user_id: User ID (for authorization)
            
        Returns:
            Study guide data
        """
        try:
            guide_ref = self.db.collection("study_guides").document(guide_id)
            guide = guide_ref.get()
            
            if not guide.exists:
                raise NotFoundException(f"Study guide {guide_id} not found")
            
            guide_data = guide.to_dict()
            
            # Check if user owns the study guide
            if guide_data.get("user_id") != user_id:
                raise ValidationException("Not authorized to access this study guide")
            
            return guide_data
            
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(f"Error getting study guide: {str(e)}")
            raise FirebaseException(f"Failed to get study guide: {str(e)}")
    
    async def get_user_study_guides(self, user_id: str, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all study guides for a user, optionally filtered by course.
        
        Args:
            user_id: User ID
            course_id: Optional course ID filter
            
        Returns:
            List of study guide summaries
        """
        try:
            query = self.db.collection("study_guides").where("user_id", "==", user_id)
            
            if course_id:
                query = query.where("course_id", "==", course_id)
            
            guides = []
            for doc in query.stream():
                guide = doc.to_dict()
                # Create a summary without all sections
                guides.append({
                    "id": guide.get("id"),
                    "title": guide.get("title"),
                    "description": guide.get("description"),
                    "course_id": guide.get("course_id"),
                    "module_id": guide.get("module_id"),
                    "topic_id": guide.get("topic_id"),
                    "created_at": guide.get("created_at"),
                    "updated_at": guide.get("updated_at"),
                    "detail_level": guide.get("detail_level"),
                    "format": guide.get("format"),
                    "section_count": len(guide.get("sections", []))
                })
            
            # Sort by created_at (newest first)
            guides.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
            
            return guides
            
        except Exception as e:
            logger.error(f"Error getting user study guides: {str(e)}")
            raise FirebaseException(f"Failed to get user study guides: {str(e)}")
    
    # Practice Questions methods
    async def create_practice_questions(self, user_id: str, course_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new practice question set.
        
        Args:
            user_id: User ID
            course_id: Course ID
            data: Question set data
            
        Returns:
            Created question set with ID
        """
        try:
            question_set_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            question_set_data = {
                "id": question_set_id,
                "user_id": user_id,
                "course_id": course_id,
                "module_id": data.get("module_id"),
                "topic_id": data.get("topic_id"),
                "title": data.get("title", "Practice Questions"),
                "description": data.get("description"),
                "difficulty": data.get("difficulty", "medium"),
                "questions": data.get("questions", []),
                "citations": data.get("citations", []),
                "created_at": now,
                "updated_at": now
            }
            
            # Save to Firestore
            self.db.collection("practice_questions").document(question_set_id).set(question_set_data)
            
            return question_set_data
            
        except Exception as e:
            logger.error(f"Error creating practice questions: {str(e)}")
            raise FirebaseException(f"Failed to create practice questions: {str(e)}")
    
    async def get_practice_questions(self, question_set_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get a practice question set by ID.
        
        Args:
            question_set_id: Question set ID
            user_id: User ID (for authorization)
            
        Returns:
            Question set data
        """
        try:
            question_set_ref = self.db.collection("practice_questions").document(question_set_id)
            question_set = question_set_ref.get()
            
            if not question_set.exists:
                raise NotFoundException(f"Practice question set {question_set_id} not found")
            
            question_set_data = question_set.to_dict()
            
            # Check if user owns the question set
            if question_set_data.get("user_id") != user_id:
                raise ValidationException("Not authorized to access these practice questions")
            
            return question_set_data
            
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(f"Error getting practice questions: {str(e)}")
            raise FirebaseException(f"Failed to get practice questions: {str(e)}")
    
    async def get_user_practice_questions(self, user_id: str, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all practice question sets for a user, optionally filtered by course.
        
        Args:
            user_id: User ID
            course_id: Optional course ID filter
            
        Returns:
            List of question set summaries
        """
        try:
            query = self.db.collection("practice_questions").where("user_id", "==", user_id)
            
            if course_id:
                query = query.where("course_id", "==", course_id)
            
            question_sets = []
            for doc in query.stream():
                question_set = doc.to_dict()
                # Create a summary without all questions
                question_sets.append({
                    "id": question_set.get("id"),
                    "title": question_set.get("title"),
                    "description": question_set.get("description"),
                    "course_id": question_set.get("course_id"),
                    "module_id": question_set.get("module_id"),
                    "topic_id": question_set.get("topic_id"),
                    "created_at": question_set.get("created_at"),
                    "difficulty": question_set.get("difficulty"),
                    "question_count": len(question_set.get("questions", [])),
                    "question_types": list(set(q.get("type", "unknown") for q in question_set.get("questions", [])))
                })
            
            # Sort by created_at (newest first)
            question_sets.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
            
            return question_sets
            
        except Exception as e:
            logger.error(f"Error getting user practice questions: {str(e)}")
            raise FirebaseException(f"Failed to get user practice questions: {str(e)}")
    
    # Knowledge Gap methods
    async def create_knowledge_gap(self, user_id: str, course_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new knowledge gap assessment.
        
        Args:
            user_id: User ID
            course_id: Course ID
            data: Assessment data
            
        Returns:
            Created assessment with ID
        """
        try:
            assessment_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            assessment_data = {
                "id": assessment_id,
                "user_id": user_id,
                "course_id": course_id,
                "module_id": data.get("module_id"),
                "topic_id": data.get("topic_id"),
                "title": data.get("title", "Knowledge Assessment"),
                "gaps": data.get("gaps", []),
                "strengths": data.get("strengths", []),
                "recommended_study_plan": data.get("recommended_study_plan"),
                "citations": data.get("citations", []),
                "created_at": now,
                "updated_at": now
            }
            
            # Save to Firestore
            self.db.collection("knowledge_gaps").document(assessment_id).set(assessment_data)
            
            return assessment_data
            
        except Exception as e:
            logger.error(f"Error creating knowledge gap assessment: {str(e)}")
            raise FirebaseException(f"Failed to create knowledge gap assessment: {str(e)}")
    
    async def get_knowledge_gap(self, assessment_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get a knowledge gap assessment by ID.
        
        Args:
            assessment_id: Assessment ID
            user_id: User ID (for authorization)
            
        Returns:
            Assessment data
        """
        try:
            assessment_ref = self.db.collection("knowledge_gaps").document(assessment_id)
            assessment = assessment_ref.get()
            
            if not assessment.exists:
                raise NotFoundException(f"Knowledge gap assessment {assessment_id} not found")
            
            assessment_data = assessment.to_dict()
            
            # Check if user owns the assessment
            if assessment_data.get("user_id") != user_id:
                raise ValidationException("Not authorized to access this knowledge gap assessment")
            
            return assessment_data
            
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(f"Error getting knowledge gap assessment: {str(e)}")
            raise FirebaseException(f"Failed to get knowledge gap assessment: {str(e)}")
    
    async def get_user_knowledge_gaps(self, user_id: str, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all knowledge gap assessments for a user, optionally filtered by course.
        
        Args:
            user_id: User ID
            course_id: Optional course ID filter
            
        Returns:
            List of assessment summaries
        """
        try:
            query = self.db.collection("knowledge_gaps").where("user_id", "==", user_id)
            
            if course_id:
                query = query.where("course_id", "==", course_id)
            
            assessments = []
            for doc in query.stream():
                assessment = doc.to_dict()
                # Create a summary without all gaps
                assessments.append({
                    "id": assessment.get("id"),
                    "title": assessment.get("title"),
                    "course_id": assessment.get("course_id"),
                    "module_id": assessment.get("module_id"),
                    "topic_id": assessment.get("topic_id"),
                    "created_at": assessment.get("created_at"),
                    "gap_count": len(assessment.get("gaps", [])),
                    "highest_severity": max((gap.get("severity", "low") for gap in assessment.get("gaps", [])), default=None)
                })
            
            # Sort by created_at (newest first)
            assessments.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
            
            return assessments
            
        except Exception as e:
            logger.error(f"Error getting user knowledge gaps: {str(e)}")
            raise FirebaseException(f"Failed to get user knowledge gaps: {str(e)}")
        
    
    async def update_document(
        self, collection: str, document_id: str, data: Dict[str, Any]
    ) -> None:
        """
        Update a document in a collection.
        
        Args:
            collection: Collection name
            document_id: Document ID
            data: Data to update
            
        Raises:
            NotFoundException: If document not found
            FirebaseException: For other Firebase errors
        """
        try:
            doc_ref = self.db.collection(collection).document(document_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise NotFoundException(f"Document {document_id} not found in {collection}")
            
            # Update the document
            doc_ref.update(data)
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error updating document: {str(e)}")
            raise FirebaseException(f"Failed to update document: {str(e)}")
        
    
    async def add_document(
        self, collection: str, data: Dict[str, Any], document_id: Optional[str] = None
    ) -> str:
        """
        Add a new document to a collection.
        
        Args:
            collection: Collection name
            data: Document data
            document_id: Optional document ID (generates UUID if not provided)
            
        Returns:
            Document ID
            
        Raises:
            FirebaseException: For Firebase errors
        """
        try:
            if document_id:
                doc_ref = self.db.collection(collection).document(document_id)
                doc_ref.set(data)
                return document_id
            else:
                # Generate a new document ID
                doc_id = str(uuid.uuid4())
                doc_ref = self.db.collection(collection).document(doc_id)
                doc_ref.set(data)
                return doc_id
            
        except Exception as e:
            logger.error(f"Error adding document: {str(e)}")
            raise FirebaseException(f"Failed to add document: {str(e)}")

    def server_timestamp(self):
        """Get a server timestamp for Firestore"""
        return SERVER_TIMESTAMP