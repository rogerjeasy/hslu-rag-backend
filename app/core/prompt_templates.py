"""
Prompt templates for HSLU RAG application.

This module contains structured prompt templates for different features of the RAG application:
- Question answering
- Study guide generation
- Practice question generation
- Knowledge gap analysis

Each template is designed to provide effective instructions to the LLM for generating
high-quality, context-relevant responses from course materials.
"""
from typing import List, Dict, Any, Optional
from enum import Enum


class PromptType(str, Enum):
    """Enum for different types of prompts."""
    QUESTION_ANSWERING = "question_answering"
    STUDY_GUIDE = "study_guide"
    PRACTICE_QUESTIONS = "practice_questions" 
    KNOWLEDGE_GAP = "knowledge_gap"


class DetailLevel(str, Enum):
    """Detail level for study guides and other content."""
    BASIC = "basic"
    MEDIUM = "medium"
    COMPREHENSIVE = "comprehensive"


class Format(str, Enum):
    """Format options for study guides."""
    OUTLINE = "outline"
    NOTES = "notes"
    FLASHCARDS = "flashcards"
    MIND_MAP = "mind_map"
    SUMMARY = "summary"


class Difficulty(str, Enum):
    """Difficulty levels for practice questions."""
    BASIC = "basic"
    MEDIUM = "medium"
    ADVANCED = "advanced"


class GapSeverity(str, Enum):
    """Severity levels for knowledge gaps."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class QuestionType(str, Enum):
    """Types of practice questions."""
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"
    TRUE_FALSE = "true_false"
    FILL_IN_BLANK = "fill_in_blank"
    MATCHING = "matching"


def get_system_prompt(prompt_type: PromptType, additional_params: Optional[Dict[str, Any]] = None) -> str:
    """
    Get the appropriate system prompt based on prompt type and additional parameters.
    
    Args:
        prompt_type: Type of prompt to generate
        additional_params: Additional parameters for prompt customization
        
    Returns:
        Formatted system prompt
    """
    if prompt_type == PromptType.QUESTION_ANSWERING:
        return _get_question_answering_system_prompt(additional_params)
    elif prompt_type == PromptType.STUDY_GUIDE:
        return _get_study_guide_system_prompt(additional_params)
    elif prompt_type == PromptType.PRACTICE_QUESTIONS:
        return _get_practice_questions_system_prompt(additional_params)
    elif prompt_type == PromptType.KNOWLEDGE_GAP:
        return _get_knowledge_gap_system_prompt(additional_params)
    else:
        return _get_default_system_prompt()


def get_user_prompt(
    prompt_type: PromptType,
    query: str,
    context_chunks: List[Dict[str, Any]],
    additional_params: Optional[Dict[str, Any]] = None
) -> str:
    """
    Get the appropriate user prompt based on prompt type and context.
    
    Args:
        prompt_type: Type of prompt to generate
        query: User query text
        context_chunks: Retrieved context chunks
        additional_params: Additional parameters for prompt customization
        
    Returns:
        Formatted user prompt with context
    """
    # Format context for inclusion in prompt
    formatted_context = _format_context(context_chunks)
    
    if prompt_type == PromptType.QUESTION_ANSWERING:
        return _get_question_answering_user_prompt(query, formatted_context, additional_params)
    elif prompt_type == PromptType.STUDY_GUIDE:
        return _get_study_guide_user_prompt(query, formatted_context, additional_params)
    elif prompt_type == PromptType.PRACTICE_QUESTIONS:
        return _get_practice_questions_user_prompt(query, formatted_context, additional_params)
    elif prompt_type == PromptType.KNOWLEDGE_GAP:
        return _get_knowledge_gap_user_prompt(query, formatted_context, additional_params)
    else:
        return _get_default_user_prompt(query, formatted_context)


def _format_context(context_chunks: List[Dict[str, Any]]) -> str:
    """
    Format context chunks for inclusion in prompts.
    
    Args:
        context_chunks: List of context chunks with metadata
        
    Returns:
        Formatted context string with numbered references
    """
    formatted_chunks = []
    
    for i, chunk in enumerate(context_chunks):
        chunk_text = f"[{i+1}] From '{chunk.get('title', 'Unknown')}'"
        
        if chunk.get('source_page'):
            chunk_text += f", Page {chunk['source_page']}"
        
        chunk_text += f":\n{chunk.get('chunk_content', '')}\n"
        formatted_chunks.append(chunk_text)
    
    return "\n".join(formatted_chunks)


# ===== SYSTEM PROMPTS =====

def _get_default_system_prompt() -> str:
    """Default system prompt for fallback."""
    return """You are an AI teaching assistant for HSLU university students in the Applied Information and Data Science MSc program.
