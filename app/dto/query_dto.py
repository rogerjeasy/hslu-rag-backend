from typing import Dict, Any, List, Optional
from datetime import datetime
from app.schemas.query import (
    QueryRequest, QueryResponse, CitationSource, QueryType,
    StudyGuideRequest, PracticeQuestionsRequest, KnowledgeGapRequest
)


class FrontendQueryRequestDTO:
    """DTO for converting frontend query requests to backend schema"""
    
    @staticmethod
    def to_backend(data: Dict[str, Any]) -> QueryRequest:
        """Convert frontend query data to backend QueryRequest"""
        return QueryRequest(
            text=data.get("text", ""),
            course_id=data.get("courseId", ""),
            module_id=data.get("moduleId"),
            topic_id=data.get("topicId"),
            query_type=data.get("queryType", "question_answering"),
            conversation_id=data.get("conversationId"),
            model_id=data.get("modelId", "gpt-4"),
            additional_params=data.get("additionalParams")
        )
    
    @staticmethod
    def to_study_guide_request(data: Dict[str, Any]) -> StudyGuideRequest:
        """Convert frontend data to StudyGuideRequest"""
        base_request = FrontendQueryRequestDTO.to_backend(data)
        return StudyGuideRequest(
            **base_request.dict(),
            detail_level=data.get("detailLevel", "medium"),
            format=data.get("format", "outline"),
            include_practice_questions=data.get("includePracticeQuestions", False)
        )
    
    @staticmethod
    def to_practice_questions_request(data: Dict[str, Any]) -> PracticeQuestionsRequest:
        """Convert frontend data to PracticeQuestionsRequest"""
        base_request = FrontendQueryRequestDTO.to_backend(data)
        return PracticeQuestionsRequest(
            **base_request.dict(),
            question_count=data.get("questionCount", 5),
            difficulty=data.get("difficulty", "medium"),
            question_types=data.get("questionTypes", ["multiple_choice", "short_answer"])
        )
    
    @staticmethod
    def to_knowledge_gap_request(data: Dict[str, Any]) -> KnowledgeGapRequest:
        """Convert frontend data to KnowledgeGapRequest"""
        base_request = FrontendQueryRequestDTO.to_backend(data)
        return KnowledgeGapRequest(
            **base_request.dict(),
            past_interactions_count=data.get("pastInteractionsCount", 10)
        )


class BackendQueryResponseDTO:
    """DTO for converting backend query responses to frontend format"""
    
    @staticmethod
    def to_frontend(response: QueryResponse) -> Dict[str, Any]:
        """Convert backend QueryResponse to frontend format"""
        return {
            "responseText": response.response_text,
            "citations": [
                {
                    "materialId": citation.material_id,
                    "title": citation.title,
                    "chunkIndex": citation.chunk_index,
                    "pageNumber": citation.page_number,
                    "contentPreview": citation.content_preview,
                    "fileUrl": citation.file_url
                }
                for citation in response.citations
            ],
            "queryType": response.query_type,
            "conversationId": response.conversation_id,
            "timestamp": response.timestamp.isoformat(),
            "additionalData": response.additional_data
        }


class CitationDTO:
    """DTO for citation conversions"""
    
    @staticmethod
    def to_backend(data: Dict[str, Any]) -> CitationSource:
        """Convert frontend citation data to backend CitationSource"""
        return CitationSource(
            material_id=data.get("materialId", ""),
            title=data.get("title", ""),
            chunk_index=data.get("chunkIndex", 0),
            page_number=data.get("pageNumber"),
            content_preview=data.get("contentPreview", ""),
            file_url=data.get("fileUrl")
        )
    
    @staticmethod
    def to_frontend(citation: CitationSource) -> Dict[str, Any]:
        """Convert backend CitationSource to frontend format"""
        return {
            "materialId": citation.material_id,
            "title": citation.title,
            "chunkIndex": citation.chunk_index,
            "pageNumber": citation.page_number,
            "contentPreview": citation.content_preview,
            "fileUrl": citation.file_url
        }