"""Balances, position view (qty, avg entry), and entry persistence."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from rangebot.config.settings import MIN_SELLABLE_CRYPTO_QTY
from rangebot.exchange.base import ExchangeClient

log = logging.getLogger(__name__)


def _balance_entry(balance: dict[str, Any], code: str) -> tuple[float, float]:
    """(free, total) for unified currency code."""
    b = balance.get(code) or {}
    if isinstance(b, dict):
        return float(b.get("free") or 0), float(b.get("total") or 0)
    return 0.0, float(b or 0)


def get_qty_for_symbol(client: ExchangeClient, symbol: str) -> tuple[float, float]:
    """(free_base, total_base) for BASE/USD."""
    return client.get_open_positions([symbol]).get(symbol, (0.0, 0.0))


def get_buying_power_usd(client: ExchangeClient) -> float:
    """Free quote (USD / venue-equivalent) for sizing."""
    return client.get_free_quote_balance()


def estimate_portfolio_usd(
    client: ExchangeClient,
    reference_symbols: list[str],
) -> float:
    """Rough USD: free USD + sum free base * last for watchlist symbols."""
    bal = client.get_balances()
    usd_free, _ = _balance_entry(bal, "USD")
    if usd_free <= 0:
        usd_free, _ = _balance_entry(bal, "ZUSD")
    total = usd_free
    for sym in reference_symbols:
        base = sym.split("/")[0]
        qf, _ = _balance_entry(bal, base)
        if qf and qf > 0:
            try:
                last = client.get_latest_price(sym)
                if last:
                    total += float(qf) * float(last)
            except Exception as e:  # noqa: BLE001
                log.warning("price %s: %s", sym, e)
    return total


def get_positions_map(
    client: ExchangeClient,
    symbols: list[str],
    entries_state: dict[str, Any],
) -> dict[str, tuple[float, float]]:
    """Per symbol: (free qty, avg entry from state)."""
    out: dict[str, tuple[float, float]] = {}
    for sym in symbols:
        free_q, _tot = get_qty_for_symbol(client, sym)
        ent = entries_state.get(sym) or {}
        ep = float(ent.get("entry") or 0)
        out[sym] = (free_q, ep)
    return out


def persist_entries_from_balances(
    client: ExchangeClient,
    symbols: list[str],
    entries_memory: dict[str, Any],
    mid_prices: dict[str, float],
) -> dict[str, Any]:
    """Entries dict: qty from balance, entry from memory or mid price."""
    out: dict[str, Any] = {}
    for sym in symbols:
        free_q, _ = get_qty_for_symbol(client, sym)
        if free_q <= 0:
            continue
        if Decimal(str(free_q)) < MIN_SELLABLE_CRYPTO_QTY:
            continue
        mem = entries_memory.get(sym)
        if mem and float(mem.get("entry") or 0) > 0:
            out[sym] = {"qty": float(free_q), "entry": float(mem["entry"])}
        else:
            px = float(mid_prices.get(sym) or 0)
            out[sym] = {"qty": float(free_q), "entry": px}
    return out
