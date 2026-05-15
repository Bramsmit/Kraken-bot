"""Limit order placement, cancel, and age helpers (via :class:`ExchangeClient`)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from rangebot.config.settings import MICRO_PRICE_EPS, ROUND_LIMIT_PRICE_ONE
from rangebot.exchange.base import ExchangeClient
from rangebot.execution.position_manager import get_qty_for_symbol


def round_limit_price(price: float) -> float:
    """Round price for stable order submission (same thresholds as before)."""
    p = float(price)
    if p < MICRO_PRICE_EPS:
        return round(p, 8)
    if p < ROUND_LIMIT_PRICE_ONE:
        return round(p, 6)
    return round(p, 4)


def cancel_order_safe(client: ExchangeClient, order_id: str, symbol: str) -> None:
    client.cancel_order(order_id, symbol)


def submit_limit_buy(
    client: ExchangeClient,
    symbol: str,
    qty: float,
    price: float,
) -> dict[str, Any] | None:
    return client.place_order(
        symbol, "buy", "limit", qty, price, params=None
    )


def submit_limit_sell_all_free(
    client: ExchangeClient,
    symbol: str,
    price: float,
) -> dict[str, Any] | None:
    free_q, _ = get_qty_for_symbol(client, symbol)
    if free_q <= 0:
        raise ValueError(f"Geen vrije qty voor sell {symbol}")
    return client.place_order(
        symbol, "sell", "limit", free_q, price, params=None
    )


def order_age_hours(order: dict[str, Any]) -> float:
    ts = order.get("timestamp")
    if not ts:
        return 0.0
    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