Answer questions based ONLY on the provided context. If you don't know the answer based on the context, say so rather than making up information.

Format your response as a JSON object with these fields:
{
    "answer": "Your detailed answer here",
    "citations": [1, 2, 3] (list of context chunk numbers you used, referenced as [1], [2], etc.)
}
"""


def _get_question_answering_system_prompt(additional_params: Optional[Dict[str, Any]] = None) -> str:
    """System prompt for question answering."""
    return """You are an AI teaching assistant for HSLU university students in the Applied Information and Data Science MSc program.
Answer questions based ONLY on the provided context. If you don't know the answer based on the context, say so rather than making up information.

When answering, follow these guidelines:
1. Be precise and accurate with technical data science concepts
2. When explaining code or algorithms, be clear and follow best practices
3. Relate concepts to practical applications when possible
4. Structure answers with clear headings and bullet points when appropriate
5. Include relevant formulas or notations when necessary

Format your response as a JSON object with these fields:
{
    "answer": "Your detailed answer here with properly formatted Markdown",
    "citations": [1, 2, 3] (list of context chunk numbers you used, referenced as [1], [2], etc.)
}
"""


def _get_study_guide_system_prompt(additional_params: Optional[Dict[str, Any]] = None) -> str:
    """System prompt for study guide generation."""
    # Get detail level and format preferences
    detail_level = DetailLevel.MEDIUM.value
    format_type = Format.OUTLINE.value
    
    if additional_params:
        if "detail_level" in additional_params:
            detail_level = additional_params["detail_level"]
        if "format" in additional_params:
            format_type = additional_params["format"]
    
    # Adjust instructions based on detail level
    detail_instructions = {
        DetailLevel.BASIC.value: "Focus on core concepts and definitions. Keep explanations concise and simple.",
        DetailLevel.MEDIUM.value: "Balance between core concepts and supporting details. Include key examples and applications.",
        DetailLevel.COMPREHENSIVE.value: "Include in-depth explanations, examples, applications, and connections between concepts. Cover theoretical foundations and practical implementations."
    }.get(detail_level, "Balance between core concepts and supporting details. Include key examples and applications.")
    
    # Adjust instructions based on format
    format_instructions = {
        Format.OUTLINE.value: "Structure the guide with clear headings, subheadings, and bullet points for key points.",
        Format.NOTES.value: "Create detailed notes with explanations, examples, and key points to remember.",
        Format.FLASHCARDS.value: "Create question-answer pairs suitable for flashcard study. Format as 'Q: [question]' followed by 'A: [answer]'.",
        Format.MIND_MAP.value: "Structure the content as a conceptual map showing relationships between concepts. Use headings for main concepts and bullet points for connections.",
        Format.SUMMARY.value: "Create a condensed summary of the most important points and concepts."
    }.get(format_type, "Structure the guide with clear headings, subheadings, and bullet points for key points.")
    
    return f"""You are an AI teaching assistant for HSLU university students in the Applied Information and Data Science MSc program.
Create a detailed study guide based ONLY on the provided context. If important information is missing from the context, note this gap rather than making up information.

Detail level: {detail_level}
{detail_instructions}

Format: {format_type}
{format_instructions}

For this study guide, create a comprehensive learning resource with:
1. Key concepts and definitions
2. Important theories and their applications
3. Examples that illustrate the concepts
4. Relationships between different concepts

