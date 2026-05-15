# Kraken USD range trading bot

Python spot bot: **daily range** op **Kraken** (USD-paren). Strategielogica in `src/rangebot/strategy/`; runtime via `kraken/` en `rangebot.main`.

## Quick start

1. `pip install -e ".[dev]"` (productie: `pip install -e .`).
2. Kopieer `.env.example` → `.env`.
3. `KRAKEN_API_KEY`, `KRAKEN_API_SECRET` (optioneel legacy `KRAKEN_SECRET_KEY`). Standaard **`KRAKEN_DRY_RUN=true`**.
4. Eén run: `python -m kraken.live_trader` of `rangebot` / `python -m rangebot.main`.
5. Continue: `python -m rangebot.live.run_loop` (legacy: `python -m bot_live.run_loop`).
6. Telegram-bot: `rangebot-telegram` of `python -m rangebot.telegram`.
7. Tests / lint: `pytest` · `ruff check src tests`.

## Config & logging

- Parameters: `src/rangebot/config/settings.py`.
- Optioneel: `RANGEBOT_LOG_FORMAT=json`, `RANGEBOT_LOG_LEVEL` — zie `.env.example`.

## Layout (actief)

| Pad | Rol |
|-----|-----|
| `src/rangebot/` | Config, strategie, Kraken, execution, Telegram, journal, `main`, **`live/`** (daemon, dagrapport, cancel-orders) |
| `kraken/` | Entry + `kraken_runtime` |
| `bot_live/` | Dunne **`python -m bot_live.*`-entrypoints** + `config`/`telegram`/`journal`-shims (o.a. voor gearchiveerde scripts) |
| `tests/` | Pytest |
| `scripts/run_bot.py` | Roept `rangebot.main` aan |

## GitHub Actions & secrets

Workflows: `ci.yml` (Ruff + Pytest + optionele Mypy), `trade_kraken.yml`, `daily_report.yml`, `daily_status.yml`.

- **`trade_kraken.yml`** — **elk uur op het hele uur (UTC)** (`cron: 0 * * * *`), zelfde cadans als de vroegere Alpaca hourly trade-workflow. Draait alleen op de **default branch** van de repo.

Onder **Settings → Secrets and variables → Actions** (waarden nooit in logs):

| Secret | Rol |
|--------|-----|
| `KRAKEN_API_KEY` | Kraken API key |
| `KRAKEN_API_SECRET` | Private key |
| `TELEGRAM_BOT_TOKEN` | Optioneel |
| `TELEGRAM_CHAT_ID` | Optioneel |

**Variable:** `KRAKEN_DRY_RUN=false` alleen als scheduled runs **live** orders mogen.

Handmatig: **Actions** → workflow → **Run workflow**.

## Deploy (VPS, kort)

```bash
pip install -e .    # in gekloonde repo
# .env met KRAKEN_* en optioneel Telegram
```

- **Cron (uur):** `0 * * * * cd /pad/na/repo && python3 -m kraken.live_trader >> /var/log/kraken-bot.log 2>&1`
- **Continu:** `nohup python3 -m rangebot.live.run_loop >> /var/log/kraken-bot.log 2>&1 &`

(Zie git history voor oudere uitgebreide deploy-notities.)

## Telegram

Zie `.env.example`: `TELEGRAM_*`, optioneel `TELEGRAM_*_KRAKEN` overrides.

## Journal-exports (optioneel)

Oude export/`run_compare`-hulpscripts zaten in een verwijderde archiefmap; desnoods terugzetten uit eerdere commits via git.
