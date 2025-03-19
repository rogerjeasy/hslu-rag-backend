from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class MaterialBase(BaseModel):
    """Base schema for course material"""
    title: str
    description: Optional[str] = None
    type: str  # lecture, lab, exercise, reading
    course_id: str
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    source_url: Optional[str] = None

class MaterialCreate(MaterialBase):
    """Schema for creating a new material"""
    content_text: Optional[str] = None
    file_path: Optional[str] = None

class MaterialUpdate(BaseModel):
    """Schema for updating an existing material"""
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    source_url: Optional[str] = None
    content_text: Optional[str] = None
    file_path: Optional[str] = None

class MaterialResponse(MaterialBase):
    """Schema for material response in API endpoints"""
    id: str
    uploaded_at: str
    updated_at: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    
    class Config:
        from_attributes = True