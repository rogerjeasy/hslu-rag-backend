# app/api/routes/materials.py
import os
import logging
import tempfile
import time
import uuid
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.security import check_admin_or_instructor_role, get_current_user_id
from app.schemas.material_upload import MaterialUploadRequest, MaterialUploadResponse, MaterialProcessingStatus
from app.schemas.material import MaterialResponse, MaterialUpdate
from app.dto.material_dto import FrontendMaterialUploadResponseDTO, FrontendMaterialProcessingStatusDTO
from app.services.cloudinary_service import CloudinaryService
from app.services.material_service import MaterialService
from app.rag_new.rag_service import RAGService
from app.services.rag_manager import RAGManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/materials", tags=["materials"])

# Initialize services
cloudinary_service = CloudinaryService()
material_service = MaterialService()
rag_service = RAGService()
rag_manager = RAGManager()

@router.post("/upload", response_model=FrontendMaterialUploadResponseDTO)
async def upload_material(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    type: str = Form("lecture"),
    course_id: str = Form(...),
    module_id: Optional[str] = Form(None),
    topic_id: Optional[str] = Form(None),
    user_id: str = Depends(check_admin_or_instructor_role)
):
    """
    Upload a new course material.
    
    This endpoint is restricted to admin and instructor roles.
    """
    try:
        # Validate file type
        file_extension = os.path.splitext(file.filename)[1].lower().lstrip('.')
        if file_extension not in settings.ALLOWED_FILE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not supported. Allowed types: {', '.join(settings.ALLOWED_FILE_TYPES)}"
            )
        
        # Validate file size (limit to configured max size)
        file_size = 0
        chunk_size = 1024 * 1024  # 1MB
        
        # Create a temporary file to save the uploaded content
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Read and write the file in chunks
            while chunk := await file.read(chunk_size):
                file_size += len(chunk)
                if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB."
                    )
                temp_file.write(chunk)
            
            temp_path = temp_file.name
        
        try:
            # Use filename as title if not provided
            if not title:
                title = os.path.splitext(file.filename)[0]
            
            # Generate unique ID
            material_id = str(uuid.uuid4())
            
            # Upload to Cloudinary
            folder = f"course_materials/{course_id}"
            public_id = f"{folder}/{material_id}"
            
            upload_result = await cloudinary_service.upload_file(
                file_path=temp_path,
                folder=folder,
                public_id=material_id
            )
            
            # Create material upload response
            timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            material_response = MaterialUploadResponse(
                id=material_id,
                title=title,
                description=description,
                type=type,
                course_id=course_id,
                module_id=module_id,
                topic_id=topic_id,
                file_url=upload_result["secure_url"],
                file_size=file_size,
                file_type=file_extension,
                status="processing",
                uploaded_at=timestamp,
                uploaded_by=user_id
            )
            
            # Store material metadata in database
            await material_service.create_material(material_response)
            
            # Start processing in background (don't await to return quickly)
            asyncio.create_task(process_material_background(material_response))
            
            # Return response
            return FrontendMaterialUploadResponseDTO.from_backend(material_response)
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading material: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading material: {str(e)}"
        )

async def process_material_background(material: MaterialUploadResponse):
    """Background task to process uploaded material"""
    try:
        logger.info(f"Starting background processing of material {material.id}")
        
        # Set the initial processing status
        processing_status = MaterialProcessingStatus(
            material_id=material.id,
            status="processing",
            progress=0.1,
            started_at=material.uploaded_at
        )
        
        # Update processing status
        await material_service.update_processing_status(processing_status)
        
        # Process the material with RAG service
        processing_status = await rag_service.process_material(material)
        
        # Update material status
        material.status = processing_status.status
        
        if processing_status.status == "completed":
            # If successful, update with chunk count and vector IDs
            material.chunk_count = len(material.vector_ids) if hasattr(material, 'vector_ids') and material.vector_ids else 0
            
            logger.info(f"Successfully processed material {material.id} with {material.chunk_count} chunks")
            
            # Update material in database
            await material_service.update_material(material.id, material)
        else:
            # If failed, update status
            logger.error(f"Failed to process material {material.id}: {processing_status.error_message}")
            await material_service.update_material_status(material.id, "failed", processing_status.error_message)
            
        # Store final processing status
        await material_service.update_processing_status(processing_status)
            
    except Exception as e:
        logger.error(f"Error in background processing of material {material.id}: {str(e)}", exc_info=True)
        # Update material status to failed
        await material_service.update_material_status(material.id, "failed", str(e))
        
        # Update processing status
        error_status = MaterialProcessingStatus(
            material_id=material.id,
            status="failed",
            progress=0.0,
            started_at=material.uploaded_at,
            completed_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            error_message=str(e)
        )
        await material_service.update_processing_status(error_status)


