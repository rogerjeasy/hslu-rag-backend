from fastapi import APIRouter, Depends, HTTPException, Body, status
from typing import Dict, Any, List, Optional
from app.schemas.knowledge_gap import (
    KnowledgeAssessment, KnowledgeAssessmentSummary, GapSeverity
)
from app.dto.knowledge_gap_dto import (
    FrontendKnowledgeGapDTO, BackendKnowledgeGapDTO
)
from app.services.firestore_service import FirestoreService
from app.rag_new.rag_service import RAGService
from app.services.retrieval_service import RetrievalService
from app.services.generation_service import GenerationService
from app.schemas.query import KnowledgeGapRequest, QueryType
from app.core.security import get_current_user
from app.schemas.auth import UserResponse
from app.core.firebase import firebase

router = APIRouter(prefix="/knowledge-gaps", tags=["knowledge-gaps"])

# Initialize services
retrieval_service = RetrievalService()
generation_service = GenerationService()
firestore_service = FirestoreService(firebase.get_firestore())
rag_service = RAGService()

@router.post("/", response_model=Dict[str, Any])
async def analyze_knowledge_gap(
    data: Dict[str, Any] = Body(...),
    current_user: UserResponse = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new knowledge gap assessment for a topic or question"""
    try:
        # Create a knowledge gap request
        knowledge_gap_request = KnowledgeGapRequest(
            text=data.get("query", ""),
            course_id=data.get("courseId", ""),
            module_id=data.get("moduleId"),
            topic_id=data.get("topicId"),
            query_type=QueryType.KNOWLEDGE_GAP,
            model_id=data.get("modelId", "gpt-4"),
            past_interactions_count=data.get("pastInteractionsCount", 10)
        )
        
        # Process the knowledge gap request
        response = await rag_service.process_query(
            query_request=knowledge_gap_request,
            user_id=current_user.id
        )
        
        # The assessment has been saved to firestore during processing
        # Return basic details
        return {
            "id": response.conversation_id,
            "title": data.get("query", "Knowledge Assessment"),
            "courseId": data.get("courseId", ""),
            "createdAt": response.timestamp.isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating knowledge gap assessment: {str(e)}"
        )

@router.get("/", response_model=List[Dict[str, Any]])
async def get_knowledge_gap_assessments(
    course_id: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Get list of user's knowledge gap assessments"""
    try:
        assessments = await firestore_service.get_user_knowledge_gaps(
            user_id=current_user.id,
            course_id=course_id
        )
        return assessments
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving knowledge gap assessments: {str(e)}"
        )

@router.get("/{assessment_id}", response_model=Dict[str, Any])
async def get_knowledge_gap_assessment(
    assessment_id: str,
    current_user: UserResponse = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get a specific knowledge gap assessment"""
    try:
        assessment = await firestore_service.get_knowledge_gap(
            assessment_id=assessment_id,
            user_id=current_user.id
        )
        return assessment
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving knowledge gap assessment: {str(e)}"
        )

@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_gap_assessment(
    assessment_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a knowledge gap assessment"""
    try:
        # First ensure the user has access to this assessment
        await firestore_service.get_knowledge_gap(
            assessment_id=assessment_id,
            user_id=current_user.id
        )
        
        # Delete the assessment
        await firestore_service.delete_document(
            collection="knowledge_gaps",
            document_id=assessment_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting knowledge gap assessment: {str(e)}"
        )

@router.post("/{assessment_id}/study-plan", response_model=Dict[str, Any])
async def generate_study_plan(
    assessment_id: str,
    data: Dict[str, Any] = Body(...),
    current_user: UserResponse = Depends(get_current_user)
) -> Dict[str, Any]:
    """Generate a personalized study plan based on knowledge gaps"""
    try:
        # First ensure the user has access to this assessment
        assessment = await firestore_service.get_knowledge_gap(
            assessment_id=assessment_id,
            user_id=current_user.id
        )
        
        # Extract gaps from the assessment
        gaps = assessment.get("gaps", [])
        if not gaps:
            return {
                "message": "No knowledge gaps found to create a study plan",
                "study_plan": None
            }
        
        # Create a prompt for the LLM to generate a study plan
        gap_descriptions = "\n".join([
            f"- {gap.get('concept')}: {gap.get('description')} (Severity: {gap.get('severity', 'medium')})"
            for gap in gaps
        ])
        
        # Create a specialized request for generating the study plan
        time_frame = data.get("timeFrame", "2 weeks")
        hours_per_week = data.get("hoursPerWeek", 10)
        
        study_plan_request = KnowledgeGapRequest(
            text=f"Create a {time_frame} study plan for approximately {hours_per_week} hours per week to address these knowledge gaps:\n{gap_descriptions}",
            course_id=assessment.get("course_id", ""),
            module_id=assessment.get("module_id"),
            topic_id=assessment.get("topic_id"),
            query_type=QueryType.KNOWLEDGE_GAP,
            model_id=data.get("modelId", "gpt-4"),
            additional_params={
                "purpose": "study_plan",
                "time_frame": time_frame,
                "hours_per_week": hours_per_week
            }
        )
        
        # Process the request
        response = await rag_service.process_query(
            query_request=study_plan_request,
            user_id=current_user.id
        )
        
        # Update the assessment with the study plan
        study_plan = response.response_text
        await firestore_service.update_document(
            collection="knowledge_gaps",
            document_id=assessment_id,
            data={"recommended_study_plan": study_plan}
        )
        
        return {
            "assessment_id": assessment_id,
            "study_plan": study_plan,
            "time_frame": time_frame,
            "hours_per_week": hours_per_week
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating study plan: {str(e)}"
        )