# app/api/routes/content.py
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from pydantic import BaseModel

from app.core.security import get_current_user_id
from app.services.firebase_retrieval_service import FirebaseRetrievalService
from app.services.firebase_storage_service import FirebaseStorageService
from app.schemas.rag_query import RAGResponse, KnowledgeGapResponse
from app.dto.content_dto import (
    FrontendStudyGuideSummaryDTO, 
    FrontendRAGResponseDTO,
    FrontendPracticeQuestionsSummaryDTO,
    FrontendKnowledgeGapSummaryDTO,
    FrontendKnowledgeGapResponseDTO,
    FrontendDeleteResponseDTO,
    FrontendDeleteAllResponseDTO
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content")

# Initialize Firebase Services
firebase_retrieval_service = FirebaseRetrievalService()
firebase_storage_service = FirebaseStorageService()

class ContentSummary(BaseModel):
    """Model for content summary listings"""
    id: str
    topic: str
    course_id: Optional[str] = None
    module_id: Optional[str] = None
    created_at: int


class StudyGuideSummary(ContentSummary):
    """Model for study guide summary"""
    format: str
    detail_level: str


class PracticeQuestionsSummary(ContentSummary):
    """Model for practice questions summary"""
    difficulty: str
    question_count: int


class KnowledgeGapSummary(ContentSummary):
    """Model for knowledge gap summary"""
    query: str
    gap_count: int
    strength_count: int


class DeleteResponse(BaseModel):
    """Model for delete operation response"""
    success: bool
    message: str


class DeleteAllResponse(BaseModel):
    """Model for delete all operation response"""
    success: bool
    deleted_counts: Dict[str, int]
    message: str


# Study Guide Endpoints
@router.get("/study-guides", response_model=List[FrontendStudyGuideSummaryDTO])
async def list_user_study_guides(
    limit: int = Query(10, ge=1, le=50),
    user_id: str = Depends(get_current_user_id)
):
    """
    List study guides created by the current user
    """
    try:
        study_guides = await firebase_retrieval_service.get_user_study_guides(user_id, limit)
        return [FrontendStudyGuideSummaryDTO.from_backend(guide) for guide in study_guides]
    except Exception as e:
        logger.error(f"Error listing user study guides: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing study guides: {str(e)}"
        )


@router.get("/study-guides/{guide_id}", response_model=FrontendRAGResponseDTO)
async def get_study_guide(
    guide_id: str = Path(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Retrieve a specific study guide by ID
    """
    try:
        study_guide = await firebase_retrieval_service.get_study_guide(guide_id, user_id)
        if not study_guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Study guide with ID {guide_id} not found or not accessible"
            )
        return FrontendRAGResponseDTO.from_backend(study_guide)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving study guide: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving study guide: {str(e)}"
        )


@router.delete("/study-guides/{guide_id}", response_model=FrontendDeleteResponseDTO)
async def delete_study_guide(
    guide_id: str = Path(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Delete a specific study guide by ID
    """
    try:
        success, message = await firebase_storage_service.delete_study_guide(guide_id, user_id)
        
        if not success:
            if "not found" in message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=message
                )
            elif "permission" in message:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=message
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=message
                )
        
        response = DeleteResponse(success=True, message=message)
        return FrontendDeleteResponseDTO.from_backend(response.dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting study guide: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting study guide: {str(e)}"
        )


# Practice Questions Endpoints
@router.get("/practice-questions", response_model=List[FrontendPracticeQuestionsSummaryDTO])
async def list_user_practice_questions(
    limit: int = Query(10, ge=1, le=50),
    user_id: str = Depends(get_current_user_id)
):
    """
    List practice question sets created by the current user
    """
    try:
        practice_questions = await firebase_retrieval_service.get_user_practice_questions(user_id, limit)
        return [FrontendPracticeQuestionsSummaryDTO.from_backend(questions) for questions in practice_questions]
    except Exception as e:
        logger.error(f"Error listing user practice questions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing practice questions: {str(e)}"
        )


@router.get("/practice-questions/{questions_id}", response_model=FrontendRAGResponseDTO)
async def get_practice_questions(
    questions_id: str = Path(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Retrieve a specific practice question set by ID
    """
    try:
        practice_questions = await firebase_retrieval_service.get_practice_questions(questions_id, user_id)
        if not practice_questions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Practice questions with ID {questions_id} not found or not accessible"
            )
        return FrontendRAGResponseDTO.from_backend(practice_questions)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving practice questions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving practice questions: {str(e)}"
        )


@router.delete("/practice-questions/{questions_id}", response_model=FrontendDeleteResponseDTO)
async def delete_practice_questions(
    questions_id: str = Path(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Delete a specific practice question set by ID
    """
    try:
        success, message = await firebase_storage_service.delete_practice_questions(questions_id, user_id)
        
        if not success:
            if "not found" in message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=message
                )
            elif "permission" in message:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=message
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=message
                )
        
        response = DeleteResponse(success=True, message=message)
        return FrontendDeleteResponseDTO.from_backend(response.dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting practice questions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting practice questions: {str(e)}"
        )


# Knowledge Gap Endpoints
@router.get("/knowledge-gaps", response_model=List[FrontendKnowledgeGapSummaryDTO])
async def list_user_knowledge_gaps(
    limit: int = Query(10, ge=1, le=50),
    user_id: str = Depends(get_current_user_id)
):
    """
    List knowledge gap analyses created by the current user
    """
    try:
        knowledge_gaps = await firebase_retrieval_service.get_user_knowledge_gaps(user_id, limit)
        return [FrontendKnowledgeGapSummaryDTO.from_backend(gap) for gap in knowledge_gaps]
    except Exception as e:
        logger.error(f"Error listing user knowledge gaps: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing knowledge gaps: {str(e)}"
        )


@router.get("/knowledge-gaps/{gap_id}", response_model=FrontendKnowledgeGapResponseDTO)
async def get_knowledge_gap(
    gap_id: str = Path(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Retrieve a specific knowledge gap analysis by ID
    """
    try:
        knowledge_gap = await firebase_retrieval_service.get_knowledge_gap(gap_id, user_id)
        if not knowledge_gap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge gap analysis with ID {gap_id} not found or not accessible"
            )
        return FrontendKnowledgeGapResponseDTO.from_backend(knowledge_gap)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving knowledge gap analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving knowledge gap analysis: {str(e)}"
        )


@router.delete("/knowledge-gaps/{gap_id}", response_model=FrontendDeleteResponseDTO)
async def delete_knowledge_gap(
    gap_id: str = Path(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Delete a specific knowledge gap analysis by ID
    """
    try:
        success, message = await firebase_storage_service.delete_knowledge_gap(gap_id, user_id)
        
        if not success:
            if "not found" in message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=message
                )
            elif "permission" in message:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=message
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=message
                )
        
        response = DeleteResponse(success=True, message=message)
        return FrontendDeleteResponseDTO.from_backend(response.dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting knowledge gap analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting knowledge gap analysis: {str(e)}"
        )


# Delete All User Content Endpoint
@router.delete("/user-content", response_model=FrontendDeleteAllResponseDTO)
async def delete_all_user_content(
    user_id: str = Depends(get_current_user_id)
):
    """
    Delete all content created by the current user
    """
    try:
        results = await firebase_storage_service.delete_all_user_content(user_id)
        
        total_count = results["total"]
        success = total_count > 0
        
        message = f"Successfully deleted {total_count} items" if success else "No content found to delete"
        
        response = DeleteAllResponse(
            success=success,
            deleted_counts=results,
            message=message
        )
        
        return FrontendDeleteAllResponseDTO.from_backend(response.dict())
    except Exception as e:
        logger.error(f"Error deleting all user content: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting all user content: {str(e)}"
        )