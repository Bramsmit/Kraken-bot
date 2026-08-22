# data/

Persistente trade-logs voor de Kraken live-bot. CI merged werkjournals na elke
uurlijkse run en commit terug naar deze map (zoals Alpaca `data/alpaca_trades.*`).

| Bestand | Inhoud |
|---|---|
| `kraken_trades.jsonl` | Alle gevulde trades (JSONL, deduped op `trade_id`) |
| `kraken_trades.csv` | Zelfde data als CSV |

## Kolommen

| Kolom | Uitleg |
|---|---|
| `timestamp` | Fill-tijd (UTC ISO-8601), bij voorkeur exchange-tijd |
| `trade_id` | Stabiele Kraken/ccxt trade-id (dedupe-sleutel) |
| `symbol` | Handelspaar, bijv. `UNI/USD` |
| `side` | `buy` of `sell` |
| `qty` | Gevulde hoeveelheid |
| `price` | Vulprijs |
| `fee_usd` | Exchange-fee in USD (indien bekend) |
| `notional_usd` | qty × price |
| `entry_price` | Gemiddelde inkoop (sells, indien bekend) |
| `profit_usd` | Netto PnL schatting (sells, indien bekend) |
| `portfolio_value_usd` | Portfolio-schatting op moment van log |
| `source` | Herkomstbestand (`kraken_bot_trades.jsonl`, API-pull, …) |

## Commando

```bash
python -m rangebot.live.export_trade_log
python -m rangebot.live.export_trade_log --source /pad/naar/extra.jsonl
```

Ephemeral bestanden in de repo-root (`kraken_bot_trades.jsonl`, `kraken_trades.jsonl`)
blijven gitignored; alleen `data/` is de canonieke, versioned log.
