"""Unit tests for risk_manager (pure helpers)."""

from __future__ import annotations

import pytest

from rangebot.config.settings import STOP_LOSS_PER_UNIT
from rangebot.execution.risk_manager import stop_price_below_entry


def test_stop_price_below_entry() -> None:
    assert stop_price_below_entry(100.0) == pytest.approx(100.0 - STOP_LOSS_PER_UNIT)
