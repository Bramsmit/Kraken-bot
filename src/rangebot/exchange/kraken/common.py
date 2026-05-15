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