Format your response as a JSON object with these fields:
{{
    "answer": "Your well-structured study guide with Markdown formatting",
    "citations": [1, 2, 3] (list of context chunk numbers you used, referenced as [1], [2], etc.),
    "meta": {{
        "detail_level": "{detail_level}",
        "format": "{format_type}"
    }}
}}
"""


def _get_practice_questions_system_prompt(additional_params: Optional[Dict[str, Any]] = None) -> str:
    """System prompt for practice question generation."""
    # Get question preferences
    question_count = 5
    difficulty = Difficulty.MEDIUM.value
    question_types = [QuestionType.MULTIPLE_CHOICE.value, QuestionType.SHORT_ANSWER.value]
    
    if additional_params:
        if "question_count" in additional_params:
            question_count = additional_params["question_count"]
        if "difficulty" in additional_params:
            difficulty = additional_params["difficulty"]
        if "question_types" in additional_params:
            question_types = additional_params["question_types"]
    
    # Convert question types list to string for prompt
    question_types_str = ", ".join(question_types)
    
    # Difficulty-specific instructions
    difficulty_instructions = {
        Difficulty.BASIC.value: "Focus on fundamental concepts and straightforward applications. Questions should test basic recall and understanding.",
        Difficulty.MEDIUM.value: "Balance between fundamental concepts and applications. Include questions that require deeper understanding and some analysis.",
        Difficulty.ADVANCED.value: "Focus on complex applications, analysis, and synthesis of multiple concepts. Include challenging questions that test deep understanding."
    }.get(difficulty, "Balance between fundamental concepts and applications. Include questions that require deeper understanding and some analysis.")

    return f"""You are an AI teaching assistant for HSLU university students in the Applied Information and Data Science MSc program.
Generate {question_count} practice questions based ONLY on the provided context. If you can't create good questions from the context, explain why rather than making up information.

Question types to include: {question_types_str}
Difficulty level: {difficulty}
{difficulty_instructions}

For multiple-choice questions:
1. Provide 4 options (A, B, C, D)
2. Ensure only one answer is correct
3. Make distractors plausible but clearly incorrect
4. Include a brief explanation of why the correct answer is right

For short-answer questions:
1. Create clear, specific questions
2. Provide a model answer
3. Include key points that should be mentioned in a good answer

For true/false questions:
1. Create unambiguous statements that are clearly true or false
2. Provide explanation of why the statement is true or false

For fill-in-the-blank questions:
1. Create sentences with key terms removed
2. Provide the correct terms that should fill the blanks
3. Ensure there's enough context for students to determine the answer

For matching questions:
1. Create pairs of related terms/concepts
2. Ensure clear connections between matched items

For each question, include citations to the relevant context chunks.

Format your response as a JSON object with these fields:
{{
    "answer": "Practice questions with explanations and answers",
    "questions": [
        {{
            "id": "q1",
            "type": "multiple_choice",
            "text": "Question text here",
            "options": [
                {{ "id": "A", "text": "Option A", "is_correct": true }},
                {{ "id": "B", "text": "Option B", "is_correct": false }},
                {{ "id": "C", "text": "Option C", "is_correct": false }},
                {{ "id": "D", "text": "Option D", "is_correct": false }}
            ],
            "explanation": "Explanation of the correct answer",
            "citations": [1, 3],
            "difficulty": "{difficulty}"
        }},
        {{
            "id": "q2",
            "type": "short_answer",
            "text": "Question text here",
            "sample_answer": "Model answer text",
            "explanation": "Key points to include",
            "citations": [2],
            "difficulty": "{difficulty}"
        }}
    ],
    "citations": [1, 2, 3],
    "meta": {{
        "difficulty": "{difficulty}",
        "question_count": {question_count},
        "question_types": {question_types}
    }}
}}
"""


def _get_knowledge_gap_system_prompt(additional_params: Optional[Dict[str, Any]] = None) -> str:
    """System prompt for knowledge gap analysis."""
    return """You are an AI teaching assistant for HSLU university students in the Applied Information and Data Science MSc program.
Analyze the student's query and the provided context to identify potential knowledge gaps based on the course materials.

