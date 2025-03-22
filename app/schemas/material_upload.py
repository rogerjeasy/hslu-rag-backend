# app/schemas/material_upload.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime

class MaterialUploadRequest(BaseModel):
    """Schema for material upload request"""
    course_id: str
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    title: Optional[str] = None  # If not provided, will use the filename
    description: Optional[str] = None
    type: str = "lecture"  # Default to lecture type

class MaterialUploadResponse(BaseModel):
    """Schema for material upload response"""
    id: str
    title: str
    description: Optional[str] = None
    type: str
    course_id: str
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    file_url: str
    file_size: int
    file_type: str
    status: str = "processing"  # processing, completed, failed
    uploaded_at: str
    chunk_count: Optional[int] = None
    vector_ids: Optional[List[str]] = None
    
    class Config:
        from_attributes = True

# class MaterialProcessingStatus(BaseModel):
#     """Schema for material processing status"""
#     material_id: str
#     status: str  # processing, completed, failed
#     progress: float  # 0.0 to 1.0
#     error_message: Optional[str] = None
#     started_at: str  # Make sure this is always provided
#     completed_at: Optional[str] = None

class MaterialProcessingStatus(BaseModel):
    """Schema for material processing status"""
    material_id: str
    status: str  # processing, completed, failed
    progress: float = 0.0  # 0.0 to 1.0, default to 0
    error_message: Optional[str] = None
    started_at: str  # Required ISO datetime string
    completed_at: Optional[str] = None  # Optional ISO datetime string
    
    class Config:
        from_attributes = True
        
    @validator('progress')
    def validate_progress(cls, value):
        # Ensure progress is a float between 0 and 1
        try:
            float_value = float(value)
            return max(0.0, min(1.0, float_value))
        except (TypeError, ValueError):
            return 0.0
            
    @validator('started_at')
    def validate_started_at(cls, value):
        # Ensure started_at is a string
        if value is None:
            return datetime.utcnow().isoformat()
        return value