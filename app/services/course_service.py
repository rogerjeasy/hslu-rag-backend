import uuid
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from app.core.firebase import firebase
from app.core.exceptions import NotFoundException

logger = logging.getLogger(__name__)

class CourseService:
    """Service for handling course operations in the HSLU RAG application"""
    
    def __init__(self):
        """Initialize the course service with Firestore connection"""
        self.db = firebase.get_firestore() if firebase.app else None
    
    async def get_courses(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get a list of all courses available to the user.
        
        Args:
            user_id: The ID of the current user
            
        Returns:
            List of course summary objects
        """
        try:
            # If in mock mode, return sample courses
            if self.db is None:
                return [
                    {
                        "id": "data-science-101",
                        "title": "Introduction to Data Science",
                        "code": "DS101",
                        "description": "Fundamentals of data science and analytics",
                        "semester": "Fall",
                        "year": 2023,
                        "instructor": "Dr. Smith",
                        "module_count": 3,
                        "material_count": 12
                    },
                    {
                        "id": "machine-learning",
                        "title": "Machine Learning",
                        "code": "ML201",
                        "description": "Foundations of machine learning algorithms",
                        "semester": "Spring",
                        "year": 2023,
                        "instructor": "Dr. Johnson",
                        "module_count": 4,
                        "material_count": 15
                    }
                ]
            
            # Determine user's role and course access
            user_doc = self.db.collection("users").document(user_id).get()
            if not user_doc.exists:
                raise NotFoundException(f"User with ID {user_id} not found")
                
            user_data = user_doc.to_dict()
            user_role = user_data.get("role", "student")
            
            # If admin, get all courses
            if user_role == "admin":
                courses_ref = self.db.collection("courses")
            else:
                # Get only enrolled courses for students
                enrolled_courses = user_data.get("courses", [])
                if not enrolled_courses:
                    return []
                courses_ref = self.db.collection("courses").where("id", "in", enrolled_courses)
            
            # Query and format courses
            courses = []
            for doc in courses_ref.stream():
                course_data = doc.to_dict()
                
                # Get module and material counts
                modules = course_data.get("modules", [])
                materials_query = self.db.collection("materials").where("course_id", "==", doc.id).stream()
                materials = list(materials_query)
                
                # Create course summary
                course_summary = {
                    "id": doc.id,
                    "title": course_data.get("title", ""),
                    "code": course_data.get("code", ""),
                    "description": course_data.get("description", ""),
                    "semester": course_data.get("semester", ""),
                    "year": course_data.get("year", None),
                    "instructor": course_data.get("instructor", ""),
                    "module_count": len(modules),
                    "material_count": len(materials)
                }
                
                courses.append(course_summary)
            
            return courses
            
        except Exception as e:
            logger.error(f"Error retrieving courses: {str(e)}")
            raise
    
    async def get_course(self, course_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific course.
        
        Args:
            course_id: The ID of the course
            user_id: The ID of the current user
            
        Returns:
            Course detail object
        """
        try:
            # If in mock mode, return sample course detail
            if self.db is None:
                return {
                    "id": course_id,
                    "title": "Introduction to Data Science",
                    "code": "DS101",
                    "description": "Fundamentals of data science and analytics",
                    "semester": "Fall",
                    "year": 2023,
                    "instructor": "Dr. Smith",
                    "modules": [
                        {
                            "id": "module-1",
                            "title": "Data Science Foundations",
                            "description": "Introduction to core concepts",
                            "order": 1,
                            "topics": [
                                {
                                    "id": "topic-1",
                                    "title": "What is Data Science?",
                                    "description": "Overview of the field",
                                    "order": 1
                                }
                            ]
                        }
                    ],
                    "materials": [
                        {
                            "id": "material-1",
                            "title": "Introduction Slides",
                            "description": "Course overview slides",
                            "type": "lecture",
                            "module_id": "module-1",
                            "topic_id": "topic-1",
                            "source_url": "slides/intro.pdf",
                            "uploaded_at": datetime.utcnow().isoformat()
                        }
                    ],
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                    "student_count": 25
                }
            
            # Check user access to course
            user_doc = self.db.collection("users").document(user_id).get()
            if not user_doc.exists:
                raise NotFoundException(f"User with ID {user_id} not found")
                
            user_data = user_doc.to_dict()
            user_role = user_data.get("role", "student")
            enrolled_courses = user_data.get("courses", [])
            
            # Verify access permission
            if user_role != "admin" and course_id not in enrolled_courses:
                raise NotFoundException(f"Course with ID {course_id} not found or not accessible")
            
            # Get course data
            course_doc = self.db.collection("courses").document(course_id).get()
            if not course_doc.exists:
                raise NotFoundException(f"Course with ID {course_id} not found")
                
            course_data = course_doc.to_dict()
            
            # Get course materials
            materials_query = self.db.collection("materials").where("course_id", "==", course_id).stream()
            materials = [doc.to_dict() for doc in materials_query]
            
            # Get student count
            students_query = self.db.collection("users").where("courses", "array_contains", course_id).stream()
            student_count = len(list(students_query))
            
            # Create detailed course object
            course_detail = {
                "id": course_id,
                "title": course_data.get("title", ""),
                "code": course_data.get("code", ""),
                "description": course_data.get("description", ""),
                "semester": course_data.get("semester", ""),
                "year": course_data.get("year", None),
                "instructor": course_data.get("instructor", ""),
                "modules": course_data.get("modules", []),
                "materials": materials,
                "created_at": course_data.get("created_at", datetime.utcnow().isoformat()),
                "updated_at": course_data.get("updated_at", None),
                "student_count": student_count
            }
            
            return course_detail
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving course {course_id}: {str(e)}")
            raise
    
    async def create_course(self, course_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new course.
        
        Args:
            course_data: Course data for creation
            
        Returns:
            Created course detail
        """
        try:
            # If in mock mode, return sample response
            if self.db is None:
                return {
                    "id": f"course-{uuid.uuid4()}",
                    "title": course_data.get("title", ""),
                    "code": course_data.get("code", ""),
                    "description": course_data.get("description", ""),
                    "semester": course_data.get("semester", ""),
                    "year": course_data.get("year", None),
                    "instructor": course_data.get("instructor", ""),
                    "modules": course_data.get("modules", []),
                    "materials": [],
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": None,
                    "student_count": 0
                }
            
            # Generate unique ID based on course code
            course_id = f"{course_data.get('code', '').lower()}-{uuid.uuid4().hex[:8]}"
            
            # Prepare course document
            course_doc = {
                "title": course_data.get("title", ""),
                "code": course_data.get("code", ""),
                "description": course_data.get("description", ""),
                "semester": course_data.get("semester", ""),
                "year": course_data.get("year", None),
                "instructor": course_data.get("instructor", ""),
                "modules": course_data.get("modules", []),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": None
            }
            
            # Save to Firestore
            self.db.collection("courses").document(course_id).set(course_doc)
            
            # Return created course with ID
            return {
                "id": course_id,
                **course_doc,
                "materials": [],
                "student_count": 0
            }
            
        except Exception as e:
            logger.error(f"Error creating course: {str(e)}")
            raise
    
    async def update_course(self, course_id: str, course_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing course.
        
        Args:
            course_id: The ID of the course to update
            course_data: Updated course data
            
        Returns:
            Updated course detail
        """
        try:
            # If in mock mode, return sample response
            if self.db is None:
                return {
                    "id": course_id,
                    "title": course_data.get("title", "Updated Course"),
                    "code": course_data.get("code", "CODE101"),
                    "description": course_data.get("description", ""),
                    "semester": course_data.get("semester", ""),
                    "year": course_data.get("year", None),
                    "instructor": course_data.get("instructor", ""),
                    "modules": course_data.get("modules", []),
                    "materials": [],
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                    "student_count": 0
                }
            
            # Check if course exists
            course_doc = self.db.collection("courses").document(course_id).get()
            if not course_doc.exists:
                raise NotFoundException(f"Course with ID {course_id} not found")
            
            # Prepare update data
            update_data = {k: v for k, v in course_data.items() if v is not None}
            update_data["updated_at"] = datetime.utcnow().isoformat()
            
            # Update in Firestore
            self.db.collection("courses").document(course_id).update(update_data)
            
            # Get updated course
            updated_course = await self.get_course(course_id=course_id, user_id="admin")  # Use admin ID for unrestricted access
            
            return updated_course
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error updating course {course_id}: {str(e)}")
            raise
    
    async def delete_course(self, course_id: str) -> bool:
        """
        Delete a course.
        
        Args:
            course_id: The ID of the course to delete
            
        Returns:
            True if deletion was successful
        """
        try:
            # If in mock mode, return success
            if self.db is None:
                return True
            
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
                
                if course_id in courses:
                    courses.remove(course_id)
                    batch.update(user_ref, {"courses": courses})
            
            # Commit batch updates
            batch.commit()
            
            return True
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error deleting course {course_id}: {str(e)}")
            raise
    
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
            # If in mock mode, return success
            if self.db is None:
                return True
            
            # Check if course exists
            course_doc = self.db.collection("courses").document(course_id).get()
            if not course_doc.exists:
                raise NotFoundException(f"Course with ID {course_id} not found")
            
            # Check if user exists
            user_doc = self.db.collection("users").document(user_id).get()
            if not user_doc.exists:
                raise NotFoundException(f"User with ID {user_id} not found")
            
            # Update user's enrolled courses
            user_data = user_doc.to_dict()
            courses = user_data.get("courses", [])
            
            if course_id not in courses:
                courses.append(course_id)
                self.db.collection("users").document(user_id).update({"courses": courses})
            
            return True
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error enrolling user {user_id} in course {course_id}: {str(e)}")
            raise
    
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
            # If in mock mode, return success
            if self.db is None:
                return True
            
            # Check if user exists
            user_doc = self.db.collection("users").document(user_id).get()
            if not user_doc.exists:
                raise NotFoundException(f"User with ID {user_id} not found")
            
            # Update user's enrolled courses
            user_data = user_doc.to_dict()
            courses = user_data.get("courses", [])
            
            if course_id in courses:
                courses.remove(course_id)
                self.db.collection("users").document(user_id).update({"courses": courses})
            
            return True
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error unenrolling user {user_id} from course {course_id}: {str(e)}")
            raise