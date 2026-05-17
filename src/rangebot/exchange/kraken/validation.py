"""Pre-trade checks for Kraken limit orders."""

from __future__ import annotations

from typing import Any, Literal

import ccxt

from rangebot.exchange.kraken.common import balance_entry, norm_symbol


class OrderValidationError(ValueError):
    """Raised when a limit order fails pre-trade checks."""


def _market_limits(
    ex: ccxt.kraken, symbol: str
) -> tuple[float | None, float | None, float | None, float | None]:
    """(min_amount, max_amount, min_cost, max_cost) from unified market if present."""
    m = ex.markets.get(symbol) or {}
    lim = m.get("limits") or {}
    amt = lim.get("amount") or {}
    cost = lim.get("cost") or {}
    return (
        _f(amt.get("min")),
        _f(amt.get("max")),
        _f(cost.get("min")),
        _f(cost.get("max")),
    )


def _f(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def kraken_limit_minimums(
    ex: ccxt.kraken, symbol: str
) -> tuple[float | None, float | None]:
    """Minimum base amount and minimum quote notional for a limit order, if known."""
    sym = norm_symbol(symbol)
    min_amt, _max_amt, min_cost, _max_cost = _market_limits(ex, sym)
    return min_amt, min_cost


def validate_limit_order_placement(
    ex: ccxt.kraken,
    balances: dict[str, Any],
    symbol: str,
    side: Literal["buy", "sell"],
    amount: float,
    price: float,
    *,
    max_position_value_usd: float | None,
    open_orders: list[dict[str, Any]],
) -> None:
    """
    Validate pair, size, balances, optional max position, and conflicting open orders.

    ``amount`` and ``price`` must already match exchange precision.
    """
    sym = norm_symbol(symbol)
    if sym not in ex.markets:
        raise OrderValidationError(f"Markt onbekend op Kraken: {sym}")
    mkt = ex.markets[sym]
    if not mkt.get("active", True):
        raise OrderValidationError(f"Markt niet actief: {sym}")

    if amount <= 0 or price <= 0:
        raise OrderValidationError(f"Ongeldige grootte of prijs voor {sym}")

    min_amt, max_amt, min_cost, max_cost = _market_limits(ex, sym)
    notional = amount * price
    if min_amt is not None and amount + 1e-12 < min_amt:
        raise OrderValidationError(
            f"Orderhoeveelheid {amount} < minimum {min_amt} voor {sym}"
        )
    if max_amt is not None and amount > max_amt:
        raise OrderValidationError(
            f"Orderhoeveelheid {amount} > maximum {max_amt} voor {sym}"
        )
    if min_cost is not None and notional + 1e-8 < min_cost:
        raise OrderValidationError(
            f"Ordertegoed ${notional:.4f} < minimum cost ${min_cost} voor {sym}"
        )
    if max_cost is not None and notional > max_cost:
        raise OrderValidationError(
            f"Ordertegoed ${notional:.4f} > maximum cost ${max_cost} voor {sym}"
        )

    base = sym.split("/")[0]
    quote = sym.split("/")[1]
    free_base, _ = balance_entry(balances, base)
    free_quote, _ = balance_entry(balances, quote)
    if quote == "USD" and free_quote <= 0:
        free_quote, _ = balance_entry(balances, "ZUSD")

    if side == "sell":
        if amount > free_base + 1e-10:
            raise OrderValidationError(
                f"Onvoldoende {base}: nodig {amount}, vrij {free_base} ({sym})"
            )
    else:
        required = notional
        if required > free_quote + 1e-6:
            raise OrderValidationError(
                f"Onvoldoende {quote}: nodig ~${required:.4f}, "
                f"vrij ~${free_quote:.4f} ({sym})"
            )

    if max_position_value_usd is not None and max_position_value_usd > 0 and side == "buy":
        projected_value = (free_base + amount) * price
        if projected_value > max_position_value_usd + 1e-6:
            raise OrderValidationError(
                f"Max positiewaarde ${max_position_value_usd:.2f} zou overschreden "
                f"worden (~${projected_value:.2f} na order) voor {sym}"
            )

    for o in open_orders:
        o_side = str(o.get("side") or "").lower()
        o_type = str(o.get("type") or "").lower()
        if o_side != side:
            continue
        if o_type in ("limit", "", "exchange limit"):
            raise OrderValidationError(
                f"Er staat al een open {side} limit op {sym} (order {o.get('id')}); "
                "annuleer eerst of gebruik vervang-logica."
            )
