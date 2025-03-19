from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from typing import List, Optional
from app.core.security import get_current_user
from app.schemas.material import MaterialCreate, MaterialResponse, MaterialUpdate
from app.services.material_service import MaterialService

router = APIRouter(prefix="/materials", tags=["materials"])
material_service = MaterialService()

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