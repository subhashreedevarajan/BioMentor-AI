"""BioMentor AI — Student Mastery Graph

Tracks per-student, per-concept mastery scores. Updated dynamically
after quizzes. Creates a cognitive profile of each learner.
"""
import sqlite3
from datetime import datetime
from config import DB_PATH


class MasteryGraph:
    """Student mastery tracking with SQLite persistence."""

    def _conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def get_mastery(self, student_id: int, topic_id: str) -> dict:
        """Get mastery score for a student on a specific topic."""
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM mastery WHERE student_id = ? AND topic_id = ?",
            (student_id, topic_id)
        ).fetchone()
        conn.close()

        if row:
            return dict(row)
        return {
            "student_id": student_id,
            "topic_id": topic_id,
            "mastery_score": 0.0,
            "attempts": 0,
            "last_updated": None,
        }

    def update_mastery(self, student_id: int, topic_id: str, new_score: float):
        """Update mastery score using weighted moving average.

        Formula: mastery = (old_mastery * 0.4) + (new_score * 0.6)
        This gives more weight to recent performance while preserving history.
        """
        conn = self._conn()
        existing = self.get_mastery(student_id, topic_id)

        if existing["attempts"] > 0:
            # Weighted average: 40% old + 60% new
            updated_score = (existing["mastery_score"] * 0.4) + (new_score * 0.6)
        else:
            updated_score = new_score

        updated_score = max(0, min(100, round(updated_score, 1)))

        conn.execute("""
            INSERT INTO mastery (student_id, topic_id, mastery_score, attempts, last_updated)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(student_id, topic_id) DO UPDATE SET
                mastery_score = ?,
                attempts = attempts + 1,
                last_updated = ?
        """, (
            student_id, topic_id, updated_score, datetime.now().isoformat(),
            updated_score, datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
        return updated_score

    def get_full_profile(self, student_id: int) -> list:
        """Get all mastery scores for a student."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM mastery WHERE student_id = ? ORDER BY mastery_score ASC",
            (student_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_weak_topics(self, student_id: int, threshold: float = 50.0) -> list:
        """Get topics where mastery is below threshold."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM mastery WHERE student_id = ? AND mastery_score < ? ORDER BY mastery_score ASC",
            (student_id, threshold)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_strong_topics(self, student_id: int, threshold: float = 70.0) -> list:
        """Get topics where mastery is above threshold."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM mastery WHERE student_id = ? AND mastery_score >= ? ORDER BY mastery_score DESC",
            (student_id, threshold)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_topic_mastery_map(self, student_id: int) -> dict:
        """Get a dict of {topic_id: mastery_score} for fast lookup."""
        profile = self.get_full_profile(student_id)
        return {entry["topic_id"]: entry["mastery_score"] for entry in profile}


# Singleton
mastery_graph = MasteryGraph()
