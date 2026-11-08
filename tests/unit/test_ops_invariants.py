"""Ops-invarianten: fill-lookback en CI trade-state cache."""

from __future__ import annotations

from rangebot.config.settings import (
    FILLED_ORDERS_LOOKBACK_HOURS,
    KRAKEN_MAX_DEPLOYED_PCT,
    KRAKEN_MAX_POSITION_PCT,
    SYMBOLS_ACTIVE,
)
from rangebot.utils.paths import repository_root


def test_filled_orders_lookback_covers_github_schedule_gaps() -> None:
    # GitHub hourly cron loopt in de praktijk met gaten tot ~9,5u (soms een hele dag).
    # Gemiste fills → geen journal, geen instapprijs, geen sell-floor.
    assert FILLED_ORDERS_LOOKBACK_HOURS >= 72


def test_trade_workflow_cache_saves_after_hit() -> None:
    """actions/cache@v4 slaat niet op bij hit op de primary key — key moet uniek zijn."""
    yml = (repository_root() / ".github" / "workflows" / "trade.yml").read_text(
        encoding="utf-8"
    )
    assert "github.run_id" in yml
    assert "kraken-trade-state-${{ runner.os }}-${{ github.run_id }}" in yml
    assert "kraken-trade-state-${{ runner.os }}-" in yml
    # Exacte OS-key als restore-prefix is de bug: dan wordt de cache nooit herschreven.
    assert "key: kraken-trade-state-${{ runner.os }}\n" not in yml
    # Tweede restore-key zonder streepje pakt de bevroren Aug-22 cache.
    assert "kraken-trade-state-${{ runner.os }}\n" not in yml.split("restore-keys:")[-1]


def _workflow(name: str) -> str:
    return (repository_root() / ".github" / "workflows" / name).read_text(
        encoding="utf-8"
    )


def test_trade_workflow_commits_state_and_equity_and_honours_pause() -> None:
    yml = _workflow("trade.yml")
    # Een run die halverwege orders zit mag niet worden afgebroken.
    assert "cancel-in-progress: false" in yml
    staged = yml.split("git commit")[0].split("pull --rebase")[1]
    assert "data/kraken_state.json" in staged
    assert "data/kraken_equity.csv" in staged
    assert "KRAKEN_TRADING_PAUSED: ${{ vars.KRAKEN_TRADING_PAUSED }}" in yml


def test_daily_jobs_read_committed_data_not_cache() -> None:
    status = _workflow("daily_status.yml")
    assert "actions/checkout" in status
    assert "rangebot.live.health_check" in status
    assert "KRAKEN_TRADING_PAUSED: ${{ vars.KRAKEN_TRADING_PAUSED }}" in status

    report = _workflow("daily_report.yml")
    assert "actions/cache" not in report
    assert "rangebot.live.daily_report" in report


def test_slot_and_position_cap_prevent_three_bag_deadlock() -> None:
    """Met >=4 actieve slots en max 20% per positie blokkeren 3 bags niet alle koopslots."""
    assert SYMBOLS_ACTIVE >= 4
    assert 0.10 <= KRAKEN_MAX_POSITION_PCT <= 0.20
    assert KRAKEN_MAX_DEPLOYED_PCT >= 0.60

