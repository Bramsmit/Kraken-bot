"""Unit tests for sell-floor logic (A1)."""

from __future__ import annotations

from rangebot.execution.risk_manager import minimum_profitable_sell_price


def test_limit_sell_uses_floor_when_range_level_too_low() -> None:
    entry = 4.19
    sell_level = 4.07  # dalende markt, onder entry
    fee_floor = minimum_profitable_sell_price(entry, maker_round_trip_pct=0.006)
    limit_sell = max(sell_level, fee_floor)
    assert limit_sell == fee_floor
    assert limit_sell > entry
