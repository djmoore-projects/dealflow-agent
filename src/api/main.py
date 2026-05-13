"""
FastAPI application entry point.

Lifespan context manager handles startup (logging config, tracing config)
and shutdown. Order matters: configure_logging() must run before any
structured log calls; tracing.enable() must run before any LangGraph import
so LangSmith's LANGCHAIN_TRACING_V2 env var is set before chain construction.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.analyze import router as analyze_router
from src.utils.logging import configure_logging, get_logger
from src.utils.tracing import TracingConfig


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run startup tasks before accepting requests, teardown on shutdown."""
    configure_logging()
    logger = get_logger(__name__)

    tracing = TracingConfig.from_env()
    tracing.enable()

    # Store on app state so routes can access it without re-reading env
    app.state.tracing = tracing

    logger.info("DealFlow Agent starting up", tracing_enabled=tracing.enabled)
    yield
    logger.info("DealFlow Agent shutting down")


app = FastAPI(
    title="DealFlow Agent API",
    description="Multi-agent investment deal analysis. Upload a deal PDF, get a structured memo.",
    version="1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Phase 2: restrict to frontend origin in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router, tags=["analysis"])


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe for Docker Compose and ALB health checks."""
    return {"status": "ok", "version": "1.0"}
