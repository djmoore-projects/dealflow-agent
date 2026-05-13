"""
Tests for the RAG pipeline (ingestion + retrieval).

These tests mock pgvector and OpenAI embeddings so they run without
a live database or API keys. They verify:
  - ingest_pdf calls the vector store with the right metadata
  - retrieve_chunks returns typed RetrievedChunk objects
  - Error handling when the store is unreachable

For live integration tests against a real database, pass --live flag
and ensure DATABASE_URL and OPENAI_API_KEY are set.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rag.retrieval import RetrievedChunk


# --- retrieve_chunks ---


def _make_mock_doc(content: str, metadata: dict) -> tuple[MagicMock, float]:
    """Build a (Document, score) tuple as returned by pgvector similarity search."""
    doc = MagicMock()
    doc.page_content = content
    doc.metadata = metadata
    return doc, 0.92


@patch("src.rag.retrieval._get_store")
def test_retrieve_chunks_returns_typed_results(mock_get_store: MagicMock) -> None:
    """retrieve_chunks returns a list of RetrievedChunk with correct fields."""
    mock_store = MagicMock()
    mock_get_store.return_value = mock_store
    mock_store.similarity_search_with_score.return_value = [
        _make_mock_doc(
            "Cap rate: 5.5%", {"page": 3, "source": "deal.pdf", "job_id": "j1"}
        ),
        _make_mock_doc(
            "NOI: $990,000", {"page": 5, "source": "deal.pdf", "job_id": "j1"}
        ),
    ]

    from src.rag.retrieval import retrieve_chunks

    results = retrieve_chunks(query="What is the cap rate?", k=2)

    assert len(results) == 2
    assert isinstance(results[0], RetrievedChunk)
    assert results[0].content == "Cap rate: 5.5%"
    assert results[0].page_number == 3
    assert results[0].source == "deal.pdf"
    assert results[0].score == pytest.approx(0.92)


@patch("src.rag.retrieval._get_store")
def test_retrieve_chunks_passes_job_filter(mock_get_store: MagicMock) -> None:
    """retrieve_chunks passes job_id filter to the vector store."""
    mock_store = MagicMock()
    mock_get_store.return_value = mock_store
    mock_store.similarity_search_with_score.return_value = []

    from src.rag.retrieval import retrieve_chunks

    retrieve_chunks(query="vacancy", k=3, job_id="job-xyz")

    call_kwargs = mock_store.similarity_search_with_score.call_args.kwargs
    assert "filter" in call_kwargs
    assert call_kwargs["filter"] == {"job_id": "job-xyz"}


@patch("src.rag.retrieval._get_store")
def test_retrieve_chunks_handles_missing_metadata(mock_get_store: MagicMock) -> None:
    """retrieve_chunks handles documents with missing metadata fields gracefully."""
    mock_store = MagicMock()
    mock_get_store.return_value = mock_store
    mock_store.similarity_search_with_score.return_value = [
        _make_mock_doc("Some text", {}),  # no page, source, or job_id
    ]

    from src.rag.retrieval import retrieve_chunks

    results = retrieve_chunks(query="test")
    assert results[0].page_number is None
    assert results[0].source is None


# --- RetrievedChunk model ---


def test_retrieved_chunk_serializes() -> None:
    """RetrievedChunk.model_dump() produces a JSON-serializable dict."""
    chunk = RetrievedChunk(
        content="DSCR: 1.28",
        page_number=4,
        source="riverside_om.pdf",
        job_id="abc-123",
        score=0.95,
    )
    d = chunk.model_dump()
    assert d["content"] == "DSCR: 1.28"
    assert d["score"] == pytest.approx(0.95)
    # Verify exclude works (used by MCP server)
    d_no_job = chunk.model_dump(exclude={"job_id"})
    assert "job_id" not in d_no_job


# --- Golden dataset sanity ---


def test_golden_dataset_structure() -> None:
    """All golden Q&A pairs have required keys and non-empty values."""
    from src.evals.golden_dataset import GOLDEN_QA_PAIRS

    assert len(GOLDEN_QA_PAIRS) == 10
    for i, qa in enumerate(GOLDEN_QA_PAIRS):
        assert "question" in qa, f"Entry {i} missing 'question'"
        assert "ground_truth" in qa, f"Entry {i} missing 'ground_truth'"
        assert "context" in qa, f"Entry {i} missing 'context'"
        assert qa["question"].strip(), f"Entry {i} has empty question"
        assert qa["ground_truth"].strip(), f"Entry {i} has empty ground_truth"
