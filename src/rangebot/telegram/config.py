"""Telegram credentials from environment (Kraken-specific overrides applied first)."""

from __future__ import annotations

import os
from dataclasses import dataclass


class TelegramConfigError(RuntimeError):
    """Missing or invalid Telegram configuration (no secrets in message)."""


@dataclass(frozen=True)
class TelegramCredentials:
    """Resolved bot token and default chat id (never log these in full)."""

    token: str
    chat_id: str


def apply_kraken_telegram_env_overrides() -> None:
    """Prefer ``*_KRAKEN`` token/chat for Kraken tooling when set."""
    cid = os.environ.get("TELEGRAM_CHAT_ID_KRAKEN")
    tok = os.environ.get("TELEGRAM_BOT_TOKEN_KRAKEN")
    if cid:
        os.environ["TELEGRAM_CHAT_ID"] = cid.strip().strip('"')
    if tok:
        os.environ["TELEGRAM_BOT_TOKEN"] = tok.strip().strip('"')


def load_telegram_credentials(*, require_chat: bool = True) -> TelegramCredentials:
    apply_kraken_telegram_env_overrides()
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token:
        raise TelegramConfigError(
            "Telegram bot token ontbreekt. Zet TELEGRAM_BOT_TOKEN (of TELEGRAM_BOT_TOKEN_KRAKEN) in .env."
        )
    if require_chat and not chat_id:
        raise TelegramConfigError(
            "Telegram chat id ontbreekt. Zet TELEGRAM_CHAT_ID (of TELEGRAM_CHAT_ID_KRAKEN) in .env."
        )
    if chat_id == "VUL_HIER_JE_CHAT_ID_IN":
        raise TelegramConfigError(
            "Vervang de placeholder TELEGRAM_CHAT_ID in .env door jouw echte chat id."
        )
    return TelegramCredentials(token=token, chat_id=chat_id)
