# app/api/routes/courses.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.core.security import get_current_user_id
from app.dto.course_dto import (
    FrontendCourseCreateDTO,
    FrontendCourseUpdateDTO,
    FrontendCourseResponseDTO
)
from app.services.course_service import CourseService
from app.core.exceptions import (
    BaseAPIException
)

router = APIRouter(prefix="/courses", tags=["courses"])
course_service = CourseService()

@router.get("/", response_model=List[FrontendCourseResponseDTO])
async def get_courses(
    user_id: str = Depends(get_current_user_id)
):
    """
    Get a list of all courses available to the user.
    
    Requires authentication.
    """
    try:
        courses = await course_service.get_courses(user_id=user_id)
        return [FrontendCourseResponseDTO.from_backend(course) for course in courses]
    except BaseAPIException as e:
        # Use the status_code and detail directly from the exception
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve courses: {str(e)}"
        )

@router.get("/{course_id}", response_model=FrontendCourseResponseDTO)
async def get_course(
    course_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Get details for a specific course.
    
    Requires authentication and course access.
    """
    try:
        course = await course_service.get_course(course_id=course_id, user_id=user_id)
        return FrontendCourseResponseDTO.from_backend(course)
    except BaseAPIException as e:
        # Unified exception handling for all BaseAPIException types
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve course: {str(e)}"
        )

@router.post("/", response_model=FrontendCourseResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_course(
    course_data: FrontendCourseCreateDTO,
    user_id: str = Depends(get_current_user_id)
):
    """
    Create a new course.
    
    Requires authentication. Only admins and instructors can create courses.
    """
    try:
        # Convert frontend DTO to backend schema
        backend_course_data = course_data.to_course_create()
        
        # Create course using service
        created_course = await course_service.create_course(
            course_data=backend_course_data,
            user_id=user_id
        )
        
        # Convert backend response to frontend DTO
        return FrontendCourseResponseDTO.from_backend(created_course)
    except BaseAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create course: {str(e)}"
        )

@router.put("/{course_id}", response_model=FrontendCourseResponseDTO)
async def update_course(
    course_id: str,
    course_data: FrontendCourseUpdateDTO,
    user_id: str = Depends(get_current_user_id)
):
    """
    Update a course.
    
    Requires authentication. Only admins and the instructor who created the course can update it.
    """
    try:
        # Convert frontend DTO to backend schema
        backend_course_data = course_data.to_course_update()
        
        # Update course using service
        updated_course = await course_service.update_course(
            course_id=course_id,
            course_data=backend_course_data,
            user_id=user_id
        )
        
        # Convert backend response to frontend DTO
        return FrontendCourseResponseDTO.from_backend(updated_course)
    except BaseAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update course: {str(e)}"
        )

@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Delete a course.
    
    Requires authentication. Only admins can delete courses.
    """
    try:
        await course_service.delete_course(course_id=course_id, user_id=user_id)
        return None
    except BaseAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete course: {str(e)}"
        )

@router.post("/{course_id}/enroll", status_code=status.HTTP_200_OK)
async def enroll_in_course(
    course_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Enroll the current user in a course.
    
    Requires authentication.
    """
    try:
        await course_service.enroll_student(user_id=user_id, course_id=course_id)
        return {"detail": f"Successfully enrolled in course {course_id}"}
    except BaseAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enroll in course: {str(e)}"
        )

@router.post("/{course_id}/unenroll", status_code=status.HTTP_200_OK)
async def unenroll_from_course(
    course_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Unenroll the current user from a course.
    
    Requires authentication.
    """
    try:
        await course_service.unenroll_student(user_id=user_id, course_id=course_id)
        return {"detail": f"Successfully unenrolled from course {course_id}"}
    except BaseAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unenroll from course: {str(e)}"
        )