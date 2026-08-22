# Kraken Range-Bot Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop live Kraken losses from sells below cost, unlock idle capital, and align fee/sizing models with measured Kraken maker costs — without increasing `SYMBOLS_ACTIVE` beyond 3.

**Architecture:** Pure helpers in `risk_manager.py` and `position_manager.py`; orchestration changes in `main.py`; selection/dust in `signals.py`; Kraken-specific fee constants in `settings.py`. Each phase is independently testable and committable. Reference implementation patterns live in `MCP-alpaca v1 1000 eu/alpaca_bot/live_trader.py` (`is_tradable_position`, `buy_slots`).

**Tech Stack:** Python 3.11+, pytest, Kraken REST via `rangebot.exchange.kraken`, GitHub Actions hourly cron.

## Global Constraints

- `SYMBOLS_ACTIVE` blijft **3** (niet verhogen naar 5)
- `KRAKEN_MAX_DEPLOYED_PCT` default **0.45** (niet Alpaca's 0.60)
- Alle wijzigingen met **pytest**-tests; `pytest -q` groen na elke commit
- Eerst testen met `KRAKEN_DRY_RUN=true`; live pas na expliciet `KRAKEN_DRY_RUN=false`
- Geen Alpaca 5-slot / 60%-deploy 1-op-1 kopiëren
- Commit-volgorde: A1 → A2 → B → C → D1 → D2 → D3 (7 commits)

---

### Task 1: Sell-floor onder kostprijs (A1)

**Files:**
- Modify: `src/rangebot/execution/risk_manager.py`
- Modify: `src/rangebot/main.py:219-314` (sell-tak)
- Modify: `tests/unit/test_risk_manager.py`
- Create: `tests/unit/test_sell_floor.py`

**Interfaces:**
- Consumes: `RANGE_CRYPTO_ESTIMATED_MAKER_ROUND_TRIP_PCT` from `settings.py` (Task 4 updates value; Task 1 uses existing import path)
- Produces: `minimum_profitable_sell_price(entry, *, maker_round_trip_pct, min_margin_pct=0.003) -> float`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_risk_manager.py — add:

from rangebot.execution.risk_manager import minimum_profitable_sell_price


def test_minimum_profitable_sell_price_above_entry() -> None:
    floor = minimum_profitable_sell_price(4.19, maker_round_trip_pct=0.006)
    assert floor > 4.19
    assert floor == pytest.approx(4.19 * (1 + 0.006 + 0.003))


def test_minimum_profitable_sell_price_zero_entry() -> None:
    assert minimum_profitable_sell_price(0.0, maker_round_trip_pct=0.006) == 0.0
```

```python
# tests/unit/test_sell_floor.py — new file:

from rangebot.execution.risk_manager import minimum_profitable_sell_price


def test_limit_sell_uses_floor_when_range_level_too_low() -> None:
    entry = 4.19
    sell_level = 4.07  # dalende markt, onder entry
    fee_floor = minimum_profitable_sell_price(entry, maker_round_trip_pct=0.006)
    limit_sell = max(sell_level, fee_floor)
    assert limit_sell == fee_floor
    assert limit_sell > entry
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_risk_manager.py tests/unit/test_sell_floor.py -v`
Expected: FAIL — `ImportError: cannot import name 'minimum_profitable_sell_price'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/rangebot/execution/risk_manager.py — add after stop_price_below_entry:

def minimum_profitable_sell_price(
    entry: float,
    *,
    maker_round_trip_pct: float,
    min_margin_pct: float = 0.003,
) -> float:
    """Minimale verkoopprijs: entry + roundtrip maker-fees + kleine marge."""
    if entry <= 0:
        return 0.0
    return entry * (1 + maker_round_trip_pct + min_margin_pct)
```

```python
# src/rangebot/main.py — in sell-tak (~regel 229), replace limit_sell = sell_level:

from rangebot.config.settings import RANGE_CRYPTO_ESTIMATED_MAKER_ROUND_TRIP_PCT
from rangebot.execution.risk_manager import minimum_profitable_sell_price

# ... inside pos_qty > 0 block:
fee_floor = minimum_profitable_sell_price(
    entry,
    maker_round_trip_pct=RANGE_CRYPTO_ESTIMATED_MAKER_ROUND_TRIP_PCT,
)
limit_sell = max(sell_level, fee_floor)
if limit_sell > sell_level:
    log.info(
        "  %s: sell-floor $%.4f (entry $%.4f), range-level $%.4f → floor actief",
        symbol,
        limit_sell,
        entry,
        sell_level,
    )
```

```python
# main.py — in existing_sell update logic, before price_diff check:
# Als oude sell >= fee_floor en nieuw level < fee_floor → niet verlagen
if (
    existing_sell
    and old_sell_price >= fee_floor
    and limit_sell < fee_floor
):
    log.info(
        "  %s: Sell ongewijzigd @ $%.4f (floor beschermt tegen verlaging)",
        symbol,
        old_sell_price,
    )
    stats["unchanged"] += 1
    needs_new_sell = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_risk_manager.py tests/unit/test_sell_floor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/rangebot/execution/risk_manager.py src/rangebot/main.py tests/unit/test_risk_manager.py tests/unit/test_sell_floor.py
git commit -m "$(cat <<'EOF'
fix: never replace Kraken sell below cost plus fees

EOF
)"
```

---

### Task 2: Orphan exit voor vastzittende posities (A2)

**Files:**
- Modify: `src/rangebot/main.py:131-192` (managed loop)
- Modify: `src/rangebot/strategy/range_strategy.py` (add `levels_for_exit_only`)
- Modify: `tests/unit/test_signals.py` or create `tests/unit/test_main_orphan_exit.py`

**Interfaces:**
- Consumes: `symbols_with_balance()`, `minimum_profitable_sell_price()` (Task 1)
- Produces: `levels_for_exit_only(rows: list[dict]) -> tuple[float, float] | None`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_main_orphan_exit.py — new file:

from unittest.mock import MagicMock

from rangebot.strategy.range_strategy import levels_for_exit_only


def _daily_rows(spread_ok: bool) -> list[dict]:
    low, high = (100.0, 102.0) if spread_ok else (100.0, 100.5)
    return [{"low": low, "high": high}] * 3


def test_levels_for_exit_only_ignores_spread_gate() -> None:
    rows = _daily_rows(spread_ok=False)
    result = levels_for_exit_only(rows)
    assert result is not None
    buy, sell = result
    assert sell > buy


def test_managed_symbols_include_held_outside_selection() -> None:
    symbols = ["AAVE/USD", "XRP/USD", "CRV/USD"]
    held = {"UNI/USD"}
    managed = list(dict.fromkeys(symbols + [s for s in held if s not in symbols]))
    assert "UNI/USD" in managed
    assert len(managed) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main_orphan_exit.py -v`