@router.get("/processing/{material_id}", response_model=FrontendMaterialProcessingStatusDTO)
async def get_material_processing_status(
    material_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Get the processing status of a material.
    """
    try:
        # Get processing status
        processing_status = await material_service.get_processing_status(material_id)
        
        if not processing_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Processing status not found for material {material_id}"
            )
        
        return FrontendMaterialProcessingStatusDTO.from_backend(processing_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting processing status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting processing status: {str(e)}"
        )


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: str,
    delete_embeddings: bool = Query(True),
    user_id: str = Depends(check_admin_or_instructor_role)
):
    """
    Delete a material and optionally its embeddings.
    """
    try:
        # Get material
        material = await material_service.get_material(material_id)
        
        if not material:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Material {material_id} not found"
            )
            
        # Delete material
        success = await material_service.delete_material(material_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error deleting material {material_id}"
            )
            
        # Delete file from Cloudinary
        try:
            # Extract public ID from URL
            public_id = f"course_materials/{material.course_id}/{material_id}"
            await cloudinary_service.delete_file(public_id)
            logger.info(f"Deleted file from Cloudinary: {public_id}")
        except Exception as e:
            logger.warning(f"Error deleting file from Cloudinary: {str(e)}")
        
        # Delete embeddings if requested
        if delete_embeddings:
            try:
                # Use the RAG service to delete embeddings
                success = await rag_service.delete_material_embeddings(material_id)
                logger.info(f"Deleted embeddings for material {material_id}: {success}")
            except Exception as e:
                logger.warning(f"Error deleting embeddings: {str(e)}")
        
        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting material: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting material: {str(e)}"
        )


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Get a material by ID.
    """
    try:
        # Get material
        material = await material_service.get_material(material_id)
        
        if not material:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Material {material_id} not found"
            )
            
        return material
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting material: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting material: {str(e)}"
        )


@router.post("/{material_id}/reindex", response_model=FrontendMaterialProcessingStatusDTO)
async def reindex_material(
    material_id: str,
    user_id: str = Depends(check_admin_or_instructor_role)
):
    """
    Reindex a material (delete and recreate vector embeddings).
    
    This endpoint is restricted to admin and instructor roles.
    """
    try:
        # Get material
        material = await material_service.get_material(material_id)
        
        if not material:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Material {material_id} not found"
            )
        
        # Create new processing status
        timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        processing_status = MaterialProcessingStatus(
            material_id=material_id,
            status="processing",
            progress=0.0,
            started_at=timestamp
        )
        
        # Update processing status
        await material_service.update_processing_status(processing_status)
        
        # Start reindexing in background
        asyncio.create_task(reindex_material_background(material))
        
        return FrontendMaterialProcessingStatusDTO.from_backend(processing_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reindexing material: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reindexing material: {str(e)}"
        )


