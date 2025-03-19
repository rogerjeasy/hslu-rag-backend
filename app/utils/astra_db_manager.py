# app/utils/astra_db_manager.py
import logging
import time
from typing import Optional, List, Dict, Any
from astrapy import DataAPIClient, Database, Collection
from app.core.config import settings
from app.core.exceptions import RAGException
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
        self.namespace = getattr(settings, "ASTRA_DB_NAMESPACE", "default_keyspace")
        self.client = None
        self.database = None
        
    def connect(self) -> Database:
        """
        Establish connection to AstraDB.
        
        Returns:
            Database: Connected database instance
        
        Raises:
            RAGException: If connection fails
        """
        try:
            self.client = DataAPIClient(self.token)
            self.database = self.client.get_database(self.endpoint)
            logger.info(f"Connected to AstraDB database {self.database.info().name}")
            return self.database
        except Exception as e:
            logger.error(f"Failed to connect to AstraDB: {str(e)}")
            raise RAGException(f"Failed to connect to AstraDB: {str(e)}")
    
    def get_or_create_collection(
        self, 
        collection_name: str,
        dimension: int = getattr(settings, "EMBEDDING_DIMENSIONS", 1536),
        metric: str = VectorMetric.COSINE,
        max_retries: int = 3,
        retry_delay: int = 3
    ) -> Collection:
        """
        Get existing collection or create a new one if it doesn't exist.
        This improved version handles AstraDB's eventual consistency issues.
        
        Args:
            collection_name: Name of the collection
            dimension: Vector dimension size
            metric: Distance metric for vector similarity
            max_retries: Maximum number of creation attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            Collection: AstraDB collection instance
            
        Raises:
            RAGException: If operation fails after all retries
        """
        if not self.database:
            self.connect()
                
        last_exception = None
        
        for attempt in range(1, max_retries + 1):
            try:
                # First attempt to explicitly create the collection
                # This approach ensures the collection is created fresh
                logger.info(f"Creating collection (attempt {attempt}/{max_retries}): {collection_name}")
                
                # Get provider and model name with fallbacks
                provider = getattr(settings, "EMBEDDING_PROVIDER", "openai")
                model_name = getattr(settings, "EMBEDDING_MODEL_NAME", "text-embedding-3-small")
                openai_key = getattr(settings, "OPENAI_API_KEY", "")

                try:
                    # Try to create the collection, if it already exists this will fail
                    collection = self.database.create_collection(
                        collection_name,
                        dimension=dimension,
                        metric=metric,
                        service=CollectionVectorServiceOptions(
                            provider=provider,
                            model_name=model_name,
                        ),
                        embedding_api_key=openai_key,
                        check_exists=False  # Important: We're explicitly trying to create
                    )
                    logger.info(f"Collection created: {collection_name}")
                except Exception as create_error:
                    # If creation fails, the collection might already exist
                    logger.info(f"Could not create collection: {str(create_error)}")
                    logger.info(f"Trying to get existing collection...")
                    collection = self.database.get_collection(collection_name)
                    logger.info(f"Using existing collection: {collection}")
                
                # Add a delay to ensure collection is ready
                sleep_time = retry_delay * attempt  # Progressive delay
                logger.info(f"Waiting {sleep_time}s for collection to be fully available...")
                time.sleep(sleep_time)
                
                # Create a test document to verify the collection is working
                try:
                    test_doc = {
                        "_id": f"test_doc_{int(time.time())}",
                        "test_field": "Collection verification",
                        "$vectorize": "Test document for collection verification"
                    }
                    
                    logger.info(f"Inserting test document to verify collection...")
                    result = collection.insert_one(test_doc)
                    
                    # If we get here, the collection is working properly
                    logger.info(f"Collection verified with test document insertion")
                    
                    # Clean up the test document
                    try:
                        collection.delete_one(id=test_doc["_id"])
                        logger.info(f"Test document removed")
                    except Exception as delete_error:
                        # Non-critical error, we can continue
                        logger.warning(f"Could not delete test document: {str(delete_error)}")
                    
                    return collection
                    
                except Exception as verify_error:
                    logger.warning(f"Collection verification failed: {str(verify_error)}")
                    if attempt < max_retries:
                        logger.info(f"Retrying collection creation...")
                        continue
                    else:
                        raise
                        
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt} to create/verify collection failed: {str(e)}")
                if attempt < max_retries:
                    wait_time = retry_delay * attempt * 2  # Longer delay for next retry
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to create collection {collection_name} after {max_retries} attempts: {str(e)}")
                    logger.error(f"Error details: {repr(e)}")
                    raise RAGException(f"Failed to create collection: {str(e)}")
        
        # If we get here, all retries failed
        raise RAGException(f"Failed to create collection after {max_retries} attempts: {str(last_exception)}")
        
    def insert_documents(
        self,
        collection: Collection,
        documents: List[Dict[str, Any]],
        vectorize_key: str = "$vectorize",
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> Dict[str, Any]:
        """
        Insert documents into collection with vectorization.
        Added retry logic for more robust insertion.
        
        Args:
            collection: AstraDB collection instance
            documents: List of document dictionaries
            vectorize_key: Key used for vectorization content
            max_retries: Maximum number of insertion attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            dict: Response from the insert operation
            
        Raises:
            RAGException: If insert operation fails after all retries
        """
        try:
            # Make sure each document has an _id field
            for doc in documents:
                if "_id" not in doc:
                    import uuid
                    doc["_id"] = str(uuid.uuid4())
            
            # Insert in smaller batches to avoid timeouts
            batch_size = 20
            inserted_ids = []
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                batch_inserted = False
                batch_retry_count = 0
                
                while not batch_inserted and batch_retry_count < max_retries:
                    try:
                        result = collection.insert_many(batch)
                        if hasattr(result, 'inserted_ids'):
                            inserted_ids.extend(result.inserted_ids)
                        else:
                            # Handle alternative response format
                            inserted_ids.extend([doc.get("_id") for doc in batch])
                        logger.info(f"Inserted batch of {len(batch)} documents")
                        batch_inserted = True
                    except Exception as batch_error:
                        batch_retry_count += 1
                        logger.warning(f"Error inserting batch (attempt {batch_retry_count}/{max_retries}): {str(batch_error)}")
                        
                        if batch_retry_count < max_retries:
                            wait_time = retry_delay * batch_retry_count
                            logger.info(f"Retrying batch in {wait_time} seconds...")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"Failed to insert batch after {max_retries} attempts")
                            # Continue with next batch instead of failing completely
            
            # Create a result object similar to what MongoDB would return
            class InsertManyResult:
                def __init__(self, ids):
                    self.inserted_ids = ids
                    self.inserted_count = len(ids)
            
            logger.info(f"Inserted total of {len(inserted_ids)} documents into {collection.full_name}")
            return InsertManyResult(inserted_ids)
            
        except Exception as e:
            logger.error(f"Error inserting documents: {str(e)}")
            logger.error(f"Error details: {repr(e)}")
            raise RAGException(f"Failed to insert documents: {str(e)}")
    
    def find_similar(
        self,
        collection: Collection,
        query_vector: List[float],
        limit: int = 5,
        include_value: bool = False,
        filter_condition: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Find similar documents using vector search.
        Added retry logic for more robust searching.
        
        Args:
            collection: AstraDB collection instance
            query_vector: Embedding vector to search with
            limit: Maximum number of results
            include_value: Whether to include similarity score
            filter_condition: Optional metadata filter
            max_retries: Maximum number of search attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            list: Similar documents with metadata
            
        Raises:
            RAGException: If search operation fails after all retries
        """
        last_exception = None
        
        for attempt in range(1, max_retries + 1):
            try:
                results = collection.vector_find(
                    vector=query_vector,
                    limit=limit,
                    include_similarity=include_value,
                    filter=filter_condition
                )
                return results
            except Exception as e:
                last_exception = e
                logger.warning(f"Vector search attempt {attempt}/{max_retries} failed: {str(e)}")
                if attempt < max_retries:
                    wait_time = retry_delay * attempt
                    logger.info(f"Retrying vector search in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error in vector search after {max_retries} attempts: {str(e)}")
        
        raise RAGException(f"Failed to perform vector search after {max_retries} attempts: {str(last_exception)}")
    
    def find_similar_by_text(
        self,
        collection: Collection,
        query_text: str,
        limit: int = 5,
        include_value: bool = False,
        filter_condition: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Find similar documents using text query (auto-vectorized).
        Updated to handle different API versions.
        
        Args:
            collection: AstraDB collection instance
            query_text: Text to search with (will be vectorized)
            limit: Maximum number of results
            include_value: Whether to include similarity score
            filter_condition: Optional metadata filter
            max_retries: Maximum number of search attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            list: Similar documents with metadata
            
        Raises:
            RAGException: If search operation fails after all retries
        """
        last_exception = None
        
        for attempt in range(1, max_retries + 1):
            try:
                # Try different method names for compatibility with different AstraDB client versions
                if hasattr(collection, "vector_find_by_text"):
                    # Newer API version
                    results = collection.vector_find_by_text(
                        text=query_text,
                        limit=limit,
                        include_similarity=include_value,
                        filter=filter_condition
                    )
                    return results
                elif hasattr(collection, "find_by_text"):
                    # Alternate API version
                    results = collection.find_by_text(
                        text=query_text,
                        limit=limit,
                        include_similarity=include_value,
                        filter=filter_condition
                    )
                    return results
                elif hasattr(collection, "similarity_search"):
                    # Another possible API version
                    results = collection.similarity_search(
                        text=query_text,
                        limit=limit,
                        include_similarity=include_value,
                        filter=filter_condition
                    )
                    return results
                elif hasattr(collection, "vector_search"):
                    # Fallback to vector_search if text-specific methods are unavailable
                    # This requires generating an embedding separately
                    from app.rag.embeddings import EmbeddingGenerator
                    generator = EmbeddingGenerator()
                    embedding = generator.generate_sync(query_text)
                    
                    results = collection.vector_search(
                        vector=embedding,
                        limit=limit,
                        include_similarity=include_value,
                        filter=filter_condition
                    )
                    return results
                else:
                    # Last resort - try the most common method name
                    results = collection.find_similar_by_text(
                        text=query_text,
                        limit=limit,
                        include_similarity=include_value,
                        filter=filter_condition
                    )
                    return results
                    
            except Exception as e:
                last_exception = e
                logger.warning(f"Text-based vector search attempt {attempt}/{max_retries} failed: {str(e)}")
                if attempt < max_retries:
                    wait_time = retry_delay * attempt
                    logger.info(f"Retrying text-based vector search in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error in text-based vector search after {max_retries} attempts: {str(e)}")
        
        raise RAGException(f"Failed to perform text-based vector search after {max_retries} attempts: {str(last_exception)}")
    
    def delete_documents(
        self, 
        collection: Collection,
        ids: Optional[List[str]] = None,
        filter_condition: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> Dict[str, Any]:
        """
        Delete documents from a collection.
        Updated to handle API parameter differences.
        
        Args:
            collection: AstraDB collection instance
            ids: List of document IDs to delete
            filter_condition: Filter condition to select documents for deletion
            max_retries: Maximum number of deletion attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            dict: Result of the delete operation
            
        Raises:
            RAGException: If delete operation fails after all retries
        """
        if ids is None and filter_condition is None:
            raise ValueError("Either ids or filter_condition must be provided")
                
        last_exception = None
        
        for attempt in range(1, max_retries + 1):
            try:
                if ids is not None:
                    # Try different parameter names for id-based deletion
                    try:
                        # First try the 'ids' parameter (plural)
                        result = collection.delete_many(ids=ids)
                    except TypeError:
                        try:
                            # Then try 'id' parameter (singular, but with list)
                            result = collection.delete_many(id=ids)
                        except TypeError:
                            # Fallback to iterative deletion
                            class DeleteResult:
                                def __init__(self):
                                    self.deleted_count = 0
                                    
                            result = DeleteResult()
                            for doc_id in ids:
                                try:
                                    # Try with 'id' parameter (singular)
                                    collection.delete_one(id=doc_id)
                                    result.deleted_count += 1
                                except TypeError:
                                    # Last resort: try with '_id' parameter
                                    collection.delete_one(_id=doc_id)
                                    result.deleted_count += 1
                    
                    logger.info(f"Deleted {result.deleted_count} documents by ID from {collection.full_name}")
                    return result
                else:  # filter_condition is not None
                    try:
                        result = collection.delete_many(filter=filter_condition)
                    except TypeError:
                        # Try alternate parameter name
                        result = collection.delete_many(query=filter_condition)
                        
                    logger.info(f"Deleted {result.deleted_count} documents by filter from {collection.full_name}")
                    return result
                    
            except Exception as e:
                last_exception = e
                logger.warning(f"Document deletion attempt {attempt}/{max_retries} failed: {str(e)}")
                if attempt < max_retries:
                    wait_time = retry_delay * attempt
                    logger.info(f"Retrying document deletion in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error deleting documents after {max_retries} attempts: {str(e)}")
        
        raise RAGException(f"Failed to delete documents after {max_retries} attempts: {str(last_exception)}")
    
    def count_documents(
        self,
        collection: Collection,
        filter_condition: Optional[Dict[str, Any]] = None,
        upper_bound: int = 1000000,
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> int:
        """
        Count documents in a collection with retry logic.
        
        Args:
            collection: AstraDB collection instance
            filter_condition: Optional filter condition
            upper_bound: Maximum number of documents to count (required by AstraDB)
            max_retries: Maximum number of count attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            int: Number of documents
            
        Raises:
            RAGException: If count operation fails after all retries
        """
        last_exception = None
        
        for attempt in range(1, max_retries + 1):
            try:
                count = collection.count_documents(
                    filter=filter_condition,
                    upper_bound=upper_bound
                )
                return count
            except Exception as e:
                last_exception = e
                logger.warning(f"Document count attempt {attempt}/{max_retries} failed: {str(e)}")
                if attempt < max_retries:
                    wait_time = retry_delay * attempt
                    logger.info(f"Retrying document count in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error counting documents after {max_retries} attempts: {str(e)}")
        
        raise RAGException(f"Failed to count documents after {max_retries} attempts: {str(last_exception)}")
    
    def find_documents(
        self,
        collection: Collection,
        filter_condition: Dict[str, Any],
        limit: int = 100,
        skip: int = 0,
        sort: Optional[List[Dict[str, int]]] = None,
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Find documents in a collection using a filter.
        Added retry logic for more robust querying.
        
        Args:
            collection: AstraDB collection instance
            filter_condition: Filter condition to select documents
            limit: Maximum number of documents to return
            skip: Number of documents to skip
            sort: Sort criteria
            max_retries: Maximum number of find attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            list: Documents matching the filter
            
        Raises:
            RAGException: If find operation fails after all retries
        """
        last_exception = None
        
        for attempt in range(1, max_retries + 1):
            try:
                results = collection.find(
                    filter=filter_condition,
                    options={
                        "limit": limit,
                        "skip": skip,
                        "sort": sort
                    }
                )
                return results
            except Exception as e:
                last_exception = e
                logger.warning(f"Document find attempt {attempt}/{max_retries} failed: {str(e)}")
                if attempt < max_retries:
                    wait_time = retry_delay * attempt
                    logger.info(f"Retrying document find in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error finding documents after {max_retries} attempts: {str(e)}")
        
        raise RAGException(f"Failed to find documents after {max_retries} attempts: {str(last_exception)}")
    
    def update_document(
        self,
        collection: Collection,
        document_id: str,
        update: Dict[str, Any],
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> Dict[str, Any]:
        """
        Update a document in a collection.
        Added retry logic for more robust updating.
        
        Args:
            collection: AstraDB collection instance
            document_id: ID of the document to update
            update: Update to apply to the document
            max_retries: Maximum number of update attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            dict: Result of the update operation
            
        Raises:
            RAGException: If update operation fails after all retries
        """
        last_exception = None
        
        for attempt in range(1, max_retries + 1):
            try:
                result = collection.update_one(
                    id=document_id,
                    update=update
                )
                return result
            except Exception as e:
                last_exception = e
                logger.warning(f"Document update attempt {attempt}/{max_retries} failed: {str(e)}")
                if attempt < max_retries:
                    wait_time = retry_delay * attempt
                    logger.info(f"Retrying document update in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error updating document after {max_retries} attempts: {str(e)}")
        
        raise RAGException(f"Failed to update document after {max_retries} attempts: {str(last_exception)}")
    
    def get_document_by_id(
        self,
        collection: Collection,
        document_id: str,
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> Optional[Dict[str, Any]]:
        """
        Get a document by its ID.
        Updated to handle API parameter differences.
        
        Args:
            collection: AstraDB collection instance
            document_id: ID of the document to get
            max_retries: Maximum number of get attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            dict: Document if found, None otherwise
            
        Raises:
            RAGException: If get operation fails after all retries
        """
        last_exception = None
        
        for attempt in range(1, max_retries + 1):
            try:
                # Try different parameter names for compatibility
                try:
                    # First try with 'id' parameter
                    result = collection.find_one(id=document_id)
                except TypeError:
                    # Then try with '_id' parameter
                    result = collection.find_one(_id=document_id)
                    
                return result
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Document get attempt {attempt}/{max_retries} failed: {str(e)}")
                if attempt < max_retries:
                    wait_time = retry_delay * attempt
                    logger.info(f"Retrying document get in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error getting document after {max_retries} attempts: {str(e)}")
        
        raise RAGException(f"Failed to get document after {max_retries} attempts: {str(last_exception)}")