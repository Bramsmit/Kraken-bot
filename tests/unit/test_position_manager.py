"""Unit tests for portfolio / slot sizing helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rangebot.execution.position_manager import (
    capital_per_active_symbol_usd,
    estimate_portfolio_usd,
    get_positions_map,
    is_tradable_position,
    persist_entries_from_balances,
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


def test_is_tradable_position_rejects_dust_notional() -> None:
    assert is_tradable_position(0.106, 1.50) is False  # ~$0.16


def test_is_tradable_position_accepts_real_position() -> None:
    assert is_tradable_position(1.0, 30.0) is True


def test_buy_slots_one_free_slot_gets_full_cash() -> None:
    c = capital_per_active_symbol_usd(
        portfolio_equity_usd=402.0,
        free_quote_usd=402.0,
        n_symbols=1,  # buy_slots=1
    )
    assert c == pytest.approx(402.0 / 1 * 0.995)


def _client_with_locked_aave() -> MagicMock:
    """AAVE volledig in een sell-order; cash deels in een open buy."""
    client = MagicMock()
    client.get_balances.return_value = {
        "USD": {"free": 145.0, "total": 211.0},
        "AAVE": {"free": 0.0, "total": 0.3444},
        "CRV": {"free": 544.3, "total": 544.3},
    }
    client.get_latest_price.side_effect = lambda s: {
        "AAVE/USD": 126.3,
        "CRV/USD": 0.3494,
    }[s]
    client.get_open_positions.side_effect = lambda syms: {
        s: {
            "AAVE/USD": (0.0, 0.3444),
            "CRV/USD": (544.3, 544.3),
        }.get(s, (0.0, 0.0))
        for s in syms
    }
    return client


def test_estimate_portfolio_counts_locked_coins_and_reserved_cash() -> None:
    """Open sell/buy-orders mogen equity niet laten verdwijnen."""
    client = _client_with_locked_aave()
    equity = estimate_portfolio_usd(client, ["AAVE/USD", "CRV/USD"])
    expected = 211.0 + 0.3444 * 126.3 + 544.3 * 0.3494
    assert equity == pytest.approx(expected, rel=1e-4)
    # De oude free-only som was ~$335 en miste AAVE + gereserveerde USD.
    assert equity > 400.0


def test_persist_entries_keeps_cost_basis_when_sell_locks_qty() -> None:
    client = _client_with_locked_aave()
    out = persist_entries_from_balances(
        client,
        ["AAVE/USD"],
        {"AAVE/USD": {"qty": 0.3444, "entry": 125.66}},
        {"AAVE/USD": 126.3},
    )
    assert "AAVE/USD" in out
    assert out["AAVE/USD"]["entry"] == pytest.approx(125.66)
    assert out["AAVE/USD"]["qty"] == pytest.approx(0.3444)


def test_persist_entries_does_not_invent_mid_as_entry() -> None:
    """Zonder bekende instap geen nep-kostprijs (= huidige koers)."""
    client = _client_with_locked_aave()
    out = persist_entries_from_balances(
        client,
        ["AAVE/USD"],
        {},
        {"AAVE/USD": 126.3},
    )
    assert "AAVE/USD" not in out or out["AAVE/USD"].get("entry") in (None, 0)


def test_positions_map_uses_total_qty_for_slots() -> None:
    client = _client_with_locked_aave()
    pos = get_positions_map(
        client,
        ["AAVE/USD"],
        {"AAVE/USD": {"entry": 125.66}},
    )
    qty, entry = pos["AAVE/USD"]
    assert qty == pytest.approx(0.3444)
    assert entry == pytest.approx(125.66)
    assert is_tradable_position(qty, 126.3) is True

