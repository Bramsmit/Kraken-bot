"""Symbol selection and dry-run flag — uses only :class:`~rangebot.exchange.base.ExchangeClient`."""

from __future__ import annotations

from rangebot.config.settings import (
    KRAKEN_MAX_BUY_DISTANCE_PCT,
    kraken_dry_run_from_env,
    required_min_spread_fraction_crypto_usd,
)
from rangebot.data.market_data import fetch_symbol_rows_for_pool
from rangebot.exchange.base import ExchangeClient
from rangebot.execution.position_manager import get_qty_for_symbol, is_tradable_position
from rangebot.strategy.range_strategy import (
    build_levels_scored_from_symbol_rows,
    levels_passing_spread,
    select_top_symbols_from_scores,
)


def dry_run_from_env() -> bool:
    """Kraken dry-run: default True; set ``KRAKEN_DRY_RUN=false`` for live orders."""
    return kraken_dry_run_from_env()


def pool_latest_prices(client: ExchangeClient, pool: list[str]) -> dict[str, float]:
    """Latest price per pool symbol; symbols without a usable quote are omitted."""
    out: dict[str, float] = {}
    for sym in pool:
        try:
            px = client.get_latest_price(sym)
        except Exception:
            continue
        if px:
            out[sym] = float(px)
    return out


def symbols_with_balance(
    client: ExchangeClient,
    pool: list[str],
    prices: dict[str, float] | None = None,
) -> set[str]:
    """Symbols in pool with tradable notional (above dust fee floor)."""
    out: set[str] = set()
    for sym in pool:
        qf, _ = get_qty_for_symbol(client, sym)
        if prices is None:
            try:
                ref_px = client.get_latest_price(sym)
            except Exception:
                continue
        else:
            ref_px = prices.get(sym)
        if ref_px and is_tradable_position(qf, float(ref_px)):
            out.add(sym)
    return out


def select_top_symbols_for_range(
    client: ExchangeClient,
    pool: list[str],
    n: int,
    ref_notional_usd: float,
) -> tuple[
    list[str],
    dict[str, tuple[float, float]],
    dict[str, tuple[float, float, float]],
    dict[str, float],
]:
    """Pick top-N by score, always keeping symbols with balance (same as before).

    Returns ``(selected, levels, levels_scored, pool_prices)`` where
    ``levels_scored`` maps each pool symbol that passed data/spread gates to
    ``(buy, sell, score)``. Candidates trading further than
    ``KRAKEN_MAX_BUY_DISTANCE_PCT`` above their buy level are skipped: their
    limit order would hold a buy slot without a realistic chance to fill.
    """
    min_spread_frac = required_min_spread_fraction_crypto_usd(ref_notional_usd)
    rows_map = fetch_symbol_rows_for_pool(client, pool)
    levels_scored = build_levels_scored_from_symbol_rows(
        rows_map, pool, min_spread_frac
    )
    pool_prices = pool_latest_prices(client, pool)
    symbols_with_positions = symbols_with_balance(client, pool, prices=pool_prices)
    selected, levels = select_top_symbols_from_scores(
        levels_scored,
        symbols_with_positions,
        n,
        current_prices=pool_prices,
        max_buy_distance_frac=KRAKEN_MAX_BUY_DISTANCE_PCT,
    )
    missing = [s for s in selected if s not in levels]
    for sym in missing:
        rows = rows_map.get(sym)
        if rows:
            lv = levels_passing_spread(rows, min_spread_frac)
            if lv:
                levels[sym] = lv
    return selected, levels, levels_scored, pool_prices


select_top_symbols_kraken = select_top_symbols_for_range
