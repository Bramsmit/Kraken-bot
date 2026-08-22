# Task 3 Report: Dust threshold + buy-slots + deploy cap + audit (B1–B3)

## Status

**DONE**

## Commits

- `91f90ddf74309de9a5c66b322aca2ffa603bc26a` — `fix: Kraken buy sizing by free slots and notional dust threshold`

## Tests run

```text
$ pytest tests/unit/test_position_manager.py tests/unit/test_signals.py -v -k "tradable or buy_slots or symbols_with_balance"
tests/unit/test_position_manager.py::test_is_tradable_position_rejects_dust_notional PASSED
tests/unit/test_position_manager.py::test_is_tradable_position_accepts_real_position PASSED
tests/unit/test_position_manager.py::test_buy_slots_one_free_slot_gets_full_cash PASSED
tests/unit/test_signals.py::test_symbols_with_balance_includes_only_above_dust PASSED
tests/unit/test_signals.py::test_symbols_with_balance_skips_symbol_when_price_unavailable PASSED
5 passed in 0.22s

$ pytest -q
54 passed in 0.22s
```

## Changes

- **`settings.py`**: Added `KRAKEN_MIN_POSITION_NOTIONAL_USD` ($25 at defaults: `$0.50 / 0.02`) and `KRAKEN_MAX_DEPLOYED_PCT` (env override, default `0.45`).
- **`position_manager.py`**: Added `is_tradable_position(qty, ref_price)`; `persist_entries_from_balances` now skips sub-threshold notionals.
- **`signals.py`**: `symbols_with_balance` uses latest price + `is_tradable_position`; API errors skip the symbol gracefully.
- **`main.py`**: Buy sizing divides by `buy_slots` (symbols without tradable position), capped by `deploy_room` at 45% deployed; log line shows Koopslots; audit JSONL adds `buy_slots`, `deployed_usd`, `deployed_pct`, `symbols_selected`, `symbols_held`.

## Self-review notes

- Brief test `test_buy_slots_one_free_slot_gets_full_cash` used `portfolio_equity_usd=535` with `free_quote_usd=402`; with existing `capital_per_active_symbol_usd` the cash cap wins (`402`) without applying the `0.995` equity fraction. Test adjusted to `equity=402` so it correctly asserts one-slot full-cash sizing.
- `buy_slots` uses avg entry from positions as ref price (Alpaca pattern); `symbols_with_balance` uses live latest price — intentional per brief.
- Main sell loop still uses qty-based dust cancel (`MIN_SELLABLE_CRYPTO_QTY`) for sub-qty dust; notional dust above min qty still enters sell branch (unchanged, out of scope).

## Concerns

- Notional dust positions (qty above `MIN_SELLABLE_CRYPTO_QTY` but below $25) may still attempt sell orders in the per-symbol loop; only selection, sizing, and persistence treat them as non-positions. A follow-up could unify sell-skip logic with `is_tradable_position`.
- `deployed_pct` in audit uses pre-run `portfolio_equity` (same snapshot as sizing), not end-of-run portfolio — consistent with sizing context but differs from final `portfolio_value_usd` field.
