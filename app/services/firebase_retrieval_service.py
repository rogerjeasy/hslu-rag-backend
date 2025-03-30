# app/services/firebase_retrieval_service.py
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime

from app.core.exceptions import FirebaseException
from app.core.firebase import firebase
from app.schemas.rag_query import RAGResponse, RAGContext, KnowledgeGapResponse, KnowledgeGap, Strength

logger = logging.getLogger(__name__)

class FirebaseRetrievalService:
    """
    Service for retrieving stored RAG content from Firebase Firestore
    """
    
    def __init__(self):
        """Initialize the firebase retrieval service"""
        try:
            self.db = firebase.get_firestore()
        except Exception as e:
            logger.error(f"Failed to initialize FirebaseRetrievalService: {str(e)}")
            raise FirebaseException(f"Firebase initialization error: {str(e)}")
    
    async def get_study_guide(self, doc_id: str, user_id: Optional[str] = None) -> Optional[RAGResponse]:
        """
        Retrieve a study guide from Firestore
        
        Args:
            doc_id: Document ID of the study guide
            user_id: Optional user ID for access control
            
        Returns:
            RAGResponse object if found, None otherwise
        """
        try:
            # Get document reference
            doc_ref = self.db.collection("study_guides").document(doc_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.warning(f"Study guide with ID {doc_id} not found")
                return None
                
            # Get document data
            data = doc.to_dict()
            
            # Check user access if user_id provided
            if user_id and data.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to access study guide {doc_id} belonging to user {data.get('user_id')}")
                return None
            
            # Convert to RAGResponse
            context_list = []
            for ctx in data.get("context", []):
                context_list.append(RAGContext(**ctx))
            
            # Create response object
            response = RAGResponse(
                query_id=data.get("id", doc_id),
                query=data.get("query", ""),
                answer=data.get("answer", ""),
                context=context_list,
                citations=data.get("citations", []),
                prompt_type="study_guide",
                timestamp=datetime.fromtimestamp(data.get("created_at", 0)),
                meta={
                    "course_id": data.get("course_id"),
                    "module_id": data.get("module_id"),
                    "topic": data.get("topic"),
                    "format": data.get("format"),
                    "detail_level": data.get("detail_level"),
                    "document_id": doc_id
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error retrieving study guide from Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error retrieving study guide: {str(e)}")
    
    async def get_practice_questions(self, doc_id: str, user_id: Optional[str] = None) -> Optional[RAGResponse]:
        """
        Retrieve practice questions from Firestore
        
        Args:
            doc_id: Document ID of the practice questions
            user_id: Optional user ID for access control
            
        Returns:
            RAGResponse object if found, None otherwise
        """
        try:
            # Get document reference
            doc_ref = self.db.collection("practice_questions").document(doc_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.warning(f"Practice questions with ID {doc_id} not found")
                return None
                
            # Get document data
            data = doc.to_dict()
            
            # Check user access if user_id provided
            if user_id and data.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to access practice questions {doc_id} belonging to user {data.get('user_id')}")
                return None
            
            # Convert to RAGResponse
            context_list = []
            for ctx in data.get("context", []):
                context_list.append(RAGContext(**ctx))
            
            # Create response object
            response = RAGResponse(
                query_id=data.get("id", doc_id),
                query=data.get("query", ""),
                answer=data.get("answer", ""),
                context=context_list,
                citations=data.get("citations", []),
                prompt_type="practice_questions",
                timestamp=datetime.fromtimestamp(data.get("created_at", 0)),
                meta={
                    "course_id": data.get("course_id"),
                    "module_id": data.get("module_id"),
                    "topic": data.get("topic"),
                    "difficulty": data.get("difficulty"),
                    "question_count": data.get("question_count"),
                    "questions": data.get("questions", []),
                    "document_id": doc_id
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error retrieving practice questions from Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error retrieving practice questions: {str(e)}")
    
    async def get_knowledge_gap(self, doc_id: str, user_id: Optional[str] = None) -> Optional[KnowledgeGapResponse]:
        """
        Retrieve a knowledge gap analysis from Firestore
        
        Args:
            doc_id: Document ID of the knowledge gap analysis
            user_id: Optional user ID for access control
            
        Returns:
            KnowledgeGapResponse object if found, None otherwise
        """
        try:
            # Get document reference
            doc_ref = self.db.collection("knowledge_gaps").document(doc_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.warning(f"Knowledge gap analysis with ID {doc_id} not found")
                return None
                
            # Get document data
            data = doc.to_dict()
            
            # Check user access if user_id provided
            if user_id and data.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to access knowledge gap analysis {doc_id} belonging to user {data.get('user_id')}")
                return None
            
            # Convert to KnowledgeGapResponse
            context_list = []
            for ctx in data.get("context", []):
                context_list.append(RAGContext(**ctx))
            
            gaps_list = []
            for gap in data.get("gaps", []):
                gaps_list.append(KnowledgeGap(**gap))
            
            strengths_list = []
            for strength in data.get("strengths", []):
                strengths_list.append(Strength(**strength))
            
            # Create response object
            response = KnowledgeGapResponse(
                query_id=data.get("id", doc_id),
                query=data.get("query", ""),
                answer=data.get("answer", ""),
                gaps=gaps_list,
                strengths=strengths_list,
                context=context_list,
                citations=data.get("citations", []),
                timestamp=datetime.fromtimestamp(data.get("created_at", 0))
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error retrieving knowledge gap analysis from Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error retrieving knowledge gap analysis: {str(e)}")
    
    async def check_document_access(self, collection: str, doc_id: str, user_id: str) -> Tuple[bool, str]:
        """
        Check if a user has access to a specific document
        
        Args:
            collection: Firestore collection name
            doc_id: Document ID
            user_id: User ID requesting access
            
        Returns:
            Tuple of (has_access, message)
        """
        try:
            # Get document reference
            doc_ref = self.db.collection(collection).document(doc_id)
            doc = doc_ref.get()
            
            # Check if document exists
            if not doc.exists:
                return False, f"Document with ID {doc_id} not found in {collection}"
                
            # Get document data
            data = doc.to_dict()
            
            # Check user access
            if data.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to access document {doc_id} in {collection} belonging to user {data.get('user_id')}")
                return False, f"You do not have permission to access this {collection.rstrip('s')} document"
            
            return True, "User has access"
            
        except Exception as e:
            logger.error(f"Error checking document access: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error checking document access: {str(e)}")
    
    async def get_user_study_guides(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve a list of study guides for a specific user
        
        Args:
            user_id: User ID
            limit: Maximum number of records to return
            
        Returns:
            List of study guide summary objects
        """
        try:
            # Query Firestore for user's study guides
            query = self.db.collection("study_guides").where("user_id", "==", user_id).order_by("created_at", direction="DESCENDING").limit(limit)
            docs = query.stream()
            
            # Convert to list of summaries
            results = []
            for doc in docs:
                data = doc.to_dict()
                results.append({
                    "id": doc.id,
                    "topic": data.get("topic", ""),
                    "course_id": data.get("course_id"),
                    "module_id": data.get("module_id"),
                    "format": data.get("format", "outline"),
                    "detail_level": data.get("detail_level", "medium"),
                    "created_at": data.get("created_at", 0)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving user study guides from Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error retrieving user study guides: {str(e)}")
    
    async def get_user_practice_questions(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve a list of practice question sets for a specific user
        
        Args:
            user_id: User ID
            limit: Maximum number of records to return
            
        Returns:
            List of practice question set summary objects
        """
        try:
            # Query Firestore for user's practice question sets
            query = self.db.collection("practice_questions").where("user_id", "==", user_id).order_by("created_at", direction="DESCENDING").limit(limit)
            docs = query.stream()
            
            # Convert to list of summaries
            results = []
            for doc in docs:
                data = doc.to_dict()
                results.append({
                    "id": doc.id,
                    "topic": data.get("topic", ""),
                    "course_id": data.get("course_id"),
                    "module_id": data.get("module_id"),
                    "difficulty": data.get("difficulty", "medium"),
                    "question_count": data.get("question_count", 0),
                    "created_at": data.get("created_at", 0)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving user practice questions from Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error retrieving user practice questions: {str(e)}")
    
    async def get_user_knowledge_gaps(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve a list of knowledge gap analyses for a specific user
        
        Args:
            user_id: User ID
            limit: Maximum number of records to return
            
        Returns:
            List of knowledge gap analysis summary objects
        """
        try:
            # Query Firestore for user's knowledge gap analyses
            query = self.db.collection("knowledge_gaps").where("user_id", "==", user_id).order_by("created_at", direction="DESCENDING").limit(limit)
            docs = query.stream()
            
            # Convert to list of summaries
            results = []
            for doc in docs:
                data = doc.to_dict()
                results.append({
                    "id": doc.id,
                    "query": data.get("query", ""),
                    "topic": data.get("topic", ""),
                    "course_id": data.get("course_id"),
                    "module_id": data.get("module_id"),
                    "gap_count": len(data.get("gaps", [])),
                    "strength_count": len(data.get("strengths", [])),
                    "created_at": data.get("created_at", 0)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving user knowledge gaps from Firebase: {str(e)}", exc_info=True)
            raise FirebaseException(f"Error retrieving user knowledge gaps: {str(e)}")