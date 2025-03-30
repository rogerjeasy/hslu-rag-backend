# app/services/firebase_storage_service.py
import logging
import time
import uuid
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

from app.core.exceptions import FirebaseException
from app.core.firebase import firebase
from app.schemas.rag_query import RAGResponse, KnowledgeGapResponse

logger = logging.getLogger(__name__)

class FirebaseStorageService:
    """
    Service for storing and deleting generated RAG content in Firebase Firestore
    """
    
    def __init__(self):
        """Initialize the firebase storage service"""
        try:
            self.db = firebase.get_firestore()
        except Exception as e:
            logger.error(f"Failed to initialize FirebaseStorageService: {str(e)}")
            raise FirebaseException(f"Firebase initialization error: {str(e)}")
    
    async def save_study_guide(self, response: RAGResponse, user_id: str) -> str:
        """
        Save a generated study guide to Firestore
        
        Args:
            response: The generated RAG response
            user_id: User ID who requested the study guide
            
        Returns:
            Document ID of the saved study guide
        """
        try:
            # Generate a unique ID
            doc_id = str(uuid.uuid4())
            
            # Create document data
            doc_data = {
            "id": doc_id,
            "user_id": user_id,
            "query": response.query,
            "answer": response.answer,
            "citations": response.citations,
            "context": [context.dict() for context in response.context],
            "created_at": int(time.time()),
            "course_id": response.meta.get("course_id") if response.meta else None,
            "module_id": response.meta.get("module_id") if response.meta else None,
            # Use explicit topic from metadata if available, fallback to query
            "topic": response.meta.get("topic") if response.meta and response.meta.get("topic") else response.query,
            "format": response.meta.get("format", "outline") if response.meta else "outline",
            "detail_level": response.meta.get("detail_level", "medium") if response.meta else "medium"
            }
            
            # Save to Firestore
            self.db.collection("study_guides").document(doc_id).set(doc_data)
            
            logger.info(f"Saved study guide with ID {doc_id} for user {user_id}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Error saving study guide to Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error saving study guide: {str(e)}")
    
    async def save_practice_questions(self, response: RAGResponse, user_id: str) -> str:
        """
        Save generated practice questions to Firestore
        
        Args:
            response: The generated RAG response
            user_id: User ID who requested the practice questions
            
        Returns:
            Document ID of the saved practice questions
        """
        try:
            # Generate a unique ID
            doc_id = str(uuid.uuid4())
            
            # Get questions from meta if available
            questions = []
            if response.meta and "questions" in response.meta:
                questions = response.meta["questions"]
            
            # Create document data
            doc_data = {
                "id": doc_id,
                "user_id": user_id,
                "query": response.query,
                "answer": response.answer,
                "questions": questions,
                "citations": response.citations,
                "context": [context.dict() for context in response.context],
                "created_at": int(time.time()),
                "course_id": response.meta.get("course_id") if response.meta else None,
                "module_id": response.meta.get("module_id") if response.meta else None,
                "topic": response.meta.get("topic") if response.meta else response.query,
                "difficulty": response.meta.get("difficulty", "medium") if response.meta else "medium",
                "question_count": len(questions)
            }
            
            # Save to Firestore
            self.db.collection("practice_questions").document(doc_id).set(doc_data)
            
            logger.info(f"Saved practice questions with ID {doc_id} for user {user_id}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Error saving practice questions to Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error saving practice questions: {str(e)}")
    
    async def save_knowledge_gap(self, response: KnowledgeGapResponse, user_id: str) -> str:
        """
        Save a knowledge gap analysis to Firestore
        
        Args:
            response: The generated knowledge gap response
            user_id: User ID who requested the analysis
            
        Returns:
            Document ID of the saved knowledge gap analysis
        """
        try:
            # Generate a unique ID
            doc_id = str(uuid.uuid4())
            
            # Create document data
            doc_data = {
                "id": doc_id,
                "user_id": user_id,
                "query": response.query,
                "answer": response.answer,
                "gaps": [gap.dict() for gap in response.gaps],
                "strengths": [strength.dict() for strength in response.strengths],
                "citations": response.citations,
                "context": [context.dict() for context in response.context],
                "created_at": int(time.time()),
                "course_id": None,  # Add from meta if available in future
                "module_id": None,  # Add from meta if available in future
                "topic": response.query
            }
            
            # Save to Firestore
            self.db.collection("knowledge_gaps").document(doc_id).set(doc_data)
            
            logger.info(f"Saved knowledge gap analysis with ID {doc_id} for user {user_id}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Error saving knowledge gap analysis to Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error saving knowledge gap analysis: {str(e)}")
    
    async def delete_study_guide(self, doc_id: str, user_id: str) -> Tuple[bool, str]:
        """
        Delete a study guide from Firestore
        
        Args:
            doc_id: Document ID of the study guide to delete
            user_id: User ID requesting deletion (for access control)
            
        Returns:
            Tuple of (success status, message)
        """
        try:
            # Get document reference
            doc_ref = self.db.collection("study_guides").document(doc_id)
            doc = doc_ref.get()
            
            # Check if document exists
            if not doc.exists:
                return False, f"Study guide with ID {doc_id} not found"
                
            # Get document data
            data = doc.to_dict()
            
            # Check user access
            if data.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to delete study guide {doc_id} belonging to user {data.get('user_id')}")
                return False, "You do not have permission to delete this study guide"
            
            # Delete the document
            doc_ref.delete()
            
            logger.info(f"Deleted study guide with ID {doc_id} for user {user_id}")
            return True, f"Study guide with ID {doc_id} deleted successfully"
            
        except Exception as e:
            logger.error(f"Error deleting study guide from Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error deleting study guide: {str(e)}")
    
    async def delete_practice_questions(self, doc_id: str, user_id: str) -> Tuple[bool, str]:
        """
        Delete practice questions from Firestore
        
        Args:
            doc_id: Document ID of the practice questions to delete
            user_id: User ID requesting deletion (for access control)
            
        Returns:
            Tuple of (success status, message)
        """
        try:
            # Get document reference
            doc_ref = self.db.collection("practice_questions").document(doc_id)
            doc = doc_ref.get()
            
            # Check if document exists
            if not doc.exists:
                return False, f"Practice questions with ID {doc_id} not found"
                
            # Get document data
            data = doc.to_dict()
            
            # Check user access
            if data.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to delete practice questions {doc_id} belonging to user {data.get('user_id')}")
                return False, "You do not have permission to delete these practice questions"
            
            # Delete the document
            doc_ref.delete()
            
            logger.info(f"Deleted practice questions with ID {doc_id} for user {user_id}")
            return True, f"Practice questions with ID {doc_id} deleted successfully"
            
        except Exception as e:
            logger.error(f"Error deleting practice questions from Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error deleting practice questions: {str(e)}")
    
    async def delete_knowledge_gap(self, doc_id: str, user_id: str) -> Tuple[bool, str]:
        """
        Delete a knowledge gap analysis from Firestore
        
        Args:
            doc_id: Document ID of the knowledge gap analysis to delete
            user_id: User ID requesting deletion (for access control)
            
        Returns:
            Tuple of (success status, message)
        """
        try:
            # Get document reference
            doc_ref = self.db.collection("knowledge_gaps").document(doc_id)
            doc = doc_ref.get()
            
            # Check if document exists
            if not doc.exists:
                return False, f"Knowledge gap analysis with ID {doc_id} not found"
                
            # Get document data
            data = doc.to_dict()
            
            # Check user access
            if data.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to delete knowledge gap analysis {doc_id} belonging to user {data.get('user_id')}")
                return False, "You do not have permission to delete this knowledge gap analysis"
            
            # Delete the document
            doc_ref.delete()
            
            logger.info(f"Deleted knowledge gap analysis with ID {doc_id} for user {user_id}")
            return True, f"Knowledge gap analysis with ID {doc_id} deleted successfully"
            
        except Exception as e:
            logger.error(f"Error deleting knowledge gap analysis from Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error deleting knowledge gap analysis: {str(e)}")
    
    async def delete_all_user_content(self, user_id: str) -> Dict[str, Any]:
        """
        Delete all content for a specific user across all collections
        
        Args:
            user_id: User ID whose content should be deleted
            
        Returns:
            Dictionary with counts of deleted items by collection
        """
        try:
            results = {
                "study_guides": 0,
                "practice_questions": 0,
                "knowledge_gaps": 0,
                "total": 0
            }
            
            # Delete study guides
            sg_query = self.db.collection("study_guides").where("user_id", "==", user_id)
            sg_docs = sg_query.stream()
            for doc in sg_docs:
                doc.reference.delete()
                results["study_guides"] += 1
                
            # Delete practice questions
            pq_query = self.db.collection("practice_questions").where("user_id", "==", user_id)
            pq_docs = pq_query.stream()
            for doc in pq_docs:
                doc.reference.delete()
                results["practice_questions"] += 1
            
            # Delete knowledge gaps
            kg_query = self.db.collection("knowledge_gaps").where("user_id", "==", user_id)
            kg_docs = kg_query.stream()
            for doc in kg_docs:
                doc.reference.delete()
                results["knowledge_gaps"] += 1
            
            # Calculate total
            results["total"] = results["study_guides"] + results["practice_questions"] + results["knowledge_gaps"]
            
            logger.info(f"Deleted all content for user {user_id}. Total items deleted: {results['total']}")
            return results
            
        except Exception as e:
            logger.error(f"Error deleting all user content from Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error deleting user content: {str(e)}")