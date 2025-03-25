from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body, status, Query
from typing import Dict, Any, List, Optional
from app.schemas.practice_questions import (
    QuestionSet, QuestionSetSummary, DifficultyLevel, QuestionType
)
from app.dto.practice_questions_dto import (
    FrontendPracticeQuestionsDTO, BackendPracticeQuestionsDTO
)
from app.services.firestore_service import FirestoreService
from app.services.rag_service import RAGService
from app.services.retrieval_service import RetrievalService
from app.services.generation_service import GenerationService
from app.schemas.query import PracticeQuestionsRequest, QueryType
from app.core.security import get_current_user
from app.schemas.auth import UserResponse
from app.core.firebase import firebase

router = APIRouter(prefix="/practice-questions", tags=["practice-questions"])

# Initialize services
retrieval_service = RetrievalService()
generation_service = GenerationService()
firestore_service = FirestoreService(firebase.get_firestore())
rag_service = RAGService(
    retrieval_service=retrieval_service,
    generation_service=generation_service,
    firestore_service=firestore_service
)

@router.post("/", response_model=Dict[str, Any])
async def create_practice_questions(
    data: Dict[str, Any] = Body(...),
    current_user: UserResponse = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new set of practice questions for a topic"""
    try:
        # Validate required fields
        if not data.get("topic"):
            raise ValueError("Topic is required to generate practice questions")
        
        if not data.get("courseId"):
            raise ValueError("Course ID is required")
            
        # Create a practice questions request
        practice_questions_request = PracticeQuestionsRequest(
            text=data.get("topic", ""),
            course_id=data.get("courseId", ""),
            module_id=data.get("moduleId"),
            topic_id=data.get("topicId"),
            query_type=QueryType.PRACTICE_QUESTIONS,
            model_id=data.get("modelId", "gpt-4"),
            question_count=data.get("questionCount", 5),
            difficulty=data.get("difficulty", "medium"),
            question_types=data.get("questionTypes", ["multiple_choice", "short_answer"])
        )
        
        # Process the practice questions request
        response = await rag_service.process_query(
            query_request=practice_questions_request,
            user_id=current_user.id
        )
        
        # Return the question set summary using DTO
        result = {
            "id": response.conversation_id,
            "title": data.get("topic", "Practice Questions"),
            "courseId": data.get("courseId", ""),
            "moduleId": data.get("moduleId"),
            "topicId": data.get("topicId"),
            "createdAt": response.timestamp.isoformat(),
            "message": "Practice questions created successfully"
        }
        
        return result
        
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Log the error for debugging
        print(f"Error creating practice questions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create practice questions: {str(e)}"
        )

@router.get("/", response_model=List[Dict[str, Any]])
async def get_practice_question_sets(
    course_id: Optional[str] = Query(None, description="Filter by course ID"),
    limit: int = Query(50, description="Maximum number of records to return"),
    offset: int = Query(0, description="Number of records to skip"),
    current_user: UserResponse = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Get list of user's practice question sets"""
    try:
        # Get question sets from firestore
        question_sets_data = await firestore_service.get_user_practice_questions(
            user_id=current_user.id,
            course_id=course_id,
            limit=limit,
            offset=offset
        )
        
        # Convert to frontend format using DTO
        question_sets = []
        for data in question_sets_data:
            # Convert database timestamp to datetime if needed
            created_at = data.get("createdAt")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            
            updated_at = data.get("updatedAt", created_at)
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)
                
            # Create a summary object
            summary = QuestionSetSummary(
                id=data.get("id", ""),
                title=data.get("title", ""),
                course_id=data.get("courseId", ""),
                module_id=data.get("moduleId"),
                topic_id=data.get("topicId"),
                created_at=created_at,
                updated_at=updated_at,
                difficulty=data.get("difficulty", "medium"),
                question_count=len(data.get("questions", [])),
                types=[question.get("type") for question in data.get("questions", [])]
            )
            
            # Convert to frontend format
            question_sets.append(BackendPracticeQuestionsDTO.summary_to_frontend(summary))
            
        return question_sets
    except Exception as e:
        # Log the error for debugging
        print(f"Error retrieving practice question sets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve practice question sets: {str(e)}"
        )

