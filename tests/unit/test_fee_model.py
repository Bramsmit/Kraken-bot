"""Unit tests for Kraken fee model and spread gate thresholds."""

from __future__ import annotations

from rangebot.config.settings import required_min_spread_fraction_crypto_usd


def test_min_spread_at_100_usd_no_fixed_fee() -> None:
    frac = required_min_spread_fraction_crypto_usd(100.0)
    assert frac >= 0.008  # ~0.6% fees + 0.2% buffer + 2% floor


def test_doge_marginal_trade_blocked() -> None:
    capital_per = 37.0
    buy, sell = 0.0910, 0.0911  # ~0.1% spread
    spread_frac = (sell - buy) / buy
    gross = capital_per * spread_frac
    fee = capital_per * 0.006  # percentage-only roundtrip
    assert gross < fee
