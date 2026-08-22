"""Symbol selection and dry-run flag — uses only :class:`~rangebot.exchange.base.ExchangeClient`."""

from __future__ import annotations

from rangebot.config.settings import (
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


def symbols_with_balance(client: ExchangeClient, pool: list[str]) -> set[str]:
    """Symbols in pool with tradable notional (above dust fee floor)."""
    out: set[str] = set()
    for sym in pool:
        qf, _ = get_qty_for_symbol(client, sym)
        try:
            ref_px = client.get_latest_price(sym)
        except Exception:
            continue
        if ref_px and is_tradable_position(qf, float(ref_px)):
            out.add(sym)
    return out


def select_top_symbols_for_range(
    client: ExchangeClient,
    pool: list[str],
    n: int,
    ref_notional_usd: float,
) -> tuple[list[str], dict[str, tuple[float, float]]]:
    """Pick top-N by score, always keeping symbols with balance (same as before)."""
    min_spread_frac = required_min_spread_fraction_crypto_usd(ref_notional_usd)
    rows_map = fetch_symbol_rows_for_pool(client, pool)
    levels_scored = build_levels_scored_from_symbol_rows(
        rows_map, pool, min_spread_frac
    )
    symbols_with_positions = symbols_with_balance(client, pool)
    selected, levels = select_top_symbols_from_scores(
        levels_scored, symbols_with_positions, n
    )
    missing = [s for s in selected if s not in levels]
    for sym in missing:
        rows = rows_map.get(sym)
        if rows:
            lv = levels_passing_spread(rows, min_spread_frac)
            if lv:
                levels[sym] = lv
    return selected, levels


select_top_symbols_kraken = select_top_symbols_for_range
