# GitHub Actions Schedule Reliability

## Observatie

De trade workflow (`.github/workflows/trade.yml`) is geconfigureerd om **elk uur** te draaien via cron:

```yaml
on:
  schedule:
    - cron: "0 * * * *"  # Elk uur op minuut 0
```

**Verwachting:** 24 runs per dag  
**Werkelijkheid:** ~3-4 runs per dag (observatie week van 15-22 nov 2026)

## Oorzaak: GitHub Actions Schedule Limitations

GitHub Actions scheduled workflows zijn **best-effort** en niet gegarandeerd:

1. **High-load periods**: Runs worden uitgesteld of overgeslagen tijdens drukke tijden
2. **Repository activity**: Inactieve repositories krijgen lagere prioriteit
3. **Queue delays**: Runs kunnen minuten tot uren wachten in de queue
4. **Maximum delay**: GitHub garandeert geen maximum vertraging

**Referentie:** [GitHub Docs - Scheduled Events](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule)

> "Scheduled workflows can be delayed during periods of high load or fail to run entirely. There is no SLA for scheduled workflow runs."

## Impact op de Bot

### Positief
- **Fill-reconciliatie** is robuust: `FILLED_ORDERS_LOOKBACK_HOURS=72` dekt grote gaten
- **State-persistentie** voorkomt dataverlies via cache + committed snapshot
- **Concurrency-lock** voorkomt race conditions bij late/overlappende runs

### Negatief
- **Vertraagde reactie** op marktbewegingen (buy/sell levels kunnen uren verouderd zijn)
- **Missed opportunities** bij snelle range-breaks
- **Health monitoring** (12u-drempel) kan valse alarmen geven
- **Position deadlock** wordt verergerd (minder kans op exit, ook met aged floor)

## Aanbevolen Oplossingen

### 1. **Self-Hosted Runner** (Meest Betrouwbaar)

**Setup:**
```bash
# Op eigen VPS/server met reliable cron
0 * * * * cd /path/to/bot && python3 -m kraken.live_trader
```

**Voordelen:**
- ✅ Gegarandeerde timing (systeemcron is betrouwbaar)
- ✅ Geen queue-delays
- ✅ Geen GitHub Actions-limieten
- ✅ Kan frequentie verhogen (bijv. elk half uur)

**Nadelen:**
- ⚠️ Vereist eigen server/VPS (~$5-10/maand)
- ⚠️ Onderhoud en monitoring
- ⚠️ Secrets-beheer (API keys op server)

**Implementatie:**
```bash
# Op VPS:
git clone <repo>
cd <repo>
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Secrets in .env (niet committen!)
cat > .env << EOF
KRAKEN_API_KEY=...
KRAKEN_API_SECRET=...
KRAKEN_DRY_RUN=false
# ... aged floor settings
EOF

# Crontab
crontab -e
# 0 * * * * cd /path/to/rangebot && /path/to/venv/bin/python -m kraken.live_trader >> /var/log/rangebot.log 2>&1
```

### 2. **External Cron Service** (Betaald, Betrouwbaar)

Services zoals **EasyCron**, **cron-job.org**, of **Cronitor** kunnen GitHub Actions triggers aanroepen:

```yaml
# Voeg workflow_dispatch trigger toe (al aanwezig):
on:
  workflow_dispatch:
  schedule:
    - cron: "0 * * * *"
```

**Setup externe cron:**
```bash
# EasyCron/cron-job.org URL (via GitHub API):
curl -X POST \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token <GITHUB_PAT>" \
  https://api.github.com/repos/<owner>/<repo>/actions/workflows/trade.yml/dispatches \
  -d '{"ref":"main"}'
```

**Voordelen:**
- ✅ Betaalbaar (~$5/maand voor betrouwbare triggers)
- ✅ Geen eigen server nodig
- ✅ Monitoring/alerting ingebouwd

**Nadelen:**
- ⚠️ GitHub Actions queue-delays blijven bestaan (maar triggers zijn op tijd)
- ⚠️ Externe afhankelijkheid

### 3. **Verhoog Schedule-Resolutie** (Workaround)

Verhoog frequentie om gemiste runs te compenseren:

