"""Unit tests for portfolio / slot sizing helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rangebot.execution.position_manager import (
    capital_per_active_symbol_usd,
    ref_notional_for_range_selection,
)


def test_capital_per_slot_all_cash_equal_thirds() -> None:
    """Equity = cash → per-slot target equals cash/3 (with 0.995 factor)."""
    c = capital_per_active_symbol_usd(
        portfolio_equity_usd=900.0,
        free_quote_usd=900.0,
        n_symbols=3,
    )
    assert c == pytest.approx(900.0 / 3 * 0.995)


def test_capital_per_slot_cash_limited() -> None:
    """High equity in coins but little USD → capped by cash/n."""
    c = capital_per_active_symbol_usd(
        portfolio_equity_usd=900.0,
        free_quote_usd=30.0,
        n_symbols=3,
    )
    assert c == pytest.approx(10.0)


def test_ref_notional_uses_equity_over_cash_scale() -> None:
    client = MagicMock()
    client.get_balances.return_value = {
        "USD": {"free": 100.0},
        "ETH": {"free": 2.0},
    }
    client.get_free_quote_balance.return_value = 100.0
    client.get_latest_price.return_value = 10.0

    kr_pool = ["ETH/USD", "BTC/USD"]
    ref, equity = ref_notional_for_range_selection(
        client, kr_pool, symbols_active=2
    )
    assert equity == pytest.approx(120.0)
    assert ref == pytest.approx(59.7)