async def reindex_material_background(material: MaterialResponse):
    """Background task to reindex material"""
    try:
        logger.info(f"Starting reindexing of material {material.id}")
        
        # Delete existing embeddings
        await rag_service.delete_material_embeddings(material.id)
        
        # Process the material again
        # Convert MaterialResponse to MaterialUploadResponse
        material_upload = MaterialUploadResponse(
            id=material.id,
            title=material.title,
            description=material.description,
            type=material.type,
            course_id=material.course_id,
            module_id=material.module_id,
            topic_id=material.topic_id,
            file_url=material.file_url,
            file_size=material.file_size,
            file_type=material.file_type,
            status="processing",
            uploaded_at=material.uploaded_at,
            uploaded_by=material.uploaded_by if hasattr(material, 'uploaded_by') else None
        )
        
        # Process the material
        processing_status = await rag_service.process_material(material_upload)
        
        # Update material status
        await material_service.update_material_status(material.id, processing_status.status, 
                                                    processing_status.error_message if processing_status.status == "failed" else None)
        
        # Update processing status
        await material_service.update_processing_status(processing_status)
        
        logger.info(f"Completed reindexing of material {material.id} with status: {processing_status.status}")
        
    except Exception as e:
        logger.error(f"Error in reindexing material {material.id}: {str(e)}", exc_info=True)
        # Update material status to failed
        await material_service.update_material_status(material.id, "failed", str(e))
        
        # Update processing status
        error_status = MaterialProcessingStatus(
            material_id=material.id,
            status="failed",
            progress=0.0,
            started_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            completed_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            error_message=str(e)
        )
        await material_service.update_processing_status(error_status)


@router.patch("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: str,
    update_data: MaterialUpdate,
    user_id: str = Depends(check_admin_or_instructor_role)
):
    """
    Update a material's metadata.
    
    This endpoint is restricted to admin and instructor roles.
    """
    try:
        # Get original material to ensure it exists
        original_material = await material_service.get_material(material_id)
        
        if not original_material:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Material {material_id} not found"
            )
        
        # Check if updating is allowed (don't allow if processing)
        if original_material.status == "processing":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update material {material_id} while it's being processed"
            )
        
        # Update material metadata
        updated = await material_service.update_material_metadata(material_id, update_data.dict(exclude_unset=True))
        
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error updating material {material_id}"
            )
        
        # Get updated material
        updated_material = await material_service.get_material(material_id)
        
        return updated_material
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating material: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating material: {str(e)}"
        )

@router.get("/", response_model=List[MaterialResponse])
async def get_materials(
    course_id: Optional[str] = Query(None),
    module_id: Optional[str] = Query(None),
    topic_id: Optional[str] = Query(None),
    material_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id)
):
    """
    Get materials with optional filters.
    """
    try:
        # Get materials based on filters
        if course_id:
            materials = await material_service.get_materials_by_course(course_id, module_id, topic_id)
            
            # Filter by type if provided
            if material_type:
                materials = [m for m in materials if m.type == material_type]
                
            # Filter by status if provided
            if status:
                materials = [m for m in materials if m.status == status]
            
            # Apply pagination
            materials = materials[offset:offset + limit]
        else:
            # Get all materials with pagination and status filter
            materials = await material_service.get_all_materials(limit, offset, status)
            
            # Filter by type if provided
            if material_type:
                materials = [m for m in materials if m.type == material_type]
        
        return materials
        
    except Exception as e:
        logger.error(f"Error getting materials: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting materials: {str(e)}"
        )
    
    
# from datetime import datetime
# import json
# from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, logger, status, File, UploadFile
# from typing import List, Optional
# from app.core.security import check_admin_or_instructor_role, get_current_user
# from app.dto.material_dto import FrontendMaterialProcessingStatusDTO, FrontendMaterialUploadResponseDTO
# from app.schemas.material import MaterialCreate, MaterialResponse, MaterialUpdate
# from app.schemas.material_upload import MaterialProcessingStatus, MaterialUploadResponse
# from app.services.file_processing_service import FileProcessingService
# from app.services.material_service import MaterialService

# router = APIRouter(prefix="/materials", tags=["materials"])
# material_service = MaterialService()
# file_processing_service = FileProcessingService()

# @router.post("/upload", response_model=FrontendMaterialUploadResponseDTO, status_code=status.HTTP_201_CREATED)
# async def upload_material(
#     background_tasks: BackgroundTasks,
#     file: UploadFile = File(...),
#     course_id: str = Form(...),
#     module_id: Optional[str] = Form(None),
#     topic_id: Optional[str] = Form(None),
#     title: Optional[str] = Form(None),
#     description: Optional[str] = Form(None),
#     material_type: Optional[str] = Form("lecture"),
#     current_user=Depends(get_current_user),
#     _=Depends(check_admin_or_instructor_role)
# ):
#     """
#     Upload a material file for processing and RAG indexing.
    
