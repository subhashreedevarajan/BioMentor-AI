"""BioMentor AI — Admin API Routes

Grounded Course Generation Pipeline:
  1. Upload PDF → extract full text
  2. course_agent: Extract metadata (title, summary, domain — from text only)
  3. course_agent: Detect sections → generate structured content per section
  4. graph_agent: Extract knowledge graph (no hallucination)
  5. validation_agent: Second-pass grounding check
  6. Save structured results to normalized DB
  7. RAG ingest for chatbot
"""
import os
import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from config import UPLOADS_DIR
from database import get_db
from rag.ingestion import process_upload, extract_text_from_file
from rag.retriever import collection as chroma_collection, get_collection_stats
from agents.course_agent import generate_course_from_text
from agents.graph_agent import extract_knowledge_graph
from agents.validation_agent import validate_concepts

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ── Upload PDF → Grounded Course Generation ───────────
@router.post("/upload")
async def upload_material(
    file: UploadFile = File(...),
    education_level: str = Form("UG"),
    difficulty: int = Form(3),
):
    """Upload a PDF/text file → extract text → grounded course generation.

    Pipeline:
      1. Save file & extract full text
      2. Generate course metadata (grounded in text)
      3. Detect sections & generate content per section
      4. Extract knowledge graph (grounded in text)
      5. Validate concepts against source text
      6. Save everything to normalized DB
      7. RAG ingest for chatbot
    """

    # Validate file type
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pdf", ".txt", ".md"):
        raise HTTPException(400, "Only PDF, TXT, and MD files are supported")

    # Save file
    file_path = os.path.join(UPLOADS_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Step 1: Extract FULL text from file
    raw_text = extract_text_from_file(file_path)
    if not raw_text.strip():
        raise HTTPException(400, "Could not extract text from file")

    print(f"📄 Extracted {len(raw_text)} characters from {file.filename}")

    # Step 2: RAG ingest (for chatbot, separate from course generation)
    chunks = process_upload(file_path, education_level, difficulty)
    try:
        chroma_collection.add(
            ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[c["metadata"] for c in chunks],
        )
    except Exception as e:
        print(f"  ⚠️ RAG ingest warning: {e}")

    # Step 3: Grounded course generation (metadata + sections)
    course_data = generate_course_from_text(raw_text, education_level)

    # Step 4: Extract knowledge graph (grounded)
    print("  🔍 Extracting knowledge graph...")
    graph_data = extract_knowledge_graph(raw_text)

    # Step 5: Validate all concepts against source text
    all_concepts = list(set(
        course_data.get("concepts", []) +
        [c["name"] for c in graph_data.get("concepts", [])]
    ))
    validated_concepts = validate_concepts(raw_text, all_concepts)

    # Step 6: Save to database
    db = get_db()
    cursor = db.cursor()

    # Save course
    cursor.execute("""
        INSERT INTO courses (title, summary, main_topic, domain, difficulty, education_level, raw_text, source_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        course_data["title"],
        course_data.get("summary", ""),
        course_data.get("main_topic", ""),
        course_data.get("domain", "Not specified in text"),
        course_data.get("difficulty", "Intermediate"),
        education_level,
        raw_text,
        file.filename,
    ))
    course_id = cursor.lastrowid

    # Save sections
    sections = course_data.get("sections", [])
    for i, section in enumerate(sections):
        cursor.execute("""
            INSERT INTO course_sections (
                course_id, section_index, section_title, detailed_explanation,
                key_points, explicit_concepts, mentioned_challenges,
                mentioned_applications, section_summary, source_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            course_id,
            i,
            section.get("section_title", f"Section {i+1}"),
            section.get("detailed_explanation", ""),
            json.dumps(section.get("key_points", [])),
            json.dumps(section.get("explicit_concepts", [])),
            json.dumps(section.get("mentioned_challenges", [])),
            json.dumps(section.get("mentioned_applications", [])),
            section.get("section_summary", ""),
            section.get("source_text", ""),
        ))

    # Save validated concepts
    for concept in validated_concepts:
        cursor.execute(
            "INSERT OR IGNORE INTO concepts (course_id, name) VALUES (?, ?)",
            (course_id, concept)
        )

    # Save graph relationships
    for rel in graph_data.get("relationships", []):
        cursor.execute(
            "INSERT INTO relationships (course_id, source_concept, target_concept, relation_type) VALUES (?, ?, ?, ?)",
            (course_id, rel["source"], rel["target"], rel.get("relation_type", "related_to"))
        )

    # Save material record
    cursor.execute("""
        INSERT INTO materials (filename, education_level, difficulty, course_id)
        VALUES (?, ?, ?, ?)
    """, (file.filename, education_level, difficulty, course_id))

    db.commit()
    db.close()

    return {
        "message": "Course generated successfully",
        "course_id": course_id,
        "filename": file.filename,
        "course_title": course_data["title"],
        "sections_generated": len(sections),
        "concepts_extracted": len(validated_concepts),
        "graph_relationships": len(graph_data.get("relationships", [])),
        "chunks_created": len(chunks),
    }


# ── List Courses ──────────────────────────────────────
@router.get("/courses")
def list_courses():
    """Get all generated courses with their concepts."""
    db = get_db()

    courses = db.execute("""
        SELECT id, title, summary, main_topic, domain, difficulty, education_level,
               source_filename, additional_notes, created_at
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
            "id": c["id"],
            "title": c["title"],
            "summary": c["summary"],
            "main_topic": c["main_topic"],
            "domain": c["domain"],
            "difficulty": c["difficulty"],
            "education_level": c["education_level"],
            "source_filename": c["source_filename"],
            "additional_notes": c["additional_notes"],
            "created_at": c["created_at"],
            "concepts": [cp["name"] for cp in concepts],
            "section_count": section_count,
        })

    db.close()
    return {"courses": result}


# ── Delete Course ─────────────────────────────────────
@router.delete("/courses/{course_id}")
def delete_course(course_id: int):
    """Delete a course and all related data (cascades)."""
    db = get_db()
    course = db.execute("SELECT id FROM courses WHERE id = ?", (course_id,)).fetchone()
    if not course:
        raise HTTPException(404, "Course not found")

    db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    db.commit()
    db.close()
    return {"message": "Course deleted"}


# ── System Stats ──────────────────────────────────────
@router.get("/stats")
def get_stats():
    """System statistics for admin dashboard."""
    db = get_db()

    total_courses = db.execute("SELECT COUNT(*) as c FROM courses").fetchone()["c"]
    total_concepts = db.execute("SELECT COUNT(*) as c FROM concepts").fetchone()["c"]
    total_materials = db.execute("SELECT COUNT(*) as c FROM materials").fetchone()["c"]
    total_students = db.execute("SELECT COUNT(*) as c FROM users WHERE role = 'student'").fetchone()["c"]
    total_sections = db.execute("SELECT COUNT(*) as c FROM course_sections").fetchone()["c"]
    total_relationships = db.execute("SELECT COUNT(*) as c FROM relationships").fetchone()["c"]

    try:
        vector_count = chroma_collection.count()
    except:
        vector_count = 0

    db.close()

    return {
        "total_courses": total_courses,
        "total_concepts": total_concepts,
        "total_sections": total_sections,
        "total_relationships": total_relationships,
        "total_materials": total_materials,
        "total_students": total_students,
        "vector_store": {"total_documents": vector_count},
    }


# ── Materials List ────────────────────────────────────
@router.get("/materials")
def list_materials():
    """List all uploaded materials."""
    db = get_db()
    materials = db.execute("""
        SELECT m.*, c.title as course_title
        FROM materials m
        LEFT JOIN courses c ON m.course_id = c.id
        ORDER BY m.uploaded_at DESC
    """).fetchall()
    db.close()
    return {"materials": [dict(m) for m in materials]}


# ── Reference Links (Admin Enrichment) ────────────────
class AddReferenceRequest(BaseModel):
    title: str
    url: str

@router.post("/courses/{course_id}/references")
def add_reference(course_id: int, req: AddReferenceRequest):
    """Add a reference link to a course (display-only, does NOT affect graph)."""
    db = get_db()
    course = db.execute("SELECT id FROM courses WHERE id = ?", (course_id,)).fetchone()
    if not course:
        raise HTTPException(404, "Course not found")

    db.execute(
        "INSERT INTO course_references (course_id, title, url) VALUES (?, ?, ?)",
        (course_id, req.title, req.url)
    )
    db.commit()
    db.close()
    return {"message": "Reference added"}

@router.delete("/references/{ref_id}")
def delete_reference(ref_id: int):
    """Delete a reference link."""
    db = get_db()
    db.execute("DELETE FROM course_references WHERE id = ?", (ref_id,))
    db.commit()
    db.close()
    return {"message": "Reference deleted"}

@router.get("/courses/{course_id}/references")
def get_references(course_id: int):
    """Get all reference links for a course."""
    db = get_db()
    refs = db.execute(
        "SELECT id, title, url FROM course_references WHERE course_id = ?", (course_id,)
    ).fetchall()
    db.close()
    return {"references": [dict(r) for r in refs]}


# ── Admin Notes (Enrichment) ──────────────────────────
class UpdateNotesRequest(BaseModel):
    notes: str

@router.put("/courses/{course_id}/notes")
def update_notes(course_id: int, req: UpdateNotesRequest):
    """Update admin notes for a course (display-only, does NOT affect graph)."""
    db = get_db()
    course = db.execute("SELECT id FROM courses WHERE id = ?", (course_id,)).fetchone()
    if not course:
        raise HTTPException(404, "Course not found")

    db.execute(
        "UPDATE courses SET additional_notes = ? WHERE id = ?",
        (req.notes, course_id)
    )
    db.commit()
    db.close()
    return {"message": "Notes updated"}
