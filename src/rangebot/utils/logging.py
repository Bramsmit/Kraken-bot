"""Central logging setup for CLI entrypoints (text or JSON lines to stdout)."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


class _JsonLogFormatter(logging.Formatter):
    """One JSON object per line; suitable for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _parse_log_level(raw: str | None) -> int:
    if not raw:
        return logging.INFO
    if raw.isdigit():
        return int(raw)
    return getattr(logging, raw.upper(), logging.INFO)


def configure_stdout_logging(level: int | None = None) -> None:
    """
    Configure root logger: stdout, no duplicate handlers on repeat calls.

    Environment (optional):

    - ``RANGEBOT_LOG_FORMAT`` — ``text`` (default) or ``json``.
    - ``RANGEBOT_LOG_LEVEL`` — e.g. ``INFO``, ``DEBUG``, or numeric level.
    """
    if level is None:
        level = _parse_log_level(os.environ.get("RANGEBOT_LOG_LEVEL"))

    fmt = os.environ.get("RANGEBOT_LOG_FORMAT", "text").strip().lower()
    if fmt == "json":
        handler: logging.Handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonLogFormatter())
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-8s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)
