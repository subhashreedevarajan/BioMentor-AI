"""BioMentor AI — Quiz Agent (Strict Grounding)

Generates MCQ questions strictly from course text.
RULES:
  - Questions must be answerable ONLY from the provided text
  - No external knowledge
  - No trick questions
  - No domain assumptions
  - Each question tagged to a concept from the text
"""
import json
from langchain_groq import ChatGroq
from config import GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURES


def _get_llm():
    """Create LLM for quiz generation with sufficient token budget."""
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURES.get("quiz", 0.3),
        max_tokens=4096,  # Quiz needs more tokens than default for multiple MCQs
    )


def _parse_json_response(content: str) -> list:
    """Parse JSON array from LLM response."""
    content = content.strip()
    if content.startswith("```"):
        parts = content.split("```")
        if len(parts) >= 3:
            inner = parts[1]
            if inner.startswith("json"):
                inner = inner[4:]
            content = inner.strip()
        else:
            content = parts[1] if len(parts) > 1 else content
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
    return json.loads(content)


QUIZ_SYSTEM_PROMPT = """You are a strict academic quiz generator.
Create questions that are ONLY answerable from the provided text.
Do NOT use external knowledge.
Do NOT add trick questions.
Do NOT assume knowledge beyond what the text states.

Every question must be directly answerable by reading the provided text.
Every explanation must reference specific information from the text."""

QUIZ_USER_PROMPT = """Generate exactly {num_questions} multiple-choice questions from the following course text.

RULES:
- Each question must test understanding of content IN the text
- All 4 options must be plausible, but only one correct
- correct_answer must be one of: "A", "B", "C", "D"
- concept_tag must be a concept explicitly mentioned in the text
- explanation must cite specific information from the text
- Do NOT create questions about topics not covered in the text
- Cover DIFFERENT concepts across questions — spread across the material
- Vary difficulty: include recall, understanding, and application-level questions
- Questions must be answerable ONLY by reading the provided text below

CONCEPTS IN THIS COURSE: {concepts}

COURSE TEXT:
\"\"\"
{course_text}
\"\"\"

Return ONLY this JSON array (no markdown, no explanation):
[
  {{
    "question": "",
    "options": {{"A": "", "B": "", "C": "", "D": ""}},
    "correct_answer": "A",
    "concept_tag": "",
    "explanation": ""
  }}
]"""


def generate_quiz(
    course_text: str,
    concepts: list,
    num_questions: int = 5,
    course_title: str = "Course",
) -> list:
    """Generate concept-tagged MCQ questions strictly from course text.

    Args:
        course_text: Raw text or section content to generate questions from
        concepts: List of concept names to tag questions to
        num_questions: Number of questions to generate
        course_title: Title for context

    Returns:
        List of validated question dicts
    """
    llm = _get_llm()

    concepts_str = ", ".join(concepts) if concepts else "general concepts"

    try:
        response = llm.invoke([
            {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
            {"role": "user", "content": QUIZ_USER_PROMPT.format(
                num_questions=num_questions,
                concepts=concepts_str,
                course_text=course_text[:8000],
            )},
        ])

        questions = _parse_json_response(response.content)

        # Validate structure
        validated = []
        for q in questions:
            if all(k in q for k in ["question", "options", "correct_answer"]):
                q.setdefault("concept_tag", concepts[0] if concepts else "General")
                q.setdefault("explanation", "")
                validated.append(q)

        return validated if validated else _fallback_questions(course_title, concepts)

    except (json.JSONDecodeError, Exception) as e:
        print(f"Quiz generation error: {e}")
        return _fallback_questions(course_title, concepts)


def _fallback_questions(title: str, concepts: list) -> list:
    """Fallback questions if LLM fails."""
    concept = concepts[0] if concepts else "the topic"
    return [{
        "question": f"What is the primary focus of the section on {concept}?",
        "options": {
            "A": f"Understanding {concept}",
            "B": "Unrelated topic",
            "C": "External application",
            "D": "Historical background only"
        },
        "correct_answer": "A",
        "concept_tag": concept,
        "explanation": f"The section primarily covers {concept} as described in the text."
    }]
