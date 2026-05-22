"""CLI entry: one Kraken USD range pass (``run_once``) or continuous retry loop."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from rangebot.config.settings import (
    MAIN_RUN_MAX_RETRIES,
    MAIN_RUN_RETRY_WAIT_BASE_SEC,
    MIN_CAPITAL_PER_ASSET_USD,
    MIN_SELLABLE_CRYPTO_QTY,
    MICRO_PRICE_EPS,
    ORDER_MAX_AGE_HOURS,
    ORDER_REPLACE_DELAY_SEC,
    ORDER_STALE_PRICE_THRESHOLD,
    ORDER_UPDATE_THRESHOLD,
    RANGE_CRYPTO_ESTIMATED_MAKER_ROUND_TRIP_PCT,
    RANGE_CRYPTO_ROUND_TRIP_FIXED_USD,
    SYMBOL_POOL,
    SYMBOLS_ACTIVE,
    required_min_spread_fraction_crypto_usd,
)
from rangebot.data.market_data import get_mid_price
from rangebot.execution.order_manager import (
    cancel_order_safe,
    order_age_hours,
    round_limit_price,
    submit_limit_buy,
    submit_limit_sell_all_free,
)
from rangebot.execution.position_manager import (
    estimate_portfolio_usd,
    get_buying_power_usd,
    get_positions_map,
    get_qty_for_symbol,
    persist_entries_from_balances,
    capital_per_active_symbol_usd,
    ref_notional_for_range_selection,
)
from rangebot.execution.risk_manager import stop_price_below_entry
from rangebot.exchange.kraken import (
    check_and_notify_kraken_fills,
    fetch_open_orders,
    filter_kraken_usd_pool,
    make_exchange,
    norm_symbol,
    save_kraken_state,
)
from rangebot.exchange.kraken.validation import OrderValidationError
from rangebot.run_audit import KRAKEN_RUNS_JSONL, log_run_audit
from rangebot.strategy.signals import (
    dry_run_from_env,
    select_top_symbols_for_range,
)
from rangebot.telegram.bot import send_telegram
from rangebot.telegram.config import apply_kraken_telegram_env_overrides
from rangebot.telegram.control_state import is_trading_paused
from rangebot.utils.logging import configure_stdout_logging

_REPO_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv_if_present(repo_root: Path | None = None) -> None:
    """Populate process env from ``.env`` without overriding existing variables."""
    root = repo_root or _REPO_ROOT
    env_path = root / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"'))


def bootstrap_cli_environment(repo_root: Path | None = None) -> None:
    """Load dotenv, Telegram env overrides for Kraken, and configure logging."""
    load_dotenv_if_present(repo_root)
    apply_kraken_telegram_env_overrides()
    configure_stdout_logging()


bootstrap_cli_environment()
log = logging.getLogger(__name__)


def _is_kraken_below_minimum_order(exc: OrderValidationError) -> bool:
    """Kraken/ccxt minimum amount or minimum cost shortfall."""
    return "< minimum" in str(exc).lower()


def run_once() -> dict:
    """
    Single scheduled pass: venue connection, symbol selection, fill reconcile, limit upkeep.

    **Strategy impact:** symbol/level *selection* is delegated to
    ``select_top_symbols_for_range`` / ``rangebot.strategy`` — unchanged by this loop.

    **Phases:** (1) pause guard, pool filter; (2) ref-notional sizing and symbol pick;
    (3) fill notify + mid prices + positions; (4) per-symbol order maintenance;
    (5) persist state, audit line, Telegram summary.

    Returns run stats ``{placed, updated, unchanged, skipped}`` or ``{}`` if skipped early.
    """
    if is_trading_paused():
        log.info("run_once overgeslagen: trading staat op pauze (Telegram /pause).")
        return {}

    client = make_exchange()
    dry = client.dry_run
    kr_pool = filter_kraken_usd_pool(client, SYMBOL_POOL)
    if not kr_pool:
        log.warning("Geen Kraken USD-markten voor SYMBOL_POOL")
        send_telegram("⚠️ Kraken: geen bruikbare USD-markten in pool")
        log_run_audit(
            {"bot": "kraken_range", "event": "no_markets", "dry_run": dry},
            filename=KRAKEN_RUNS_JSONL,
        )
        return {}

    ref_usd, _ = ref_notional_for_range_selection(
        client, kr_pool, symbols_active=SYMBOLS_ACTIVE
    )

    symbols, levels = select_top_symbols_for_range(
        client, kr_pool, SYMBOLS_ACTIVE, ref_usd
    )
    if not symbols:
        log.warning("Geen symbolen geselecteerd")
        send_telegram("⚠️ Kraken: geen symbolen geselecteerd uit pool")
        log_run_audit(
            {
                "bot": "kraken_range",
                "event": "no_symbols_selected",
                "dry_run": dry,
            },
            filename=KRAKEN_RUNS_JSONL,
        )
        return {}

    portfolio_usd_pre = estimate_portfolio_usd(client, kr_pool)
    new_trades, entries_after_fills = check_and_notify_kraken_fills(
        client,
        kr_pool,
        portfolio_usd=portfolio_usd_pre,
    )

    mid_prices: dict[str, float] = {}
    for s in symbols:
        mp = get_mid_price(client, s)
        if mp:
            mid_prices[s] = mp

    positions = get_positions_map(client, symbols, entries_after_fills)
    portfolio_equity = estimate_portfolio_usd(client, kr_pool)
    free_usd = get_buying_power_usd(client)
    capital_per = capital_per_active_symbol_usd(
        portfolio_equity_usd=portfolio_equity,
        free_quote_usd=free_usd,
        n_symbols=len(symbols),
    )

    stats = {"placed": 0, "updated": 0, "unchanged": 0, "skipped": 0}

    log.info("[Kraken] Geselecteerd: %s", ", ".join(symbols))
    log.info(
        "Spread-drempel: ref-notional $%.2f → min. spread %.2f%%",
        ref_usd,
        required_min_spread_fraction_crypto_usd(ref_usd) * 100,
    )
    log.info(
        "Portfolio ~ $%.2f | Vrije USD $%.2f | Per slot (buy max) $%.2f | DRY_RUN=%s",
        portfolio_equity,
        free_usd,
        capital_per,
        dry,
    )
    log.info("Levels: %s", levels)
    log.info("Mid prices: %s", mid_prices)
    log.info("Positions (free qty): %s", positions)
    log.info("")

    for symbol in symbols:
        if symbol not in levels:
            continue
        buy_level, sell_level = levels[symbol]
        pos_qty, avg_entry = positions.get(symbol, (0.0, 0.0))
        open_orders = fetch_open_orders(client, symbol)

        if pos_qty <= 0:
            for o in open_orders:
                if o.get("side") == "sell":
                    try:
                        cancel_order_safe(client, str(o["id"]), symbol)
                        log.info("  %s: Orphan sell geannuleerd", symbol)
                    except Exception:
                        pass

        if pos_qty > 0 and Decimal(str(pos_qty)) < MIN_SELLABLE_CRYPTO_QTY:
            for o in open_orders:
                if o.get("side") == "sell":
                    try:
                        cancel_order_safe(client, str(o["id"]), symbol)
                        log.info(
                            "  %s: Dust qty=%s, sell geannuleerd",
                            symbol,
                            pos_qty,
                        )
                    except Exception:
                        pass
            continue

        if pos_qty > 0:
            existing_sell = next(
                (
                    o
                    for o in open_orders
                    if o.get("side") == "sell"
                    and str(o.get("type") or "").lower() == "limit"
                ),
                None,
            )
            entry = avg_entry if avg_entry > 0 else buy_level
            stop_price = stop_price_below_entry(entry)
            limit_sell = sell_level
            needs_new_sell = True

            if existing_sell:
                old_sell_price = float(existing_sell.get("price") or 0)
                age_hours = order_age_hours(existing_sell)
                price_diff = (
                    abs(old_sell_price - limit_sell) / old_sell_price
                    if old_sell_price
                    else 1.0
                )
                current_price = mid_prices.get(symbol)

                if (
                    current_price
                    and old_sell_price
                    and current_price
                    < limit_sell * (1 - ORDER_STALE_PRICE_THRESHOLD)
                ):
                    try:
                        cancel_order_safe(
                            client, str(existing_sell["id"]), symbol
                        )
                        pct_below = (
                            (limit_sell - current_price) / limit_sell * 100
                        )
                        log.info(
                            "  %s: Sell vervangen (prijs onder target %.1f%%)",
                            symbol,
                            pct_below,
                        )
                        send_telegram(
                            f"🔄 [Kraken] {symbol}: Sell vervangen, "
                            f"nieuwe @ ${limit_sell:.4f}"
                        )
                        stats["updated"] += 1
                    except Exception as e:
                        log.warning("  %s: cancel sell: %s", symbol, e)
                        needs_new_sell = False
                elif age_hours >= ORDER_MAX_AGE_HOURS:
                    try:
                        cancel_order_safe(
                            client, str(existing_sell["id"]), symbol
                        )
                        log.info(
                            "  %s: Sell vervangen na %.0fh",
                            symbol,
                            age_hours,
                        )
                        send_telegram(
                            f"🔄 [Kraken] {symbol}: Sell na {age_hours:.0f}h "
                            f"@ ${limit_sell:.4f}"
                        )
                        stats["updated"] += 1
                    except Exception as e:
                        log.warning("  %s: cancel sell: %s", symbol, e)
                        needs_new_sell = False
                elif price_diff > ORDER_UPDATE_THRESHOLD:
                    try:
                        cancel_order_safe(
                            client, str(existing_sell["id"]), symbol
                        )
                        log.info(
                            "  %s: Sell bijgewerkt %.4f → %.4f",
                            symbol,
                            old_sell_price,
                            limit_sell,
                        )
                        send_telegram(
                            f"🔄 [Kraken] {symbol}: Sell @ ${limit_sell:.4f}"
                        )
                        stats["updated"] += 1
                    except Exception as e:
                        log.warning("  %s: cancel sell: %s", symbol, e)
                        needs_new_sell = False
                else:
                    log.info(
                        "  %s: Sell ongewijzigd @ $%.4f (%.0fh)",
                        symbol,
                        old_sell_price,
                        age_hours,
                    )
                    stats["unchanged"] += 1
                    needs_new_sell = False

            if needs_new_sell:
                try:
                    if existing_sell and ORDER_REPLACE_DELAY_SEC > 0:
                        time.sleep(ORDER_REPLACE_DELAY_SEC)
                    free_q, _ = get_qty_for_symbol(client, symbol)
                    if free_q <= 0:
                        log.warning(
                            "  %s: geen free qty voor sell na cancel",
                            symbol,
                        )
                    else:
                        min_amt, min_cost = client.limit_order_minimums(
                            symbol
                        )
                        sell_notional = free_q * limit_sell
                        below_amt = (
                            min_amt is not None
                            and free_q + 1e-12 < float(min_amt)
                        )
                        below_cost = (
                            min_cost is not None
                            and sell_notional + 1e-8 < float(min_cost)
                        )
                        if below_amt or below_cost:
                            log.info(
                                "  %s: Sell overgeslagen (stof onder "
                                "Kraken-min): qty=%s (min_amt=%s) "
                                "nom=$%.4f (min_cost=%s)",
                                symbol,
                                free_q,
                                min_amt,
                                sell_notional,
                                min_cost,
                            )
                            for o in open_orders:
                                if o.get("side") == "sell":
                                    try:
                                        cancel_order_safe(
                                            client,
                                            str(o["id"]),
                                            symbol,
                                        )
                                    except Exception:
                                        pass
                            stats["skipped"] += 1
                        else:
                            submit_limit_sell_all_free(
                                client, symbol, limit_sell
                            )
                            log.info(
                                "  %s: Sell limit @ $%.4f (stop-ref $%.4f)",
                                symbol,
                                limit_sell,
                                stop_price,
                            )
                            if not existing_sell:
                                send_telegram(
                                    f"📊 [Kraken] {symbol}: Sell limit @ "
                                    f"${limit_sell:.4f}"
                                )
                                stats["placed"] += 1
                except OrderValidationError as e:
                    if _is_kraken_below_minimum_order(e):
                        log.info(
                            "  %s: Sell overgeslagen (stof): %s",
                            symbol,
                            e,
                        )
                    else:
                        log.warning("  %s: sell fout: %s", symbol, e)
                        send_telegram(
                            f"❌ [Kraken] {symbol}: sell-fout: {e}"
                        )
                except Exception as e:
                    log.warning("  %s: sell fout: %s", symbol, e)
                    send_telegram(f"❌ [Kraken] {symbol}: sell-fout: {e}")
        else:
            if capital_per < MIN_CAPITAL_PER_ASSET_USD:
                log.info(
                    "  %s: Te weinig kapitaal ($%.2f), skip",
                    symbol,
                    capital_per,
                )
                stats["skipped"] += 1
            elif buy_level < MICRO_PRICE_EPS:
                log.info("  %s: Prijs te laag voor limiet", symbol)
                stats["skipped"] += 1
            else:
                existing_buy = next(
                    (
                        o
                        for o in open_orders
                        if o.get("side") == "buy"
                    ),
                    None,
                )
                needs_new_order = True

                if existing_buy:
                    old_price = float(existing_buy.get("price") or 0)
                    age_hours = order_age_hours(existing_buy)
                    price_diff = (
                        abs(old_price - buy_level) / old_price
                        if old_price
                        else 1.0
                    )
                    current_price = mid_prices.get(symbol)

                    if (
                        current_price
                        and old_price
                        and current_price
                        > old_price * (1 + ORDER_STALE_PRICE_THRESHOLD)
                    ):
                        try:
                            cancel_order_safe(
                                client, str(existing_buy["id"]), symbol
                            )
                            send_telegram(
                                f"🔄 [Kraken] {symbol}: Buy vervangen @ "
                                f"${buy_level:.4f}"
                            )
                            stats["updated"] += 1
                        except Exception as e:
                            log.warning(
                                "  %s: cancel buy: %s", symbol, e
                            )
                            needs_new_order = False
                    elif age_hours >= ORDER_MAX_AGE_HOURS:
                        try:
                            cancel_order_safe(
                                client, str(existing_buy["id"]), symbol
                            )
                            send_telegram(
                                f"🔄 [Kraken] {symbol}: Buy na {age_hours:.0f}h "
                                f"@ ${buy_level:.4f}"
                            )
                            stats["updated"] += 1
                        except Exception as e:
                            log.warning(
                                "  %s: cancel buy: %s", symbol, e
                            )
                            needs_new_order = False
                    elif price_diff > ORDER_UPDATE_THRESHOLD:
                        try:
                            cancel_order_safe(
                                client, str(existing_buy["id"]), symbol
                            )
                            send_telegram(
                                f"🔄 [Kraken] {symbol}: Buy bijgewerkt @ "
                                f"${buy_level:.4f}"
                            )
                            stats["updated"] += 1
                        except Exception as e:
                            log.warning(
                                "  %s: cancel buy: %s", symbol, e
                            )
                            needs_new_order = False
                    else:
                        stats["unchanged"] += 1
                        needs_new_order = False

                if needs_new_order:
                    if existing_buy and ORDER_REPLACE_DELAY_SEC > 0:
                        time.sleep(ORDER_REPLACE_DELAY_SEC)
                    spread_frac = (
                        (sell_level - buy_level) / buy_level
                        if buy_level > 0
                        else 0
                    )
                    gross_usd_est = capital_per * spread_frac
                    fee_usd_est = (
                        RANGE_CRYPTO_ROUND_TRIP_FIXED_USD
                        + capital_per
                        * RANGE_CRYPTO_ESTIMATED_MAKER_ROUND_TRIP_PCT
                    )
                    if gross_usd_est < fee_usd_est:
                        log.warning(
                            "  %s: Buy skip bruto $%.2f < fees $%.2f",
                            symbol,
                            gross_usd_est,
                            fee_usd_est,
                        )
                        stats["skipped"] += 1
                        continue
                    limit_px = round_limit_price(buy_level)
                    safe_px = client.maker_safe_limit_buy_price(
                        symbol, limit_px
                    )
                    if safe_px is None:
                        log.warning(
                            "  %s: Buy skip (geen maker-prijs onder ask)",
                            symbol,
                        )
                        stats["skipped"] += 1
                        continue
                    if safe_px < MICRO_PRICE_EPS:
                        log.info("  %s: Prijs te laag na klemming", symbol)
                        stats["skipped"] += 1
                        continue
                    if abs(safe_px - limit_px) > MICRO_PRICE_EPS:
                        log.info(
                            "  %s: Buy limiet geklemd %.6f → %.6f "
                            "(geen marketable limit)",
                            symbol,
                            limit_px,
                            safe_px,
                        )
                    limit_px = safe_px
                    qty = capital_per / limit_px
                    try:
                        submit_limit_buy(
                            client,
                            symbol,
                            qty,
                            limit_px,
                        )
                        log.info(
                            "  %s: Limit buy @ $%.6f notioneel $%.0f",
                            symbol,
                            limit_px,
                            capital_per,
                        )
                        if not existing_buy:
                            send_telegram(
                                f"📊 [Kraken] {symbol}: Limit buy @ "
                                f"${limit_px:.4f}"
                            )
                            stats["placed"] += 1
                    except Exception as e:
                        log.warning("  %s: buy fout: %s", symbol, e)
                        send_telegram(
                            f"❌ [Kraken] {symbol}: buy-fout: {e}"
                        )

    entries_final = persist_entries_from_balances(
        client,
        kr_pool,
        entries_after_fills,
        mid_prices,
    )
    save_kraken_state(entries=entries_final)

    trade_status = (
        f"{new_trades} nieuwe trade(s) gevuld"
        if new_trades
        else "Geen nieuwe trades gevuld"
    )
    summary = (
        f"[Kraken] Run: {stats['placed']} geplaatst, {stats['updated']} bijgewerkt, "
        f"{stats['unchanged']} ongewijzigd, {stats['skipped']} overgeslagen | "
        f"{trade_status}"
    )
    if symbols:
        summary += f"\nActief: {', '.join(symbols)}"
    log.info(summary)

    portfolio_usd = estimate_portfolio_usd(client, kr_pool)
    buying_final = get_buying_power_usd(client)
    positions_final = get_positions_map(client, symbols, entries_final)
    levels_snap = {
        s: [round(float(levels[s][0]), 8), round(float(levels[s][1]), 8)]
        for s in symbols
        if s in levels
    }
    pos_snap = {
        s: {
            "qty": round(float(q), 8),
            "avg_entry": round(float(e), 8),
        }
        for s, (q, e) in positions_final.items()
    }
    log_run_audit(
        {
            "bot": "kraken_range",
            "dry_run": dry,
            "fills_new_this_run": new_trades,
            "symbols": list(symbols),
            "levels": levels_snap,
            "mid_prices": {k: round(float(v), 8) for k, v in mid_prices.items()},
            "positions": pos_snap,
            "stats": dict(stats),
            "ref_notional_usd": round(float(ref_usd), 4),
            "buying_power_usd": round(buying_final, 4),
            "capital_per_usd": round(float(capital_per), 4),
            "portfolio_value_usd": round(portfolio_usd, 2),
            "summary_text": summary,
            "kraken_pool": [norm_symbol(x) for x in kr_pool],
        },
        filename=KRAKEN_RUNS_JSONL,
    )

    if new_trades or stats["placed"] or stats["updated"]:
        send_telegram(f"📋 {summary}")
    return stats


def main() -> None:
    log.info("=" * 50)
    log.info("Kraken Live USD — range (rangebot)")
    log.info("=" * 50)
    log.info(
        "Pool (USD): %s | top %d | DRY_RUN=%s",
        ", ".join(SYMBOL_POOL),
        SYMBOLS_ACTIVE,
        dry_run_from_env(),
    )
    log.info("Run: %s", datetime.now().isoformat())

    for attempt in range(MAIN_RUN_MAX_RETRIES + 1):
        try:
            run_once()
            log.info("Klaar.")
            return
        except Exception as e:
            log.warning(
                "Fout (poging %d/%d): %s",
                attempt + 1,
                MAIN_RUN_MAX_RETRIES + 1,
                e,
            )
            if attempt < MAIN_RUN_MAX_RETRIES:
                wait_sec = MAIN_RUN_RETRY_WAIT_BASE_SEC * (attempt + 1)
                log.info("Retry over %d sec...", wait_sec)
                time.sleep(wait_sec)
            else:
                send_telegram(f"❌ [Kraken] Bot fout: {e}")
                raise


if __name__ == "__main__":
    main()
