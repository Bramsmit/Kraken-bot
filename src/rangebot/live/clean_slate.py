#!/usr/bin/env python3
"""
Annuleer alle open orders in ``SYMBOL_POOL`` en reset trade state.

Gebruik na handmatige USD-reset op Kraken voor een schone start met portfolio÷3 sizing.
"""

from __future__ import annotations

import os

from rangebot.config.settings import SYMBOL_POOL, SYMBOLS_ACTIVE
from rangebot.exchange.kraken import create_kraken_client, filter_kraken_usd_pool
from rangebot.execution.position_manager import (
    capital_per_active_symbol_usd,
    estimate_portfolio_usd,
    get_buying_power_usd,
)
from rangebot.live.reset_state import reset_kraken_trade_state
from rangebot.utils.paths import repository_root


def _load_dotenv_if_present() -> None:
    env_path = repository_root() / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"'))


def cancel_all_pool_orders(client) -> int:
    total = 0
    for symbol in SYMBOL_POOL:
        try:
            orders = client.get_open_orders(symbol)
        except Exception as e:
            print(f"  Fout open orders {symbol}: {e}")
            continue
        for o in orders:
            try:
                client.cancel_order(str(o["id"]), symbol)
                print(
                    f"  Geannuleerd: {symbol} {o.get('side', '?')} "
                    f"@ {o.get('price', '?')} (id={str(o.get('id', ''))[:12]})"
                )
                total += 1
            except Exception as e:
                print(f"  Fout annuleren {o.get('id')}: {e}")
    return total


def main() -> None:
    _load_dotenv_if_present()
    try:
        client = create_kraken_client()
    except ValueError as e:
        print(f"❌ {e}")
        return

    kr_pool = filter_kraken_usd_pool(client, SYMBOL_POOL)
    cash = get_buying_power_usd(client)
    port = estimate_portfolio_usd(client, kr_pool)
    per_slot = capital_per_active_symbol_usd(
        portfolio_equity_usd=port,
        free_quote_usd=cash,
        n_symbols=SYMBOLS_ACTIVE,
    )

    print("=== Clean slate ===")
    print(f"Portfolio ~ ${port:.2f} | Vrije USD ${cash:.2f}")
    print(f"Doel per slot (max {SYMBOLS_ACTIVE}): ~ ${per_slot:.2f} (~1/{SYMBOLS_ACTIVE} totaal)")
    print("Open orders annuleren...")

    n = cancel_all_pool_orders(client)
    reset_kraken_trade_state()
    print(f"\n✅ {n} order(s) geannuleerd; trade state gereset.")
    print(
        "Volgende bot-run plaatst max 3 buys à ~1/3 portfolio "
        "(zolang alles USD is)."
    )


if __name__ == "__main__":
    main()
