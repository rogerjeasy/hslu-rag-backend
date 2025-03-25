from typing import Dict, Any, List, Optional
from datetime import datetime
from app.schemas.study_guide import (
    StudyGuide, StudyGuideSummary, StudyGuideSection, 
    DetailLevel, StudyGuideFormat, StudyGuideCreateResponse
)
from app.dto.query_dto import CitationDTO


class FrontendStudyGuideDTO:
    """DTO for converting frontend study guide data to backend schemas"""
    
    @staticmethod
    def section_to_backend(data: Dict[str, Any]) -> StudyGuideSection:
        """Convert frontend section data to StudyGuideSection"""
        section = StudyGuideSection(
            title=data.get("title", ""),
            content=data.get("content", ""),
            order=data.get("order", 0),
            citations=[
                CitationDTO.to_backend(citation)
                for citation in data.get("citations", [])
            ],
            sub_sections=[]
        )
        
        # Process sub-sections recursively if present
        for sub_section_data in data.get("subSections", []):
            section.sub_sections.append(
                FrontendStudyGuideDTO.section_to_backend(sub_section_data)
            )
        
        return section


class BackendStudyGuideDTO:
    """DTO for converting backend study guide schemas to frontend format"""
    
    @staticmethod
    def study_guide_to_frontend(guide: StudyGuide) -> Dict[str, Any]:
        """Convert backend StudyGuide to frontend format"""
        return {
            "id": guide.id,
            "title": guide.title,
            "description": guide.description,
            "courseId": guide.course_id,
            "moduleId": guide.module_id,
            "topicId": guide.topic_id,
            "userId": guide.user_id,
            "createdAt": guide.created_at.isoformat(),
            "updatedAt": guide.updated_at.isoformat(),
            "detailLevel": guide.detail_level,
            "format": guide.format,
            "sections": [
                BackendStudyGuideDTO.section_to_frontend(section)
                for section in guide.sections
            ],
            "citations": [
                CitationDTO.to_frontend(citation)
                for citation in guide.citations
            ],
            "metadata": guide.metadata
        }
    
    @staticmethod
    def section_to_frontend(section: StudyGuideSection) -> Dict[str, Any]:
        """Convert backend StudyGuideSection to frontend format"""
        return {
            "title": section.title,
            "content": section.content,
            "order": section.order,
            "citations": [
                CitationDTO.to_frontend(citation)
                for citation in section.citations
            ],
            "subSections": [
                BackendStudyGuideDTO.section_to_frontend(sub_section)
                for sub_section in section.sub_sections
            ]
        }
    
    @staticmethod
    def summary_to_frontend(summary: StudyGuideSummary) -> Dict[str, Any]:
        """Convert backend StudyGuideSummary to frontend format"""
        return {
            "id": summary.id,
            "title": summary.title,
            "courseId": summary.course_id,
            "moduleId": summary.module_id,
            "topicId": summary.topic_id,
            "createdAt": summary.created_at.isoformat(),
            "updatedAt": summary.updated_at.isoformat(),
            "detailLevel": summary.detail_level,
            "format": summary.format,
            "sectionCount": summary.section_count
        }
    
    @staticmethod
    def create_response_to_frontend(response: StudyGuideCreateResponse) -> Dict[str, Any]:
        """Convert backend StudyGuideCreateResponse to frontend format"""
        return {
            "id": response.id,
            "title": response.title,
            "courseId": response.course_id,
            "createdAt": response.created_at.isoformat()
        }