"""BioMentor AI — Student API Routes

Grounded course-based learning:
  - Browse courses (from admin uploads)
  - Learn from section-based structured content
  - Take grounded quizzes (text-only, no external knowledge)
  - Track per-concept mastery
  - Behavioral intelligence (learning event tracking)
  - Adaptive recommendations via knowledge graph
  - AI doubt chatbot (RAG-constrained to course text)
"""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import get_db
from rag.retriever import get_context_string
from agents.quiz_agent import generate_quiz
from agents.evaluation_agent import evaluate_quiz, get_quiz_history
from agents.chat_agent import chat_with_tutor
from agents.adaptive_engine import classify_learning_status

router = APIRouter(prefix="/api/student", tags=["Student"])


# ── Request Models ────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    education_level: str = "UG"

class LearnRequest(BaseModel):
    student_id: int
    course_id: int

class QuizRequest(BaseModel):
    student_id: int
    course_id: int
    num_questions: int = 5

class SubmitQuizRequest(BaseModel):
    student_id: int
    course_id: int
    questions: list
    answers: dict

class ChatRequest(BaseModel):
    student_id: int
    course_id: int
    message: str

class TrackEventRequest(BaseModel):
    student_id: int
    course_id: int
    event_type: str
    section_index: int = None
    duration_seconds: int = 0


# ── Auth ──────────────────────────────────────────────
@router.post("/login")
def login(req: LoginRequest):
    db = get_db()
    user = db.execute(
        "SELECT id, username, role, education_level FROM users WHERE username = ? AND password = ?",
        (req.username, req.password)
    ).fetchone()
    db.close()
    if not user:
        raise HTTPException(401, "Invalid credentials")
    return {"user": dict(user)}


@router.post("/register")
def register(req: RegisterRequest):
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username = ?", (req.username,)).fetchone()
    if existing:
        raise HTTPException(400, "Username already exists")

    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO users (username, password, role, education_level) VALUES (?, ?, 'student', ?)",
        (req.username, req.password, req.education_level)
    )
    db.commit()
    user = db.execute(
        "SELECT id, username, role, education_level FROM users WHERE id = ?",
        (cursor.lastrowid,)
    ).fetchone()
    db.close()
    return {"user": dict(user)}


# ── Browse Courses ────────────────────────────────────
@router.get("/courses")
def get_courses():
    """Get all available courses for student dashboard."""
    db = get_db()
    courses = db.execute("""
        SELECT id, title, summary, domain, difficulty, education_level, created_at
        FROM courses ORDER BY created_at DESC
    """).fetchall()

    result = []
    for c in courses:
        concepts = db.execute(
            "SELECT name FROM concepts WHERE course_id = ?", (c["id"],)
        ).fetchall()
        section_count = db.execute(
            "SELECT COUNT(*) as c FROM course_sections WHERE course_id = ?", (c["id"],)
        ).fetchone()["c"]
        result.append({
            **dict(c),
            "concepts": [cp["name"] for cp in concepts],
            "section_count": section_count,
        })

    db.close()
    return {"courses": result}


