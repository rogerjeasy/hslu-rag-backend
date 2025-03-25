from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime
from app.schemas.query import CitationSource


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"
    TRUE_FALSE = "true_false"
    FILL_IN_BLANK = "fill_in_blank"
    MATCHING = "matching"


class DifficultyLevel(str, Enum):
    BASIC = "basic"
    MEDIUM = "medium"
    ADVANCED = "advanced"


class MultipleChoiceOption(BaseModel):
    """Schema for a multiple choice option"""
    id: str
    text: str
    is_correct: bool
    explanation: Optional[str] = None


class MatchingItem(BaseModel):
    """Schema for a matching item"""
    id: str
    left_text: str
    right_text: str


class QuestionBase(BaseModel):
    """Base schema for all question types"""
    id: str
    text: str
    type: QuestionType
    difficulty: DifficultyLevel
    explanation: Optional[str] = None
    citations: List[CitationSource] = []


class MultipleChoiceQuestion(QuestionBase):
    """Schema for multiple choice questions"""
    type: QuestionType = QuestionType.MULTIPLE_CHOICE
    options: List[MultipleChoiceOption]


class ShortAnswerQuestion(QuestionBase):
    """Schema for short answer questions"""
    type: QuestionType = QuestionType.SHORT_ANSWER
    sample_answer: str


class TrueFalseQuestion(QuestionBase):
    """Schema for true/false questions"""
    type: QuestionType = QuestionType.TRUE_FALSE
    correct_answer: bool


class FillInBlankQuestion(QuestionBase):
    """Schema for fill-in-the-blank questions"""
    type: QuestionType = QuestionType.FILL_IN_BLANK
    blanks: List[str]  # List of correct answers for each blank


class MatchingQuestion(QuestionBase):
    """Schema for matching questions"""
    type: QuestionType = QuestionType.MATCHING
    items: List[MatchingItem]


Question = Union[
    MultipleChoiceQuestion,
    ShortAnswerQuestion,
    TrueFalseQuestion,
    FillInBlankQuestion,
    MatchingQuestion
]


class QuestionSet(BaseModel):
    """Schema for a set of practice questions"""
    id: str
    title: str
    description: Optional[str] = None
    course_id: str
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    user_id: str
    created_at: datetime
    updated_at: datetime
    difficulty: DifficultyLevel
    questions: List[Question]
    metadata: Optional[Dict[str, Any]] = None


class QuestionSetSummary(BaseModel):
    """Schema for question set summary (for listing)"""
    id: str
    title: str
    course_id: str
    module_id: Optional[str] = None
    topic_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    difficulty: DifficultyLevel
    question_count: int
    types: List[QuestionType]