Expected: FAIL — `ImportError: cannot import name 'levels_for_exit_only'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/rangebot/strategy/range_strategy.py — add:

def levels_for_exit_only(rows: list[dict]) -> tuple[float, float] | None:
    """Bereken buy/sell levels zonder spread-gate (alleen voor orphan exit)."""
    t = levels_score_from_daily_rows(rows, min_spread_frac=0.0)
    if t is None:
        return None
    return t[0], t[1]
```

```python
# src/rangebot/main.py — after select_top_symbols_for_range:

from rangebot.strategy.signals import symbols_with_balance
from rangebot.strategy.range_strategy import levels_for_exit_only
from rangebot.data.market_data import fetch_symbol_rows_for_pool

held = symbols_with_balance(client, kr_pool)
managed = list(dict.fromkeys(symbols + [s for s in held if s not in symbols]))

# Replace loop: for symbol in symbols → for symbol in managed
# Inside loop, when symbol not in levels:
if symbol not in levels:
    if symbol in held:
        rows_map = fetch_symbol_rows_for_pool(client, [symbol])
        rows = rows_map.get(symbol)
        exit_lv = levels_for_exit_only(rows) if rows else None
        if exit_lv:
            buy_level, sell_level = exit_lv
            log.info("  %s: orphan exit mode (buiten spread-filter)", symbol)
        else:
            continue  # geen data
    else:
        continue  # geen positie, geen levels → skip
else:
    buy_level, sell_level = levels[symbol]

# Orphan-symbolen: alleen sell-tak, geen buy-tak (wrap buy-logic in: if symbol in symbols and symbol in levels)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main_orphan_exit.py -q && pytest -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/rangebot/main.py src/rangebot/strategy/range_strategy.py tests/unit/test_main_orphan_exit.py
git commit -m "$(cat <<'EOF'
fix: exit orders for held symbols outside spread filter

EOF
)"
```

