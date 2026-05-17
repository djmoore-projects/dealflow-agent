"""
MarketResearchAgent: pulls comparable market data for the subject property.

Uses Tavily web search (via Claude tool use) to retrieve live market comps:
cap rates, vacancy, rent trends, and comparable sales. Falls back to
stub data when TAVILY_API_KEY is not set (useful for offline testing).

The agent passes deal_metrics as context so Claude can form targeted search
queries (e.g., "Austin TX multifamily cap rates Q1 2025").
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import anthropic
from langsmith import traceable

from src.utils.logging import get_logger

logger = get_logger(__name__)

_WEB_SEARCH_TOOL: dict[str, Any] = {
    "name": "web_search",
    "description": "Search the web for current commercial real estate market data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
        },
        "required": ["query"],
    },
}

_RECORD_MARKET_DATA_TOOL: dict[str, Any] = {
    "name": "record_market_data",
    "description": "Record the structured market research findings.",
    "input_schema": {
        "type": "object",
        "properties": {
            "market_cap_rate_range": {
                "type": "object",
                "properties": {
                    "low": {"type": "number"},
                    "high": {"type": "number"},
                },
                "description": "Market cap rate range as decimals",
            },
            "market_vacancy_rate": {
                "type": ["number", "null"],
                "description": "Market vacancy as decimal",
            },
            "avg_rent_psf": {
                "type": ["number", "null"],
                "description": "Average rent per sq ft per year",
            },
            "rent_growth_yoy": {
                "type": ["number", "null"],
                "description": "YoY rent growth as decimal",
            },
            "comparable_sales": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "address": {"type": "string"},
                        "sale_price": {"type": "number"},
                        "cap_rate": {"type": ["number", "null"]},
                        "price_per_unit": {"type": ["number", "null"]},
                        "date": {"type": "string"},
                    },
                },
            },
            "market_summary": {
                "type": "string",
                "description": "2-3 sentence narrative on market conditions",
            },
            "data_sources": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["market_cap_rate_range", "market_summary", "data_sources"],
    },
}

_SYSTEM_PROMPT = (
    "You are a commercial real estate market analyst. Research current market conditions "
    "for the subject property's market and asset type. Focus on: cap rate ranges for comparable "
    "assets, vacancy rates, rent trends, and recent comparable sales. Use the web_search tool "
    "to find current data, then call record_market_data with your findings."
)


def _tavily_search(query: str) -> str:
    """Execute a Tavily web search. Returns a JSON string of results."""
    try:
        from tavily import TavilyClient  # type: ignore[import]

        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))
        results = client.search(query=query, max_results=5, search_depth="basic")
        return json.dumps(
            [
                {"url": r["url"], "content": r["content"][:500]}
                for r in results.get("results", [])
            ],
            indent=2,
        )
    except Exception as exc:
        logger.warning("Tavily search failed, returning stub", error=str(exc))
        return json.dumps(
            [{"url": "stub", "content": f"Market data unavailable: {exc}"}]
        )


@traceable(
    name="MarketResearchAgent",
    run_type="chain",
    tags=["dealflow-agent", "market-research"],
    metadata={"version": "1.0"},
)
async def run_market_research(state: dict) -> dict:
    """Research market conditions for the subject deal.

    Args:
        state: Current AgentState dict (must have deal_metrics populated).

    Returns:
        Partial state update: {"market_data": {...}} or {"error": "..."}.
    """
    job_id = state.get("job_id", "unknown")
    logger.info("MarketResearch starting", job_id=job_id)

    deal = state.get("deal_metrics", {})
    market = deal.get("market", "unknown market")
    prop_type = deal.get("property_type", "commercial")

    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                f"Research current market conditions for a {prop_type} property in {market}. "
                f"Deal cap rate: {deal.get('cap_rate', 'unknown')}. "
                "Search for: cap rate ranges, vacancy rates, rent trends, and comparable sales. "
                "Then call record_market_data with your findings."
            ),
        }
    ]

    try:
        total_tokens = 0
        # Agentic loop: Claude may call web_search multiple times before record_market_data
        for _ in range(6):  # max rounds prevents infinite loops
            response = await client.messages.create(
                model=model,
                max_tokens=3000,
                system=_SYSTEM_PROMPT,
                tools=[_WEB_SEARCH_TOOL, _RECORD_MARKET_DATA_TOOL],
                messages=messages,
            )
            total_tokens += response.usage.input_tokens + response.usage.output_tokens

            # Check if Claude called record_market_data (we're done)
            record_block = next(
                (
                    b
                    for b in response.content
                    if b.type == "tool_use" and b.name == "record_market_data"
                ),
                None,
            )
            if record_block:
                logger.info(
                    "MarketResearch complete",
                    job_id=job_id,
                    market=market,
                    tokens=total_tokens,
                )
                return {
                    "market_data": record_block.input,
                    "total_tokens_used": total_tokens,
                }

            # Process any web_search calls and continue the loop
            tool_results = []
            for block in response.content:
                if block.type == "tool_use" and block.name == "web_search":
                    search_result = await asyncio.to_thread(
                        _tavily_search, block.input["query"]
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": search_result,
                        }
                    )

            if not tool_results:
                # Model stopped without calling any tool — extract text as fallback
                break

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        raise RuntimeError(
            "MarketResearch agent did not call record_market_data within round limit"
        )

    except Exception as exc:
        logger.error("MarketResearch failed", job_id=job_id, error=str(exc))
        return {"error": f"market_research: {exc}"}
