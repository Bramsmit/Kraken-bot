"""Kraken adapter implementing :class:`~rangebot.exchange.base.ExchangeClient`."""

from __future__ import annotations

import logging
from typing import Any, Literal

import ccxt

from rangebot.config.settings import (
    KRAKEN_MAX_POSITION_VALUE_USD,
    kraken_dry_run_from_env,
)
from rangebot.exchange.base import ExchangeClient
from rangebot.exchange.kraken.balances import KrakenBalances
from rangebot.exchange.kraken.common import balance_entry, norm_symbol, post_only_from_env
from rangebot.exchange.kraken.market_data import KrakenMarketData
from rangebot.exchange.kraken.order_execution import KrakenOrderExecution
from rangebot.exchange.kraken.transport import build_ccxt_kraken
from rangebot.exchange.kraken.validation import (
    OrderValidationError,
    validate_limit_order_placement,
)

log = logging.getLogger(__name__)


class KrakenExchangeClient(ExchangeClient):
    """Kraken spot: market data, balances, and orders are separated internally."""

    def __init__(self, ccxt_exchange: ccxt.kraken, *, dry_run: bool) -> None:
        self._ex = ccxt_exchange
        self._dry_run = dry_run
        self._market = KrakenMarketData(ccxt_exchange)
        self._balances = KrakenBalances(ccxt_exchange)
        self._orders = KrakenOrderExecution(ccxt_exchange)

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    def get_latest_price(self, symbol: str) -> float | None:
        try:
            t = self._market.fetch_ticker(symbol)
            bid = float(t.get("bid") or 0)
            ask = float(t.get("ask") or 0)
            last = float(t.get("last") or t.get("close") or 0)
            if bid and ask:
                return (bid + ask) / 2
            return last or None
        except Exception as e:
            log.warning("get_latest_price %s: %s", symbol, e)
            return None

    def get_balances(self) -> dict[str, Any]:
        try:
            return self._balances.fetch_balances()
        except Exception as e:
            log.error("fetch_balances: %s", e)
            raise

    def get_free_quote_balance(self) -> float:
        bal = self.get_balances()
        return self._balances.free_quote_usd(bal)

    def get_open_positions(
        self, symbols: list[str]
    ) -> dict[str, tuple[float, float]]:
        bal = self.get_balances()
        out: dict[str, tuple[float, float]] = {}
        for sym in symbols:
            base = sym.split("/")[0]
            out[sym] = balance_entry(bal, base)
        return out

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
        if order_type != "limit":
            raise ValueError("only limit orders supported")
        sym = norm_symbol(symbol)
        px = float(self._ex.price_to_precision(sym, price))
        amt = float(self._ex.amount_to_precision(sym, amount))
        if amt <= 0:
            raise ValueError(f"Order amount na precision is 0 voor {sym}")

        balances = self.get_balances()
        open_orders = self._orders.fetch_open_orders(sym)
        try:
            validate_limit_order_placement(
                self._ex,
                balances,
                sym,
                side,
                amt,
                px,
                max_position_value_usd=KRAKEN_MAX_POSITION_VALUE_USD,
                open_orders=open_orders,
            )
        except OrderValidationError:
            log.warning(
                "Order validatie geweigerd %s %s amt=%s @ %s (open orders: %d)",
                side,
                sym,
                amt,
                px,
                len(open_orders),
            )
            raise

        merged = dict(params or {})
        if post_only_from_env():
            merged.setdefault("postOnly", True)

        if self._dry_run:
            log.info(
                "DRY_RUN zou nu LIMIT %s %s sturen: amt=%s @ %s params=%s",
                side.upper(),
                sym,
                amt,
                px,
                merged or None,
            )
            return None

        if side == "buy":
            return self._orders.create_limit_buy(sym, amt, px, merged)
        return self._orders.create_limit_sell(sym, amt, px, merged)

    def cancel_order(self, order_id: str, symbol: str) -> None:
        sym = norm_symbol(symbol)
        self._orders.cancel_order(order_id, sym)

    def get_open_orders(self, symbol: str) -> list[dict[str, Any]]:
        return self._orders.fetch_open_orders(norm_symbol(symbol))

    def fetch_daily_ohlcv(
        self, symbol: str, *, limit: int = 15
    ) -> list[dict[str, float]]:
        sym = norm_symbol(symbol)
        try:
            raw = self._market.fetch_ohlcv(sym, timeframe="1d", limit=limit)
            rows: list[dict[str, float]] = []
            for o in raw:
                _ts, ope, hi, lo, clo, _vol = o
                rows.append(
                    {
                        "open": float(ope),
                        "high": float(hi),
                        "low": float(lo),
                        "close": float(clo),
                    }
                )
            return rows
        except Exception as e:
            log.warning("fetch_daily_ohlcv %s: %s", sym, e)
            raise

    def fetch_my_trades(
        self,
        symbol: str,
        *,
        since_ms: int | None = None,
        limit: int = 80,
    ) -> list[dict[str, Any]]:
        sym = norm_symbol(symbol)
        try:
            return self._orders.fetch_my_trades(
                sym, since_ms=since_ms, limit=limit
            )
        except Exception as e:
            log.warning("fetch_my_trades %s: %s", sym, e)
            return []

    def filter_tradable_symbol_pool(self, pool: list[str]) -> list[str]:
        out: list[str] = []
        for sym in pool:
            u = norm_symbol(sym)
            if u.endswith("/USD") and u in self._ex.markets:
                m = self._ex.markets[u]
                if m.get("active", True):
                    out.append(u)
                else:
                    log.warning("Kraken: market inactief, skip %s", u)
            else:
                log.warning("Kraken: market ontbreekt of inactief, skip %s", sym)
        return out


def create_kraken_client(*, dry_run: bool | None = None) -> KrakenExchangeClient:
    """Connect using ``KRAKEN_*`` env vars; ``dry_run`` overrides env when set."""
    dr = kraken_dry_run_from_env() if dry_run is None else dry_run
    return KrakenExchangeClient(build_ccxt_kraken(), dry_run=dr)


def make_exchange(*, dry_run: bool | None = None) -> KrakenExchangeClient:
    return create_kraken_client(dry_run=dry_run)
