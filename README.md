# Kraken USD range trading bot

Python spot bot: **daily range** op **Kraken** (USD-paren), gedeelde fee-/spread-modellen met Bitvavo journals waar nuttig.

## Quick start (lokaal)

1. Vanaf de repo-root: `pip install -e ".[dev]"` (alleen runtime: `pip install -e .`).
2. Kopieer `.env.example` → `.env` en vul secrets **niet** in in issue’s, logs of screenshots.
3. **Kraken:** zet `KRAKEN_API_KEY` en `KRAKEN_API_SECRET` in `.env` (legacy: `KRAKEN_SECRET_KEY` wordt nog gelezen als `KRAKEN_API_SECRET` leeg is). Standaard staat **`KRAKEN_DRY_RUN=true`**: de bot verbindt en leest balansen/OHLCV maar **plaatst geen echte limit orders** tenzij je dry-run uitzet. Zet **`KRAKEN_DRY_RUN=false`** alleen als je bewust live wilt. Optioneel: `KRAKEN_MAX_POSITION_VALUE_USD` voor een plafond op de geschatte positiewaarde na een koop (per instrument).
4. Lint/tests (optioneel): `ruff check src tests` en `pytest`.
5. Eén run: `python -m kraken.live_trader` of `rangebot` na install (zie `pyproject.toml` → `project.scripts`).
6. Continue lus: `python -m bot_live.run_loop` (indien je die entry gebruikt).

## Production & configuratie

- **Strategie-parameters** (lookback, buy/sell %-offsets, spread, pool, kapitaal): `src/rangebot/config/settings.py`. **Execution-only** tunables (allocatie-fracties, retry, micro-prijs, stof-drempel) staan daar ook; die zijn bewust gescheiden van de venue-neutrale range-math in `rangebot.strategy.range_strategy`.
- **Logging:** standaard regels naar stdout met timestamp. Voor JSON-lines (b.v. naar een collector): `RANGEBOT_LOG_FORMAT=json`. Optioneel: `RANGEBOT_LOG_LEVEL=DEBUG` of `INFO`.
- **Startup (CLI):** `rangebot.main` laadt bij import: (1) repo-`.env` via `setdefault`, (2) Kraken Telegram env overrides, (3) logging. Daarna `main()` → `run_once()` met retries; zie docstring van `run_once` voor de fasen (pause → pool → **strategie-selectie** → fills → orders → persist).

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Onder andere: `rangebot.strategy.range_strategy` (levels/score), `execution.order_manager`, `execution.risk_manager`, `strategy.signals` (dust/balance), Kraken adapter mocks in `tests/unit/test_kraken_adapter.py`.

## GitHub Actions

- **CI** (`.github/workflows/ci.yml`): bij push/PR — **Ruff**, **Pytest**; een **Mypy**-job draait optioneel en mag falen (`continue-on-error`) tot de types strak staan.
- **Kraken** (`.github/workflows/trade_kraken.yml`): gepland elk uur + **handmatig** via *Run workflow*. Vereiste **repository secrets** (nooit in logs tonen):
  - `KRAKEN_API_KEY`
  - `KRAKEN_API_SECRET`  
    Als je eerder `KRAKEN_SECRET_KEY` als secret-naam gebruikte: maak een nieuwe secret `KRAKEN_API_SECRET` met dezelfde waarde en verwijder de oude naam wanneer niets die meer gebruikt.
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (optioneel, voor notificaties)
- **Repository variable** `KRAKEN_DRY_RUN`: zet op `false` als scheduled runs echte orders mogen zetten; leeg of `true` = dry-run (veilige default, gelijk aan lokaal).
- **Overige workflows:** `daily_report.yml` / `daily_status.yml` (Kraken-gerelateerde rapportage/heartbeat); Bitvavo-workflows gebruiken eigen `BITVAVO_*` / `BITVAVO_TELEGRAM_*` secrets — zie de betreffende YAML.

Handmatig testen: **Actions** → kies workflow → **Run workflow**.

## Layout

| Pad | Rol |
|-----|-----|
| `src/rangebot/` | Pakket: config, strategy, Kraken exchange, execution, Telegram, journal |
| `range_strategy/` | Compat-shim richting `rangebot.strategy.range_strategy` (backtests/metrics) |
| `kraken/` | Dunne entry + `kraken_runtime`-compat naar `rangebot` |
| `bot_live/` | Telegram-legacy, Bitvavo (EUR), `run_loop`, gedeelde audits |
| `bot_range_1000/` | Backtests, `export_handoff` |
| `metrics/` | Exports, run_compare (Kraken vs Bitvavo audits) |
| `tests/unit`, `tests/integration` | Pytest |

## Exchange-laag

- Strategie (`rangebot.strategy.range_strategy`) rekent alleen levels en selectie; het kent geen venue.
- Signaalbouw (`rangebot.strategy.signals`) haalt OHLCV/balansen op via `ExchangeClient`.
- Uitvoering (`rangebot.execution.order_manager`) zet bedoelingen om in `place_order` / `cancel_order` op die client.
- Kraken gebruikt `rangebot.exchange.kraken` (`KrakenExchangeClient`): marktdata, balansen en orders zijn gescheiden; API-calls gebruiken ccxt met rate-limit en retries op tijdelijke fouten. Pre-trade checks (pair, min/max size, saldo, optioneel max. positie, geen tweede open limit dezelfde kant) draaien vóór een live order.

## Telegram

- **Push (geplande runner / trade-fills):** zet `TELEGRAM_BOT_TOKEN` en `TELEGRAM_CHAT_ID` in `.env`. Optioneel: `TELEGRAM_BOT_TOKEN_KRAKEN` / `TELEGRAM_CHAT_ID_KRAKEN` (overschrijven de generieke variabelen voor deze bot). Er worden geen volledige API keys of secrets in Telegram-teksten gezet.
- **Commando-bot (slash commands):** start na install bv. `rangebot-telegram` of `python -m rangebot.telegram`. De poller beantwoordt alleen het geconfigureerde chat id. Commando’s: `/status`, `/positions`, `/orders`, `/balance`, `/dryrun`, `/pause`, `/resume` (plus `/help`). Pauze slaat geplande **rangebot** `run_once`-runs over (bestand `.kraken_bot_control.json` in de repo-root, lokaal).
- **Bitvavo / andere scripts** blijven `bot_live.telegram` kunnen importeren (shim naar `rangebot.telegram.bot`).

Zie `kraken/README.md` en `SETUP_GUIDE.md` voor details.
