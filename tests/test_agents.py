"""
Unit tests for individual agent nodes.

Each agent is tested in isolation by mocking the Anthropic client.
This lets us verify:
  1. Correct tool call construction (model, tool_choice, messages shape)
  2. Correct state field written on success
  3. Error written to state["error"] on failure — no exception propagation

We use unittest.mock.AsyncMock to patch the Anthropic async client.
The mock returns a pre-built response that mimics the structure of a real
Anthropic tool_use response block.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_tool_use_response(tool_name: str, tool_input: dict) -> MagicMock:
    """Build a mock Anthropic messages.create response containing one tool_use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = "tu_mock123"

    response = MagicMock()
    response.content = [block]
    return response


# --- DocumentAnalystAgent ---

MOCK_DEAL_METRICS = {
    "property_name": "Riverside Commons",
    "property_type": "multifamily",
    "market": "Austin, TX",
    "purchase_price": 18_000_000,
    "noi": 990_000,
    "cap_rate": 0.055,
    "debt_service_coverage_ratio": 1.28,
    "loan_to_value": 0.75,
    "vacancy_rate": 0.07,
    "year_built": 2018,
    "units": 120,
    "red_flags": ["HVAC end of life in Building C"],
    "submarket": None,
    "gross_rent_multiplier": 10.2,
    "square_footage": 98400,
}


@pytest.mark.asyncio
async def test_document_analyst_success() -> None:
    """DocumentAnalyst writes deal_metrics to state on a valid Claude response."""
    mock_response = _make_tool_use_response("extract_deal_metrics", MOCK_DEAL_METRICS)

    with patch("src.agents.document_analyst.anthropic.AsyncAnthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        from src.agents.document_analyst import run_document_analyst

        state = {"document_text": "Purchase price: $18M...", "job_id": "test-001"}
        result = await run_document_analyst(state)

    assert "deal_metrics" in result
    assert result["deal_metrics"]["property_name"] == "Riverside Commons"
    assert result["deal_metrics"]["cap_rate"] == 0.055
    assert "error" not in result


@pytest.mark.asyncio
async def test_document_analyst_api_error() -> None:
    """DocumentAnalyst writes error to state rather than raising on API failure."""
    with patch("src.agents.document_analyst.anthropic.AsyncAnthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create = AsyncMock(
            side_effect=RuntimeError("API unavailable")
        )

        from src.agents.document_analyst import run_document_analyst

        state = {"document_text": "some text", "job_id": "test-002"}
        result = await run_document_analyst(state)

    assert "error" in result
    assert "document_analyst" in result["error"]
    assert "deal_metrics" not in result


# --- RiskAnalystAgent ---

MOCK_RISK_SCORES = {
    "market_risk": {
        "score": 3,
        "rationale": "Vacancy trending up",
        "evidence": ["Q4 7.8%"],
    },
    "financial_risk": {
        "score": 2,
        "rationale": "DSCR of 1.28 provides cushion",
        "evidence": ["DSCR: 1.28"],
    },
    "property_risk": {
        "score": 3,
        "rationale": "HVAC nearing end of life",
        "evidence": ["Building C HVAC"],
    },
    "liquidity_risk": {
        "score": 2,
        "rationale": "Austin market is deep",
        "evidence": [],
    },
    "execution_risk": {
        "score": 1,
        "rationale": "Sponsor has strong track record",
        "evidence": [],
    },
    "overall_risk_score": 2.2,
    "investment_recommendation": "conditional_pass",
    "key_risks": ["Rising vacancy", "HVAC capex", "Rate sensitivity"],
}


@pytest.mark.asyncio
async def test_risk_analyst_success() -> None:
    """RiskAnalyst writes risk_scores to state on valid Claude response."""
    mock_response = _make_tool_use_response("score_risk", MOCK_RISK_SCORES)

    with patch("src.agents.risk_analyst.anthropic.AsyncAnthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        from src.agents.risk_analyst import run_risk_analyst

        state = {
            "job_id": "test-003",
            "deal_metrics": MOCK_DEAL_METRICS,
            "market_data": {
                "market_cap_rate_range": {"low": 0.05, "high": 0.065},
                "market_summary": "Stable",
            },
        }
        result = await run_risk_analyst(state)

    assert "risk_scores" in result
    assert result["risk_scores"]["investment_recommendation"] == "conditional_pass"
    assert result["risk_scores"]["overall_risk_score"] == 2.2


@pytest.mark.asyncio
async def test_risk_analyst_api_error() -> None:
    """RiskAnalyst writes error to state on API failure."""
    with patch("src.agents.risk_analyst.anthropic.AsyncAnthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create = AsyncMock(side_effect=ValueError("timeout"))

        from src.agents.risk_analyst import run_risk_analyst

        state = {"job_id": "test-004", "deal_metrics": {}, "market_data": {}}
        result = await run_risk_analyst(state)

    assert "error" in result
    assert "risk_analyst" in result["error"]


# --- Supervisor routing ---


def test_supervisor_routes_to_document_analyst() -> None:
    """Supervisor routes to document_analyst when deal_metrics is missing."""
    from src.agents.supervisor import _route

    state: dict[str, Any] = {
        "messages": [],
        "document_text": "...",
        "deal_metrics": None,
        "market_data": None,
        "risk_scores": None,
        "memo_draft": None,
        "current_agent": "supervisor",
        "error": None,
        "job_id": "t",
    }
    assert _route(state) == "document_analyst"


def test_supervisor_routes_to_market_research() -> None:
    """Supervisor routes to market_research once deal_metrics is populated."""
    from src.agents.supervisor import _route

    state: dict[str, Any] = {
        "messages": [],
        "document_text": "...",
        "deal_metrics": {"property_name": "X"},
        "market_data": None,
        "risk_scores": None,
        "memo_draft": None,
        "current_agent": "supervisor",
        "error": None,
        "job_id": "t",
    }
    assert _route(state) == "market_research"


def test_supervisor_halts_on_error() -> None:
    """Supervisor routes to END when error is set."""
    from langgraph.graph import END

    from src.agents.supervisor import _route

    state: dict[str, Any] = {
        "messages": [],
        "document_text": "...",
        "deal_metrics": None,
        "market_data": None,
        "risk_scores": None,
        "memo_draft": None,
        "current_agent": "supervisor",
        "error": "something failed",
        "job_id": "t",
    }
    assert _route(state) == END


def test_supervisor_routes_to_end_when_complete() -> None:
    """Supervisor routes to END when all outputs are populated."""
    from langgraph.graph import END

    from src.agents.supervisor import _route

    state: dict[str, Any] = {
        "messages": [],
        "document_text": "...",
        "deal_metrics": {"x": 1},
        "market_data": {"y": 2},
        "risk_scores": {"z": 3},
        "memo_draft": "{}",
        "current_agent": "memo_writer",
        "error": None,
        "job_id": "t",
    }
    assert _route(state) == END
