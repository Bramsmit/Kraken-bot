"""Trading pause: Telegram control file or KRAKEN_TRADING_PAUSED (Actions variable)."""

from __future__ import annotations

import pytest

import rangebot.telegram.control_state as cs


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "repository_root", lambda: tmp_path)
    monkeypatch.delenv("KRAKEN_TRADING_PAUSED", raising=False)


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", " true "])
def test_env_variable_pauses_trading(monkeypatch, value) -> None:
    monkeypatch.setenv("KRAKEN_TRADING_PAUSED", value)
    assert cs.is_trading_paused() is True


@pytest.mark.parametrize("value", ["", "false", "0", "no"])
def test_env_variable_off_does_not_pause(monkeypatch, value) -> None:
    monkeypatch.setenv("KRAKEN_TRADING_PAUSED", value)
    assert cs.is_trading_paused() is False


def test_control_file_still_pauses() -> None:
    cs.set_trading_paused(True)
    assert cs.is_trading_paused() is True
