"""
Configuratie voor de range-trading bot.

USD spot (Kraken) defaults; fee constants worden gebruikt door journal, Telegram en backtests.
"""

from __future__ import annotations

from decimal import Decimal

# Pool van USD-spot-paren (Kraken unified)
SYMBOL_POOL = [
    "AVAX/USD", "UNI/USD", "AAVE/USD", "LINK/USD", "DOT/USD",
    "SOL/USD", "ADA/USD", "XRP/USD", "BCH/USD", "LTC/USD",
    "CRV/USD", "DOGE/USD", "ETH/USD", "BTC/USD",
]

# Hoeveel symbolen actief getrade worden (geselecteerd op winstgevendheid)
SYMBOLS_ACTIVE = 3

# Voor backtest: eerste N uit pool (zelfde subset als live)
SYMBOLS = SYMBOL_POOL[:SYMBOLS_ACTIVE]

# Kapitaal (backtest / documentatie). Live sizing gebruikt
# ``estimate_portfolio_usd(SYMBOL_POOL) / SYMBOLS_ACTIVE`` i.p.v. dit getal.
START_CAPITAL = 500
# verdeel over actieve symbolen
CAPITAL_PER_ASSET = START_CAPITAL / SYMBOLS_ACTIVE

# --- main.run_once allocatie (geen strategie-math; alleen kapitaal-schaal) ---
BUYING_POWER_PER_SYMBOL_FRACTION = 0.995
ORDER_ESTIMATE_NOTIONAL_FRACTION = 0.99
MIN_CAPITAL_PER_ASSET_USD = 10.0

# --- CLI main() retry ---
MAIN_RUN_MAX_RETRIES = 2
MAIN_RUN_RETRY_WAIT_BASE_SEC = 5

# Range niveaus (daily bars)
# Gemiddelde laatste N dagen i.p.v. 1 dag — minder uitschieters
LEVELS_LOOKBACK_DAYS = 3
BUY_ABOVE_LOW_PCT = 0.005   # 0.5% boven de gem. low
SELL_BELOW_HIGH_PCT = 0.02  # 2% onder de gem. high
MIN_SPREAD_PCT = 0.02       # minimaal 2% spread tussen koop en verkoop

# Reference maker/taker (historische namen BITVAVO_*); typische retail-tier: maker 0,15%, taker 0,25%.
BITVAVO_MAKER_FEE_RATE = 0.0015
BITVAVO_TAKER_FEE_RATE = 0.0025
# Limietorders ≈ maker; stop/markt-exit ≈ taker (backtest).
# Alleen voor journal/telegram/backtest-schattingen, niet voor orderparameters op de beurs.
BITVAVO_FEE_BUY_RATE = BITVAVO_MAKER_FEE_RATE
BITVAVO_FEE_SELL_LIMIT_RATE = BITVAVO_MAKER_FEE_RATE
BITVAVO_FEE_SELL_TAKER_RATE = BITVAVO_TAKER_FEE_RATE

# USD-range bot: %-maker + vaste USD per zijde (journal/backtest legacy). Tier zelf afstemmen.
RANGE_MIN_ORDER_REF_USD = 5.0
RANGE_CRYPTO_FEE_FIXED_PER_SIDE_USD = 0.25
RANGE_CRYPTO_ROUND_TRIP_FIXED_USD = RANGE_CRYPTO_FEE_FIXED_PER_SIDE_USD * 2

import os as _os_kraken_adapter

# Gemeten live (aug 2026); Tier ~2 maker. Pas aan na volume-tier wijziging.
KRAKEN_MAKER_FEE_RATE = float(
    _os_kraken_adapter.environ.get("KRAKEN_MAKER_FEE_RATE", "0.0030")
)
KRAKEN_TAKER_FEE_RATE = float(
    _os_kraken_adapter.environ.get("KRAKEN_TAKER_FEE_RATE", "0.0040")
)
# Geen vaste USD-fee in spread-gate voor Kraken live.
KRAKEN_USE_FIXED_FEE_IN_SPREAD_GATE = False
RANGE_CRYPTO_ESTIMATED_MAKER_ROUND_TRIP_PCT = KRAKEN_MAKER_FEE_RATE * 2
# Journal/fills: uren terug naar trades. 4u is ruim genoeg voor uurlijkse runs;
# kort genoeg om bij state-verlies slechts 1 run aan fills opnieuw te melden.
FILLED_ORDERS_LOOKBACK_HOURS = 4

