# app/dto/course_dto.py
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.schemas.course import CourseCreate, CourseResponse, CourseUpdate

class FrontendCourseCreateDTO(BaseModel):
    """DTO for mapping frontend course creation data to backend schema"""
    code: str
    name: str
    description: str
    semester: str
    credits: int
    instructor: str
    status: str = "active"

    def to_course_create(self) -> CourseCreate:
        """Convert frontend DTO to backend CourseCreate schema"""
        return CourseCreate(
            code=self.code,
            name=self.name,
            description=self.description,
            semester=self.semester,
            credits=self.credits,
            instructor=self.instructor,
            status=self.status
        )

class FrontendCourseUpdateDTO(BaseModel):
    """DTO for mapping frontend course update data to backend schema"""
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    semester: Optional[str] = None
    credits: Optional[int] = None
    instructor: Optional[str] = None
    status: Optional[str] = None

    def to_course_update(self) -> CourseUpdate:
        """Convert frontend DTO to backend CourseUpdate schema"""
        return CourseUpdate(
            code=self.code,
            name=self.name,
            description=self.description,
            semester=self.semester,
            credits=self.credits,
            instructor=self.instructor,
            status=self.status
        )

class FrontendCourseResponseDTO(BaseModel):
    """DTO for mapping backend course response to frontend format"""
    id: str
    code: str
    name: str
    description: str
    semester: str
    credits: int
    status: str
    instructor: str
    materialsCount: int
    createdAt: str
    updatedAt: str
    
    @classmethod
    def from_backend(cls, course: CourseResponse) -> 'FrontendCourseResponseDTO':
        """Convert backend CourseResponse to frontend format"""
        return cls(
            id=course.id,
            code=course.code,
            name=course.name,
            description=course.description,
            semester=course.semester,
            credits=course.credits,
            status=course.status,
            instructor=course.instructor,
            materialsCount=course.materials_count,
            createdAt=course.created_at,
            updatedAt=course.updated_at
        )