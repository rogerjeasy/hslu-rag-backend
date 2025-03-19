import logging
from typing import Optional
from astrapy import DataAPIClient, Database, Collection
from app.core.config import settings
from astrapy.constants import VectorMetric
from astrapy.info import CollectionVectorServiceOptions

logger = logging.getLogger(__name__)

class AstraDBManager:
    """
    Manages AstraDB connections and collection operations.
    
    This class handles connection to AstraDB and provides methods
    for collection management, document operations, and vector search.
    """
    
    def __init__(self):
        """Initialize AstraDB manager with configuration settings"""
        self.endpoint = settings.ASTRA_DB_API_ENDPOINT
        self.token = settings.ASTRA_DB_APPLICATION_TOKEN
        self.namespace = settings.ASTRA_DB_NAMESPACE
        self.client = None
        self.database = None
        
    def connect(self) -> Database:
        """
        Establish connection to AstraDB.
        
        Returns:
            Database: Connected database instance
        
        Raises:
            Exception: If connection fails
        """
        try:
            self.client = DataAPIClient(self.token)
            self.database = self.client.get_database(self.endpoint)
            logger.info(f"Connected to AstraDB database {self.database.info().name}")
            return self.database
        except Exception as e:
            logger.error(f"Failed to connect to AstraDB: {str(e)}")
            raise
    
    def get_or_create_collection(
        self, 
        collection_name: str,
        dimension: int = settings.EMBEDDING_DIMENSION,
        metric: str = VectorMetric.COSINE
    ) -> Collection:
        """
        Get existing collection or create a new one if it doesn't exist.
        
        Args:
            collection_name: Name of the collection
            dimension: Vector dimension size
            metric: Distance metric for vector similarity
            
        Returns:
            Collection: AstraDB collection instance
        """
        if not self.database:
            self.connect()
            
        try:
            # First try to get existing collection
            collection = self.database.get_collection(collection_name)
            logger.info(f"Using existing collection: {collection_name}")
            return collection
        except Exception:
            # If collection doesn't exist, create it
            logger.info(f"Creating new collection: {collection_name}")
            collection = self.database.create_collection(
                collection_name,
                dimension=dimension,
                metric=metric,
                service=CollectionVectorServiceOptions(
                    provider=settings.EMBEDDING_PROVIDER,
                    model_name=settings.EMBEDDING_MODEL_NAME,
                ),
                embedding_api_key=settings.OPENAI_API_KEY,
                check_exists=True
            )
            return collection
    
    def insert_documents(
        self,
        collection: Collection,
        documents: list,
        vectorize_key: str = "$vectorize"
    ) -> dict:
        """
        Insert documents into collection with vectorization.
        
        Args:
            collection: AstraDB collection instance
            documents: List of document dictionaries
            vectorize_key: Key used for vectorization content
            
        Returns:
            dict: Response from the insert operation
        """
        try:
            result = collection.insert_many(documents)
            logger.info(f"Inserted {len(result.inserted_ids)} documents into {collection.full_name}")
            return result
        except Exception as e:
            logger.error(f"Error inserting documents: {str(e)}")
            raise
    
    def find_similar(
        self,
        collection: Collection,
        query_vector: list,
        limit: int = 5,
        include_value: bool = False,
        filter_condition: Optional[dict] = None
    ) -> list:
        """
        Find similar documents using vector search.
        
        Args:
            collection: AstraDB collection instance
            query_vector: Embedding vector to search with
            limit: Maximum number of results
            include_value: Whether to include similarity score
            filter_condition: Optional metadata filter
            
        Returns:
            list: Similar documents with metadata
        """
        try:
            results = collection.vector_find(
                vector=query_vector,
                limit=limit,
                include_similarity=include_value,
                filter=filter_condition
            )
            return results
        except Exception as e:
            logger.error(f"Error in vector search: {str(e)}")
            raise
    
    def find_similar_by_text(
        self,
        collection: Collection,
        query_text: str,
        limit: int = 5,
        include_value: bool = False,
        filter_condition: Optional[dict] = None
    ) -> list:
        """
        Find similar documents using text query (auto-vectorized).
        
        Args:
            collection: AstraDB collection instance
            query_text: Text to search with (will be vectorized)
            limit: Maximum number of results
            include_value: Whether to include similarity score
            filter_condition: Optional metadata filter
            
        Returns:
            list: Similar documents with metadata
        """
        try:
            results = collection.vector_find_by_text(
                text=query_text,
                limit=limit,
                include_similarity=include_value,
                filter=filter_condition
            )
            return results
        except Exception as e:
            logger.error(f"Error in text-based vector search: {str(e)}")
            raise