# Per-symbol max position notional (USD). Default unset = no cap.
_km_pos = _os_kraken_adapter.environ.get(
    "KRAKEN_MAX_POSITION_VALUE_USD", ""
).strip()
try:
    KRAKEN_MAX_POSITION_VALUE_USD: float | None = (
        float(_km_pos) if _km_pos else None
    )
except ValueError:
    KRAKEN_MAX_POSITION_VALUE_USD = None

KRAKEN_MIN_POSITION_NOTIONAL_USD = (
    RANGE_CRYPTO_ROUND_TRIP_FIXED_USD / MIN_SPREAD_PCT
)  # $25 bij defaults

KRAKEN_MAX_DEPLOYED_PCT = float(
    _os_kraken_adapter.environ.get("KRAKEN_MAX_DEPLOYED_PCT", "0.45")
)


def kraken_dry_run_from_env() -> bool:
    """Default True (safe): set ``KRAKEN_DRY_RUN=false`` for live orders."""
    v = _os_kraken_adapter.environ.get("KRAKEN_DRY_RUN", "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    if v in ("1", "true", "yes", "on"):
        return True
    return True


def required_min_spread_fraction_crypto_usd(ref_notional_usd: float) -> float:
    """Min. relatieve spread (sell vs buy); fee-model uit :mod:`rangebot.config.settings`."""
    ref = max(RANGE_MIN_ORDER_REF_USD, float(ref_notional_usd or 0))
    pct = KRAKEN_MAKER_FEE_RATE * 2
    extra_margin = 0.002
    if KRAKEN_USE_FIXED_FEE_IN_SPREAD_GATE:
        fixed = RANGE_CRYPTO_ROUND_TRIP_FIXED_USD / ref
        return max(MIN_SPREAD_PCT, fixed) + pct + extra_margin
    return max(MIN_SPREAD_PCT, pct + extra_margin)


# Journal/Telegram: vaste USD per fill (default = zijde hierboven).
import os as _os_journal_fees


_jf_default = str(RANGE_CRYPTO_FEE_FIXED_PER_SIDE_USD)
_jffe = _os_journal_fees.environ.get(
    "JOURNAL_FIXED_FEE_PER_FILL_USD", _jf_default
).strip()
JOURNAL_FIXED_FEE_PER_FILL_USD = float(_jffe) if _jffe else 0.0
# Telegram: geen bericht per koop-fill; alleen afgeronde verkoop met PnL (standaard).
TELEGRAM_NOTIFY_BUY_FILLS = _os_journal_fees.environ.get(
    "TELEGRAM_NOTIFY_BUY_FILLS", "false"
).strip().lower() in ("1", "true", "yes", "on")

# Stop-loss: vast bedrag per eenheid onder koopniveau
STOP_LOSS_PER_UNIT = 0.01

# Na cancel: korte pauze (balance moet vrijkomen)
ORDER_REPLACE_DELAY_SEC = 3

# Limietprijs: drempel voor 8-decimaal afronding en "te lage" buy-level skip (zelfde historische waarde)
MICRO_PRICE_EPS = 0.0001
ROUND_LIMIT_PRICE_ONE = 1.0

# Herplaats order als prijs meer dan dit % afwijkt
ORDER_UPDATE_THRESHOLD = 0.01  # 1%

# Na 24u: order minder relevant; herplaats met verse levels
ORDER_MAX_AGE_HOURS = 24

# Prijs >5% boven buy order: cancel + herplaats
ORDER_STALE_PRICE_THRESHOLD = 0.05
# voor backtest
STOP_LOSS_VALUES_TO_TEST = [0.01, 0.02, 0.03, 0.05, 0.10]

# Stof: onder deze vrije hoeveelheid geen sell / geen "positie" voor selectie
MIN_SELLABLE_CRYPTO_QTY = Decimal("0.0001")

# Backtest
BACKTEST_MONTHS = 3
TIMEFRAME = "1Day"

import os as _os

DRY_RUN = _os.environ.get("DRY_RUN", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
