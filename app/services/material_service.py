# app/services/material_service.py
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.firebase import firebase
from app.core.config import settings
from app.schemas.material_upload import MaterialUploadResponse, MaterialProcessingStatus
from app.schemas.material import MaterialResponse, MaterialUpdate

logger = logging.getLogger(__name__)

class MaterialService:
    """
    Enhanced service for managing course materials in the database
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
            logger.info(f"Creating material record in database: {material.id}")
            
            # Convert to dictionary
            material_dict = material.dict() if hasattr(material, 'dict') else material
            
            # Add timestamps
            if 'created_at' not in material_dict:
                material_dict['created_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            if 'updated_at' not in material_dict:
                material_dict['updated_at'] = material_dict['created_at']
            
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
            logger.error(f"Error creating material: {str(e)}", exc_info=True)
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
                logger.warning(f"Material not found: {material_id}")
                return None
            
            # Convert to MaterialResponse
            return MaterialResponse(**doc.to_dict())
            
        except Exception as e:
            logger.error(f"Error getting material: {str(e)}", exc_info=True)
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
            logger.info(f"Updating material: {material_id}")
            
            # Convert to dictionary
            material_dict = material.dict() if hasattr(material, 'dict') else material
            
            # Add update timestamp
            material_dict['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            # Update in Firestore
            self.materials_collection.document(material_id).update(material_dict)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating material: {str(e)}", exc_info=True)
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
            logger.info(f"Updating material status: {material_id} -> {status}")
            
            # Create update dictionary
            update_dict = {
                "status": status,
                "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            
            # Add error message if provided
            if error_message:
                update_dict["error_message"] = error_message
            
            # Update in Firestore
            self.materials_collection.document(material_id).update(update_dict)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating material status: {str(e)}", exc_info=True)
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
            logger.info(f"Deleting material: {material_id}")
            
            # Delete from Firestore
            self.materials_collection.document(material_id).delete()
            
            # Also delete processing status
            self.processing_collection.document(material_id).delete()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting material: {str(e)}", exc_info=True)
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
            
            # Add update timestamp if not provided
            if 'updated_at' not in status_dict:
                status_dict['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            # If completed or failed, add completed timestamp if not provided
            if status_dict['status'] in ['completed', 'failed'] and 'completed_at' not in status_dict:
                status_dict['completed_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            # Update in Firestore
            self.processing_collection.document(status.material_id).set(status_dict)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating processing status: {str(e)}", exc_info=True)
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
                logger.warning(f"Processing status not found for material: {material_id}")
                return None
            
            # Convert to MaterialProcessingStatus
            return MaterialProcessingStatus(**doc.to_dict())
            
        except Exception as e:
            logger.error(f"Error getting processing status: {str(e)}", exc_info=True)
            raise
    
    async def get_materials_by_course(self, course_id: str, module_id: Optional[str] = None, topic_id: Optional[str] = None) -> List[MaterialResponse]:
        """
        Get materials by course ID and optionally module ID or topic ID
        
        Args:
            course_id: Course ID
            module_id: Optional module ID
            topic_id: Optional topic ID
            
        Returns:
            List of materials
        """
        try:
            # Query Firestore
            query = self.materials_collection.where(filter=FieldFilter("course_id", "==", course_id))
            
            if module_id:
                query = query.where(filter=FieldFilter("module_id", "==", module_id))
            
            if topic_id:
                query = query.where(filter=FieldFilter("topic_id", "==", topic_id))
            
            # Execute query
            docs = query.get()
            
            # Convert to MaterialResponse objects
            return [MaterialResponse(**doc.to_dict()) for doc in docs]
            
        except Exception as e:
            logger.error(f"Error getting materials by course: {str(e)}", exc_info=True)
            raise
    
    async def get_all_materials(self, limit: int = 100, offset: int = 0, status: Optional[str] = None) -> List[MaterialResponse]:
        """
        Get all materials with pagination and optional status filter
        
        Args:
            limit: Maximum number of materials to return
            offset: Offset for pagination
            status: Optional status filter
            
        Returns:
            List of materials
        """
        try:
            # Query Firestore
            query = self.materials_collection.order_by("uploaded_at", direction=firestore.Query.DESCENDING)
            
            # Add status filter if provided
            if status:
                query = query.where(filter=FieldFilter("status", "==", status))
            
            # Apply pagination
            query = query.limit(limit).offset(offset)
            
            # Execute query
            docs = query.get()
            
            # Convert to MaterialResponse objects
            return [MaterialResponse(**doc.to_dict()) for doc in docs]
            
        except Exception as e:
            logger.error(f"Error getting all materials: {str(e)}", exc_info=True)
            raise
    
    async def update_material_metadata(self, material_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update material metadata without changing other fields
        
        Args:
            material_id: ID of the material
            metadata: Metadata to update
            
        Returns:
            Success status
        """
        try:
            logger.info(f"Updating material metadata: {material_id}")
            
            # Add update timestamp
            metadata['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            # Update in Firestore
            self.materials_collection.document(material_id).update(metadata)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating material metadata: {str(e)}", exc_info=True)
            raise
    
    async def count_materials_by_status(self) -> Dict[str, int]:
        """
        Count materials by status
        
        Returns:
            Dictionary of status counts
        """
        try:
            # Get all materials
            all_docs = self.materials_collection.get()
            
            # Count by status
            status_counts = {
                "processing": 0,
                "completed": 0,
                "failed": 0,
                "total": 0
            }
            
            for doc in all_docs:
                data = doc.to_dict()
                status = data.get("status", "unknown")
                
                if status in status_counts:
                    status_counts[status] += 1
                else:
                    status_counts[status] = 1
                
                status_counts["total"] += 1
            
            return status_counts
            
        except Exception as e:
            logger.error(f"Error counting materials by status: {str(e)}", exc_info=True)
            raise
    
    async def get_recent_materials(self, limit: int = 5) -> List[MaterialResponse]:
        """
        Get most recently uploaded materials
        
        Args:
            limit: Maximum number of materials to return
            
        Returns:
            List of materials
        """
        try:
            # Query Firestore
            query = (self.materials_collection
                     .order_by("uploaded_at", direction=firestore.Query.DESCENDING)
                     .limit(limit))
            
            # Execute query
            docs = query.get()
            
            # Convert to MaterialResponse objects
            return [MaterialResponse(**doc.to_dict()) for doc in docs]
            
        except Exception as e:
            logger.error(f"Error getting recent materials: {str(e)}", exc_info=True)
            raise


    async def update_material_with_schema(self, material_id: str, update_data: MaterialUpdate) -> bool:
        """
        Update a material in the database using MaterialUpdate schema
        
        Args:
            material_id: ID of the material
            update_data: Updated material data
            
        Returns:
            Success status
        """
        try:
            logger.info(f"Updating material with schema: {material_id}")
            
            # Convert to dictionary, only including set fields
            update_dict = update_data.dict(exclude_unset=True)
            
            # Handle type field conversion - in frontend it's just "type", in backend it's "material_type"
            if "type" in update_dict:
                update_dict["material_type"] = update_dict.pop("type")
            
            # Handle course_id field conversion
            if "course_id" in update_dict:
                update_dict["course_id"] = update_dict.pop("course_id")
            
            # Add update timestamp
            update_dict['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            # Update in Firestore
            self.materials_collection.document(material_id).update(update_dict)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating material with schema: {str(e)}", exc_info=True)
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

