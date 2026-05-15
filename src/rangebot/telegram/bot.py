"""
Telegram facade: notification helpers and public send entry points.

Low-level HTTP: ``rangebot.telegram.client``; fills: ``rangebot.telegram.notifications``.
"""

from __future__ import annotations

from rangebot.telegram.client import (
    TelegramBotApi,
    get_telegram_api,
    send_plain_message,
)
from rangebot.telegram.notifications import (
    notify_stop_loss,
    notify_trade,
    notify_trade_filled,
)


def send_telegram(message: str) -> bool:
    """Send a plain-text message to the configured default chat."""
    return send_plain_message(message)


__all__ = [
    "TelegramBotApi",
    "get_telegram_api",
    "notify_stop_loss",
    "notify_trade",
    "notify_trade_filled",
    "send_plain_message",
    "send_telegram",
]
