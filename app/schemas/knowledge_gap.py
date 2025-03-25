from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
from app.schemas.query import CitationSource


class GapSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class KnowledgeGap(BaseModel):
    """Schema for a knowledge gap"""
    id: str
    concept: str
    description: str
    severity: GapSeverity
    recommended_resources: List[Dict[str, Any]]
    citations: List[CitationSource] = []


class KnowledgeAssessment(BaseModel):
    """Schema for a knowledge assessment"""
    id: str
    title: str
    user_id: str
    course_id: str
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    gaps: List[KnowledgeGap] = []
    strengths: List[Dict[str, Any]] = []
    recommended_study_plan: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class KnowledgeAssessmentSummary(BaseModel):
    """Schema for knowledge assessment summary (for listing)"""
    id: str
    title: str
    course_id: str
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    gap_count: int
    highest_severity: Optional[GapSeverity] = None