"""Unit tests for risk_manager (pure helpers)."""

from __future__ import annotations

import pytest

from rangebot.config.settings import STOP_LOSS_PER_UNIT
from rangebot.execution.risk_manager import (
    minimum_profitable_sell_price,
    stop_price_below_entry,
)


def test_stop_price_below_entry() -> None:
    assert stop_price_below_entry(100.0) == pytest.approx(100.0 - STOP_LOSS_PER_UNIT)


def test_minimum_profitable_sell_price_above_entry() -> None:
    floor = minimum_profitable_sell_price(4.19, maker_round_trip_pct=0.006)
    assert floor > 4.19
    assert floor == pytest.approx(4.19 * (1 + 0.006 + 0.003))


def test_minimum_profitable_sell_price_zero_entry() -> None:
    assert minimum_profitable_sell_price(0.0, maker_round_trip_pct=0.006) == 0.0
