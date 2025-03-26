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
    def conversation_to_frontend(conversation: Dict[str, Any]) -> Dict[str, Any]:
        """Convert dictionary conversation to frontend format"""
        # Format datetime objects if they exist
        created_at = conversation.get("created_at")
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()
            
        updated_at = conversation.get("updated_at")
        if hasattr(updated_at, "isoformat"):
            updated_at = updated_at.isoformat()
        
        # Handle messages conversion
        messages = []
        for message in conversation.get("messages", []):
            timestamp = message.get("timestamp")
            if hasattr(timestamp, "isoformat"):
                timestamp = timestamp.isoformat()
                
            messages.append({
                "id": message.get("id"),
                "content": message.get("content"),
                "role": message.get("role"),
                "timestamp": timestamp,
                "metadata": message.get("metadata")
            })
        
        return {
            "id": conversation.get("id"),
            "title": conversation.get("title"),
            "courseId": conversation.get("course_id"),
            "moduleId": conversation.get("module_id"),
            "topicId": conversation.get("topic_id"),
            "createdAt": created_at,
            "updatedAt": updated_at,
            "messages": messages,
            "active": conversation.get("active", True)
        }
    
    @staticmethod
    def summary_to_frontend(summary: Dict[str, Any]) -> Dict[str, Any]:
        """Convert dictionary conversation summary to frontend format"""
        return {
            "id": summary.get("id"),
            "title": summary.get("title"),
            "courseId": summary.get("course_id"),
            "moduleId": summary.get("module_id"),
            "topicId": summary.get("topic_id"),
            "createdAt": summary.get("created_at").isoformat() if hasattr(summary.get("created_at"), "isoformat") else summary.get("created_at"),
            "updatedAt": summary.get("updated_at").isoformat() if hasattr(summary.get("updated_at"), "isoformat") else summary.get("updated_at"),
            "messageCount": summary.get("message_count"),
            "lastMessagePreview": summary.get("last_message", {}).get("content", "")[:100] if summary.get("last_message") else None,
            "active": summary.get("active", True)
        }
    
    @staticmethod
    def message_to_frontend(message: Dict[str, Any]) -> Dict[str, Any]:
        """Convert backend Message (dict or object) to frontend format"""
        # Handle dictionary input
        if isinstance(message, dict):
            # Format timestamp if needed
            timestamp = message.get("timestamp")
            if hasattr(timestamp, "isoformat"):
                timestamp = timestamp.isoformat()
                
            return {
                "id": message.get("id"),
                "content": message.get("content"),
                "role": message.get("role"),
                "timestamp": timestamp,
                "metadata": message.get("metadata", {})
            }
        # Handle Message object input
        else:
            return {
                "id": message.id,
                "content": message.content,
                "role": message.role,
                "timestamp": message.timestamp.isoformat() if hasattr(message.timestamp, "isoformat") else message.timestamp,
                "metadata": message.metadata
            }