# schemas/course.py
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class CourseBase(BaseModel):
    """Base schema for course"""
    code: str
    name: str  # Changed from title to match frontend
    description: str
    semester: str
    credits: int  # Added to match frontend
    instructor: str
    status: str = Field(..., description="Course status: 'active', 'inactive', or 'archived'")

class CourseCreate(CourseBase):
    """Schema for creating a new course"""
    pass

class CourseUpdate(BaseModel):
    """Schema for updating an existing course"""
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    semester: Optional[str] = None
    credits: Optional[int] = None
    instructor: Optional[str] = None
    status: Optional[str] = None

class CourseInDB(CourseBase):
    """Schema for course as stored in database"""
    id: str
    materials_count: int = 0
    created_at: str
    updated_at: str

class CourseResponse(CourseInDB):
    """Schema for course response in API endpoints"""
    class Config:
        from_attributes = True