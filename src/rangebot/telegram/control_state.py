"""Pause/resume trading from Telegram (local JSON, not committed by default)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rangebot.utils.paths import repository_root

log = logging.getLogger(__name__)


def control_state_path() -> Path:
    return repository_root() / ".kraken_bot_control.json"


def is_trading_paused() -> bool:
    path = control_state_path()
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
        return bool(data.get("paused"))
    except Exception as e:
        log.warning("Kon control state niet lezen: %s", e)
        return False


def set_trading_paused(paused: bool) -> None:
    path = control_state_path()
    payload: dict[str, Any] = {
        "paused": paused,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        path.write_text(json.dumps(payload, indent=2))
    except Exception as e:
        log.warning("Kon control state niet schrijven: %s", e)
        raise
