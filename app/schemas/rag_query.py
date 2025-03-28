# app/schemas/rag_query.py
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class RAGContext(BaseModel):
    """
    Schema for context information returned with RAG responses
    """
    id: str = Field(..., description="Unique identifier for the context chunk")
    title: str = Field(..., description="Title/source of the context chunk")
    content: str = Field(..., description="Content of the context chunk")
    citation_number: int = Field(..., description="Citation number for referencing")
    material_id: Optional[str] = Field(None, description="ID of the source material")
    source_url: Optional[str] = Field(None, description="URL of the source")
    source_page: Optional[int] = Field(None, description="Page number in the source")
    score: Optional[float] = Field(None, description="Relevance score of the chunk")


class RAGQuery(BaseModel):
    """
    Schema for RAG query requests
    """
    query: str = Field(..., description="User query text")
    course_id: Optional[str] = Field(None, description="Course ID filter")
    module_id: Optional[str] = Field(None, description="Module ID filter")
    topic_id: Optional[str] = Field(None, description="Topic ID filter")
    user_id: Optional[str] = Field(None, description="User ID for personalization")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Query timestamp")
    session_id: Optional[str] = Field(None, description="Session ID for conversation context")
    prompt_type: str = Field("question_answering", description="Type of prompt to use")
    additional_params: Optional[Dict[str, Any]] = Field(None, description="Additional parameters")


class RAGResponse(BaseModel):
    """
    Schema for RAG query responses
    """
    query_id: str = Field(..., description="Unique identifier for the query")
    query: str = Field(..., description="Original query text")
    answer: str = Field(..., description="Generated answer text")
    context: List[RAGContext] = Field(default_factory=list, description="Context chunks used")
    citations: List[int] = Field(default_factory=list, description="Citation numbers used in answer")
    prompt_type: str = Field(..., description="Type of prompt used")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    meta: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class StudyGuideRequest(BaseModel):
    """
    Schema for study guide generation requests
    """
    topic: str = Field(..., description="Topic for the study guide")
    course_id: Optional[str] = Field(None, description="Course ID filter")
    module_id: Optional[str] = Field(None, description="Module ID filter")
    detail_level: str = Field("medium", description="Detail level (basic, medium, comprehensive)")
    format: str = Field("outline", description="Format (outline, notes, flashcards, mind_map, summary)")
    user_id: Optional[str] = Field(None, description="User ID for personalization")


class PracticeQuestionsRequest(BaseModel):
    """
    Schema for practice questions generation requests
    """
    topic: str = Field(..., description="Topic for practice questions")
    course_id: Optional[str] = Field(None, description="Course ID filter")
    module_id: Optional[str] = Field(None, description="Module ID filter")
    question_count: int = Field(5, ge=1, le=10, description="Number of questions to generate")
    difficulty: str = Field("medium", description="Difficulty level (basic, medium, advanced)")
    question_types: List[str] = Field(
        ["multiple_choice", "short_answer"],
        description="Types of questions to generate"
    )
    user_id: Optional[str] = Field(None, description="User ID for personalization")


class Question(BaseModel):
    """
    Schema for a practice question
    """
    id: str = Field(..., description="Question identifier")
    type: str = Field(..., description="Question type")
    text: str = Field(..., description="Question text")
    difficulty: str = Field(..., description="Question difficulty")
    citations: List[int] = Field(default_factory=list, description="Citations for this question")
    
    # For multiple choice questions
    options: Optional[List[Dict[str, Any]]] = Field(None, description="Multiple choice options")
    
    # For other question types
    sample_answer: Optional[str] = Field(None, description="Sample answer for open questions")
    explanation: Optional[str] = Field(None, description="Explanation of the answer")


class KnowledgeGap(BaseModel):
    """
    Schema for a knowledge gap
    """
    id: str = Field(..., description="Gap identifier")
    concept: str = Field(..., description="Concept name")
    description: str = Field(..., description="Description of the knowledge gap")
    severity: str = Field(..., description="Severity level (low, medium, high)")
    recommended_resources: List[Dict[str, Any]] = Field(default_factory=list, description="Recommended resources")
    citations: List[int] = Field(default_factory=list, description="Citations for this gap")


class Strength(BaseModel):
    """
    Schema for a knowledge strength
    """
    id: str = Field(..., description="Strength identifier")
    concept: str = Field(..., description="Concept name")
    description: str = Field(..., description="Description of the knowledge strength")


class KnowledgeGapResponse(BaseModel):
    """
    Schema for knowledge gap analysis responses
    """
    query_id: str = Field(..., description="Unique identifier for the query")
    query: str = Field(..., description="Original query text")
    answer: str = Field(..., description="Analysis summary")
    gaps: List[KnowledgeGap] = Field(default_factory=list, description="Identified knowledge gaps")
    strengths: List[Strength] = Field(default_factory=list, description="Identified knowledge strengths")
    context: List[RAGContext] = Field(default_factory=list, description="Context chunks used")
    citations: List[int] = Field(default_factory=list, description="Citation numbers used in analysis")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")