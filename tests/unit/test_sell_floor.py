"""Unit tests for sell-floor logic (A1)."""

from __future__ import annotations

import pytest

from rangebot.execution.risk_manager import (
    calculate_aged_sell_floor,
    minimum_profitable_sell_price,
)


def test_limit_sell_uses_floor_when_range_level_too_low() -> None:
    entry = 4.19
    sell_level = 4.07  # dalende markt, onder entry
    fee_floor = minimum_profitable_sell_price(entry, maker_round_trip_pct=0.006)
    limit_sell = max(sell_level, fee_floor)
    assert limit_sell == fee_floor
    assert limit_sell > entry


def test_aged_floor_backward_compatible_without_opened_at() -> None:
    """Zonder opened_at blijft calculate_aged_sell_floor gelijk aan minimum_profitable_sell_price."""
    entry = 4.19
    base_floor = minimum_profitable_sell_price(entry, maker_round_trip_pct=0.006)
    aged_floor, is_aged = calculate_aged_sell_floor(
        entry,
        maker_round_trip_pct=0.006,
        opened_at_iso=None,
    )
    assert not is_aged
    assert aged_floor == base_floor


def test_minimum_profitable_sell_price_covers_fees_and_margin() -> None:
    """Floor moet entry + roundtrip fees + marge dekken."""
    entry = 100.0
    maker_rt = 0.006  # 0.6% roundtrip
    margin = 0.003    # 0.3% extra
    floor = minimum_profitable_sell_price(
        entry,
        maker_round_trip_pct=maker_rt,
        min_margin_pct=margin,
    )
    # 100 × (1 + 0.006 + 0.003) = 100.9
    assert floor == pytest.approx(100.9)
    assert floor > entry
