"""Structured, secret-safe logging setup. No import side effects.

``configure_logging`` is idempotent and is called from the FastAPI lifespan, the
arq worker, and CLI entrypoints. We never log the ``Settings`` object or raw
tokens/payloads; secrets are ``SecretStr`` and mask themselves.
"""

from __future__ import annotations

import json
import logging
import sys
from logging.config import dictConfig

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter (no external dependency)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    """Configure root logging once. Safe to call repeatedly."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    formatter = "json" if json_logs else "console"
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "console": {"format": "%(asctime)s %(levelname)-8s %(name)s | %(message)s"},
                "json": {"()": f"{__name__}.JsonFormatter"},
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter,
                    "stream": sys.stdout,
                },
            },
            "root": {"level": level.upper(), "handlers": ["default"]},
            "loggers": {
                # Tame noisy third-party loggers.
                "uvicorn.access": {"level": "WARNING"},
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
                "aiogram.event": {"level": "WARNING"},
            },
        }
    )
    _CONFIGURED = True
