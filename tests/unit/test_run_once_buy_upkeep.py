"""run_once buy-order upkeep: orphan buys and dust balances."""

from __future__ import annotations

import time
from typing import Any

import pytest

import rangebot.main as main


class FakeClient:
    def __init__(
        self,
        open_orders: dict[str, list[dict[str, Any]]],
        positions: dict[str, tuple[float, float]],
    ) -> None:
        self.dry_run = False
        self.open_orders = open_orders
        self.positions = positions
        self.cancelled: list[tuple[str, str]] = []
        self.placed: list[tuple[str, str, float, float]] = []

    def get_open_orders(self, symbol: str) -> list[dict[str, Any]]:
        return list(self.open_orders.get(symbol, []))

    def cancel_order(self, order_id: str, symbol: str) -> None:
        self.cancelled.append((symbol, order_id))
        self.open_orders[symbol] = [
            o for o in self.open_orders.get(symbol, []) if o["id"] != order_id
        ]

    def place_order(self, symbol, side, order_type, amount, price, *, params=None):
        self.placed.append((symbol, side, float(amount), float(price)))
        return {"id": f"new-{symbol}-{side}"}

    def get_open_positions(self, symbols: list[str]) -> dict[str, tuple[float, float]]:
        return {s: (self.positions.get(s, (0.0, 0.0))[0],) * 2 for s in symbols}

    def maker_safe_limit_buy_price(self, symbol: str, desired: float) -> float:
        return desired

    def limit_order_minimums(self, symbol: str) -> tuple[float, float]:
        return 3.9, 0.5


def _buy(order_id: str, price: float, amount: float) -> dict[str, Any]:
    return {
        "id": order_id,
        "side": "buy",
        "type": "limit",
        "price": price,
        "amount": amount,
        "remaining": amount,
        "timestamp": int(time.time() * 1000),
    }


@pytest.fixture
def run(monkeypatch):
    def _run(
        *,
        symbols: list[str],
        levels: dict[str, tuple[float, float]],
        mids: dict[str, float],
        positions: dict[str, tuple[float, float]],
        open_orders: dict[str, list[dict[str, Any]]],
        pool: list[str],
    ) -> FakeClient:
        client = FakeClient(open_orders, positions)
        held = [s for s, (q, _) in positions.items() if q > 0]
        scored = {s: (b, sl, 0.05) for s, (b, sl) in levels.items()}

        patches = {
            "is_trading_paused": lambda: False,
            "make_exchange": lambda: client,
            "filter_kraken_usd_pool": lambda c, p: list(pool),
            "ref_notional_for_range_selection": lambda c, p, symbols_active: (55.0, 600.0),
            "select_top_symbols_for_range": lambda c, p, n, ref: (
                list(symbols), dict(levels), scored, dict(mids)
            ),
            "_log_and_build_selection_debug": lambda *a, **k: {},
            "symbols_with_balance": lambda c, p: list(held),
            "estimate_portfolio_usd": lambda c, p: 600.0,
            "check_and_notify_kraken_fills": lambda c, p, portfolio_usd: (0, {}),
            "get_mid_price": lambda c, s: mids.get(s),
            "get_positions_map": lambda c, syms, entries: {
                s: positions.get(s, (0.0, 0.0)) for s in syms
            },
            "get_buying_power_usd": lambda c: 110.0,
            "persist_entries_from_balances": lambda *a, **k: {},
            "save_kraken_state": lambda **k: None,
            "log_run_audit": lambda *a, **k: None,
            "send_telegram": lambda *a, **k: None,
            "ORDER_REPLACE_DELAY_SEC": 0,
        }
        for name, value in patches.items():
            monkeypatch.setattr(main, name, value)

        main.run_once()
        return client

    return _run


def test_cancels_buy_on_symbol_outside_selection(run) -> None:
    client = run(
        symbols=["UNI/USD"],
        levels={"UNI/USD": (8.84, 8.97)},
        mids={"UNI/USD": 8.86},
        positions={},
        open_orders={
            "UNI/USD": [_buy("uni-1", 8.84, 6.0)],
            "AAVE/USD": [_buy("aave-1", 169.23, 0.6)],
        },
        pool=["UNI/USD", "AAVE/USD"],
    )

    assert ("AAVE/USD", "aave-1") in client.cancelled
    assert ("UNI/USD", "uni-1") not in client.cancelled


def test_keeps_sell_on_symbol_outside_selection(run) -> None:
    sell = {**_buy("uni-sell", 9.49, 8.19), "side": "sell"}
    client = run(
        symbols=["ADA/USD"],
        levels={"ADA/USD": (0.2563, 0.2703)},
        mids={"ADA/USD": 0.2715},
        positions={},
        open_orders={"UNI/USD": [sell]},
        pool=["ADA/USD", "UNI/USD"],
    )

    assert ("UNI/USD", "uni-sell") not in client.cancelled


@pytest.mark.parametrize(
    ("symbol", "dust_qty", "levels", "mid", "stale_buy_px"),
    [
        ("ADA/USD", 2.2e-06, (0.2563, 0.2703), 0.2715, 0.2065),
        ("DOT/USD", 0.0035486736, (1.1919, 1.2183), 1.2208, 1.1531),
    ],
)
def test_dust_balance_does_not_freeze_stale_buy(
    run, symbol, dust_qty, levels, mid, stale_buy_px
) -> None:
    client = run(
        symbols=[symbol],
        levels={symbol: levels},
        mids={symbol: mid},
        positions={symbol: (dust_qty, 0.0)},
        open_orders={symbol: [_buy("stale-1", stale_buy_px, 100.0)]},
        pool=[symbol],
    )

    assert (symbol, "stale-1") in client.cancelled
    buys = [p for p in client.placed if p[0] == symbol and p[1] == "buy"]
    assert len(buys) == 1
    assert buys[0][3] == pytest.approx(levels[0], rel=1e-3)
