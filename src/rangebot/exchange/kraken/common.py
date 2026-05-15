"""Shared helpers for the Kraken adapter (no I/O)."""

from __future__ import annotations

from typing import Any


def norm_symbol(s: str) -> str:
    """Normalize to unified BASE/USD when possible."""
    if "/" in s:
        return s
    if s.endswith("USD"):
        return f"{s[:-3]}/USD"
    return f"{s}/USD"


def balance_entry(balance: dict[str, Any], code: str) -> tuple[float, float]:
    """(free, total) for unified currency code (ccxt balance dict)."""
    b = balance.get(code) or {}
    if isinstance(b, dict):
        return float(b.get("free") or 0), float(b.get("total") or 0)
    return 0.0, float(b or 0)


def post_only_from_env() -> bool:
    import os

    return os.environ.get("KRAKEN_POST_ONLY", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def trade_fee_usd_from_ccxt(
    tr: dict[str, Any],
    *,
    symbol: str,
    price: float,
) -> float | None:
    """
    Parse unified ccxt trade ``fee`` into USD where possible (Kraken: ZUSD / quote).
    Returns None if missing or currency not mapped.
    """
    fee = tr.get("fee")
    if not isinstance(fee, dict):
        return None
    try:
        cost = float(fee.get("cost") or 0)
    except (TypeError, ValueError):
        return None
    if cost <= 0:
        return None
    ccy = str(fee.get("currency") or "").upper()
    norm_ccy = ccy.lstrip("Z")
    if norm_ccy in ("USD", "USDT"):
        return cost
    base = norm_symbol(symbol).split("/")[0].upper()
    fb = ccy.lstrip("Z")
    if fb in (base, "XBT") and base in ("BTC", "XBT"):
        return cost * float(price or 0)
    if fb == base:
        return cost * float(price or 0)
    return None