@router.get("/{question_set_id}", response_model=Dict[str, Any])
async def get_practice_question_set(
    question_set_id: str,
    current_user: UserResponse = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get a specific practice question set"""
    try:
        # Get the question set data from firestore
        question_set_data = await firestore_service.get_practice_questions(
            question_set_id=question_set_id,
            user_id=current_user.id
        )
        
        if not question_set_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Practice question set with ID {question_set_id} not found"
            )
            
        # Convert database timestamp to datetime if needed
        created_at = question_set_data.get("createdAt")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        updated_at = question_set_data.get("updatedAt", created_at)
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
            
        # Convert questions to backend model
        questions = []
        for q_data in question_set_data.get("questions", []):
            questions.append(FrontendPracticeQuestionsDTO.question_to_backend(q_data))
            
        # Create QuestionSet model
        question_set = QuestionSet(
            id=question_set_data.get("id", ""),
            title=question_set_data.get("title", ""),
            description=question_set_data.get("description"),
            course_id=question_set_data.get("courseId", ""),
            module_id=question_set_data.get("moduleId"),
            topic_id=question_set_data.get("topicId"),
            user_id=question_set_data.get("userId", current_user.id),
            created_at=created_at,
            updated_at=updated_at,
            difficulty=question_set_data.get("difficulty", "medium"),
            questions=questions,
            metadata=question_set_data.get("metadata", {})
        )
        
        # Convert to frontend format using DTO
        return BackendPracticeQuestionsDTO.question_set_to_frontend(question_set)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the error for debugging
        print(f"Error retrieving practice question set: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve practice question set: {str(e)}"
        )

@router.delete("/{question_set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_practice_question_set(
    question_set_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a practice question set"""
    try:
        # First ensure the user has access to this question set
        question_set = await firestore_service.get_practice_questions(
            question_set_id=question_set_id,
            user_id=current_user.id
        )
        
        if not question_set:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Practice question set with ID {question_set_id} not found"
            )
            
        # Check if this user owns the question set
        if question_set.get("userId") != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this practice question set"
            )
        
        # Delete the question set
        await firestore_service.delete_document(
            collection="practice_questions",
            document_id=question_set_id
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the error for debugging
        print(f"Error deleting practice question set: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete practice question set: {str(e)}"
        )

@router.put("/{question_set_id}", response_model=Dict[str, Any])
async def update_practice_question_set(
    question_set_id: str,
    data: Dict[str, Any] = Body(...),
    current_user: UserResponse = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update a practice question set's metadata"""
    try:
        # First ensure the user has access to this question set
        question_set_data = await firestore_service.get_practice_questions(
            question_set_id=question_set_id,
            user_id=current_user.id
        )
        
        if not question_set_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Practice question set with ID {question_set_id} not found"
            )
            
        # Check if this user owns the question set
        if question_set_data.get("userId") != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this practice question set"
            )
        
        # Update only allowed fields
        update_data = {}
        if "title" in data:
            update_data["title"] = data["title"]
        if "description" in data:
            update_data["description"] = data["description"]
        
        # Add timestamp for update
        update_data["updatedAt"] = datetime.utcnow().isoformat()
        
        # Update the document
        if update_data:
            await firestore_service.update_document(
                collection="practice_questions",
                document_id=question_set_id,
                data=update_data
            )
            
            # Update local copy for response
            question_set_data.update(update_data)
            
            # Convert timestamps to datetime objects
            created_at = question_set_data.get("createdAt")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
                
            updated_at = question_set_data.get("updatedAt")
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)
                
            # Convert questions to backend model
            questions = []
            for q_data in question_set_data.get("questions", []):
                questions.append(FrontendPracticeQuestionsDTO.question_to_backend(q_data))
                
            # Create QuestionSet model
            question_set = QuestionSet(
                id=question_set_data.get("id", ""),
                title=question_set_data.get("title", ""),
                description=question_set_data.get("description"),
                course_id=question_set_data.get("courseId", ""),
                module_id=question_set_data.get("moduleId"),
                topic_id=question_set_data.get("topicId"),
                user_id=question_set_data.get("userId", current_user.id),
                created_at=created_at,
                updated_at=updated_at,
                difficulty=question_set_data.get("difficulty", "medium"),
                questions=questions,
                metadata=question_set_data.get("metadata", {})
            )
            
            # Return updated data in frontend format
            return BackendPracticeQuestionsDTO.question_set_to_frontend(question_set)
        else:
            # If no fields were updated, return the original data
            return question_set_data
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the error for debugging
        print(f"Error updating practice question set: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update practice question set: {str(e)}"
        )

