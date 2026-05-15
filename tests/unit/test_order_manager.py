"""Unit tests for order_manager helpers (no live exchange)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from rangebot.execution.order_manager import (
    cancel_order_safe,
    order_age_hours,
    round_limit_price,
    submit_limit_buy,
    submit_limit_sell_all_free,
)


def test_round_limit_price_uses_micro_threshold() -> None:
    assert round_limit_price(0.00005) == round(0.00005, 8)


def test_round_limit_price_between_micro_and_one() -> None:
    assert round_limit_price(0.5) == round(0.5, 6)


def test_round_limit_price_one_or_above() -> None:
    assert round_limit_price(123.456789) == round(123.456789, 4)


def test_order_age_hours_missing_timestamp() -> None:
    assert order_age_hours({}) == 0.0


def test_order_age_hours_from_millis() -> None:
    ts_ms = int(
        (datetime.now(timezone.utc) - timedelta(hours=2, minutes=30)).timestamp() * 1000
    )
    assert order_age_hours({"timestamp": ts_ms}) == pytest.approx(2.5, abs=0.02)


def test_cancel_order_safe_delegates() -> None:
    c = MagicMock()
    cancel_order_safe(c, "oid", "ETH/USD")
    c.cancel_order.assert_called_once_with("oid", "ETH/USD")


def test_submit_limit_buy_delegates() -> None:
    c = MagicMock()
    c.place_order.return_value = {"id": "x"}
    out = submit_limit_buy(c, "ETH/USD", 0.1, 3000.0)
    assert out == {"id": "x"}
    c.place_order.assert_called_once_with(
        "ETH/USD", "buy", "limit", 0.1, 3000.0, params=None
    )


def test_submit_limit_sell_all_free_raises_when_flat() -> None:
    c = MagicMock()
    c.get_open_positions.return_value = {"ETH/USD": (0.0, 0.0)}
    with pytest.raises(ValueError, match="vrije qty"):
        submit_limit_sell_all_free(c, "ETH/USD", 100.0)


def test_submit_limit_sell_all_free_uses_free_qty() -> None:
    c = MagicMock()
    c.get_open_positions.return_value = {"ETH/USD": (0.25, 0.25)}
    c.place_order.return_value = {"id": "s"}
    out = submit_limit_sell_all_free(c, "ETH/USD", 99.0)
    assert out == {"id": "s"}
    c.place_order.assert_called_once_with(
        "ETH/USD", "sell", "limit", 0.25, 99.0, params=None
    )
