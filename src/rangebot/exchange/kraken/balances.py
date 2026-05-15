"""Balance fetching — separate from market data and order execution."""

from __future__ import annotations

from typing import Any

import ccxt

from rangebot.exchange.kraken.common import balance_entry
from rangebot.exchange.kraken.transport import retry_ccxt


class KrakenBalances:
    """Account balances via ccxt (retried)."""

    def __init__(self, ex: ccxt.kraken) -> None:
        self._ex = ex

    def fetch_balances(self) -> dict[str, Any]:
        return retry_ccxt("fetch_balance", lambda: self._ex.fetch_balance())

    def free_quote_usd(self, balances: dict[str, Any]) -> float:
        """Free USD including Kraken ZUSD alias."""
        free, _ = balance_entry(balances, "USD")
        if free <= 0:
            free_z, _ = balance_entry(balances, "ZUSD")
            free = free_z
        return free
