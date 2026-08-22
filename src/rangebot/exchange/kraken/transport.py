"""ccxt Kraken construction, credentials from environment, and retried API calls."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import ccxt

from rangebot.utils.paths import repository_root

log = logging.getLogger(__name__)

T = TypeVar("T")

_KRAKEN_NONCE_FILE = ".kraken_api_nonce"


def _kraken_nonce_path() -> Path:
    return repository_root() / _KRAKEN_NONCE_FILE


def _read_stored_kraken_nonce() -> int:
    path = _kraken_nonce_path()
    if not path.exists():
        return 0
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0


def _write_stored_kraken_nonce(value: int) -> None:
    path = _kraken_nonce_path()
    path.write_text(str(value), encoding="utf-8")


def _kraken_nonce_now_ms() -> int:
    """Kraken expects an always-increasing nonce; milliseconds since epoch is standard."""
    return int(time.time() * 1000)


def _normalize_stored_kraken_nonce(last: int) -> int:
    """Convert accidental microsecond-scale stored values back to milliseconds."""
    if last > 10**14:
        return last // 1000
    return last


def next_kraken_nonce() -> int:
    """
    Monotonic Kraken API nonce (milliseconds), persisted across runs.

    Kraken rejects duplicate or decreasing nonces. Sharing one API key across
    CI, local runs, and MCP requires a file-backed counter that always moves
    forward.
    """
    now_ms = _kraken_nonce_now_ms()
    last = _normalize_stored_kraken_nonce(_read_stored_kraken_nonce())
    n = max(last + 1, now_ms)
    _write_stored_kraken_nonce(n)
    return n


def bump_kraken_nonce_after_invalid(*, ahead_ms: int = 60_000) -> None:
    """Jump nonce forward after EAPI:Invalid nonce (other client used the key)."""
    now_ms = _kraken_nonce_now_ms()
    last = _normalize_stored_kraken_nonce(_read_stored_kraken_nonce())
    _write_stored_kraken_nonce(max(last + ahead_ms, now_ms + ahead_ms))
    log.warning(
        "Kraken nonce bumped naar %d ms na InvalidNonce",
        _read_stored_kraken_nonce(),
    )


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
            "nonce": next_kraken_nonce,
            "options": {"adjustForTimeDifference": True},
        }
    )
    ex.load_markets()
    return ex


_RETRIABLE = (
    ccxt.NetworkError,
    ccxt.RequestTimeout,
    ccxt.ExchangeNotAvailable,
    ccxt.DDoSProtection,
    ccxt.InvalidNonce,
)


def retry_ccxt(description: str, fn: Callable[[], T], *, max_attempts: int = 4) -> T:
    """Retry transient ccxt failures with backoff (respects exchange.rateLimit)."""
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except _RETRIABLE as e:
            last_exc = e
            if isinstance(e, ccxt.InvalidNonce):
                bump_kraken_nonce_after_invalid()
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
