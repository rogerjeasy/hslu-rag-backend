import uuid
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from app.core.firebase import firebase
from app.core.exceptions import NotFoundException
from app.rag.llm_connector import LLMConnector
from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)

class StudyGuideService:
    """Service for generating and managing study guides"""
    
    def __init__(self):
        """Initialize the study guide service"""
        self.db = firebase.get_firestore() if firebase.app else None
        self.llm_connector = LLMConnector()
        self.retriever = Retriever()
    
    async def get_study_guides(
        self,
        user_id: str,
        course_id: Optional[str] = None,
        topic_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all study guides created by the user, with optional filtering.
        
        Args:
            user_id: User ID
            course_id: Optional course ID filter
            topic_id: Optional topic ID filter
            
        Returns:
            List of study guide objects
        """
        try:
            # For mock mode, return sample data
            if self.db is None:
                return [
                    {
                        "id": "guide-1",
                        "title": "Complete Machine Learning Study Guide",
                        "course_id": "machine-learning",
                        "topic_ids": ["neural-networks", "deep-learning"],
                        "guide_type": "summary",
                        "sections": [
                            {
                                "title": "Introduction to Neural Networks",
                                "content": "Neural networks are computational models inspired by the human brain...",
                                "order": 1
                            },
                            {
                                "title": "Deep Learning Foundations",
                                "content": "Deep learning is a subset of machine learning...",
                                "order": 2
                            }
                        ],
                        "created_at": datetime.utcnow().isoformat(),
                        "created_by": user_id
                    }
                ]
            
            # Build query
            query = self.db.collection("study_guides").where("created_by", "==", user_id)
            
            # Apply filters
            if course_id:
                query = query.where("course_id", "==", course_id)
                
            if topic_id:
                query = query.where("topic_ids", "array_contains", topic_id)
            
            # Execute query and format results
            guides = []
            for doc in query.stream():
                guide_data = doc.to_dict()
                guide_data["id"] = doc.id
                guides.append(guide_data)
                
            return guides
            
        except Exception as e:
            logger.error(f"Error retrieving study guides: {str(e)}")
            raise
    
    async def get_study_guide(self, guide_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get a specific study guide by ID.
        
        Args:
            guide_id: Study guide ID
            user_id: User ID (for authorization)
            
        Returns:
            Study guide object
        """
        try:
            # For mock mode, return sample data
            if self.db is None:
                return {
                    "id": guide_id,
                    "title": "Complete Machine Learning Study Guide",
                    "course_id": "machine-learning",
                    "topic_ids": ["neural-networks", "deep-learning"],
                    "guide_type": "summary",
                    "sections": [
                        {
                            "title": "Introduction to Neural Networks",
                            "content": "Neural networks are computational models inspired by the human brain...",
                            "order": 1
                        },
                        {
                            "title": "Deep Learning Foundations",
                            "content": "Deep learning is a subset of machine learning...",
                            "order": 2
                        }
                    ],
                    "created_at": datetime.utcnow().isoformat(),
                    "created_by": user_id
                }
            
            # Get guide document
            guide_doc = self.db.collection("study_guides").document(guide_id).get()
            
            if not guide_doc.exists:
                raise NotFoundException(f"Study guide with ID {guide_id} not found")
            
            # Check authorization
            guide_data = guide_doc.to_dict()
            if guide_data.get("created_by") != user_id:
                raise NotFoundException(f"Study guide with ID {guide_id} not found")
            
            # Format and return
            guide_data["id"] = guide_id
            return guide_data
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving study guide {guide_id}: {str(e)}")
            raise
    
    async def create_study_guide(
        self,
        user_id: str,
        guide_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new AI-generated study guide.
        
        Args:
            user_id: User ID
            guide_request: Study guide generation parameters
            
        Returns:
            Generated study guide
        """
        try:
            # For mock mode, return sample data
            if self.db is None:
                guide_id = f"guide-{uuid.uuid4().hex[:8]}"
                return {
                    "id": guide_id,
                    "title": guide_request.get("title", "Study Guide"),
                    "course_id": guide_request.get("course_id"),
                    "topic_ids": guide_request.get("topic_ids"),
                    "guide_type": guide_request.get("guide_type", "summary"),
                    "sections": [
                        {
                            "title": "Introduction",
                            "content": "This is an AI-generated study guide based on your course materials...",
                            "order": 1
                        },
                        {
                            "title": "Key Concepts",
                            "content": "Here are the most important concepts to understand...",
                            "order": 2
                        },
                        {
                            "title": "Summary",
                            "content": "In conclusion, these topics form the foundation of the subject...",
                            "order": 3
                        }
                    ],
                    "created_at": datetime.utcnow().isoformat(),
                    "created_by": user_id
                }
            
            # Generate title if not provided
            title = guide_request.get("title")
            if not title:
                if guide_request.get("topic_ids"):
                    title = f"{guide_request.get('guide_type', 'Summary')} Guide: Selected Topics"
                else:
                    # Get course title for better naming
                    course_doc = self.db.collection("courses").document(guide_request.get("course_id")).get()
                    course_title = "Course"
                    if course_doc.exists:
                        course_title = course_doc.to_dict().get("title", "Course")
                    title = f"{guide_request.get('guide_type', 'Summary')} Guide: {course_title}"
            
            # Retrieve relevant content for the guide
            retrieved_chunks = await self.retriever.retrieve(
                query=f"Generate a {guide_request.get('guide_type', 'summary')} study guide",
                course_id=guide_request.get("course_id"),
                topic_ids=guide_request.get("topic_ids"),
                limit=10  # Get more chunks for a comprehensive guide
            )
            
            # Generate guide content using LLM
            prompt = self._build_study_guide_prompt(
                guide_type=guide_request.get("guide_type", "summary"),
                focus_areas=guide_request.get("focus_areas", []),
                max_length=guide_request.get("max_length", 2000),
                include_examples=guide_request.get("include_examples", True),
                include_diagrams=guide_request.get("include_diagrams", False)
            )
            
            response = await self.llm_connector.generate_response(
                query=prompt,
                retrieved_chunks=retrieved_chunks,
                conversation_history=[]
            )
            
            # Process LLM response into sections
            sections = self._parse_sections(response["content"])
            
            # Prepare guide document
            guide_id = f"guide-{uuid.uuid4().hex}"
            guide_data = {
                "title": title,
                "course_id": guide_request.get("course_id"),
                "topic_ids": guide_request.get("topic_ids"),
                "guide_type": guide_request.get("guide_type", "summary"),
                "sections": sections,
                "created_at": datetime.utcnow().isoformat(),
                "created_by": user_id
            }
            
            # Save to Firestore
            self.db.collection("study_guides").document(guide_id).set(guide_data)
            
            # Return complete guide with ID
            return {
                "id": guide_id,
                **guide_data
            }
            
        except Exception as e:
            logger.error(f"Error creating study guide: {str(e)}")
            raise
    
    async def delete_study_guide(self, guide_id: str, user_id: str) -> bool:
        """
        Delete a study guide.
        
        Args:
            guide_id: Study guide ID
            user_id: User ID (for authorization)
            
        Returns:
            True if deletion was successful
        """
        try:
            # For mock mode, return success
            if self.db is None:
                return True
            
            # Get guide document
            guide_doc = self.db.collection("study_guides").document(guide_id).get()
            
            if not guide_doc.exists:
                raise NotFoundException(f"Study guide with ID {guide_id} not found")
            
            # Check authorization
            guide_data = guide_doc.to_dict()
            if guide_data.get("created_by") != user_id:
                raise NotFoundException(f"Study guide with ID {guide_id} not found")
            
            # Delete document
            self.db.collection("study_guides").document(guide_id).delete()
            
            return True
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error deleting study guide {guide_id}: {str(e)}")
            raise
    
    def _build_study_guide_prompt(
        self,
        guide_type: str,
        focus_areas: List[str],
        max_length: int,
        include_examples: bool,
        include_diagrams: bool
    ) -> str:
        """
        Build a prompt for generating a study guide.
        
        Args:
            guide_type: Type of guide to generate
            focus_areas: Specific areas to focus on
            max_length: Maximum length in words
            include_examples: Whether to include examples
            include_diagrams: Whether to include diagram descriptions
            
        Returns:
            Formatted prompt
        """
        prompt = f"Generate a {guide_type} study guide"
        
        if focus_areas:
            prompt += f" focusing on the following areas: {', '.join(focus_areas)}"
        
        prompt += f". The guide should be structured with clear sections and should not exceed {max_length} words."
        
        if include_examples:
            prompt += " Include practical examples to illustrate key concepts."
        
        if include_diagrams:
            prompt += " Include descriptions of diagrams or visualizations where helpful."
        
        prompt += " Format each section with a clear title followed by content."
        
        return prompt
    
    def _parse_sections(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse the LLM response into structured sections.
        
        Args:
            content: Raw LLM response
            
        Returns:
            List of section objects
        """
        # This is a simple implementation - could be enhanced with better parsing
        lines = content.split("\n")
        sections = []
        current_section = None
        section_content = []
        order = 1
        
        for line in lines:
            # Heuristic: A section title is likely a short line that doesn't end with punctuation
            if (len(line.strip()) > 0 and len(line.strip()) < 60 and 
                not line.strip().endswith(('.', ':', '?', '!'))):
                
                # Save previous section if exists
                if current_section:
                    sections.append({
                        "title": current_section,
                        "content": "\n".join(section_content).strip(),
                        "order": order
                    })
                    order += 1
                
                # Start new section
                current_section = line.strip()
                section_content = []
            elif current_section:
                section_content.append(line)
        
        # Add the last section
        if current_section:
            sections.append({
                "title": current_section,
                "content": "\n".join(section_content).strip(),
                "order": order
            })
        
        # If no sections were identified, create a single section
        if not sections:
            sections.append({
                "title": "Study Guide",
                "content": content.strip(),
                "order": 1
            })
        
        return sections