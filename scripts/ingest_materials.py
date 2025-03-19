#!/usr/bin/env python
"""
Batch ingest course materials into the RAG system.
This script processes a directory of files, extracts content, creates chunks,
generates embeddings, and stores everything in Firestore and the vector database.
"""
import os
import sys
import argparse
import logging
import json
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from tqdm import tqdm

# Add the parent directory to sys.path to import app modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.exceptions import DocumentProcessingException, RAGException
from app.core.firebase import firebase
from app.rag.document_processor import DocumentProcessor
from app.rag.retriever import Retriever
from scripts.setup_vector_db import setup_chroma

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def process_directory(directory_path, course_id, module_id=None, topic_id=None, skip_existing=False):
    """
    Process all files in a directory and add them to the RAG system.
    
    Args:
        directory_path: Path to the directory containing files
        course_id: ID of the course these materials belong to
        module_id: Optional module ID
        topic_id: Optional topic ID
        skip_existing: Skip files that have already been processed
    """
    try:
        # Check if directory exists
        if not os.path.isdir(directory_path):
            raise ValueError(f"Directory not found: {directory_path}")
        
        # Get course information
        course_info = await get_course_info(course_id)
        
        logger.info(f"Processing directory: {directory_path} for course: {course_info.get('title', course_id)}")
        
        # Initialize document processor and vector database
        doc_processor = DocumentProcessor()
        retriever = Retriever()
        
        # Get list of files already processed
        processed_files = []
        if skip_existing:
            processed_files = await get_processed_files(course_id)
            logger.info(f"Found {len(processed_files)} already processed files")
        
        # Process each file in the directory
        total_chunks = 0
        processed_count = 0
        skipped_count = 0
        
        # Get all files in directory (recursive)
        all_files = []
        for root, _, files in os.walk(directory_path):
            for file in files:
                if file.startswith('.'):  # Skip hidden files
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, directory_path)
                all_files.append((file_path, rel_path))
        
        logger.info(f"Found {len(all_files)} files to process")
        
        # Process files with progress bar
        with tqdm(total=len(all_files), desc="Processing files") as pbar:
            for file_path, rel_path in all_files:
                try:
                    # Check if file should be skipped
                    if skip_existing and rel_path in processed_files:
                        logger.debug(f"Skipping already processed file: {rel_path}")
                        skipped_count += 1
                        pbar.update(1)
                        continue
                    
                    # Read file content
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                    
                    # Determine metadata
                    metadata = {
                        "course_id": course_id,
                        "course_name": course_info.get("title", ""),
                        "module_id": module_id,
                        "topic_id": topic_id,
                        "relative_path": rel_path,
                    }
                    
                    # Add module and topic names if available
                    if module_id and "modules" in course_info:
                        for module in course_info["modules"]:
                            if module["id"] == module_id:
                                metadata["module_name"] = module["title"]
                                if topic_id and "topics" in module:
                                    for topic in module["topics"]:
                                        if topic["id"] == topic_id:
                                            metadata["topic_name"] = topic["title"]
                                            break
                                break
                    
                    # Process document
                    chunks, doc_metadata = await doc_processor.process_document(
                        file_content=file_content,
                        filename=os.path.basename(file_path),
                        metadata=metadata
                    )
                    
                    # Skip if no chunks were created
                    if not chunks:
                        logger.warning(f"No chunks created for file: {rel_path}")
                        pbar.update(1)
                        continue
                    
                    # Add chunks to Firestore
                    await store_chunks_in_firestore(chunks, course_id, rel_path)
                    
                    # Add chunks to vector database
                    await retriever.add_chunks(chunks)
                    
                    # Create material record in Firestore
                    await store_material_info(
                        course_id=course_id,
                        filename=os.path.basename(file_path),
                        rel_path=rel_path,
                        metadata=doc_metadata,
                        module_id=module_id,
                        topic_id=topic_id,
                        chunk_count=len(chunks)
                    )
                    
                    total_chunks += len(chunks)
                    processed_count += 1
                    logger.debug(f"Processed file: {rel_path} - Created {len(chunks)} chunks")
                    
                except Exception as e:
                    logger.error(f"Error processing file {rel_path}: {str(e)}")
                
                pbar.update(1)
        
        logger.info(f"Batch ingestion complete:")
        logger.info(f"- Processed {processed_count} files")
        logger.info(f"- Skipped {skipped_count} files")
        logger.info(f"- Created {total_chunks} total chunks")
        
    except Exception as e:
        logger.error(f"Error processing directory: {str(e)}")
        raise RAGException(f"Failed to process directory: {str(e)}")


