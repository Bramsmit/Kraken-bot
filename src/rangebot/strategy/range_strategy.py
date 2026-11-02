"""
Venue-neutrale range-logica: dagbars → buy/sell-levels en scores.

Numerieke constanten uit :mod:`rangebot.config.settings`.
"""

from __future__ import annotations

from rangebot.config.settings import (
    BUY_ABOVE_LOW_PCT,
    FALLING_KNIFE_DROP_PCT,
    FALLING_KNIFE_LOOKBACK_DAYS,
    LEVELS_LOOKBACK_DAYS,
    ORDER_MAX_AGE_HOURS,
    ORDER_STALE_PRICE_THRESHOLD,
    ORDER_UPDATE_THRESHOLD,
    RANGE_DRIFT_MIN_WEIGHT,
    RANGE_DRIFT_SENSITIVITY,
    SELL_BELOW_HIGH_PCT,
)

# Uitkomsten van `decide_buy_order_action`.
BUY_ORDER_ABANDON = "abandon"
BUY_ORDER_PLACE = "place"
BUY_ORDER_REPLACE_STALE_PRICE = "replace_stale_price"
BUY_ORDER_REPLACE_AGED = "replace_aged"
BUY_ORDER_UPDATE_LEVEL = "update_level"
BUY_ORDER_KEEP = "keep"


def levels_score_from_daily_rows(
    rows: list[dict[str, float]],
    min_spread_frac: float,
) -> tuple[float, float, float] | None:
    """
    rows: chronologische OHLC (`high`, `low` verplicht), minstens
    LEVELS_LOOKBACK_DAYS rijen.
    Retourneert (buy_level, sell_level, score) of None bij te weinig data.
    """
    if len(rows) < LEVELS_LOOKBACK_DAYS:
        return None
    recent = rows[-LEVELS_LOOKBACK_DAYS:]
    low = sum(float(r["low"]) for r in recent) / len(recent)
    high = sum(float(r["high"]) for r in recent) / len(recent)
    buy_level = low * (1 + BUY_ABOVE_LOW_PCT)
    sell_level = high * (1 - SELL_BELOW_HIGH_PCT)
    spread_ok = sell_level >= buy_level * (1 + min_spread_frac)
    spread_pct = (
        (sell_level - buy_level) / buy_level if spread_ok and buy_level else 0.0
    )
    range_pct = (high - low) / low if low else 0.0
    open_first = float(recent[0].get("open") or 0.0)
    close_last = float(recent[-1].get("close") or 0.0)
    if open_first > 0 and close_last > 0:
        drift = (close_last - open_first) / open_first
        drift_weight = max(
            RANGE_DRIFT_MIN_WEIGHT,
            1.0 + RANGE_DRIFT_SENSITIVITY * drift,
        )
    else:
        drift_weight = 1.0
    score = spread_pct * (1 + range_pct) * drift_weight
    return buy_level, sell_level, score


def is_falling_knife(
    rows: list[dict[str, float]],
    *,
    lookback_days: int = FALLING_KNIFE_LOOKBACK_DAYS,
    drop_pct: float = FALLING_KNIFE_DROP_PCT,
) -> bool:
    """
    Detecteer een versnellende meerdaagse neertrend (vallend mes).

    True zodra het symbool over de afgelopen ``lookback_days`` meer dan
    ``drop_pct`` is gedaald én onder het gemiddelde slot van de reeks sluit.
    """
    if len(rows) < lookback_days + 1:
        return False
    closes = [float(r.get("close") or 0.0) for r in rows if float(r.get("close") or 0.0) > 0]
    if len(closes) < lookback_days + 1:
        return False
    ref_close = closes[-(lookback_days + 1)]
    last_close = closes[-1]
    if ref_close <= 0:
        return False
    ret = (last_close - ref_close) / ref_close
    mean_close = sum(closes) / len(closes)
    return ret <= -abs(drop_pct) and last_close < mean_close


def levels_for_exit_only(
    rows: list[dict[str, float]],
) -> tuple[float, float] | None:
    """Bereken buy/sell levels zonder spread-gate (alleen voor orphan exit)."""
    t = levels_score_from_daily_rows(rows, min_spread_frac=0.0)
    if t is None:
        return None
    return t[0], t[1]


def levels_passing_spread(
    rows: list[dict[str, float]],
    min_spread_frac: float,
) -> tuple[float, float] | None:
    """Levels alleen als minimale spread gehaald wordt."""
    t = levels_score_from_daily_rows(rows, min_spread_frac)
    if t is None:
        return None
    buy_level, sell_level, _ = t
    if sell_level < buy_level * (1 + min_spread_frac):
        return None
    return buy_level, sell_level


