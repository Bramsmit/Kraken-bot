"""Unit tests for strategy signal helpers (mocked exchange)."""

from __future__ import annotations

from unittest.mock import MagicMock

from rangebot.exchange.base import ExchangeClient
from rangebot.strategy import signals


def test_symbols_with_balance_includes_only_above_dust() -> None:
    client = MagicMock(spec=ExchangeClient)

    def mock_positions(syms: list[str]) -> dict[str, tuple[float, float]]:
        out: dict[str, tuple[float, float]] = {}
        for s in syms:
            if s == "ETH/USD":
                out[s] = (1.0, 30.0)
            else:
                out[s] = (0.106, 1.50)
        return out

    def mock_price(sym: str) -> float:
        return {"ETH/USD": 30.0, "BTC/USD": 1.50}[sym]

    client.get_open_positions.side_effect = mock_positions
    client.get_latest_price.side_effect = mock_price
    pool = ["ETH/USD", "BTC/USD"]
    assert signals.symbols_with_balance(client, pool) == {"ETH/USD"}


def test_symbols_with_balance_skips_symbol_when_price_unavailable() -> None:
    client = MagicMock(spec=ExchangeClient)
    client.get_open_positions.return_value = {"ETH/USD": (1.0, 30.0)}
    client.get_latest_price.side_effect = RuntimeError("api down")
    assert signals.symbols_with_balance(client, ["ETH/USD"]) == set()
