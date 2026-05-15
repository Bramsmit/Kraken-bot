"""Daily OHLCV and latest prices via :class:`~rangebot.exchange.base.ExchangeClient`."""

from __future__ import annotations

import logging

from rangebot.exchange.base import ExchangeClient

log = logging.getLogger(__name__)


def fetch_daily_rows(
    client: ExchangeClient,
    symbol: str,
    *,
    limit: int = 15,
) -> list[dict[str, float]]:
    """1D OHLCV rows for strategy (open/high/low/close floats)."""
    return client.fetch_daily_ohlcv(symbol, limit=limit)


def fetch_symbol_rows_for_pool(
    client: ExchangeClient,
    pool: list[str],
) -> dict[str, list[dict[str, float]]]:
    """Fetch daily rows for each symbol in pool (skip on per-symbol failure)."""
    out: dict[str, list[dict[str, float]]] = {}
    for sym in pool:
        try:
            out[sym] = fetch_daily_rows(client, sym)
        except Exception as e:
            log.warning("OHLCV %s: %s", sym, e)
    return out


def get_mid_price(client: ExchangeClient, symbol: str) -> float | None:
    """Mid price from bid/ask or last."""
    return client.get_latest_price(symbol)
