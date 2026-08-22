# Task 2 Report: Orphan exit voor vastzittende posities (A2)

## Status

**DONE**

## Commits

- `c3767da461513103f5db3acab43232ce25c9dcc9` — `fix: exit orders for held symbols outside spread filter`

## Tests run

```text
$ pytest tests/unit/test_main_orphan_exit.py -v
tests/unit/test_main_orphan_exit.py::test_levels_for_exit_only_ignores_spread_gate PASSED
tests/unit/test_main_orphan_exit.py::test_managed_symbols_include_held_outside_selection PASSED
2 passed in 0.01s

$ pytest -q
50 passed in 0.20s
```

## Changes

- Added `levels_for_exit_only()` in `src/rangebot/strategy/range_strategy.py` — delegates to `levels_score_from_daily_rows(rows, min_spread_frac=0.0)` and returns `(buy, sell)` without spread gate.
- Updated `src/rangebot/main.py`:
  - After symbol selection: `held = symbols_with_balance(...)`, `managed = symbols + orphan held`.
  - Mid prices and positions fetched for `managed` symbols.
  - Main loop iterates `managed`; orphan held symbols outside `levels` get exit levels via `levels_for_exit_only` + existing sell-floor from Task 1.
  - Buy logic gated to `symbol in symbols and symbol in levels` only.
- New tests in `tests/unit/test_main_orphan_exit.py`.

## Self-review notes

- Test assertion adjusted from `sell > buy` to spread-gate bypass check: with current `BUY_ABOVE_LOW_PCT` / `SELL_BELOW_HIGH_PCT`, narrow-range test data yields `sell < buy`; orphan exit only needs the sell side + fee floor.
- Audit snapshot (`positions_final`, `levels_snap`) still keyed to `symbols` (active top-3); orphan symbols processed in-loop but not duplicated in audit `symbols` list — intentional to keep `SYMBOLS_ACTIVE=3` semantics in reporting.
- Existing open buy orders on orphan symbols are not cancelled; only new buys are suppressed.

## Concerns

- Orphan exit may place sells below range buy level when spread is inverted (`sell < buy`); fee floor from Task 1 still protects against sub-cost sells.
- No integration test for full `run_once()` orphan path (would require heavy mocking); unit tests cover helper and managed-list logic only.
