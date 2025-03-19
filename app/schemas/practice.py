from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    CODING = "coding"

class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class PracticeRequest(BaseModel):
    """Request parameters for generating practice questions"""
    course_id: str
    topic_ids: Optional[List[str]] = None
    question_count: int = 5
    question_types: List[QuestionType] = [QuestionType.MULTIPLE_CHOICE]
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM
    title: Optional[str] = None
    include_explanations: bool = True

class PracticeQuestion(BaseModel):
    """A practice question"""
    id: str
    question: str
    type: QuestionType
    options: Optional[List[str]] = None  # For multiple choice
    correct_answer: Union[str, List[str]]  # Answer or list of correct options
    explanation: Optional[str] = None

class PracticeResponse(BaseModel):
    """Schema for practice set response"""
    id: str
    title: str
    course_id: str
    topic_ids: Optional[List[str]] = None
    question_count: int
    difficulty: DifficultyLevel
    questions: List[PracticeQuestion]
    created_at: str
    created_by: str  # User ID

    class Config:
        from_attributes = True

class PracticeAnswer(BaseModel):
    """User's answer to a practice question"""
    question_id: str
    answer: Union[str, List[str]]

class QuestionResult(BaseModel):
    """Result for a single question"""
    question_id: str
    correct: bool
    user_answer: Union[str, List[str]]
    correct_answer: Union[str, List[str]]
    explanation: Optional[str] = None

class PracticeResult(BaseModel):
    """Results of a practice session"""
    practice_id: str
    user_id: str
    score: float  # Percentage correct
    question_results: List[QuestionResult]
    completed_at: str
    feedback: str