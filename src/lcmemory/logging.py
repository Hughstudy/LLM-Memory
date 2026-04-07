"""Logging configuration."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger for the lcmemory package."""
    logger = logging.getLogger("lcmemory")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger scoped under the lcmemory package."""
    return logging.getLogger(f"lcmemory.{name}")
