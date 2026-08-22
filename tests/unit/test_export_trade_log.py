"""Tests for persistent Kraken trade-log export."""

from __future__ import annotations

import json
from pathlib import Path

from rangebot.live.export_trade_log import merge_and_export, normalize_record


def test_normalize_audit_and_journal_shapes() -> None:
    audit = normalize_record(
        {
            "trade_id": "abc",
            "exchange_trade_timestamp": "2026-07-16T07:32:08+00:00",
            "symbol": "UNI/USD",
            "side": "buy",
            "filled_qty": 10.0,
            "filled_avg_price_usd": 3.5,
            "exchange_fee_usd": 0.04,
            "portfolio_value_usd": 500.0,
        }
    )
    assert audit is not None
    assert audit["trade_id"] == "abc"
    assert audit["qty"] == 10.0
    assert audit["fee_usd"] == 0.04

    journal = normalize_record(
        {
            "order_id": "abc",
            "timestamp": "2026-07-16T07:33:00+00:00",
            "symbol": "UNI/USD",
            "side": "buy",
            "qty": 10.0,
            "price": 3.5,
            "portfolio_value": 501.0,
        }
    )
    assert journal is not None
    assert journal["trade_id"] == "abc"
    assert journal["portfolio_value_usd"] == 501.0


def test_merge_dedupes_and_enriches(tmp_path: Path) -> None:
    root = tmp_path
    (root / "kraken_bot_trades.jsonl").write_text(
        json.dumps(
            {
                "trade_id": "t1",
                "exchange_trade_timestamp": "2026-07-16T08:00:00+00:00",
                "symbol": "UNI/USD",
                "side": "buy",
                "filled_qty": 1.0,
                "filled_avg_price_usd": 3.0,
                "exchange_fee_usd": 0.01,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "kraken_trades.jsonl").write_text(
        json.dumps(
            {
                "order_id": "t1",
                "timestamp": "2026-07-16T08:00:01+00:00",
                "symbol": "UNI/USD",
                "side": "buy",
                "qty": 1.0,
                "price": 3.0,
                "portfolio_value": 510.0,
            }
        )
        + "\n"
        + json.dumps(
            {
                "order_id": "t2",
                "timestamp": "2026-07-16T09:00:00+00:00",
                "symbol": "AAVE/USD",
                "side": "sell",
                "qty": 0.5,
                "price": 100.0,
                "profit": 1.2,
                "portfolio_value": 512.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    added = merge_and_export(root=root)
    assert added == 2

    data = (root / "data" / "kraken_trades.jsonl").read_text(encoding="utf-8")
    lines = [json.loads(x) for x in data.splitlines() if x.strip()]
    assert len(lines) == 2
    by_id = {r["trade_id"]: r for r in lines}
    assert by_id["t1"]["fee_usd"] == 0.01
    assert by_id["t1"]["portfolio_value_usd"] == 510.0
    assert by_id["t2"]["profit_usd"] == 1.2

    # Second run: no new ids
    added2 = merge_and_export(root=root)
    assert added2 == 0
    assert len((root / "data" / "kraken_trades.jsonl").read_text().splitlines()) == 2
    assert (root / "data" / "kraken_trades.csv").exists()
