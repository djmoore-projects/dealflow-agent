"""
Structured JSON logging via structlog with stdlib integration.

Uses structlog.stdlib.LoggerFactory() so the underlying logger is always a
stdlib logging.Logger — giving us .name for add_logger_name, correct level
filtering, and passthrough from third-party libs (uvicorn, langchain).

Every agent, API handler, and background task calls get_logger(__name__).
Output is JSON in production (LOG_FORMAT=json) and pretty-printed locally.
"""
import logging
import os
import sys
from typing import Any

import structlog


def configure_logging() -> None:
    """Configure structlog + stdlib logging. Call once at application startup."""
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    log_format = os.getenv("LOG_FORMAT", "json")

    # Processors shared between JSON and console renderers
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        renderer: Any = structlog.processors.JSONRenderer()
        stream = sys.stdout
    else:
        renderer = structlog.dev.ConsoleRenderer()
        stream = sys.stderr

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # foreign_pre_chain handles log records from stdlib loggers (uvicorn, etc.)
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Avoid adding duplicate handlers on repeated configure_logging() calls
    if not any(isinstance(h, logging.StreamHandler) and h.formatter is formatter
               for h in root_logger.handlers):
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
    root_logger.setLevel(log_level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog BoundLogger bound to the given module name."""
    return structlog.get_logger(name)
