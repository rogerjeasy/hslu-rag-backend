from typing import Dict, Any, List, Optional
from app.schemas.study_guide import (
    StudyGuideSection, StudyGuideRequest, StudyGuideResponse, StudyGuideType
)
# from app.dto.query_dto import CitationDTO

class FrontendStudyGuideRequestDTO:
    """DTO for handling frontend study guide creation requests"""
   
    @staticmethod
    def to_backend(data: Dict[str, Any]) -> StudyGuideRequest:
        """Convert frontend request data to StudyGuideRequest"""
        # Map frontend format to backend guide_type
        format_to_guide_type = {
            "outline": StudyGuideType.KEY_POINTS,
            "notes": StudyGuideType.DETAILED,
            "summary": StudyGuideType.SUMMARY,
            "mind_map": StudyGuideType.CONCEPT_MAP,
            "flashcards": StudyGuideType.SUMMARY
        }
        
        # Get the guide type from format, defaulting to SUMMARY
        format_value = data.get("format", "outline")
        guide_type = format_to_guide_type.get(format_value, StudyGuideType.SUMMARY)
        
        # Create and return backend request object
        return StudyGuideRequest(
            course_id=data.get("courseId"),
            topic_ids=[data.get("topicId")] if data.get("topicId") else None,
            guide_type=guide_type,
            title=data.get("topic"),  # Use topic as title
            focus_areas=None,
            max_length=2000,  # Default value
            include_examples=True,
            include_diagrams=format_value == "mind_map"
        )
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> StudyGuideRequest:
        """Alias for to_backend for consistency with other DTOs"""
        return FrontendStudyGuideRequestDTO.to_backend(data)

class BackendStudyGuideDTO:
    """DTO for converting backend study guide schemas to frontend format"""
   
    @staticmethod
    def study_guide_to_frontend(guide: Dict[str, Any]) -> Dict[str, Any]:
        """Convert backend study guide dict to frontend format"""
        return {
            "id": guide.get("id"),
            "title": guide.get("title"),
            "courseId": guide.get("course_id"),
            "topicIds": guide.get("topic_ids"),
            "format": guide.get("guide_type"),
            "sections": [
                BackendStudyGuideDTO.section_to_frontend(section)
                for section in guide.get("sections", [])
            ],
            "createdAt": guide.get("created_at"),
            "createdBy": guide.get("created_by")
        }
   
    @staticmethod
    def section_to_frontend(section: Dict[str, Any]) -> Dict[str, Any]:
        """Convert backend section dict to frontend format"""
        return {
            "title": section.get("title", ""),
            "content": section.get("content", ""),
            "order": section.get("order", 0)
        }
   
    @staticmethod
    def response_to_frontend(response: StudyGuideResponse) -> Dict[str, Any]:
        """Convert StudyGuideResponse to frontend format"""
        return {
            "id": response.id,
            "title": response.title,
            "courseId": response.course_id,
            "topicIds": response.topic_ids,
            "format": response.guide_type,
            "sections": [
                {
                    "title": section.title,
                    "content": section.content,
                    "order": section.order
                }
                for section in response.sections
            ],
            "createdAt": response.created_at,
            "createdBy": response.created_by
        }