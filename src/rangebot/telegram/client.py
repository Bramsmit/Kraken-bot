"""Low-level Telegram Bot API client (send + long-poll receive)."""

from __future__ import annotations

import logging
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

from rangebot.telegram.config import (
    TelegramConfigError,
    load_telegram_credentials,
)

log = logging.getLogger(__name__)

_USE_REQUESTS = (
    "Het `requests` pakket is nodig voor Telegram. Installeer dependencies."
)
_POST_FAIL = (
    "Kan geen verbinding maken met Telegram. Controleer netwerk (zie logs)."
)

_DEFAULT_API: TelegramBotApi | None = None


def _redact_url(url: str) -> str:
    """Avoid logging bot tokens in API URLs."""
    if "/bot" in url:
        prefix, _, rest = url.partition("/bot")
        tok, _, tail = rest.partition("/")
        if tok:
            return f"{prefix}/bot***{tail and '/' + tail}"
    return url


class TelegramBotApi:
    """Minimal Telegram Bot API wrapper.

    Does not expose secrets in logs or replies.
    """

    def __init__(self, token: str, default_chat_id: str) -> None:
        self._token = token
        self._default_chat_id = default_chat_id

    @property
    def default_chat_id(self) -> str:
        return self._default_chat_id

    def _post(self, method: str, **params: Any) -> dict[str, Any]:
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        if not requests:
            raise TelegramConfigError(_USE_REQUESTS)
        try:
            r = requests.post(url, json=params, timeout=35)
            data = r.json()
        except Exception as e:
            log.warning(
                "Telegram API request mislukt (%s): %s",
                _redact_url(url),
                type(e).__name__,
            )
            raise TelegramConfigError(_POST_FAIL) from e
        if not data.get("ok"):
            desc = data.get("description") or "onbekende fout"
            log.warning("Telegram API fout: %s", desc)
            raise TelegramConfigError(f"Telegram weigerde het verzoek: {desc}")
        return data

    def _get(self, method: str, **params: Any) -> dict[str, Any]:
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        if not requests:
            raise TelegramConfigError(_USE_REQUESTS)
        try:
            r = requests.get(url, params=params, timeout=40)
            data = r.json()
        except Exception as e:
            log.warning(
                "Telegram API GET mislukt (%s): %s",
                _redact_url(url),
                type(e).__name__,
            )
            raise TelegramConfigError(
                "Kan updates niet ophalen van Telegram (zie logs)."
            ) from e
        if not data.get("ok"):
            desc = data.get("description") or "onbekende fout"
            raise TelegramConfigError(f"Telegram updates: {desc}")
        return data

    def send_message(self, text: str, *, chat_id: str | None = None) -> bool:
        cid = chat_id if chat_id is not None else self._default_chat_id
        if not cid:
            log.warning("Geen chat_id voor Telegram-bericht")
            return False
        self._post("sendMessage", chat_id=cid, text=text)
        return True

    def get_updates(
        self,
        *,
        offset: int | None = None,
        timeout: int = 25,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        data = self._get("getUpdates", **params)
        return list(data.get("result") or [])


def get_telegram_api(*, reset: bool = False) -> TelegramBotApi | None:
    """Singleton client from env; None if token of default chat ontbreekt."""
    global _DEFAULT_API
    if reset:
        _DEFAULT_API = None
    if _DEFAULT_API is None:
        try:
            creds = load_telegram_credentials(require_chat=True)
            _DEFAULT_API = TelegramBotApi(creds.token, creds.chat_id)
        except TelegramConfigError as e:
            log.debug("Telegram niet geconfigureerd: %s", e)
            return None
    return _DEFAULT_API


def send_plain_message(text: str) -> bool:
    """Verstuur naar default chat; False bij ontbrekende config of fout."""
    api = get_telegram_api()
    if not api:
        print(
            "⚠️ TELEGRAM_BOT_TOKEN of TELEGRAM_CHAT_ID niet gezet; "
            "bericht niet verstuurd."
        )
        return False
    try:
        return api.send_message(text)
    except TelegramConfigError as e:
        print(f"❌ Telegram: {e}")
        return False
