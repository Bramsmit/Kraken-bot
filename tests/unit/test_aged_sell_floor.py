"""Unit tests for aged sell floor and hard stop-loss (position deadlock prevention)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from rangebot.execution.risk_manager import (
    calculate_aged_sell_floor,
    should_force_exit_position,
)


def _iso_hours_ago(hours: float) -> str:
    """Helper: ISO timestamp N uren geleden."""
    dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    return dt.isoformat()


def test_aged_floor_disabled_by_default() -> None:
    """Zonder max_holding_hours blijft floor constant."""
    entry = 100.0
    floor, is_aged = calculate_aged_sell_floor(
        entry,
        maker_round_trip_pct=0.006,
        opened_at_iso=_iso_hours_ago(500),  # 500 uur oud
        max_holding_hours=None,
        decay_mode="linear",
    )
    
    assert not is_aged
    assert floor == pytest.approx(100.9)  # 100 × 1.009


def test_aged_floor_step_mode_after_holding_period() -> None:
    """Step-mode: directe sprong naar min_multiplier na max_holding_hours."""
    entry = 100.0
    
    # Voor de drempel: normale floor
    floor_before, aged_before = calculate_aged_sell_floor(
        entry,
        maker_round_trip_pct=0.006,
        opened_at_iso=_iso_hours_ago(300),
        max_holding_hours=336,
        decay_mode="step",
        min_multiplier=0.995,
    )
    assert not aged_before
    assert floor_before == pytest.approx(100.9)
    
    # Net na de drempel: directe sprong
    floor_after, aged_after = calculate_aged_sell_floor(
        entry,
        maker_round_trip_pct=0.006,
        opened_at_iso=_iso_hours_ago(340),
        max_holding_hours=336,
        decay_mode="step",
        min_multiplier=0.995,
    )
    assert aged_after
    assert floor_after == pytest.approx(99.5)  # 100 × 0.995


def test_aged_floor_linear_mode_gradual_decay() -> None:
    """Linear-mode: geleidelijke daling van floor over decay_hours."""
    entry = 100.0
    base_mult = 1.009  # 1 + 0.006 + 0.003
    min_mult = 0.995
    
    # T=0 (336u): start verval
    floor_start, aged_start = calculate_aged_sell_floor(
        entry,
        maker_round_trip_pct=0.006,
        opened_at_iso=_iso_hours_ago(336),
        max_holding_hours=336,
        decay_mode="linear",
        decay_hours=168,
        min_multiplier=0.995,
    )
    assert aged_start
    assert floor_start == pytest.approx(100.9, abs=0.1)  # nog bij base
    
    # T=84u in verval (336+84): 50% van 168u verval
    floor_mid, aged_mid = calculate_aged_sell_floor(
        entry,
        maker_round_trip_pct=0.006,
        opened_at_iso=_iso_hours_ago(336 + 84),
        max_holding_hours=336,
        decay_mode="linear",
        decay_hours=168,
        min_multiplier=0.995,
    )
    assert aged_mid
    expected_mid = entry * (base_mult + 0.5 * (min_mult - base_mult))
    assert floor_mid == pytest.approx(expected_mid, abs=0.1)
    
    # T=168u+ in verval: volledig naar min
    floor_end, aged_end = calculate_aged_sell_floor(
        entry,
        maker_round_trip_pct=0.006,
        opened_at_iso=_iso_hours_ago(336 + 200),
        max_holding_hours=336,
        decay_mode="linear",
        decay_hours=168,
        min_multiplier=0.995,
    )
    assert aged_end
    assert floor_end == pytest.approx(99.5)


def test_aged_floor_respects_disabled_mode() -> None:
    """decay_mode="disabled" schakelt aging uit, zelfs met max_holding_hours."""
    floor, is_aged = calculate_aged_sell_floor(
        100.0,
        maker_round_trip_pct=0.006,
        opened_at_iso=_iso_hours_ago(1000),
        max_holding_hours=336,
        decay_mode="disabled",
    )
    
    assert not is_aged
    assert floor == pytest.approx(100.9)


def test_aged_floor_handles_missing_opened_at() -> None:
    """Zonder opened_at blijft floor op basis-niveau (geen aging)."""
    floor, is_aged = calculate_aged_sell_floor(
        100.0,
        maker_round_trip_pct=0.006,
        opened_at_iso=None,
        max_holding_hours=336,
        decay_mode="step",
        min_multiplier=0.995,
    )
    
    assert not is_aged
    assert floor == pytest.approx(100.9)


def test_hard_stop_loss_disabled_by_default() -> None:
    """Zonder enabled geen force-exit."""
    assert not should_force_exit_position(
        current_price=50.0,
        entry=100.0,
        enabled=False,
    )


def test_hard_stop_loss_triggers_below_threshold() -> None:
    """Hard stop-loss activeert als prijs onder entry × (1 + stop_loss_pct)."""
    entry = 100.0
    # Drempel: 100 × (1 + -0.15) = 85.0
    
    # Net boven drempel: geen exit
    assert not should_force_exit_position(85.1, entry, enabled=True, stop_loss_pct=-0.15)
    
    # Op drempel: nog geen exit (< strict)
    assert not should_force_exit_position(85.0, entry, enabled=True, stop_loss_pct=-0.15)
    
    # Onder drempel: force exit
    assert should_force_exit_position(84.9, entry, enabled=True, stop_loss_pct=-0.15)
    assert should_force_exit_position(50.0, entry, enabled=True, stop_loss_pct=-0.15)


def test_hard_stop_loss_handles_missing_price() -> None:
    """Zonder current_price geen force-exit (veilig gedrag)."""
    assert not should_force_exit_position(None, 100.0, enabled=True, stop_loss_pct=-0.15)
    assert not should_force_exit_position(0.0, 100.0, enabled=True, stop_loss_pct=-0.15)


def test_aged_floor_clamps_to_zero_if_min_multiplier_negative() -> None:
    """min_multiplier <0 wordt geklemd naar 0 (veiligheidscheck)."""
    floor, is_aged = calculate_aged_sell_floor(
        100.0,
        maker_round_trip_pct=0.006,
        opened_at_iso=_iso_hours_ago(400),
        max_holding_hours=336,
        decay_mode="step",
        min_multiplier=-0.5,
    )
    
    assert is_aged
    assert floor == pytest.approx(0.0)


def test_aged_floor_integration_scenario() -> None:
    """
    Realistisch scenario: positie 20 dagen oud, linear decay van 14-21 dagen.
    
    Entry $0.38, huidige prijs $0.18 (-53%). Zonder aging zou floor ~$0.383 zijn.
    Na 20 dagen (336+144u) is 6 dagen in 7-daagse decay = 85% verval.
    Floor moet richting $0.38 × 0.998 = $0.379 bewegen.
    """
    entry = 0.38
    # 20 dagen = 480u = 336 + 144 (144/168 = ~86% van decay)
    floor, is_aged = calculate_aged_sell_floor(
        entry,
        maker_round_trip_pct=0.006,
        opened_at_iso=_iso_hours_ago(480),
        max_holding_hours=336,
        decay_mode="linear",
        decay_hours=168,
        min_multiplier=0.998,
    )
    
    assert is_aged
    # Base: 0.38 × 1.009 = 0.38342
    # Min: 0.38 × 0.998 = 0.37924
    # Progress 86%: 0.38342 + 0.86 × (0.37924 - 0.38342) ≈ 0.3798
    assert 0.379 <= floor <= 0.381
