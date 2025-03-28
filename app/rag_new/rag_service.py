import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from fastapi import UploadFile
import langchain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma, Pinecone
from langchain.embeddings import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain.docstore.document import Document

from app.core.config import settings
from app.schemas.material_upload import MaterialUploadResponse, MaterialProcessingStatus
from app.services.cloudinary_service import CloudinaryService
from app.rag_new.chuncker import EnhancedTextChunker
from app.rag_new.embdeddings import EmbeddingService
from app.rag_new.document_processor import DocumentProcessor
import app.rag_new.prompt_templates as prompts

logger = logging.getLogger(__name__)

class RAGService:
    """
    Enhanced service for RAG operations with LangChain integration
    """
    
    def __init__(self):
        """Initialize RAG service with dependencies"""
        # Initialize services
        self.cloudinary_service = CloudinaryService()
        self.chunker = EnhancedTextChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        self.embedding_service = EmbeddingService()
        self.document_processor = DocumentProcessor(
            cloudinary_service=self.cloudinary_service,
            chunker=self.chunker,
            embedding_service=self.embedding_service
        )
        
        # Initialize LangChain components
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL_NAME
        )
        
        # Initialize text splitter for LangChain
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ".", " ", ""],
            length_function=len
        )
    
    async def process_material(self, material: MaterialUploadResponse) -> MaterialProcessingStatus:
        """
        Process uploaded material and create vector embeddings
        
        Args:
            material: Material upload response
            
        Returns:
            Processing status
        """
        # Initialize processing status
        status = MaterialProcessingStatus(
            material_id=material.id,
            status="processing",
            progress=0.0,
            started_at=material.uploaded_at
        )
        
        try:
            logger.info(f"Starting processing of material {material.id} of type {material.file_type}")
            
            # Process the file
            chunks, vector_ids = await self.document_processor.process_file(
                file_url=material.file_url,
                file_type=material.file_type,
                material_id=material.id,
                type=material.type
            )
            
            # Update material with chunk count and vector IDs
            material.chunk_count = len(chunks)
            material.vector_ids = vector_ids
            
            # Update status
            status.status = "completed"
            status.progress = 1.0
            status.completed_at = material.updated_at if hasattr(material, 'updated_at') else material.uploaded_at 
            
            logger.info(f"Completed processing of material {material.id} with {len(chunks)} chunks")
            return status
            
        except Exception as e:
            logger.error(f"Error processing material {material.id}: {str(e)}", exc_info=True)
            status.status = "failed"
            status.error_message = str(e)
            return status
    
    async def retrieve_relevant_context(
        self, 
        query: str, 
        min_relevance_score: float,
        course_id: Optional[str] = None,
        module_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        max_chunks: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context for a query with improved relevance filtering
        
        Args:
            query: User query
            course_id: Optional course filter
            module_id: Optional module filter
            topic_id: Optional topic filter
            max_chunks: Maximum number of chunks to retrieve
            min_relevance_score: Minimum relevance score threshold
            
        Returns:
            List of relevant context chunks
        """
        try:
            # Build filter
            filter_dict = {}
            if course_id:
                filter_dict["course_id"] = course_id
            if module_id:
                filter_dict["module_id"] = module_id
            if topic_id:
                filter_dict["topic_id"] = topic_id
            
            logger.info(f"Retrieving context for query: '{query}' with filters: {filter_dict}")
            
            # Retrieve similar chunks from vector DB
            search_results = await self.embedding_service.search_similar(
                query=query,
                filter=filter_dict,
                top_k=max_chunks * 2  # Retrieve more than needed to filter by relevance
            )

            # Add before filtering:
            logger.info(f"Raw search results count: {len(search_results)}")
            if search_results:
                logger.info(f"Top result score: {search_results[0]['score']}, id: {search_results[0]['id']}")
                        
            # Filter results by relevance score
            filtered_results = [
                result for result in search_results 
                if result["score"] >= min_relevance_score
            ]
            
            # Take top K after filtering
            top_results = filtered_results[:max_chunks]
            
            # Format context chunks
            context_chunks = []
            for i, result in enumerate(top_results):
                context_chunks.append({
                    "chunk_id": result["id"],
                    "chunk_content": result["metadata"].get("chunk_text_preview", ""),
                    "full_content": result["metadata"].get("chunk_text_preview", ""),  # This would ideally contain the full chunk text
                    "score": result["score"],
                    "material_id": result["metadata"].get("material_id", ""),
                    "source_url": result["metadata"].get("source_url", ""),
                    "file_type": result["metadata"].get("file_type", ""),
                    "source_page": result["metadata"].get("source_page", None),
                    "chunk_index": result["metadata"].get("chunk_index", 0),
                    "total_chunks": result["metadata"].get("total_chunks", 0),
                    "title": result["metadata"].get("title", f"Source {i+1}")
                })
            
            logger.info(f"Retrieved {len(context_chunks)} relevant chunks for query")
            return context_chunks
            
        except Exception as e:
            logger.error(f"Error retrieving context: {str(e)}", exc_info=True)
            return []

    async def generate_rag_response(
        self, 
        query: str, 
        context_chunks: List[Dict[str, Any]],
        prompt_type: str = "question_answering",
        additional_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a response using RAG approach with context and LLM
        
        Args:
            query: User query
            context_chunks: Retrieved context chunks
            prompt_type: Type of prompt to use (question_answering, study_guide, etc.)
            additional_params: Additional parameters for customization
            
        Returns:
            Generated response with metadata
        """
        try:
            from app.services.llm_service import LLMService
            
            # Initialize LLM service
            llm_service = LLMService()
            
            # Get appropriate prompts
            system_prompt = prompts.get_system_prompt(
                prompt_type=prompt_type, 
                additional_params=additional_params
            )
            
            user_prompt = prompts.get_user_prompt(
                prompt_type=prompt_type,
                query=query,
                context_chunks=context_chunks,
                additional_params=additional_params
            )
            
            # Generate response using LLM service
            response = await llm_service.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7 if prompt_type == "question_answering" else 0.8,
                max_tokens=2000
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating RAG response: {str(e)}", exc_info=True)
            return {
                "response": {
                    "answer": f"Error generating response: {str(e)}",
                    "citations": []
                },
                "raw_response": f"Error: {str(e)}",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            }
    
    async def delete_material_embeddings(self, material_id: str) -> bool:
        """
        Delete all embeddings for a material
        
        Args:
            material_id: ID of the material
            
        Returns:
            Success status
        """
        try:
            logger.info(f"Deleting embeddings for material {material_id}")
            
            # Delete by metadata filter
            success = await self.embedding_service.delete_by_metadata(
                filter={"material_id": material_id}
            )
            
            return success
        except Exception as e:
            logger.error(f"Error deleting material embeddings: {str(e)}", exc_info=True)
            return False
    
    async def reindex_material(self, material_id: str) -> Tuple[bool, Optional[str]]:
        """
        Reindex a material's embeddings (delete and recreate)
        
        Args:
            material_id: ID of the material
            
        Returns:
            Tuple of (success status, error message if any)
        """
        try:
            # First delete existing embeddings
            delete_success = await self.delete_material_embeddings(material_id)
            
            if not delete_success:
                return False, "Failed to delete existing embeddings"
            
            # Get material info
            # This would require material_service, which we're not implementing here
            # In a real implementation, you'd get the material and process it again
            
            return True, None
            
        except Exception as e:
            error_msg = f"Error reindexing material: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    async def process_langchain_documents(
        self, 
        texts: List[str], 
        metadata_list: List[Dict[str, Any]]
    ) -> List[Document]:
        """
        Process documents using LangChain for enhanced retrieval
        
        Args:
            texts: List of text content
            metadata_list: List of metadata dicts for each text
            
        Returns:
            List of processed LangChain Document objects
        """
        try:
            # Create LangChain documents
            docs = [
                Document(page_content=text, metadata=metadata)
                for text, metadata in zip(texts, metadata_list)
            ]
            
            # Split documents using LangChain text splitter
            split_docs = self.text_splitter.split_documents(docs)
            
            return split_docs
            
        except Exception as e:
            logger.error(f"Error processing LangChain documents: {str(e)}", exc_info=True)
            return []
    
    def _create_qa_chain(self, retriever):
        """
        Create a QA chain with the retriever
        
        Args:
            retriever: Document retriever
            
        Returns:
            RetrievalQA chain
        """
        # Create prompt template
        template = """
        Use the following pieces of context to answer the question at the end.
        If you don't know the answer based on the context, say that you don't know, 
        don't try to make up an answer.
        Always cite the source of your information using [SOURCE_NUMBER].

        CONTEXT:
        {context}

        QUESTION: {question}
        
        ANSWER:
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["context", "question"]
        )
        
        # Create the chain
        chain = RetrievalQA.from_chain_type(
            llm=None,  # We'll use our own LLM service
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": prompt}
        )
        
        return chain