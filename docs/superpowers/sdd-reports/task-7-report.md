# Task 7 Report: Symbol-selectie debug (D3)

## Status

**DONE**

## Commits

- `6ccbaba57a4915959c854512a3a4b6ffcda1c983` — `chore: log symbol selection scores and reject reasons`

## Tests run

```text
$ pytest -q
56 passed in 0.21s

$ KRAKEN_DRY_RUN=true python -m kraken.live_trader
Blocked: ccxt InvalidNonce (EAPI:Invalid nonce) on fetch_balance — environment/API timing, not related to this change.
```

## Changes

- **`src/rangebot/strategy/signals.py`**
  - `select_top_symbols_for_range` now returns a third value: `levels_scored` (`dict[sym → (buy, sell, score)]`).
- **`src/rangebot/main.py`**
  - Added `_log_and_build_selection_debug()` — logs per `kr_pool` symbol whether it is in `levels_scored`, score, spread %, and selection status.
  - Logs appear immediately after symbol selection, before the no-symbols early exit.
  - Run audit payload includes `selection_debug` (also on `no_symbols_selected` events).
- **`src/rangebot/telegram/services/kraken_snapshot.py`**
  - Updated callers to unpack the new third return value.

## Example log output

```text
Symbol-selectie (pool):
  BTC/USD: score=0.0123 spread=2.45%
  ETH/USD: score=0.0098 spread=2.10% (niet geselecteerd)
  AVAX/USD: niet in levels_scored (data/spread)
```

## Self-review notes

- Exposing `levels_scored` from `select_top_symbols_for_range` avoids duplicate market-data fetches in `main.py`.
- Rejected symbols log `(niet geselecteerd)` when scored but outside top-N; missing data/spread uses the brief's reject message.
- Audit `selection_debug` includes `in_levels_scored`, `score`, `spread_pct`, and `selected` per pool symbol.

## Concerns

- Live dry-run smoke test could not complete due to Kraken nonce error in this environment; pytest covers selection helpers and existing main flow mocks are unchanged.
