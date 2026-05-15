"""ccxt Kraken construction, credentials from environment, and retried API calls."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

import ccxt

log = logging.getLogger(__name__)

T = TypeVar("T")


def load_kraken_credentials_from_env() -> tuple[str, str]:
    """Read API key and secret from the environment (never hardcoded).

    Canonical secret env: ``KRAKEN_API_SECRET``. Legacy alias: ``KRAKEN_SECRET_KEY``.
    """
    import os

    api_key = os.environ.get("KRAKEN_API_KEY", "").strip()
    secret = (
        os.environ.get("KRAKEN_API_SECRET", "").strip()
        or os.environ.get("KRAKEN_SECRET_KEY", "").strip()
    )
    if not api_key or not secret:
        raise ValueError(
            "KRAKEN_API_KEY en KRAKEN_API_SECRET (of legacy KRAKEN_SECRET_KEY) "
            "zijn verplicht in de omgeving (.env)"
        )
    return api_key, secret


def build_ccxt_kraken() -> ccxt.kraken:
    """Connect with rate limiting enabled; loads markets."""
    api_key, secret = load_kraken_credentials_from_env()
    ex = ccxt.kraken(
        {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
        }
    )
    ex.load_markets()
    return ex


_RETRIABLE = (
    ccxt.NetworkError,
    ccxt.RequestTimeout,
    ccxt.ExchangeNotAvailable,
    ccxt.DDoSProtection,
)


def retry_ccxt(description: str, fn: Callable[[], T], *, max_attempts: int = 4) -> T:
    """Retry transient ccxt failures with backoff (respects exchange.rateLimit)."""
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except _RETRIABLE as e:
            last_exc = e
            wait = min(8.0, 1.0 * (2**attempt))
            log.warning(
                "%s (poging %d/%d): %s — %s",
                description,
                attempt + 1,
                max_attempts,
                type(e).__name__,
                e,
            )
            time.sleep(wait)
        except Exception:
            raise
    assert last_exc is not None
    log.error("%s definitief mislukt na %d pogingen", description, max_attempts)
    raise last_exc
