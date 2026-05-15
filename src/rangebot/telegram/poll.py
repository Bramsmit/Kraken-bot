"""Dispatch Telegram long-polling loop for slash commands."""

from __future__ import annotations

import logging
import sys

from rangebot.telegram.client import TelegramBotApi
from rangebot.telegram.commands import (
    dispatch_command,
    extract_command_text_and_chat,
)
from rangebot.telegram.config import TelegramConfigError, load_telegram_credentials
from rangebot.utils.logging import configure_stdout_logging


def main() -> None:
    configure_stdout_logging()
    log = logging.getLogger(__name__)
    try:
        creds = load_telegram_credentials(require_chat=True)
    except TelegramConfigError as e:
        print(f"Config: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    api = TelegramBotApi(creds.token, creds.chat_id)
    log.info(
        "Telegram command-bot gestart (long poll). Reageert alleen op de geconfigureerde chat."
    )
    offset: int | None = None
    while True:
        try:
            updates = api.get_updates(offset=offset, timeout=25)
        except TelegramConfigError as e:
            log.warning("getUpdates: %s", e)
            continue
        for u in updates:
            uid = u.get("update_id")
            if isinstance(uid, int):
                offset = uid + 1
            msg = u.get("message")
            if not msg:
                continue
            text, cid = extract_command_text_and_chat(msg)
            if not text.startswith("/"):
                continue
            reply = dispatch_command(
                text,
                expected_chat_id=api.default_chat_id,
                from_chat_id=cid,
            )
            if reply:
                try:
                    api.send_message(reply, chat_id=str(cid))
                except TelegramConfigError as send_err:
                    log.warning("antwoord sturen mislukt: %s", send_err)


if __name__ == "__main__":
    main()
