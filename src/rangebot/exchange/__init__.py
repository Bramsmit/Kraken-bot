"""Exchange adapters: protocol + Kraken implementation."""

from rangebot.exchange.base import ExchangeClient
from rangebot.exchange.kraken import (
    KrakenExchangeClient,
    create_kraken_client,
    make_exchange,
)

__all__ = [
    "ExchangeClient",
    "KrakenExchangeClient",
    "create_kraken_client",
    "make_exchange",
]
