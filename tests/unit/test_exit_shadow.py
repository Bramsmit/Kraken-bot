"""Beschermende uitstap: nieuwe posities begrensd, de lopende vier alleen bij -60%."""

from datetime import datetime, timezone

from rangebot.live.equity_log import EquityRow, new_buys_paused
from rangebot.strategy.exit_shadow import protective_exit_reason

NOW = datetime(2026, 11, 22, tzinfo=timezone.utc)
OPEN = "2026-11-20T00:00:00+00:00"


def test_legacy_position_has_no_exit_at_fifty_percent_loss() -> None:
    assert protective_exit_reason(100.0, 50.0, None, NOW) is None


def test_legacy_position_exits_at_sixty_percent_loss() -> None:
    assert protective_exit_reason(100.0, 40.0, None, NOW) == "noodgrens"
    assert protective_exit_reason(100.0, 40.01, None, NOW) is None


def test_new_position_exits_at_fifteen_percent_loss() -> None:
    assert protective_exit_reason(100.0, 85.0, OPEN, NOW) == "verlies"
    assert protective_exit_reason(100.0, 85.01, OPEN, NOW) is None


def test_new_position_exits_after_fourteen_days() -> None:
    assert (
        protective_exit_reason(100.0, 99.0, "2026-11-01T00:00:00+00:00", NOW)
        == "leeftijd"
    )
    assert protective_exit_reason(100.0, 99.0, "2026-11-10T00:00:00+00:00", NOW) is None


def _row(equity: float) -> EquityRow:
    return EquityRow(NOW, equity, 0.0, 0.0, "")


def test_new_buys_pause_when_drawdown_passes_fifteen_percent() -> None:
    assert new_buys_paused([_row(500.0), _row(425.0)]) is True
    assert new_buys_paused([_row(500.0), _row(426.0)]) is False
    assert new_buys_paused([]) is False
