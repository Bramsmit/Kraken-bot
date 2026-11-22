"""Beschermende uitstap.

Nieuwe posities (met ``opened_at``): verkopen bij 15% verlies of na 14 dagen.
Posities van vóór deze regel, zonder openingsdatum: alleen bij 60% verlies
vanaf de instap. Dat ligt onder de koersen van 22 nov 2026, dus de vier
lopende posities worden daar niet door verkocht.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

NEW_POSITION_LOSS_PCT = 0.15
NEW_POSITION_MAX_AGE_DAYS = 14
LEGACY_MAX_LOSS_PCT = 0.60


def protective_exit_reason(
    entry: float,
    price: float,
    opened_at: str | None,
    now: datetime,
) -> str | None:
    if entry <= 0 or price <= 0:
        return None
    if not opened_at:
        if price <= entry * (1 - LEGACY_MAX_LOSS_PCT):
            return "noodgrens"
        return None
    try:
        opened = datetime.fromisoformat(opened_at)
    except ValueError:
        return None
    if opened.tzinfo is None:
        opened = opened.replace(tzinfo=timezone.utc)
    if price <= entry * (1 - NEW_POSITION_LOSS_PCT):
        return "verlies"
    if now - opened >= timedelta(days=NEW_POSITION_MAX_AGE_DAYS):
        return "leeftijd"
    return None
