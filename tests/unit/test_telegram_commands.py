"""Tests for Telegram command dispatch and control state."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rangebot.telegram.commands import (
    dispatch_command,
    format_user_error,
)
from rangebot.telegram.control_state import (
    is_trading_paused,
    set_trading_paused,
)
from rangebot.telegram.services.kraken_snapshot import KrakenTelegramService


def test_dispatch_rejects_wrong_chat() -> None:
    out = dispatch_command(
        "/status",
        expected_chat_id="111",
        from_chat_id=999,
        service=MagicMock(spec=KrakenTelegramService),
    )
    assert out is None


def test_dispatch_help() -> None:
    r = dispatch_command(
        "/help",
        expected_chat_id="42",
        from_chat_id=42,
        service=MagicMock(spec=KrakenTelegramService),
    )
    assert r is not None
    assert "/status" in r


def test_format_user_error_hides_secret_like_text() -> None:
    msg = format_user_error(ValueError("invalid api_key in request"))
    assert "api_key" not in msg.lower()


def test_pause_toggle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "rangebot.telegram.control_state.repository_root",
        lambda: tmp_path,
    )
    assert is_trading_paused() is False
    set_trading_paused(True)
    assert is_trading_paused() is True
    data = json.loads((tmp_path / ".kraken_bot_control.json").read_text())
    assert data.get("paused") is True
    set_trading_paused(False)
    assert is_trading_paused() is False


def test_dispatch_dryrun_no_connect() -> None:
    svc = MagicMock(spec=KrakenTelegramService)
    svc.dry_run_summary.return_value = "dry info"
    r = dispatch_command(
        "/dryrun",
        expected_chat_id="1",
        from_chat_id=1,
        service=svc,
    )
    assert r == "dry info"
    svc.connect.assert_not_called()


def test_dispatch_balance_uses_service(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = object()
    svc = MagicMock(spec=KrakenTelegramService)
    svc.connect.return_value = fake_client
    svc.balance_summary.return_value = "bal"
    r = dispatch_command(
        "/balance",
        expected_chat_id="1",
        from_chat_id=1,
        service=svc,
    )
    assert r == "bal"
    svc.connect.assert_called_once()
    svc.balance_summary.assert_called_once_with(fake_client)
