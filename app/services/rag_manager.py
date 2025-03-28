# app/services/rag_manager.py
import logging
import asyncio
import uuid
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime

from app.core.config import settings
from app.rag_new.rag_service import RAGService
from app.services.material_service import MaterialService
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
            meta = rag_response.get("meta", None)
            
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
    
    async def generate_study_guide(self, request: StudyGuideRequest) -> RAGResponse:
        """
        Generate a study guide for a specific topic
        
        Args:
            request: Study guide request with topic and parameters
            
        Returns:
            RAG response with study guide
        """
        try:
            logger.info(f"Generating study guide for topic: {request.topic}")
            
            # Create RAG query
            query = RAGQuery(
                query=request.topic,
                course_id=request.course_id,
                module_id=request.module_id,
                user_id=request.user_id,
                prompt_type="study_guide",
                additional_params={
                    "detail_level": request.detail_level,
                    "format": request.format
                }
            )
            
            # Process through regular query processing
            return await self.process_query(query)
            
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
    
    async def generate_practice_questions(self, request: PracticeQuestionsRequest) -> RAGResponse:
        """
        Generate practice questions for a specific topic
        
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
                    "question_types": request.question_types
                }
            )
            
            # Process through regular query processing
            response = await self.process_query(query)
            
            # Ensure questions are included in meta
            if response.meta is None:
                response.meta = {}
            
            # Extract questions from raw response if not already in meta
            if "questions" not in response.meta and "response" in response.meta:
                raw_response = response.meta.get("response", {})
                if "questions" in raw_response:
                    response.meta["questions"] = raw_response["questions"]
            
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
    
    async def analyze_knowledge_gaps(self, query: RAGQuery) -> KnowledgeGapResponse:
        """
        Analyze knowledge gaps based on a query
        
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
            return KnowledgeGapResponse(
                query_id=response.query_id,
                query=response.query,
                answer=response.answer,
                gaps=gaps,
                strengths=strengths,
                context=response.context,
                citations=response.citations,
                timestamp=response.timestamp
            )
            
        except Exception as e:
            logger.error(f"Error analyzing knowledge gaps: {str(e)}", exc_info=True)
            # Return error response
            return KnowledgeGapResponse(
                query_id=str(uuid.uuid4()),
                query=query.query,
                answer=f"Error analyzing knowledge gaps: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def reindex_material(self, material_id: str) -> Tuple[bool, Optional[str]]:
        """
        Reindex a material's embeddings (delete and recreate)
        
        Args:
            material_id: ID of the material
            
        Returns:
            Tuple of (success status, error message if any)
        """
        return await self.rag_service.reindex_material(material_id)