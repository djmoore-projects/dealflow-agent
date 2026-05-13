"""
RAG retrieval: similarity search against pgvector with metadata passthrough.

Returning a typed Pydantic model (rather than raw LangChain Document dicts)
gives us a serializable schema that the MCP server can return as JSON and
the MemoWriter agent can cite with page numbers.
"""

import os
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from langchain_postgres import PGVector

logger = get_logger(__name__)

COLLECTION_NAME = "deal_documents"


class RetrievedChunk(BaseModel):
    """A single document chunk returned from similarity search."""

    content: str
    page_number: Optional[int] = None
    source: Optional[str] = None
    job_id: Optional[str] = None
    score: float


def _get_store() -> "PGVector":
    """Return the configured vector store (not cached — cheap to construct).

    Imports are deferred so that RetrievedChunk can be imported in tests
    without requiring langchain_postgres and langchain_openai to be installed.
    """
    from langchain_openai import OpenAIEmbeddings
    from langchain_postgres import PGVector

    embeddings = OpenAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    )
    return PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        connection=os.getenv("DATABASE_URL", ""),
        use_jsonb=True,
    )


def retrieve_chunks(
    query: str,
    k: int = 5,
    job_id: Optional[str] = None,
) -> list[RetrievedChunk]:
    """Retrieve the top-k chunks most similar to query.

    Args:
        query: Natural language question or search string.
        k: Number of results to return.
        job_id: If provided, filter results to chunks from this job.

    Returns:
        List of RetrievedChunk, ordered by descending similarity score.
    """
    logger.info("Retrieving chunks", query=query[:80], k=k, job_id=job_id)
    store = _get_store()

    filter_kwargs: dict = {}
    if job_id:
        filter_kwargs["filter"] = {"job_id": job_id}

    results = store.similarity_search_with_score(query, k=k, **filter_kwargs)

    chunks = [
        RetrievedChunk(
            content=doc.page_content,
            page_number=doc.metadata.get("page"),
            source=doc.metadata.get("source"),
            job_id=doc.metadata.get("job_id"),
            score=float(score),
        )
        for doc, score in results
    ]
    logger.info("Retrieval complete", results=len(chunks))
    return chunks
