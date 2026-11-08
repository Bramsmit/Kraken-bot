"""Daily Status heartbeat: is de bot echt gedraaid, en hoe staat de equity ervoor?

Leest ``data/kraken_equity.csv`` (gecommit door elke trade-run); geen exchange-calls.
"""

from __future__ import annotations

from datetime import datetime, timezone

from rangebot.live.equity_log import EquityRow, read_equity_rows
from rangebot.telegram.bot import send_telegram
from rangebot.telegram.control_state import is_trading_paused

MAX_RUN_AGE_HOURS = 12.0
MAX_DRAWDOWN_FROM_PEAK = 0.10


def build_health_message(
    rows: list[EquityRow], now: datetime, paused: bool
) -> tuple[bool, str]:
    if not rows:
        return False, (
            "⚠️ Kraken bot: geen equity-regels gevonden in data/kraken_equity.csv. "
            "Check GitHub Actions."
        )

    last = rows[-1]
    peak = max(r.equity_usd for r in rows)
    age_h = (now - last.timestamp).total_seconds() / 3600
    from_peak = last.equity_usd / peak - 1 if peak > 0 else 0.0

    problems: list[str] = []
    if age_h > MAX_RUN_AGE_HOURS:
        problems.append(f"laatste run {age_h:.0f}u geleden")
    if from_peak < -MAX_DRAWDOWN_FROM_PEAK:
        problems.append(f"equity {from_peak:.1%} onder piek")
    if paused:
        problems.append("trading staat op pauze")

    details = (
        f"Laatste run: {age_h:.0f}u geleden\n"
        f"Equity: ${last.equity_usd:.2f} (piek ${peak:.2f}, {from_peak:+.1%})\n"
        f"Ingezet: {last.deployed_pct:.0%}"
    )
    if problems:
        return False, f"⚠️ Kraken bot: {'; '.join(problems)}\n{details}"
    return True, f"✅ Kraken bot gezond\n{details}"


def main() -> None:
    _, msg = build_health_message(
        read_equity_rows(), datetime.now(timezone.utc), is_trading_paused()
    )
    print(msg)
    send_telegram(msg)


if __name__ == "__main__":
    main()
