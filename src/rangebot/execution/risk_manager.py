"""
Risk-related helpers (stop distance uses shared config constants).

Stop/limit orchestration stays in ``main.run_once``; this module holds small
pure helpers so thresholds stay centralized.
"""

from __future__ import annotations

from datetime import datetime, timezone

from rangebot.config.settings import (
    MAX_POSITION_HOLDING_HOURS,
    POSITION_HARD_STOP_LOSS_ENABLED,
    POSITION_HARD_STOP_LOSS_PCT,
    SELL_FLOOR_DECAY_HOURS,
    SELL_FLOOR_DECAY_MODE,
    SELL_FLOOR_MIN_MULTIPLIER,
    STOP_LOSS_PER_UNIT,
)


def stop_price_below_entry(entry: float) -> float:
    """Reference stop one STOP_LOSS_PER_UNIT below entry (logging / messaging)."""
    return entry - STOP_LOSS_PER_UNIT


def minimum_profitable_sell_price(
    entry: float,
    *,
    maker_round_trip_pct: float,
    min_margin_pct: float = 0.003,
) -> float:
    """Minimale verkoopprijs: entry + roundtrip maker-fees + kleine marge."""
    if entry <= 0:
        return 0.0
    return entry * (1 + maker_round_trip_pct + min_margin_pct)


def _parse_opened_at_hours_ago(opened_at_iso: str | None) -> float | None:
    """Parse ISO timestamp naar uren geleden (None bij ontbrekende/ongeldige input)."""
    if not opened_at_iso:
        return None
    try:
        opened_dt = datetime.fromisoformat(opened_at_iso.replace("Z", "+00:00"))
        if opened_dt.tzinfo is None:
            opened_dt = opened_dt.replace(tzinfo=timezone.utc)
        age_sec = (datetime.now(timezone.utc) - opened_dt).total_seconds()
        return age_sec / 3600
    except (ValueError, AttributeError):
        return None


def calculate_aged_sell_floor(
    entry: float,
    *,
    maker_round_trip_pct: float,
    min_margin_pct: float = 0.003,
    opened_at_iso: str | None = None,
    max_holding_hours: int | None = None,
    decay_mode: str | None = None,
    decay_hours: int | None = None,
    min_multiplier: float | None = None,
) -> tuple[float, bool]:
    """
    Bereken sell-floor met optionele versoepeling op basis van houdtijd.

    Returns (floor_price, is_aged) waarbij is_aged=True als de floor verlaagd is.

    Mechanisme:
    - Zonder max_holding_hours of decay_mode="disabled":
      retourneert de standaard break-even floor (entry × (1 + fees + marge)).
    - Na max_holding_hours:
      - "step": directe verlaging naar entry × min_multiplier
      - "linear": geleidelijke daling over decay_hours
    - min_multiplier bepaalt de laagste multiplier (bijv. 0.998 = -0.2% verlies).
    
    Parameters worden gelezen uit settings wanneer None; kan overschreven worden voor tests.
    """
    # Lees uit settings wanneer niet expliciet gegeven (productie gebruik)
    if max_holding_hours is None:
        max_holding_hours = MAX_POSITION_HOLDING_HOURS
    if decay_mode is None:
        decay_mode = SELL_FLOOR_DECAY_MODE
    if decay_hours is None:
        decay_hours = SELL_FLOOR_DECAY_HOURS
    if min_multiplier is None:
        min_multiplier = SELL_FLOOR_MIN_MULTIPLIER
    
    base_floor = minimum_profitable_sell_price(
        entry, maker_round_trip_pct=maker_round_trip_pct, min_margin_pct=min_margin_pct
    )
    if (
        max_holding_hours is None
        or max_holding_hours <= 0
        or decay_mode == "disabled"
    ):
        return base_floor, False

    hours_ago = _parse_opened_at_hours_ago(opened_at_iso)
    if hours_ago is None or hours_ago <= max_holding_hours:
        return base_floor, False

    base_mult = 1 + maker_round_trip_pct + min_margin_pct
    min_mult = max(0.0, float(min_multiplier))

    if decay_mode == "step":
        return entry * min_mult, True

    if decay_mode == "linear":
        excess_hours = hours_ago - max_holding_hours
        decay_period = max(1, decay_hours)
        progress = min(1.0, excess_hours / decay_period)
        effective_mult = base_mult + progress * (min_mult - base_mult)
        return entry * effective_mult, True

    return base_floor, False


def should_force_exit_position(
    current_price: float | None,
    entry: float,
    *,
    enabled: bool | None = None,
    stop_loss_pct: float | None = None,
) -> bool:
    """
    Bepaal of positie geforceerd moet worden gesloten (hard stop-loss).

    True als enabled en de prijs onder entry × (1 + stop_loss_pct).
    
    Parameters worden gelezen uit settings wanneer None; kan overschreven worden voor tests.
    """
    if enabled is None:
        enabled = POSITION_HARD_STOP_LOSS_ENABLED
    if stop_loss_pct is None:
        stop_loss_pct = POSITION_HARD_STOP_LOSS_PCT
        
    if not enabled:
        return False
    if not current_price or current_price <= 0 or entry <= 0:
        return False
    threshold = entry * (1 + stop_loss_pct)
    return current_price < threshold
