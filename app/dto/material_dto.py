# app/dto/material_dto.py

from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.material_upload import MaterialUploadResponse, MaterialProcessingStatus

class FrontendMaterialUploadResponseDTO(BaseModel):
    """DTO for converting backend MaterialUploadResponse to frontend format"""
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
    chunkCount: Optional[int] = None
    vectorIds: Optional[List[str]] = None
    
    @classmethod
    def from_backend(cls, backend: MaterialUploadResponse) -> 'FrontendMaterialUploadResponseDTO':
        """Convert from backend model to frontend DTO"""
        return cls(
            id=backend.id,
            title=backend.title,
            description=backend.description,
            type=backend.type,
            courseId=backend.course_id,
            moduleId=backend.module_id,
            topicId=backend.topic_id,
            fileUrl=backend.file_url,
            fileSize=backend.file_size,
            fileType=backend.file_type,
            status=backend.status,
            uploadedAt=backend.uploaded_at,
            chunkCount=backend.chunk_count if hasattr(backend, 'chunk_count') else None,
            vectorIds=backend.vector_ids if hasattr(backend, 'vector_ids') else None
        )

class FrontendMaterialProcessingStatusDTO(BaseModel):
    """DTO for converting backend MaterialProcessingStatus to frontend format"""
    materialId: str
    status: str
    progress: float
    stage: str = "pending"  # Added this field to match frontend type
    stageProgress: float = 0.0  # Added this field to match frontend type
    totalChunks: Optional[int] = None
    processedChunks: Optional[int] = None
    errorMessage: Optional[str] = None
    startedAt: str
    completedAt: Optional[str] = None
    
    @classmethod
    def from_backend(cls, backend: MaterialProcessingStatus) -> 'FrontendMaterialProcessingStatusDTO':
        """Convert from backend model to frontend DTO"""
        
        # Infer stage from progress
        stage = "pending"
        if backend.status == "processing":
            if backend.progress < 0.2:
                stage = "upload_complete"
            elif backend.progress < 0.4:
                stage = "text_extraction"
            elif backend.progress < 0.6:
                stage = "chunking"
            elif backend.progress < 0.8:
                stage = "embedding"
            else:
                stage = "indexing"
        elif backend.status == "completed":
            stage = "completed"
        elif backend.status == "failed":
            stage = "failed"
        
        return cls(
            materialId=backend.material_id,
            status=backend.status,
            progress=backend.progress,
            stage=stage,
            stageProgress=min(1.0, (backend.progress % 0.2) * 5),  # Calculate stage progress
            errorMessage=backend.error_message,
            startedAt=backend.started_at,
            completedAt=backend.completed_at
        )