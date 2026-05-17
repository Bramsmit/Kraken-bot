"""Venue-neutral exchange interface — range strategy and execution depend on this only."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal


class ExchangeClient(ABC):
    """Spot exchange surface used by the range runner.

    Implementations wrap a concrete API (e.g. ccxt). Strategy modules must not
    import venue-specific SDKs; they receive data via this client or pure inputs.
    """

    @property
    @abstractmethod
    def dry_run(self) -> bool:
        """When true, :meth:`place_order` must not hit the live API."""

    @abstractmethod
    def get_latest_price(self, symbol: str) -> float | None:
        """Mid or last price for ``symbol`` (e.g. ``BASE/USD``)."""

    def maker_safe_limit_buy_price(
        self, symbol: str, desired: float
    ) -> float | None:
        """Clamp limit buy so it does not cross the best ask (maker).

        Override on venues that can inspect the book. Default: no clamp.
        Return ``None`` only when no valid maker price exists.
        """
        _ = symbol
        return float(desired)

    def limit_order_minimums(
        self, symbol: str
    ) -> tuple[float | None, float | None]:
        """Minimum size on venue: ``(min_base_amount, min_quote_cost)`` if known."""
        _ = symbol
        return None, None

    @abstractmethod
    def get_balances(self) -> dict[str, Any]:
        """Unified balances (ccxt-style ``{code: {free, used, total}}``)."""

    @abstractmethod
    def get_free_quote_balance(self) -> float:
        """Free cash in the strategy quote asset (e.g. USD, including venue aliases)."""

    @abstractmethod
    def get_open_positions(
        self, symbols: list[str]
    ) -> dict[str, tuple[float, float]]:
        """Per ``BASE/USD`` symbol: ``(free_base, total_base)``."""

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        order_type: Literal["limit"],
        amount: float,
        price: float,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Submit a limit order; returns ``None`` when :attr:`dry_run` is active."""

    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> None:
        ...

    @abstractmethod
    def get_open_orders(self, symbol: str) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def fetch_daily_ohlcv(
        self, symbol: str, *, limit: int = 15
    ) -> list[dict[str, float]]:
        """Daily candles as strategy rows (``open``/``high``/``low``/``close``)."""

    @abstractmethod
    def fetch_my_trades(
        self,
        symbol: str,
        *,
        since_ms: int | None = None,
        limit: int = 80,
    ) -> list[dict[str, Any]]:
        """Recent account trades for fill reconciliation."""

    @abstractmethod
    def filter_tradable_symbol_pool(self, pool: list[str]) -> list[str]:
        """Symbols from ``pool`` that exist and are tradable on this venue."""
