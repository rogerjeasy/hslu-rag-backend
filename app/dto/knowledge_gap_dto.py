from typing import Dict, Any, List, Optional
from datetime import datetime
from app.schemas.knowledge_gap import (
    KnowledgeAssessment, KnowledgeAssessmentSummary, 
    KnowledgeGap, GapSeverity
)
from app.dto.query_dto import CitationDTO


class FrontendKnowledgeGapDTO:
    """DTO for converting frontend knowledge gap data to backend schemas"""
    
    @staticmethod
    def gap_to_backend(data: Dict[str, Any]) -> KnowledgeGap:
        """Convert frontend gap data to KnowledgeGap"""
        return KnowledgeGap(
            id=data.get("id", ""),
            concept=data.get("concept", ""),
            description=data.get("description", ""),
            severity=data.get("severity", "medium"),
            recommended_resources=data.get("recommendedResources", []),
            citations=[
                CitationDTO.to_backend(citation)
                for citation in data.get("citations", [])
            ]
        )


class BackendKnowledgeGapDTO:
    """DTO for converting backend knowledge gap schemas to frontend format"""
    
    @staticmethod
    def assessment_to_frontend(assessment: KnowledgeAssessment) -> Dict[str, Any]:
        """Convert backend KnowledgeAssessment to frontend format"""
        return {
            "id": assessment.id,
            "title": assessment.title,
            "userId": assessment.user_id,
            "courseId": assessment.course_id,
            "moduleId": assessment.module_id,
            "topicId": assessment.topic_id,
            "createdAt": assessment.created_at.isoformat(),
            "updatedAt": assessment.updated_at.isoformat(),
            "gaps": [
                BackendKnowledgeGapDTO.gap_to_frontend(gap)
                for gap in assessment.gaps
            ],
            "strengths": assessment.strengths,
            "recommendedStudyPlan": assessment.recommended_study_plan,
            "metadata": assessment.metadata
        }
    
    @staticmethod
    def gap_to_frontend(gap: KnowledgeGap) -> Dict[str, Any]:
        """Convert backend KnowledgeGap to frontend format"""
        return {
            "id": gap.id,
            "concept": gap.concept,
            "description": gap.description,
            "severity": gap.severity,
            "recommendedResources": gap.recommended_resources,
            "citations": [
                CitationDTO.to_frontend(citation)
                for citation in gap.citations
            ]
        }
    
    @staticmethod
    def summary_to_frontend(summary: KnowledgeAssessmentSummary) -> Dict[str, Any]:
        """Convert backend KnowledgeAssessmentSummary to frontend format"""
        return {
            "id": summary.id,
            "title": summary.title,
            "courseId": summary.course_id,
            "moduleId": summary.module_id,
            "topicId": summary.topic_id,
            "createdAt": summary.created_at.isoformat(),
            "updatedAt": summary.updated_at.isoformat(),
            "gapCount": summary.gap_count,
            "highestSeverity": summary.highest_severity
        }