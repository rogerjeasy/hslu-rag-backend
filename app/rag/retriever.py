import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.exceptions import RAGException
from app.rag.embeddings import EmbeddingGenerator
from app.utils.astra_db_manager import AstraDBManager

logger = logging.getLogger(__name__)

class Retriever:
    """
    Component for retrieving relevant document chunks based on query embeddings.
    
    This class handles the connection to AstraDB and performs
    similarity search to find relevant context for user queries.
    """
    
    def __init__(self):
        """Initialize the retriever with AstraDB connection"""
        self.embedding_generator = EmbeddingGenerator()
        self.astra_manager = AstraDBManager()
        self.collection_name = settings.ASTRA_DB_COLLECTION or "course_materials"
        self._init_astra_db()
    
    def _init_astra_db(self):
        """Initialize connection to AstraDB"""
        try:
            # Connect to AstraDB
            self.database = self.astra_manager.connect()
            
            # Get or create collection
            self.collection = self.astra_manager.get_or_create_collection(
                collection_name=self.collection_name
            )
            
            logger.info(f"AstraDB connection initialized successfully for collection: {self.collection_name}")
        
        except Exception as e:
            logger.error(f"Error initializing AstraDB: {str(e)}")
            raise RAGException(f"Failed to initialize AstraDB: {str(e)}")
    
    async def retrieve(
        self,
        query: str,
        limit: int = 5,
        course_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant document chunks based on the query.
        
        Args:
            query: The user's question or request
            limit: Maximum number of chunks to retrieve
            course_id: Optional course ID to filter by
            
        Returns:
            List of relevant document chunks with metadata
        """
        try:
            # Generate embedding for the query
            query_embedding = await self.embedding_generator.generate(query)
            
            # Prepare filter if course_id is provided
            filter_condition = None
            if course_id:
                filter_condition = {"metadata.course_id": course_id}
            
            # Perform vector search
            results = self.astra_manager.find_similar(
                collection=self.collection,
                query_vector=query_embedding,
                limit=limit,
                include_value=True,
                filter_condition=filter_condition
            )
            
            # Format results
            chunks = []
            for result in results:
                chunk = {
                    "id": result.get("_id", ""),
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "score": result.get("$similarity", 0.0)
                }
                chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error retrieving relevant chunks: {str(e)}")
            raise RAGException(f"Failed to retrieve relevant chunks: {str(e)}")
    
    async def add_chunks(
        self,
        chunks: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Add document chunks to AstraDB.
        
        Args:
            chunks: List of document chunks with text and metadata
            
        Returns:
            List of IDs for the added chunks
        """
        try:
            # Prepare documents for insertion
            documents = []
            for chunk in chunks:
                # Create vectorization text
                content = chunk.get("content", "")
                metadata = chunk.get("metadata", {})
                
                # Create document structure
                document = {
                    "_id": chunk.get("id"),
                    "content": content,
                    "metadata": metadata,
                    "$vectorize": self._create_vectorization_text(content, metadata)
                }
                documents.append(document)
            
            # Insert documents
            result = self.astra_manager.insert_documents(self.collection, documents)
            
            logger.info(f"Added {len(chunks)} chunks to AstraDB")
            return result.inserted_ids
            
        except Exception as e:
            logger.error(f"Error adding chunks to AstraDB: {str(e)}")
            raise RAGException(f"Failed to add chunks to AstraDB: {str(e)}")
    
    def _create_vectorization_text(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Create text that will be converted to vector embedding.
        
        Args:
            content: Document content
            metadata: Document metadata
            
        Returns:
            str: Text to be vectorized
        """
        # Get relevant metadata for context 
        course_name = metadata.get("course_name", "")
        course_id = metadata.get("course_id", "")
        source = metadata.get("source", "")
        chunk_type = metadata.get("chunk_type", "")
        
        # Combine content with relevant metadata for better semantic search
        vectorize_text = f"Course: {course_name} ({course_id})\nSource: {source}\nType: {chunk_type}\nContent: {content}"
        return vectorize_text
    
    async def delete_chunks(
        self,
        chunk_ids: List[str] = None,
        filter_criteria: Dict[str, Any] = None
    ) -> None:
        """
        Delete chunks from AstraDB.
        
        Args:
            chunk_ids: Optional list of chunk IDs to delete
            filter_criteria: Optional filter to select chunks for deletion
        """
        try:
            self.astra_manager.delete_documents(
                collection=self.collection,
                ids=chunk_ids,
                filter_condition=filter_criteria
            )
            
            logger.info(f"Deleted chunks from AstraDB")
            
        except Exception as e:
            logger.error(f"Error deleting chunks from AstraDB: {str(e)}")
            raise RAGException(f"Failed to delete chunks from AstraDB: {str(e)}")