"""BioMentor AI — AI Doubt Chatbot Agent

Context-aware + Mastery-aware + Adaptive-tone AI Tutor.
Uses RAG context from uploaded materials + student mastery profile
to answer doubts at the right difficulty level.
"""
import json
from langchain_groq import ChatGroq
from config import GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURES, LLM_MAX_TOKENS


def get_llm():
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURES.get("chat", 0.4),
        max_tokens=LLM_MAX_TOKENS,
    )


def get_mastery_tone(mastery_score: float) -> dict:
    """Determine explanation tone based on mastery level."""
    if mastery_score < 30:
        return {
            "level": "beginner",
            "instruction": (
                "The student is a BEGINNER. Use very simple language, everyday analogies, "
                "step-by-step explanations. Avoid jargon unless you define it first. "
                "Use examples they can relate to."
            ),
        }
    elif mastery_score < 60:
        return {
            "level": "intermediate",
            "instruction": (
                "The student has INTERMEDIATE understanding. Use proper scientific terminology "
                "but explain complex concepts clearly. Include relevant examples and connect "
                "to related concepts they may already know."
            ),
        }
    else:
        return {
            "level": "advanced",
            "instruction": (
                "The student has ADVANCED understanding. Use precise scientific language. "
                "Go deeper into mechanisms, edge cases, and research context. "
                "Challenge them with nuances and real-world applications."
            ),
        }


def chat_with_tutor(
    topic_name: str,
    topic_domain: str,
    student_question: str,
    mastery_score: float,
    rag_context: str,
    chat_history: list = None,
    weak_topics: list = None,
) -> str:
    """
    Generate a tutor response that is:
    - Context-aware (uses RAG material)
    - Mastery-aware (adapts difficulty)
    - Graph-aware (references related/weak topics)
    """
    tone = get_mastery_tone(mastery_score)

    # Build context about weak areas
    weak_topic_note = ""
    if weak_topics:
        weak_names = [w["topic_name"] for w in weak_topics[:3]]
        weak_topic_note = (
            f"\nThe student is also weak in: {', '.join(weak_names)}. "
            "If the question touches these areas, gently explain those concepts too."
        )

    # Build conversation history string
    history_str = ""
    if chat_history and len(chat_history) > 0:
        recent = chat_history[-6:]  # Last 3 exchanges
        history_str = "\n\nRecent conversation:\n"
        for msg in recent:
            role = "Student" if msg["role"] == "user" else "Tutor"
            history_str += f"{role}: {msg['message']}\n"

    prompt = f"""You are BioMentor AI Tutor — an intelligent, adaptive biotechnology tutor.

CURRENT CONTEXT:
- Topic: {topic_name} ({topic_domain})
- Student mastery in this topic: {mastery_score}% ({tone['level']})
{weak_topic_note}

TONE INSTRUCTION:
{tone['instruction']}

REFERENCE MATERIAL (from uploaded course text):
{rag_context if rag_context else 'No specific material available for this question.'}
{history_str}

STUDENT'S QUESTION:
{student_question}

RULES:
1. Answer the question directly and clearly
2. Adapt complexity to the student's mastery level
3. Use the reference material when relevant — cite it naturally
4. If the question relates to a weak area, provide extra clarity
5. Keep your response concise but thorough (3-6 sentences typically)
6. Use bullet points or numbered steps for complex explanations
7. End with a brief encouraging note or follow-up question to keep engagement
8. IMPORTANT: If the answer is not in the reference material, say "Based on the course material, I don't have specific information on this. Here's what I can share..."
9. Prefer information from the course text over general knowledge

Respond naturally as a helpful tutor:"""

    try:
        llm = get_llm()
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        return f"I'm having trouble connecting right now. Please try again in a moment. (Error: {str(e)})"