#     Args:
#         file: File to upload
#         course_id: Course ID to associate with the material
#         module_id: Optional module ID
#         topic_id: Optional topic ID
#         title: Optional title (uses filename if not provided)
#         description: Optional description
#         material_type: Type of material (lecture, lab, reading, etc.)
        
#     Returns:
#         Material upload response with processing status
#     """
#     try:
#         # Process the file (initial steps only)
#         material_data = await file_processing_service.process_file_initial(
#             file=file,
#             course_id=course_id,
#             user_id=current_user.id,
#             module_id=module_id,
#             topic_id=topic_id,
#             title=title,
#             description=description,
#             file_type=material_type
#         )

#         # Add the complete processing to background tasks
#         background_tasks.add_task(
#             file_processing_service.process_file_background,
#             material_id=material_data["id"]
#         )
        
#         # Convert to response model
#         upload_response = MaterialUploadResponse(
#             id=material_data["id"],
#             title=material_data["title"],
#             description=material_data["description"],
#             type=material_data["type"],
#             course_id=material_data["course_id"],
#             module_id=material_data.get("module_id"),
#             topic_id=material_data.get("topic_id"),
#             file_url=material_data["file_url"],
#             file_size=material_data["file_size"],
#             file_type=material_data["file_type"],
#             status=material_data["status"],
#             uploaded_at=material_data["uploaded_at"]
#         )
        
#         # Convert to frontend DTO
#         return FrontendMaterialUploadResponseDTO.from_backend(upload_response)
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to upload material: {str(e)}"
#         )

# @router.post("/batch-upload", response_model=List[FrontendMaterialUploadResponseDTO], status_code=status.HTTP_201_CREATED)
# async def batch_upload_materials(
#     background_tasks: BackgroundTasks,
#     files: List[UploadFile] = File(...),
#     course_id: str = Form(...),
#     module_id: Optional[str] = Form(None),
#     topic_id: Optional[str] = Form(None),
#     metadata: Optional[str] = Form(None),  # JSON string with title/description for each file
#     material_type: Optional[str] = Form("lecture"),
#     current_user=Depends(get_current_user),
#     _=Depends(check_admin_or_instructor_role)
# ):
#     """
#     Upload multiple material files in a batch.
    
#     Args:
#         files: Files to upload
#         course_id: Course ID to associate with the materials
#         module_id: Optional module ID
#         topic_id: Optional topic ID
#         metadata: Optional JSON string with metadata for each file
#         material_type: Type of material (lecture, lab, reading, etc.)
        
#     Returns:
#         List of material upload responses
#     """
#     try:
#         # Parse metadata if provided
#         file_metadata = {}
#         if metadata:
#             try:
#                 file_metadata = json.loads(metadata)
#             except json.JSONDecodeError:
#                 raise HTTPException(
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     detail="Invalid metadata JSON format"
#                 )
        
#         # Process files
#         responses = []
#         for file in files:
#             # Get metadata for this file if available
#             file_meta = file_metadata.get(file.filename, {})
            
#             # Process the file (initial steps only)
#             material_data = await file_processing_service.process_file_initial(
#                 file=file,
#                 course_id=course_id,
#                 user_id=current_user.id,
#                 module_id=module_id,
#                 topic_id=topic_id,
#                 title=file_meta.get("title"),
#                 description=file_meta.get("description"),
#                 file_type=material_type
#             )
            
#             # Add the complete processing to background tasks
#             background_tasks.add_task(
#                 file_processing_service.process_file_background,
#                 material_id=material_data["id"]
#             )
            
#             # Convert to response model
#             upload_response = MaterialUploadResponse(
#                 id=material_data["id"],
#                 title=material_data["title"],
#                 description=material_data["description"],
#                 type=material_data["type"],
#                 course_id=material_data["course_id"],
#                 module_id=material_data.get("module_id"),
#                 topic_id=material_data.get("topic_id"),
#                 file_url=material_data["file_url"],
#                 file_size=material_data["file_size"],
#                 file_type=material_data["file_type"],
#                 status=material_data["status"],
#                 uploaded_at=material_data["uploaded_at"]
#             )
            
#             # Convert to frontend DTO and add to responses
#             responses.append(FrontendMaterialUploadResponseDTO.from_backend(upload_response))
        