# ── Learn (Get Course Content) ────────────────────────
@router.post("/learn")
def learn(req: LearnRequest):
    """Get structured course content for learning.

    Returns section-based content from course_sections table,
    knowledge graph from relationships table, and behavioral classification.
    """
    db = get_db()

    course = db.execute(
        "SELECT * FROM courses WHERE id = ?", (req.course_id,)
    ).fetchone()
    if not course:
        raise HTTPException(404, "Course not found")

    # Get structured sections
    sections = db.execute("""
        SELECT id, section_index, section_title, detailed_explanation,
               key_points, explicit_concepts, mentioned_challenges,
               mentioned_applications, section_summary
        FROM course_sections
        WHERE course_id = ?
        ORDER BY section_index ASC
    """, (req.course_id,)).fetchall()

    # Parse JSON fields in sections
    parsed_sections = []
    for s in sections:
        parsed_sections.append({
            "id": s["id"],
            "section_index": s["section_index"],
            "section_title": s["section_title"],
            "detailed_explanation": s["detailed_explanation"],
            "key_points": json.loads(s["key_points"]) if s["key_points"] else [],
            "explicit_concepts": json.loads(s["explicit_concepts"]) if s["explicit_concepts"] else [],
            "mentioned_challenges": json.loads(s["mentioned_challenges"]) if s["mentioned_challenges"] else [],
            "mentioned_applications": json.loads(s["mentioned_applications"]) if s["mentioned_applications"] else [],
            "section_summary": s["section_summary"],
        })

    # Get concepts
    concepts = db.execute(
        "SELECT name FROM concepts WHERE course_id = ?", (req.course_id,)
    ).fetchall()

    # Get student mastery
    mastery_rows = db.execute(
        "SELECT concept, mastery_score FROM mastery WHERE student_id = ? AND course_id = ?",
        (req.student_id, req.course_id)
    ).fetchall()
    mastery = {m["concept"]: m["mastery_score"] for m in mastery_rows}
    avg_mastery = round(sum(mastery.values()) / len(mastery), 1) if mastery else 0

    # Get knowledge graph (relationships)
    graph = db.execute(
        "SELECT source_concept, target_concept, relation_type FROM relationships WHERE course_id = ?",
        (req.course_id,)
    ).fetchall()

    # ── Cross-course prerequisite matching ──
    this_course_concepts = set(c["name"].lower().strip() for c in concepts)
    prereq_sources = set(g["source_concept"] for g in graph)
    external_prereqs = set()
    for ps in prereq_sources:
        if ps.lower().strip() not in this_course_concepts:
            external_prereqs.add(ps)

    cross_course_prereqs = []
    unresolved_prereqs = []

    if external_prereqs:
        all_other_concepts = db.execute("""
            SELECT c.id as course_id, c.title as course_title, cp.name as concept_name
            FROM concepts cp
            JOIN courses c ON cp.course_id = c.id
            WHERE c.id != ?
        """, (req.course_id,)).fetchall()

        course_map = {}
        found_concepts = set()

        for ext in external_prereqs:
            ext_lower = ext.lower().strip()
            for oc in all_other_concepts:
                oc_lower = oc["concept_name"].lower().strip()
                if ext_lower == oc_lower or ext_lower in oc_lower or oc_lower in ext_lower:
                    cid = oc["course_id"]
                    if cid not in course_map:
                        course_map[cid] = {"course_id": cid, "course_title": oc["course_title"], "matching_concepts": []}
                    if ext not in course_map[cid]["matching_concepts"]:
                        course_map[cid]["matching_concepts"].append(ext)
                    found_concepts.add(ext)

        cross_course_prereqs = list(course_map.values())
        unresolved_prereqs = list(external_prereqs - found_concepts)

    # Get reference links
    references = db.execute(
        "SELECT id, title, url FROM course_references WHERE course_id = ?", (req.course_id,)
    ).fetchall()

    # Log lesson_opened event
    db.execute(
        "INSERT INTO learning_events (student_id, course_id, event_type) VALUES (?, ?, 'lesson_opened')",
        (req.student_id, req.course_id)
    )
    db.commit()
    db.close()

    # Get learning status
    try:
        learning_status = classify_learning_status(req.student_id, req.course_id)
    except Exception:
        learning_status = {}

    return {
        "course": {
            "id": course["id"],
            "title": course["title"],
            "summary": course["summary"],
            "main_topic": course["main_topic"],
            "domain": course["domain"],
            "difficulty": course["difficulty"],
        },
        "sections": parsed_sections,
        "concepts": [c["name"] for c in concepts],
        "mastery": mastery,
        "avg_mastery": avg_mastery,
        "graph": [{"source": g["source_concept"], "target": g["target_concept"], "relation_type": g["relation_type"]} for g in graph],
        "cross_course_prereqs": cross_course_prereqs,
        "unresolved_prereqs": unresolved_prereqs,
        "additional_notes": course["additional_notes"] or "",
        "references": [{"id": r["id"], "title": r["title"], "url": r["url"]} for r in references],
        "pdf_url": f"/uploads/{course['source_filename']}" if course["source_filename"] else None,
        "learning_status": learning_status,
    }


# ── Quiz ──────────────────────────────────────────────
@router.post("/quiz")
def quiz(req: QuizRequest):
    """Generate a grounded quiz for a course (questions from text only)."""
    db = get_db()
    course = db.execute("SELECT * FROM courses WHERE id = ?", (req.course_id,)).fetchone()
    if not course:
        raise HTTPException(404, "Course not found")

    concepts = db.execute(
        "SELECT name FROM concepts WHERE course_id = ?", (req.course_id,)
    ).fetchall()

    # Get section content for quiz generation (grounded in text)
    sections = db.execute(
        "SELECT detailed_explanation, section_summary FROM course_sections WHERE course_id = ? ORDER BY section_index",
        (req.course_id,)
    ).fetchall()

    db.close()

    # Use raw PDF text as primary source (actual uploaded content = source of truth)
    course_text = course["raw_text"][:10000] if course["raw_text"] else ""

    # Supplement with section summaries for concept coverage
    if not course_text.strip():
        course_text = "\n\n".join([
            s["detailed_explanation"] for s in sections if s["detailed_explanation"]
        ])
    if not course_text.strip():
        course_text = "No content available."

    concept_names = [c["name"] for c in concepts]

    # Generate quiz from raw PDF text only (grounded, no external knowledge)
    questions = generate_quiz(
        course_text=course_text,
        concepts=concept_names,
        num_questions=req.num_questions,
        course_title=course["title"],
    )
    return {"questions": questions, "course_id": req.course_id}


