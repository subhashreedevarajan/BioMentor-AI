"""BioMentor AI — Adaptive Engine (Deterministic Rules)

Classifies learning status using deterministic rules — no ML, no LLM.
Two dimensions:
  Dimension 1: Concept mastery scores (from quizzes)
  Dimension 2: Learning behavior signals (from tracking events)

Status classifications:
  - NOT_LEARNED: Never viewed + no quiz attempts
  - FORGOTTEN: Previously scored >80%, now <50%
  - SKIMMED: Section viewed <30 seconds
  - MASTERED: Consistent high scores (>=75%, 2+ attempts)
  - LEARNING: Moderate progress (score >=50%)
  - STRUGGLING: Studied but low scores
"""
from database import get_db


def classify_learning_status(student_id: int, course_id: int) -> dict:
    """Classify each concept's learning status using mastery + behavior.

    Uses deterministic rules — no ML needed.

    Returns:
        Dict mapping concept name → status dict with classification and details.
    """
    db = get_db()

    # Get all concepts for this course
    concept_rows = db.execute(
        "SELECT name FROM concepts WHERE course_id = ?",
        (course_id,)
    ).fetchall()

    # Get mastery data
    mastery_rows = db.execute(
        "SELECT concept, mastery_score, attempts FROM mastery WHERE student_id = ? AND course_id = ?",
        (student_id, course_id)
    ).fetchall()
    mastery = {m["concept"]: {"score": m["mastery_score"], "attempts": m["attempts"]} for m in mastery_rows}

    # Get learning events
    events = db.execute(
        "SELECT event_type, section_index, duration_seconds, created_at FROM learning_events WHERE student_id = ? AND course_id = ? ORDER BY created_at ASC",
        (student_id, course_id)
    ).fetchall()

    # Get quiz history for trend detection
    quiz_rows = db.execute(
        "SELECT score, taken_at FROM quiz_history WHERE student_id = ? AND course_id = ? ORDER BY taken_at ASC",
        (student_id, course_id)
    ).fetchall()

    db.close()

    # Aggregate behavior signals
    has_opened_lesson = any(e["event_type"] == "lesson_opened" for e in events)
    section_views = [e for e in events if e["event_type"] == "section_viewed"]
    total_view_duration = sum(e["duration_seconds"] or 0 for e in section_views)

    # Detect mastery trend (declining = forgotten)
    quiz_scores = [q["score"] for q in quiz_rows]
    peak_score = max(quiz_scores) if quiz_scores else 0
    latest_score = quiz_scores[-1] if quiz_scores else 0

    # ── Classify each concept ─────────────────────────
    statuses = {}
    for concept_row in concept_rows:
        concept = concept_row["name"]
        m = mastery.get(concept, {"score": 0, "attempts": 0})
        score = m["score"]
        attempts = m["attempts"]

        if attempts == 0 and not has_opened_lesson:
            status = "not_learned"
            reason = "You haven't studied this concept yet"
            icon = "📭"
        elif attempts == 0 and has_opened_lesson and total_view_duration < 30:
            status = "skimmed"
            reason = "You briefly viewed this — spend more time studying"
            icon = "👀"
        elif attempts >= 2 and peak_score >= 80 and score < 50:
            status = "forgotten"
            reason = f"Your mastery dropped from {peak_score}% to {score}% — review needed"
            icon = "🔄"
        elif score >= 75 and attempts >= 2:
            status = "mastered"
            reason = "Strong and consistent understanding"
            icon = "✅"
        elif score >= 50:
            status = "learning"
            reason = "Making progress — keep practicing"
            icon = "📈"
        elif has_opened_lesson and total_view_duration >= 30:
            status = "struggling"
            reason = "You've studied this but need more practice"
            icon = "💪"
        else:
            status = "not_learned"
            reason = "Study this topic and take a quiz"
            icon = "📭"

        statuses[concept] = {
            "status": status,
            "reason": reason,
            "icon": icon,
            "mastery": score,
            "attempts": attempts,
        }

    return statuses


