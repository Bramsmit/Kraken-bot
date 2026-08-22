"""
Persistente trade-log voor de Kraken live-bot.

Merged werkbestanden (CI/lokaal) met ``data/kraken_trades.jsonl`` (versioned):

- ``kraken_bot_trades.jsonl`` — audit met exchange fees (voorkeur)
- ``kraken_trades.jsonl`` — journal via ``log_trade``

Schrijft:
  - ``data/kraken_trades.jsonl``
  - ``data/kraken_trades.csv``

Gebruik::

    python -m rangebot.live.export_trade_log
    python -m rangebot.live.export_trade_log --source /pad/extra.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from rangebot.utils.paths import repository_root

CSV_FIELDS = [
    "timestamp",
    "trade_id",
    "symbol",
    "side",
    "qty",
    "price",
    "fee_usd",
    "notional_usd",
    "entry_price",
    "profit_usd",
    "portfolio_value_usd",
    "source",
]


def _data_dir(root: Path | None = None) -> Path:
    return (root or repository_root()) / "data"


def _persistent_jsonl(root: Path | None = None) -> Path:
    return _data_dir(root) / "kraken_trades.jsonl"


def _persistent_csv(root: Path | None = None) -> Path:
    return _data_dir(root) / "kraken_trades.csv"


def _trade_id(rec: dict[str, Any]) -> str:
    return str(
        rec.get("trade_id")
        or rec.get("order_id")
        or ""
    ).strip()


def normalize_record(raw: dict[str, Any], *, default_source: str = "") -> dict[str, Any] | None:
    """Map audit/journal/API shapes onto the canonical persistent schema."""
    tid = _trade_id(raw)
    side = str(raw.get("side") or "").lower().strip()
    qty = float(raw.get("qty") or raw.get("filled_qty") or 0)
    price = float(
        raw.get("price") or raw.get("filled_avg_price_usd") or 0
    )
    if not tid or side not in ("buy", "sell") or qty <= 0 or price <= 0:
        return None

    ts = (
        raw.get("timestamp")
        or raw.get("exchange_trade_timestamp")
        or raw.get("logged_at")
    )
    fee = raw.get("fee_usd")
    if fee is None:
        fee = raw.get("exchange_fee_usd")
    if fee is None:
        fee = raw.get("fee_eur")  # legacy journal field name

    entry = raw.get("entry_price")
    if entry is None:
        entry = raw.get("entry_price_usd_for_pnl")

    profit = raw.get("profit_usd")
    if profit is None:
        profit = raw.get("estimated_roundtrip_profit_usd")
    if profit is None:
        profit = raw.get("profit")

    pv = raw.get("portfolio_value_usd")
    if pv is None:
        pv = raw.get("portfolio_usd")
    if pv is None:
        pv = raw.get("portfolio_value")

    source = str(raw.get("source") or default_source or "").strip() or None

    return {
        "timestamp": ts,
        "trade_id": tid,
        "symbol": str(raw.get("symbol") or ""),
        "side": side,
        "qty": qty,
        "price": price,
        "fee_usd": float(fee) if fee is not None else None,
        "notional_usd": round(qty * price, 8),
        "entry_price": float(entry) if entry not in (None, "") else None,
        "profit_usd": float(profit) if profit not in (None, "") else None,
        "portfolio_value_usd": float(pv) if pv not in (None, "") else None,
        "source": source,
    }


def load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    """Load JSONL → dict keyed by trade_id (later row wins)."""
    result: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return result
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            rec = normalize_record(raw, default_source=path.name)
            if rec is None:
                continue
            tid = rec["trade_id"]
            prev = result.get(tid)
            if prev is None:
                result[tid] = rec
                continue
            merged = dict(prev)
            for k, v in rec.items():
                if v is None:
                    continue
                if merged.get(k) is None:
                    merged[k] = v
                elif k in ("fee_usd", "profit_usd", "entry_price", "portfolio_value_usd"):
                    # Prefer non-null enrichment from richer sources
                    merged[k] = v
            result[tid] = merged
    return result


def merge_and_export(
    *,
    root: Path | None = None,
    extra_sources: list[Path] | None = None,
) -> int:
    """
    Merge ephemeral journals + optional extra files into ``data/kraken_trades.*``.

    Returns number of newly added trade_ids vs previous persistent file.
    """
    root = root or repository_root()
    persistent_path = _persistent_jsonl(root)
    before = load_jsonl(persistent_path)
    before_ids = set(before)

    merged: dict[str, dict[str, Any]] = dict(before)

    default_sources = [
        root / "kraken_bot_trades.jsonl",
        root / "kraken_trades.jsonl",
    ]
    sources = list(default_sources)
    if extra_sources:
        sources.extend(extra_sources)

    for src in sources:
        incoming = load_jsonl(src)
        for tid, rec in incoming.items():
            if tid not in merged:
                merged[tid] = rec
            else:
                # Enrich existing with missing fee/profit
                cur = merged[tid]
                for k in ("fee_usd", "profit_usd", "entry_price", "portfolio_value_usd"):
                    if cur.get(k) is None and rec.get(k) is not None:
                        cur[k] = rec[k]
                if not cur.get("source") and rec.get("source"):
                    cur["source"] = rec["source"]

    sorted_records = sorted(
        merged.values(),
        key=lambda r: (r.get("timestamp") or "", r.get("trade_id") or ""),
    )

    data_dir = _data_dir(root)
    data_dir.mkdir(parents=True, exist_ok=True)

    with persistent_path.open("w", encoding="utf-8") as f:
        for rec in sorted_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    csv_path = _persistent_csv(root)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for rec in sorted_records:
            writer.writerow({k: rec.get(k, "") for k in CSV_FIELDS})

    added = len(set(merged) - before_ids)
    print(
        f"export_trade_log: {len(sorted_records)} trades totaal, "
        f"{added} nieuw → {persistent_path.relative_to(root)} "
        f"+ {csv_path.relative_to(root)}"
    )
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge Kraken journals into data/kraken_trades.jsonl + .csv",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Extra JSONL om te mergen (herhaalbaar)",
    )
    parser.add_argument(
        "--repo-root",
        default="",
        help="Override repository root (tests)",
    )
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve() if args.repo_root else repository_root()
    extras = [Path(s).expanduser().resolve() for s in args.source]
    merge_and_export(root=root, extra_sources=extras or None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
