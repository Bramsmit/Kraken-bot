# Robuuste entry-state en monitoring (8 nov 2026)

## Aanleiding

Review van 8 nov: als de bewaarde instapprijs ontbreekt valt de sell-floor terug op het
huidige buy-level en kan stil 25–35% verlies realiseren. State staat alleen in de
Actions-cache (7 dagen eviction), fill-lookback is 24u terwijl de cron gaten tot ~9,5u
(en soms een dag) heeft. `/pause` werkt niet in CI; heartbeat is een vaste tekst; het
dagrapport herstelt zijn cache nooit.

## Punt 1 — instapprijzen

1. `save_kraken_state` schrijft ook `data/kraken_state.json` (met `updated_at`). Laden
   kiest de nieuwste van cache-bestand en gecommitte snapshot. De trade-workflow commit
   het bestand samen met de trade-log.
2. Entries krijgen `opened_at` (eerste buy van de open positie); behouden bij bijkopen,
   gewist bij volledige verkoop.
3. `persist_entries_from_balances` laat een bekende entry niet meer vallen alleen omdat
   de mid-prijs in deze run ontbreekt.
4. Onbekende entry bij een verkoopbare positie: geen sell plaatsen, waarschuwing loggen
   en Telegram-alert. Geen terugval op `buy_level` meer.
5. `FILLED_ORDERS_LOOKBACK_HOURS` = 72. Dedupe via `notified_trade_ids` in de snapshot.
6. Sell dekt niet de hele vrije hoeveelheid → direct vervangen. Open buys op een symbool
   met verkoopbare positie worden geannuleerd (geen bijkopen).
7. `cancel-in-progress: false` in `trade.yml`.

## Punt 2 — noodknop en monitoring

1. Repository variable `KRAKEN_TRADING_PAUSED=true` → `run_once` doet niets.
2. Elke run voegt een regel toe aan `data/kraken_equity.csv`
   (`timestamp, equity_usd, cash_usd, deployed_pct, positions`).
3. `python -m rangebot.live.health_check` (Daily Status): ⚠️ als laatste run > 12u oud,
   equity > 10% onder piek, of pauze aan; anders ✅ met kerncijfers.
4. Dagrapport leest `data/` (snapshot + equity-CSV): equity nu, Δ24u, Δ vanaf piek,
   cumulatieve fees. Geen cache meer nodig.

## Buiten scope

Alles wat posities verkoopt of sell-targets verlaagt (exit-regel, punt 3) — wordt apart
ontworpen met de lange-termijnstrategie van de eigenaar.
