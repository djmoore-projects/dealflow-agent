"""
RiskAnalystAgent: cross-references deal terms vs. market data across 5 risk dimensions.

Risk dimensions:
1. Market Risk — cap rate vs. market range, demand drivers, absorption
2. Financial Risk — DSCR, LTV, debt structure, interest rate sensitivity
3. Property Risk — age, condition, capex reserves, deferred maintenance
4. Liquidity Risk — asset class depth, typical hold period, exit optionality
5. Execution Risk — business plan complexity, sponsorship track record

Each dimension scored 1-5 (1=low risk, 5=high risk) with written rationale
and supporting evidence citations. This structured output is what the
MemoWriter uses to populate the Risk Assessment section of the memo.
"""
from __future__ import annotations

import os
from typing import Any

import anthropic

from src.utils.logging import get_logger

logger = get_logger(__name__)

_TOOL: dict[str, Any] = {
    "name": "score_risk",
    "description": (
        "Score the deal across 5 risk dimensions using deal metrics and market data. "
        "Score 1 = low risk, 5 = high risk."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "market_risk": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 1, "maximum": 5},
                    "rationale": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["score", "rationale", "evidence"],
            },
            "financial_risk": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 1, "maximum": 5},
                    "rationale": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["score", "rationale", "evidence"],
            },
            "property_risk": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 1, "maximum": 5},
                    "rationale": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["score", "rationale", "evidence"],
            },
            "liquidity_risk": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 1, "maximum": 5},
                    "rationale": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["score", "rationale", "evidence"],
            },
            "execution_risk": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 1, "maximum": 5},
                    "rationale": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["score", "rationale", "evidence"],
            },
            "overall_risk_score": {
                "type": "number",
                "description": "Weighted average of all five dimension scores",
            },
            "investment_recommendation": {
                "type": "string",
                "enum": ["strong_pass", "pass", "conditional_pass", "decline", "strong_decline"],
            },
            "key_risks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Top 3 risks that could most impact investment outcomes",
            },
        },
        "required": [
            "market_risk", "financial_risk", "property_risk",
            "liquidity_risk", "execution_risk", "overall_risk_score",
            "investment_recommendation", "key_risks",
        ],
    },
}

_SYSTEM_PROMPT = (
    "You are a senior real estate risk analyst. Evaluate the deal against market benchmarks "
    "and score risk across five dimensions. Be specific: cite exact numbers from deal_metrics "
    "and market_data. A DSCR of 1.28 is different from 1.05 — the score must reflect the data. "
    "Conservative underwriting is expected; flag all scenarios where assumptions appear optimistic."
)


async def run_risk_analyst(state: dict) -> dict:
    """Score deal risk using deal_metrics and market_data.

    Args:
        state: AgentState with deal_metrics and market_data populated.

    Returns:
        {"risk_scores": {...}} or {"error": "risk_analyst: ..."}.
    """
    job_id = state.get("job_id", "unknown")
    logger.info("RiskAnalyst starting", job_id=job_id)

    import json

    deal = state.get("deal_metrics", {})
    market = state.get("market_data", {})

    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=3000,
            system=_SYSTEM_PROMPT,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "score_risk"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Deal metrics:\n{json.dumps(deal, indent=2)}\n\n"
                        f"Market data:\n{json.dumps(market, indent=2)}\n\n"
                        "Score this deal's risk across all five dimensions."
                    ),
                }
            ],
        )

        tool_block = next(b for b in response.content if b.type == "tool_use")
        risk_scores: dict = tool_block.input

        logger.info(
            "RiskAnalyst complete",
            job_id=job_id,
            overall_score=risk_scores.get("overall_risk_score"),
            recommendation=risk_scores.get("investment_recommendation"),
        )
        return {"risk_scores": risk_scores}

    except Exception as exc:
        logger.error("RiskAnalyst failed", job_id=job_id, error=str(exc))
        return {"error": f"risk_analyst: {exc}"}
