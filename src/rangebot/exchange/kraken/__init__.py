"""Kraken spot USD adapter (package root — re-exports stable public API)."""

from __future__ import annotations

from rangebot.exchange.kraken.client import (
    KrakenExchangeClient,
    create_kraken_client,
    make_exchange,
)
from rangebot.exchange.kraken.common import norm_symbol
from rangebot.exchange.kraken.state_and_fills import (
    append_kraken_fill_audit,
    check_and_notify_kraken_fills,
    fetch_open_orders,
    filter_kraken_usd_pool,
    get_kraken_cumulative_fictive_fees_usd,
    load_kraken_trade_state,
    save_kraken_state,
)
from rangebot.exchange.kraken.validation import OrderValidationError
from rangebot.exchange.kraken.transport import (
    build_ccxt_kraken,
    load_kraken_credentials_from_env,
    retry_ccxt,
)

__all__ = [
    "OrderValidationError",
    "KrakenExchangeClient",
    "append_kraken_fill_audit",
    "build_ccxt_kraken",
    "check_and_notify_kraken_fills",
    "create_kraken_client",
    "fetch_open_orders",
    "filter_kraken_usd_pool",
    "get_kraken_cumulative_fictive_fees_usd",
    "load_kraken_credentials_from_env",
    "load_kraken_trade_state",
    "make_exchange",
    "norm_symbol",
    "retry_ccxt",
    "save_kraken_state",
]
