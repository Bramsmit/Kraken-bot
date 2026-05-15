# Kraken USD range bot — entry

Spot **USD** range-strategie: dagelijkse candles → gemiddelde low/high, limiet **buy** / **sell**, top-`N` paren uit `SYMBOL_POOL` (`rangebot.config.settings`; `bot_live.config` is nog een dunne shim).

## Setup

Zie root **`README.md`** en **`.env.example`**: `KRAKEN_API_KEY`, `KRAKEN_API_SECRET`, `KRAKEN_DRY_RUN`, optioneel Telegram.

## Runnen

```bash
pip install -e .
python -m kraken.live_trader
```

## Implementatie

- Logica: `rangebot.strategy.range_strategy` + `rangebot.strategy.signals`.
- Exchange: `rangebot.exchange.kraken` (ccxt).
- State: `.kraken_trade_state.json`, `kraken_trades.jsonl`, `kraken_runs.jsonl`.

## Backtests / handoffs (gearchiveerd)

Vroeger: `bot_range_1000/` en `range_strategy/` compat-shim. Die staan nu onder **`_archive_not_kraken_relevant/`**; niet nodig om deze entry te draaien.
