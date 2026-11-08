#!/usr/bin/env python3
"""
Dagelijks rapport naar Telegram: equity nu, verschil met 24u geleden, afstand tot
de piek en cumulatieve Kraken-fees. Historie uit ``data/kraken_equity.csv``, fees uit
de gecommitte state-snapshot; geen Actions-cache nodig.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from kraken.kraken_runtime import (
    estimate_portfolio_usd,
    filter_kraken_usd_pool,
    get_kraken_cumulative_kraken_fees_usd,
    make_exchange,
)
from rangebot.config.settings import SYMBOL_POOL
from rangebot.live.equity_log import EquityRow, read_equity_rows
from rangebot.telegram.bot import send_telegram

log = logging.getLogger(__name__)


def build_daily_report(
    rows: list[EquityRow],
    now: datetime,
    *,
    live_value: float | None,
    cum_fees: float,
) -> str:
    value = live_value if live_value is not None else (
        rows[-1].equity_usd if rows else 0.0
    )
    date_str = now.strftime("%d-%m-%Y")
    lines = [f"📊 Dagrapport {date_str} (Kraken USD)", f"Equity:  ${value:.2f}"]

    day_ago = now - timedelta(hours=24)
    ref = next((r for r in reversed(rows) if r.timestamp <= day_ago), None)
    if ref and ref.equity_usd > 0:
        diff = value - ref.equity_usd
        lines.append(f"24u:     ${diff:+.2f} ({diff / ref.equity_usd:+.1%})")
    else:
        lines.append("24u:     n.v.t. (nog geen historie)")

    peak = max([r.equity_usd for r in rows] + [value])
    if peak > 0:
        lines.append(f"Piek:    ${peak:.2f} ({value / peak - 1:+.1%})")

    lines.append(f"\n💸 Kraken-fees (cumulatief, volgens fills): ${cum_fees:.2f}")
    return "\n".join(lines)


def send_daily_report() -> None:
    live_value: float | None
    try:
        exchange = make_exchange()
        kr_pool = filter_kraken_usd_pool(exchange, SYMBOL_POOL)
        live_value = estimate_portfolio_usd(exchange, kr_pool)
    except Exception as e:
        log.warning("Live equity ophalen mislukt, gebruik laatste CSV-regel: %s", e)
        live_value = None

    msg = build_daily_report(
        read_equity_rows(),
        datetime.now(timezone.utc),
        live_value=live_value,
        cum_fees=get_kraken_cumulative_kraken_fees_usd(),
    )
    print(msg)
    send_telegram(msg)


def main() -> None:
    send_daily_report()


if __name__ == "__main__":
    main()
