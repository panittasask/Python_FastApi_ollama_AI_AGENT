"""Loguru-based logging configuration."""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.core.config import get_settings

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        backtrace=True,
        diagnose=False,
        enqueue=False,
    )
    Path("logs").mkdir(exist_ok=True)
    logger.add(
        "logs/agent_api_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="14 days",
        level=settings.log_level,
        encoding="utf-8",
    )
    _configured = True


__all__ = ["logger", "setup_logging"]