#         return responses
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to upload materials: {str(e)}"
#         )

# @router.get("/processing/{material_id}", response_model=FrontendMaterialProcessingStatusDTO)
# async def get_material_processing_status(
#     material_id: str,
#     current_user=Depends(get_current_user)
# ):
#     """
#     Get the processing status of a material.
    
#     Args:
#         material_id: ID of the material to check
        
#     Returns:
#         Processing status details
#     """
#     try:
#         # Get processing status
#         status_data = await file_processing_service.get_processing_status(material_id)
        
#         # Validate the data before constructing the Pydantic model
#         if not isinstance(status_data.get("started_at"), str):
#             status_data["started_at"] = datetime.utcnow().isoformat()
        
#         # Convert to response model
#         processing_status = MaterialProcessingStatus(
#             material_id=status_data["material_id"],
#             status=status_data["status"],
#             progress=status_data["progress"],
#             error_message=status_data.get("error_message"),
#             started_at=status_data["started_at"],
#             completed_at=status_data.get("completed_at")
#         )
        
#         # Convert to frontend DTO
#         return FrontendMaterialProcessingStatusDTO.from_backend(processing_status)
        
#     except Exception as e:
#         import traceback
#         error_msg = f"Failed to get processing status: {str(e)}\n{traceback.format_exc()}"
#         logger.error(error_msg)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to get processing status: {str(e)}"
#         )

# @router.get("/", response_model=List[MaterialResponse])
# async def get_materials(
#     course_id: Optional[str] = None,
#     module_id: Optional[str] = None,
#     topic_id: Optional[str] = None,
#     material_type: Optional[str] = None,
#     current_user=Depends(get_current_user)
# ):
#     """
#     Get a list of materials with optional filtering.
#     """
#     try:
#         materials = await material_service.get_materials(
#             user_id=current_user["id"],
#             course_id=course_id,
#             module_id=module_id,
#             topic_id=topic_id,
#             material_type=material_type
#         )
#         return materials
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to retrieve materials: {str(e)}"
#         )

# @router.get("/{material_id}", response_model=MaterialResponse)
# async def get_material(
#     material_id: str,
#     current_user=Depends(get_current_user)
# ):
#     """
#     Get a specific material by ID.
#     """
#     try:
#         material = await material_service.get_material(
#             material_id=material_id,
#             user_id=current_user["id"]
#         )
#         if not material:
#             raise HTTPException(
#                 status_code=404,
#                 detail=f"Material with ID {material_id} not found"
#             )
#         return material
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to retrieve material: {str(e)}"
#         )

# @router.post("/", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
# async def create_material(
#     material_data: MaterialCreate,
#     current_user=Depends(get_current_user)
# ):
#     """
#     Create a new material (admin only).
#     """
#     # Check if user is admin
#     if current_user.get("role") != "admin":
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Only administrators can create materials"
#         )
    
#     try:
#         material = await material_service.create_material(material_data)
#         return material
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to create material: {str(e)}"
#         )

# @router.put("/{material_id}", response_model=MaterialResponse)
# async def update_material(
#     material_id: str,
#     material_data: MaterialUpdate,
#     current_user=Depends(get_current_user)
# ):
#     """
#     Update a material (admin only).
#     """
#     # Check if user is admin
#     if current_user.get("role") != "admin":
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Only administrators can update materials"
#         )
    
#     try:
#         material = await material_service.update_material(
#             material_id=material_id,
#             material_data=material_data
#         )
#         if not material:
#             raise HTTPException(
#                 status_code=404,
#                 detail=f"Material with ID {material_id} not found"
#             )
#         return material
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to update material: {str(e)}"
#         )

# @router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def delete_material(
#     material_id: str,
#     current_user=Depends(get_current_user)
# ):
#     """
#     Delete a material (admin only).
#     """
#     # Check if user is admin
#     if current_user.get("role") != "admin":
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Only administrators can delete materials"
#         )
    
#     try:
#         deleted = await material_service.delete_material(material_id=material_id)
#         if not deleted:
#             raise HTTPException(
#                 status_code=404,
#                 detail=f"Material with ID {material_id} not found"
#             )
#         return None
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to delete material: {str(e)}"
#         )