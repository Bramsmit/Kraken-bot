from rangebot.strategy.range_strategy import (
    levels_for_exit_only,
    levels_passing_spread,
)


def _daily_rows(spread_ok: bool) -> list[dict]:
    low, high = (100.0, 102.0) if spread_ok else (100.0, 100.5)
    return [{"low": low, "high": high}] * 3


def test_levels_for_exit_only_ignores_spread_gate() -> None:
    rows = _daily_rows(spread_ok=False)
    assert levels_passing_spread(rows, min_spread_frac=0.02) is None
    result = levels_for_exit_only(rows)
    assert result is not None
    buy, sell = result
    assert buy > 0 and sell > 0


def test_managed_symbols_include_held_outside_selection() -> None:
    symbols = ["AAVE/USD", "XRP/USD", "CRV/USD"]
    held = {"UNI/USD"}
    managed = list(dict.fromkeys(symbols + [s for s in held if s not in symbols]))
    assert "UNI/USD" in managed
    assert len(managed) == 4