```yaml
schedule:
  - cron: "0,30 * * * *"  # Elk half uur
  # of elke 15 minuten:
  - cron: "0,15,30,45 * * * *"
```

**Voordelen:**
- ✅ Geen extra kosten
- ✅ Eenvoudig

**Nadelen:**
- ⚠️ Lost base-problem niet op (nog steeds best-effort)
- ⚠️ Meer runs = meer Actions-minutes (waarschijnlijk binnen free tier)

### 4. **Cloud Functions** (Serverless)

**AWS Lambda / Google Cloud Functions:**
```python
# Lambda handler (triggered via CloudWatch Events elk uur)
def lambda_handler(event, context):
    # Trigger GitHub Actions
    requests.post(
        "https://api.github.com/repos/<owner>/<repo>/actions/workflows/trade.yml/dispatches",
        headers={"Authorization": f"token {GITHUB_PAT}"},
        json={"ref": "main"}
    )
```

**Voordelen:**
- ✅ Betrouwbare timing (CloudWatch Events)
- ✅ Lage kosten (vaak binnen free tier)
- ✅ Geen server-onderhoud

**Nadelen:**
- ⚠️ Complexere setup
- ⚠️ GitHub Actions queue blijft limitatie

### 5. **Ping-From-Bot** (Zelf-trigger)

Laat de bot zichzelf re-triggeren aan het einde van elke run:

```yaml
# In trade.yml, laatste step:
- name: Schedule next run
  if: success()
  run: |
    # Wacht 55 minuten, trigger dan volgende run
    sleep 3300
    curl -X POST ... (zie #2)
```

**Voordelen:**
- ✅ Garanteert continue runs
- ✅ Geen externe services

**Nadelen:**
- ⚠️ Workflow blijft open (telt tegen concurrent-jobs limiet)
- ⚠️ Falen stopt cascade (geen self-healing)
- ⚠️ Onorthodox gebruik van Actions

## Advies voor deze Bot

**Korte termijn (volgende 1-2 weken):**
1. ✅ **Implementeer aged floor** (deze PR) om impact van gemiste runs te verminderen
2. ✅ **Monitor actual schedule** via `kraken_runs.jsonl` timestamps
3. ⚠️ **Verhoog FILLED_ORDERS_LOOKBACK_HOURS** naar 96 of 120u (voor nog grotere gaten)

**Middellange termijn (binnen 1 maand):**
4. 🔄 **Test external cron service** (bijv. cron-job.org free tier) voor 1-2 weken
5. 📊 **Vergelijk betrouwbaarheid** met GitHub Actions baseline
6. ✅ **Overweeg workflow_dispatch frequency** naar half uur (als Actions blijven)

**Lange termijn (als bot serieus blijft):**
7. 🎯 **Migreer naar self-hosted runner** (VPS met systeemcron)
8. 🎯 **Of overweeg cloud function** (Lambda + CloudWatch) voor betrouwbaarheid
9. 🎯 **Implementeer health monitoring** met externe uptime checks (Uptime Robot, etc.)

## Verificatie

**Check daadwerkelijke run-frequentie:**
```bash
# Parse kraken_runs.jsonl voor timestamp gaps
jq -r '.timestamp' data/kraken_runs.jsonl | \
  awk '{if (NR>1) print ($1-prev)/3600 " hours"; prev=$1}'
```

**Monitor GitHub Actions queue time:**
```bash
# Via GitHub API (vereist PAT):
gh run list --workflow=trade.yml --limit=50 --json databaseId,createdAt,startedAt
```

## Conclusie

GitHub Actions scheduled workflows zijn **niet geschikt voor time-critical trading bots** zonder backup-mechanisme. De aged floor in deze PR vermindert de impact, maar een betrouwbare scheduling-oplossing (self-hosted runner of external cron) is noodzakelijk voor optimale performance.

**Prioriteit:** 🟡 Medium (bot draait, maar gemiste opportunities en vertraagde exits)  
**Effort:** 🟢 Low (self-hosted runner) tot 🟡 Medium (cloud functions)  
**ROI:** 🟢 High (betrouwbaarheid, betere trading-resultaten)
