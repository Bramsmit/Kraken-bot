"""
Compatibility shim: Kraken runtime now lives under ``rangebot``.

New code should import from ``rangebot.exchange.kraken`` and related modules.
"""

from __future__ import annotations

from rangebot.data.market_data import (
    fetch_daily_rows,
    fetch_symbol_rows_for_pool,
    get_mid_price,
)
from rangebot.exchange.base import ExchangeClient
from rangebot.exchange.kraken import (
    KrakenExchangeClient,
    append_kraken_fill_audit,
    check_and_notify_kraken_fills,
    create_kraken_client,
    fetch_open_orders,
    filter_kraken_usd_pool,
    get_kraken_cumulative_fictive_fees_usd,
    load_kraken_trade_state,
    make_exchange,
    norm_symbol,
    save_kraken_state,
)
from rangebot.execution.order_manager import (
    cancel_order_safe,
    order_age_hours,
    round_limit_price,
    submit_limit_buy,
    submit_limit_sell_all_free,
)
from rangebot.execution.position_manager import (
    MIN_SELLABLE_CRYPTO_QTY,
    estimate_portfolio_usd,
    get_buying_power_usd,
    get_positions_map,
    get_qty_for_symbol,
    persist_entries_from_balances,
)

_norm_symbol = norm_symbol
_round_price = round_limit_price


def fetch_daily_rows_ccxt(
    client: ExchangeClient,
    symbol: str,
    *,
    limit: int = 15,
) -> list[dict[str, float]]:
    """Backward-compatible name; pass any :class:`ExchangeClient` implementation."""
    return fetch_daily_rows(client, symbol, limit=limit)


__all__ = [
    "MIN_SELLABLE_CRYPTO_QTY",
    "KrakenExchangeClient",
    "_norm_symbol",
    "_round_price",
    "append_kraken_fill_audit",
    "cancel_order_safe",
    "check_and_notify_kraken_fills",
    "create_kraken_client",
    "estimate_portfolio_usd",
    "fetch_daily_rows",
    "fetch_daily_rows_ccxt",
    "fetch_open_orders",
    "fetch_symbol_rows_for_pool",
    "filter_kraken_usd_pool",
    "get_buying_power_usd",
    "get_kraken_cumulative_fictive_fees_usd",
    "get_mid_price",
    "get_positions_map",
    "get_qty_for_symbol",
    "load_kraken_trade_state",
    "make_exchange",
    "norm_symbol",
    "order_age_hours",
    "persist_entries_from_balances",
    "save_kraken_state",
    "submit_limit_buy",
    "submit_limit_sell_all_free",
]