---

### Task 3: Dust-drempel + buy-slots + deploy cap + audit (B1–B3)

**Files:**
- Modify: `src/rangebot/config/settings.py`
- Modify: `src/rangebot/execution/position_manager.py`
- Modify: `src/rangebot/strategy/signals.py`
- Modify: `src/rangebot/main.py:160-183,588-606`
- Modify: `tests/unit/test_position_manager.py`, `tests/unit/test_signals.py`

**Interfaces:**
- Consumes: `RANGE_CRYPTO_ROUND_TRIP_FIXED_USD`, `MIN_SPREAD_PCT` from settings
- Produces: `is_tradable_position(qty, ref_price) -> bool`, `KRAKEN_MIN_POSITION_NOTIONAL_USD`, `KRAKEN_MAX_DEPLOYED_PCT`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_position_manager.py — add:

from rangebot.execution.position_manager import is_tradable_position


def test_is_tradable_position_rejects_dust_notional() -> None:
    assert is_tradable_position(0.106, 1.50) is False  # ~$0.16


def test_is_tradable_position_accepts_real_position() -> None:
    assert is_tradable_position(1.0, 30.0) is True


def test_buy_slots_one_free_slot_gets_full_cash() -> None:
    c = capital_per_active_symbol_usd(
        portfolio_equity_usd=535.0,
        free_quote_usd=402.0,
        n_symbols=1,  # buy_slots=1
    )
    assert c == pytest.approx(402.0 / 1 * 0.995)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_position_manager.py -v -k "tradable or buy_slots"`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# src/rangebot/config/settings.py — add:

KRAKEN_MIN_POSITION_NOTIONAL_USD = (
    RANGE_CRYPTO_ROUND_TRIP_FIXED_USD / MIN_SPREAD_PCT
)  # $25 bij defaults

KRAKEN_MAX_DEPLOYED_PCT = float(
    _os_kraken_adapter.environ.get("KRAKEN_MAX_DEPLOYED_PCT", "0.45")
)
```

```python
# src/rangebot/execution/position_manager.py — add:

from rangebot.config.settings import KRAKEN_MIN_POSITION_NOTIONAL_USD

def is_tradable_position(qty: float, ref_price: float) -> bool:
    if qty <= 0 or Decimal(str(qty)) < MIN_SELLABLE_CRYPTO_QTY:
        return False
    return qty * float(ref_price or 0) >= KRAKEN_MIN_POSITION_NOTIONAL_USD
```

```python
# src/rangebot/strategy/signals.py — update symbols_with_balance:
# Gebruik entry/mid price via client.get_latest_price(sym) of avg from positions
# Voor nu: latest price als ref_price in is_tradable_position check
```

