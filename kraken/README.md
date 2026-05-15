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

## Backtests (optioneel)

Vroeger aparte `bot_range_1000` / `range_strategy`-shims; niet nodig voor deze entry. Eventueel uit eerdere git commits terugzetten.
