# Position Deadlock Prevention

## Probleem

De Kraken USD range bot kan vastlopen wanneer alle koopslots bezet zijn door onderwater-posities met sell-floors ver boven de markt. Dit gebeurt omdat:

1. De **sell-floor** (minimum winstgevende verkoopprijs) op `entry × 1.009` staat (0.6% fees + 0.3% marge)
2. Bij een -45% verlies staat de sell-limiet nog steeds net boven de entry (bijv. CRV sell $0.3857 vs mid ~$0.184)
3. Posities blijven weken/maanden open zonder exit-mogelijkheid
4. Cash en slots blijven geblokkeerd, nieuwe trades worden onmogelijk

**Voorbeeld uit productie (nov 2026):**
- 4 slots bezet: UNI, ADA, BCH, CRV (allen -40% tot -50%)
- ~$183 USD cash inactief
- Bot draait wel, maar plaatst geen nieuwe orders
- 15+ dagen geen trading-activiteit

## Oplossing: Configureerbare Deadlock-preventie

### 1. **Aged Sell Floor** (Tijdgebaseerde Floor-versoepeling)

Na een instelbare maximale houdtijd wordt de sell-floor geleidelijk verlaagd zodat posities kunnen exiten.

**Configuratie:**

```bash
# Activeer aged floor (aanbevolen: 336 = 14 dagen)
MAX_POSITION_HOLDING_HOURS=336

# Kies vervalmodus:
# - "disabled" (default): feature uit
# - "linear": geleidelijke daling over SELL_FLOOR_DECAY_HOURS
# - "step": directe sprong naar MIN_MULTIPLIER
SELL_FLOOR_DECAY_MODE=linear

# Duur van lineaire verval (default: 168 = 7 dagen na MAX_POSITION_HOLDING_HOURS)
SELL_FLOOR_DECAY_HOURS=168

# Minimale floor-multiplier (default: 0.998 = -0.2% verlies toegestaan)
# - 1.000 = originele floor (break-even + fees)
# - 0.998 = tot -0.2% verlies (conservatief)
# - 0.995 = tot -0.5% verlies
# - 0.990 = tot -1.0% verlies
SELL_FLOOR_MIN_MULTIPLIER=0.998
```

**Werking:**

- **Dag 0-14**: Normale floor ($entry × 1.009)
- **Dag 14-21** (linear mode): Geleidelijke daling naar $entry × 0.998
- **Na dag 21**: Floor blijft op minimum (-0.2% verlies)

**Voorbeeld:** Positie met entry $0.38, marktprijs $0.18 (-53%)
- Zonder aging: sell floor $0.383 (nooit gevuld bij $0.18)
- Na 20 dagen (linear, min=0.998): floor ~$0.3795 (nog steeds boven markt, maar slot kan later vrijkomen)
- Met min=0.990: floor ~$0.376 (grotere kans op exit, maar meer verlies)

### 2. **Hard Stop-Loss** (Vast verliespercentage)

Forceert exit zodra de prijs een vast verliespercentage bereikt, ongeacht houdtijd.

**Configuratie:**

```bash
# Activeer hard stop-loss (default: false)
POSITION_HARD_STOP_LOSS_ENABLED=true

# Stop-loss drempel onder entry (default: -0.15 = -15%)
POSITION_HARD_STOP_LOSS_PCT=-0.15
```

**Werking:**

- Bij entry $100, drempel -15%: forceert taker-exit zodra prijs <$85
- Exit is **onmiddellijk** (taker-order, accepteert verlies)
- Telegram-alert: "🛑 [Kraken] {symbol}: Hard stop-loss @ ${price}"

**⚠️ Let op:**
- Triggert taker-fee (~0.4% i.p.v. 0.3% maker)
- Realiseert direct verlies
- Alleen gebruiken bij extreme dalingen waar herstel onwaarschijnlijk is

### 3. **Combinatie** (Aanbevolen Setup)

Voor optimale deadlock-preventie met beperkte verliezen:

```bash
# Aged floor: 14 dagen wachten, dan 7 dagen geleidelijk verval naar -0.2%
MAX_POSITION_HOLDING_HOURS=336
SELL_FLOOR_DECAY_MODE=linear
SELL_FLOOR_DECAY_HOURS=168
SELL_FLOOR_MIN_MULTIPLIER=0.998

# Hard stop-loss: alleen bij extreme crashes (<-20%)
POSITION_HARD_STOP_LOSS_ENABLED=true
POSITION_HARD_STOP_LOSS_PCT=-0.20
```

