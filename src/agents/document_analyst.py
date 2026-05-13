"""
DocumentAnalystAgent: extracts structured deal metrics from raw PDF text.

Uses tool_choice={"type": "tool", "name": "extract_deal_metrics"} to force
Claude to produce a valid tool call. This gives us:
- A compile-time contract: if the tool call is missing, we get an exception,
  not silently malformed data.
- Typed outputs: Anthropic validates the JSON against the input_schema before
  returning it to us.
- A clear failure mode: exceptions are caught and written to state.error,
  halting the pipeline with a debuggable message.
"""

from __future__ import annotations

import os
from typing import Any

import anthropic
from langsmith import traceable

from src.utils.logging import get_logger

logger = get_logger(__name__)

_TOOL: dict[str, Any] = {
    "name": "extract_deal_metrics",
    "description": (
        "Extract all available structured deal metrics from the document. "
        "Set any field to null if it is not explicitly stated — do not estimate "
        "or back-calculate values that aren't present."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "property_name": {
                "type": "string",
                "description": "Name or address of the property",
            },
            "property_type": {
                "type": "string",
                "enum": [
                    "multifamily",
                    "office",
                    "retail",
                    "industrial",
                    "mixed-use",
                    "hotel",
                    "other",
                ],
            },
            "market": {"type": "string", "description": "City or MSA"},
            "submarket": {"type": ["string", "null"]},
            "purchase_price": {"type": "number", "description": "USD"},
            "noi": {
                "type": ["number", "null"],
                "description": "Annual Net Operating Income, USD",
            },
            "cap_rate": {
                "type": ["number", "null"],
                "description": "As decimal, e.g. 0.055 for 5.5%",
            },
            "debt_service_coverage_ratio": {"type": ["number", "null"]},
            "loan_to_value": {
                "type": ["number", "null"],
                "description": "As decimal, e.g. 0.70",
            },
            "vacancy_rate": {"type": ["number", "null"], "description": "As decimal"},
            "gross_rent_multiplier": {"type": ["number", "null"]},
            "year_built": {"type": ["integer", "null"]},
            "square_footage": {"type": ["number", "null"]},
            "units": {
                "type": ["integer", "null"],
                "description": "Unit count (multifamily only)",
            },
            "red_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Any concerns, inconsistencies, or missing critical information found",
            },
        },
        "required": [
            "property_name",
            "property_type",
            "market",
            "purchase_price",
            "red_flags",
        ],
    },
}

_SYSTEM_PROMPT = (
    "You are a senior commercial real estate analyst specializing in deal underwriting. "
    "Extract structured metrics from investment memos, offering memoranda, and loan documents. "
    "Be precise: use exact numbers from the document. Never estimate values not stated. "
    "Flag any internal inconsistencies or missing critical information as red_flags."
)


@traceable(
    name="DocumentAnalystAgent",
    run_type="chain",
    tags=["dealflow-agent", "document-analyst"],
    metadata={"version": "1.0"},
)
async def run_document_analyst(state: dict) -> dict:
    """Extract deal metrics from state.document_text using Claude tool use.

    Args:
        state: Current AgentState dict.

    Returns:
        Partial state update: {"deal_metrics": {...}} on success,
        or {"error": "document_analyst: ..."} on failure.
    """
    job_id = state.get("job_id", "unknown")
    logger.info("DocumentAnalyst starting", job_id=job_id)

    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "extract_deal_metrics"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract all deal metrics from this document:\n\n"
                        + state["document_text"][:12000]
                    ),
                }
            ],
        )

        tool_block = next(b for b in response.content if b.type == "tool_use")
        deal_metrics: dict = tool_block.input
        tokens = response.usage.input_tokens + response.usage.output_tokens

        logger.info(
            "DocumentAnalyst complete",
            job_id=job_id,
            property=deal_metrics.get("property_name"),
            red_flags=len(deal_metrics.get("red_flags", [])),
            tokens=tokens,
        )
        return {"deal_metrics": deal_metrics, "total_tokens_used": tokens}

    except Exception as exc:
        logger.error("DocumentAnalyst failed", job_id=job_id, error=str(exc))
        return {"error": f"document_analyst: {exc}"}
