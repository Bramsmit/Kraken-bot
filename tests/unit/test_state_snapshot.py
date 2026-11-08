"""Trade state survives Actions-cache loss via the committed data/ snapshot."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import rangebot.exchange.kraken.state_and_fills as saf


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(saf, "repository_root", lambda: tmp_path)
    return tmp_path


def _write(path: Path, entries: dict, updated_at: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {"entries": entries, "notified_trade_ids": ["t1"]}
    if updated_at is not None:
        data["updated_at"] = updated_at
    path.write_text(json.dumps(data))


def test_save_also_writes_committed_snapshot(root: Path) -> None:
    saf.save_kraken_state(entries={"UNI/USD": {"qty": 8.19, "entry": 9.40}})

    snap = json.loads((root / "data" / "kraken_state.json").read_text())
    assert snap["entries"]["UNI/USD"]["entry"] == 9.40
    assert snap["updated_at"]


def test_load_uses_snapshot_when_cache_file_is_missing(root: Path) -> None:
    _write(
        root / "data" / "kraken_state.json",
        {"UNI/USD": {"qty": 8.19, "entry": 9.40}},
        "2026-11-08T10:00:00+00:00",
    )

    state = saf.load_kraken_trade_state()

    assert state["entries"]["UNI/USD"]["entry"] == 9.40
    assert state["notified_trade_ids"] == ["t1"]


def test_load_prefers_newer_snapshot_over_stale_cache(root: Path) -> None:
    _write(root / ".kraken_trade_state.json", {"UNI/USD": {"qty": 8.19, "entry": 6.82}}, None)
    _write(
        root / "data" / "kraken_state.json",
        {"UNI/USD": {"qty": 8.19, "entry": 9.40}},
        "2026-11-08T10:00:00+00:00",
    )

    assert saf.load_kraken_trade_state()["entries"]["UNI/USD"]["entry"] == 9.40


class _TradesClient:
    def __init__(self, trades: list[dict]) -> None:
        self.trades = trades

    def fetch_my_trades(self, symbol: str, *, since_ms: int, limit: int) -> list[dict]:
        return [t for t in self.trades if t["symbol"] == symbol]


def _trade(tid: str, side: str, qty: float, price: float, ts_ms: int) -> dict:
    return {
        "id": tid,
        "symbol": "CRV/USD",
        "side": side,
        "amount": qty,
        "price": price,
        "timestamp": ts_ms,
        "fee": {"cost": qty * price * 0.004, "currency": "USD"},
    }


def test_fills_record_opened_at_of_first_buy(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("notify_trade_filled", "log_trade", "append_kraken_fill_audit"):
        monkeypatch.setattr(saf, name, lambda *a, **k: None)
    first_ms = 1_792_000_000_000
    client = _TradesClient(
        [
            _trade("b1", "buy", 100.0, 0.38, first_ms),
            _trade("b2", "buy", 50.0, 0.37, first_ms + 3_600_000),
            _trade("s1", "sell", 60.0, 0.39, first_ms + 7_200_000),
        ]
    )

    _, entries = saf.check_and_notify_kraken_fills(client, ["CRV/USD"], portfolio_usd=500.0)

    assert entries["CRV/USD"]["qty"] == pytest.approx(90.0)
    assert entries["CRV/USD"]["opened_at"].startswith("2026-10-14T17:46")


def test_load_prefers_newer_cache_over_older_snapshot(root: Path) -> None:
    _write(
        root / ".kraken_trade_state.json",
        {"ADA/USD": {"qty": 556.0, "entry": 0.2464}},
        "2026-11-08T12:00:00+00:00",
    )
    _write(
        root / "data" / "kraken_state.json",
        {"UNI/USD": {"qty": 8.19, "entry": 9.40}},
        "2026-11-08T10:00:00+00:00",
    )

    assert set(saf.load_kraken_trade_state()["entries"]) == {"ADA/USD"}
