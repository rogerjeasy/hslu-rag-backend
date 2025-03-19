# scripts/query_astra_db.py
import asyncio
import argparse
import logging
import os
import json
from typing import Dict, Any, List

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.embedding_service import AstraDocumentService

async def query_collection(query: str, limit: int, collection_name: str, course_id: str = None) -> None:
    """Query the AstraDB collection for similar documents."""
    astra_service = AstraDocumentService()
    
    # Prepare filter if course_id is provided
    filter_condition = None
    if course_id:
        filter_condition = {"metadata.course_id": course_id}
    
    try:
        logger.info(f"Querying collection '{collection_name}' with: {query}")
        
        results = await astra_service.search_similar_documents(
            query=query,
            limit=limit,
            collection_name=collection_name,
            filter_condition=filter_condition
        )
        
        logger.info(f"Found {len(results)} results")
        
        # Display results
        for i, result in enumerate(results):
            print(f"\n--- Result {i+1} (Similarity: {result['score']:.4f}) ---")
            print(f"ID: {result['id']}")
            
            # Print metadata
            metadata = result.get('metadata', {})
            if metadata:
                print("\nMetadata:")
                for key, value in metadata.items():
                    print(f"  {key}: {value}")
            
            # Print content (first 200 chars)
            content = result.get('content', '')
            if content:
                print("\nContent Preview:")
                print(f"  {content[:200]}..." if len(content) > 200 else content)
            
            print("-" * 50)
        
    except Exception as e:
        logger.error(f"Error querying database: {str(e)}")

async def main():
    """Main function for script execution."""
    parser = argparse.ArgumentParser(description='Query AstraDB collection')
    parser.add_argument('--query', type=str, required=True, help='Query text')
    parser.add_argument('--limit', type=int, default=5, help='Maximum number of results (default: 5)')
    parser.add_argument('--collection', type=str, default='hslu_rag_data', 
                       help='Collection name (default: hslu_rag_data)')
    parser.add_argument('--course', type=str, help='Filter by course ID')
    
    args = parser.parse_args()
    
    await query_collection(args.query, args.limit, args.collection, args.course)

if __name__ == "__main__":
    asyncio.run(main())