from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query as QueryParam
from typing import List, Optional

from app.core.security import get_current_user
from app.schemas.query import QueryCreate, QueryResponse, QueryHistory
from app.services.rag_service import RAGService

router = APIRouter(prefix="/queries", tags=["queries"])

rag_service = RAGService()

@router.post("/", response_model=QueryResponse)
async def create_query(
    query_data: QueryCreate,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user)
):
    """
    Submit a new query to the RAG system.
    
    This endpoint processes the user's query, retrieves relevant context from 
    the vector database, and generates a response using the LLM.
    
    The user's query history is saved in the background for learning analytics.
    """
    try:
        # Process the query through the RAG pipeline
        response = await rag_service.process_query(
            query=query_data.query,
            user_id=current_user["id"],
            course_id=query_data.course_id,
            conversation_id=query_data.conversation_id,
        )
        
        # Save query to history in the background
        background_tasks.add_task(
            rag_service.save_query_history,
            user_id=current_user["id"],
            query=query_data.query,
            response=response,
            course_id=query_data.course_id,
            conversation_id=query_data.conversation_id,
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}",
        )


@router.get("/history", response_model=List[QueryHistory])
async def get_query_history(
    limit: int = QueryParam(10, ge=1, le=100),
    offset: int = QueryParam(0, ge=0),
    course_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    """
    Get the user's query history.
    
    This endpoint retrieves the user's previous queries and responses,
    optionally filtered by course or conversation.
    """
    try:
        history = await rag_service.get_query_history(
            user_id=current_user["id"],
            limit=limit,
            offset=offset,
            course_id=course_id,
            conversation_id=conversation_id,
        )
        return history
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve query history: {str(e)}",
        )


@router.get("/conversations", response_model=List[str])
async def get_conversations(
    current_user=Depends(get_current_user)
):
    """
    Get all conversation IDs for the current user.
    """
    try:
        conversations = await rag_service.get_user_conversations(
            user_id=current_user["id"]
        )
        return conversations
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve conversations: {str(e)}",
        )


@router.delete("/history/{query_id}")
async def delete_query(
    query_id: str,
    current_user=Depends(get_current_user)
):
    """
    Delete a specific query from history.
    """
    try:
        await rag_service.delete_query(
            query_id=query_id,
            user_id=current_user["id"]
        )
        return {"detail": "Query deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete query: {str(e)}",
        )