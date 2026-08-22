"""Balances, position view (qty, avg entry), and entry persistence."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from rangebot.config.settings import (
    BUYING_POWER_PER_SYMBOL_FRACTION,
    KRAKEN_MIN_POSITION_NOTIONAL_USD,
    MIN_SELLABLE_CRYPTO_QTY,
    ORDER_ESTIMATE_NOTIONAL_FRACTION,
    RANGE_MIN_ORDER_REF_USD,
)
from rangebot.exchange.base import ExchangeClient

log = logging.getLogger(__name__)


def is_tradable_position(qty: float, ref_price: float) -> bool:
    """True when free qty is above dust and notional meets the fee floor."""
    if qty <= 0 or Decimal(str(qty)) < MIN_SELLABLE_CRYPTO_QTY:
        return False
    return qty * float(ref_price or 0) >= KRAKEN_MIN_POSITION_NOTIONAL_USD


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


def ref_notional_for_range_selection(
    client: ExchangeClient,
    kr_pool: list[str],
    *,
    symbols_active: int,
) -> tuple[float, float]:
    """
    ``ref_usd`` for :func:`select_top_symbols_for_range` plus portfolio equity.

    Scale is **total portfolio** in ``kr_pool`` (cash + marked-to-market bases)
    divided by ``symbols_active``, capped by available cash on the estimate path.
    """
    equity = estimate_portfolio_usd(client, kr_pool)
    cash = get_buying_power_usd(client)
    n = max(1, int(symbols_active))
    cap_target = (equity / n) * BUYING_POWER_PER_SYMBOL_FRACTION
    est_order_usd = min(
        cap_target,
        max(0.0, cash * ORDER_ESTIMATE_NOTIONAL_FRACTION),
    )
    if est_order_usd > 0:
        ref_usd = max(RANGE_MIN_ORDER_REF_USD, est_order_usd)
    else:
        ref_usd = max(RANGE_MIN_ORDER_REF_USD, cap_target)
    return ref_usd, equity


def capital_per_active_symbol_usd(
    *,
    portfolio_equity_usd: float,
    free_quote_usd: float,
    n_symbols: int,
) -> float:
    """
    Target buy notional per selected symbol:

    ``min( (equity/n)×fraction , cash/n )`` so each slot may use up to 1/n of
    total portfolio (mark-to-market), but never more than a fair share of USD.
    """
    if n_symbols <= 0:
        return 0.0
    n = float(n_symbols)
    slot = max(0.0, portfolio_equity_usd) / n * BUYING_POWER_PER_SYMBOL_FRACTION
    cash_cap = max(0.0, free_quote_usd) / n
    return min(slot, cash_cap)


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
        ref_px = float(mid_prices.get(sym) or 0)
        if not is_tradable_position(free_q, ref_px):
            continue
        mem = entries_memory.get(sym)
        if mem and float(mem.get("entry") or 0) > 0:
            out[sym] = {"qty": float(free_q), "entry": float(mem["entry"])}
        else:
            px = float(mid_prices.get(sym) or 0)
            out[sym] = {"qty": float(free_q), "entry": px}
    return out
