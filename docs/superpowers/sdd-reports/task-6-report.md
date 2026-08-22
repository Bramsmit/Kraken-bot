# Task 6 Report: POST_ONLY + fee-rate logging (D2)

## Status

**DONE**

## Commits

- `a34607464a0cf77c298637a9c6fff14d58ab1224` — `chore: align KRAKEN_POST_ONLY defaults and log fee rates`

## Tests run

```text
$ pytest -q
56 passed in 0.21s
```

## Changes

- **`.env`** (local only, gitignored)
  - `KRAKEN_POST_ONLY=false` → `KRAKEN_POST_ONLY=true` so local live runs match CI post-only behavior.
- **`.github/workflows/trade.yml`**
  - Added `KRAKEN_POST_ONLY: ${{ vars.KRAKEN_POST_ONLY || 'true' }}` to the `kraken_trade` step env block.
- **`src/rangebot/exchange/kraken/state_and_fills.py`**
  - On each fill, compute `fee_rate = fee_usd / notional` when both are available.
  - Log warning `"Taker-verdacht fee rate …"` when `fee_rate > 0.0035` (taker suspect vs ~0.30% maker).

## Self-review notes

- `.env.example` already had `KRAKEN_POST_ONLY=true`; no change needed.
- `common.py` default remains `"true"` when env unset; CI now sets it explicitly.
- Fee-rate check runs only when `fee_usd is not None` and `notional > 0` to avoid division errors.

## Concerns

- None. Threshold 0.0035 (~0.35%) is slightly above measured maker ~0.30% to reduce false positives.
