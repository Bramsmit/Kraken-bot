"""Ops-invarianten: fill-lookback en CI trade-state cache."""

from __future__ import annotations

from rangebot.config.settings import FILLED_ORDERS_LOOKBACK_HOURS
from rangebot.utils.paths import repository_root


def test_filled_orders_lookback_covers_github_schedule_gaps() -> None:
    # GitHub hourly cron loopt in de praktijk met gaten tot ~7u (soms een hele dag).
    # 4u lookback mist fills → geen journal, geen instapprijs, geen sell-floor.
    assert FILLED_ORDERS_LOOKBACK_HOURS >= 24


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
