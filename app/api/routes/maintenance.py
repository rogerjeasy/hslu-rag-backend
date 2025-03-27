# app/api/routes/maintenance.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Body
from typing import List, Optional, Dict
from app.core.security import check_admin_role, get_current_user
from app.services.file_processing_service import FileProcessingService
from app.core.firebase import firebase
from pydantic import BaseModel

# Import the PineconeRepairService
from app.services.pinecone_repair_service import PineconeRepairService

router = APIRouter(prefix="/maintenance", tags=["maintenance"])
file_processing_service = FileProcessingService()
pinecone_repair_service = PineconeRepairService()

class FixEncodingsRequest(BaseModel):
    material_ids: Optional[List[str]] = None
    repair_method: Optional[str] = "full"  # Options: "full", "metadata_only"

@router.post("/fix-encodings", status_code=status.HTTP_202_ACCEPTED)
async def fix_encoded_chunks(
    request: FixEncodingsRequest = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user=Depends(get_current_user),
    _=Depends(check_admin_role)  # Only allow admins
):
    """
    Fix binary-encoded chunks in Pinecone.
    
    This is an admin-only endpoint to fix encoding issues in the vector database.
    It will reprocess the specified materials or all materials if none specified.
    
    Args:
        request: Request body containing:
            material_ids: Optional list of material IDs to fix. If not provided, fix all.
            repair_method: "full" for complete reprocessing or "metadata_only" for 
                           only fixing the metadata without new embeddings
    """
    try:
        material_ids = request.material_ids
        repair_method = request.repair_method or "full"
        
        # Validate repair method
        if repair_method not in ["full", "metadata_only"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid repair method: {repair_method}. Must be 'full' or 'metadata_only'"
            )
        
        # Start a background task based on the repair method
        if repair_method == "full":
            # Use the enhanced PineconeRepairService for full repair
            background_tasks.add_task(
                pinecone_repair_service.fix_binary_chunks,
                material_ids=material_ids
            )
        else:
            # Use the original method for metadata-only repair
            background_tasks.add_task(
                file_processing_service.fix_encoded_chunks,
                material_ids=material_ids
            )
        
        return {
            "status": "processing",
            "message": f"Started fixing {'specified materials' if material_ids else 'all materials'} using {repair_method} method",
            "material_count": len(material_ids) if material_ids else "all",
            "repair_method": repair_method
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting encoding fix process: {str(e)}"
        )

@router.get("/fix-status", status_code=status.HTTP_200_OK)
async def get_repair_status(
    current_user=Depends(get_current_user),
    _=Depends(check_admin_role)  # Only allow admins
):
    """
    Get the status of the encoding fix process.
    
    Returns information about materials that have been reprocessed and those in progress.
    """
    try:
        # Query Firestore for materials with status "reprocessing"
        in_progress_docs = firebase.get_firestore().collection("materials").where("status", "==", "reprocessing").stream()
        in_progress = [{"id": doc.id, **doc.to_dict()} for doc in in_progress_docs]
        
        # Query for recently completed materials (in the last 24 hours)
        import datetime
        yesterday = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        yesterday_str = yesterday.isoformat()
        
        completed_docs = firebase.get_firestore().collection("materials")\
            .where("status", "==", "completed")\
            .where("updated_at", ">=", yesterday_str).stream()
        
        recently_completed = [{"id": doc.id, **doc.to_dict()} for doc in completed_docs]
        
        # Query for recently failed materials
        failed_docs = firebase.get_firestore().collection("materials")\
            .where("status", "==", "failed")\
            .where("updated_at", ">=", yesterday_str).stream()
        
        recently_failed = [{"id": doc.id, **doc.to_dict()} for doc in failed_docs]
        
        return {
            "in_progress_count": len(in_progress),
            "recently_completed_count": len(recently_completed),
            "recently_failed_count": len(recently_failed),
            "in_progress": in_progress,
            "recently_completed": recently_completed,
            "recently_failed": recently_failed
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting repair status: {str(e)}"
        )

@router.post("/retry-failed", status_code=status.HTTP_202_ACCEPTED)
async def retry_failed_materials(
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    _=Depends(check_admin_role)  # Only allow admins
):
    """
    Retry all materials with 'failed' status.
    """
    try:
        # Get all failed materials
        failed_docs = firebase.get_firestore().collection("materials").where("status", "==", "failed").stream()
        failed_material_ids = [doc.id for doc in failed_docs]
        
        if not failed_material_ids:
            return {
                "status": "no_action",
                "message": "No failed materials found to retry"
            }
        
        # Start the repair process for failed materials
        background_tasks.add_task(
            pinecone_repair_service.fix_binary_chunks,
            material_ids=failed_material_ids
        )
        
        return {
            "status": "processing",
            "message": f"Started retrying {len(failed_material_ids)} failed materials",
            "material_count": len(failed_material_ids)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting retry process: {str(e)}"
        )