# ── Submit Quiz ───────────────────────────────────────
@router.post("/submit-quiz")
def submit_quiz(req: SubmitQuizRequest):
    """Submit quiz answers for evaluation."""
    evaluation = evaluate_quiz(req.student_id, req.course_id, req.questions, req.answers)

    # Generate adaptive recommendation
    recommendation = _generate_recommendation(req.student_id, req.course_id, evaluation)

    return {
        "evaluation": evaluation,
        "recommendation": recommendation,
    }


def _generate_recommendation(student_id: int, course_id: int, evaluation: dict) -> dict:
    """Generate adaptive recommendation based on quiz results and knowledge graph."""
    db = get_db()

    mastery_rows = db.execute(
        "SELECT concept, mastery_score FROM mastery WHERE student_id = ? AND course_id = ?",
        (student_id, course_id)
    ).fetchall()
    mastery = {m["concept"]: m["mastery_score"] for m in mastery_rows}

    # Use relationships table (not course_graph)
    graph = db.execute(
        "SELECT source_concept, target_concept FROM relationships WHERE course_id = ?",
        (course_id,)
    ).fetchall()

    db.close()

    score = evaluation["overall_score"]
    weak_concepts = [c for c, s in mastery.items() if s < 50]

    weak_prereqs = []
    for edge in graph:
        if edge["target_concept"] in weak_concepts:
            prereq = edge["source_concept"]
            prereq_mastery = mastery.get(prereq, 0)
            if prereq_mastery < 60:
                weak_prereqs.append({
                    "concept": prereq,
                    "mastery": prereq_mastery,
                    "needed_for": edge["target_concept"],
                })

    if score >= 80:
        return {
            "action": "advance",
            "reason": "You've mastered this material! Great work.",
            "weak_concepts": [],
            "weak_prerequisites": [],
        }
    elif score >= 50:
        return {
            "action": "practice",
            "reason": f"Good progress! Focus on: {', '.join(weak_concepts[:3]) if weak_concepts else 'review the material'}.",
            "weak_concepts": weak_concepts,
            "weak_prerequisites": weak_prereqs,
        }
    else:
        reason = "You need more review. "
        if weak_prereqs:
            prereq_names = [wp["concept"] for wp in weak_prereqs[:3]]
            reason += f"Prerequisites are weak: {', '.join(prereq_names)}. Study those first!"
        else:
            reason += "Try the AI Tutor for help understanding difficult concepts."

        return {
            "action": "remediate",
            "reason": reason,
            "weak_concepts": weak_concepts,
            "weak_prerequisites": weak_prereqs,
        }


# ── Analytics ─────────────────────────────────────────
@router.get("/analytics/{student_id}")
def get_analytics(student_id: int):
    """Get student analytics across all courses."""
    db = get_db()

    mastery_rows = db.execute(
        "SELECT course_id, concept, mastery_score FROM mastery WHERE student_id = ?",
        (student_id,)
    ).fetchall()

    courses = db.execute("SELECT id, title, domain FROM courses").fetchall()

    course_mastery = {}
    for m in mastery_rows:
        cid = m["course_id"]
        if cid not in course_mastery:
            course_mastery[cid] = {"scores": [], "concepts": {}}
        course_mastery[cid]["scores"].append(m["mastery_score"])
        course_mastery[cid]["concepts"][m["concept"]] = m["mastery_score"]

    all_courses = []
    for c in courses:
        cm = course_mastery.get(c["id"], {"scores": [], "concepts": {}})
        avg = round(sum(cm["scores"]) / len(cm["scores"]), 1) if cm["scores"] else 0
        all_courses.append({
            "id": c["id"],
            "title": c["title"],
            "domain": c["domain"],
            "avg_mastery": avg,
            "concepts": cm["concepts"],
        })

    all_scores = [m["mastery_score"] for m in mastery_rows]
    overall = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
    studied = len(set(m["course_id"] for m in mastery_rows))

    quiz_hist = get_quiz_history(student_id)

    domains = {}
    for c in all_courses:
        d = c["domain"]
        if d not in domains:
            domains[d] = {"scores": [], "count": 0}
        domains[d]["count"] += 1
        if c["avg_mastery"] > 0:
            domains[d]["scores"].append(c["avg_mastery"])

    domain_breakdown = {}
    for d, stats in domains.items():
        domain_breakdown[d] = {
            "avg_mastery": round(sum(stats["scores"]) / len(stats["scores"]), 1) if stats["scores"] else 0,
            "count": stats["count"],
        }

    db.close()

    return {
        "dashboard": {
            "overall_mastery": overall,
            "courses_total": len(courses),
            "courses_studied": studied,
            "all_courses": all_courses,
            "domain_breakdown": domain_breakdown,
        },
        "quiz_history": quiz_hist,
    }


