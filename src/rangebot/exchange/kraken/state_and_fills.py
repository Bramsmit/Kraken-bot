"""Persistent state, fill auditing, and reconciliation (Kraken journal paths)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from rangebot.config.settings import (
    BITVAVO_FEE_BUY_RATE,
    BITVAVO_FEE_SELL_LIMIT_RATE,
    FILLED_ORDERS_LOOKBACK_HOURS,
    JOURNAL_FIXED_FEE_PER_FILL_USD,
    TELEGRAM_NOTIFY_BUY_FILLS,
)
from rangebot.exchange.base import ExchangeClient
from rangebot.exchange.kraken.common import norm_symbol
from rangebot.journal import log_trade
from rangebot.telegram.notifications import notify_trade_filled
from rangebot.utils.paths import repository_root

log = logging.getLogger(__name__)


def filter_kraken_usd_pool(
    client: ExchangeClient, pool: list[str]
) -> list[str]:
    """Keep symbols that exist as active Kraken spot USD markets."""
    return client.filter_tradable_symbol_pool(pool)


def fetch_open_orders(client: ExchangeClient, symbol: str) -> list[dict[str, Any]]:
    try:
        return client.get_open_orders(symbol) or []
    except Exception as e:
        log.warning("get_open_orders %s: %s", symbol, e)
        return []


def _state_path() -> Path:
    return repository_root() / ".kraken_trade_state.json"


def _load_state() -> dict[str, Any]:
    base = {
        "entries": {},
        "notified_trade_ids": [],
        "cumulative_fictive_fees_usd": 0.0,
    }
    path = _state_path()
    if not path.exists():
        return base.copy()
    try:
        data = json.loads(path.read_text())
        out = base.copy()
        out["entries"] = data.get("entries", {})
        out["notified_trade_ids"] = data.get("notified_trade_ids", [])
        out["cumulative_fictive_fees_usd"] = float(
            data.get("cumulative_fictive_fees_usd", 0) or 0
        )
        return out
    except Exception:
        return base.copy()


def save_kraken_state(
    *,
    entries: dict[str, Any] | None = None,
    notified_trade_ids: list[str] | None = None,
    cumulative_fictive_fees_usd: float | None = None,
) -> None:
    path = _state_path()
    state = _load_state()
    if entries is not None:
        state["entries"] = entries
    if notified_trade_ids is not None:
        state["notified_trade_ids"] = notified_trade_ids[-500:]
    if cumulative_fictive_fees_usd is not None:
        state["cumulative_fictive_fees_usd"] = float(
            cumulative_fictive_fees_usd
        )
    try:
        path.write_text(json.dumps(state, indent=2))
    except Exception as e:
        log.warning("Kraken state schrijven mislukt: %s", e)


def get_kraken_cumulative_fictive_fees_usd() -> float:
    return float(_load_state().get("cumulative_fictive_fees_usd", 0) or 0)


def load_kraken_trade_state() -> dict[str, Any]:
    return _load_state()


def _kraken_trade_log_path() -> Path | None:
    raw = os.environ.get("KRAKEN_BOT_TRADE_LOG")
    if raw is None:
        return repository_root() / "kraken_bot_trades.jsonl"
    s = raw.strip()
    if s.lower() in ("", "0", "false", "no", "off"):
        return None
    p = Path(s).expanduser()
    return p if p.is_absolute() else repository_root() / p


def append_kraken_fill_audit(record: dict[str, Any]) -> None:
    path = _kraken_trade_log_path()
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception as e:
        log.warning("kraken_bot_trade_log: %s", e)


def check_and_notify_kraken_fills(
    client: ExchangeClient,
    symbols_pool: list[str],
    *,
    portfolio_usd: float,
) -> tuple[int, dict[str, Any]]:
    """
    Poll recent trades; journal + Telegram; update entries for PnL model.

    Returns (new_trade_count, updated_entries).
    """
    try:
        since_ms = int(
            (
                datetime.now(timezone.utc)
                - timedelta(hours=FILLED_ORDERS_LOOKBACK_HOURS)
            ).timestamp()
            * 1000
        )
        pool_set = {norm_symbol(s) for s in symbols_pool}
        trades_raw: list[dict[str, Any]] = []
        for sym in pool_set:
            try:
                batch = client.fetch_my_trades(sym, since_ms=since_ms, limit=80)
                trades_raw.extend(batch or [])
            except Exception as e:
                log.warning("fetch_my_trades %s: %s", sym, e)

        dedup: dict[str, dict[str, Any]] = {}
        for tr in trades_raw:
            tid = str(tr.get("id") or "")
            if tid:
                dedup[tid] = tr
        trades_sorted = sorted(
            dedup.values(), key=lambda x: x.get("timestamp") or 0
        )

        state = _load_state()
        entries: dict[str, Any] = dict(state.get("entries", {}))
        notified = list(state.get("notified_trade_ids", []))
        notified_set = set(notified)
        cum_fees = float(state.get("cumulative_fictive_fees_usd", 0) or 0)
        new_count = 0

        for tr in trades_sorted:
            tid = str(tr.get("id") or "")
            if not tid or tid in notified_set:
                continue
            sym = norm_symbol(tr.get("symbol") or "")
            if sym not in pool_set:
                continue
            qty = float(tr.get("amount") or 0)
            price = float(tr.get("price") or 0)
            if qty <= 0 or price <= 0:
                continue
            side = str(tr.get("side") or "").lower()
            if side not in ("buy", "sell"):
                continue

            if side == "buy":
                cum_fees += (
                    qty * price * BITVAVO_FEE_BUY_RATE
                    + JOURNAL_FIXED_FEE_PER_FILL_USD
                )
                prev = entries.get(sym)
                if prev and float(prev.get("qty") or 0) > 0:
                    pq = float(prev["qty"])
                    pe = float(prev.get("entry") or 0)
                    new_qty = pq + qty
                    new_entry = (
                        (pe * pq + price * qty) / new_qty
                        if new_qty > 0
                        else price
                    )
                    entries[sym] = {"qty": new_qty, "entry": new_entry}
                else:
                    entries[sym] = {"qty": qty, "entry": price}
                profit = None
                entry_price_for_log = None
            else:
                cum_fees += (
                    qty * price * BITVAVO_FEE_SELL_LIMIT_RATE
                    + JOURNAL_FIXED_FEE_PER_FILL_USD
                )
                profit = None
                entry_price_for_log = None
                if sym in entries:
                    entry = float(entries[sym].get("entry") or 0)
                    entry_price_for_log = entry if entry > 0 else None
                    if entry > 0:
                        cost_incl = (
                            entry * qty * (1 + BITVAVO_FEE_BUY_RATE)
                            + JOURNAL_FIXED_FEE_PER_FILL_USD
                        )
                        proceeds = (
                            price * qty * (1 - BITVAVO_FEE_SELL_LIMIT_RATE)
                            - JOURNAL_FIXED_FEE_PER_FILL_USD
                        )
                        profit = proceeds - cost_incl
                    prev_qty = float(entries[sym].get("qty") or 0)
                    remain_q = prev_qty - qty
                    if remain_q <= 1e-12:
                        del entries[sym]
                    else:
                        entries[sym] = {
                            "qty": remain_q,
                            "entry": entries[sym].get("entry"),
                        }

            ts_ms = tr.get("timestamp")
            ts_iso = (
                datetime.fromtimestamp(
                    ts_ms / 1000, tz=timezone.utc
                ).isoformat()
                if ts_ms
                else None
            )
            append_kraken_fill_audit(
                {
                    "logged_at": datetime.now(timezone.utc).isoformat(),
                    "exchange_trade_timestamp": ts_iso,
                    "trade_id": tid,
                    "symbol": sym,
                    "quote_currency": "USD",
                    "side": side,
                    "filled_qty": qty,
                    "filled_avg_price_usd": price,
                    "notional_usd": round(qty * price, 10),
                    "portfolio_value_usd": round(portfolio_usd, 2),
                    "entry_price_usd_for_pnl": entry_price_for_log,
                    "estimated_roundtrip_profit_usd": round(profit, 8)
                    if profit is not None
                    else None,
                    "note": (
                        "Kraken spot USD; journal gebruikt fictieve "
                        "maker-fee percentages uit settings."
                    ),
                }
            )

            send_tg = (side == "buy" and TELEGRAM_NOTIFY_BUY_FILLS) or (
                side == "sell"
                and entry_price_for_log
                and entry_price_for_log > 0
            )
            notify_trade_filled(
                side,
                sym,
                qty,
                price,
                profit,
                portfolio_usd,
                entry_price=entry_price_for_log,
                send_telegram_message=send_tg,
                currency_label="USD",
            )
            log_trade(
                order_id=tid,
                symbol=sym,
                side=side,
                qty=qty,
                price=price,
                entry_price=entry_price_for_log,
                profit=profit,
                portfolio_value=portfolio_usd,
                journal_filename="kraken_trades.jsonl",
            )
            notified.append(tid)
            notified_set.add(tid)
            new_count += 1

        if new_count:
            save_kraken_state(
                entries=entries,
                notified_trade_ids=notified,
                cumulative_fictive_fees_usd=cum_fees,
            )
        return new_count, entries
    except Exception as e:
        log.warning("Kraken fill-check: %s", e)
        return 0, dict(_load_state().get("entries", {}))
