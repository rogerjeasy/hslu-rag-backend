import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from pydantic import BaseModel

from app.core.security import get_current_user_id
from app.services.rag_manager import RAGManager
from app.schemas.rag_query import RAGQuery, RAGResponse, RAGContext
from app.schemas.rag_query import StudyGuideRequest, PracticeQuestionsRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])

# Initialize RAGManager instead of RAGService
rag_manager = RAGManager()

class QueryRequest(BaseModel):
    """Request model for RAG query"""
    query: str
    course_id: Optional[str] = None
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    prompt_type: str = "question_answering"
    additional_params: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    """Response model for RAG query"""
    answer: str
    citations: List[int] = []
    context: List[RAGContext] = []
    meta: Optional[Dict[str, Any]] = None


@router.post("/query", response_model=QueryResponse)
async def rag_query(
    request: QueryRequest = Body(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Process a RAG query and return a contextualized response.
    """
    try:
        logger.info(f"RAG query received: {request.query[:100]}...")
        
        # Create RAGQuery object
        query = RAGQuery(
            query=request.query,
            course_id=request.course_id,
            module_id=request.module_id,
            topic_id=request.topic_id,
            user_id=user_id,
            prompt_type=request.prompt_type,
            additional_params=request.additional_params
        )
        
        # Process through RAGManager
        response = await rag_manager.process_query(query)
        
        # Convert to API response format
        return QueryResponse(
            answer=response.answer,
            citations=response.citations,
            context=response.context,
            meta=response.meta
        )
        
    except Exception as e:
        logger.error(f"Error processing RAG query: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )


@router.post("/study-guide", response_model=QueryResponse)
async def generate_study_guide(
    request: StudyGuideRequest = Body(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Generate a study guide for a specific topic.
    """
    try:
        logger.info(f"Study guide request received for topic: {request.topic}")
        
        # Add user_id to the request
        request.user_id = user_id
        
        # Use RAGManager to generate study guide
        response = await rag_manager.generate_study_guide(request)
        
        # Convert to API response format
        return QueryResponse(
            answer=response.answer,
            citations=response.citations,
            context=response.context,
            meta=response.meta
        )
        
    except Exception as e:
        logger.error(f"Error generating study guide: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating study guide: {str(e)}"
        )


@router.post("/practice-questions", response_model=QueryResponse)
async def generate_practice_questions(
    request: PracticeQuestionsRequest = Body(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Generate practice questions for a specific topic.
    """
    try:
        logger.info(f"Practice questions request received for topic: {request.topic}")
        
        # Validate inputs
        if request.question_count < 1 or request.question_count > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question count must be between 1 and 10"
            )
        
        # Add user_id to the request
        request.user_id = user_id
        
        # Use RAGManager to generate practice questions
        response = await rag_manager.generate_practice_questions(request)
        
        # Convert to API response format
        return QueryResponse(
            answer=response.answer,
            citations=response.citations,
            context=response.context,
            meta=response.meta
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating practice questions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating practice questions: {str(e)}"
        )


@router.post("/knowledge-gap", response_model=QueryResponse)
async def analyze_knowledge_gap(
    request: QueryRequest = Body(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Analyze knowledge gaps based on a student query.
    """
    try:
        logger.info(f"Knowledge gap analysis request received for query: {request.query[:100]}...")
        
        # Create RAGQuery object
        query = RAGQuery(
            query=request.query,
            course_id=request.course_id,
            module_id=request.module_id,
            topic_id=request.topic_id,
            user_id=user_id,
            prompt_type="knowledge_gap",
            additional_params=request.additional_params
        )
        
        # Use RAGManager to analyze knowledge gaps
        response = await rag_manager.analyze_knowledge_gaps(query)
        
        # Convert to API response format
        return QueryResponse(
            answer=response.answer,
            citations=response.citations,
            context=response.context,
            meta={
                "gaps": response.gaps,
                "strengths": response.strengths
            }
        )
        
    except Exception as e:
        logger.error(f"Error analyzing knowledge gaps: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing knowledge gaps: {str(e)}"
        )