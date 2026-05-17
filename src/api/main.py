"""
FastAPI application entry point.

Lifespan context manager handles startup (logging config, tracing config)
and shutdown. Order matters: configure_logging() must run before any
structured log calls; tracing.enable() must run before any LangGraph import
so LangSmith's LANGCHAIN_TRACING_V2 env var is set before chain construction.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes.analyze import router as analyze_router
from src.utils.logging import configure_logging, get_logger
from src.utils.tracing import TracingConfig

_UNAUTHENTICATED_PATHS = {"/health"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key header when API_KEY env var is set.

    When API_KEY is not set (local dev), all requests pass through.
    When set (production), requests without a matching key receive 401.
    Health check is always unauthenticated so load balancers work without keys.
    """

    def __init__(self, app: FastAPI, api_key: str | None) -> None:
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if self._api_key and request.url.path not in _UNAUTHENTICATED_PATHS:
            incoming = request.headers.get("X-API-Key", "")
            if incoming != self._api_key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing X-API-Key header"},
                )
        return await call_next(request)


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

app.add_middleware(ApiKeyMiddleware, api_key=os.getenv("API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict to frontend origin in prod via API_KEY + CORS config
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router, tags=["analysis"])


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe for Docker Compose and ALB health checks."""
    return {"status": "ok", "version": "1.0"}
