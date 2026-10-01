"""BioMentor AI — RAG Retriever

ChromaDB-based vector store for semantic search over ingested materials.
Uses sentence-transformers for local, free embeddings.
"""
import chromadb
from chromadb.utils import embedding_functions
from config import CHROMA_DIR, EMBEDDING_MODEL, TOP_K


# Initialize ChromaDB with persistent storage
_client = chromadb.PersistentClient(path=CHROMA_DIR)
_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL
)

# Get or create the collection
collection = _client.get_or_create_collection(
    name="biomentor_docs",
    embedding_function=_embedding_fn,
    metadata={"hnsw:space": "cosine"}
)


def add_documents(chunks: list):
    """Add processed chunks to the vector store.

    Args:
        chunks: List of dicts with 'id', 'text', 'metadata'
    """
    if not chunks:
        return

    collection.add(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )
    print(f"✅ Added {len(chunks)} chunks to vector store")


def retrieve(query: str, top_k: int = TOP_K, education_level: str = None) -> list:
    """Retrieve relevant document chunks for a query.

    Args:
        query: Search query (topic name or question)
        top_k: Number of results to return
        education_level: Optional filter

    Returns:
        List of relevant text chunks
    """
    where_filter = None
    if education_level:
        where_filter = {"education_level": education_level}

    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count()) if collection.count() > 0 else 1,
            where=where_filter if where_filter and collection.count() > 0 else None,
        )

        if results and results["documents"]:
            return results["documents"][0]
        return []

    except Exception as e:
        print(f"Retrieval error: {e}")
        return []


def get_context_string(query: str, top_k: int = TOP_K) -> str:
    """Get retrieved chunks formatted as a single context string."""
    chunks = retrieve(query, top_k)
    if not chunks:
        return "No additional study materials available for this topic."
    return "\n\n---\n\n".join(chunks)


def get_collection_stats() -> dict:
    """Get stats about the vector store."""
    return {
        "total_documents": collection.count(),
        "collection_name": "biomentor_docs",
    }