async def get_course_info(course_id):
    """
    Get course information from Firestore.
    
    Args:
        course_id: ID of the course
        
    Returns:
        Dictionary with course information
    """
    try:
        # Get Firestore client
        db = firebase.get_firestore()
        
        # Get course document
        course_doc = db.collection("courses").document(course_id).get()
        
        if not course_doc.exists:
            logger.warning(f"Course not found: {course_id}")
            return {"id": course_id}
        
        course_data = course_doc.to_dict()
        course_data["id"] = course_id
        
        return course_data
        
    except Exception as e:
        logger.error(f"Error getting course info: {str(e)}")
        return {"id": course_id}


async def get_processed_files(course_id):
    """
    Get list of files that have already been processed for this course.
    
    Args:
        course_id: ID of the course
        
    Returns:
        List of relative file paths that have been processed
    """
    try:
        # Get Firestore client
        db = firebase.get_firestore()
        
        # Query materials for this course
        materials_ref = db.collection("materials").where("course_id", "==", course_id)
        materials = materials_ref.stream()
        
        # Extract relative paths
        processed_files = []
        for material in materials:
            data = material.to_dict()
            if "relative_path" in data:
                processed_files.append(data["relative_path"])
        
        return processed_files
        
    except Exception as e:
        logger.error(f"Error getting processed files: {str(e)}")
        return []


async def store_chunks_in_firestore(chunks, course_id, rel_path):
    """
    Store document chunks in Firestore.
    
    Args:
        chunks: List of document chunks
        course_id: ID of the course
        rel_path: Relative path of the source file
    """
    try:
        # Get Firestore client
        db = firebase.get_firestore()
        
        # Prepare batch
        batch = db.batch()
        
        # Add each chunk to batch
        for chunk in chunks:
            chunk_ref = db.collection("document_chunks").document(chunk["id"])
            chunk_data = {
                "content": chunk["content"],
                "metadata": chunk["metadata"],
                "course_id": course_id,
                "source_file": rel_path,
                "created_at": datetime.utcnow().isoformat()
            }
            batch.set(chunk_ref, chunk_data)
        
        # Commit batch
        batch.commit()
        
    except Exception as e:
        logger.error(f"Error storing chunks in Firestore: {str(e)}")
        raise RAGException(f"Failed to store chunks in Firestore: {str(e)}")


async def store_material_info(course_id, filename, rel_path, metadata, module_id, topic_id, chunk_count):
    """
    Store material information in Firestore.
    
    Args:
        course_id: ID of the course
        filename: Name of the file
        rel_path: Relative path of the file
        metadata: Document metadata
        module_id: Optional module ID
        topic_id: Optional topic ID
        chunk_count: Number of chunks created
    """
    try:
        # Get Firestore client
        db = firebase.get_firestore()
        
        # Generate material ID
        material_id = str(uuid.uuid4())
        
        # Determine material type based on file extension
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.pdf']:
            material_type = "document"
        elif ext in ['.pptx', '.ppt']:
            material_type = "slides"
        elif ext in ['.ipynb', '.py', '.js', '.java', '.cpp', '.sql', '.r']:
            material_type = "code"
        else:
            material_type = "other"
        
        # Create material data
        material_data = {
            "id": material_id,
            "title": filename,
            "description": f"Extracted from {rel_path}",
            "type": material_type,
            "course_id": course_id,
            "module_id": module_id,
            "topic_id": topic_id,
            "relative_path": rel_path,
            "metadata": metadata,
            "chunk_count": chunk_count,
            "uploaded_at": datetime.utcnow().isoformat()
        }
        
        # Store in Firestore
        db.collection("materials").document(material_id).set(material_data)
        
    except Exception as e:
        logger.error(f"Error storing material info: {str(e)}")
        raise RAGException(f"Failed to store material info: {str(e)}")


async def main_async():
    parser = argparse.ArgumentParser(description="Batch ingest course materials")
    parser.add_argument(
        "--dir", 
        type=str, 
        required=True,
        help="Directory containing course materials"
    )
    parser.add_argument(
        "--course", 
        type=str, 
        required=True,
        help="Course ID these materials belong to"
    )
    parser.add_argument(
        "--module", 
        type=str, 
        help="Optional module ID"
    )
    parser.add_argument(
        "--topic", 
        type=str, 
        help="Optional topic ID"
    )
    parser.add_argument(
        "--setup-db", 
        action="store_true",
        help="Set up the vector database before processing"
    )
    parser.add_argument(
        "--skip-existing", 
        action="store_true",
        help="Skip files that have already been processed"
    )
    parser.add_argument(
        "--export-chunks",
        type=str,
        help="Export processed chunks to a JSON file"
    )
    args = parser.parse_args()
    
    try:
        # Set up the vector database if requested
        if args.setup_db:
            setup_chroma()
        
        # Process directory
        await process_directory(
            directory_path=args.dir,
            course_id=args.course,
            module_id=args.module,
            topic_id=args.topic,
            skip_existing=args.skip_existing
        )
        
        logger.info("Material ingestion completed successfully")
        
    except Exception as e:
        logger.error(f"Material ingestion failed: {str(e)}")
        sys.exit(1)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()