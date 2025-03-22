from datetime import datetime
import json
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, logger, status, File, UploadFile
from typing import List, Optional
from app.core.security import check_admin_or_instructor_role, get_current_user
from app.dto.material_dto import FrontendMaterialProcessingStatusDTO, FrontendMaterialUploadResponseDTO
from app.schemas.material import MaterialCreate, MaterialResponse, MaterialUpdate
from app.schemas.material_upload import MaterialProcessingStatus, MaterialUploadResponse
from app.services.file_processing_service import FileProcessingService
from app.services.material_service import MaterialService

router = APIRouter(prefix="/materials", tags=["materials"])
material_service = MaterialService()
file_processing_service = FileProcessingService()

@router.post("/upload", response_model=FrontendMaterialUploadResponseDTO, status_code=status.HTTP_201_CREATED)
async def upload_material(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    course_id: str = Form(...),
    module_id: Optional[str] = Form(None),
    topic_id: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    material_type: Optional[str] = Form("lecture"),
    current_user=Depends(get_current_user),
    _=Depends(check_admin_or_instructor_role)
):
    """
    Upload a material file for processing and RAG indexing.
    
    Args:
        file: File to upload
        course_id: Course ID to associate with the material
        module_id: Optional module ID
        topic_id: Optional topic ID
        title: Optional title (uses filename if not provided)
        description: Optional description
        material_type: Type of material (lecture, lab, reading, etc.)
        
    Returns:
        Material upload response with processing status
    """
    try:
        # Process the file (initial steps only)
        material_data = await file_processing_service.process_file_initial(
            file=file,
            course_id=course_id,
            user_id=current_user.id,
            module_id=module_id,
            topic_id=topic_id,
            title=title,
            description=description,
            file_type=material_type
        )

        # Add the complete processing to background tasks
        background_tasks.add_task(
            file_processing_service.process_file_background,
            material_id=material_data["id"]
        )
        
        # Convert to response model
        upload_response = MaterialUploadResponse(
            id=material_data["id"],
            title=material_data["title"],
            description=material_data["description"],
            type=material_data["type"],
            course_id=material_data["course_id"],
            module_id=material_data.get("module_id"),
            topic_id=material_data.get("topic_id"),
            file_url=material_data["file_url"],
            file_size=material_data["file_size"],
            file_type=material_data["file_type"],
            status=material_data["status"],
            uploaded_at=material_data["uploaded_at"]
        )
        
        # Convert to frontend DTO
        return FrontendMaterialUploadResponseDTO.from_backend(upload_response)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload material: {str(e)}"
        )

@router.post("/batch-upload", response_model=List[FrontendMaterialUploadResponseDTO], status_code=status.HTTP_201_CREATED)
async def batch_upload_materials(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    course_id: str = Form(...),
    module_id: Optional[str] = Form(None),
    topic_id: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),  # JSON string with title/description for each file
    material_type: Optional[str] = Form("lecture"),
    current_user=Depends(get_current_user),
    _=Depends(check_admin_or_instructor_role)
):
    """
    Upload multiple material files in a batch.
    
    Args:
        files: Files to upload
        course_id: Course ID to associate with the materials
        module_id: Optional module ID
        topic_id: Optional topic ID
        metadata: Optional JSON string with metadata for each file
        material_type: Type of material (lecture, lab, reading, etc.)
        
    Returns:
        List of material upload responses
    """
    try:
        # Parse metadata if provided
        file_metadata = {}
        if metadata:
            try:
                file_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid metadata JSON format"
                )
        
        # Process files
        responses = []
        for file in files:
            # Get metadata for this file if available
            file_meta = file_metadata.get(file.filename, {})
            
            # Process the file (initial steps only)
            material_data = await file_processing_service.process_file_initial(
                file=file,
                course_id=course_id,
                user_id=current_user.id,
                module_id=module_id,
                topic_id=topic_id,
                title=file_meta.get("title"),
                description=file_meta.get("description"),
                file_type=material_type
            )
            
            # Add the complete processing to background tasks
            background_tasks.add_task(
                file_processing_service.process_file_background,
                material_id=material_data["id"]
            )
            
            # Convert to response model
            upload_response = MaterialUploadResponse(
                id=material_data["id"],
                title=material_data["title"],
                description=material_data["description"],
                type=material_data["type"],
                course_id=material_data["course_id"],
                module_id=material_data.get("module_id"),
                topic_id=material_data.get("topic_id"),
                file_url=material_data["file_url"],
                file_size=material_data["file_size"],
                file_type=material_data["file_type"],
                status=material_data["status"],
                uploaded_at=material_data["uploaded_at"]
            )
            
            # Convert to frontend DTO and add to responses
            responses.append(FrontendMaterialUploadResponseDTO.from_backend(upload_response))
        
        return responses
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload materials: {str(e)}"
        )

