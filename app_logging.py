"""Shared logging setup for the fund analysis project."""

from __future__ import annotations

import logging
from pathlib import Path


LOGS_DIR = Path("logs")
LOG_FILE = LOGS_DIR / "fund_analysis.log"


def get_logger(name: str = "fund_analysis") -> logging.Logger:
    """Create or reuse a project logger that writes to both console and file."""
    LOGS_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger
