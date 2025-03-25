from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.schemas.query import QueryType


class Message(BaseModel):
    """Schema for a single message in a conversation"""
    id: str
    content: str
    role: str  # user or assistant
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class Conversation(BaseModel):
    """Schema for a conversation"""
    id: str
    title: str
    user_id: str
    course_id: str
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[Message] = []
    active: bool = True


class ConversationSummary(BaseModel):
    """Schema for conversation summary (for listing)"""
    id: str
    title: str
    course_id: str
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int
    last_message_preview: Optional[str] = None
    active: bool = True


class ConversationCreateRequest(BaseModel):
    """Schema for creating a new conversation"""
    title: str
    course_id: str
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    initial_message: Optional[str] = None


class ConversationUpdateRequest(BaseModel):
    """Schema for updating a conversation"""
    title: Optional[str] = None
    active: Optional[bool] = None


class MessageCreateRequest(BaseModel):
    """Schema for creating a new message"""
    content: str
    query_type: QueryType = QueryType.QUESTION_ANSWERING
    additional_params: Optional[Dict[str, Any]] = None