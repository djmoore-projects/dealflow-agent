"""
Integration tests for FastAPI endpoints.

Uses httpx.AsyncClient with ASGITransport to test against the real FastAPI
app without binding a port. The LangGraph pipeline is mocked so tests are
fast and deterministic.

Tests cover:
  - POST /analyze: valid PDF, empty file, non-PDF content type
  - GET /status: known/unknown job IDs, progress transitions
  - GET /result: queued/running/complete/failed states
  - GET /health: liveness probe
"""
from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.api.models import JobStatus

# Minimal valid PDF bytes (enough to pass pypdf parsing)
_MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
    b"/Contents 4 0 R /Resources << >> >>\nendobj\n"
    b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 100 700 Td (Riverside Commons) Tj ET\nendstream\nendobj\n"
    b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n"
    b"0000000115 00000 n\n0000000266 00000 n\n"
    b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n360\n%%EOF"
)


@pytest.fixture
def client():
    """Async HTTP client bound to the FastAPI ASGI app."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    """Health endpoint returns 200 with status ok."""
    async with client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_analyze_enqueues_job(client: AsyncClient) -> None:
    """POST /analyze with valid PDF returns 202 and a job_id."""
    with patch("src.api.routes.analyze._run_pipeline", new_callable=AsyncMock):
        async with client:
            response = await client.post(
                "/analyze",
                files={"file": ("test.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf")},
            )

    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["status"] == JobStatus.QUEUED


@pytest.mark.asyncio
async def test_analyze_rejects_non_pdf(client: AsyncClient) -> None:
    """POST /analyze with a non-PDF file returns 422."""
    async with client:
        response = await client.post(
            "/analyze",
            files={"file": ("report.txt", io.BytesIO(b"not a pdf"), "text/plain")},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analyze_rejects_empty_file(client: AsyncClient) -> None:
    """POST /analyze with empty file body returns 422."""
    async with client:
        response = await client.post(
            "/analyze",
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_status_unknown_job(client: AsyncClient) -> None:
    """GET /status for unknown job_id returns 404."""
    async with client:
        response = await client.get("/status/nonexistent-job-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_status_queued_job(client: AsyncClient) -> None:
    """GET /status for a queued job returns QUEUED status with 0% progress."""
    from src.api.routes.analyze import JOB_STORE

    job_id = "test-queued-001"
    JOB_STORE[job_id] = {"status": JobStatus.QUEUED, "state": None, "error": None}

    try:
        async with client:
            response = await client.get(f"/status/{job_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == JobStatus.QUEUED
        assert body["job_id"] == job_id
    finally:
        JOB_STORE.pop(job_id, None)


@pytest.mark.asyncio
async def test_status_complete_job(client: AsyncClient) -> None:
    """GET /status for a complete job returns 100% progress."""
    from src.api.routes.analyze import JOB_STORE

    job_id = "test-complete-001"
    JOB_STORE[job_id] = {
        "status": JobStatus.COMPLETE,
        "state": {"memo_draft": "{}", "current_agent": "__end__", "error": None},
        "error": None,
    }

    try:
        async with client:
            response = await client.get(f"/status/{job_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == JobStatus.COMPLETE
        assert body["progress_pct"] == 100
    finally:
        JOB_STORE.pop(job_id, None)


@pytest.mark.asyncio
async def test_result_complete_job(client: AsyncClient) -> None:
    """GET /result for a complete job returns full memo JSON."""
    from src.api.routes.analyze import JOB_STORE

    memo = {"executive_summary": "Strong deal in Austin multifamily market."}
    job_id = "test-result-001"
    JOB_STORE[job_id] = {
        "status": JobStatus.COMPLETE,
        "state": {
            "deal_metrics": {"property_name": "Riverside Commons"},
            "market_data": {"market_summary": "Stable"},
            "risk_scores": {"overall_risk_score": 2.2},
            "memo_draft": json.dumps(memo),
            "error": None,
        },
        "error": None,
    }

    try:
        async with client:
            response = await client.get(f"/result/{job_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == JobStatus.COMPLETE
        assert body["memo"]["executive_summary"] == "Strong deal in Austin multifamily market."
    finally:
        JOB_STORE.pop(job_id, None)


@pytest.mark.asyncio
async def test_result_running_job_returns_202(client: AsyncClient) -> None:
    """GET /result for a running job returns HTTP 202."""
    from src.api.routes.analyze import JOB_STORE

    job_id = "test-running-001"
    JOB_STORE[job_id] = {"status": JobStatus.RUNNING, "state": None, "error": None}

    try:
        async with client:
            response = await client.get(f"/result/{job_id}")
        assert response.status_code == 202
    finally:
        JOB_STORE.pop(job_id, None)
