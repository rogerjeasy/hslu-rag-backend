import uuid
from typing import List, Dict, Any, Optional, Union
import logging
from datetime import datetime

from app.core.firebase import firebase
from app.core.exceptions import NotFoundException
from app.rag.llm_connector import LLMConnector
from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)

class PracticeService:
    """Service for generating and managing practice question sets"""
    
    def __init__(self):
        """Initialize the practice service"""
        self.db = firebase.get_firestore() if firebase.app else None
        self.llm_connector = LLMConnector()
        self.retriever = Retriever()
    
    async def get_practice_sets(
        self,
        user_id: str,
        course_id: Optional[str] = None,
        topic_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all practice sets created by the user, with optional filtering.
        
        Args:
            user_id: User ID
            course_id: Optional course ID filter
            topic_id: Optional topic ID filter
            
        Returns:
            List of practice set objects
        """
        try:
            # For mock mode, return sample data
            if self.db is None:
                return [
                    {
                        "id": "practice-1",
                        "title": "Machine Learning Quiz",
                        "course_id": "machine-learning",
                        "topic_ids": ["neural-networks", "deep-learning"],
                        "question_count": 5,
                        "difficulty": "medium",
                        "questions": [
                            {
                                "id": "q1",
                                "question": "What is the primary goal of supervised learning?",
                                "type": "multiple_choice",
                                "options": [
                                    "Finding hidden patterns in unlabeled data",
                                    "Predicting outputs based on labeled training data",
                                    "Reinforcing actions based on rewards",
                                    "Clustering similar data points"
                                ],
                                "correct_answer": "Predicting outputs based on labeled training data",
                                "explanation": "Supervised learning uses labeled training data to learn a function that maps inputs to outputs."
                            }
                        ],
                        "created_at": datetime.utcnow().isoformat(),
                        "created_by": user_id
                    }
                ]
            
            # Build query
            query = self.db.collection("practice_sets").where("created_by", "==", user_id)
            
            # Apply filters
            if course_id:
                query = query.where("course_id", "==", course_id)
                
            if topic_id:
                query = query.where("topic_ids", "array_contains", topic_id)
            
            # Execute query and format results
            practice_sets = []
            for doc in query.stream():
                practice_data = doc.to_dict()
                practice_data["id"] = doc.id
                practice_sets.append(practice_data)
                
            return practice_sets
            
        except Exception as e:
            logger.error(f"Error retrieving practice sets: {str(e)}")
            raise
    
    async def get_practice_set(self, practice_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get a specific practice set by ID.
        
        Args:
            practice_id: Practice set ID
            user_id: User ID (for authorization)
            
        Returns:
            Practice set object
        """
        try:
            # For mock mode, return sample data
            if self.db is None:
                return {
                    "id": practice_id,
                    "title": "Machine Learning Quiz",
                    "course_id": "machine-learning",
                    "topic_ids": ["neural-networks", "deep-learning"],
                    "question_count": 5,
                    "difficulty": "medium",
                    "questions": [
                        {
                            "id": "q1",
                            "question": "What is the primary goal of supervised learning?",
                            "type": "multiple_choice",
                            "options": [
                                "Finding hidden patterns in unlabeled data",
                                "Predicting outputs based on labeled training data",
                                "Reinforcing actions based on rewards",
                                "Clustering similar data points"
                            ],
                            "correct_answer": "Predicting outputs based on labeled training data",
                            "explanation": "Supervised learning uses labeled training data to learn a function that maps inputs to outputs."
                        }
                    ],
                    "created_at": datetime.utcnow().isoformat(),
                    "created_by": user_id
                }
            
            # Get practice document
            practice_doc = self.db.collection("practice_sets").document(practice_id).get()
            
            if not practice_doc.exists:
                raise NotFoundException(f"Practice set with ID {practice_id} not found")
            
            # Check authorization
            practice_data = practice_doc.to_dict()
            if practice_data.get("created_by") != user_id:
                raise NotFoundException(f"Practice set with ID {practice_id} not found")
            
            # Format and return
            practice_data["id"] = practice_id
            return practice_data
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving practice set {practice_id}: {str(e)}")
            raise
    
    async def create_practice_set(
        self,
        user_id: str,
        practice_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new AI-generated practice question set.
        
        Args:
            user_id: User ID
            practice_request: Practice set generation parameters
            
        Returns:
            Generated practice set
        """
        try:
            # For mock mode, return sample data
            if self.db is None:
                practice_id = f"practice-{uuid.uuid4().hex[:8]}"
                return {
                    "id": practice_id,
                    "title": practice_request.get("title", "Practice Questions"),
                    "course_id": practice_request.get("course_id"),
                    "topic_ids": practice_request.get("topic_ids"),
                    "question_count": practice_request.get("question_count", 5),
                    "difficulty": practice_request.get("difficulty", "medium"),
                    "questions": [
                        {
                            "id": "q1",
                            "question": "What is the primary goal of supervised learning?",
                            "type": "multiple_choice",
                            "options": [
                                "Finding hidden patterns in unlabeled data",
                                "Predicting outputs based on labeled training data",
                                "Reinforcing actions based on rewards",
                                "Clustering similar data points"
                            ],
                            "correct_answer": "Predicting outputs based on labeled training data",
                            "explanation": "Supervised learning uses labeled training data to learn a function that maps inputs to outputs."
                        },
                        {
                            "id": "q2",
                            "question": "Which of the following is NOT a common activation function in neural networks?",
                            "type": "multiple_choice",
                            "options": [
                                "ReLU",
                                "Sigmoid",
                                "Tanh",
                                "Logarithmic Mean Square"
                            ],
                            "correct_answer": "Logarithmic Mean Square",
                            "explanation": "ReLU, Sigmoid, and Tanh are common activation functions. Logarithmic Mean Square is not a standard activation function."
                        }
                    ],
                    "created_at": datetime.utcnow().isoformat(),
                    "created_by": user_id
                }
            
            # Generate title if not provided
            title = practice_request.get("title")
            if not title:
                if practice_request.get("topic_ids"):
                    title = f"{practice_request.get('difficulty', 'medium').title()} Difficulty Practice Questions"
                else:
                    # Get course title for better naming
                    course_doc = self.db.collection("courses").document(practice_request.get("course_id")).get()
                    course_title = "Course"
                    if course_doc.exists:
                        course_title = course_doc.to_dict().get("title", "Course")
                    title = f"{course_title} - {practice_request.get('difficulty', 'medium').title()} Practice Questions"
            
            # Retrieve relevant content for questions
            retrieved_chunks = await self.retriever.retrieve(
                query=f"Generate {practice_request.get('question_count', 5)} {practice_request.get('difficulty', 'medium')} practice questions",
                course_id=practice_request.get("course_id"),
                topic_ids=practice_request.get("topic_ids"),
                limit=10  # Get more chunks for comprehensive questions
            )
            
            # Generate questions using LLM
            prompt = self._build_practice_questions_prompt(
                question_count=practice_request.get("question_count", 5),
                question_types=practice_request.get("question_types", ["multiple_choice"]),
                difficulty=practice_request.get("difficulty", "medium"),
                include_explanations=practice_request.get("include_explanations", True)
            )
            
            response = await self.llm_connector.generate_response(
                query=prompt,
                retrieved_chunks=retrieved_chunks,
                conversation_history=[]
            )
            
            # Process LLM response into questions
            questions = self._parse_questions(response["content"])
            
            # Ensure we have the requested number of questions
            while len(questions) < practice_request.get("question_count", 5) and len(retrieved_chunks) > 0:
                # Try again with a more specific prompt
                additional_prompt = f"Generate {practice_request.get('question_count', 5) - len(questions)} more {practice_request.get('difficulty', 'medium')} practice questions"
                additional_response = await self.llm_connector.generate_response(
                    query=additional_prompt,
                    retrieved_chunks=retrieved_chunks,
                    conversation_history=[]
                )
                
                additional_questions = self._parse_questions(additional_response["content"])
                questions.extend(additional_questions)
                
                # Cap at the requested count
                if len(questions) > practice_request.get("question_count", 5):
                    questions = questions[:practice_request.get("question_count", 5)]
            
            # Prepare practice set document
            practice_id = f"practice-{uuid.uuid4().hex}"
            practice_data = {
                "title": title,
                "course_id": practice_request.get("course_id"),
                "topic_ids": practice_request.get("topic_ids"),
                "question_count": len(questions),
                "difficulty": practice_request.get("difficulty", "medium"),
                "questions": questions,
                "created_at": datetime.utcnow().isoformat(),
                "created_by": user_id
            }
            
            # Save to Firestore
            self.db.collection("practice_sets").document(practice_id).set(practice_data)
            
            # Return complete practice set with ID
            return {
                "id": practice_id,
                **practice_data
            }
            
        except Exception as e:
            logger.error(f"Error creating practice set: {str(e)}")
            raise
    
    async def evaluate_practice_answers(
        self,
        practice_id: str,
        user_id: str,
        answers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate user answers to practice questions.
        
        Args:
            practice_id: Practice set ID
            user_id: User ID
            answers: List of user answers
            
        Returns:
            Evaluation results
        """
        try:
            # Get practice set
            practice_set = await self.get_practice_set(practice_id, user_id)
            
            # Initialize results
            correct_count = 0
            question_results = []
            
            # Build a map of question IDs to questions for easier lookup
            questions_map = {q["id"]: q for q in practice_set["questions"]}
            
            # Evaluate each answer
            for answer in answers:
                question_id = answer.get("question_id")
                user_answer = answer.get("answer")
                
                if question_id not in questions_map:
                    continue
                
                question = questions_map[question_id]
                correct_answer = question.get("correct_answer")
                
                # Determine if answer is correct based on question type
                is_correct = False
                
                if question.get("type") == "multiple_choice" or question.get("type") == "true_false":
                    # For multiple choice, direct comparison should work
                    is_correct = user_answer == correct_answer
                elif question.get("type") == "short_answer":
                    # For short answer, use more flexible matching
                    # This is a simple implementation - could be enhanced with NLP
                    is_correct = user_answer.lower().strip() == correct_answer.lower().strip()
                elif question.get("type") == "coding":
                    # For coding questions, we would need a more sophisticated evaluation
                    # For now, use simple string matching
                    is_correct = user_answer.strip() == correct_answer.strip()
                
                if is_correct:
                    correct_count += 1
                
                # Add to results
                question_results.append({
                    "question_id": question_id,
                    "correct": is_correct,
                    "user_answer": user_answer,
                    "correct_answer": correct_answer,
                    "explanation": question.get("explanation")
                })
            
            # Calculate score
            score = (correct_count / len(practice_set["questions"])) * 100 if practice_set["questions"] else 0
            
            # Generate feedback based on score
            feedback = self._generate_feedback(score, practice_set["difficulty"])
            
            # Create result object
            result = {
                "practice_id": practice_id,
                "user_id": user_id,
                "score": score,
                "question_results": question_results,
                "completed_at": datetime.utcnow().isoformat(),
                "feedback": feedback
            }
            
            # Save result to Firestore
            if self.db:
                result_id = f"result-{uuid.uuid4().hex}"
                self.db.collection("practice_results").document(result_id).set(result)
            
            return result
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error evaluating practice answers: {str(e)}")
            raise
    
    async def delete_practice_set(self, practice_id: str, user_id: str) -> bool:
        """
        Delete a practice set.
        
        Args:
            practice_id: Practice set ID
            user_id: User ID (for authorization)
            
        Returns:
            True if deletion was successful
        """
        try:
            # For mock mode, return success
            if self.db is None:
                return True
            
            # Get practice document
            practice_doc = self.db.collection("practice_sets").document(practice_id).get()
            
            if not practice_doc.exists:
                raise NotFoundException(f"Practice set with ID {practice_id} not found")
            
            # Check authorization
            practice_data = practice_doc.to_dict()
            if practice_data.get("created_by") != user_id:
                raise NotFoundException(f"Practice set with ID {practice_id} not found")
            
            # Delete document
            self.db.collection("practice_sets").document(practice_id).delete()
            
            return True
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error deleting practice set {practice_id}: {str(e)}")
            raise
    
    def _build_practice_questions_prompt(
        self,
        question_count: int,
        question_types: List[str],
        difficulty: str,
        include_explanations: bool
    ) -> str:
        """
        Build a prompt for generating practice questions.
        
        Args:
            question_count: Number of questions to generate
            question_types: Types of questions to generate
            difficulty: Difficulty level
            include_explanations: Whether to include explanations
            
        Returns:
            Formatted prompt
        """
        type_str = ", ".join(question_types)
        prompt = f"Generate {question_count} {difficulty} difficulty {type_str} questions based on the provided course materials."
        
        if "multiple_choice" in question_types:
            prompt += " For multiple choice questions, provide 4 options with exactly one correct answer."
            
        if include_explanations:
            prompt += " For each question, include a brief explanation of the correct answer."
            
        prompt += " Format each question with a clear question text, followed by options (if applicable), the correct answer, and explanation."
        
        return prompt
    
    def _parse_questions(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse the LLM response into structured questions.
        
        Args:
            content: Raw LLM response
            
        Returns:
            List of question objects
        """
        # This is a simplified implementation - in practice, you'd want more robust parsing
        lines = content.split("\n")
        questions = []
        current_question = None
        current_content = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Heuristic: A question likely starts with a number or "Question"
            if (line.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.", "Question")) and 
                (i == 0 or not lines[i-1].strip())):
                
                # Save previous question if exists
                if current_question and current_content:
                    question_obj = self._process_question_content(current_question, current_content)
                    if question_obj:
                        questions.append(question_obj)
                
                # Start new question
                current_question = line
                current_content = []
            elif current_question is not None:
                current_content.append(line)
        
        # Add the last question
        if current_question and current_content:
            question_obj = self._process_question_content(current_question, current_content)
            if question_obj:
                questions.append(question_obj)
        
        return questions
    
    def _process_question_content(self, question_text: str, content: List[str]) -> Dict[str, Any]:
        """
        Process the content of a single question to extract components.
        
        Args:
            question_text: The question text line
            content: The lines of content for this question
            
        Returns:
            Structured question object
        """
        # Remove question number prefix
        for prefix in ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.", "Question:"]:
            if question_text.startswith(prefix):
                question_text = question_text[len(prefix):].strip()
                break
        
        # Determine question type and extract components
        options = []
        correct_answer = None
        explanation = None
        
        # Check for options (indicating multiple choice)
        option_markers = ["A)", "B)", "C)", "D)", "a)", "b)", "c)", "d)", "A.", "B.", "C.", "D."]
        has_options = any(any(line.strip().startswith(marker) for marker in option_markers) for line in content)
        
        if has_options:
            # Multiple choice question
            question_type = "multiple_choice"
            
            for line in content:
                line = line.strip()
                
                # Extract options
                for marker in option_markers:
                    if line.startswith(marker):
                        option_text = line[len(marker):].strip()
                        options.append(option_text)
                        break
                
                # Extract correct answer
                if line.startswith(("Correct answer:", "Answer:", "Correct:")):
                    correct_part = line.split(":", 1)[1].strip()
                    # Handle different formats of correct answer
                    if correct_part in ["A", "B", "C", "D"] and options:
                        # Convert letter to option text
                        idx = ord(correct_part) - ord("A")
                        if 0 <= idx < len(options):
                            correct_answer = options[idx]
                    else:
                        correct_answer = correct_part
                
                # Extract explanation
                if line.startswith(("Explanation:", "Reason:")):
                    explanation = line.split(":", 1)[1].strip()
                    # Include following lines in explanation
                    explanation_lines = [explanation]
                    for exp_line in content[content.index(line) + 1:]:
                        if any(exp_line.strip().startswith(prefix) for prefix in ["Correct answer:", "Answer:", "Correct:", "Question:"]):
                            break
                        explanation_lines.append(exp_line.strip())
                    explanation = " ".join(filter(None, explanation_lines))
        
        elif any("true" in line.lower() or "false" in line.lower() for line in content[:3]):
            # Likely a true/false question
            question_type = "true_false"
            options = ["True", "False"]
            
            for line in content:
                line = line.strip().lower()
                if "answer: true" in line or "correct: true" in line:
                    correct_answer = "True"
                elif "answer: false" in line or "correct: false" in line:
                    correct_answer = "False"
                
                if line.startswith(("explanation:", "reason:")):
                    explanation = line.split(":", 1)[1].strip()
        
        else:
            # Assume short answer question
            question_type = "short_answer"
            
            for line in content:
                line = line.strip()
                if line.startswith(("Answer:", "Correct answer:")):
                    correct_answer = line.split(":", 1)[1].strip()
                
                if line.startswith(("Explanation:", "Reason:")):
                    explanation = line.split(":", 1)[1].strip()
        
        # If we couldn't identify components, don't return a question
        if not correct_answer:
            return None
        
        # Create question object
        question_obj = {
            "id": f"q-{uuid.uuid4().hex[:8]}",
            "question": question_text,
            "type": question_type
        }
        
        if options:
            question_obj["options"] = options
            
        question_obj["correct_answer"] = correct_answer
        
        if explanation:
            question_obj["explanation"] = explanation
            
        return question_obj
    
    def _generate_feedback(self, score: float, difficulty: str) -> str:
        """
        Generate feedback based on score and difficulty.
        
        Args:
            score: Percentage score
            difficulty: Difficulty level
            
        Returns:
            Feedback message
        """
        if score >= 90:
            return "Excellent work! You've demonstrated mastery of this material."
        elif score >= 80:
            return "Great job! You have a solid understanding of the concepts."
        elif score >= 70:
            return "Good effort! You're on the right track, but might benefit from reviewing a few topics."
        elif score >= 60:
            return "You've passed, but there are several concepts you should review to strengthen your understanding."
        else:
            return "You should spend more time studying these topics. Consider reviewing the course materials and try again."