"""
Pydantic models for all API request/response contracts.

Keeping models in a dedicated module (rather than inline in routes) lets us
import them from tests without pulling in FastAPI or route dependencies.
"""
from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class JobStatus(str, Enum):
    """Possible states for a deal analysis job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class AnalyzeResponse(BaseModel):
    """Returned immediately after POST /analyze."""

    job_id: str
    status: JobStatus = JobStatus.QUEUED
    message: str = "Job enqueued"


class StatusResponse(BaseModel):
    """Returned by GET /status/{job_id}."""

    job_id: str
    status: JobStatus
    current_agent: Optional[str] = None
    progress_pct: int = Field(ge=0, le=100)
    error: Optional[str] = None

    @field_validator("progress_pct", mode="before")
    @classmethod
    def clamp_progress(cls, v: Any) -> int:
        """Ensure progress is always a valid percentage."""
        return max(0, min(100, int(v)))


class RiskDimension(BaseModel):
    """A single scored risk dimension."""

    score: int = Field(ge=1, le=5)
    rationale: str
    evidence: list[str]


class RiskAssessment(BaseModel):
    """Structured risk output from RiskAnalystAgent."""

    market_risk: RiskDimension
    financial_risk: RiskDimension
    property_risk: RiskDimension
    liquidity_risk: RiskDimension
    execution_risk: RiskDimension
    overall_risk_score: float
    investment_recommendation: str
    key_risks: list[str]


class DataCitation(BaseModel):
    """Links a memo claim to its source."""

    claim: str
    source: str


class MemoResult(BaseModel):
    """The full structured investment memo returned by GET /result/{job_id}."""

    job_id: str
    status: JobStatus
    deal_metrics: Optional[dict[str, Any]] = None
    market_data: Optional[dict[str, Any]] = None
    risk_scores: Optional[dict[str, Any]] = None
    memo: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    # Observability fields — populated after pipeline completes
    latency_ms: Optional[int] = None
    total_tokens: Optional[int] = None
    langsmith_trace_url: Optional[str] = None  # populated in Workstream B

    @classmethod
    def from_agent_state(
        cls,
        job_id: str,
        state: dict[str, Any],
        latency_ms: Optional[int] = None,
        langsmith_trace_url: Optional[str] = None,
    ) -> "MemoResult":
        """Construct a MemoResult from a completed AgentState dict."""
        memo_json = state.get("memo_draft")
        memo = json.loads(memo_json) if memo_json else None

        has_error = bool(state.get("error"))
        is_complete = memo is not None and not has_error

        return cls(
            job_id=job_id,
            status=JobStatus.FAILED if has_error else (JobStatus.COMPLETE if is_complete else JobStatus.RUNNING),
            deal_metrics=state.get("deal_metrics"),
            market_data=state.get("market_data"),
            risk_scores=state.get("risk_scores"),
            memo=memo,
            error=state.get("error"),
            latency_ms=latency_ms,
            total_tokens=state.get("total_tokens_used"),
            langsmith_trace_url=langsmith_trace_url,
        )
