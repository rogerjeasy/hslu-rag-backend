from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ModuleBase(BaseModel):
    """Base schema for course module"""
    id: str
    title: str
    description: Optional[str] = None
    order: int = 0

class TopicBase(BaseModel):
    """Base schema for module topic"""
    id: str
    title: str
    description: Optional[str] = None
    order: int = 0

class ModuleWithTopics(ModuleBase):
    """Schema for module with topics"""
    topics: List[TopicBase] = []

class CourseBase(BaseModel):
    """Base schema for course"""
    title: str
    code: str
    description: Optional[str] = None
    semester: Optional[str] = None
    year: Optional[int] = None
    instructor: Optional[str] = None

class CourseCreate(CourseBase):
    """Schema for creating a new course"""
    modules: Optional[List[ModuleWithTopics]] = []

class CourseUpdate(BaseModel):
    """Schema for updating an existing course"""
    title: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    semester: Optional[str] = None
    year: Optional[int] = None
    instructor: Optional[str] = None
    modules: Optional[List[ModuleWithTopics]] = None

class MaterialBase(BaseModel):
    """Base schema for course material"""
    id: str
    title: str
    description: Optional[str] = None
    type: str  # lecture, lab, exercise, reading
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    source_url: Optional[str] = None
    uploaded_at: str

class CourseDetail(CourseBase):
    """Schema for detailed course information"""
    id: str
    modules: List[ModuleWithTopics] = []
    materials: List[MaterialBase] = []
    created_at: str
    updated_at: Optional[str] = None
    student_count: Optional[int] = None
   
    class Config:
        from_attributes = True
        orm_mode = True

class CourseSummary(BaseModel):
    """Schema for course summary information"""
    id: str
    title: str
    code: str
    description: Optional[str] = None
    semester: Optional[str] = None
    year: Optional[int] = None
    instructor: Optional[str] = None
    module_count: int
    material_count: int
   
    class Config:
        from_attributes = True
        orm_mode = True

class CourseEnrollmentRequest(BaseModel):
    """Schema for course enrollment request"""
    course_id: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "course_id": "machine-learning-101"
            }
        }
        schema_extra = {
            "example": {
                "course_id": "machine-learning-101"
            }
        }

class EnrolledCourse(BaseModel):
    """Schema for a course a user is enrolled in"""
    course_id: str
    enrolled_at: str
    progress: Optional[float] = 0.0  # Percentage of course completed
    last_activity: Optional[str] = None

# Add CourseResponse as an alias for CourseDetail to fix import error
class CourseResponse(CourseDetail):
    """Schema for course response in API endpoints"""
    pass