**Resultaat:**
- Normale range-trading blijft onveranderd (posities <14 dagen)
- Vastzittende posities krijgen na 14-21 dagen meer exit-mogelijkheden
- Extreme crashes (-20%+) worden direct afgesneden
- Beperkt verlies tot max ~1% per positie (via aged floor) of -20% (via stop-loss)

## Veiligheidskenmerken

1. **Backward compatible**: Zonder configuratie blijft gedrag identiek
2. **Respect voor bestaande limits**: 
   - `KRAKEN_MAX_DEPLOYED_PCT` blijft gehandhaafd
   - `KRAKEN_MAX_POSITION_PCT` blijft gehandhaafd
   - POST_ONLY blijft actief (alleen aged floor gebruikt maker-orders)
3. **Geen state-verandering**: Gebruikt bestaande `opened_at` timestamp in entries
4. **Logging & alerts**: Telegram-berichten bij aged floor en stop-loss activering

## Monitoring & Logging

**Telegram-berichten:**

- **Aged floor actief**: `"AGED sell-floor $X.XX (entry $Y.YY, opened YYYY-MM-DD)"`
- **Hard stop-loss**: `"🛑 [Kraken] {symbol}: Hard stop-loss @ $X.XX (entry $Y.YY)"`

**Logs:**

```
  CRV/USD: AGED sell-floor $0.3795 (entry $0.3800, opened 2026-10-25T14:32:11+00:00), range $0.1840
  UNI/USD: sell-floor $4.2200 (entry $4.1900), range-level $3.8500 → floor actief
```

## Testing

Uitgebreide unit tests in `tests/unit/test_aged_sell_floor.py`:

```bash
pytest tests/unit/test_aged_sell_floor.py -v
pytest tests/unit/test_sell_floor.py -v  # backward compatibility
```

## Risico's & Trade-offs

### Aged Floor
- ✅ Voorkomt permanente deadlock
- ✅ Conservatief instelbaar (min=0.998 = max -0.2% verlies)
- ⚠️ Kan kleine verliezen realiseren om slots vrij te maken
- ⚠️ Exit is niet gegarandeerd (prijs moet nog steeds floor raken)

### Hard Stop-Loss
- ✅ Voorkomt extreme verliezen (crash-bescherming)
- ✅ Maakt slot direct vrij
- ⚠️ Realiseert verlies onmiddellijk
- ⚠️ Taker-fee (~0.4%)
- ⚠️ Geen herstel mogelijk na exit

## Implementatiedetails

- **Module**: `src/rangebot/execution/risk_manager.py`
- **Functies**:
  - `calculate_aged_sell_floor()`: Berekent tijdgebaseerde floor
  - `should_force_exit_position()`: Controleert hard stop-loss
- **Integratie**: `src/rangebot/main.py:386-414` (sell-floor logica)
- **State**: Gebruikt bestaande `opened_at` veld in `data/kraken_state.json`

## Aanbevolen Strategie

**Fase 1 - Monitoring (eerste 2 weken):**
```bash
# Alleen aged floor, zeer conservatief
MAX_POSITION_HOLDING_HOURS=336
SELL_FLOOR_DECAY_MODE=linear
SELL_FLOOR_DECAY_HOURS=168
SELL_FLOOR_MIN_MULTIPLIER=0.999  # max -0.1% verlies
```

**Fase 2 - Actieve preventie (na evaluatie):**
```bash
# Aged floor + stop-loss
MAX_POSITION_HOLDING_HOURS=336
SELL_FLOOR_DECAY_MODE=linear
SELL_FLOOR_DECAY_HOURS=168
SELL_FLOOR_MIN_MULTIPLIER=0.998
POSITION_HARD_STOP_LOSS_ENABLED=true
POSITION_HARD_STOP_LOSS_PCT=-0.20
```

**Fase 3 - Agressieve exit (bij aanhoudende bearmarkt):**
```bash
# Kortere houdtijd, lagere floor
MAX_POSITION_HOLDING_HOURS=240  # 10 dagen
SELL_FLOOR_DECAY_MODE=step
SELL_FLOOR_MIN_MULTIPLIER=0.995  # -0.5% direct
POSITION_HARD_STOP_LOSS_ENABLED=true
POSITION_HARD_STOP_LOSS_PCT=-0.15
```

## Verificatie Health Check

De bestaande `health_check.py` detecteert drawdown >10% en alerteert via Telegram. Met deze fix moeten:

1. Health alerts blijven functioneren (geen code-aanpassing nodig)
2. Drawdown-alerts nu ook daadwerkelijk leiden tot exit-acties (via aged floor)
3. Equity eerder herstellen door vrijgekomen slots te gebruiken

Controleer na implementatie of de health check daadwerkelijk alerteert bij >10% drawdown door `data/kraken_equity.csv` te monitoren.
