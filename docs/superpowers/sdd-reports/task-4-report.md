# Task 4 Report: Kraken fee model (C)

## Status

**DONE**

## Commits

- `606080342f998dcffefc6b2403e836760c9a851f` — `fix: use measured Kraken maker fees in spread gate`

## Tests run

```text
$ pytest tests/unit/test_fee_model.py -v
tests/unit/test_fee_model.py::test_min_spread_at_100_usd_no_fixed_fee PASSED
tests/unit/test_fee_model.py::test_doge_marginal_trade_blocked PASSED
2 passed in 0.01s

$ pytest -q
56 passed in 0.21s
```

## Changes

- **`src/rangebot/config/settings.py`**
  - Added `KRAKEN_MAKER_FEE_RATE` (default 0.30%), `KRAKEN_TAKER_FEE_RATE` (default 0.40%), `KRAKEN_USE_FIXED_FEE_IN_SPREAD_GATE = False`.
  - `RANGE_CRYPTO_ESTIMATED_MAKER_ROUND_TRIP_PCT` now derived from `KRAKEN_MAKER_FEE_RATE * 2` (0.60% roundtrip).
  - Rewrote `required_min_spread_fraction_crypto_usd()`: percentage-only path returns `max(MIN_SPREAD_PCT, pct + 0.002 extra margin)`; optional fixed-fee path preserved behind flag.
- **`src/rangebot/main.py`**
  - Buy-gate fee estimate uses percentage-only roundtrip unless `KRAKEN_USE_FIXED_FEE_IN_SPREAD_GATE` is enabled.
- **`src/rangebot/exchange/kraken/state_and_fills.py`**
  - Logs `buy_fee unknown (legacy entry)` when selling a position with zero tracked buy fee.
  - `exchange_buy_fee_usd` already forwarded to Telegram on sells (unchanged).
- **`tests/unit/test_fee_model.py`** — new tests per brief.

## Self-review notes

- At $100 ref notional, min spread remains 2% floor (`MIN_SPREAD_PCT`); fee+buffer (0.8%) is below floor — test asserts `>= 0.008`.
- No existing tests required adjustment; higher spread threshold still dominated by 2% floor for typical capital sizes.
- `KRAKEN_MIN_POSITION_NOTIONAL_USD` still uses legacy fixed-fee formula ($25); not in Task 4 scope.

## Concerns

- Live maker tier may change with volume; override via `KRAKEN_MAKER_FEE_RATE` env var.
- Legacy positions without `buy_fee_usd` in state will show $0 buy fee in Telegram PnL until closed; log message aids diagnosis.
- Journal/backtest still use `BITVAVO_*` and `JOURNAL_FIXED_FEE_PER_FILL_USD` — separate from live spread gate.
