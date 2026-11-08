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
from datetime import datetime
from pathlib import Path

# Kraken-package staat op repo-root (naast ``src/``); pad vroeg zetten.
_REPO_ROOT = Path(__file__).resolve().parents[3]
os.chdir(_REPO_ROOT)
sys.path.insert(0, str(_REPO_ROOT))

from kraken.live_trader import run_once  # noqa: E402
from rangebot.live.daily_report import send_daily_report  # noqa: E402
from rangebot.telegram.bot import send_telegram  # noqa: E402

INTERVAL_MINUTEN = 60
DAGRAPPORT_UUR = 22


def main() -> None:
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
