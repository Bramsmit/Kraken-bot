"""Read-only Kraken runtime snapshots for Telegram (uses ExchangeClient only)."""

from __future__ import annotations

from rangebot.config.settings import (
    SYMBOL_POOL,
    SYMBOLS_ACTIVE,
    kraken_dry_run_from_env,
)
from rangebot.data.market_data import get_mid_price
from rangebot.exchange.base import ExchangeClient
from rangebot.exchange.kraken.client import make_exchange
from rangebot.exchange.kraken.state_and_fills import (
    fetch_open_orders,
    filter_kraken_usd_pool,
    load_kraken_trade_state,
)
from rangebot.execution.position_manager import (
    estimate_portfolio_usd,
    get_buying_power_usd,
    get_positions_map,
    ref_notional_for_range_selection,
)
from rangebot.strategy.signals import select_top_symbols_for_range


class KrakenTelegramService:
    """Collects formatted status lines without importing strategy/exchange ad hoc from handlers."""

    def connect(self) -> ExchangeClient:
        """Create Kraken client from environment (same as scheduled runner)."""
        return make_exchange()

    def dry_run_summary(self) -> str:
        env_on = kraken_dry_run_from_env()
        return (
            "Dry-run\n"
            f"- KRAKEN_DRY_RUN in omgeving: {'aan' if env_on else 'uit'} "
            "(default: aan tenzij expliciet false).\n"
            "- Voor live limits: zet KRAKEN_DRY_RUN=false in .env en herstart de runner."
        )

    def balance_summary(self, client: ExchangeClient) -> str:
        kr_pool = filter_kraken_usd_pool(client, SYMBOL_POOL)
        if not kr_pool:
            return "Geen bruikbare USD-markten in SYMBOL_POOL."
        cash = get_buying_power_usd(client)
        portfolio = estimate_portfolio_usd(client, kr_pool)
        return (
            "Balans (schatting)\n"
            f"- Vrije USD (incl. ZUSD): ${cash:.2f}\n"
            f"- Portfolio (USD schatting): ${portfolio:.2f}"
        )

    def positions_summary(self, client: ExchangeClient) -> str:
        kr_pool = filter_kraken_usd_pool(client, SYMBOL_POOL)
        if not kr_pool:
            return "Geen bruikbare markten; posities onbekend."
        ref_usd, _ = ref_notional_for_range_selection(
            client, kr_pool, symbols_active=SYMBOLS_ACTIVE
        )
        symbols, _levels, _ = select_top_symbols_for_range(
            client, kr_pool, SYMBOLS_ACTIVE, ref_usd
        )
        state = load_kraken_trade_state()
        entries = state.get("entries") or {}
        pos = get_positions_map(client, symbols or list(kr_pool[:SYMBOLS_ACTIVE]), entries)
        if not pos:
            return "Posities\n- Geen actieve posities (voor geselecteerde symbolen)."
        lines = ["Posities (vrije qty, avg entry uit state)"]
        for sym, (qty, avg) in sorted(pos.items()):
            lines.append(f"- {sym}: qty {qty:.8f}, avg ${avg:.4f}")
        return "\n".join(lines)

    def orders_summary(self, client: ExchangeClient) -> str:
        kr_pool = filter_kraken_usd_pool(client, SYMBOL_POOL)
        if not kr_pool:
            return "Geen markten; geen orders weergegeven."
        ref_usd, _ = ref_notional_for_range_selection(
            client, kr_pool, symbols_active=SYMBOLS_ACTIVE
        )
        symbols, _, _ = select_top_symbols_for_range(
            client, kr_pool, SYMBOLS_ACTIVE, ref_usd
        )
        watch = symbols if symbols else kr_pool[:SYMBOLS_ACTIVE]
        lines: list[str] = ["Open orders"]
        any_o = False
        for sym in watch:
            orders = fetch_open_orders(client, sym)
            for o in orders:
                any_o = True
                side = str(o.get("side", "?")).upper()
                px = o.get("price", "?")
                amt = o.get("remaining") or o.get("amount", "?")
                oid = str(o.get("id", "?"))[:12]
                lines.append(f"- {sym} {side} {amt} @ {px} (id …{oid})")
        if not any_o:
            lines.append("- Geen open orders op de geselecteerde symbolen.")
        return "\n".join(lines)

    def status_summary(self, client: ExchangeClient) -> str:
        kr_pool = filter_kraken_usd_pool(client, SYMBOL_POOL)
        if not kr_pool:
            return "⚠️ Kraken: geen bruikbare USD-markten in pool."
        ref_usd, _ = ref_notional_for_range_selection(
            client, kr_pool, symbols_active=SYMBOLS_ACTIVE
        )
        symbols, levels, _ = select_top_symbols_for_range(
            client, kr_pool, SYMBOLS_ACTIVE, ref_usd
        )
        state = load_kraken_trade_state()
        entries = state.get("entries") or {}
        portfolio = estimate_portfolio_usd(client, kr_pool)
        cash = get_buying_power_usd(client)
        positions = get_positions_map(client, symbols, entries)
        parts = [
            "Kraken range — status",
            f"- Dry-run (env): {'ja' if kraken_dry_run_from_env() else 'nee'}",
            f"- Client dry_run: {'ja' if client.dry_run else 'nee'}",
            f"- Vrije USD: ${cash:.2f} | Portfolio ~ ${portfolio:.2f}",
            f"- Geselecteerd: {', '.join(symbols) if symbols else '—'}",
            "",
            "Levels vs mid",
        ]
        for sym in symbols:
            if sym not in levels:
                continue
            buy_l, sell_l = levels[sym]
            mid = get_mid_price(client, sym)
            pos_qty, _ = positions.get(sym, (0.0, 0.0))
            mid_s = f"${mid:.4f}" if mid else "?"
            parts.append(
                f"- {sym} mid {mid_s} | buy ${buy_l:.4f} | sell ${sell_l:.4f} | "
                f"qty {pos_qty:.6f}"
            )
        return "\n".join(parts)
