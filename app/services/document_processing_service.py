# document_processing_service.py
class DocumentProcessingService:
    def __init__(
        self, 
        file_extractor,
        chunking_service, 
        embedding_service, 
        pinecone_service, 
        cloudinary_service,
        material_service
    ):
        # Initialize with all necessary services
        pass
        
    async def process_document(self, file_path, course_id, module_id=None, topic_id=None, metadata=None):
        """Process a document for RAG by extracting text, chunking, and creating embeddings"""
        
    async def process_multiple_documents(self, file_paths, course_id, module_id=None, topic_id=None, metadata=None):
        """Process multiple documents in parallel"""
        
    async def _store_material_metadata(self, cloudinary_url, document_info, chunks_info, course_id, module_id, topic_id):
        """Store document metadata and references in Firestore"""

