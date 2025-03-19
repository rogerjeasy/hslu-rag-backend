from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from app.core.security import get_current_user
from app.schemas.practice import PracticeRequest, PracticeResponse, PracticeAnswer, PracticeResult
from app.services.practice_service import PracticeService

router = APIRouter(prefix="/practice", tags=["practice"])
practice_service = PracticeService()

@router.get("/", response_model=List[PracticeResponse])
async def get_practice_sets(
    course_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    """
    Get all practice question sets created by the user, with optional filtering.
    """
    try:
        practice_sets = await practice_service.get_practice_sets(
            user_id=current_user["id"],
            course_id=course_id,
            topic_id=topic_id
        )
        return practice_sets
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve practice sets: {str(e)}"
        )

@router.get("/{practice_id}", response_model=PracticeResponse)
async def get_practice_set(
    practice_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get a specific practice question set by ID.
    """
    try:
        practice_set = await practice_service.get_practice_set(
            practice_id=practice_id,
            user_id=current_user["id"]
        )
        if not practice_set:
            raise HTTPException(
                status_code=404,
                detail=f"Practice set with ID {practice_id} not found"
            )
        return practice_set
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve practice set: {str(e)}"
        )

@router.post("/", response_model=PracticeResponse, status_code=status.HTTP_201_CREATED)
async def create_practice_set(
    practice_request: PracticeRequest,
    current_user=Depends(get_current_user)
):
    """
    Create a new AI-generated practice question set for a course or topic.
    """
    try:
        practice_set = await practice_service.create_practice_set(
            user_id=current_user["id"],
            practice_request=practice_request
        )
        return practice_set
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create practice set: {str(e)}"
        )

@router.post("/{practice_id}/submit", response_model=PracticeResult)
async def submit_practice_answers(
    practice_id: str,
    answers: List[PracticeAnswer],
    current_user=Depends(get_current_user)
):
    """
    Submit answers to a practice question set and get results.
    """
    try:
        result = await practice_service.evaluate_practice_answers(
            practice_id=practice_id,
            user_id=current_user["id"],
            answers=answers
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to evaluate practice answers: {str(e)}"
        )

@router.delete("/{practice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_practice_set(
    practice_id: str,
    current_user=Depends(get_current_user)
):
    """
    Delete a practice question set.
    """
    try:
        deleted = await practice_service.delete_practice_set(
            practice_id=practice_id,
            user_id=current_user["id"]
        )
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Practice set with ID {practice_id} not found"
            )
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete practice set: {str(e)}"
        )