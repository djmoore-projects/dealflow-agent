"""
/analyze routes: PDF upload, job status polling, result retrieval.

Job lifecycle:
  POST /analyze → job enqueued → background task starts pipeline
  GET /status/{job_id} → poll until status == "complete" or "failed"
  GET /result/{job_id} → full memo JSON

Job state is stored in the module-level dict JOB_STORE. In Phase 2 this
becomes a Redis hash — the interface (job_id → state dict) stays identical,
only the backing store changes.
"""
from __future__ import annotations

import asyncio
import io
import time
import uuid
from typing import Any

from langchain_core.runnables import RunnableConfig
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile
from pypdf import PdfReader

from src.agents.supervisor import AgentState, build_graph
from src.api.models import (
    AnalyzeResponse,
    JobStatus,
    MemoResult,
    StatusResponse,
)
from src.utils.logging import get_logger
from src.utils.tracing import TracingConfig

logger = get_logger(__name__)
router = APIRouter()

# In-process job store: job_id → {"status": ..., "state": AgentState | None, ...}
JOB_STORE: dict[str, dict[str, Any]] = {}

# Compiled graph — built once at module load, reused for all jobs
_GRAPH = build_graph()

# Maps current_agent name to approximate progress percentage
_AGENT_PROGRESS: dict[str, int] = {
    "document_analyst": 15,
    "market_research": 40,
    "risk_analyst": 65,
    "memo_writer": 85,
    "__end__": 100,
}


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract raw text from PDF bytes using pypdf."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


async def _run_pipeline(job_id: str, document_text: str, tracing: TracingConfig) -> None:
    """Execute the LangGraph pipeline for a job. Runs as a background task."""
    logger.info("Pipeline starting", job_id=job_id)
    JOB_STORE[job_id]["status"] = JobStatus.RUNNING

    initial_state: AgentState = {
        "messages": [],
        "document_text": document_text,
        "deal_metrics": None,
        "market_data": None,
        "risk_scores": None,
        "memo_draft": None,
        "current_agent": "supervisor",
        "error": None,
        "total_tokens_used": 0,
        "job_id": job_id,
    }

    # Pre-generate a run_id so we can retrieve the LangSmith trace URL after
    # ainvoke completes. When tracing is disabled this ID is still generated
    # but never sent anywhere.
    langgraph_run_id = uuid.uuid4()
    run_config = RunnableConfig(
        run_id=langgraph_run_id,
        tags=["dealflow-agent"],
        metadata={"job_id": job_id},
    )

    try:
        t0 = time.monotonic()
        final_state = await _GRAPH.ainvoke(initial_state, config=run_config)
        latency_ms = int((time.monotonic() - t0) * 1000)

        JOB_STORE[job_id]["state"] = final_state
        JOB_STORE[job_id]["latency_ms"] = latency_ms

        # Resolve LangSmith URL — does a single API call; None if tracing off
        JOB_STORE[job_id]["langsmith_trace_url"] = tracing.get_run_url(langgraph_run_id)

        has_error = bool(final_state.get("error"))
        JOB_STORE[job_id]["status"] = JobStatus.FAILED if has_error else JobStatus.COMPLETE
        logger.info(
            "Pipeline complete",
            job_id=job_id,
            status=JOB_STORE[job_id]["status"],
            latency_ms=latency_ms,
            tokens=final_state.get("total_tokens_used", 0),
            langsmith_run_id=str(langgraph_run_id),
            error=final_state.get("error"),
        )
    except Exception as exc:
        logger.error("Pipeline crashed", job_id=job_id, error=str(exc))
        JOB_STORE[job_id]["status"] = JobStatus.FAILED
        JOB_STORE[job_id]["error"] = str(exc)


@router.post("/analyze", response_model=AnalyzeResponse, status_code=202)
async def analyze(
    request: Request,
    file: UploadFile,
    background_tasks: BackgroundTasks,
) -> AnalyzeResponse:
    """Accept a PDF upload and enqueue the analysis pipeline.

    Args:
        file: The PDF deal document. Must be Content-Type application/pdf.

    Returns:
        job_id to use for polling /status and /result.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    try:
        document_text = _extract_pdf_text(pdf_bytes)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"PDF extraction failed: {exc}") from exc

    if not document_text.strip():
        raise HTTPException(status_code=422, detail="PDF contains no extractable text (may be scanned image)")

    job_id = str(uuid.uuid4())
    JOB_STORE[job_id] = {"status": JobStatus.QUEUED, "state": None, "error": None}

    tracing: TracingConfig = getattr(request.app.state, "tracing", TracingConfig(api_key=None, project="dealflow-agent"))
    background_tasks.add_task(_run_pipeline, job_id, document_text, tracing)
    logger.info("Job enqueued", job_id=job_id, filename=file.filename, text_chars=len(document_text))

    return AnalyzeResponse(job_id=job_id)


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str) -> StatusResponse:
    """Return the current status and progress of a job.

    Poll this endpoint until status is "complete" or "failed".
    Suggested polling interval: 3 seconds.
    """
    if job_id not in JOB_STORE:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    job = JOB_STORE[job_id]
    state: dict = job.get("state") or {}
    current_agent = state.get("current_agent", "supervisor")
    progress = _AGENT_PROGRESS.get(current_agent, 5)

    if job["status"] == JobStatus.COMPLETE:
        progress = 100
    elif job["status"] == JobStatus.FAILED:
        progress = 0

    return StatusResponse(
        job_id=job_id,
        status=job["status"],
        current_agent=current_agent if job["status"] == JobStatus.RUNNING else None,
        progress_pct=progress,
        error=job.get("error") or state.get("error"),
    )


@router.get("/result/{job_id}", response_model=MemoResult)
async def get_result(job_id: str) -> MemoResult:
    """Return the full memo and all intermediate agent outputs.

    Returns HTTP 202 if the job is still running, 200 when complete.
    """
    if job_id not in JOB_STORE:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    job = JOB_STORE[job_id]
    status = job["status"]

    if status == JobStatus.QUEUED:
        raise HTTPException(status_code=202, detail="Job is queued, not yet started")

    if status == JobStatus.RUNNING:
        raise HTTPException(status_code=202, detail="Job is still running")

    state = job.get("state") or {}
    return MemoResult.from_agent_state(
        job_id,
        state,
        latency_ms=job.get("latency_ms"),
        langsmith_trace_url=job.get("langsmith_trace_url"),
    )
