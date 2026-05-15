#!/usr/bin/env python3
"""
Draai de Kraken range-trader continu: elke INTERVAL_MINUTEN minuten.

Gebruik op een server met: nohup python3 -m rangebot.live.run_loop &
Stuurt een dagrapport om DAGRAPPORT_UUR (lokale tijd).
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Kraken-package staat op repo-root (naast ``src/``); pad vroeg zetten.
_REPO_ROOT = Path(__file__).resolve().parents[3]
os.chdir(_REPO_ROOT)
sys.path.insert(0, str(_REPO_ROOT))

from kraken.kraken_runtime import (  # noqa: E402
    estimate_portfolio_usd,
    filter_kraken_usd_pool,
    make_exchange,
)
from kraken.live_trader import run_once  # noqa: E402
from rangebot.config.settings import SYMBOL_POOL  # noqa: E402
from rangebot.live.daily_report import (  # noqa: E402
    load_day_start,
    save_day_start,
    send_daily_report,
)
from rangebot.telegram.bot import send_telegram  # noqa: E402

INTERVAL_MINUTEN = 60
DAGRAPPORT_UUR = 22


def _init_day_start() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date, _ = load_day_start()
    if start_date != today:
        ex = make_exchange()
        pool = filter_kraken_usd_pool(ex, SYMBOL_POOL)
        save_day_start(estimate_portfolio_usd(ex, pool))


def main() -> None:
    _init_day_start()

    send_telegram(
        "🟢 Kraken bot gestart "
        f"(elke {INTERVAL_MINUTEN} min | dagrapport om {DAGRAPPORT_UUR}:00)"
    )

    last_report_day = None

    while True:
        now = datetime.now()
        try:
            run_once()
        except Exception as e:
            send_telegram(f"❌ Kraken bot fout: {e}")
            print(f"Fout: {e}")

        today = now.strftime("%Y-%m-%d")
        if now.hour == DAGRAPPORT_UUR and today != last_report_day:
            try:
                send_daily_report()
                last_report_day = today
            except Exception as e:
                send_telegram(f"❌ Dagrapport fout: {e}")

        time.sleep(INTERVAL_MINUTEN * 60)


if __name__ == "__main__":
    main()
