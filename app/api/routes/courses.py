from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from app.core.security import get_current_user
from app.schemas.course import CourseResponse, CourseCreate, CourseUpdate
from app.services.course_service import CourseService

router = APIRouter(prefix="/courses", tags=["courses"])
course_service = CourseService()

@router.get("/", response_model=List[CourseResponse])
async def get_courses(
    current_user=Depends(get_current_user)
):
    """
    Get a list of all courses available to the user.
    """
    try:
        courses = await course_service.get_courses(user_id=current_user["id"])
        return courses
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve courses: {str(e)}"
        )

@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get details for a specific course.
    """
    try:
        course = await course_service.get_course(
            course_id=course_id,
            user_id=current_user["id"]
        )
        if not course:
            raise HTTPException(
                status_code=404,
                detail=f"Course with ID {course_id} not found"
            )
        return course
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve course: {str(e)}"
        )

@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    course_data: CourseCreate,
    current_user=Depends(get_current_user)
):
    """
    Create a new course (admin only).
    """
    # Check if user is admin
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create courses"
        )
    
    try:
        course = await course_service.create_course(course_data)
        return course
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create course: {str(e)}"
        )

@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: str,
    course_data: CourseUpdate,
    current_user=Depends(get_current_user)
):
    """
    Update a course (admin only).
    """
    # Check if user is admin
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update courses"
        )
    
    try:
        course = await course_service.update_course(
            course_id=course_id,
            course_data=course_data
        )
        if not course:
            raise HTTPException(
                status_code=404,
                detail=f"Course with ID {course_id} not found"
            )
        return course
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update course: {str(e)}"
        )

@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: str,
    current_user=Depends(get_current_user)
):
    """
    Delete a course (admin only).
    """
    # Check if user is admin
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete courses"
        )
    
    try:
        deleted = await course_service.delete_course(course_id=course_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Course with ID {course_id} not found"
            )
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete course: {str(e)}"
        )