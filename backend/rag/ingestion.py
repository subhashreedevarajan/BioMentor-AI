"""BioMentor AI — RAG Ingestion Pipeline

Processes admin-uploaded PDFs and text files:
1. Extract text from PDF
2. Chunk text with overlap
3. Generate embeddings
4. Store in ChromaDB with metadata
"""
import os
import uuid
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from config import CHUNK_SIZE, CHUNK_OVERLAP, UPLOADS_DIR


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def extract_text_from_file(file_path: str) -> str:
    """Extract text from any supported file."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in (".txt", ".md"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def chunk_text(text: str) -> list:
    """Split text into overlapping chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


def process_upload(file_path: str, education_level: str = "UG", difficulty: int = 3) -> list:
    """Full ingestion pipeline: extract → chunk → return with metadata.

    Args:
        file_path: Path to uploaded file
        education_level: School / UG / PG
        difficulty: 1-5

    Returns:
        List of chunk dicts ready for embedding
    """
    text = extract_text_from_file(file_path)
    chunks = chunk_text(text)

    filename = os.path.basename(file_path)
    result = []
    for i, chunk in enumerate(chunks):
        result.append({
            "id": str(uuid.uuid4()),
            "text": chunk,
            "metadata": {
                "source": filename,
                "education_level": education_level,
                "difficulty": difficulty,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
        })

    return result
