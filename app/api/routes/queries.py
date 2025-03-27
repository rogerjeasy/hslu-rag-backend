# app/api/routes/queries.py
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from app.core.security import get_current_user_id
from app.core.prompt_templates import get_system_prompt, get_user_prompt, PromptType
from app.schemas.auth import UserResponse
from app.rag_new.rag_service import RAGService
from app.services.llm_service import LLMService
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queries", tags=["queries"])

# Initialize services
rag_service = RAGService()
llm_service = LLMService()

# Request and response models
class QueryRequest(BaseModel):
    """Model for a query request"""
    query: str
    course_id: Optional[str] = None
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    prompt_type: PromptType = PromptType.QUESTION_ANSWERING
    max_chunks: int = 5
    additional_params: Optional[Dict[str, Any]] = None
    
class ChunkInfo(BaseModel):
    """Model for a context chunk"""
    chunk_id: str
    material_id: str
    source_url: str
    title: str
    score: float
    file_type: str
    
class QueryResponse(BaseModel):
    """Model for a query response"""
    answer: str
    citations: List[int]
    context_chunks: List[ChunkInfo]
    metadata: Optional[Dict[str, Any]] = None

@router.post("", response_model=QueryResponse)
async def create_query(
    query_request: QueryRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Process a query and return a response with context.
    """
    try:
        # Retrieve relevant context chunks
        context_chunks = await rag_service.retrieve_relevant_context(
            query=query_request.query,
            course_id=query_request.course_id,
            module_id=query_request.module_id,
            topic_id=query_request.topic_id,
            max_chunks=query_request.max_chunks
        )
        
        if not context_chunks:
            # No context found, return a message about insufficient information
            return QueryResponse(
                answer="I couldn't find any relevant information to answer your question. Please try rephrasing or asking about a different topic.",
                citations=[],
                context_chunks=[],
                metadata={"status": "no_relevant_context"}
            )
        
        # Generate system prompt
        system_prompt = get_system_prompt(
            prompt_type=query_request.prompt_type,
            additional_params=query_request.additional_params
        )
        
        # Generate user prompt with context
        user_prompt = get_user_prompt(
            prompt_type=query_request.prompt_type,
            query=query_request.query,
            context_chunks=context_chunks,
            additional_params=query_request.additional_params
        )
        
        # Call LLM to generate response
        response = await llm_service.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        
        try:
            # Parse JSON response
            parsed_response = response.get("response", {})
            
            # Extract answer and citations
            answer = parsed_response.get("answer", "")
            citations = parsed_response.get("citations", [])
            metadata = parsed_response.get("meta", {})
            
            # Convert context_chunks to ChunkInfo objects
            chunk_infos = []
            for chunk in context_chunks:
                chunk_infos.append(ChunkInfo(
                    chunk_id=chunk.get("chunk_id", ""),
                    material_id=chunk.get("material_id", ""),
                    source_url=chunk.get("source_url", ""),
                    title=chunk.get("title", ""),
                    score=chunk.get("score", 0.0),
                    file_type=chunk.get("file_type", "")
                ))
            
            # Return response
            return QueryResponse(
                answer=answer,
                citations=citations,
                context_chunks=chunk_infos,
                metadata=metadata
            )
            
        except Exception as e:
            # If parsing fails, return the raw response
            logger.error(f"Error parsing LLM response: {str(e)}")
            return QueryResponse(
                answer=str(response),
                citations=[],
                context_chunks=[ChunkInfo(
                    chunk_id="",
                    material_id="",
                    source_url="",
                    title="Error parsing response",
                    score=0.0,
                    file_type=""
                )],
                metadata={"error": "parsing_error"}
            )
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )


# Define study guide generation endpoint
class StudyGuideRequest(BaseModel):
    """Model for a study guide request"""
    topic: str
    course_id: str
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    detail_level: str = "medium"  # basic, medium, comprehensive
    format: str = "outline"  # outline, notes, flashcards, mind_map, summary
    max_chunks: int = 10

@router.post("/study-guide", response_model=QueryResponse)
async def generate_study_guide(
    request: StudyGuideRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Generate a study guide for a specific topic.
    """
    try:
        # Set additional parameters
        additional_params = {
            "detail_level": request.detail_level,
            "format": request.format
        }
        
        # Create a query request
        query_request = QueryRequest(
            query=f"Create a {request.detail_level} study guide on {request.topic}",
            course_id=request.course_id,
            module_id=request.module_id,
            topic_id=request.topic_id,
            prompt_type=PromptType.STUDY_GUIDE,
            max_chunks=request.max_chunks,
            additional_params=additional_params
        )
        
        # Use the query endpoint
        return await create_query(query_request, current_user)
        
    except Exception as e:
        logger.error(f"Error generating study guide: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating study guide: {str(e)}"
        )


# Define practice questions generation endpoint
class PracticeQuestionsRequest(BaseModel):
    """Model for a practice questions request"""
    topic: str
    course_id: str
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    difficulty: str = "medium"  # basic, medium, advanced
    question_count: int = 5
    question_types: List[str] = ["multiple_choice", "short_answer"]
    max_chunks: int = 10

@router.post("/practice-questions", response_model=QueryResponse)
async def generate_practice_questions(
    request: PracticeQuestionsRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Generate practice questions for a specific topic.
    """
    try:
        # Set additional parameters
        additional_params = {
            "difficulty": request.difficulty,
            "question_count": request.question_count,
            "question_types": request.question_types
        }
        
        # Create a query request
        query_request = QueryRequest(
            query=f"Generate {request.question_count} {request.difficulty} practice questions on {request.topic}",
            course_id=request.course_id,
            module_id=request.module_id,
            topic_id=request.topic_id,
            prompt_type=PromptType.PRACTICE_QUESTIONS,
            max_chunks=request.max_chunks,
            additional_params=additional_params
        )
        
        # Use the query endpoint
        return await create_query(query_request, current_user)
        
    except Exception as e:
        logger.error(f"Error generating practice questions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating practice questions: {str(e)}"
        )


# Define knowledge gap analysis endpoint
class KnowledgeGapRequest(BaseModel):
    """Model for a knowledge gap analysis request"""
    query: str
    course_id: str
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    past_interactions_count: int = 10
    max_chunks: int = 10

@router.post("/knowledge-gap", response_model=QueryResponse)
async def analyze_knowledge_gap(
    request: KnowledgeGapRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Analyze knowledge gaps based on a query.
    """
    try:
        # Set additional parameters
        additional_params = {
            "past_interactions_count": request.past_interactions_count
        }
        
        # Create a query request
        query_request = QueryRequest(
            query=request.query,
            course_id=request.course_id,
            module_id=request.module_id,
            topic_id=request.topic_id,
            prompt_type=PromptType.KNOWLEDGE_GAP,
            max_chunks=request.max_chunks,
            additional_params=additional_params
        )
        
        # Use the query endpoint
        return await create_query(query_request, current_user)
        
    except Exception as e:
        logger.error(f"Error analyzing knowledge gap: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing knowledge gap: {str(e)}"
        )