# ── AI Chatbot ────────────────────────────────────────
@router.post("/chat")
def chat(req: ChatRequest):
    """AI Tutor chatbot — RAG-constrained to course text."""
    db = get_db()

    course = db.execute("SELECT * FROM courses WHERE id = ?", (req.course_id,)).fetchone()
    if not course:
        raise HTTPException(404, "Course not found")

    mastery_rows = db.execute(
        "SELECT concept, mastery_score FROM mastery WHERE student_id = ? AND course_id = ?",
        (req.student_id, req.course_id)
    ).fetchall()
    mastery = {m["concept"]: m["mastery_score"] for m in mastery_rows}
    avg_mastery = round(sum(mastery.values()) / len(mastery), 1) if mastery else 0

    weak_concepts = [{"topic_name": c, "mastery": s} for c, s in mastery.items() if s < 50]

    # RAG context (constrained to this course's uploaded text)
    rag_context = get_context_string(req.message, top_k=3)

    history_rows = db.execute(
        "SELECT role, message FROM chat_history WHERE student_id = ? AND course_id = ? ORDER BY created_at DESC LIMIT 6",
        (req.student_id, req.course_id)
    ).fetchall()
    chat_history = [dict(r) for r in reversed(history_rows)]

    db.execute(
        "INSERT INTO chat_history (student_id, course_id, role, message) VALUES (?, ?, 'user', ?)",
        (req.student_id, req.course_id, req.message)
    )
    db.commit()

    response = chat_with_tutor(
        topic_name=course["title"],
        topic_domain=course["domain"],
        student_question=req.message,
        mastery_score=avg_mastery,
        rag_context=rag_context,
        chat_history=chat_history,
        weak_topics=weak_concepts,
    )

    db.execute(
        "INSERT INTO chat_history (student_id, course_id, role, message) VALUES (?, ?, 'assistant', ?)",
        (req.student_id, req.course_id, response)
    )
    db.commit()
    db.close()

    tone = "beginner" if avg_mastery < 30 else "intermediate" if avg_mastery < 60 else "advanced"

    return {
        "response": response,
        "mastery_level": avg_mastery,
        "tone": tone,
    }


@router.get("/chat-history/{student_id}/{course_id}")
def get_chat_hist(student_id: int, course_id: int):
    """Get chat history for a student + course."""
    db = get_db()
    rows = db.execute(
        "SELECT role, message, created_at FROM chat_history WHERE student_id = ? AND course_id = ? ORDER BY created_at ASC LIMIT 50",
        (student_id, course_id)
    ).fetchall()
    db.close()
    return {"messages": [dict(r) for r in rows]}


# ── Behavioral Intelligence ───────────────────────────
@router.post("/track-event")
def track_event(req: TrackEventRequest):
    """Log a learning event for behavioral intelligence."""
    valid_events = ["lesson_opened", "section_viewed", "quiz_started", "quiz_completed", "chat_asked"]
    if req.event_type not in valid_events:
        raise HTTPException(400, f"Invalid event type. Must be one of: {valid_events}")

    db = get_db()
    db.execute(
        "INSERT INTO learning_events (student_id, course_id, event_type, section_index, duration_seconds) VALUES (?, ?, ?, ?, ?)",
        (req.student_id, req.course_id, req.event_type, req.section_index, req.duration_seconds)
    )
    db.commit()
    db.close()
    return {"status": "tracked"}


@router.get("/learning-status/{student_id}/{course_id}")
def get_learning_status(student_id: int, course_id: int):
    """Get per-concept behavioral classification."""
    status = classify_learning_status(student_id, course_id)
    return {"learning_status": status}
