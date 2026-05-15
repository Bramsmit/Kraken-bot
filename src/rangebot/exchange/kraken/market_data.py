"""Market data calls (ticker, OHLCV) — separate from balances and orders."""

from __future__ import annotations

from typing import Any

import ccxt

from rangebot.exchange.kraken.transport import retry_ccxt


class KrakenMarketData:
    """Public market data via ccxt (retried)."""

    def __init__(self, ex: ccxt.kraken) -> None:
        self._ex = ex

    def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        return retry_ccxt(
            f"fetch_ticker({symbol})",
            lambda: self._ex.fetch_ticker(symbol),
        )

    def fetch_ohlcv(
        self, symbol: str, *, timeframe: str = "1d", limit: int = 15
    ) -> list[list[Any]]:
        return retry_ccxt(
            f"fetch_ohlcv({symbol})",
            lambda: self._ex.fetch_ohlcv(
                symbol, timeframe=timeframe, limit=limit
            ),
        )
