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
        self.telegram: list[str] = []
        self.equity_rows: list[dict[str, Any]] = []

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
        out = {}
        for s in symbols:
            total = self.positions.get(s, (0.0, 0.0))[0]
            locked = sum(
                float(o["remaining"])
                for o in self.open_orders.get(s, [])
                if o["side"] == "sell"
            )
            out[s] = (max(0.0, total - locked), total)
        return out

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
        free_usd: float = 110.0,
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
            "get_buying_power_usd": lambda c: free_usd,
            "persist_entries_from_balances": lambda *a, **k: {},
            "save_kraken_state": lambda **k: None,
            "log_run_audit": lambda *a, **k: None,
            "send_telegram": lambda msg, *a, **k: client.telegram.append(msg),
            "append_equity_row": lambda **k: client.equity_rows.append(k),
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


def test_sell_order_at_fee_floor_not_cancelled_when_price_far_below_target(
    run,
) -> None:
    """
    Bug-regressie: CRV/UNI/ADA staan ~30% onder hun fee_floor sell-order.
    Omdat limit_sell == fee_floor == old_sell_price (price_diff == 0), mag de
    bot NIET elk uur dezelfde sell-order annuleren en opnieuw plaatsen.
    """
    entry_px = 9.4014
    # fee_floor = 9.4014 * (1 + 0.006 + 0.003) = 9.4860126
    existing_sell_px = 9.4860
    sell_ord = {
        **_buy("uni-sell-floor", existing_sell_px, 8.188),
        "side": "sell",
        "timestamp": int((time.time() - 30 * 3600) * 1000),  # >24u oud
    }
    client = run(
        symbols=["UNI/USD"],
        levels={"UNI/USD": (7.05, 7.35)},  # sell_level (7.35) < fee_floor (9.486)
        mids={"UNI/USD": 7.18},  # >30% onder limit_sell
        positions={"UNI/USD": (8.188, entry_px)},
        open_orders={"UNI/USD": [sell_ord]},
        pool=["UNI/USD"],
    )

    assert ("UNI/USD", "uni-sell-floor") not in client.cancelled
    sells_placed = [p for p in client.placed if p[0] == "UNI/USD" and p[1] == "sell"]
    assert len(sells_placed) == 0


def test_unknown_entry_places_no_sell_and_alerts(run) -> None:
    client = run(
        symbols=["CRV/USD"],
        levels={"CRV/USD": (0.255, 0.27)},
        mids={"CRV/USD": 0.262},
        positions={"CRV/USD": (456.0, 0.0)},
        open_orders={},
        pool=["CRV/USD"],
    )

    assert not [p for p in client.placed if p[0] == "CRV/USD" and p[1] == "sell"]
    assert any("CRV/USD" in m and "instap onbekend" in m for m in client.telegram)


def test_unknown_entry_keeps_existing_sell(run) -> None:
    sell = {**_buy("crv-sell", 0.3857, 456.0), "side": "sell"}
    client = run(
        symbols=["CRV/USD"],
        levels={"CRV/USD": (0.255, 0.27)},
        mids={"CRV/USD": 0.262},
        positions={"CRV/USD": (456.0, 0.0)},
        open_orders={"CRV/USD": [sell]},
        pool=["CRV/USD"],
    )

    assert ("CRV/USD", "crv-sell") not in client.cancelled
    assert not [p for p in client.placed if p[0] == "CRV/USD" and p[1] == "sell"]


def test_resting_buy_cancelled_while_position_is_held(run) -> None:
    sell = {**_buy("uni-sell", 9.486, 8.188), "side": "sell"}
    client = run(
        symbols=["UNI/USD"],
        levels={"UNI/USD": (7.05, 7.35)},
        mids={"UNI/USD": 7.18},
        positions={"UNI/USD": (8.188, 9.4014)},
        open_orders={"UNI/USD": [sell, _buy("uni-buy-rest", 7.05, 4.0)]},
        pool=["UNI/USD"],
    )

    assert ("UNI/USD", "uni-buy-rest") in client.cancelled
    assert ("UNI/USD", "uni-sell") not in client.cancelled


def test_sell_replaced_when_it_does_not_cover_all_held_qty(run) -> None:
    sell = {**_buy("uni-sell", 9.486, 8.188), "side": "sell"}
    client = run(
        symbols=["UNI/USD"],
        levels={"UNI/USD": (7.05, 7.35)},
        mids={"UNI/USD": 7.18},
        positions={"UNI/USD": (12.0, 9.4014)},
        open_orders={"UNI/USD": [sell]},
        pool=["UNI/USD"],
    )

    assert ("UNI/USD", "uni-sell") in client.cancelled
    sells = [p for p in client.placed if p[0] == "UNI/USD" and p[1] == "sell"]
    assert len(sells) == 1
    assert sells[0][2] == pytest.approx(12.0)
    assert sells[0][3] == pytest.approx(9.486, rel=1e-3)


def test_run_appends_equity_row_with_all_held_positions(run) -> None:
    sell = {**_buy("uni-sell", 9.486, 8.188), "side": "sell"}
    client = run(
        symbols=["ADA/USD"],
        levels={"ADA/USD": (0.2563, 0.2703)},
        mids={"ADA/USD": 0.2715, "UNI/USD": 7.18},
        positions={"UNI/USD": (8.188, 9.4014)},
        open_orders={"UNI/USD": [sell]},
        pool=["ADA/USD", "UNI/USD"],
    )

    assert len(client.equity_rows) == 1
    row = client.equity_rows[0]
    assert row["equity_usd"] == pytest.approx(600.0)
    assert row["positions_usd"] == {"UNI/USD": pytest.approx(8.188 * 7.18)}


def test_last_free_buy_slot_capped_by_max_position_pct(run) -> None:
    """
    Wanneer 1 koopslot vrij is en er veel vrije USD / deploy_room is, mag de
    laatste buy-order niet >20% van de portefeuille ($600 * 0.20 = $120) pakken.
    """
    client = run(
        symbols=["UNI/USD", "ADA/USD", "CRV/USD"],
        levels={
            "UNI/USD": (7.0, 7.5),
            "ADA/USD": (0.20, 0.22),
            "CRV/USD": (0.30, 0.33),
        },
        mids={"UNI/USD": 7.1, "ADA/USD": 0.20, "CRV/USD": 0.305},
        positions={
            "UNI/USD": (10.0, 7.1),   # ~$71
            "ADA/USD": (350.0, 0.20),  # ~$70 (samen $141 deployed op $600 eq -> $249 deploy_room)
        },
        open_orders={},
        pool=["UNI/USD", "ADA/USD", "CRV/USD"],
        free_usd=300.0,
    )

    crv_buys = [p for p in client.placed if p[0] == "CRV/USD" and p[1] == "buy"]
    assert len(crv_buys) == 1
    _, _, qty, px = crv_buys[0]
    notional = qty * px
    # Zonder cap zou dit min($300 cash, $219 deploy_room) = $219 zijn;
    # met KRAKEN_MAX_POSITION_PCT=0.20 op $600 is het exact begrensd op $120.
    assert notional == pytest.approx(600.0 * 0.20, rel=1e-3)

