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
                out[s] = (0.001, 0.001)
            else:
                out[s] = (0.00001, 0.00001)
        return out

    client.get_open_positions.side_effect = mock_positions
    pool = ["ETH/USD", "BTC/USD"]
    assert signals.symbols_with_balance(client, pool) == {"ETH/USD"}
