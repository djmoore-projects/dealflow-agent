"""
LangSmith tracing configuration.

When LANGCHAIN_API_KEY is present, this module enables LANGCHAIN_TRACING_V2
so every LangGraph node execution and @traceable-decorated agent function
appears in the LangSmith UI with full prompt/response, per-node latency,
and token counts.

When the key is absent, tracing is a no-op — zero overhead, no import errors.
This means the same code runs in local dev (no key) and production (key set
via Secrets Manager) without any conditional branches in agent code.

Usage:
    # Once at startup (FastAPI lifespan):
    tracing = TracingConfig.from_env()
    tracing.enable()

    # In _run_pipeline, to capture the root run URL:
    run_id = uuid.uuid4()
    config = RunnableConfig(run_id=run_id, tags=["dealflow-agent"], metadata={"job_id": job_id})
    state  = await graph.ainvoke(initial_state, config=config)
    url    = tracing.get_run_url(str(run_id))
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TracingConfig:
    """Encapsulates LangSmith connection settings read from environment."""

    api_key: str | None
    project: str
    enabled: bool = field(init=False)

    def __post_init__(self) -> None:
        self.enabled = bool(self.api_key)

    @classmethod
    def from_env(cls) -> TracingConfig:
        """Read config from environment variables."""
        return cls(
            api_key=os.getenv("LANGCHAIN_API_KEY"),
            project=os.getenv("LANGCHAIN_PROJECT", "dealflow-agent"),
        )

    def enable(self) -> None:
        """Set the env vars LangChain/LangGraph look for at import time.

        Must be called before any LangChain/LangGraph code runs. The FastAPI
        lifespan is the right place — it fires before any request handler.
        """
        if not self.enabled:
            logger.info("LangSmith tracing disabled (no LANGCHAIN_API_KEY)")
            return

        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = self.api_key  # type: ignore[assignment]
        os.environ["LANGCHAIN_PROJECT"] = self.project
        logger.info("LangSmith tracing enabled", project=self.project)

    def get_run_url(self, run_id: str | uuid.UUID) -> str | None:
        """Return the LangSmith UI URL for a completed run.

        Fetches the URL via the LangSmith client so we get the exact
        org-scoped URL rather than constructing a guess. Returns None
        if tracing is disabled or the client call fails (e.g. the run
        hasn't propagated yet).

        Args:
            run_id: The UUID passed as RunnableConfig(run_id=...) to ainvoke().

        Returns:
            Full https://smith.langchain.com/... URL, or None.
        """
        if not self.enabled:
            return None

        try:
            from langsmith import Client  # deferred — not installed in every env

            client = Client(api_key=self.api_key)
            run = client.read_run(str(run_id))
            url: str | None = getattr(run, "url", None)
            logger.info("LangSmith run URL retrieved", run_id=str(run_id), url=url)
            return url
        except Exception as exc:
            logger.warning(
                "Could not retrieve LangSmith run URL",
                run_id=str(run_id),
                error=str(exc),
            )
            return None
