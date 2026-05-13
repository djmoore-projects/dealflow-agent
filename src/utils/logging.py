"""
Structured JSON logging via structlog.

Every agent, API handler, and background task uses get_logger(__name__) rather
than print() or bare logging calls. This ensures all log lines are parseable by
CloudWatch Logs Insights, Datadog, or any JSON-aware log aggregator.
"""
import logging
import os
import sys
from typing import Any

import structlog


def configure_logging() -> None:
    """Configure structlog with JSON or pretty output based on LOG_FORMAT env var.

    Call once at application startup (in FastAPI lifespan or __main__).
    """
    log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    log_format = os.getenv("LOG_FORMAT", "json")

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
        stream_handler = logging.StreamHandler(sys.stdout)
    else:
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(),
        ]
        stream_handler = logging.StreamHandler(sys.stderr)

    structlog.configure(
        processors=processors,  # type: ignore[arg-type]
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(stream_handler.stream),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so third-party libs (uvicorn, langchain) emit JSON
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to the given module name."""
    return structlog.get_logger(name)