def get_adaptive_recommendation(student_id: int, course_id: int) -> dict:
    """Generate adaptive recommendation based on mastery + behavior + graph.

    Deterministic two-dimensional decision logic.
    """
    db = get_db()

    # Get student mastery
    mastery_rows = db.execute(
        "SELECT concept, mastery_score, attempts FROM mastery WHERE student_id = ? AND course_id = ?",
        (student_id, course_id)
    ).fetchall()
    mastery = {m["concept"]: {"score": m["mastery_score"], "attempts": m["attempts"]} for m in mastery_rows}

    # Get graph (relationships)
    graph_rows = db.execute(
        "SELECT source_concept, target_concept, relation_type FROM relationships WHERE course_id = ?",
        (course_id,)
    ).fetchall()

    # Get all concepts
    concept_rows = db.execute(
        "SELECT name FROM concepts WHERE course_id = ?",
        (course_id,)
    ).fetchall()

    # Get learning events
    events = db.execute(
        "SELECT event_type, duration_seconds FROM learning_events WHERE student_id = ? AND course_id = ?",
        (student_id, course_id)
    ).fetchall()

    # Get quiz trend
    quiz_rows = db.execute(
        "SELECT score FROM quiz_history WHERE student_id = ? AND course_id = ? ORDER BY taken_at ASC",
        (student_id, course_id)
    ).fetchall()

    db.close()

    all_concepts = [c["name"] for c in concept_rows]
    graph = [(g["source_concept"], g["target_concept"]) for g in graph_rows]

    # Behavioral signals
    has_opened = any(e["event_type"] == "lesson_opened" for e in events)
    total_study_time = sum(e["duration_seconds"] or 0 for e in events if e["event_type"] == "section_viewed")
    quiz_scores = [q["score"] for q in quiz_rows]
    peak_score = max(quiz_scores) if quiz_scores else 0

    # Classify concepts
    weak_concepts = []
    strong_concepts = []
    unstudied_concepts = []
    forgotten_concepts = []

    for concept in all_concepts:
        if concept in mastery:
            score = mastery[concept]["score"]
            attempts = mastery[concept]["attempts"]

            if attempts >= 2 and peak_score >= 80 and score < 50:
                forgotten_concepts.append({"concept": concept, "mastery": score, "peak": peak_score})
            elif score < 50:
                weak_concepts.append({"concept": concept, "mastery": score})
            else:
                strong_concepts.append({"concept": concept, "mastery": score})
        else:
            unstudied_concepts.append(concept)

    # Check prerequisites of weak concepts
    weak_prerequisites = []
    for source, target in graph:
        if target in [w["concept"] for w in weak_concepts]:
            source_mastery = mastery.get(source, {}).get("score", 0)
            if source_mastery < 60:
                weak_prerequisites.append({
                    "concept": source,
                    "mastery": source_mastery,
                    "needed_for": target,
                })

    # Overall mastery
    all_scores = [m["score"] for m in mastery.values()]
    avg_mastery = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0

    # ── Deterministic decision logic ──────────────────
    if avg_mastery >= 80:
        action = "advance"
        reason = "Excellent mastery! You've demonstrated strong understanding across all concepts."
    elif forgotten_concepts:
        action = "review"
        forgotten_names = [f["concept"] for f in forgotten_concepts[:3]]
        reason = f"Your knowledge of {', '.join(forgotten_names)} has declined. Review needed."
    elif not has_opened and avg_mastery < 50:
        action = "study"
        reason = "You haven't viewed the lesson content yet. Read through the sections before quizzes."
    elif has_opened and total_study_time < 60 and avg_mastery < 50:
        action = "study_deeper"
        reason = "You briefly viewed the material but need more study time."
    elif avg_mastery >= 50:
        action = "practice"
        if weak_concepts:
            weak_names = [w["concept"] for w in weak_concepts[:3]]
            reason = f"Good progress! Focus on improving: {', '.join(weak_names)}."
        else:
            reason = "Good progress! Keep practicing to strengthen your knowledge."
    else:
        action = "remediate"
        if weak_prerequisites:
            prereq_names = [wp["concept"] for wp in weak_prerequisites[:3]]
            reason = f"Strengthen prerequisites first: {', '.join(prereq_names)}."
        else:
            reason = "More study needed. Use the AI Tutor for help."

    return {
        "action": action,
        "reason": reason,
        "avg_mastery": avg_mastery,
        "weak_concepts": weak_concepts,
        "strong_concepts": strong_concepts,
        "unstudied_concepts": unstudied_concepts,
        "forgotten_concepts": forgotten_concepts,
        "weak_prerequisites": weak_prerequisites,
        "graph": [{"source": s, "target": t} for s, t in graph],
        "behavior": {
            "has_opened_lesson": has_opened,
            "total_study_seconds": total_study_time,
            "quiz_attempts": len(quiz_scores),
            "peak_score": peak_score,
        },
    }
