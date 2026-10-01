"""BioMentor AI — SQLite Database

Normalized schema for grounded course generation:
  - courses: metadata + raw_text (source of truth)
  - course_sections: per-section structured content
  - concepts: extracted concepts per course
  - relationships: directed edges between concepts
  - mastery, quiz_history, learning_events, course_references: analytics + enrichment
"""
import sqlite3
import os
from config import DB_PATH


def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        -- Users
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'student')),
            education_level TEXT DEFAULT 'UG',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Courses (metadata + raw source text)
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            summary TEXT DEFAULT '',
            main_topic TEXT DEFAULT '',
            domain TEXT DEFAULT 'Not specified in text',
            difficulty TEXT DEFAULT 'Intermediate',
            education_level TEXT DEFAULT 'UG',
            raw_text TEXT NOT NULL,
            additional_notes TEXT DEFAULT '',
            source_filename TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        -- Course sections (per-section structured content)
        CREATE TABLE IF NOT EXISTS course_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            section_index INTEGER NOT NULL,
            section_title TEXT NOT NULL,
            detailed_explanation TEXT NOT NULL,
            key_points TEXT DEFAULT '[]',
            explicit_concepts TEXT DEFAULT '[]',
            mentioned_challenges TEXT DEFAULT '[]',
            mentioned_applications TEXT DEFAULT '[]',
            section_summary TEXT DEFAULT '',
            source_text TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
        );

        -- Concepts extracted per course
        CREATE TABLE IF NOT EXISTS concepts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            UNIQUE(course_id, name)
        );

        -- Directed relationships between concepts
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            source_concept TEXT NOT NULL,
            target_concept TEXT NOT NULL,
            relation_type TEXT NOT NULL DEFAULT 'related_to',
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
        );

        -- Student mastery per concept per course
        CREATE TABLE IF NOT EXISTS mastery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            concept TEXT NOT NULL,
            mastery_score REAL DEFAULT 0.0,
            attempts INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(id),
            UNIQUE(student_id, course_id, concept)
        );

        -- Quiz history
        CREATE TABLE IF NOT EXISTS quiz_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            score REAL NOT NULL,
            total_questions INTEGER NOT NULL,
            correct_answers INTEGER NOT NULL,
            details TEXT,
            taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(id)
        );

        -- Materials (uploaded files)
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            education_level TEXT DEFAULT 'UG',
            difficulty INTEGER DEFAULT 3,
            course_id INTEGER,
            uploaded_by INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (uploaded_by) REFERENCES users(id),
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL
        );

        -- Chat history for AI tutor
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(id)
        );

        -- Learning events for behavioral intelligence
        CREATE TABLE IF NOT EXISTS learning_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            section_index INTEGER,
            duration_seconds INTEGER DEFAULT 0,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(id)
        );

        -- Reference links for admin enrichment
        CREATE TABLE IF NOT EXISTS course_references (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
        );

        -- Seed default accounts
        INSERT OR IGNORE INTO users (username, password, role)
        VALUES ('admin', 'admin123', 'admin');

        INSERT OR IGNORE INTO users (username, password, role, education_level)
        VALUES ('student', 'student123', 'student', 'UG');
    """)

    conn.commit()
    conn.close()
    print(f"✅ Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
