import logging
from fastapi import APIRouter, Depends, HTTPException, Body, status
from typing import Dict, Any, List, Optional
from app.schemas.conversation import (
    Conversation, ConversationSummary, Message,
    ConversationCreateRequest, ConversationUpdateRequest, MessageCreateRequest
)
from app.dto.conversation_dto import (
    FrontendConversationDTO, BackendConversationDTO
)
from app.services.firestore_service import FirestoreService
from app.services.rag_service import RAGService
from app.services.retrieval_service import RetrievalService
from app.services.generation_service import GenerationService
from app.schemas.query import QueryRequest, QueryType
from app.core.security import get_current_user
from app.schemas.auth import UserResponse
from datetime import datetime
from app.core.firebase import firebase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])

# Initialize services
retrieval_service = RetrievalService()
generation_service = GenerationService()
firestore_service = FirestoreService(firebase.get_firestore())
rag_service = RAGService(
    retrieval_service=retrieval_service,
    generation_service=generation_service,
    firestore_service=firestore_service
)

@router.post("/", response_model=Dict[str, Any])
async def create_conversation(
    data: Dict[str, Any] = Body(...),
    current_user: UserResponse = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new conversation"""
    try:
        # Convert frontend data to backend request
        conversation_request = FrontendConversationDTO.to_create_request(data)
        
        # Create conversation in Firestore
        conversation = await firestore_service.create_conversation(
            user_id=current_user.id,
            course_id=conversation_request.course_id,
            data={
                "title": conversation_request.title,
                "module_id": conversation_request.module_id,
                "topic_id": conversation_request.topic_id,
                "initial_message": conversation_request.initial_message
            }
        )
        
        # If there's an initial message, process it with RAG
        if conversation_request.initial_message:
            # Create query request
            query_request = QueryRequest(
                text=conversation_request.initial_message,
                course_id=conversation_request.course_id,
                module_id=conversation_request.module_id,
                topic_id=conversation_request.topic_id,
                conversation_id=conversation["id"],
                query_type=QueryType.QUESTION_ANSWERING
            )
            
            # Process the query
            ai_response = await rag_service.process_query(
                query_request=query_request,
                user_id=current_user.id
            )
        
        # Convert to frontend format and return
        return BackendConversationDTO.conversation_to_frontend(conversation)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating conversation: {str(e)}"
        )

@router.get("/", response_model=List[Dict[str, Any]])
async def get_conversations(
    course_id: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Get list of user conversations"""
    try:
        conversations = await firestore_service.get_user_conversations(
            user_id=current_user.id,
            course_id=course_id
        )
                
        # Convert to frontend format
        result = []
        for conversation in conversations:
            try:
                result.append(BackendConversationDTO.summary_to_frontend(conversation))
            except Exception as e:
                print(f"Error converting conversation: {str(e)}")
                # Skip this conversation or handle appropriately

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving conversations: {str(e)}"
        )

@router.get("/{conversation_id}", response_model=Dict[str, Any])
async def get_conversation(
    conversation_id: str,
    current_user: UserResponse = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get a specific conversation with all messages"""
    try:
        conversation = await firestore_service.get_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id
        )
        
        # Convert to frontend format
        return BackendConversationDTO.conversation_to_frontend(conversation)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving conversation: {str(e)}"
        )

@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a conversation"""
    try:
        # First ensure the user has access to this conversation
        await firestore_service.get_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id
        )
        
        # Delete the conversation
        await firestore_service.delete_document(
            collection="conversations",
            document_id=conversation_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting conversation: {str(e)}"
        )

@router.put("/{conversation_id}", response_model=Dict[str, Any])
async def update_conversation(
    conversation_id: str,
    data: Dict[str, Any] = Body(...),
    current_user: UserResponse = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update conversation metadata"""
    try:
        # Convert frontend data to backend request
        conversation_update = FrontendConversationDTO.to_update_request(data)
        
        # First ensure the user has access to this conversation
        conversation = await firestore_service.get_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id
        )
        
        # Update only allowed fields
        update_data = {}
        if conversation_update.title is not None:
            update_data["title"] = conversation_update.title
        if conversation_update.active is not None:
            update_data["active"] = conversation_update.active
        
        # Update the document
        if update_data:
            await firestore_service.update_document(
                collection="conversations",
                document_id=conversation_id,
                data=update_data
            )
            
            # Update local copy for response
            conversation.update(update_data)
        
        # Convert to frontend format and return
        return BackendConversationDTO.conversation_to_frontend(conversation)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating conversation: {str(e)}"
        )

@router.post("/{conversation_id}/messages", response_model=Dict[str, Any])
async def add_message(
    conversation_id: str,
    data: Dict[str, Any] = Body(...),
    current_user: UserResponse = Depends(get_current_user)
) -> Dict[str, Any]:
    """Add a message to a conversation and get AI response"""
    try:
        # Convert frontend data to backend request
        message_request = FrontendConversationDTO.to_message_create_request(data)
        
        # First ensure the user has access to this conversation
        conversation = await firestore_service.get_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id
        )
        
        # Add user message to conversation
        user_message = await firestore_service.add_message_to_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id,
            message_data={
                "content": message_request.content,
                "role": "user",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # Create query request with original conversation context
        query_request = QueryRequest(
            text=message_request.content,
            course_id=conversation["course_id"],
            module_id=conversation.get("module_id"),
            topic_id=conversation.get("topic_id"),
            conversation_id=conversation_id,
            query_type=message_request.query_type,
            additional_params=message_request.additional_params
        )
        
        # Process the query - this will add the AI response to the conversation
        response = await rag_service.process_query(
            query_request=query_request,
            user_id=current_user.id
        )

        # Add the response to conversation
        ai_message = await firestore_service.add_message_to_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id,
            message_data={
                "content": response.get("response", ""),
                "role": "assistant",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "citations": response.get("citations", []),
                    "query_id": response.get("query_id")
                }
            }
        )
        
        # Get updated conversation
        updated_conversation = await firestore_service.get_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id
        )
        
        # Extract just the latest exchange
        messages = updated_conversation.get("messages", [])
        latest_exchange = messages[-2:] if len(messages) >= 2 else messages
        
        return {
            "conversation_id": conversation_id,
            "exchange": [
                BackendConversationDTO.message_to_frontend(message)
                for message in latest_exchange
            ],
            "citations": response.get("citations", [])
        }
    except Exception as e:
        logger.error(f"Error adding message: {str(e)}", exc_info=True)  # Add exc_info=True to get the stack trace
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding message: {str(e)}"
        )