@router.get("/processing/{material_id}", response_model=FrontendMaterialProcessingStatusDTO)
async def get_material_processing_status(
    material_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get the processing status of a material.
    
    Args:
        material_id: ID of the material to check
        
    Returns:
        Processing status details
    """
    try:
        # Get processing status
        status_data = await file_processing_service.get_processing_status(material_id)
        
        # Validate the data before constructing the Pydantic model
        if not isinstance(status_data.get("started_at"), str):
            status_data["started_at"] = datetime.utcnow().isoformat()
        
        # Convert to response model
        processing_status = MaterialProcessingStatus(
            material_id=status_data["material_id"],
            status=status_data["status"],
            progress=status_data["progress"],
            error_message=status_data.get("error_message"),
            started_at=status_data["started_at"],
            completed_at=status_data.get("completed_at")
        )
        
        # Convert to frontend DTO
        return FrontendMaterialProcessingStatusDTO.from_backend(processing_status)
        
    except Exception as e:
        import traceback
        error_msg = f"Failed to get processing status: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get processing status: {str(e)}"
        )

@router.get("/", response_model=List[MaterialResponse])
async def get_materials(
    course_id: Optional[str] = None,
    module_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    material_type: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    """
    Get a list of materials with optional filtering.
    """
    try:
        materials = await material_service.get_materials(
            user_id=current_user["id"],
            course_id=course_id,
            module_id=module_id,
            topic_id=topic_id,
            material_type=material_type
        )
        return materials
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve materials: {str(e)}"
        )

@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get a specific material by ID.
    """
    try:
        material = await material_service.get_material(
            material_id=material_id,
            user_id=current_user["id"]
        )
        if not material:
            raise HTTPException(
                status_code=404,
                detail=f"Material with ID {material_id} not found"
            )
        return material
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve material: {str(e)}"
        )

@router.post("/", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    material_data: MaterialCreate,
    current_user=Depends(get_current_user)
):
    """
    Create a new material (admin only).
    """
    # Check if user is admin
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create materials"
        )
    
    try:
        material = await material_service.create_material(material_data)
        return material
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create material: {str(e)}"
        )

@router.put("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: str,
    material_data: MaterialUpdate,
    current_user=Depends(get_current_user)
):
    """
    Update a material (admin only).
    """
    # Check if user is admin
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update materials"
        )
    
    try:
        material = await material_service.update_material(
            material_id=material_id,
            material_data=material_data
        )
        if not material:
            raise HTTPException(
                status_code=404,
                detail=f"Material with ID {material_id} not found"
            )
        return material
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update material: {str(e)}"
        )

@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: str,
    current_user=Depends(get_current_user)
):
    """
    Delete a material (admin only).
    """
    # Check if user is admin
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete materials"
        )
    
    try:
        deleted = await material_service.delete_material(material_id=material_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Material with ID {material_id} not found"
            )
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete material: {str(e)}"
        )