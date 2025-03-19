# Example of using AstraDB in your application
import asyncio
from app.rag.document_processor import DocumentProcessor
from app.services.embedding_service import AstraDocumentService
from app.rag.retriever import Retriever
from app.rag.llm_connector import LLMConnector

async def process_and_store_documents():
    """Process and store documents in AstraDB."""
    # Initialize services
    doc_processor = DocumentProcessor()
    astra_service = AstraDocumentService()
    
    # Process a PDF file
    with open("document_files/Exercise-03.pdf", "rb") as f:
        file_content = f.read()
    
    # Process document
    metadata = {
        "course_id": "ds101",
        "course_name": "Introduction to Data Science",
        "source_type": "lecture"
    }
    
    # Extract and chunk document
    astra_chunks, doc_metadata = await doc_processor.process_document_for_astra(
        file_content, "Exercise-03.pdf", metadata
    )
    
    # Store in AstraDB
    chunk_ids = await astra_service.process_and_store_documents(astra_chunks)
    print(f"Stored {len(chunk_ids)} chunks in AstraDB")

async def query_and_generate_response():
    """Query AstraDB and generate a response using RAG."""
    # Initialize components
    retriever = Retriever()
    llm_connector = LLMConnector()
    
    # User query
    query = "Explain the difference between supervised and unsupervised learning"
    
    # Optional filter by course
    course_id = "ds101"
    
    # Retrieve relevant chunks
    relevant_chunks = await retriever.retrieve(query, limit=5, course_id=course_id)
    
    # Generate response using retrieved context
    response = await llm_connector.generate_response(
        query=query,
        retrieved_chunks=relevant_chunks
    )
    
    print("Generated response:")
    print(response["content"])
    
    print("\nSources:")
    for source in response["sources"]:
        print(f"- {source['source']} ({source['course_name']})")

# Run the examples
if __name__ == "__main__":
    asyncio.run(process_and_store_documents())
    asyncio.run(query_and_generate_response())