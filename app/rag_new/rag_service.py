
# app/rag/rag_service.py
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from fastapi import UploadFile

from app.core.config import settings
from app.schemas.material_upload import MaterialUploadResponse, MaterialProcessingStatus
from app.services.cloudinary_service import CloudinaryService
from app.rag_new.document_processor import DocumentProcessor
from app.rag_new.chuncker import TextChunker
from app.rag_new.embdeddings import EmbeddingService
from app.rag_new.retriever import RAGRetriever

logger = logging.getLogger(__name__)

class RAGService:
    """
    Main service for RAG operations
    """
    
    def __init__(self):
        """Initialize RAG service with dependencies"""
        # Initialize services
        self.cloudinary_service = CloudinaryService()
        self.chunker = TextChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        self.embedding_service = EmbeddingService()
        self.document_processor = DocumentProcessor(
            cloudinary_service=self.cloudinary_service,
            chunker=self.chunker,
            embedding_service=self.embedding_service
        )
        self.retriever = RAGRetriever(
            embedding_service=self.embedding_service
        )
    
    async def process_material(self, material: MaterialUploadResponse) -> MaterialProcessingStatus:
        """
        Process uploaded material and create vector embeddings
        
        Args:
            material: Material upload response
            
        Returns:
            Processing status
        """
        # Initialize processing status
        status = MaterialProcessingStatus(
            material_id=material.id,
            status="processing",
            progress=0.0,
            started_at=material.uploaded_at
        )
        
        try:
            # Process the file
            chunks, vector_ids = await self.document_processor.process_file(
                file_url=material.file_url,
                file_type=material.file_type,
                material_id=material.id
            )
            
            # Update material with chunk count and vector IDs
            material.chunk_count = len(chunks)
            material.vector_ids = vector_ids
            
            # Update status
            status.status = "completed"
            status.progress = 1.0
            status.completed_at = material.uploaded_at  # Use current time in implementation
            
            return status
            
        except Exception as e:
            logger.error(f"Error processing material {material.id}: {str(e)}")
            status.status = "failed"
            status.error_message = str(e)
            return status
    
    async def retrieve_relevant_context(
        self, 
        query: str, 
        course_id: Optional[str] = None,
        module_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        max_chunks: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context for a query
        
        Args:
            query: User query
            course_id: Optional course filter
            module_id: Optional module filter
            topic_id: Optional topic filter
            max_chunks: Maximum number of chunks to retrieve
            
        Returns:
            List of relevant context chunks
        """
        # Build filter
        filter_dict = {}
        if course_id:
            filter_dict["course_id"] = course_id
        if module_id:
            filter_dict["module_id"] = module_id
        if topic_id:
            filter_dict["topic_id"] = topic_id
        
        # Retrieve context
        context_chunks = await self.retriever.retrieve(
            query=query,
            filter=filter_dict,
            top_k=max_chunks
        )
        
        return context_chunks
    
    async def delete_material_embeddings(self, material_id: str) -> bool:
        """
        Delete all embeddings for a material
        
        Args:
            material_id: ID of the material
            
        Returns:
            Success status
        """
        try:
            # Delete by metadata filter
            success = await self.embedding_service.delete_by_metadata(
                filter={"material_id": material_id}
            )
            return success
        except Exception as e:
            logger.error(f"Error deleting material embeddings: {str(e)}")
            return False
