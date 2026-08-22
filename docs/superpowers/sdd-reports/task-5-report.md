# Task 5 Report: Per-symbol notional cap (D1)

## Status

**DONE**

## Commits

- `4957b238a98086f75bf2242c6a63077cbd53f38c` — `feat: optional per-symbol notional cap for Kraken buys`

## Tests run

```text
$ pytest -q
56 passed in 0.21s
```

## Changes

- **`.env.example`**
  - Documented `KRAKEN_MAX_POSITION_VALUE_USD=200` with comment (max notional per symbol; empty = no cap).
- **`src/rangebot/config/settings.py`**
  - Added comment: default unset = no cap (`None`).
- **`src/rangebot/main.py`**
  - Import `KRAKEN_MAX_POSITION_VALUE_USD`.
  - In buy-loop (`needs_new_order`), before `submit_limit_buy`: compute `current_notional = pos_qty * mid`; skip with log when at cap; size orders with `capital_for_order = min(capital_per, cap - current_notional)` when cap set.
  - Spread-gate estimate, qty, and log use `capital_for_order` instead of `capital_per`.

## Self-review notes

- Buy branch only runs when `pos_qty <= 0`, so `current_notional` is typically 0 and the skip path triggers only if a held balance slips through; primary effect is capping single-order notional to `min(capital_per, cap)`.
- Exchange-layer validation in `validation.py` still enforces projected position value on submit (defense in depth).
- No new unit tests in brief; existing suite green.

## Concerns

- Cap does not include pending open buy notional in `current_notional`; validation layer may still reject oversized projected positions if balance + order exceeds cap.
