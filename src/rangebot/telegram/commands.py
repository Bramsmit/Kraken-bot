"""Map slash-commands to :class:`KrakenTelegramService` (no direct handler → strategy imports)."""

from __future__ import annotations

import logging

from rangebot.telegram.config import TelegramConfigError
from rangebot.telegram.control_state import is_trading_paused, set_trading_paused
from rangebot.telegram.services.kraken_snapshot import KrakenTelegramService

log = logging.getLogger(__name__)

_SECRET_SUBSTRINGS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "token",
    "credential",
)


def format_user_error(exc: BaseException) -> str:
    """User-visible error without leaking secrets."""
    msg = str(exc).strip() or type(exc).__name__
    low = msg.lower()
    if any(s in low for s in _SECRET_SUBSTRINGS):
        return (
            "Er ging iets mis; details zijn verborgen (mogelijk gevoelige info). "
            "Controleer de serverlogs."
        )
    if len(msg) > 400:
        return msg[:400] + "…"
    return msg


def _normalize_chat_id(x: str | int | None) -> str:
    if x is None:
        return ""
    return str(x).strip()


def dispatch_command(
    text: str,
    *,
    expected_chat_id: str,
    from_chat_id: str | int | None,
    service: KrakenTelegramService | None = None,
) -> str | None:
    """Return reply text, or None if not handled / unauthorized."""
    if _normalize_chat_id(from_chat_id) != _normalize_chat_id(expected_chat_id):
        log.warning("Telegram command genegeerd: chat id komt niet overeen met config")
        return None
    line = text.strip()
    if not line.startswith("/"):
        return None
    parts = line.split(maxsplit=1)
    cmd = parts[0].split("@")[0].lower()
    svc = service or KrakenTelegramService()

    try:
        if cmd in ("/help", "/start"):
            return (
                "Beschikbare commando’s:\n"
                "/status — selectie, levels, balans\n"
                "/positions — posities\n"
                "/orders — open orders\n"
                "/balance — USD / portfolio schatting\n"
                "/dryrun — dry-run status\n"
                "/pause — pauzeer geplande runs (reconciliatie stopt)\n"
                "/resume — hervat runs"
            )
        if cmd == "/dryrun":
            return svc.dry_run_summary()
        if cmd == "/pause":
            set_trading_paused(True)
            return "Trading gepauzeerd. Geplande runs slaan orderlogica over (controle: logs). Stuur /resume om verder te gaan."
        if cmd == "/resume":
            set_trading_paused(False)
            return "Trading hervat. Volgende run voert normaal uit."
        if cmd in ("/paused", "/ispaused"):
            return (
                "Pauze: "
                + ("JA — runs zijn uitgesteld." if is_trading_paused() else "NEE — runs actief.")
            )

        if cmd in ("/balance", "/positions", "/orders", "/status"):
            client = svc.connect()
            if cmd == "/balance":
                return svc.balance_summary(client)
            if cmd == "/positions":
                return svc.positions_summary(client)
            if cmd == "/orders":
                return svc.orders_summary(client)
            if cmd == "/status":
                return svc.status_summary(client)

        return f"Onbekend commando: {cmd}. Probeer /help."
    except TelegramConfigError as e:
        return format_user_error(e)
    except Exception as e:
        log.exception("Telegram command %s faalde", cmd)
        return "Fout: " + format_user_error(e)


def extract_command_text_and_chat(message: dict) -> tuple[str, str | None]:
    """From Telegram message object, return (text, chat_id)."""
    text = message.get("text") or ""
    chat = message.get("chat") or {}
    cid = chat.get("id")
    return text, cid
