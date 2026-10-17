"""JSON 行日志（v1 简化版可观测性的核心）。

任何模块用 `from app.core.logging import get_logger` 然后 `logger.info(...)`，
输出形如 `{"ts": "...", "level": "INFO", "logger": "app.x", "msg": "..."}`。
"""
from __future__ import annotations

import logging
import sys

from pythonjsonlogger import json as jsonlogger

from app.core.config import get_settings


def configure_logging() -> None:
    """Process-wide logging setup. Call once at startup."""
    settings = get_settings()
    root = logging.getLogger()
    # idempotent: 避免 reload 时重复加 handler
    if getattr(root, "_vnb_configured", False):
        return

    root.setLevel(settings.log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    fmt = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
        timestamp=True,
    )
    handler.setFormatter(fmt)
    root.handlers = [handler]
    root._vnb_configured = True  # type: ignore[attr-defined]


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or "app")