```python
# src/rangebot/main.py — replace n_symbols=len(symbols):

buy_slots = sum(
    1
    for sym in symbols
    if not is_tradable_position(*positions.get(sym, (0.0, 0.0)))
)
deployed = max(0.0, portfolio_equity - free_usd)
deploy_room = max(0.0, portfolio_equity * KRAKEN_MAX_DEPLOYED_PCT - deployed)
capital_per = capital_per_active_symbol_usd(
    portfolio_equity_usd=portfolio_equity,
    free_quote_usd=free_usd,
    n_symbols=max(1, buy_slots),
)
capital_per = min(capital_per, deploy_room / max(1, buy_slots))

log.info(
    "Portfolio ~ $%.2f | Vrije USD $%.2f | Koopslots: %d van %d | Per slot $%.2f",
    portfolio_equity, free_usd, buy_slots, len(symbols), capital_per,
)
```

```python
# main.py log_run_audit — add fields:
"buy_slots": buy_slots,
"deployed_usd": round(deployed, 4),
"deployed_pct": round(deployed / portfolio_equity, 4) if portfolio_equity else 0,
"symbols_selected": list(symbols),
"symbols_held": sorted(held),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q`
Expected: PASS (45+ tests)

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
fix: Kraken buy sizing by free slots and notional dust threshold

EOF
)"
```

---

### Task 4: Kraken fee-model (C)

**Files:**
- Modify: `src/rangebot/config/settings.py:46-98`
- Modify: `src/rangebot/main.py:486-491` (buy-gate)
- Modify: `src/rangebot/exchange/kraken/state_and_fills.py` (fee logging)
- Create: `tests/unit/test_fee_model.py`

**Interfaces:**
- Produces: `KRAKEN_MAKER_FEE_RATE`, `KRAKEN_USE_FIXED_FEE_IN_SPREAD_GATE`, updated `required_min_spread_fraction_crypto_usd()`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_fee_model.py:

from rangebot.config.settings import required_min_spread_fraction_crypto_usd


def test_min_spread_at_100_usd_no_fixed_fee() -> None:
    frac = required_min_spread_fraction_crypto_usd(100.0)
    assert frac >= 0.008  # ~0.6% fees + 0.2% buffer + 2% floor


def test_doge_marginal_trade_blocked() -> None:
    capital_per = 37.0
    buy, sell = 0.0910, 0.0911  # ~0.1% spread
    spread_frac = (sell - buy) / buy
    gross = capital_per * spread_frac
    fee = capital_per * 0.006  # percentage-only roundtrip
    assert gross < fee
```

- [ ] **Step 2–4: Implement, verify**

```python
# settings.py:
KRAKEN_MAKER_FEE_RATE = float(os.environ.get("KRAKEN_MAKER_FEE_RATE", "0.0030"))
KRAKEN_TAKER_FEE_RATE = float(os.environ.get("KRAKEN_TAKER_FEE_RATE", "0.0040"))
KRAKEN_USE_FIXED_FEE_IN_SPREAD_GATE = False
RANGE_CRYPTO_ESTIMATED_MAKER_ROUND_TRIP_PCT = KRAKEN_MAKER_FEE_RATE * 2

def required_min_spread_fraction_crypto_usd(ref_notional_usd: float) -> float:
    ref = max(RANGE_MIN_ORDER_REF_USD, float(ref_notional_usd or 0))
    pct = KRAKEN_MAKER_FEE_RATE * 2
    extra_margin = 0.002
    if KRAKEN_USE_FIXED_FEE_IN_SPREAD_GATE:
        fixed = RANGE_CRYPTO_ROUND_TRIP_FIXED_USD / ref
        return max(MIN_SPREAD_PCT, fixed) + pct + extra_margin
    return max(MIN_SPREAD_PCT, pct + extra_margin)
```

```python
# main.py buy-gate — replace fee_usd_est:
fee_usd_est = capital_per * RANGE_CRYPTO_ESTIMATED_MAKER_ROUND_TRIP_PCT
if KRAKEN_USE_FIXED_FEE_IN_SPREAD_GATE:
    fee_usd_est += RANGE_CRYPTO_ROUND_TRIP_FIXED_USD
```

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
fix: use measured Kraken maker fees in spread gate

