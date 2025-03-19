#!/usr/bin/env python
"""
Generate embeddings for existing document chunks and store them in the vector database.
This script is useful for regenerating embeddings when changing embedding models.
"""
import os
import sys
import argparse
import logging
import json
from pathlib import Path
from tqdm import tqdm
import asyncio

# Add the parent directory to sys.path to import app modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.exceptions import RAGException
from app.rag.embeddings import EmbeddingGenerator
from app.rag.retriever import Retriever
from scripts.setup_vector_db import setup_chroma

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def load_chunks_from_file(file_path):
    """
    Load document chunks from a JSON file.
    
    Args:
        file_path: Path to the JSON file containing document chunks
        
    Returns:
        List of document chunks
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
            logger.info(f"Loaded {len(chunks)} chunks from {file_path}")
            return chunks
    except Exception as e:
        logger.error(f"Error loading chunks from {file_path}: {str(e)}")
        raise RAGException(f"Failed to load chunks from {file_path}: {str(e)}")


async def generate_and_store_embeddings(chunks, batch_size=10):
    """
    Generate embeddings for document chunks and store them in the vector database.
    
    Args:
        chunks: List of document chunks
        batch_size: Number of chunks to process in each batch
    """
    try:
        embedding_generator = EmbeddingGenerator()
        retriever = Retriever()
        
        # Process in batches to avoid memory issues and rate limits
        total_batches = (len(chunks) + batch_size - 1) // batch_size
        
        with tqdm(total=len(chunks), desc="Generating embeddings") as pbar:
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i+batch_size]
                
                # Generate embeddings and store in vector database
                await retriever.add_chunks(batch)
                
                pbar.update(len(batch))
                
        logger.info(f"Successfully generated and stored embeddings for {len(chunks)} chunks")
                
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        raise RAGException(f"Failed to generate embeddings: {str(e)}")


async def create_embeddings_from_firestore():
    """
    Load document chunks from Firestore and generate embeddings.
    This is useful when chunks are already stored in Firestore but 
    need to be added to the vector database.
    """
    try:
        from app.core.firebase import firebase
        
        logger.info("Loading document chunks from Firestore...")
        
        # Get Firestore client
        db = firebase.get_firestore()
        
        # Get document chunks collection
        chunks_ref = db.collection("document_chunks")
        chunks_docs = chunks_ref.stream()
        
        # Convert to list of chunks
        chunks = []
        for doc in chunks_docs:
            chunk_data = doc.to_dict()
            chunk_data["id"] = doc.id
            chunks.append(chunk_data)
        
        logger.info(f"Loaded {len(chunks)} chunks from Firestore")
        
        if not chunks:
            logger.warning("No chunks found in Firestore")
            return
        
        # Generate and store embeddings
        await generate_and_store_embeddings(chunks)
        
    except Exception as e:
        logger.error(f"Error creating embeddings from Firestore: {str(e)}")
        raise RAGException(f"Failed to create embeddings from Firestore: {str(e)}")


async def main_async():
    parser = argparse.ArgumentParser(description="Generate embeddings for document chunks")
    parser.add_argument(
        "--file", 
        type=str, 
        help="Path to JSON file containing document chunks"
    )
    parser.add_argument(
        "--firestore", 
        action="store_true",
        help="Load document chunks from Firestore"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=10,
        help="Number of chunks to process in each batch"
    )
    parser.add_argument(
        "--setup-db", 
        action="store_true",
        help="Set up the vector database before generating embeddings"
    )
    args = parser.parse_args()
    
    try:
        # Set up the vector database if requested
        if args.setup_db:
            setup_chroma()
        
        if args.file:
            # Load chunks from file
            chunks = await load_chunks_from_file(args.file)
            await generate_and_store_embeddings(chunks, args.batch_size)
        elif args.firestore:
            # Load chunks from Firestore
            await create_embeddings_from_firestore()
        else:
            logger.error("Must specify either --file or --firestore")
            sys.exit(1)
            
        logger.info("Embedding generation completed successfully")
        
    except Exception as e:
        logger.error(f"Embedding generation failed: {str(e)}")
        sys.exit(1)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()