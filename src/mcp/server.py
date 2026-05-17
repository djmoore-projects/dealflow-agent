"""
MCP server exposing the RAG pipeline as a tool callable by Claude Desktop.

Run as a standalone process:
    python -m src.mcp.server

Claude Desktop configuration (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "dealflow-rag": {
          "command": "python",
          "args": ["-m", "src.mcp.server"],
          "cwd": "/path/to/dealflow-agent",
          "env": {
            "DATABASE_URL": "postgresql+psycopg://dealflow:dealflow@localhost:5432/dealflow",
            "OPENAI_API_KEY": "sk-..."
          }
        }
      }
    }

Design note: the server is stateless — it does not hold a pgvector connection
between calls. Each tool invocation constructs a fresh connection, which is
correct for an MCP server that may sit idle for minutes between calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

# When run as __main__, the project root must be on sys.path so that
# `from src.rag...` resolves correctly without installing the package.
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.server.fastmcp import FastMCP
from src.rag.retrieval import RetrievedChunk, retrieve_chunks
from src.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

mcp = FastMCP(
    "dealflow-rag",
    instructions=(
        "Query the DealFlow Agent RAG knowledge base. "
        "Use this tool to retrieve relevant passages from uploaded deal documents "
        "when answering questions about deal terms, financial metrics, or market context."
    ),
)


@mcp.tool()
async def query_deal_knowledge_base(query: str, k: int = 5) -> list[dict]:
    """Retrieve passages from the deal document knowledge base.

    Args:
        query: Natural language question about deal terms, financial metrics,
               market conditions, or risk factors.
        k: Number of passages to return (1-20). Default is 5.

    Returns:
        List of passage dicts with keys: content, page_number, source, score.
        Results are ordered by descending relevance score.
    """
    k = max(1, min(k, 20))  # clamp to safe range
    logger.info("MCP tool called", query=query[:80], k=k)

    try:
        chunks: list[RetrievedChunk] = retrieve_chunks(query=query, k=k)
        return [c.model_dump(exclude={"job_id"}) for c in chunks]
    except Exception as exc:
        logger.error("RAG retrieval failed in MCP tool", error=str(exc))
        # Return error as a structured response rather than raising —
        # MCP clients handle tool errors better than unhandled exceptions.
        return [
            {
                "error": str(exc),
                "content": "",
                "page_number": None,
                "source": None,
                "score": 0.0,
            }
        ]


if __name__ == "__main__":
    mcp.run()