EOF
)"
```

---

### Task 5: Positie-cap per symbool (D1)

**Files:**
- Modify: `src/rangebot/main.py` (buy-loop vóór submit)
- Modify: `.env.example`

- [ ] **Step 1–4: Implement cap check**

```python
# main.py buy-loop, vóór submit_limit_buy:
from rangebot.config.settings import KRAKEN_MAX_POSITION_VALUE_USD

mid = mid_prices.get(symbol) or buy_level
current_notional = pos_qty * mid
cap = KRAKEN_MAX_POSITION_VALUE_USD
if cap and current_notional >= cap:
    log.info("  %s: positie-cap ($%.2f >= $%.2f), geen buy", symbol, current_notional, cap)
    stats["skipped"] += 1
    continue
capital_for_order = min(capital_per, (cap - current_notional)) if cap else capital_per
```

```env
# .env.example:
KRAKEN_MAX_POSITION_VALUE_USD=200
```

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: optional per-symbol notional cap for Kraken buys

EOF
)"
```

---

### Task 6: POST_ONLY + fee-rate logging (D2)

**Files:**
- Modify: `.env` (lokaal: `KRAKEN_POST_ONLY=true`)
- Modify: `.github/workflows/trade.yml` (optioneel env var)
- Modify: `src/rangebot/exchange/kraken/state_and_fills.py`

- [ ] **Step 1: Align POST_ONLY**

```env
# .env — change:
KRAKEN_POST_ONLY=true
```

```yaml
# trade.yml env block:
KRAKEN_POST_ONLY: ${{ vars.KRAKEN_POST_ONLY || 'true' }}
```

- [ ] **Step 2: Log fee_rate on fills**

```python
# state_and_fills.py — bij fill processing:
fee_rate = fee_usd / notional if notional > 0 else 0
if fee_rate > 0.0035:
    log.warning("Taker-verdacht fee rate %.4f on %s", fee_rate, symbol)
```

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
chore: align KRAKEN_POST_ONLY defaults and log fee rates

EOF
)"
```

---

### Task 7: Symbol-selectie debug (D3)

**Files:**
- Modify: `src/rangebot/main.py` (na select_top_symbols_for_range)

- [ ] **Step 1: Add selection debug logging**

```python
# main.py — after building levels_scored (may need to expose from signals or rebuild):
for sym in kr_pool:
    if sym not in levels_scored:
        log.info("  %s: niet in levels_scored (data/spread)", sym)
    else:
        buy, sell, score = levels_scored[sym]
        log.info("  %s: score=%.4f spread=%.2f%%", sym, score, (sell / buy - 1) * 100)
```

Optioneel audit field: `"selection_debug": {sym: {"score": ..., "spread_pct": ...}}`

- [ ] **Step 2: Commit + final verification**

```bash
git commit -m "$(cat <<'EOF'
chore: log symbol selection scores and reject reasons

EOF
)"
pytest -q
KRAKEN_DRY_RUN=true python -m kraken.live_trader
```

---

## Verificatie na implementatie

```bash
cd "Kraken bot 500 eu 15 mei"
pip install -e ".[dev]"
pytest -q
KRAKEN_DRY_RUN=true python -m kraken.live_trader
```

Live checklist (na `KRAKEN_DRY_RUN=false` in GitHub vars):
- Geen sell-replace onder avg entry
- Restposities <$25 geen sell/slot
- Orphan-symbolen krijgen exit-order
- Run-log: `Koopslots: n van m`
- `deployed_pct` stijgt richting 30–45%

Compare met Alpaca (optioneel):
```bash
python -m metrics.kraken_compare.cli \
  --kraken-journal "/path/to/Kraken bot/data/kraken_trades.jsonl" \
  --alpaca-journal "/path/to/MCP-alpaca/data/alpaca_trades.jsonl"
```
