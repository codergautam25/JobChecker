"""Structured logging configuration.

Configures structlog for consistent, machine-readable logging across
the application. Supports both human-readable (dev) and JSON (prod)
output formats.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog

from career_tracker.config import get_settings


def setup_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Configure structlog and stdlib logging.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        json_output: If True, output JSON lines. If False, human-readable.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure stdlib logging (captures third-party library logs)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=log_level,
    )

    # Structlog processors
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Also configure a file handler for audit logs
    pass
