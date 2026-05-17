"""
RAG ingestion pipeline: PDF → chunks → embeddings → pgvector.

Design choices:
- RecursiveCharacterTextSplitter preserves sentence boundaries better than
  fixed-size chunking, reducing semantic fragmentation across chunk edges.
- chunk_overlap=100 ensures context bleeds across boundaries for dense
  financial documents where a metric may span two paragraphs.
- Metadata (page_number, source) flows through to retrieval results so
  the MemoWriter can emit proper citations.
"""

import os
from pathlib import Path
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
COLLECTION_NAME = "deal_documents"


def _get_embeddings():  # type: ignore[return]
    """Return configured embedding model (import deferred to avoid hard dep in tests)."""
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    )


def _get_vector_store():  # type: ignore[return]
    """Return configured PGVector store connected to the running postgres."""
    from langchain_postgres import PGVector

    return PGVector(
        embeddings=_get_embeddings(),
        collection_name=COLLECTION_NAME,
        connection=os.getenv("DATABASE_URL", ""),
        use_jsonb=True,
    )


def ingest_pdf(pdf_path: str | Path, job_id: str) -> int:
    """Load a PDF, chunk it, embed, and upsert into pgvector.

    Args:
        pdf_path: Path to the uploaded PDF file.
        job_id: Used as metadata so chunks are queryable per-job.

    Returns:
        Number of chunks ingested.
    """
    pdf_path = Path(pdf_path)
    logger.info("Starting PDF ingestion", job_id=job_id, path=str(pdf_path))

    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    loader = PyPDFLoader(str(pdf_path))
    raw_docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(raw_docs)

    # Attach job-level metadata so retrieval can filter by job
    for chunk in chunks:
        chunk.metadata["job_id"] = job_id
        chunk.metadata["source"] = pdf_path.name

    store = _get_vector_store()
    ids = store.add_documents(chunks)

    logger.info("PDF ingestion complete", job_id=job_id, chunks=len(ids))
    return len(ids)


def ingest_text(text: str, metadata: dict[str, Any], job_id: str) -> int:
    """Ingest raw text (for testing without a real PDF).

    Args:
        text: Document text content.
        metadata: Additional metadata fields.
        job_id: Job identifier for filtering.

    Returns:
        Number of chunks ingested.
    """
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    doc = Document(page_content=text, metadata={**metadata, "job_id": job_id})
    chunks = splitter.split_documents([doc])

    store = _get_vector_store()
    ids = store.add_documents(chunks)
    logger.info("Text ingestion complete", job_id=job_id, chunks=len(ids))
    return len(ids)
