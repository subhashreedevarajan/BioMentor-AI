"""BioMentor AI — Evaluation Agent

Scores quiz submissions, calculates per-concept accuracy,
and updates student mastery in the database.
"""
import json
from database import get_db


def evaluate_quiz(student_id: int, course_id: int, questions: list, student_answers: dict) -> dict:
    """Evaluate a quiz submission and update per-concept mastery.

    Args:
        student_id: Student user ID
        course_id: Course being quizzed
        questions: List of question dicts (from quiz_agent)
        student_answers: Dict of {question_index: "A"/"B"/"C"/"D"}

    Returns:
        Evaluation result with scores and feedback
    """
    total = len(questions)
    correct = 0
    per_concept = {}  # {concept: {correct: n, total: n}}
    details = []

    for i, q in enumerate(questions):
        idx = str(i)
        student_answer = student_answers.get(idx, "")
        is_correct = student_answer == q["correct_answer"]

        if is_correct:
            correct += 1

        # Track per-concept accuracy
        tag = q.get("concept_tag", "General")
        if tag not in per_concept:
            per_concept[tag] = {"correct": 0, "total": 0}
        per_concept[tag]["total"] += 1
        if is_correct:
            per_concept[tag]["correct"] += 1

        details.append({
            "question": q["question"],
            "your_answer": student_answer,
            "correct_answer": q["correct_answer"],
            "is_correct": is_correct,
            "explanation": q.get("explanation", ""),
            "concept_tag": tag,
        })

    # Calculate overall percentage
    overall_score = round((correct / total) * 100, 1) if total > 0 else 0

    # Update per-concept mastery in DB
    db = get_db()
    concept_scores = {}

    for concept, stats in per_concept.items():
        quiz_score = round((stats["correct"] / stats["total"]) * 100, 1)
        concept_scores[concept] = quiz_score

        # Get current mastery
        row = db.execute(
            "SELECT mastery_score, attempts FROM mastery WHERE student_id = ? AND course_id = ? AND concept = ?",
            (student_id, course_id, concept)
        ).fetchone()

        if row:
            # Weighted average: old mastery weighted by attempts, new score weighted by 1
            old_score = row["mastery_score"]
            attempts = row["attempts"]
            new_mastery = round(((old_score * attempts) + quiz_score) / (attempts + 1), 1)
            db.execute(
                "UPDATE mastery SET mastery_score = ?, attempts = ?, last_updated = CURRENT_TIMESTAMP WHERE student_id = ? AND course_id = ? AND concept = ?",
                (new_mastery, attempts + 1, student_id, course_id, concept)
            )
        else:
            new_mastery = quiz_score
            db.execute(
                "INSERT INTO mastery (student_id, course_id, concept, mastery_score, attempts) VALUES (?, ?, ?, ?, 1)",
                (student_id, course_id, concept, quiz_score)
            )

        concept_scores[f"{concept}_mastery"] = new_mastery

    # Save quiz history
    db.execute(
        "INSERT INTO quiz_history (student_id, course_id, score, total_questions, correct_answers, details) VALUES (?, ?, ?, ?, ?, ?)",
        (student_id, course_id, overall_score, total, correct, json.dumps(details))
    )

    db.commit()
    db.close()

    # Generate feedback
    if overall_score >= 80:
        feedback = "Excellent work! You have a strong understanding of this course. Ready to advance."
    elif overall_score >= 60:
        feedback = "Good effort! Some concepts need more practice. Review the incorrect answers."
    elif overall_score >= 40:
        feedback = "You're making progress but need more study. Review the weak concepts."
    else:
        feedback = "This material needs significant review. Try the AI Tutor for help with difficult concepts."

    return {
        "overall_score": overall_score,
        "correct_answers": correct,
        "total_questions": total,
        "per_concept_scores": concept_scores,
        "feedback": feedback,
        "details": details,
    }


def get_quiz_history(student_id: int, course_id: int = None) -> list:
    """Get quiz history for a student, optionally filtered by course."""
    db = get_db()
    if course_id:
        rows = db.execute(
            "SELECT * FROM quiz_history WHERE student_id = ? AND course_id = ? ORDER BY taken_at DESC",
            (student_id, course_id)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM quiz_history WHERE student_id = ? ORDER BY taken_at DESC",
            (student_id,)
        ).fetchall()
    db.close()
    return [dict(r) for r in rows]
