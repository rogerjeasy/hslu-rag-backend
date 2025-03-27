# app/services/material_service.py
import logging
import time
from typing import List, Dict, Any, Optional
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.firebase import firebase
from app.schemas.material_upload import MaterialUploadResponse, MaterialProcessingStatus
from app.schemas.material import MaterialResponse, MaterialUpdate

logger = logging.getLogger(__name__)

class MaterialService:
    """
    Service for managing course materials in the database
    """
    
    def __init__(self):
        """Initialize the service with Firestore database"""
        self.db = firebase.get_firestore()
        self.materials_collection = self.db.collection("materials")
        self.processing_collection = self.db.collection("material_processing")
    
    async def create_material(self, material: MaterialUploadResponse) -> str:
        """
        Create a new material in the database
        
        Args:
            material: Material upload response
            
        Returns:
            Material ID
        """
        try:
            # Convert to dictionary
            material_dict = material.dict() if hasattr(material, 'dict') else material
            
            # Add to Firestore
            self.materials_collection.document(material.id).set(material_dict)
            
            # Create initial processing status
            processing_status = MaterialProcessingStatus(
                material_id=material.id,
                status="processing",
                progress=0.0,
                started_at=material.uploaded_at
            )
            
            # Add processing status to Firestore
            self.processing_collection.document(material.id).set(
                processing_status.dict() if hasattr(processing_status, 'dict') else processing_status
            )
            
            return material.id
            
        except Exception as e:
            logger.error(f"Error creating material: {str(e)}")
            raise
    
    async def get_material(self, material_id: str) -> Optional[MaterialResponse]:
        """
        Get a material by ID
        
        Args:
            material_id: ID of the material
            
        Returns:
            Material response or None if not found
        """
        try:
            # Get from Firestore
            doc = self.materials_collection.document(material_id).get()
            
            if not doc.exists:
                return None
            
            # Convert to MaterialResponse
            return MaterialResponse(**doc.to_dict())
            
        except Exception as e:
            logger.error(f"Error getting material: {str(e)}")
            raise
    
    async def update_material(self, material_id: str, material: MaterialUploadResponse) -> bool:
        """
        Update a material in the database
        
        Args:
            material_id: ID of the material
            material: Updated material data
            
        Returns:
            Success status
        """
        try:
            # Convert to dictionary
            material_dict = material.dict() if hasattr(material, 'dict') else material
            
            # Update in Firestore
            self.materials_collection.document(material_id).update(material_dict)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating material: {str(e)}")
            raise
    
    async def update_material_status(self, material_id: str, status: str, error_message: Optional[str] = None) -> bool:
        """
        Update material status
        
        Args:
            material_id: ID of the material
            status: New status (processing, completed, failed)
            error_message: Optional error message for failed status
            
        Returns:
            Success status
        """
        try:
            # Update in Firestore
            self.materials_collection.document(material_id).update({
                "status": status,
                "error_message": error_message
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating material status: {str(e)}")
            raise
    
    async def delete_material(self, material_id: str) -> bool:
        """
        Delete a material from the database
        
        Args:
            material_id: ID of the material
            
        Returns:
            Success status
        """
        try:
            # Delete from Firestore
            self.materials_collection.document(material_id).delete()
            
            # Also delete processing status
            self.processing_collection.document(material_id).delete()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting material: {str(e)}")
            raise
    
    async def update_processing_status(self, status: MaterialProcessingStatus) -> bool:
        """
        Update processing status in the database
        
        Args:
            status: Processing status
            
        Returns:
            Success status
        """
        try:
            # Convert to dictionary
            status_dict = status.dict() if hasattr(status, 'dict') else status
            
            # Update in Firestore
            self.processing_collection.document(status.material_id).set(status_dict)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating processing status: {str(e)}")
            raise
    
    async def get_processing_status(self, material_id: str) -> Optional[MaterialProcessingStatus]:
        """
        Get processing status by material ID
        
        Args:
            material_id: ID of the material
            
        Returns:
            Processing status or None if not found
        """
        try:
            # Get from Firestore
            doc = self.processing_collection.document(material_id).get()
            
            if not doc.exists:
                return None
            
            # Convert to MaterialProcessingStatus
            return MaterialProcessingStatus(**doc.to_dict())
            
        except Exception as e:
            logger.error(f"Error getting processing status: {str(e)}")
            raise
    
    async def get_materials_by_course(self, course_id: str, module_id: Optional[str] = None) -> List[MaterialResponse]:
        """
        Get materials by course ID and optionally module ID
        
        Args:
            course_id: Course ID
            module_id: Optional module ID
            
        Returns:
            List of materials
        """
        try:
            # Query Firestore
            query = self.materials_collection.where(filter=FieldFilter("course_id", "==", course_id))
            
            if module_id:
                query = query.where(filter=FieldFilter("module_id", "==", module_id))
            
            # Execute query
            docs = query.get()
            
            # Convert to MaterialResponse objects
            return [MaterialResponse(**doc.to_dict()) for doc in docs]
            
        except Exception as e:
            logger.error(f"Error getting materials by course: {str(e)}")
            raise
    
    async def get_all_materials(self, limit: int = 100, offset: int = 0) -> List[MaterialResponse]:
        """
        Get all materials with pagination
        
        Args:
            limit: Maximum number of materials to return
            offset: Offset for pagination
            
        Returns:
            List of materials
        """
        try:
            # Query Firestore
            query = self.materials_collection.order_by("uploaded_at", direction=firestore.Query.DESCENDING)
            
            # Apply pagination
            query = query.limit(limit).offset(offset)
            
            # Execute query
            docs = query.get()
            
            # Convert to MaterialResponse objects
            return [MaterialResponse(**doc.to_dict()) for doc in docs]
            
        except Exception as e:
            logger.error(f"Error getting all materials: {str(e)}")
            raise
        

# import uuid
# from typing import List, Dict, Any, Optional
# import logging
# from datetime import datetime

# from app.core.firebase import firebase
# from app.core.exceptions import NotFoundException

# logger = logging.getLogger(__name__)

# class MaterialService:
#     """Service for handling course materials in the HSLU RAG application"""
    
#     def __init__(self):
#         """Initialize the material service with Firestore connection"""
#         self.db = firebase.get_firestore() if firebase.app else None
    
#     async def get_materials(
#         self,
#         user_id: str,
#         course_id: Optional[str] = None,
#         module_id: Optional[str] = None,
#         topic_id: Optional[str] = None,
#         material_type: Optional[str] = None
#     ) -> List[Dict[str, Any]]:
#         """
#         Get a list of materials with optional filtering.
        
#         Args:
#             user_id: The ID of the current user
#             course_id: Optional course ID to filter by
#             module_id: Optional module ID to filter by
#             topic_id: Optional topic ID to filter by
#             material_type: Optional material type to filter by
            
#         Returns:
#             List of material objects
#         """
#         try:
#             # For now, return mock data
#             return [
#                 {
#                     "id": "material-1",
#                     "title": "Introduction to Data Science",
#                     "description": "Overview of data science fundamentals",
#                     "type": "lecture",
#                     "course_id": course_id or "data-science-101",
#                     "module_id": module_id or "module-1",
#                     "topic_id": topic_id or "topic-1",
#                     "source_url": "/materials/lecture1.pdf",
#                     "uploaded_at": datetime.utcnow().isoformat(),
#                     "updated_at": None,
#                     "file_size": 1024,
#                     "file_type": "pdf"
#                 }
#             ]
            
#         except Exception as e:
#             logger.error(f"Error retrieving materials: {str(e)}")
#             raise
    
#     async def get_material(self, material_id: str, user_id: str) -> Dict[str, Any]:
#         """
#         Get a specific material by ID.
        
#         Args:
#             material_id: The ID of the material
#             user_id: The ID of the current user
            
#         Returns:
#             Material object
#         """
#         try:
#             # For now, return mock data
#             return {
#                 "id": material_id,
#                 "title": "Introduction to Data Science",
#                 "description": "Overview of data science fundamentals",
#                 "type": "lecture",
#                 "course_id": "data-science-101",
#                 "module_id": "module-1",
#                 "topic_id": "topic-1",
#                 "source_url": "/materials/lecture1.pdf",
#                 "uploaded_at": datetime.utcnow().isoformat(),
#                 "updated_at": None,
#                 "file_size": 1024,
#                 "file_type": "pdf"
#             }
            
#         except Exception as e:
#             logger.error(f"Error retrieving material {material_id}: {str(e)}")
#             raise
    
#     async def create_material(self, material_data: Dict[str, Any]) -> Dict[str, Any]:
#         """
#         Create a new material.
        
#         Args:
#             material_data: Material data for creation
            
#         Returns:
#             Created material object
#         """
#         try:
#             # For now, return mock data with generated ID
#             material_id = f"material-{uuid.uuid4().hex[:8]}"
            
#             return {
#                 "id": material_id,
#                 "title": material_data.get("title", ""),
#                 "description": material_data.get("description", ""),
#                 "type": material_data.get("type", ""),
#                 "course_id": material_data.get("course_id", ""),
#                 "module_id": material_data.get("module_id", None),
#                 "topic_id": material_data.get("topic_id", None),
#                 "source_url": material_data.get("source_url", None),
#                 "uploaded_at": datetime.utcnow().isoformat(),
#                 "updated_at": None,
#                 "file_size": 0,
#                 "file_type": "pdf"
#             }
            
#         except Exception as e:
#             logger.error(f"Error creating material: {str(e)}")
#             raise
    
#     async def update_material(self, material_id: str, material_data: Dict[str, Any]) -> Dict[str, Any]:
#         """
#         Update an existing material.
        
#         Args:
#             material_id: The ID of the material to update
#             material_data: Updated material data
            
#         Returns:
#             Updated material object
#         """
#         try:
#             # For now, return mock data
#             return {
#                 "id": material_id,
#                 "title": material_data.get("title", "Updated Material"),
#                 "description": material_data.get("description", ""),
#                 "type": material_data.get("type", "lecture"),
#                 "course_id": "data-science-101",
#                 "module_id": material_data.get("module_id", None),
#                 "topic_id": material_data.get("topic_id", None),
#                 "source_url": material_data.get("source_url", None),
#                 "uploaded_at": datetime.utcnow().isoformat(),
#                 "updated_at": datetime.utcnow().isoformat(),
#                 "file_size": 1024,
#                 "file_type": "pdf"
#             }
            
#         except Exception as e:
#             logger.error(f"Error updating material {material_id}: {str(e)}")
#             raise
    
#     async def delete_material(self, material_id: str) -> bool:
#         """
#         Delete a material.
        
#         Args:
#             material_id: The ID of the material to delete
            
#         Returns:
#             True if deletion was successful
#         """
#         try:
#             # For now, return success
#             return True
            
#         except Exception as e:
#             logger.error(f"Error deleting material {material_id}: {str(e)}")
#             raise

