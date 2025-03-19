from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class QueryCreate(BaseModel):
    """Schema for creating a new query"""
    query: str = Field(..., min_length=1)
    course_id: Optional[str] = None
    conversation_id: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "query": "Explain the differences between supervised and unsupervised learning",
                "course_id": "machine-learning-101",
                "conversation_id": "9f7b5e3a-8c1d-4b5a-b5e3-9f7b5e3a8c1d"
            }
        }


class SourceInfo(BaseModel):
    """Schema for source citation information"""
    source_id: Optional[str] = None
    source: str
    course_id: Optional[str] = None
    course_name: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None


class QueryResponse(BaseModel):
    """Schema for query response"""
    query_id: str
    query: str
    response: str
    sources: List[SourceInfo]
    conversation_id: str
    timestamp: str
    course_id: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "query_id": "123e4567-e89b-12d3-a456-426614174000",
                "query": "Explain the differences between supervised and unsupervised learning",
                "response": "Supervised learning uses labeled data where the model learns from input-output pairs. Unsupervised learning works with unlabeled data, finding patterns without explicit guidance.",
                "sources": [
                    {
                        "source_id": "ml-textbook-ch3",
                        "source": "Machine Learning Textbook",
                        "course_id": "machine-learning-101",
                        "course_name": "Introduction to Machine Learning",
                        "page": 45,
                        "section": "Learning Paradigms"
                    }
                ],
                "conversation_id": "9f7b5e3a-8c1d-4b5a-b5e3-9f7b5e3a8c1d",
                "timestamp": "2023-09-15T14:30:25.123Z",
                "course_id": "machine-learning-101"
            }
        }


class QueryHistory(BaseModel):
    """Schema for query history item"""
    id: str
    user_id: str
    query: str
    response: str
    sources: List[SourceInfo]
    conversation_id: str
    timestamp: str
    course_id: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "user123",
                "query": "Explain the differences between supervised and unsupervised learning",
                "response": "Supervised learning uses labeled data where the model learns from input-output pairs. Unsupervised learning works with unlabeled data, finding patterns without explicit guidance.",
                "sources": [
                    {
                        "source_id": "ml-textbook-ch3",
                        "source": "Machine Learning Textbook",
                        "course_id": "machine-learning-101",
                        "course_name": "Introduction to Machine Learning",
                        "page": 45,
                        "section": "Learning Paradigms"
                    }
                ],
                "conversation_id": "9f7b5e3a-8c1d-4b5a-b5e3-9f7b5e3a8c1d",
                "timestamp": "2023-09-15T14:30:25.123Z",
                "course_id": "machine-learning-101"
            }
        }


class FeedbackCreate(BaseModel):
    """Schema for user feedback on responses"""
    query_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    is_helpful: bool = True
    category: Optional[str] = None


class ConversationSummary(BaseModel):
    """Schema for conversation summary"""
    conversation_id: str
    title: str
    last_query: str
    last_timestamp: str
    query_count: int
    course_id: Optional[str] = None