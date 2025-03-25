from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from app.schemas.practice_questions import (
    QuestionSet, QuestionSetSummary, Question, QuestionType,
    MultipleChoiceQuestion, ShortAnswerQuestion, TrueFalseQuestion,
    FillInBlankQuestion, MatchingQuestion, MultipleChoiceOption, MatchingItem,
    DifficultyLevel
)
from app.dto.query_dto import CitationDTO


class FrontendPracticeQuestionsDTO:
    """DTO for converting frontend practice questions data to backend schemas"""
    
    @staticmethod
    def question_to_backend(data: Dict[str, Any]) -> Question:
        """Convert frontend question data to appropriate backend Question type"""
        question_type = data.get("type", "multiple_choice")
        
        if question_type == "multiple_choice":
            return MultipleChoiceQuestion(
                id=data.get("id", ""),
                text=data.get("text", ""),
                type=QuestionType.MULTIPLE_CHOICE,
                difficulty=data.get("difficulty", "medium"),
                explanation=data.get("explanation"),
                citations=[
                    CitationDTO.to_backend(citation)
                    for citation in data.get("citations", [])
                ],
                options=[
                    MultipleChoiceOption(
                        id=option.get("id", ""),
                        text=option.get("text", ""),
                        is_correct=option.get("isCorrect", False),
                        explanation=option.get("explanation")
                    )
                    for option in data.get("options", [])
                ]
            )
        elif question_type == "short_answer":
            return ShortAnswerQuestion(
                id=data.get("id", ""),
                text=data.get("text", ""),
                type=QuestionType.SHORT_ANSWER,
                difficulty=data.get("difficulty", "medium"),
                explanation=data.get("explanation"),
                citations=[
                    CitationDTO.to_backend(citation)
                    for citation in data.get("citations", [])
                ],
                sample_answer=data.get("sampleAnswer", "")
            )
        elif question_type == "true_false":
            return TrueFalseQuestion(
                id=data.get("id", ""),
                text=data.get("text", ""),
                type=QuestionType.TRUE_FALSE,
                difficulty=data.get("difficulty", "medium"),
                explanation=data.get("explanation"),
                citations=[
                    CitationDTO.to_backend(citation)
                    for citation in data.get("citations", [])
                ],
                correct_answer=data.get("correctAnswer", False)
            )
        elif question_type == "fill_in_blank":
            return FillInBlankQuestion(
                id=data.get("id", ""),
                text=data.get("text", ""),
                type=QuestionType.FILL_IN_BLANK,
                difficulty=data.get("difficulty", "medium"),
                explanation=data.get("explanation"),
                citations=[
                    CitationDTO.to_backend(citation)
                    for citation in data.get("citations", [])
                ],
                blanks=data.get("blanks", [])
            )
        elif question_type == "matching":
            return MatchingQuestion(
                id=data.get("id", ""),
                text=data.get("text", ""),
                type=QuestionType.MATCHING,
                difficulty=data.get("difficulty", "medium"),
                explanation=data.get("explanation"),
                citations=[
                    CitationDTO.to_backend(citation)
                    for citation in data.get("citations", [])
                ],
                items=[
                    MatchingItem(
                        id=item.get("id", ""),
                        left_text=item.get("leftText", ""),
                        right_text=item.get("rightText", "")
                    )
                    for item in data.get("items", [])
                ]
            )
        else:
            # Default to multiple choice if type is not recognized
            return MultipleChoiceQuestion(
                id=data.get("id", ""),
                text=data.get("text", ""),
                type=QuestionType.MULTIPLE_CHOICE,
                difficulty=data.get("difficulty", "medium"),
                explanation=data.get("explanation"),
                citations=[],
                options=[]
            )


class BackendPracticeQuestionsDTO:
    """DTO for converting backend practice questions schemas to frontend format"""
    
    @staticmethod
    def question_set_to_frontend(question_set: QuestionSet) -> Dict[str, Any]:
        """Convert backend QuestionSet to frontend format"""
        return {
            "id": question_set.id,
            "title": question_set.title,
            "description": question_set.description,
            "courseId": question_set.course_id,
            "moduleId": question_set.module_id,
            "topicId": question_set.topic_id,
            "userId": question_set.user_id,
            "createdAt": question_set.created_at.isoformat(),
            "updatedAt": question_set.updated_at.isoformat(),
            "difficulty": question_set.difficulty,
            "questions": [
                BackendPracticeQuestionsDTO.question_to_frontend(question)
                for question in question_set.questions
            ],
            "metadata": question_set.metadata
        }
    
    @staticmethod
    def question_to_frontend(question: Question) -> Dict[str, Any]:
        """Convert backend Question to frontend format"""
        base_question = {
            "id": question.id,
            "text": question.text,
            "type": question.type,
            "difficulty": question.difficulty,
            "explanation": question.explanation,
            "citations": [
                CitationDTO.to_frontend(citation)
                for citation in question.citations
            ]
        }
        
        if isinstance(question, MultipleChoiceQuestion):
            base_question["options"] = [
                {
                    "id": option.id,
                    "text": option.text,
                    "isCorrect": option.is_correct,
                    "explanation": option.explanation
                }
                for option in question.options
            ]
        elif isinstance(question, ShortAnswerQuestion):
            base_question["sampleAnswer"] = question.sample_answer
        elif isinstance(question, TrueFalseQuestion):
            base_question["correctAnswer"] = question.correct_answer
        elif isinstance(question, FillInBlankQuestion):
            base_question["blanks"] = question.blanks
        elif isinstance(question, MatchingQuestion):
            base_question["items"] = [
                {
                    "id": item.id,
                    "leftText": item.left_text,
                    "rightText": item.right_text
                }
                for item in question.items
            ]
        
        return base_question
    
    @staticmethod
    def summary_to_frontend(summary: QuestionSetSummary) -> Dict[str, Any]:
        """Convert backend QuestionSetSummary to frontend format"""
        return {
            "id": summary.id,
            "title": summary.title,
            "courseId": summary.course_id,
            "moduleId": summary.module_id,
            "topicId": summary.topic_id,
            "createdAt": summary.created_at.isoformat(),
            "updatedAt": summary.updated_at.isoformat(),
            "difficulty": summary.difficulty,
            "questionCount": summary.question_count,
            "types": summary.types
        }