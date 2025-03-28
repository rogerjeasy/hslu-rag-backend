# app/services/cloudinary_service.py
import os
import logging
import cloudinary
import cloudinary.uploader
from typing import Dict, Any

from app.core.config import settings
from app.core.exceptions import ValidationException

logger = logging.getLogger(__name__)

class CloudinaryService:
    """Service for managing file storage in Cloudinary"""
    
    def __init__(self):
        """Initialize Cloudinary with settings"""
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True
        )
    
    async def upload_file(self, file_path: str, folder: str = None, public_id: str = None) -> Dict[str, Any]:
        """
        Upload a file to Cloudinary.
        
        Args:
            file_path: Path to the file
            folder: Cloudinary folder path
            public_id: Optional public ID for the resource
            
        Returns:
            Cloudinary upload response
        """
        try:
            # Determine resource type based on file extension
            resource_type = self._get_resource_type(file_path)
            
            # Set upload options
            options = {
                "resource_type": resource_type,
                "use_filename": True,
                "unique_filename": True
            }
            
            if folder:
                options["folder"] = folder
                
            if public_id:
                options["public_id"] = public_id
            
            # Upload file to Cloudinary
            result = cloudinary.uploader.upload(file_path, **options)
            
            return result
            
        except Exception as e:
            logger.error(f"Error uploading file to Cloudinary: {str(e)}")
            raise ValidationException(f"Failed to upload file to storage: {str(e)}")
    
    async def delete_file(self, public_id: str, resource_type: str = "auto") -> Dict[str, Any]:
        """
        Delete a file from Cloudinary.
        
        Args:
            public_id: Public ID of the resource
            resource_type: Type of resource (image, video, raw, auto)
            
        Returns:
            Cloudinary deletion response
        """
        try:
            result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            return result
            
        except Exception as e:
            logger.error(f"Error deleting file from Cloudinary: {str(e)}")
            raise ValidationException(f"Failed to delete file from storage: {str(e)}")
    
    def _get_resource_type(self, file_path: str) -> str:
        """
        Determine the appropriate resource type for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Resource type: 'image', 'video', or 'raw'
        """
        # Get file extension
        _, extension = os.path.splitext(file_path)
        extension = extension.lower()
        
        # Image types
        if extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.svg']:
            return 'image'
        
        # Video types
        if extension in ['.mp4', '.mov', '.avi', '.webm', '.mkv', '.flv']:
            return 'video'
        
        # Default to raw for all other file types
        return 'raw'
    
    async def download_file(self, file_url: str, destination_path: str) -> str:
        """
        Download a file from Cloudinary URL to a local path.
        
        Args:
            file_url: Cloudinary URL of the file
            destination_path: Local path to save the file
            
        Returns:
            Path to downloaded file
        """
        try:
            import requests
            
            # Fetch the file from Cloudinary
            response = requests.get(file_url, stream=True)
            response.raise_for_status()  # Raise error for bad status codes
            
            # Save the file to the destination path
            with open(destination_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"Successfully downloaded file from {file_url} to {destination_path}")
            return destination_path
            
        except Exception as e:
            logger.error(f"Error downloading file from Cloudinary: {str(e)}")
            raise ValidationException(f"Failed to download file from storage: {str(e)}")