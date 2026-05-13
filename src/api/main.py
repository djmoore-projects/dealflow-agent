"""
FastAPI application entry point.

Lifespan context manager handles startup (logging config, DB init) and
shutdown (graceful cleanup). Health endpoint is intentionally minimal —
it's what the Docker Compose and ALB health checks call.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.analyze import router as analyze_router
from src.utils.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run startup tasks before accepting requests, teardown on shutdown."""
    configure_logging()
    logger = get_logger(__name__)
    logger.info("DealFlow Agent starting up")
    yield
    logger.info("DealFlow Agent shutting down")


app = FastAPI(
    title="DealFlow Agent API",
    description="Multi-agent investment deal analysis. Upload a deal PDF, get a structured memo.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Phase 2: restrict to frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router, tags=["analysis"])


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe for Docker Compose and ALB health checks."""
    return {"status": "ok", "service": "dealflow-agent"}
