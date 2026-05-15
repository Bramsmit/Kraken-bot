"""Order placement, cancel, and open-order queries (retried)."""

from __future__ import annotations

import logging
from typing import Any

import ccxt

from rangebot.exchange.kraken.transport import retry_ccxt

log = logging.getLogger(__name__)


class KrakenOrderExecution:
    """Private order API via ccxt (retried)."""

    def __init__(self, ex: ccxt.kraken) -> None:
        self._ex = ex

    def fetch_open_orders(self, symbol: str) -> list[dict[str, Any]]:
        try:
            return (
                retry_ccxt(
                    f"fetch_open_orders({symbol})",
                    lambda: self._ex.fetch_open_orders(symbol) or [],
                )
            )
        except Exception as e:
            log.warning("fetch_open_orders %s: %s", symbol, e)
            return []

    def cancel_order(self, order_id: str, symbol: str) -> None:
        retry_ccxt(
            f"cancel_order({order_id})",
            lambda: self._ex.cancel_order(order_id, symbol),
        )

    def create_limit_buy(
        self,
        symbol: str,
        amount: float,
        price: float,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        return retry_ccxt(
            f"create_limit_buy({symbol})",
            lambda: self._ex.create_limit_buy_order(
                symbol, amount, price, params=params
            ),
        )

    def create_limit_sell(
        self,
        symbol: str,
        amount: float,
        price: float,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        return retry_ccxt(
            f"create_limit_sell({symbol})",
            lambda: self._ex.create_limit_sell_order(
                symbol, amount, price, params=params
            ),
        )

    def fetch_my_trades(
        self,
        symbol: str,
        *,
        since_ms: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        return retry_ccxt(
            f"fetch_my_trades({symbol})",
            lambda: self._ex.fetch_my_trades(symbol, since=since_ms, limit=limit)
            or [],
        )