Focus on:
1. Concepts that the student appears to misunderstand or not fully grasp
2. Foundational knowledge that might be missing based on their question
3. Advanced topics that build on the concepts they're asking about
4. Common misconceptions related to the topic

For each identified gap, provide:
1. A clear description of the gap
2. Why this knowledge is important
3. Specific learning recommendations from the course materials
4. Study strategies for addressing the gap

Format your response as a JSON object with these fields:
{
    "answer": "Your analysis with recommendations",
    "gaps": [
        {
            "id": "gap1",
            "concept": "Name of the concept",
            "description": "Description of the knowledge gap",
            "severity": "low|medium|high",
            "recommended_resources": [
                {"description": "Specific recommendation"}
            ],
            "citations": [1, 3]
        }
    ],
    "strengths": [
        {
            "id": "strength1",
            "concept": "Concept the student understands well",
            "description": "Brief description"
        }
    ],
    "citations": [1, 2, 3]
}
"""


# ===== USER PROMPTS =====

def _get_default_user_prompt(query: str, formatted_context: str) -> str:
    """Default user prompt for fallback."""
    return f"""Query: {query}

Relevant context:

{formatted_context}
"""


def _get_question_answering_user_prompt(
    query: str, 
    formatted_context: str, 
    additional_params: Optional[Dict[str, Any]] = None
) -> str:
    """User prompt for question answering."""
    return f"""Query: {query}

Relevant context:

{formatted_context}

Remember to answer ONLY based on the provided context. If you don't know the answer based on this context, acknowledge that there's insufficient information rather than making up an answer. Format your response as a JSON object as instructed.
"""


def _get_study_guide_user_prompt(
    query: str, 
    formatted_context: str, 
    additional_params: Optional[Dict[str, Any]] = None
) -> str:
    """User prompt for study guide generation."""
    # Get detail level and format preferences
    detail_level = DetailLevel.MEDIUM.value
    format_type = Format.OUTLINE.value
    
    if additional_params:
        if "detail_level" in additional_params:
            detail_level = additional_params["detail_level"]
        if "format" in additional_params:
            format_type = additional_params["format"]
    
    return f"""Create a {detail_level} detail level study guide in {format_type} format on the topic: {query}

Use the following information as your source material:

{formatted_context}

Remember to create the study guide ONLY based on the provided context. If important aspects of the topic are missing from the context, note these gaps rather than making up information. Format your response as a JSON object as instructed.
"""


def _get_practice_questions_user_prompt(
    query: str, 
    formatted_context: str, 
    additional_params: Optional[Dict[str, Any]] = None
) -> str:
    """User prompt for practice question generation."""
    # Get question preferences
    question_count = 5
    difficulty = Difficulty.MEDIUM.value
    
    if additional_params:
        if "question_count" in additional_params:
            question_count = additional_params["question_count"]
        if "difficulty" in additional_params:
            difficulty = additional_params["difficulty"]
    
    return f"""Generate {question_count} practice questions at {difficulty} difficulty level for the topic: {query}

Use the following information as your source material:

{formatted_context}

Remember to create questions ONLY based on the provided context. Make sure the questions test understanding of key concepts and provide clear explanations for the answers. Format your response as a JSON object as instructed.
"""


def _get_knowledge_gap_user_prompt(
    query: str, 
    formatted_context: str, 
    additional_params: Optional[Dict[str, Any]] = None
) -> str:
    """User prompt for knowledge gap analysis."""
    past_interactions_count = 10
    if additional_params and "past_interactions_count" in additional_params:
        past_interactions_count = additional_params["past_interactions_count"]
    
    return f"""Analyze my question below and identify any knowledge gaps I might have on this topic.

My question: {query}

Use the following information as your source material:

{formatted_context}

Based on my question and the context provided, identify concepts I might not fully understand, potential misconceptions, and recommend specific sections from the course materials to address these gaps. Also note any strengths shown in my understanding. Format your response as a JSON object as instructed.

Consider this as part of my recent learning journey, where I've had approximately {past_interactions_count} previous interactions on related topics.
"""