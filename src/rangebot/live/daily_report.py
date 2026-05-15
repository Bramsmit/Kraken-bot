#!/usr/bin/env python3
"""
Dagelijks rapport: stuur portfoliowaarde + winst/verlies naar Telegram.
Kraken USD (geschat uit vrije USD + watchlist-tickers).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from kraken.kraken_runtime import (
    estimate_portfolio_usd,
    filter_kraken_usd_pool,
    get_kraken_cumulative_fictive_fees_usd,
    make_exchange,
)
from rangebot.config.settings import SYMBOL_POOL
from rangebot.telegram.bot import send_telegram
from rangebot.utils.paths import repository_root

_DAY_STATE_PATH = repository_root() / ".kraken_day_state.json"


def save_day_start(value: float) -> None:
    """Sla de portfoliowaarde aan het begin van de dag op."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = {"date": today, "start_value": value}
    _DAY_STATE_PATH.write_text(json.dumps(data))


def load_day_start() -> tuple[str | None, float | None]:
    """Start-van-dag waarde: (datum, waarde) of (None, None)."""
    if not _DAY_STATE_PATH.exists():
        return None, None
    try:
        data = json.loads(_DAY_STATE_PATH.read_text())
        return data.get("date"), data.get("start_value")
    except Exception:
        return None, None


def send_daily_report() -> None:
    """Stuur eindrapport met start vs. huidige waarde en winst/verlies."""
    exchange = make_exchange()
    kr_pool = filter_kraken_usd_pool(exchange, SYMBOL_POOL)
    value = estimate_portfolio_usd(exchange, kr_pool)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_str = datetime.now(timezone.utc).strftime("%d-%m-%Y")

    start_date, start_value = load_day_start()

    if start_value and start_date == today:
        diff = value - start_value
        pct = (diff / start_value * 100) if start_value else 0
        arrow = "📈" if diff >= 0 else "📉"
        msg = (
            f"{arrow} Dagrapport {date_str} (Kraken USD, schatting)\n"
            f"Start:  ${start_value:.2f}\n"
            f"Nu:     ${value:.2f}\n"
            f"Winst:  ${diff:+.2f} ({pct:+.1f}%)"
        )
    else:
        msg = (
            f"📊 Dagrapport {date_str} (Kraken)\n"
            f"Portfolio (schatting): ${value:.2f}"
        )

    cum_fees = get_kraken_cumulative_fictive_fees_usd()
    msg += (
        f"\n\n💸 Fictieve transactiekosten (cumulatief, model): "
        f"${cum_fees:.2f}"
    )

    send_telegram(msg)
    save_day_start(value)


def main() -> None:
    send_daily_report()


if __name__ == "__main__":
    main()
