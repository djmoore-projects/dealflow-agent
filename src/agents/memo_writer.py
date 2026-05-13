"""
MemoWriterAgent: synthesizes all prior agent outputs into a structured investment memo.

The memo schema mirrors what institutional investment committees expect:
executive summary, property overview, financial summary, market context,
risk assessment, and recommendation. Each section includes citations back
to the source data so reviewers can audit the AI's reasoning.

This agent does NOT use tool_choice to force a specific schema — it uses
a schema-guided free-text response (tool_choice="auto") because the memo
sections require prose, not just structured data. We validate the output
by requiring a specific tool call, but allow Claude discretion in forming
each section's text.
"""
from __future__ import annotations

import json
import os
from typing import Any

import anthropic

from src.utils.logging import get_logger

logger = get_logger(__name__)

_TOOL: dict[str, Any] = {
    "name": "write_investment_memo",
    "description": "Write the final structured investment memo.",
    "input_schema": {
        "type": "object",
        "properties": {
            "executive_summary": {
                "type": "string",
                "description": "3-4 sentence summary: property, price, recommendation, key risk",
            },
            "property_overview": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "market": {"type": "string"},
                    "purchase_price_usd": {"type": "number"},
                    "description": {"type": "string"},
                },
                "required": ["name", "type", "market", "purchase_price_usd", "description"],
            },
            "financial_summary": {
                "type": "object",
                "properties": {
                    "noi_usd": {"type": ["number", "null"]},
                    "cap_rate_pct": {"type": ["number", "null"]},
                    "dscr": {"type": ["number", "null"]},
                    "ltv_pct": {"type": ["number", "null"]},
                    "vacancy_pct": {"type": ["number", "null"]},
                    "analysis": {"type": "string"},
                },
                "required": ["analysis"],
            },
            "market_context": {
                "type": "string",
                "description": "Market conditions narrative with citations to data sources",
            },
            "risk_assessment": {
                "type": "object",
                "properties": {
                    "overall_score": {"type": "number"},
                    "recommendation": {"type": "string"},
                    "dimension_summary": {"type": "string"},
                    "key_risks": {"type": "array", "items": {"type": "string"}},
                    "mitigants": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["overall_score", "recommendation", "dimension_summary", "key_risks"],
            },
            "recommendation": {
                "type": "string",
                "description": "Final underwriter recommendation with conditions if applicable",
            },
            "data_citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "source": {"type": "string"},
                    },
                },
                "description": "Key factual claims mapped to their source (document, market data, etc.)",
            },
        },
        "required": [
            "executive_summary", "property_overview", "financial_summary",
            "market_context", "risk_assessment", "recommendation", "data_citations",
        ],
    },
}

_SYSTEM_PROMPT = (
    "You are a senior investment analyst writing a formal investment committee memo. "
    "Synthesize the deal metrics, market research, and risk scores into a clear, concise memo. "
    "Every claim must be traceable to either the deal document or market research data. "
    "Use precise numbers. Flag any assumption that is not directly supported by data. "
    "The memo will be reviewed by an investment committee — write for that audience."
)


async def run_memo_writer(state: dict) -> dict:
    """Synthesize all agent outputs into a structured investment memo.

    Args:
        state: AgentState with deal_metrics, market_data, and risk_scores populated.

    Returns:
        {"memo_draft": "<serialized JSON memo>"} or {"error": "memo_writer: ..."}.
    """
    job_id = state.get("job_id", "unknown")
    logger.info("MemoWriter starting", job_id=job_id)

    deal = state.get("deal_metrics", {})
    market = state.get("market_data", {})
    risks = state.get("risk_scores", {})

    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "write_investment_memo"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Deal metrics:\n{json.dumps(deal, indent=2)}\n\n"
                        f"Market data:\n{json.dumps(market, indent=2)}\n\n"
                        f"Risk scores:\n{json.dumps(risks, indent=2)}\n\n"
                        "Write the investment committee memo."
                    ),
                }
            ],
        )

        tool_block = next(b for b in response.content if b.type == "tool_use")
        memo: dict = tool_block.input

        logger.info(
            "MemoWriter complete",
            job_id=job_id,
            recommendation=memo.get("risk_assessment", {}).get("recommendation"),
            citations=len(memo.get("data_citations", [])),
        )
        return {"memo_draft": json.dumps(memo, indent=2)}

    except Exception as exc:
        logger.error("MemoWriter failed", job_id=job_id, error=str(exc))
        return {"error": f"memo_writer: {exc}"}
