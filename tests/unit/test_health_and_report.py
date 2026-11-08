"""Daily Status heartbeat and daily report built from data/kraken_equity.csv."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from rangebot.live.daily_report import build_daily_report
from rangebot.live.equity_log import EquityRow
from rangebot.live.health_check import build_health_message

NOW = datetime(2026, 11, 8, 9, 0, tzinfo=timezone.utc)


def _row(hours_ago: float, equity: float, deployed: float = 0.65) -> EquityRow:
    return EquityRow(
        timestamp=NOW - timedelta(hours=hours_ago),
        equity_usd=equity,
        cash_usd=equity * (1 - deployed),
        deployed_pct=deployed,
        positions="",
    )


def test_health_ok_when_recent_and_near_peak() -> None:
    ok, msg = build_health_message([_row(30, 520.0), _row(1, 515.0)], NOW, False)
    assert ok
    assert msg.startswith("✅")
    assert "$515.00" in msg
    assert "65%" in msg


def test_health_warns_when_last_run_is_stale() -> None:
    ok, msg = build_health_message([_row(13, 515.0)], NOW, False)
    assert not ok
    assert msg.startswith("⚠️")
    assert "13u" in msg


def test_health_warns_without_any_run() -> None:
    ok, msg = build_health_message([], NOW, False)
    assert not ok
    assert "geen" in msg.lower()


def test_health_warns_on_drawdown_from_peak() -> None:
    ok, msg = build_health_message([_row(50, 600.0), _row(1, 530.0)], NOW, False)
    assert not ok
    assert "piek" in msg.lower()


def test_health_warns_when_paused() -> None:
    ok, msg = build_health_message([_row(1, 515.0)], NOW, True)
    assert not ok
    assert "pauze" in msg.lower()


def test_report_shows_24h_change_peak_and_fees() -> None:
    rows = [_row(72, 560.0), _row(24, 520.0), _row(23, 521.0), _row(1, 514.0)]
    msg = build_daily_report(rows, NOW, live_value=510.0, cum_fees=12.34)
    assert "$510.00" in msg
    assert "-10.00" in msg  # vs 520 een dag geleden
    assert "$560.00" in msg  # piek
    assert "-8.9%" in msg  # 510 / 560
    assert "$12.34" in msg


def test_report_without_history_shows_value_and_fees() -> None:
    msg = build_daily_report([], NOW, live_value=510.0, cum_fees=1.0)
    assert "$510.00" in msg
    assert "24u" in msg and "n.v.t." in msg


def test_report_falls_back_to_last_row_when_live_value_missing() -> None:
    msg = build_daily_report([_row(1, 514.0)], NOW, live_value=None, cum_fees=0.0)
    assert "$514.00" in msg
