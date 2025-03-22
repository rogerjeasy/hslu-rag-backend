# app/dto/material_dto.py
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from app.schemas.material import MaterialResponse
from app.schemas.material_upload import MaterialUploadResponse, MaterialProcessingStatus

class FrontendMaterialUploadResponseDTO(BaseModel):
    """DTO for mapping backend material upload response to frontend format"""
    id: str
    title: str
    description: Optional[str] = None
    type: str
    courseId: str
    moduleId: Optional[str] = None
    topicId: Optional[str] = None
    fileUrl: str
    fileSize: int
    fileType: str
    status: str
    uploadedAt: str
    
    @classmethod
    def from_backend(cls, response: MaterialUploadResponse) -> 'FrontendMaterialUploadResponseDTO':
        """Convert backend MaterialUploadResponse to frontend format"""
        return cls(
            id=response.id,
            title=response.title,
            description=response.description,
            type=response.type,
            courseId=response.course_id,
            moduleId=response.module_id,
            topicId=response.topic_id,
            fileUrl=response.file_url,
            fileSize=response.file_size,
            fileType=response.file_type,
            status=response.status,
            uploadedAt=response.uploaded_at
        )

class FrontendMaterialProcessingStatusDTO(BaseModel):
    """DTO for mapping backend material processing status to frontend format"""
    materialId: str
    status: str
    progress: float
    errorMessage: Optional[str] = None
    startedAt: str
    completedAt: Optional[str] = None
    
    @classmethod
    def from_backend(cls, status: MaterialProcessingStatus) -> 'FrontendMaterialProcessingStatusDTO':
        """Convert backend MaterialProcessingStatus to frontend format"""
        return cls(
            materialId=status.material_id,
            status=status.status,
            progress=status.progress,
            errorMessage=status.error_message,
            startedAt=status.started_at,
            completedAt=status.completed_at
        )