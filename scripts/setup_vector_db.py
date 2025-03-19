#!/usr/bin/env python
"""
Setup and initialize the vector database for the HSLU RAG application.
This script creates the necessary collection in ChromaDB and configures it properly.
"""
import os
import sys
import argparse
import logging
from pathlib import Path

# Add the parent directory to sys.path to import app modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

import chromadb
from chromadb.config import Settings

from app.core.config import settings
from app.core.exceptions import RAGException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def setup_chroma(persist_directory=None, recreate=False):
    """
    Set up the ChromaDB vector database.
    
    Args:
        persist_directory: Directory to persist ChromaDB data (default to settings or env var)
        recreate: Whether to recreate the collection if it exists
    """
    try:
        # Get persist directory from args, settings, or environment variable
        persist_dir = persist_directory or os.environ.get("CHROMA_PERSIST_DIR") or "./chroma_db"
        
        logger.info(f"Setting up ChromaDB with persistence directory: {persist_dir}")
        
        # Create directory if it doesn't exist
        os.makedirs(persist_dir, exist_ok=True)
        
        # Initialize ChromaDB client
        client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )
        
        # Get existing collections
        collections = client.list_collections()
        collection_names = [col.name for col in collections]
        
        # Check if collection exists
        if "course_materials" in collection_names:
            if recreate:
                logger.warning("Recreating 'course_materials' collection (this will delete all existing data)")
                client.delete_collection("course_materials")
                collection = client.create_collection(
                    name="course_materials",
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info("Collection 'course_materials' recreated successfully")
            else:
                logger.info("Collection 'course_materials' already exists, skipping creation")
                collection = client.get_collection("course_materials")
        else:
            # Create new collection
            collection = client.create_collection(
                name="course_materials",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Collection 'course_materials' created successfully")
        
        # Log collection info
        logger.info(f"Collection count: {collection.count()}")
        
        return collection
        
    except Exception as e:
        logger.error(f"Error setting up ChromaDB: {str(e)}")
        raise RAGException(f"Failed to set up ChromaDB: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description="Set up and initialize the vector database")
    parser.add_argument(
        "--persist-dir", 
        type=str, 
        help="Directory to persist ChromaDB data"
    )
    parser.add_argument(
        "--recreate", 
        action="store_true",
        help="Recreate collections if they exist (WARNING: this will delete all existing data)"
    )
    args = parser.parse_args()
    
    try:
        setup_chroma(args.persist_dir, args.recreate)
        logger.info("Vector database setup completed successfully")
    except Exception as e:
        logger.error(f"Vector database setup failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()