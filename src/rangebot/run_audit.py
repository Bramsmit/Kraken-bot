"""
Append-only JSONL run audit (one record per scheduled run).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rangebot.utils.paths import repository_root

log = logging.getLogger(__name__)

KRAKEN_RUNS_JSONL = "kraken_runs.jsonl"


def _audit_path(filename: str) -> Path:
    return repository_root() / filename


def log_run_audit(record: dict[str, Any], *, filename: str) -> None:
    """Write one JSON line (UTF-8). On error, log a warning only."""
    row = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), **record}
    path = _audit_path(filename)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except OSError as e:
        log.warning("Kon run-audit niet schrijven naar %s: %s", filename, e)


def load_run_audits(filename: str) -> list[dict[str, Any]]:
    """Load JSONL audit lines from repo root."""
    path = _audit_path(filename)
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out
