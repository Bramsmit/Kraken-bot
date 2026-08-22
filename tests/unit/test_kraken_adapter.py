"""Unit tests for the Kraken exchange adapter (mocked ccxt)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import ccxt
import pytest

from rangebot.config.settings import kraken_dry_run_from_env
from rangebot.exchange.kraken.client import KrakenExchangeClient, create_kraken_client
from rangebot.exchange.kraken.common import post_only_from_env
from rangebot.exchange.kraken.state_and_fills import _stable_trade_id
from rangebot.exchange.kraken.validation import kraken_limit_minimums
from rangebot.exchange.kraken.transport import (
    bump_kraken_nonce_after_invalid,
    next_kraken_nonce,
    retry_ccxt,
)
from rangebot.exchange.kraken.validation import (
    OrderValidationError,
    validate_limit_order_placement,
)


def _minimal_market() -> dict:
    return {
        "active": True,
        "limits": {
            "amount": {"min": 0.01, "max": 1e9},
            "cost": {"min": 5.0, "max": 1e12},
        },
    }


@pytest.fixture
def mock_ccxt() -> MagicMock:
    mk = MagicMock(spec=ccxt.kraken)
    mk.markets = {"ETH/USD": _minimal_market(), "BTC/USD": _minimal_market()}
    mk.price_to_precision = MagicMock(side_effect=lambda _s, p: float(f"{p:.2f}"))
    mk.amount_to_precision = MagicMock(side_effect=lambda _s, a: float(f"{a:.4f}"))
    return mk


def test_kraken_dry_run_defaults_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KRAKEN_DRY_RUN", raising=False)
    assert kraken_dry_run_from_env() is True


def test_kraken_dry_run_explicit_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KRAKEN_DRY_RUN", "false")
    assert kraken_dry_run_from_env() is False


def test_post_only_defaults_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KRAKEN_POST_ONLY", raising=False)
    assert post_only_from_env() is True


def test_post_only_explicit_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KRAKEN_POST_ONLY", "false")
    assert post_only_from_env() is False


def test_retry_ccxt_succeeds_after_transient_failure(mock_ccxt: MagicMock) -> None:
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise ccxt.NetworkError("temporary")
        return "ok"

    with patch("rangebot.exchange.kraken.transport.time.sleep"):
        assert retry_ccxt("test", flaky, max_attempts=4) == "ok"
    assert calls["n"] == 2


def test_next_kraken_nonce_is_monotonic(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    nonce_file = tmp_path / ".kraken_api_nonce"
    monkeypatch.setattr(
        "rangebot.exchange.kraken.transport._kraken_nonce_path",
        lambda: nonce_file,
    )
    monkeypatch.setattr(
        "rangebot.exchange.kraken.transport.time.time",
        lambda: 1_700_000_000.0,
    )
    n1 = next_kraken_nonce()
    n2 = next_kraken_nonce()
    assert n2 > n1
    assert n1 == 1_700_000_000_000


def test_bump_kraken_nonce_after_invalid(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    nonce_file = tmp_path / ".kraken_api_nonce"
    nonce_file.write_text("1000", encoding="utf-8")
    monkeypatch.setattr(
        "rangebot.exchange.kraken.transport._kraken_nonce_path",
        lambda: nonce_file,
    )
    monkeypatch.setattr(
        "rangebot.exchange.kraken.transport.time.time",
        lambda: 1_700_000_000.0,
    )
    bump_kraken_nonce_after_invalid()
    assert int(nonce_file.read_text()) >= 1_700_000_005_000


def test_retry_ccxt_recovers_from_invalid_nonce(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    nonce_file = tmp_path / ".kraken_api_nonce"
    monkeypatch.setattr(
        "rangebot.exchange.kraken.transport._kraken_nonce_path",
        lambda: nonce_file,
    )
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise ccxt.InvalidNonce('kraken {"error":["EAPI:Invalid nonce"]}')
        return "ok"

    with patch("rangebot.exchange.kraken.transport.time.sleep"):
        assert retry_ccxt("test", flaky, max_attempts=4) == "ok"
    assert calls["n"] == 2


def test_validate_rejects_unknown_pair(mock_ccxt: MagicMock) -> None:
    bal = {"USD": {"free": 1000}}
    with pytest.raises(OrderValidationError, match="onbekend"):
        validate_limit_order_placement(
            mock_ccxt,
            bal,
            "DOGE/USD",
            "buy",
            10.0,
            0.1,
            max_position_value_usd=None,
            open_orders=[],
        )


def test_validate_rejects_duplicate_buy(mock_ccxt: MagicMock) -> None:
    bal = {"USD": {"free": 1000}, "ETH": {"free": 0}}
    open_o = [{"id": "o1", "side": "buy", "type": "limit"}]
    with pytest.raises(OrderValidationError, match="open buy"):
        validate_limit_order_placement(
            mock_ccxt,
            bal,
            "ETH/USD",
            "buy",
            0.1,
            3000.0,
            max_position_value_usd=None,
            open_orders=open_o,
        )


def test_validate_rejects_insufficient_quote(mock_ccxt: MagicMock) -> None:
    bal = {"USD": {"free": 1}, "ETH": {"free": 0}}
    with pytest.raises(OrderValidationError, match="Onvoldoende"):
        validate_limit_order_placement(
            mock_ccxt,
            bal,
            "ETH/USD",
            "buy",
            0.5,
            3000.0,
            max_position_value_usd=None,
            open_orders=[],
        )


def test_place_order_dry_run_no_ccxt_create_limit(mock_ccxt: MagicMock) -> None:
    client = KrakenExchangeClient(mock_ccxt, dry_run=True)
    with patch.object(
        client,
        "get_balances",
        return_value={"USD": {"free": 10_000}, "ETH": {"free": 0}, "ZUSD": {"free": 0}},
    ):
        client._orders.fetch_open_orders = MagicMock(return_value=[])
        out = client.place_order("ETH/USD", "buy", "limit", 0.1, 3000.0)
    assert out is None
    mock_ccxt.create_limit_buy_order.assert_not_called()
    mock_ccxt.create_limit_sell_order.assert_not_called()


def test_place_order_live_calls_create_limit_buy(mock_ccxt: MagicMock) -> None:
    client = KrakenExchangeClient(mock_ccxt, dry_run=False)
    mock_ccxt.create_limit_buy_order.return_value = {"id": "x"}
    with patch.object(
        client,
        "get_balances",
        return_value={"USD": {"free": 10_000}, "ETH": {"free": 0}, "ZUSD": {"free": 0}},
    ):
        client._orders.fetch_open_orders = MagicMock(return_value=[])
        out = client.place_order("ETH/USD", "buy", "limit", 0.1, 3000.0)
    assert out == {"id": "x"}
    mock_ccxt.create_limit_buy_order.assert_called_once()


@patch("rangebot.exchange.kraken.client.build_ccxt_kraken")
def test_create_kraken_client_respects_env_dry_run(
    mock_build: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_build.return_value = MagicMock(spec=ccxt.kraken)
    mock_build.return_value.markets = {"ETH/USD": _minimal_market()}
    monkeypatch.setenv("KRAKEN_DRY_RUN", "true")
    c = create_kraken_client()
    assert c.dry_run is True


def test_maker_safe_clamps_buy_at_or_above_ask(mock_ccxt: MagicMock) -> None:
    """Aggressive limit (>= ask at venue precision) must be pulled below the ask."""
    client = KrakenExchangeClient(mock_ccxt, dry_run=True)
    client._market.fetch_ticker = MagicMock(
        return_value={"bid": 0.24, "ask": 0.255, "last": 0.25}
    )
    out = client.maker_safe_limit_buy_price("ETH/USD", 0.2596)
    assert out is not None
    assert out == pytest.approx(0.25)
    assert out < 0.26


def test_kraken_limit_minimums_from_market(mock_ccxt: MagicMock) -> None:
    a, c = kraken_limit_minimums(mock_ccxt, "ETH/USD")
    assert a == pytest.approx(0.01)
    assert c == pytest.approx(5.0)


def test_client_limit_order_minimums_delegates(mock_ccxt: MagicMock) -> None:
    client = KrakenExchangeClient(mock_ccxt, dry_run=True)
    assert client.limit_order_minimums("ETH/USD") == (0.01, 5.0)


def test_stable_trade_id_uses_exchange_id() -> None:
    t = _stable_trade_id(
        {"id": "TX1", "symbol": "ETH/USD", "side": "sell"},
        pool_set={"ETH/USD"},
    )
    assert t == "TX1"


def test_stable_trade_id_synthetic_without_id() -> None:
    t = _stable_trade_id(
        {
            "id": "",
            "symbol": "ETH/USD",
            "timestamp": 1_700_000_000_000,
            "side": "sell",
            "amount": 1.5,
            "price": 2000.0,
        },
        pool_set={"ETH/USD"},
    )
    assert t is not None
    assert t.startswith("noid:ETH/USD:")


def test_stable_trade_id_respects_pool() -> None:
    t = _stable_trade_id(
        {"id": "", "symbol": "DOGE/USD", "timestamp": 1000, "side": "buy", "amount": 1, "price": 0.1},
        pool_set={"ETH/USD"},
    )
    assert t is None
