# app/api/routes/conversations.py
import asyncio
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query, Body
from pydantic import BaseModel
from functools import partial

from app.core.security import get_current_user_id
from app.services.conversation_service import ConversationService
from app.services.rag_manager import RAGManager
from app.schemas.rag_query import RAGQuery, RAGResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations")

# Initialize services
conversation_service = ConversationService()
rag_manager = RAGManager()

# Request/Response Models
class ConversationCreate(BaseModel):
    """Request model for creating a conversation"""
    title: Optional[str] = None
    course_id: Optional[str] = None
    module_id: Optional[str] = None
    topic_id: Optional[str] = None


class ConversationUpdate(BaseModel):
    """Request model for updating a conversation"""
    title: Optional[str] = None
    course_id: Optional[str] = None
    module_id: Optional[str] = None
    topic_id: Optional[str] = None


class MessageCreate(BaseModel):
    """Request model for adding a message to a conversation"""
    content: str
    role: str = "user"
    metadata: Optional[Dict[str, Any]] = None


class QueryMessage(BaseModel):
    """Request model for adding a query and generating a response"""
    query: str
    course_id: Optional[str] = None
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    prompt_type: str = "question_answering"
    additional_params: Optional[Dict[str, Any]] = None


class ConversationSummary(BaseModel):
    """Response model for conversation summary"""
    id: str
    title: str
    course_id: Optional[str] = None
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    message_count: int
    latest_message: Optional[str] = None
    created_at: int
    updated_at: int


class Message(BaseModel):
    """Model for a conversation message"""
    id: str
    role: str
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None


class Conversation(BaseModel):
    """Response model for a complete conversation"""
    id: str
    title: str
    user_id: str
    course_id: Optional[str] = None
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    messages: List[Message]
    created_at: int
    updated_at: int


class DeleteResponse(BaseModel):
    """Response model for delete operations"""
    success: bool
    message: str


@router.post("", response_model=Conversation)
async def create_conversation(
    request: ConversationCreate = Body(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Create a new conversation
    """
    try:
        conversation_id = await conversation_service.create_conversation(
            user_id=user_id,
            title=request.title,
            course_id=request.course_id,
            module_id=request.module_id,
            topic_id=request.topic_id
        )
        
        conversation = await conversation_service.get_conversation(conversation_id)
        return conversation
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating conversation: {str(e)}"
        )


async def run_in_executor(executor, func, *args, **kwargs):
    """Run a synchronous function in an executor."""
    loop = asyncio.get_event_loop()
    func_partial = partial(func, *args, **kwargs)
    return await loop.run_in_executor(executor, func_partial)

@router.get("", response_model=List[ConversationSummary])
async def list_user_conversations(
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id)
):
    """
    List conversations for the current user
    """
    try:
        # If you need to keep this async, you can use run_in_executor
        conversations = await run_in_executor(
            None, conversation_service.list_user_conversations, user_id, limit
        )
        return conversations
    except Exception as e:
        logger.error(f"Error listing conversations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing conversations: {str(e)}"
        )

@router.get("/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: str = Path(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Get a complete conversation by ID
    """
    try:
        conversation = await conversation_service.get_conversation(
            conversation_id=conversation_id,
            user_id=user_id
        )
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation not found or not accessible: {conversation_id}"
            )
        
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving conversation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving conversation: {str(e)}"
        )


@router.put("/{conversation_id}", response_model=Conversation)
async def update_conversation(
    conversation_id: str = Path(...),
    request: ConversationUpdate = Body(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Update conversation metadata
    """
    try:
        updated_conversation = await conversation_service.update_conversation_metadata(
            conversation_id=conversation_id,
            user_id=user_id,
            updates=request.dict(exclude_unset=True)
        )
        
        return updated_conversation
    except Exception as e:
        logger.error(f"Error updating conversation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating conversation: {str(e)}"
        )


@router.post("/{conversation_id}/messages", response_model=Message)
async def add_message(
    conversation_id: str = Path(...),
    message: MessageCreate = Body(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Add a message to a conversation
    """
    try:
        added_message = await conversation_service.add_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role=message.role,
            content=message.content,
            metadata=message.metadata
        )
        
        return added_message
    except Exception as e:
        logger.error(f"Error adding message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding message: {str(e)}"
        )


@router.post("/{conversation_id}/query", response_model=Dict[str, Any])
async def query_and_respond(
    conversation_id: str = Path(...),
    query_request: QueryMessage = Body(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Add a user query to the conversation and generate an assistant response
    """
    try:
        # Add the user query as a message
        user_message = await conversation_service.add_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role="user",
            content=query_request.query
        )
        
        # Create a RAG query
        rag_query = RAGQuery(
            query=query_request.query,
            course_id=query_request.course_id,
            module_id=query_request.module_id,
            topic_id=query_request.topic_id,
            user_id=user_id,
            prompt_type=query_request.prompt_type,
            additional_params=query_request.additional_params
        )
        
        # Process the query
        rag_response = await rag_manager.process_query(rag_query)
        
        # Add the response as a message
        assistant_message = await conversation_service.add_rag_response(
            conversation_id=conversation_id,
            user_id=user_id,
            rag_response=rag_response
        )
        
        # Return both messages and the RAG response
        return {
            "user_message": user_message,
            "assistant_message": assistant_message,
            "rag_response": rag_response
        }
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )


@router.delete("/{conversation_id}", response_model=DeleteResponse)
async def delete_conversation(
    conversation_id: str = Path(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Delete a conversation
    """
    try:
        success = await conversation_service.delete_conversation(
            conversation_id=conversation_id,
            user_id=user_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation not found or not accessible: {conversation_id}"
            )
        
        return DeleteResponse(
            success=True,
            message=f"Conversation {conversation_id} deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting conversation: {str(e)}"
        )


@router.delete("", response_model=DeleteResponse)
async def delete_all_user_conversations(
    user_id: str = Depends(get_current_user_id)
):
    """
    Delete all conversations for the current user
    """
    try:
        count = await conversation_service.delete_all_user_conversations(user_id)
        
        return DeleteResponse(
            success=True,
            message=f"Successfully deleted {count} conversations"
        )
    except Exception as e:
        logger.error(f"Error deleting all conversations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting all conversations: {str(e)}"
        )