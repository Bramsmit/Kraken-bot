"""
Risk-related helpers (stop distance uses shared config constants).

Stop/limit orchestration stays in ``main.run_once``; this module holds small
pure helpers so thresholds stay centralized.
"""

from __future__ import annotations

from rangebot.config.settings import STOP_LOSS_PER_UNIT


def stop_price_below_entry(entry: float) -> float:
    """Reference stop one STOP_LOSS_PER_UNIT below entry (logging / messaging)."""
    return entry - STOP_LOSS_PER_UNIT
