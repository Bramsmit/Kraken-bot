# Task 1 Report: Sell-floor onder kostprijs (A1)

## Status

**DONE**

## Commits

- `60e6242abbca3ceabd746aafe48af6d1874c09b0` — `fix: never replace Kraken sell below cost plus fees`

## Tests run

```text
$ pytest tests/unit/test_risk_manager.py tests/unit/test_sell_floor.py -v
tests/unit/test_risk_manager.py::test_stop_price_below_entry PASSED
tests/unit/test_risk_manager.py::test_minimum_profitable_sell_price_above_entry PASSED
tests/unit/test_risk_manager.py::test_minimum_profitable_sell_price_zero_entry PASSED
tests/unit/test_sell_floor.py::test_limit_sell_uses_floor_when_range_level_too_low PASSED
4 passed in 0.01s

$ pytest -q
48 passed in 0.20s
```

## Changes

- Added `minimum_profitable_sell_price()` in `src/rangebot/execution/risk_manager.py`.
- Wired sell floor in `src/rangebot/main.py`: `limit_sell = max(sell_level, fee_floor)` with info log when floor is active.
- Floor protection on existing sells: when `old_sell_price >= fee_floor` and `sell_level < fee_floor`, sell stays unchanged (`needs_new_sell = False`).

## Self-review notes

- Floor protection uses `sell_level < fee_floor` rather than `limit_sell < fee_floor`, because after `max(sell_level, fee_floor)` the latter is always false. Semantics match the brief intent: do not lower a sell that is already at or above the fee floor when the range level drops below it.
- Stale-price and max-age replacement branches still run before floor protection; a very old sell could still be refreshed at the floored price even if that is slightly below the old price (e.g. 4.22 → 4.21). Full “never lower” would require extending protection into those branches or the `needs_new_sell` placement path — out of scope for this minimal fix.
- `RANGE_CRYPTO_ESTIMATED_MAKER_ROUND_TRIP_PCT` was already imported in `main.py`; only `minimum_profitable_sell_price` import was added.

## Concerns

- None blocking. Fee constant still uses legacy `BITVAVO_MAKER_FEE_RATE * 2` until Task 4 updates Kraken-specific rates.
