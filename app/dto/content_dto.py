# app/dto/content_dto.py
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from app.schemas.rag_query import RAGResponse, RAGContext, KnowledgeGapResponse, KnowledgeGap, Strength


class FrontendRAGContextDTO(BaseModel):
    """DTO for mapping backend RAGContext to frontend format"""
    id: str
    title: str
    content: str
    citationNumber: int
    materialId: Optional[str] = None
    sourceUrl: Optional[str] = None
    sourcePage: Optional[int] = None
    score: Optional[float] = None
    
    @classmethod
    def from_backend(cls, context: RAGContext) -> 'FrontendRAGContextDTO':
        """Convert backend RAGContext to frontend format"""
        return cls(
            id=context.id,
            title=context.title,
            content=context.content,
            citationNumber=context.citation_number,
            materialId=context.material_id,
            sourceUrl=context.source_url,
            sourcePage=context.source_page,
            score=context.score
        )


class FrontendRAGResponseDTO(BaseModel):
    """DTO for mapping backend RAGResponse to frontend format"""
    queryId: str
    query: str
    answer: str
    context: List[FrontendRAGContextDTO]
    citations: List[int]
    promptType: str
    timestamp: datetime
    meta: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_backend(cls, response: RAGResponse) -> 'FrontendRAGResponseDTO':
        """Convert backend RAGResponse to frontend format"""
        return cls(
            queryId=response.query_id,
            query=response.query,
            answer=response.answer,
            context=[FrontendRAGContextDTO.from_backend(ctx) for ctx in response.context],
            citations=response.citations,
            promptType=response.prompt_type,
            timestamp=response.timestamp,
            meta=response.meta
        )


class FrontendContentSummaryDTO(BaseModel):
    """DTO for mapping backend ContentSummary to frontend format"""
    id: str
    topic: str
    courseId: Optional[str] = None
    moduleId: Optional[str] = None
    createdAt: int
    
    @classmethod
    def from_backend(cls, summary: Dict[str, Any]) -> 'FrontendContentSummaryDTO':
        """Convert backend ContentSummary dict to frontend format"""
        return cls(
            id=summary["id"],
            topic=summary["topic"],
            courseId=summary.get("course_id"),
            moduleId=summary.get("module_id"),
            createdAt=summary["created_at"]
        )


class FrontendStudyGuideSummaryDTO(FrontendContentSummaryDTO):
    """DTO for mapping backend StudyGuideSummary to frontend format"""
    format: str
    detailLevel: str
    
    @classmethod
    def from_backend(cls, summary: Dict[str, Any]) -> 'FrontendStudyGuideSummaryDTO':
        """Convert backend StudyGuideSummary dict to frontend format"""
        return cls(
            id=summary["id"],
            topic=summary["topic"],
            courseId=summary.get("course_id"),
            moduleId=summary.get("module_id"),
            createdAt=summary["created_at"],
            format=summary["format"],
            detailLevel=summary["detail_level"]
        )


class FrontendPracticeQuestionsSummaryDTO(FrontendContentSummaryDTO):
    """DTO for mapping backend PracticeQuestionsSummary to frontend format"""
    difficulty: str
    questionCount: int
    
    @classmethod
    def from_backend(cls, summary: Dict[str, Any]) -> 'FrontendPracticeQuestionsSummaryDTO':
        """Convert backend PracticeQuestionsSummary dict to frontend format"""
        return cls(
            id=summary["id"],
            topic=summary["topic"],
            courseId=summary.get("course_id"),
            moduleId=summary.get("module_id"),
            createdAt=summary["created_at"],
            difficulty=summary["difficulty"],
            questionCount=summary["question_count"]
        )


class FrontendKnowledgeGapSummaryDTO(FrontendContentSummaryDTO):
    """DTO for mapping backend KnowledgeGapSummary to frontend format"""
    query: str
    gapCount: int
    strengthCount: int
    
    @classmethod
    def from_backend(cls, summary: Dict[str, Any]) -> 'FrontendKnowledgeGapSummaryDTO':
        """Convert backend KnowledgeGapSummary dict to frontend format"""
        return cls(
            id=summary["id"],
            topic=summary["topic"],
            courseId=summary.get("course_id"),
            moduleId=summary.get("module_id"),
            createdAt=summary["created_at"],
            query=summary["query"],
            gapCount=summary["gap_count"],
            strengthCount=summary["strength_count"]
        )


class FrontendKnowledgeGapDTO(BaseModel):
    """DTO for mapping backend KnowledgeGap to frontend format"""
    id: str
    concept: str
    description: str
    severity: str
    recommendedResources: List[Dict[str, Any]]
    citations: List[int]
    
    @classmethod
    def from_backend(cls, gap: KnowledgeGap) -> 'FrontendKnowledgeGapDTO':
        """Convert backend KnowledgeGap to frontend format"""
        return cls(
            id=gap.id,
            concept=gap.concept,
            description=gap.description,
            severity=gap.severity,
            recommendedResources=gap.recommended_resources,
            citations=gap.citations
        )


class FrontendStrengthDTO(BaseModel):
    """DTO for mapping backend Strength to frontend format"""
    id: str
    concept: str
    description: str
    
    @classmethod
    def from_backend(cls, strength: Strength) -> 'FrontendStrengthDTO':
        """Convert backend Strength to frontend format"""
        return cls(
            id=strength.id,
            concept=strength.concept,
            description=strength.description
        )


class FrontendKnowledgeGapResponseDTO(BaseModel):
    """DTO for mapping backend KnowledgeGapResponse to frontend format"""
    queryId: str
    query: str
    answer: str
    gaps: List[FrontendKnowledgeGapDTO]
    strengths: List[FrontendStrengthDTO]
    context: List[FrontendRAGContextDTO]
    citations: List[int]
    timestamp: datetime
    
    @classmethod
    def from_backend(cls, response: KnowledgeGapResponse) -> 'FrontendKnowledgeGapResponseDTO':
        """Convert backend KnowledgeGapResponse to frontend format"""
        return cls(
            queryId=response.query_id,
            query=response.query,
            answer=response.answer,
            gaps=[FrontendKnowledgeGapDTO.from_backend(gap) for gap in response.gaps],
            strengths=[FrontendStrengthDTO.from_backend(strength) for strength in response.strengths],
            context=[FrontendRAGContextDTO.from_backend(ctx) for ctx in response.context],
            citations=response.citations,
            timestamp=response.timestamp
        )


class FrontendDeleteResponseDTO(BaseModel):
    """DTO for mapping backend DeleteResponse to frontend format"""
    success: bool
    message: str
    
    @classmethod
    def from_backend(cls, response: Dict[str, Any]) -> 'FrontendDeleteResponseDTO':
        """Convert backend DeleteResponse to frontend format"""
        return cls(
            success=response["success"],
            message=response["message"]
        )


class FrontendDeleteAllResponseDTO(BaseModel):
    """DTO for mapping backend DeleteAllResponse to frontend format"""
    success: bool
    deletedCounts: Dict[str, int]
    message: str
    
    @classmethod
    def from_backend(cls, response: Dict[str, Any]) -> 'FrontendDeleteAllResponseDTO':
        """Convert backend DeleteAllResponse to frontend format"""
        return cls(
            success=response["success"],
            deletedCounts=response["deleted_counts"],
            message=response["message"]
        )