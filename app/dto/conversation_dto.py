from typing import Dict, Any, List, Optional
from datetime import datetime
from app.schemas.conversation import (
    Conversation, ConversationSummary, Message, 
    ConversationCreateRequest, ConversationUpdateRequest,
    MessageCreateRequest
)


class FrontendConversationDTO:
    """DTO for converting frontend conversation data to backend schemas"""
    
    @staticmethod
    def to_create_request(data: Dict[str, Any]) -> ConversationCreateRequest:
        """Convert frontend data to ConversationCreateRequest"""
        return ConversationCreateRequest(
            title=data.get("title", "New Conversation"),
            course_id=data.get("courseId", ""),
            module_id=data.get("moduleId"),
            topic_id=data.get("topicId"),
            initial_message=data.get("initialMessage")
        )
    
    @staticmethod
    def to_update_request(data: Dict[str, Any]) -> ConversationUpdateRequest:
        """Convert frontend data to ConversationUpdateRequest"""
        return ConversationUpdateRequest(
            title=data.get("title"),
            active=data.get("active")
        )
    
    @staticmethod
    def to_message_create_request(data: Dict[str, Any]) -> MessageCreateRequest:
        """Convert frontend data to MessageCreateRequest"""
        return MessageCreateRequest(
            content=data.get("content", ""),
            query_type=data.get("queryType", "question_answering"),
            additional_params=data.get("additionalParams")
        )


class BackendConversationDTO:
    """DTO for converting backend conversation schemas to frontend format"""
    
    @staticmethod
    def conversation_to_frontend(conversation: Conversation) -> Dict[str, Any]:
        """Convert backend Conversation to frontend format"""
        return {
            "id": conversation.id,
            "title": conversation.title,
            "courseId": conversation.course_id,
            "moduleId": conversation.module_id,
            "topicId": conversation.topic_id,
            "createdAt": conversation.created_at.isoformat(),
            "updatedAt": conversation.updated_at.isoformat(),
            "messages": [
                BackendConversationDTO.message_to_frontend(message)
                for message in conversation.messages
            ],
            "active": conversation.active
        }
    
    @staticmethod
    def summary_to_frontend(summary: ConversationSummary) -> Dict[str, Any]:
        """Convert backend ConversationSummary to frontend format"""
        return {
            "id": summary.id,
            "title": summary.title,
            "courseId": summary.course_id,
            "moduleId": summary.module_id,
            "topicId": summary.topic_id,
            "createdAt": summary.created_at.isoformat(),
            "updatedAt": summary.updated_at.isoformat(),
            "messageCount": summary.message_count,
            "lastMessagePreview": summary.last_message_preview,
            "active": summary.active
        }
    
    @staticmethod
    def message_to_frontend(message: Message) -> Dict[str, Any]:
        """Convert backend Message to frontend format"""
        return {
            "id": message.id,
            "content": message.content,
            "role": message.role,
            "timestamp": message.timestamp.isoformat(),
            "metadata": message.metadata
        }