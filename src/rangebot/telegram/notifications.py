"""Trade notifications sent via Telegram."""

from __future__ import annotations

from rangebot.config.settings import TELEGRAM_NOTIFY_BUY_FILLS
from rangebot.telegram.client import send_plain_message


def _quote_for_symbol(symbol: str) -> str:
    """EUR pairs as €, USD as $."""
    s = symbol.upper()
    if "/EUR" in s or s.endswith("EUR"):
        return "€"
    return "$"


def notify_trade(
    side: str, symbol: str, qty: float, price: float, order_id: str = ""
) -> bool:
    """Notify a submitted order (optional use)."""
    q = _quote_for_symbol(symbol)
    emoji = "🟢" if side.lower() == "buy" else "🔴"
    msg = f"{emoji} {side.upper()}: {qty} {symbol} @ {q}{price:.4f}"
    if order_id:
        msg += f"\nOrder ID: {order_id}"
    return send_plain_message(msg)


def _currency_prefix(currency_label: str) -> str:
    return "€" if currency_label.upper() == "EUR" else "$"


def notify_trade_filled(
    side: str,
    symbol: str,
    qty: float,
    price: float,
    profit: float | None,
    portfolio_value: float,
    entry_price: float | None = None,
    *,
    currency_label: str = "USD",
    send_telegram_message: bool | None = None,
    exchange_fee_usd: float | None = None,
    exchange_buy_fee_usd: float | None = None,
    exchange_sell_fee_usd: float | None = None,
) -> bool:
    """Notify a fill using Kraken/ccxt fee amounts when available."""
    cur = _currency_prefix(currency_label)
    side_l = side.lower()
    if send_telegram_message is None:
        send_tg = TELEGRAM_NOTIFY_BUY_FILLS or side_l != "buy"
    else:
        send_tg = send_telegram_message
    if not send_tg:
        return True

    if side_l == "sell" and qty > 0 and entry_price and entry_price > 0:
        gross = (price - entry_price) * qty
        notional = qty * price
        bb = exchange_buy_fee_usd
        sb = exchange_sell_fee_usd
        msg = (
            f"✅ Afgeronde trade: {symbol}\n"
            f"Verkoop: {qty:.6f} @ {cur}{price:.4f} "
            f"(nominaal ≈ {cur}{notional:.2f})"
        )
        msg += f"\nReferentie inkoop (avg): {cur}{entry_price:.4f}"
        msg += f"\n📈 Bruto winst: {cur}{gross:.2f}"
        if bb is not None:
            msg += f"\n📉 Transactiekosten Kraken (koop): {cur}{bb:.2f}"
        if sb is not None:
            msg += f"\n📉 Transactiekosten Kraken (verkoop): {cur}{sb:.2f}"
        if bb is not None and sb is not None:
            tot = bb + sb
            msg += f"\n💸 Totaal transactiekosten Kraken: {cur}{tot:.2f}"
            net = gross - tot
        elif sb is not None:
            net = gross - sb
        elif bb is not None:
            net = gross - bb
        else:
            net = gross
            msg += "\n💡 Geen fee-bedragen in Kraken trade-response (ccxt)."
        if bb is not None or sb is not None:
            cost_basis = entry_price * qty + (bb or 0)
            pct = (net / cost_basis * 100) if cost_basis else 0.0
            msg += (
                f"\n📊 Rendement na Kraken-kosten: {cur}{net:.2f} "
                f"({pct:+.1f}% t.o.v. kosten + inkoop)"
            )
        elif profit is not None:
            msg += f"\n📊 Netto (journal): {cur}{profit:.2f}"
    else:
        emoji = "🟢" if side_l == "buy" else "🔴"
        msg = f"{emoji} Trade: {side.upper()} {qty} {symbol} @ {cur}{price:.4f}"
        if side_l == "buy" and qty > 0 and price > 0:
            if exchange_fee_usd is not None:
                msg += f"\n📉 Transactiekosten Kraken: {cur}{exchange_fee_usd:.2f}"
            else:
                msg += "\n💡 Geen fee in Kraken trade-response (ccxt)."
        elif side_l == "sell" and profit is not None:
            msg += f"\n✅ Netto (journal): {cur}{profit:.2f}"

    msg += f"\n📊 Totaal portfolio: {cur}{portfolio_value:.2f}"
    return send_plain_message(msg)


def notify_stop_loss(symbol: str, qty: float, price: float) -> bool:
    """Notify a stop-loss exit."""
    q = _quote_for_symbol(symbol)
    msg = f"🛑 STOP-LOSS: {qty} {symbol} verkocht @ {q}{price:.4f}"
    return send_plain_message(msg)