def build_levels_scored_from_symbol_rows(
    symbol_rows: dict[str, list[dict[str, float]]],
    pool: list[str],
    min_spread_frac: float,
) -> dict[str, tuple[float, float, float]]:
    """Map pool symbol → (buy, sell, score). Short/missing series omitted."""
    result: dict[str, tuple[float, float, float]] = {}
    for symbol in pool:
        rows = symbol_rows.get(symbol)
        if not rows:
            continue
        t = levels_score_from_daily_rows(rows, min_spread_frac)
        if t is not None:
            if is_falling_knife(rows):
                result[symbol] = (t[0], t[1], 0.0)
            else:
                result[symbol] = t
    return result


def buy_level_distance_frac(
    current_price: float | None,
    buy_level: float | None,
) -> float | None:
    """
    Relatieve afstand van de markt tot het buy-level; positief = prijs erboven.

    None zodra een van beide prijzen ontbreekt of niet positief is.
    """
    if not current_price or current_price <= 0:
        return None
    if not buy_level or buy_level <= 0:
        return None
    return (float(current_price) - float(buy_level)) / float(buy_level)


def is_buy_level_reachable(
    current_price: float | None,
    buy_level: float | None,
    max_distance_frac: float,
) -> bool:
    """
    Ligt het buy-level dicht genoeg onder de markt om nog te kunnen vullen?

    Zonder bekende prijs wordt niet gefilterd: een ontbrekende quote mag geen
    symbool uit de selectie duwen.
    """
    distance = buy_level_distance_frac(current_price, buy_level)
    if distance is None:
        return True
    return distance <= max_distance_frac


def decide_buy_order_action(
    *,
    buy_level: float,
    current_price: float | None,
    existing_order_price: float | None,
    max_buy_distance_frac: float,
    order_age_hours: float = 0.0,
    stale_price_frac: float = ORDER_STALE_PRICE_THRESHOLD,
    max_age_hours: float = ORDER_MAX_AGE_HOURS,
    update_frac: float = ORDER_UPDATE_THRESHOLD,
) -> str:
    """
    Bepaal wat er met de buy-order van één symbool moet gebeuren.

    De volgorde is bewust: een buy-level dat te ver onder de markt ligt wordt
    eerst opgegeven, want zo'n order blijft anders elke run opnieuw geplaatst
    worden en houdt cash plus een koopslot bezet. Daarna pas de koers die van
    de order is weggelopen, de ouderdom en een verschoven level.
    """
    if not is_buy_level_reachable(
        current_price, buy_level, max_buy_distance_frac
    ):
        return BUY_ORDER_ABANDON

    if not existing_order_price or existing_order_price <= 0:
        return BUY_ORDER_PLACE

    if current_price and current_price > existing_order_price * (
        1 + stale_price_frac
    ):
        return BUY_ORDER_REPLACE_STALE_PRICE

    if order_age_hours >= max_age_hours:
        return BUY_ORDER_REPLACE_AGED

    level_diff = abs(existing_order_price - buy_level) / existing_order_price
    if level_diff > update_frac:
        return BUY_ORDER_UPDATE_LEVEL

    return BUY_ORDER_KEEP


def select_top_symbols_from_scores(
    levels_scored: dict[str, tuple[float, float, float]],
    symbols_with_positions: set[str],
    n: int,
    current_prices: dict[str, float] | None = None,
    max_buy_distance_frac: float | None = None,
) -> tuple[list[str], dict[str, tuple[float, float]]]:
    """
    Top N by score; symbols with open position always stay selected.

    De score meet alleen de breedte van de range, niet of de koers nog in de
    buurt van het buy-level ligt. Met ``current_prices`` plus
    ``max_buy_distance_frac`` vallen kandidaten af die te ver boven hun
    buy-level handelen; anders bezet zo'n symbool een koopslot met een order
    die nooit vult.
    """
    sorted_by_score = sorted(
        levels_scored.items(),
        key=lambda x: x[1][2],
        reverse=True,
    )
    selected = list(symbols_with_positions)
    for sym, (buy, sell, score) in sorted_by_score:
        if sym in selected or len(selected) >= n:
            continue
        if score <= 0:
            continue
        if max_buy_distance_frac is not None and not is_buy_level_reachable(
            (current_prices or {}).get(sym), buy, max_buy_distance_frac
        ):
            continue
        selected.append(sym)
    levels = {
        sym: (buy, sell)
        for sym, (buy, sell, _) in sorted_by_score
        if sym in selected
    }
    return selected, levels
