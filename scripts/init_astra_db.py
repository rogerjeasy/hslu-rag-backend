import asyncio
import argparse
import logging
import os
import json
import time
import uuid
from typing import Dict, Any, List, Optional

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.embedding_service import AstraDocumentService
from app.utils.astra_db_manager import AstraDBManager
from astrapy import Collection

async def verify_collection(collection: Collection) -> bool:
    """
    Verify that a collection is working properly by inserting and retrieving a test document.
    
    Args:
        collection: AstraDB collection instance
        
    Returns:
        bool: True if the collection is working, False otherwise
    """
    test_doc_id = f"test_verification_{uuid.uuid4()}"
    
    try:
        # Create test document
        test_doc = {
            "_id": test_doc_id,
            "content": "This is a test document for verification",
            "metadata": {"test": True},
            "$vectorize": "Test document for collection verification"
        }
        
        # Insert test document
        logger.info(f"Inserting test document with ID {test_doc_id}")
        result = collection.insert_one(test_doc)
        
        # Small delay to ensure document is indexed
        time.sleep(2)
        
        # Try to retrieve the test document
        retrieved = collection.find_one(id=test_doc_id)
        if retrieved and retrieved.get("_id") == test_doc_id:
            logger.info(f"Successfully retrieved test document")
            
            # Clean up
            collection.delete_one(id=test_doc_id)
            return True
        else:
            logger.warning(f"Could not retrieve the test document")
            return False
            
    except Exception as e:
        logger.warning(f"Verification failed: {str(e)}")
        return False

async def init_collection(collection_name: str) -> Optional[Collection]:
    """
    Initialize the AstraDB collection with a more robust approach.
    This function prioritizes verification over counting.
    
    Args:
        collection_name: Name of the collection to initialize
        
    Returns:
        Optional[Collection]: The initialized collection if successful, None otherwise
    """
    # Create a dedicated AstraDBManager for initialization
    astra_manager = AstraDBManager()
    
    logger.info(f"Initializing collection '{collection_name}'")
    
    # Connect to AstraDB
    db = astra_manager.connect()
    
    # Parameters for robust creation
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Attempt {attempt}/{max_retries} to initialize collection")
            
            # Try to get or create the collection with our improved method
            collection = astra_manager.get_or_create_collection(
                collection_name=collection_name,
                max_retries=2,  # Inner retry count
                retry_delay=3   # Inner retry delay
            )
            
            # Verify the collection is working properly
            logger.info(f"Verifying collection functionality...")
            if await verify_collection(collection):
                logger.info(f"Collection '{collection_name}' successfully initialized and verified")
                return collection
            else:
                # If verification fails but we have more retries, continue
                if attempt < max_retries:
                    wait_time = retry_delay * attempt
                    logger.warning(f"Collection verification failed. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Collection verification failed after {attempt} attempts")
                    return None
        
        except Exception as e:
            logger.error(f"Error during collection initialization (attempt {attempt}): {str(e)}")
            if attempt < max_retries:
                wait_time = retry_delay * attempt
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to initialize collection after {max_retries} attempts")
                return None
    
    return None

async def load_data_from_json(file_path: str, collection_name: str) -> None:
    """
    Load data from a JSON file into the AstraDB collection.
    
    Args:
        file_path: Path to the JSON file
        collection_name: Name of the collection to load data into
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return
       
    astra_service = AstraDocumentService()
   
    try:
        # Load JSON data
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
           
        if not isinstance(data, list):
            logger.error(f"JSON file should contain a list of documents")
            return
           
        logger.info(f"Loading {len(data)} documents into collection '{collection_name}'")
        
        # First make sure the collection exists and is ready
        collection = await init_collection(collection_name)
        if not collection:
            logger.error(f"Could not initialize collection '{collection_name}'. Cannot load data.")
            return
        
        # Prepare the documents - add IDs if missing
        for doc in data:
            if "_id" not in doc:
                doc["_id"] = str(uuid.uuid4())

        # Process in smaller batches to avoid issues
        batch_size = 10
        all_inserted_ids = []
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} of {(len(data) + batch_size - 1) // batch_size}")
            
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    # Process and store documents
                    inserted_ids = await astra_service.process_and_store_documents(
                        documents=batch,
                        collection_name=collection_name
                    )
                    
                    all_inserted_ids.extend(inserted_ids)
                    logger.info(f"Batch inserted successfully with {len(inserted_ids)} documents")
                    
                    # Small delay between batches
                    time.sleep(1)
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    retry_count += 1
                    logger.warning(f"Error processing batch (attempt {retry_count}/{max_retries}): {str(e)}")
                    if retry_count < max_retries:
                        wait_time = 5 * retry_count
                        logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Failed to process batch after {max_retries} attempts")
                        # Continue with next batch
       
        logger.info(f"Successfully inserted {len(all_inserted_ids)} documents in total")
       
    except Exception as e:
        logger.error(f"Error loading data: {str(e)}")
        logger.error(f"Error details: {repr(e)}")

async def main():
    """Main function for script execution."""
    parser = argparse.ArgumentParser(description='Initialize and populate AstraDB collection')
    parser.add_argument('--init', action='store_true', help='Initialize collection')
    parser.add_argument('--load', type=str, help='Load data from JSON file')
    parser.add_argument('--collection', type=str, default='hslu_rag_data',
                       help='Collection name (default: hslu_rag_data)')
    parser.add_argument('--force-recreate', action='store_true', 
                        help='Force recreation of collection if it exists')
   
    args = parser.parse_args()
   
    if args.init:
        collection = await init_collection(args.collection)
        if collection:
            logger.info(f"Collection '{args.collection}' initialized successfully")
        else:
            logger.error(f"Failed to initialize collection")
            return 1
       
    if args.load:
        if not os.path.exists(args.load):
            logger.error(f"File not found: {args.load}")
            return 1
            
        await load_data_from_json(args.load, args.collection)
       
    if not args.init and not args.load:
        logger.error("No action specified. Use --init to initialize or --load to load data.")
        return 1
        
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        sys.exit(1)