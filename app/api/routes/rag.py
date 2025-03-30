# app/api/routes/rag.py
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Path
from pydantic import BaseModel

from app.core.security import get_current_user_id
from app.services.rag_manager import RAGManager
from app.schemas.rag_query import RAGQuery, RAGResponse, RAGContext
from app.schemas.rag_query import StudyGuideRequest, PracticeQuestionsRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag")

# Initialize RAGManager with Firebase storage and conversation capabilities
rag_manager = RAGManager()

class QueryRequest(BaseModel):
    """Request model for RAG query"""
    query: str
    course_id: Optional[str] = None
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    prompt_type: str = "question_answering"
    additional_params: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None  # Optional conversation ID


class QueryResponse(BaseModel):
    """Response model for RAG query"""
    answer: str
    citations: List[int] = []
    context: List[RAGContext] = []
    meta: Optional[Dict[str, Any]] = None


class ConversationQueryResponse(BaseModel):
    """Response model for RAG query with conversation"""
    answer: str
    citations: List[int] = []
    context: List[RAGContext] = []
    meta: Optional[Dict[str, Any]] = None
    conversation: Dict[str, Any]


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
        if request.conversation_id:
            # Process in conversation if conversation_id is provided
            response, conversation = await rag_manager.process_query_in_conversation(
                query=query,
                conversation_id=request.conversation_id
            )
            
            # Add conversation ID to metadata
            if response.meta is None:
                response.meta = {}
            response.meta["conversation_id"] = conversation.get("id")
            
            # Return as QueryResponse (not including the full conversation)
            return QueryResponse(
                answer=response.answer,
                citations=response.citations,
                context=response.context,
                meta=response.meta
            )
        else:
            # Regular processing without conversation
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


@router.post("/query/conversation", response_model=ConversationQueryResponse)
async def rag_query_with_conversation(
    request: QueryRequest = Body(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Process a RAG query, save it in a conversation, and return both the response and conversation.
    Creates a new conversation if conversation_id is not provided.
    """
    try:
        logger.info(f"RAG query with conversation received: {request.query[:100]}...")
        
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
        
        # Process in conversation
        response, conversation = await rag_manager.process_query_in_conversation(
            query=query,
            conversation_id=request.conversation_id
        )
        
        # Convert to API response format
        return ConversationQueryResponse(
            answer=response.answer,
            citations=response.citations,
            context=response.context,
            meta=response.meta,
            conversation=conversation
        )
        
    except Exception as e:
        logger.error(f"Error processing RAG query with conversation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query with conversation: {str(e)}"
        )


@router.post("/study-guide", response_model=QueryResponse)
async def generate_study_guide(
    request: StudyGuideRequest = Body(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Generate a study guide for a specific topic and save it to Firebase.
    """
    try:
        logger.info(f"=============Study guide request received for topic: {request.topic}")  
        
        # Add user_id to the request
        request.user_id = user_id

        # Store the topic from the request to ensure it's saved in metadata
        topic = request.topic
        
        # Generate the study guide ONLY ONCE
        response = await rag_manager.generate_study_guide(request)
        
        # Ensure meta is initialized
        if response.meta is None:
            response.meta = {}
        
        # Make sure topic is explicitly added to metadata
        response.meta["topic"] = topic
        
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

@router.post("/study-guide/conversation", response_model=ConversationQueryResponse)
async def generate_study_guide_with_conversation(
    request: StudyGuideRequest = Body(...),
    conversation_id: Optional[str] = Query(None, description="Optional conversation ID"),
    user_id: str = Depends(get_current_user_id)
):
    """
    Generate a study guide and save it in a conversation.
    Creates a new conversation if conversation_id is not provided.
    """
    try:
        logger.info(f"Study guide with conversation request received for topic: {request.topic}")
        
        # Add user_id to the request
        request.user_id = user_id
        
        # Use RAGManager to generate study guide in conversation
        response, conversation = await rag_manager.generate_study_guide_in_conversation(
            request=request,
            conversation_id=conversation_id
        )
        
        # Convert to API response format
        return ConversationQueryResponse(
            answer=response.answer,
            citations=response.citations,
            context=response.context,
            meta=response.meta,
            conversation=conversation
        )
        
    except Exception as e:
        logger.error(f"Error generating study guide with conversation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating study guide with conversation: {str(e)}"
        )


@router.post("/practice-questions", response_model=QueryResponse)
async def generate_practice_questions(
    request: PracticeQuestionsRequest = Body(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Generate practice questions for a specific topic and save them to Firebase.
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


@router.post("/practice-questions/conversation", response_model=ConversationQueryResponse)
async def generate_practice_questions_with_conversation(
    request: PracticeQuestionsRequest = Body(...),
    conversation_id: Optional[str] = Query(None, description="Optional conversation ID"),
    user_id: str = Depends(get_current_user_id)
):
    """
    Generate practice questions and save them in a conversation.
    Creates a new conversation if conversation_id is not provided.
    """
    try:
        logger.info(f"Practice questions with conversation request received for topic: {request.topic}")
        
        # Validate inputs
        if request.question_count < 1 or request.question_count > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question count must be between 1 and 10"
            )
        
        # Add user_id to the request
        request.user_id = user_id
        
        # Use RAGManager to generate practice questions in conversation
        response, conversation = await rag_manager.generate_practice_questions_in_conversation(
            request=request,
            conversation_id=conversation_id
        )
        
        # Convert to API response format
        return ConversationQueryResponse(
            answer=response.answer,
            citations=response.citations,
            context=response.context,
            meta=response.meta,
            conversation=conversation
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating practice questions with conversation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating practice questions with conversation: {str(e)}"
        )


@router.post("/knowledge-gap", response_model=QueryResponse)
async def analyze_knowledge_gap(
    request: QueryRequest = Body(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Analyze knowledge gaps based on a student query and save to Firebase.
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
                "gaps": [gap.dict() for gap in response.gaps],
                "strengths": [strength.dict() for strength in response.strengths],
                "document_id": response.meta.get("document_id") if response.meta else None
            }
        )
        
    except Exception as e:
        logger.error(f"Error analyzing knowledge gaps: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing knowledge gaps: {str(e)}"
        )


@router.post("/knowledge-gap/conversation", response_model=ConversationQueryResponse)
async def analyze_knowledge_gap_with_conversation(
    request: QueryRequest = Body(...),
    conversation_id: Optional[str] = Query(None, description="Optional conversation ID"),
    user_id: str = Depends(get_current_user_id)
):
    """
    Analyze knowledge gaps and save the analysis in a conversation.
    Creates a new conversation if conversation_id is not provided.
    """
    try:
        logger.info(f"Knowledge gap analysis with conversation request received for query: {request.query[:100]}...")
        
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
        
        # Use RAGManager to analyze knowledge gaps in conversation
        response, conversation = await rag_manager.analyze_knowledge_gaps_in_conversation(
            query=query,
            conversation_id=conversation_id
        )
        
        # Convert to API response format
        return ConversationQueryResponse(
            answer=response.answer,
            citations=response.citations,
            context=response.context,
            meta={
                "gaps": [gap.dict() for gap in response.gaps],
                "strengths": [strength.dict() for strength in response.strengths],
                "document_id": response.meta.get("document_id") if response.meta else None
            },
            conversation=conversation
        )
        
    except Exception as e:
        logger.error(f"Error analyzing knowledge gaps with conversation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing knowledge gaps with conversation: {str(e)}"
        )