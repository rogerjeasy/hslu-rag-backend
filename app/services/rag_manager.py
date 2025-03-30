# app/services/rag_manager.py
import logging
import asyncio
import uuid
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime

from app.core.config import settings
from app.rag_new.rag_service import RAGService
from app.services.material_service import MaterialService
from app.services.firebase_storage_service import FirebaseStorageService
from app.services.conversation_service import ConversationService
from app.schemas.rag_query import (
    RAGQuery, RAGResponse, RAGContext, 
    StudyGuideRequest, PracticeQuestionsRequest,
    Question, KnowledgeGap, Strength, KnowledgeGapResponse
)
import app.rag_new.prompt_templates as prompts

logger = logging.getLogger(__name__)

class RAGManager:
    """
    High-level service that orchestrates RAG operations for the application
    """
    
    def __init__(self):
        """Initialize the RAG manager with dependencies"""
        self.rag_service = RAGService()
        self.material_service = MaterialService()
        self.firebase_storage = FirebaseStorageService()
        self.conversation_service = ConversationService()
    
    async def process_query(self, query: RAGQuery) -> RAGResponse:
        """
        Process a RAG query and return a response
        
        Args:
            query: The RAG query schema
            
        Returns:
            RAG response schema
        """
        try:
            logger.info(f"Processing RAG query: {query.query[:100]}...")
            
            # Generate unique query ID
            query_id = str(uuid.uuid4())
            
            # Retrieve relevant context
            context_chunks = await self.rag_service.retrieve_relevant_context(
                query=query.query,
                course_id=query.course_id,
                module_id=query.module_id,
                topic_id=query.topic_id,
                max_chunks=settings.RAG_DEFAULT_TOP_K,
                min_relevance_score=settings.RAG_MIN_RELEVANCE_SCORE
            )
            
            if not context_chunks:
                logger.warning(f"No relevant context found for query: {query.query[:100]}...")
                return RAGResponse(
                    query_id=query_id,
                    query=query.query,
                    answer="I couldn't find relevant information to answer your question. Please try rephrasing or providing more context.",
                    prompt_type=query.prompt_type,
                    timestamp=datetime.utcnow()
                )
            
            # Generate response
            response = await self.rag_service.generate_rag_response(
                query=query.query,
                context_chunks=context_chunks,
                prompt_type=query.prompt_type,
                additional_params=query.additional_params
            )
            
            # Process the response
            rag_response = response.get("response", {})
            answer = rag_response.get("answer", "")
            citations = rag_response.get("citations", [])
            meta = rag_response.get("meta", {}) or {}

            # If this is a practice questions request, extract the questions
            if query.prompt_type == "practice_questions" and "questions" in rag_response:
                meta["questions"] = rag_response["questions"]
                logger.info(f"Extracted {len(meta['questions'])} questions from response")
                
            # Format context for the response
            formatted_context = []
            for i, chunk in enumerate(context_chunks):
                if i+1 in citations:
                    formatted_context.append(
                        RAGContext(
                            id=chunk.get("chunk_id", f"chunk_{i}"),
                            title=chunk.get("title", f"Source {i+1}"),
                            content=chunk.get("chunk_content", ""),
                            citation_number=i+1,
                            material_id=chunk.get("material_id", ""),
                            source_url=chunk.get("source_url", ""),
                            source_page=chunk.get("source_page", None),
                            score=chunk.get("score", 0.0)
                        )
                    )
            
            # Build and return RAG response
            return RAGResponse(
                query_id=query_id,
                query=query.query,
                answer=answer,
                context=formatted_context,
                citations=citations,
                prompt_type=query.prompt_type,
                timestamp=datetime.utcnow(),
                meta=meta
            )
            
        except Exception as e:
            logger.error(f"Error processing RAG query: {str(e)}", exc_info=True)
            # Return error response
            return RAGResponse(
                query_id=str(uuid.uuid4()),
                query=query.query,
                answer=f"Error processing your query: {str(e)}",
                prompt_type=query.prompt_type,
                timestamp=datetime.utcnow()
            )
    
    async def process_query_in_conversation(
        self, 
        query: RAGQuery, 
        conversation_id: Optional[str] = None
    ) -> Tuple[RAGResponse, Dict[str, Any]]:
        """
        Process a RAG query and add it to a conversation
        
        Args:
            query: The RAG query schema
            conversation_id: Optional conversation ID (will create a new one if not provided)
            
        Returns:
            Tuple of (RAG response, conversation data)
        """
        try:
            # Process the query first
            response = await self.process_query(query)
            
            # Create a new conversation if not provided
            if not conversation_id:
                # Create a title from the query if it's short enough, otherwise truncate
                title = query.query
                if len(title) > 50:
                    title = title[:47] + "..."
                
                conversation_id = await self.conversation_service.create_conversation(
                    user_id=query.user_id,
                    title=title,
                    course_id=query.course_id,
                    module_id=query.module_id,
                    topic_id=query.topic_id
                )
            
            # Add user query as a message
            await self.conversation_service.add_message(
                conversation_id=conversation_id,
                user_id=query.user_id,
                role="user",
                content=query.query
            )
            
            # Add assistant response as a message
            await self.conversation_service.add_rag_response(
                conversation_id=conversation_id,
                user_id=query.user_id,
                rag_response=response
            )
            
            # Get updated conversation
            conversation = await self.conversation_service.get_conversation(conversation_id)
            
            return response, conversation
            
        except Exception as e:
            logger.error(f"Error processing query in conversation: {str(e)}", exc_info=True)
            # Return error response
            error_response = RAGResponse(
                query_id=str(uuid.uuid4()),
                query=query.query,
                answer=f"Error processing your query: {str(e)}",
                prompt_type=query.prompt_type,
                timestamp=datetime.utcnow()
            )
            return error_response, {"error": str(e)}
    
    async def generate_study_guide(self, request: StudyGuideRequest) -> RAGResponse:
        """
        Generate a study guide for a specific topic and save it to Firebase
        
        Args:
            request: Study guide request with topic and parameters
            
        Returns:
            RAG response with study guide
        """
        try:
            logger.info(f"Generating study guide for topic: {request.topic}")
            
            # Store course_id for Firebase storage but don't use it for retrieval
            firebase_course_id = request.course_id
            
            # Store the topic from the request to ensure it's preserved
            topic = request.topic
            
            # Check if we have metadata with course info
            metadata_course_id = None
            if hasattr(request, 'meta') and request.meta:
                metadata_course_id = request.meta.get('course_id')
                
            # Create RAG query without course_id to improve retrieval quality
            # This is based on observation that retrieval works better without course filtering
            query = RAGQuery(
                query=request.topic,
                # Intentionally omit course_id here
                course_id=None,  
                module_id=request.module_id,
                user_id=request.user_id,
                prompt_type="study_guide",
                additional_params={
                    "detail_level": request.detail_level,
                    "format": request.format,
                    "topic": request.topic,
                    "module_id": request.module_id
                }
            )
            
            # Process through regular query processing
            response = await self.process_query(query)
            
            # Save to Firebase with the original course_id for proper association
            if request.user_id and response:
                try:
                    # Ensure response has metadata
                    if response.meta is None:
                        response.meta = {}
                        
                    # Add course_id back for storage purposes
                    response.meta["course_id"] = firebase_course_id or metadata_course_id
                    
                    # Ensure topic is included in metadata
                    response.meta["topic"] = topic
                    
                    # Ensure format and detail_level are in metadata
                    response.meta["format"] = request.format
                    response.meta["detail_level"] = request.detail_level
                    
                    doc_id = await self.firebase_storage.save_study_guide(response, request.user_id)
                    
                    # Add the document ID to the response metadata
                    response.meta["document_id"] = doc_id
                    
                    logger.info(f"Study guide saved to Firebase with ID: {doc_id} with metadata: {response.meta}")
                except Exception as e:
                    logger.error(f"Failed to save study guide to Firebase: {str(e)}", exc_info=True)
                    # Continue anyway, as we still have the response
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating study guide: {str(e)}", exc_info=True)
            # Return error response
            return RAGResponse(
                query_id=str(uuid.uuid4()),
                query=request.topic,
                answer=f"Error generating study guide: {str(e)}",
                prompt_type="study_guide",
                timestamp=datetime.utcnow()
            )
    
    async def generate_study_guide_in_conversation(
        self, 
        request: StudyGuideRequest,
        conversation_id: Optional[str] = None
    ) -> Tuple[RAGResponse, Dict[str, Any]]:
        """
        Generate a study guide and add it to a conversation
        
        Args:
            request: Study guide request
            conversation_id: Optional conversation ID
            
        Returns:
            Tuple of (RAG response, conversation data)
        """
        try:
            # Generate the study guide
            response = await self.generate_study_guide(request)
            
            # Create a new conversation if not provided
            if not conversation_id:
                conversation_id = await self.conversation_service.create_conversation(
                    user_id=request.user_id,
                    title=f"Study Guide: {request.topic}",
                    course_id=request.course_id,
                    module_id=request.module_id
                )
            
            # Add user request as a message
            await self.conversation_service.add_message(
                conversation_id=conversation_id,
                user_id=request.user_id,
                role="user",
                content=f"Generate a {request.detail_level} study guide on {request.topic} in {request.format} format"
            )
            
            # Add assistant response as a message
            await self.conversation_service.add_rag_response(
                conversation_id=conversation_id,
                user_id=request.user_id,
                rag_response=response
            )
            
            # Get updated conversation
            conversation = await self.conversation_service.get_conversation(conversation_id)
            
            return response, conversation
            
        except Exception as e:
            logger.error(f"Error generating study guide in conversation: {str(e)}", exc_info=True)
            # Return error response
            error_response = RAGResponse(
                query_id=str(uuid.uuid4()),
                query=request.topic,
                answer=f"Error generating study guide: {str(e)}",
                prompt_type="study_guide",
                timestamp=datetime.utcnow()
            )
            return error_response, {"error": str(e)}
    
    async def generate_practice_questions(self, request: PracticeQuestionsRequest) -> RAGResponse:
        """
        Generate practice questions for a specific topic and save them to Firebase
        
        Args:
            request: Practice questions request with topic and parameters
            
        Returns:
            RAG response with practice questions
        """
        try:
            logger.info(f"Generating practice questions for topic: {request.topic}")
            
            # Create RAG query
            query = RAGQuery(
                query=request.topic,
                course_id=request.course_id,
                module_id=request.module_id,
                user_id=request.user_id,
                prompt_type="practice_questions",
                additional_params={
                    "question_count": request.question_count,
                    "difficulty": request.difficulty,
                    "question_types": request.question_types,
                    "topic": request.topic,
                    "course_id": request.course_id,
                    "module_id": request.module_id
                }
            )
            
            # Process through regular query processing
            response = await self.process_query(query)
            
            if response.meta is None:
                response.meta = {}

            response.meta["topic"] = request.topic
            
            # Extract questions from the response
            if "questions" not in response.meta and response.meta.get("response", {}):
                raw_response = response.meta.get("response", {})
                if isinstance(raw_response, dict) and "questions" in raw_response:
                    response.meta["questions"] = raw_response["questions"]
                    logger.info(f"Extracted questions from response: {len(response.meta['questions'])}")
            
            # Save to Firebase
            if request.user_id and response:
                try:
                    doc_id = await self.firebase_storage.save_practice_questions(response, request.user_id)
                    
                    response.meta["document_id"] = doc_id
                    
                    logger.info(f"Practice questions saved to Firebase with ID: {doc_id}")
                except Exception as e:
                    logger.error(f"Failed to save practice questions to Firebase: {str(e)}", exc_info=True)
                    # Continue anyway, as we still have the response
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating practice questions: {str(e)}", exc_info=True)
            # Return error response
            return RAGResponse(
                query_id=str(uuid.uuid4()),
                query=request.topic,
                answer=f"Error generating practice questions: {str(e)}",
                prompt_type="practice_questions",
                timestamp=datetime.utcnow()
            )
    
    async def generate_practice_questions_in_conversation(
        self, 
        request: PracticeQuestionsRequest,
        conversation_id: Optional[str] = None
    ) -> Tuple[RAGResponse, Dict[str, Any]]:
        """
        Generate practice questions and add them to a conversation
        
        Args:
            request: Practice questions request
            conversation_id: Optional conversation ID
            
        Returns:
            Tuple of (RAG response, conversation data)
        """
        try:
            # Generate the practice questions
            response = await self.generate_practice_questions(request)
            
            # Create a new conversation if not provided
            if not conversation_id:
                conversation_id = await self.conversation_service.create_conversation(
                    user_id=request.user_id,
                    title=f"Practice Questions: {request.topic}",
                    course_id=request.course_id,
                    module_id=request.module_id
                )
            
            # Add user request as a message
            await self.conversation_service.add_message(
                conversation_id=conversation_id,
                user_id=request.user_id,
                role="user",
                content=f"Generate {request.question_count} {request.difficulty} practice questions on {request.topic}"
            )
            
            # Add assistant response as a message
            await self.conversation_service.add_rag_response(
                conversation_id=conversation_id,
                user_id=request.user_id,
                rag_response=response
            )
            
            # Get updated conversation
            conversation = await self.conversation_service.get_conversation(conversation_id)
            
            return response, conversation
            
        except Exception as e:
            logger.error(f"Error generating practice questions in conversation: {str(e)}", exc_info=True)
            # Return error response
            error_response = RAGResponse(
                query_id=str(uuid.uuid4()),
                query=request.topic,
                answer=f"Error generating practice questions: {str(e)}",
                prompt_type="practice_questions",
                timestamp=datetime.utcnow()
            )
            return error_response, {"error": str(e)}
    
    async def analyze_knowledge_gaps(self, query: RAGQuery) -> KnowledgeGapResponse:
        """
        Analyze knowledge gaps based on a query and save to Firebase
        
        Args:
            query: RAG query with the student's question
            
        Returns:
            Knowledge gap analysis response
        """
        try:
            logger.info(f"Analyzing knowledge gaps for query: {query.query[:100]}...")
            
            # Ensure prompt type is set to knowledge_gap
            query.prompt_type = "knowledge_gap"
            
            # Process through regular query processing
            response = await self.process_query(query)
            
            # Extract knowledge gaps and strengths from meta
            gaps = []
            strengths = []
            
            if response.meta:
                # Process gaps
                raw_gaps = response.meta.get("gaps", [])
                for gap in raw_gaps:
                    gaps.append(
                        KnowledgeGap(
                            id=gap.get("id", str(uuid.uuid4())),
                            concept=gap.get("concept", "Unknown concept"),
                            description=gap.get("description", ""),
                            severity=gap.get("severity", "medium"),
                            recommended_resources=gap.get("recommended_resources", []),
                            citations=gap.get("citations", [])
                        )
                    )
                
                # Process strengths
                raw_strengths = response.meta.get("strengths", [])
                for strength in raw_strengths:
                    strengths.append(
                        Strength(
                            id=strength.get("id", str(uuid.uuid4())),
                            concept=strength.get("concept", "Unknown concept"),
                            description=strength.get("description", "")
                        )
                    )
            
            # Build knowledge gap response
            knowledge_gap_response = KnowledgeGapResponse(
                query_id=response.query_id,
                query=response.query,
                answer=response.answer,
                gaps=gaps,
                strengths=strengths,
                context=response.context,
                citations=response.citations,
                timestamp=response.timestamp
            )
            
            # Save to Firebase
            if query.user_id and knowledge_gap_response:
                try:
                    doc_id = await self.firebase_storage.save_knowledge_gap(knowledge_gap_response, query.user_id)
                    
                    logger.info(f"Knowledge gap analysis saved to Firebase with ID: {doc_id}")
                except Exception as e:
                    logger.error(f"Failed to save knowledge gap analysis to Firebase: {str(e)}", exc_info=True)
                    # Continue anyway, as we still have the response
            
            return knowledge_gap_response
            
        except Exception as e:
            logger.error(f"Error analyzing knowledge gaps: {str(e)}", exc_info=True)
            # Return error response
            return KnowledgeGapResponse(
                query_id=str(uuid.uuid4()),
                query=query.query,
                answer=f"Error analyzing knowledge gaps: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def analyze_knowledge_gaps_in_conversation(
        self, 
        query: RAGQuery,
        conversation_id: Optional[str] = None
    ) -> Tuple[KnowledgeGapResponse, Dict[str, Any]]:
        """
        Analyze knowledge gaps and add the analysis to a conversation
        
        Args:
            query: RAG query
            conversation_id: Optional conversation ID
            
        Returns:
            Tuple of (KnowledgeGapResponse, conversation data)
        """
        try:
            # Analyze knowledge gaps
            response = await self.analyze_knowledge_gaps(query)
            
            # Create a new conversation if not provided
            if not conversation_id:
                conversation_id = await self.conversation_service.create_conversation(
                    user_id=query.user_id,
                    title=f"Knowledge Gap Analysis: {query.query[:30]}...",
                    course_id=query.course_id,
                    module_id=query.module_id,
                    topic_id=query.topic_id
                )
            
            # Add user query as a message
            await self.conversation_service.add_message(
                conversation_id=conversation_id,
                user_id=query.user_id,
                role="user",
                content=query.query
            )
            
            # Create a RAGResponse from the KnowledgeGapResponse for adding to conversation
            rag_response = RAGResponse(
                query_id=response.query_id,
                query=response.query,
                answer=response.answer,
                context=response.context,
                citations=response.citations,
                prompt_type="knowledge_gap",
                timestamp=response.timestamp,
                meta={
                    "gaps": [gap.dict() for gap in response.gaps],
                    "strengths": [strength.dict() for strength in response.strengths]
                }
            )
            
            # Add assistant response as a message
            await self.conversation_service.add_rag_response(
                conversation_id=conversation_id,
                user_id=query.user_id,
                rag_response=rag_response
            )
            
            # Get updated conversation
            conversation = await self.conversation_service.get_conversation(conversation_id)
            
            return response, conversation
            
        except Exception as e:
            logger.error(f"Error analyzing knowledge gaps in conversation: {str(e)}", exc_info=True)
            # Return error response
            error_response = KnowledgeGapResponse(
                query_id=str(uuid.uuid4()),
                query=query.query,
                answer=f"Error analyzing knowledge gaps: {str(e)}",
                timestamp=datetime.utcnow()
            )
            return error_response, {"error": str(e)}
    
    async def reindex_material(self, material_id: str) -> Tuple[bool, Optional[str]]:
        """
        Reindex a material's embeddings (delete and recreate)
        
        Args:
            material_id: ID of the material
            
        Returns:
            Tuple of (success status, error message if any)
        """
        return await self.rag_service.reindex_material(material_id)