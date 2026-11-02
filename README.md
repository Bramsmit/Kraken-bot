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

### Belangrijkste strategie- & risicoparameters (nov 2026)

| Parameter | Default | Toelichting |
|-----------|---------|-------------|
| `SYMBOLS_ACTIVE` | `4` | Max. aantal actieve symbolen tegelijk. Bestaande posities behouden hun slot; met 4 slots en max. 20% per positie blijft er bij 3 onderwater-posities nog een 4e koopslot vrij. |
| `KRAKEN_MAX_DEPLOYED_PCT` | `0.65` | Maximaal 65% van de totale portefeuillewaarde (`estimate_portfolio_usd`) in posities; minimaal 35% blijft als USD-cashbuffer staan. |
| `KRAKEN_MAX_POSITION_PCT` | `0.20` | Maximaal 20% van de portefeuillewaarde per individuele kooporder/positie (voorkomt dat één enkel resterend koopslot de volledige `deploy_room` opslokt). |
| `KRAKEN_MAX_BUY_DISTANCE_PCT` | `0.10` | Als de marktprijs >10% boven het `buy_level` staat, wordt de kooporder opgegeven/overgeslagen zodat het slot naar een bereikbaar symbool gaat. |
| `LEVELS_LOOKBACK_DAYS` | `3` | Rolling window (3 dagbars) voor gemiddelde `low` (`+0,5%` buy) en `high` (`-2,0%` sell). |
| `RANGE_DRIFT_SENSITIVITY` | `3.0` | Drift-weging op de range-score (`spread_pct * (1 + range_pct) * max(0.10, 1 + 3 * drift)`): beloont herstellende/vlakke ranges en straft negatieve drift af. |
| `FALLING_KNIFE_DROP_PCT` | `0.08` | Blokkeert nieuwe buys op symbolen die over `FALLING_KNIFE_LOOKBACK_DAYS` (5d) $\ge 8\%$ zijn gecrasht én onder hun gemiddelde slotkoers handelen (`score = 0`). |
| `minimum_profitable_sell_price` | `entry × 1,009` | Sell-floor (`2 × 0,30%` maker-fee + `0,30%` netto marge): verkooporders worden nooit onder kostprijs + fees geplaatst en worden niet onnodig geannuleerd zolang de targetprijs niet $>1\%$ wijzigt. |

## Layout (actief)

| Pad | Rol |
|-----|-----|
| `src/rangebot/` | Config, strategie, Kraken, execution, Telegram, journal, `main`, **`live/`** (daemon, dagrapport, cancel-orders) |
| `kraken/` | Entry + `kraken_runtime` |
| `bot_live/` | Dunne **`python -m bot_live.*`-entrypoints** + `config`/`telegram`/`journal`-shims (o.a. voor gearchiveerde scripts) |
| `tests/` | Pytest |
| `data/` | Persistente trade-log (`kraken_trades.jsonl` / `.csv`) — CI commit na elke run |
| `scripts/run_bot.py` | Roept `rangebot.main` aan |

## GitHub Actions & secrets

Workflows: `ci.yml` (Ruff + Pytest + optionele Mypy), **`trade.yml` (uurlijks)**, `daily_report.yml`, `daily_status.yml`.

- **`trade.yml`** — **elk uur op het hele uur (UTC)** (`cron: 0 * * * *`), dezelfde **bestandsnaam en cadans** als de vroegere Alpaca `trade`-workflow. In de Actions-lijst heet die run **“Hourly — Kraken trade”**. Geplande runs draaien alleen op de **default branch**; zet onder **Settings → Actions → General** workflows aan.

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

## Persistente trade-log

Ephemeral root-bestanden (`kraken_bot_trades.jsonl`, `kraken_trades.jsonl`) zijn gitignored
en worden tussen CI-runs via Actions cache bewaard.

Canonieke log (versioned in git):

```bash
python -m rangebot.live.export_trade_log
```

Schrijft **`data/kraken_trades.jsonl`** + **`.csv`**. De uurlijkse workflow merged en pusht
nieuwe fills automatisch (`chore: trade log … [skip ci]`). Zie [`data/README.md`](data/README.md).