@router.post("/{question_set_id}/submit", response_model=Dict[str, Any])
async def submit_practice_question_answers(
    question_set_id: str,
    answers: Dict[str, Any] = Body(...),
    current_user: UserResponse = Depends(get_current_user)
) -> Dict[str, Any]:
    """Submit answers to practice questions and get results"""
    try:
        # First ensure the user has access to this question set
        question_set_data = await firestore_service.get_practice_questions(
            question_set_id=question_set_id,
            user_id=current_user.id
        )
        
        if not question_set_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Practice question set with ID {question_set_id} not found"
            )
        
        # Validate answers format
        if not isinstance(answers, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Answers must be provided as a dictionary with question IDs as keys"
            )
            
        # Get question IDs from the question set
        question_ids = [q.get("id") for q in question_set_data.get("questions", [])]
        
        # Check if any submitted answers don't correspond to questions
        invalid_question_ids = [qid for qid in answers.keys() if qid not in question_ids]
        if invalid_question_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid question IDs in submission: {', '.join(invalid_question_ids)}"
            )
        
        # Process answers and generate results
        results = {
            "total_questions": len(question_set_data.get("questions", [])),
            "answered_questions": len(answers),
            "correct_answers": 0,
            "question_results": []
        }
        
        for question in question_set_data.get("questions", []):
            question_id = question.get("id")
            user_answer = answers.get(question_id)
            
            question_result = {
                "question_id": question_id,
                "is_correct": False,
                "correct_answer": None,
                "explanation": question.get("explanation", ""),
                "user_answer": user_answer
            }
            
            # Skip if no answer provided for this question
            if user_answer is None:
                question_result["status"] = "unanswered"
                results["question_results"].append(question_result)
                continue
                
            # Check answer based on question type
            if question.get("type") == "multiple_choice":
                correct_option = next((option for option in question.get("options", []) if option.get("isCorrect")), None)
                question_result["correct_answer"] = correct_option.get("id") if correct_option else None
                question_result["is_correct"] = user_answer == question_result["correct_answer"]
                question_result["status"] = "correct" if question_result["is_correct"] else "incorrect"
            
            elif question.get("type") == "true_false":
                question_result["correct_answer"] = question.get("correctAnswer")
                # Convert string "true"/"false" to boolean if needed
                if isinstance(user_answer, str):
                    user_answer = user_answer.lower() == "true"
                question_result["is_correct"] = user_answer == question_result["correct_answer"]
                question_result["status"] = "correct" if question_result["is_correct"] else "incorrect"
            
            elif question.get("type") == "short_answer":
                # For short answer, just provide the sample answer
                question_result["correct_answer"] = question.get("sampleAnswer")
                # Short answer needs manual grading or more complex NLP
                question_result["requires_review"] = True
                question_result["status"] = "needs_review"
                
            elif question.get("type") == "fill_in_blank":
                correct_answers = question.get("blanks", [])
                # Simple exact match for now - could be improved with fuzzy matching
                question_result["correct_answer"] = correct_answers
                
                # Handle both string and list user answers
                if isinstance(user_answer, str) and len(correct_answers) == 1:
                    question_result["is_correct"] = user_answer.lower() == correct_answers[0].lower()
                elif isinstance(user_answer, list) and len(user_answer) == len(correct_answers):
                    # Check each blank
                    matches = [ua.lower() == ca.lower() for ua, ca in zip(user_answer, correct_answers)]
                    question_result["is_correct"] = all(matches)
                    question_result["partial_matches"] = matches
                else:
                    question_result["is_correct"] = False
                    
                question_result["status"] = "correct" if question_result["is_correct"] else "incorrect"
                
            elif question.get("type") == "matching":
                correct_matches = {item.get("id"): item.get("rightText") for item in question.get("items", [])}
                question_result["correct_answer"] = correct_matches
                
                # Check if user provided all matches and they're correct
                if isinstance(user_answer, dict) and set(user_answer.keys()) == set(correct_matches.keys()):
                    matches = [user_answer[item_id] == correct_text for item_id, correct_text in correct_matches.items()]
                    question_result["is_correct"] = all(matches)
                    question_result["partial_matches"] = matches
                else:
                    question_result["is_correct"] = False
                    
                question_result["status"] = "correct" if question_result["is_correct"] else "incorrect"
            
            # Add result to list
            results["question_results"].append(question_result)
            
            # Update correct answer count
            if question_result.get("is_correct", False):
                results["correct_answers"] += 1
        
        # Calculate score percentage
        scored_questions = [q for q in results["question_results"] if q.get("status") in ["correct", "incorrect"]]
        if scored_questions:
            correct_count = sum(1 for q in scored_questions if q.get("is_correct", False))
            results["score_percentage"] = round((correct_count / len(scored_questions)) * 100, 1)
        else:
            results["score_percentage"] = None
        
        # Save the submission to firestore
        submission_data = {
            "userId": current_user.id,
            "questionSetId": question_set_id,
            "courseId": question_set_data.get("courseId"),
            "moduleId": question_set_data.get("moduleId"),
            "topicId": question_set_data.get("topicId"),
            "timestamp": datetime.utcnow().isoformat(),
            "answers": answers,
            "results": results
        }
        
        submission_id = await firestore_service.add_document(
            collection="question_submissions",
            data=submission_data
        )
        
        # Add submission ID to results
        results["submission_id"] = submission_id
        
        return results
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the error for debugging
        print(f"Error processing question submission: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process question submission: {str(e)}"
        )