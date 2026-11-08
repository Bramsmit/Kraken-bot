"""Per-run equity history in ``data/kraken_equity.csv`` (committed by the trade workflow)."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rangebot.utils.paths import repository_root

log = logging.getLogger(__name__)

_HEADER = ["timestamp", "equity_usd", "cash_usd", "deployed_pct", "positions"]


@dataclass(frozen=True)
class EquityRow:
    timestamp: datetime
    equity_usd: float
    cash_usd: float
    deployed_pct: float
    positions: str


def equity_csv_path() -> Path:
    return repository_root() / "data" / "kraken_equity.csv"


def append_equity_row(
    *,
    equity_usd: float,
    cash_usd: float,
    positions_usd: dict[str, float],
    now: datetime | None = None,
) -> None:
    ts = (now or datetime.now(timezone.utc)).isoformat()
    deployed = sum(positions_usd.values())
    deployed_pct = deployed / equity_usd if equity_usd > 0 else 0.0
    positions = ";".join(
        f"{sym.split('/')[0]}:{usd:.2f}" for sym, usd in sorted(positions_usd.items())
    )
    path = equity_csv_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(_HEADER)
        w.writerow(
            [
                ts,
                f"{equity_usd:.2f}",
                f"{cash_usd:.2f}",
                f"{deployed_pct:.4f}",
                positions,
            ]
        )


def read_equity_rows() -> list[EquityRow]:
    path = equity_csv_path()
    if not path.exists():
        return []
    rows: list[EquityRow] = []
    with path.open(newline="") as f:
        for rec in csv.DictReader(f):
            try:
                rows.append(
                    EquityRow(
                        timestamp=datetime.fromisoformat(rec["timestamp"]),
                        equity_usd=float(rec["equity_usd"]),
                        cash_usd=float(rec["cash_usd"]),
                        deployed_pct=float(rec["deployed_pct"]),
                        positions=rec.get("positions") or "",
                    )
                )
            except (KeyError, TypeError, ValueError):
                log.warning("Equity-CSV: regel overgeslagen: %s", rec)
    return rows
