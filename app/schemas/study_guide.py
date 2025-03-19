from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class StudyGuideType(str, Enum):
    SUMMARY = "summary"
    CONCEPT_MAP = "concept_map"
    KEY_POINTS = "key_points"
    DETAILED = "detailed"

class StudyGuideRequest(BaseModel):
    """Request parameters for generating a study guide"""
    course_id: str
    topic_ids: Optional[List[str]] = None
    guide_type: StudyGuideType = StudyGuideType.SUMMARY
    title: Optional[str] = None
    focus_areas: Optional[List[str]] = None
    max_length: Optional[int] = 2000  # Max word count
    include_examples: bool = True
    include_diagrams: bool = False

class StudyGuideSection(BaseModel):
    """A section in a study guide"""
    title: str
    content: str
    order: int

class StudyGuideResponse(BaseModel):
    """Schema for study guide response"""
    id: str
    title: str
    course_id: str
    topic_ids: Optional[List[str]] = None
    guide_type: StudyGuideType
    sections: List[StudyGuideSection]
    created_at: str
    created_by: str  # User ID

    class Config:
        from_attributes = True