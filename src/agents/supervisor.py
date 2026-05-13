"""
LangGraph multi-agent supervisor: state schema and graph construction.

Architecture decision — the supervisor is a pure Python routing function,
not an LLM call. Routing logic is mechanical: check which state fields are
populated and route to the agent that produces the next missing field.

Why not an LLM supervisor?
- Routing is deterministic given state. LLMs add latency, cost, and
  non-determinism for zero benefit on a mechanical decision.
- Pure functions are trivially unit-testable.
- Routing failures produce clear exceptions, not confusing LLM misroutes.

Pipeline order: document_analyst → market_research → risk_analyst → memo_writer
Each agent writes its output to a dedicated state field; the supervisor reads
that field to decide whether to advance or halt.
"""
from __future__ import annotations

from typing import Annotated, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.agents.document_analyst import run_document_analyst
from src.agents.market_research import run_market_research
from src.agents.memo_writer import run_memo_writer
from src.agents.risk_analyst import run_risk_analyst
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AgentState(TypedDict):
    """Shared mutable state threaded through every node in the graph.

    Fields are intentionally flat (no nested dicts of dicts) to make
    LangGraph's state merging behavior predictable. Each agent writes
    exactly one top-level key; no agent reads another agent's output
    struct directly — they read their own input fields only.
    """

    # Accumulated conversation turns for tracing / debugging
    messages: Annotated[list[BaseMessage], add_messages]

    # Raw document text extracted from the uploaded PDF
    document_text: str

    # Outputs written by each sub-agent (None until that agent runs)
    deal_metrics: Optional[dict]
    market_data: Optional[dict]
    risk_scores: Optional[dict]
    memo_draft: Optional[str]

    # Observability fields updated by the supervisor on each pass
    current_agent: str
    error: Optional[str]

    # Passed through from the API layer for log correlation
    job_id: str


_AGENT_SEQUENCE = [
    ("deal_metrics", "document_analyst"),
    ("market_data", "market_research"),
    ("risk_scores", "risk_analyst"),
    ("memo_draft", "memo_writer"),
]


def _route(state: AgentState) -> str:
    """Return the name of the next node to execute, or END."""
    if state.get("error"):
        logger.warning(
            "Pipeline halting on error",
            job_id=state.get("job_id"),
            error=state["error"],
        )
        return END

    for field, agent_name in _AGENT_SEQUENCE:
        if not state.get(field):
            return agent_name

    return END


def _supervisor(state: AgentState) -> dict:
    """Supervisor node: update current_agent for external status polling."""
    next_node = _route(state)
    return {"current_agent": next_node}


def build_graph() -> StateGraph:
    """Construct and compile the DealFlow LangGraph pipeline.

    Returns a compiled graph ready for ainvoke(). Call once at startup
    and reuse — compilation is not cheap.
    """
    builder = StateGraph(AgentState)

    builder.add_node("supervisor", _supervisor)
    builder.add_node("document_analyst", run_document_analyst)
    builder.add_node("market_research", run_market_research)
    builder.add_node("risk_analyst", run_risk_analyst)
    builder.add_node("memo_writer", run_memo_writer)

    builder.add_edge(START, "supervisor")

    builder.add_conditional_edges(
        "supervisor",
        _route,
        {
            "document_analyst": "document_analyst",
            "market_research": "market_research",
            "risk_analyst": "risk_analyst",
            "memo_writer": "memo_writer",
            END: END,
        },
    )

    # Every agent returns control to the supervisor after completing
    for agent_name in ["document_analyst", "market_research", "risk_analyst", "memo_writer"]:
        builder.add_edge(agent_name, "supervisor")

    return builder.compile()
