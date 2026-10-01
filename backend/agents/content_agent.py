"""BioMentor AI — Content Agent

RAG-powered lesson generation. Retrieves relevant content from the
vector store and generates a structured lesson adapted to student level.
"""
import json
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from config import GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURES, LLM_MAX_TOKENS


def get_llm(temperature_key="content"):
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURES.get(temperature_key, 0.5),
        max_tokens=LLM_MAX_TOKENS,
    )


LESSON_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are BioMentor AI, an expert biotechnology tutor.
Generate a structured lesson on the given topic. Adapt the depth based on the student's mastery level.

Rules:
- If mastery is low (0-40%): Start from basics, use simple language, more analogies
- If mastery is medium (40-70%): Moderate depth, include examples and applications
- If mastery is high (70-100%): Advanced details, research connections, edge cases

Use the provided context from study materials when available.

RESPOND IN THIS EXACT JSON FORMAT:
{{
    "title": "Topic title",
    "explanation": "Main explanation (2-3 paragraphs)",
    "key_points": ["point 1", "point 2", "point 3", "point 4", "point 5"],
    "examples": ["example 1", "example 2"],
    "summary": "Brief 2-sentence summary",
    "difficulty_adapted": true
}}"""),
    ("human", """Topic: {topic_name}
Topic Description: {topic_description}
Student Mastery Level: {mastery_level}%
Education Level: {education_level}

Relevant Study Material Context:
{rag_context}

Generate the lesson now.""")
])


def generate_lesson(topic: dict, mastery_level: float, education_level: str = "UG", rag_context: str = "No additional materials available.") -> dict:
    """Generate a structured lesson for a topic.

    Args:
        topic: Topic dict from KnowledgeGraph
        mastery_level: Student's current mastery (0-100)
        education_level: School / UG / PG
        rag_context: Retrieved context from vector store

    Returns:
        Structured lesson dict
    """
    llm = get_llm("content")
    chain = LESSON_PROMPT | llm

    try:
        response = chain.invoke({
            "topic_name": topic["name"],
            "topic_description": topic["description"],
            "mastery_level": mastery_level,
            "education_level": education_level,
            "rag_context": rag_context[:2000],  # Limit context size
        })

        # Parse JSON from response
        content = response.content.strip()
        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        return json.loads(content)
    except json.JSONDecodeError:
        # Fallback: return raw content as explanation
        return {
            "title": topic["name"],
            "explanation": response.content,
            "key_points": [],
            "examples": [],
            "summary": topic["description"],
            "difficulty_adapted": True,
        }
    except Exception as e:
        return {
            "title": topic["name"],
            "explanation": f"Error generating lesson: {str(e)}",
            "key_points": [],
            "examples": [],
            "summary": topic["description"],
            "difficulty_adapted": False,
        }
