"""Per-run equity rows in data/kraken_equity.csv."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import rangebot.live.equity_log as eq


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(eq, "repository_root", lambda: tmp_path)
    return tmp_path


def test_append_writes_header_once_and_reads_back(root) -> None:
    t1 = datetime(2026, 11, 8, 10, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 8, 11, tzinfo=timezone.utc)
    eq.append_equity_row(
        equity_usd=515.0,
        cash_usd=183.0,
        positions_usd={"CRV/USD": 120.0, "ADA/USD": 136.4},
        now=t1,
    )
    eq.append_equity_row(
        equity_usd=510.0, cash_usd=183.0, positions_usd={}, now=t2
    )

    lines = (root / "data" / "kraken_equity.csv").read_text().splitlines()
    assert lines[0] == "timestamp,equity_usd,cash_usd,deployed_pct,positions"
    assert len(lines) == 3

    rows = eq.read_equity_rows()
    assert [r.equity_usd for r in rows] == [515.0, 510.0]
    assert rows[0].timestamp == t1
    assert rows[0].deployed_pct == pytest.approx(256.4 / 515.0, abs=1e-4)
    assert rows[0].positions == "ADA:136.40;CRV:120.00"
    assert rows[1].positions == ""


def test_read_missing_file_returns_empty() -> None:
    assert eq.read_equity_rows() == []


def test_read_skips_malformed_rows(root) -> None:
    path = root / "data" / "kraken_equity.csv"
    path.parent.mkdir(parents=True)
    path.write_text(
        "timestamp,equity_usd,cash_usd,deployed_pct,positions\n"
        "garbage,,,,\n"
        "2026-11-08T10:00:00+00:00,515.0,183.0,0.6447,\n"
    )
    rows = eq.read_equity_rows()
    assert len(rows) == 1
    assert rows[0].equity_usd == 515.0
