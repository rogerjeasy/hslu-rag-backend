# app/services/course_service.py
import uuid
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from app.core.firebase import firebase
from app.core.exceptions import (
    NotFoundException, 
    PermissionDeniedException, 
    ValidationException,
    FirebaseException
)
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse

logger = logging.getLogger(__name__)

class CourseService:
    """Service for handling course operations in the application"""
    
    def __init__(self):
        """Initialize the course service with Firestore connection"""
        self.db = firebase.get_firestore()
    
    async def get_courses(self, user_id: str) -> List[CourseResponse]:
        try:
            # Get user to verify user exists
            user_doc = self.db.collection("users").document(user_id).get()
            if not user_doc.exists:
                raise NotFoundException(f"User with ID {user_id} not found")
            
            # All users can access all courses, so directly query the courses collection
            courses_ref = self.db.collection("courses")
            course_docs = list(courses_ref.stream())
            
            # Process course documents
            courses = []
            for doc in course_docs:
                course_data = doc.to_dict()
                
                # Get material count
                materials_query = self.db.collection("materials").where("course_id", "==", doc.id).stream()
                materials_count = len(list(materials_query))
                
                # Create course response
                course = CourseResponse(
                    id=doc.id,
                    code=course_data.get("code", ""),
                    name=course_data.get("name", ""),
                    description=course_data.get("description", ""),
                    semester=course_data.get("semester", ""),
                    credits=course_data.get("credits", 0),
                    status=course_data.get("status", "active"),
                    instructor=course_data.get("instructor", ""),
                    materials_count=materials_count,
                    created_at=course_data.get("created_at", datetime.utcnow().isoformat()),
                    updated_at=course_data.get("updated_at", datetime.utcnow().isoformat())
                )
                
                courses.append(course)
            
            return courses
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving courses: {str(e)}")
            raise FirebaseException(f"Error retrieving courses: {str(e)}")
    
    async def get_course(self, course_id: str, user_id: str) -> CourseResponse:
        """
        Get detailed information for a specific course.
        
        Args:
            course_id: The ID of the course
            user_id: The ID of the current user
            
        Returns:
            Course detail object
        """
        try:
            # Check user access to course
            user_doc = self.db.collection("users").document(user_id).get()
            if not user_doc.exists:
                raise NotFoundException(f"User with ID {user_id} not found")
                
            user_data = user_doc.to_dict()
            user_role = user_data.get("role", ["student"])
            enrolled_courses = user_data.get("courses", [])
            
            # Check if role is stored as array or string
            is_student_only = False
            if isinstance(user_role, list):
                # If role is a list, check if it only contains "student" 
                # (no admin or instructor roles)
                is_student_only = all(role == "student" for role in user_role) and len(user_role) > 0
            else:
                # If role is a string, check if it's "student"
                is_student_only = user_role == "student"
            
            # Verify access permission - only restrict students who aren't enrolled
            if is_student_only and course_id not in enrolled_courses:
                raise PermissionDeniedException(f"You do not have access to this course")
            
            # Get course data
            course_doc = self.db.collection("courses").document(course_id).get()
            if not course_doc.exists:
                raise NotFoundException(f"Course with ID {course_id} not found")
                
            course_data = course_doc.to_dict()
            
            # Get course materials count
            materials_query = self.db.collection("materials").where("course_id", "==", course_id).stream()
            materials_count = len(list(materials_query))
            
            # Create course response
            course = CourseResponse(
                id=course_id,
                code=course_data.get("code", ""),
                name=course_data.get("name", ""),
                description=course_data.get("description", ""),
                semester=course_data.get("semester", ""),
                credits=course_data.get("credits", 0),
                status=course_data.get("status", "active"),
                instructor=course_data.get("instructor", ""),
                materials_count=materials_count,
                created_at=course_data.get("created_at", datetime.utcnow().isoformat()),
                updated_at=course_data.get("updated_at", datetime.utcnow().isoformat())
            )
            
            return course
            
        except (NotFoundException, PermissionDeniedException):
            raise
        except Exception as e:
            logger.error(f"Error retrieving course {course_id}: {str(e)}")
            raise FirebaseException(f"Error retrieving course: {str(e)}")
    
    async def create_course(self, course_data: CourseCreate, user_id: str) -> CourseResponse:
        """
        Create a new course.
        
        Args:
            course_data: Course data for creation
            user_id: ID of user creating the course
            
        Returns:
            Created course detail
        """
        try:
            # Check if user is admin or instructor
            user_doc = self.db.collection("users").document(user_id).get()
            if not user_doc.exists:
                raise NotFoundException(f"User with ID {user_id} not found")
                
            user_data = user_doc.to_dict()
            user_role = user_data.get("role", ["student"])
            
            # Check if user has admin or instructor role
            has_permission = False
            
            if isinstance(user_role, list):
                # If role is a list, check if it contains "admin" or "instructor"
                has_permission = any(role in ["admin", "instructor"] for role in user_role)
            else:
                # If role is a string, check if it's "admin" or "instructor"
                has_permission = user_role in ["admin", "instructor"]
            
            if not has_permission:
                raise PermissionDeniedException("Only administrators and instructors can create courses")
            
            # Validate course data
            if not course_data.code or not course_data.name or not course_data.description:
                raise ValidationException("Course code, name, and description are required")
            
            # Generate unique ID based on course code
            course_id = f"{course_data.code.lower()}-{uuid.uuid4().hex[:8]}"
            
            # Prepare course document
            current_time = datetime.utcnow().isoformat()
            course_doc = {
                "code": course_data.code,
                "name": course_data.name,
                "description": course_data.description,
                "semester": course_data.semester,
                "credits": course_data.credits,
                "status": course_data.status,
                "instructor": course_data.instructor,
                "created_at": current_time,
                "updated_at": current_time,
                "created_by": user_id
            }
            
            # Save to Firestore
            self.db.collection("courses").document(course_id).set(course_doc)
            
            # Return created course
            return CourseResponse(
                id=course_id,
                **course_doc,
                materials_count=0
            )
            
        except (NotFoundException, PermissionDeniedException, ValidationException):
            raise
        except Exception as e:
            logger.error(f"Error creating course: {str(e)}")
            raise FirebaseException(f"Error creating course: {str(e)}")
    
    async def update_course(self, course_id: str, course_data: CourseUpdate, user_id: str) -> CourseResponse:
        """
        Update an existing course.
        
        Args:
            course_id: The ID of the course to update
            course_data: Updated course data
            user_id: ID of user updating the course
            
        Returns:
            Updated course detail
        """
        try:
            # Check if user has permission to update
            user_doc = self.db.collection("users").document(user_id).get()
            if not user_doc.exists:
                raise NotFoundException(f"User with ID {user_id} not found")
                
            user_data = user_doc.to_dict()
            user_role = user_data.get("role", ["student"])
            
            # Check if user has admin or instructor role
            has_permission = False
            is_admin = False
            is_instructor = False
            
            if isinstance(user_role, list):
                # If role is a list, check if it contains "admin" or "instructor"
                has_permission = any(role in ["admin", "instructor"] for role in user_role)
                is_admin = "admin" in user_role
                is_instructor = "instructor" in user_role
            else:
                # If role is a string, check if it's "admin" or "instructor"
                has_permission = user_role in ["admin", "instructor"]
                is_admin = user_role == "admin"
                is_instructor = user_role == "instructor"
            
            if not has_permission:
                raise PermissionDeniedException("Only administrators and instructors can update courses")
            
            # Check if course exists
            course_doc = self.db.collection("courses").document(course_id).get()
            if not course_doc.exists:
                raise NotFoundException(f"Course with ID {course_id} not found")
            
            # If instructor, check if they're the course creator
            course_data_dict = course_doc.to_dict()
            if is_instructor and not is_admin and course_data_dict.get("created_by") != user_id:
                raise PermissionDeniedException("You can only update courses you've created")
            
            # Prepare update data
            update_data = {k: v for k, v in course_data.dict(exclude_unset=True).items() if v is not None}
            update_data["updated_at"] = datetime.utcnow().isoformat()
            
            # Update in Firestore
            self.db.collection("courses").document(course_id).update(update_data)
            
            # Get updated course
            updated_course = await self.get_course(course_id=course_id, user_id=user_id)
            
            return updated_course
            
        except (NotFoundException, PermissionDeniedException):
            raise
        except Exception as e:
            logger.error(f"Error updating course {course_id}: {str(e)}")
            raise FirebaseException(f"Error updating course: {str(e)}")
    
    async def delete_course(self, course_id: str, user_id: str) -> bool:
        """
        Delete a course.
        
        Args:
            course_id: The ID of the course to delete
            user_id: ID of user deleting the course
            
        Returns:
            True if deletion was successful
        """
        try:
            # Check if user has permission to delete
            user_doc = self.db.collection("users").document(user_id).get()
            if not user_doc.exists:
                raise NotFoundException(f"User with ID {user_id} not found")
                
            user_data = user_doc.to_dict()
            user_role = user_data.get("role", ["student"])
            
            # Check if user has admin role
            is_admin = False
            
            if isinstance(user_role, list):
                # If role is a list, check if it contains "admin"
                is_admin = "admin" in user_role
            else:
                # If role is a string, check if it's "admin"
                is_admin = user_role == "admin"
            
            if not is_admin:
                raise PermissionDeniedException("Only administrators can delete courses")
            
            # Check if course exists
            course_doc = self.db.collection("courses").document(course_id).get()
            if not course_doc.exists:
                raise NotFoundException(f"Course with ID {course_id} not found")
            
            # Delete course document
            self.db.collection("courses").document(course_id).delete()
            
            # Delete associated materials
            materials_query = self.db.collection("materials").where("course_id", "==", course_id).stream()
            for doc in materials_query:
                doc.reference.delete()
            
            # Remove course from user enrollments (batch operation)
            batch = self.db.batch()
            users_query = self.db.collection("users").where("courses", "array_contains", course_id).stream()
            
            for user_doc in users_query:
                user_ref = self.db.collection("users").document(user_doc.id)
                user_data = user_doc.to_dict()
                courses = user_data.get("courses", [])
                course_enrollments = user_data.get("course_enrollments", {})
                
                if course_id in courses:
                    courses.remove(course_id)
                    if course_id in course_enrollments:
                        course_enrollments.pop(course_id)
                    
                    batch.update(user_ref, {
                        "courses": courses,
                        "course_enrollments": course_enrollments
                    })
            
            # Commit batch updates
            batch.commit()
            
            return True
            
        except (NotFoundException, PermissionDeniedException):
            raise
        except Exception as e:
            logger.error(f"Error deleting course {course_id}: {str(e)}")
            raise FirebaseException(f"Error deleting course: {str(e)}")
    
    async def enroll_student(self, user_id: str, course_id: str) -> bool:
        """
        Enroll a student in a course.
        
        Args:
            user_id: The ID of the student
            course_id: The ID of the course
            
        Returns:
            True if enrollment was successful
        """
        try:
            # Check if course exists
            course_doc = self.db.collection("courses").document(course_id).get()
            if not course_doc.exists:
                raise NotFoundException(f"Course with ID {course_id} not found")
            
            # Check if course is active
            course_data = course_doc.to_dict()
            if course_data.get("status") != "active":
                raise ValidationException(f"Cannot enroll in inactive or archived course")
            
            # Check if user exists
            user_doc = self.db.collection("users").document(user_id).get()
            if not user_doc.exists:
                raise NotFoundException(f"User with ID {user_id} not found")
            
            # Update user's enrolled courses
            user_data = user_doc.to_dict()
            courses = user_data.get("courses", [])
            
            if course_id not in courses:
                courses.append(course_id)
                self.db.collection("users").document(user_id).update({
                    "courses": courses,
                    "course_enrollments": {
                        **user_data.get("course_enrollments", {}),
                        course_id: {
                            "enrolled_at": datetime.utcnow().isoformat(),
                            "progress": 0.0,
                            "last_activity": datetime.utcnow().isoformat()
                        }
                    }
                })
            
            return True
            
        except (NotFoundException, ValidationException):
            raise
        except Exception as e:
            logger.error(f"Error enrolling user {user_id} in course {course_id}: {str(e)}")
            raise FirebaseException(f"Error enrolling in course: {str(e)}")
    
    async def unenroll_student(self, user_id: str, course_id: str) -> bool:
        """
        Unenroll a student from a course.
        
        Args:
            user_id: The ID of the student
            course_id: The ID of the course
            
        Returns:
            True if unenrollment was successful
        """
        try:
            # Check if user exists
            user_doc = self.db.collection("users").document(user_id).get()
            if not user_doc.exists:
                raise NotFoundException(f"User with ID {user_id} not found")
            
            # Update user's enrolled courses
            user_data = user_doc.to_dict()
            courses = user_data.get("courses", [])
            course_enrollments = user_data.get("course_enrollments", {})
            
            if course_id in courses:
                courses.remove(course_id)
                if course_id in course_enrollments:
                    course_enrollments.pop(course_id)
                
                self.db.collection("users").document(user_id).update({
                    "courses": courses,
                    "course_enrollments": course_enrollments
                })
            
            return True
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error unenrolling user {user_id} from course {course_id}: {str(e)}")
            raise FirebaseException(f"Error unenrolling from course: {str(e)}")