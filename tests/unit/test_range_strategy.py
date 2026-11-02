"""Unit tests for venue-neutral range math."""

from __future__ import annotations

import pytest

from rangebot.config.settings import LEVELS_LOOKBACK_DAYS
from rangebot.strategy.range_strategy import (
    build_levels_scored_from_symbol_rows,
    is_falling_knife,
    levels_passing_spread,
    levels_score_from_daily_rows,
    select_top_symbols_from_scores,
)


def _flat_daily(low: float, high: float, n: int) -> list[dict[str, float]]:
    return [{"open": low, "high": high, "low": low, "close": (low + high) / 2} for _ in range(n)]


def test_levels_score_returns_none_when_insufficient_rows():
    rows = _flat_daily(100.0, 110.0, LEVELS_LOOKBACK_DAYS - 1)
    assert levels_score_from_daily_rows(rows, min_spread_frac=0.0) is None


def test_levels_score_flat_three_day_band():
    rows = _flat_daily(100.0, 110.0, LEVELS_LOOKBACK_DAYS)
    out = levels_score_from_daily_rows(rows, min_spread_frac=0.0)
    assert out is not None
    buy_level, sell_level, score = out
    assert buy_level == pytest.approx(100.0 * 1.005)
    assert sell_level == pytest.approx(110.0 * (1 - 0.02))
    assert score >= 0.0


def test_levels_passing_spread_none_when_min_spread_too_large():
    rows = _flat_daily(100.0, 110.0, LEVELS_LOOKBACK_DAYS)
    assert levels_passing_spread(rows, min_spread_frac=0.50) is None


def test_levels_passing_spread_returns_tuple_when_spread_ok():
    rows = _flat_daily(100.0, 120.0, LEVELS_LOOKBACK_DAYS)
    out = levels_passing_spread(rows, min_spread_frac=0.02)
    assert out is not None
    buy, sell = out
    assert sell >= buy * 1.02


def test_build_levels_scored_skips_missing_and_short_series():
    pool = ["AA", "BB"]
    symbol_rows = {
        "AA": _flat_daily(50.0, 55.0, LEVELS_LOOKBACK_DAYS),
        "BB": _flat_daily(1.0, 1.01, LEVELS_LOOKBACK_DAYS - 1),
    }
    scored = build_levels_scored_from_symbol_rows(symbol_rows, pool, min_spread_frac=0.0)
    assert "AA" in scored
    assert "BB" not in scored


def test_select_top_symbols_keeps_positions_and_respects_cap_n():
    levels_scored = {
        "ETH/USD": (100.0, 115.0, 0.50),
        "BTC/USD": (100.0, 105.0, 0.10),
        "SOL/USD": (100.0, 112.0, 0.40),
    }
    positions = {"BTC/USD"}
    selected, levels = select_top_symbols_from_scores(levels_scored, positions, n=2)

    assert selected[0] == "BTC/USD"
    assert len(selected) == 2
    assert set(levels.keys()) == set(selected)


def test_levels_score_penalizes_negative_drift_vs_positive_drift():
    """Twee reeksen met exact dezelfde high/low, maar tegengestelde 3d-drift."""
    rising = [
        {"open": 100.0, "high": 110.0, "low": 100.0, "close": 103.0},
        {"open": 103.0, "high": 110.0, "low": 100.0, "close": 106.0},
        {"open": 106.0, "high": 110.0, "low": 100.0, "close": 109.0},
    ]
    falling = [
        {"open": 109.0, "high": 110.0, "low": 100.0, "close": 106.0},
        {"open": 106.0, "high": 110.0, "low": 100.0, "close": 103.0},
        {"open": 103.0, "high": 110.0, "low": 100.0, "close": 100.0},
    ]
    res_up = levels_score_from_daily_rows(rising, min_spread_frac=0.02)
    res_dn = levels_score_from_daily_rows(falling, min_spread_frac=0.02)
    assert res_up is not None and res_dn is not None
    # Zelfde buy/sell levels, maar de stijgende/herstellende range scoort hoger dan de vrije val
    assert res_up[0] == pytest.approx(res_dn[0])
    assert res_up[1] == pytest.approx(res_dn[1])
    assert res_up[2] > res_dn[2] * 1.4


def test_is_falling_knife_detects_steep_multi_day_crash():
    crash_rows = [
        {"open": 100.0, "high": 101.0, "low": 97.0, "close": 98.0},
        {"open": 98.0, "high": 99.0, "low": 94.0, "close": 95.0},
        {"open": 95.0, "high": 96.0, "low": 91.0, "close": 92.0},
        {"open": 92.0, "high": 93.0, "low": 88.0, "close": 89.0},
        {"open": 89.0, "high": 90.0, "low": 84.0, "close": 85.0},
        {"open": 85.0, "high": 88.0, "low": 78.0, "close": 80.0},
    ]
    assert is_falling_knife(crash_rows) is True
    scored = build_levels_scored_from_symbol_rows(
        {"CRASH/USD": crash_rows}, ["CRASH/USD"], min_spread_frac=0.02
    )
    assert scored["CRASH/USD"][2] == 0.0
    selected, _ = select_top_symbols_from_scores(scored, set(), n=3)
    assert "CRASH/USD" not in selected


def test_select_top_symbols_skips_zero_score_candidates():
    scored = {
        "GOOD/USD": (100.0, 106.0, 0.05),
        "ZERO/USD": (100.0, 101.0, 0.0),
    }
    selected, _ = select_top_symbols_from_scores(scored, set(), n=3)
    assert selected == ["GOOD/USD"]

