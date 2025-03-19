from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from app.core.security import get_current_user
from app.schemas.study_guide import StudyGuideRequest, StudyGuideResponse
from app.services.study_guide_service import StudyGuideService

router = APIRouter(prefix="/study-guides", tags=["study guides"])
study_guide_service = StudyGuideService()

@router.get("/", response_model=List[StudyGuideResponse])
async def get_study_guides(
    course_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    """
    Get all study guides created by the user, with optional filtering.
    """
    try:
        guides = await study_guide_service.get_study_guides(
            user_id=current_user["id"],
            course_id=course_id,
            topic_id=topic_id
        )
        return guides
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve study guides: {str(e)}"
        )

@router.get("/{guide_id}", response_model=StudyGuideResponse)
async def get_study_guide(
    guide_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get a specific study guide by ID.
    """
    try:
        guide = await study_guide_service.get_study_guide(
            guide_id=guide_id,
            user_id=current_user["id"]
        )
        if not guide:
            raise HTTPException(
                status_code=404,
                detail=f"Study guide with ID {guide_id} not found"
            )
        return guide
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve study guide: {str(e)}"
        )

@router.post("/", response_model=StudyGuideResponse, status_code=status.HTTP_201_CREATED)
async def create_study_guide(
    guide_request: StudyGuideRequest,
    current_user=Depends(get_current_user)
):
    """
    Create a new AI-generated study guide for a course or topic.
    """
    try:
        guide = await study_guide_service.create_study_guide(
            user_id=current_user["id"],
            guide_request=guide_request
        )
        return guide
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create study guide: {str(e)}"
        )

@router.delete("/{guide_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_study_guide(
    guide_id: str,
    current_user=Depends(get_current_user)
):
    """
    Delete a study guide.
    """
    try:
        deleted = await study_guide_service.delete_study_guide(
            guide_id=guide_id,
            user_id=current_user["id"]
        )
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Study guide with ID {guide_id} not found"
            )
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete study guide: {str(e)}"
        )