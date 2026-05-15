"""Trade notifications sent via Telegram."""

from __future__ import annotations

from rangebot.config.settings import (
    BITVAVO_FEE_BUY_RATE,
    BITVAVO_FEE_SELL_LIMIT_RATE,
    JOURNAL_FIXED_FEE_PER_FILL_USD,
    TELEGRAM_NOTIFY_BUY_FILLS,
)
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
    fee_buy_rate: float | None = None,
    fee_sell_rate: float | None = None,
    fixed_fee_per_fill: float | None = None,
    currency_label: str = "USD",
    fee_eur: float | None = None,
    fee_estimated: bool = False,
    send_telegram_message: bool | None = None,
) -> bool:
    """Notify a fill with optional PnL narrative (fee model from settings)."""
    r_buy = BITVAVO_FEE_BUY_RATE if fee_buy_rate is None else fee_buy_rate
    r_sell = BITVAVO_FEE_SELL_LIMIT_RATE if fee_sell_rate is None else fee_sell_rate
    fixed = (
        JOURNAL_FIXED_FEE_PER_FILL_USD
        if fixed_fee_per_fill is None
        else fixed_fee_per_fill
    )
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
        fee_buy = entry_price * qty * r_buy + fixed
        fee_sell = price * qty * r_sell + fixed
        fees_total = fee_buy + fee_sell
        net = gross - fee_buy - fee_sell
        cost_basis = entry_price * qty * (1 + r_buy) + fixed
        pct = (net / cost_basis * 100) if cost_basis else 0.0
        notional = qty * price
        msg = (
            f"✅ Afgeronde trade: {symbol}\n"
            f"Verkoop: {qty:.6f} @ {cur}{price:.4f} "
            f"(nominaal ≈ {cur}{notional:.2f})"
        )
        msg += f"\nReferentie inkoop (avg): {cur}{entry_price:.4f}"
        msg += f"\n📈 Bruto winst: {cur}{gross:.2f}"
        msg += f"\n📉 Transactiekosten (kopen): {cur}{fee_buy:.2f}"
        msg += f"\n📉 Transactiekosten (verkoop): {cur}{fee_sell:.2f}"
        msg += f"\n💸 Totaal fictieve kosten (model): {cur}{fees_total:.2f}"
        msg += (
            f"\n📊 Rendement na kosten: {cur}{net:.2f} "
            f"({pct:+.1f}% t.o.v. kostbasis)"
        )
    else:
        emoji = "🟢" if side_l == "buy" else "🔴"
        msg = f"{emoji} Trade: {side.upper()} {qty} {symbol} @ {cur}{price:.4f}"
        if side_l == "buy" and qty > 0 and price > 0:
            fee_pct_leg = price * qty * r_buy
            fee_buy_total = fee_pct_leg + fixed
            msg += f"\n📉 Transactiekosten (kopen): {cur}{fee_buy_total:.2f}"
            detail = f"maker {r_buy * 100:.2f}%: {cur}{fee_pct_leg:.2f}"
            if fixed > 0:
                detail += f", vast: {cur}{fixed:.2f}"
            msg += f"\n   ({detail})"
        elif side_l == "sell" and profit is not None:
            msg += f"\n✅ Netto (alleen bekend): {cur}{profit:.2f}"

    if fee_eur is not None:
        tag = " (≈ geschat)" if fee_estimated else ""
        msg += f"\n💡 Deze fill volgens exchange: {cur}{fee_eur:.2f}{tag}"

    msg += f"\n📊 Totaal portfolio: {cur}{portfolio_value:.2f}"
    return send_plain_message(msg)


def notify_stop_loss(symbol: str, qty: float, price: float) -> bool:
    """Notify a stop-loss exit."""
    q = _quote_for_symbol(symbol)
    msg = f"🛑 STOP-LOSS: {qty} {symbol} verkocht @ {q}{price:.4f}"
    return send_plain_message(msg)
