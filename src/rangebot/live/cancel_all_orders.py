#!/usr/bin/env python3
"""Annuleer alle open orders op Kraken (via .env credentials)."""

from __future__ import annotations

import os

from rangebot.config.settings import SYMBOL_POOL
from rangebot.exchange.kraken import create_kraken_client
from rangebot.utils.paths import repository_root


def _load_dotenv_if_present() -> None:
    env_path = repository_root() / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"'))


def main() -> None:
    _load_dotenv_if_present()
    try:
        client = create_kraken_client()
    except ValueError as e:
        print(f"❌ {e}")
        return

    api_key = os.environ.get("KRAKEN_API_KEY", "")
    print(f"⚠️  Kraken account: {api_key[:8]}...")
    print("Open orders ophalen...")

    total_cancelled = 0
    for symbol in SYMBOL_POOL:
        try:
            orders = client.get_open_orders(symbol)
            for o in orders:
                try:
                    client.cancel_order(o["id"], symbol)
                    print(
                        f"  Geannuleerd: {symbol} {o.get('side', '?')} @ "
                        f"{o.get('price', '?')} (id={o['id'][:8]})"
                    )
                    total_cancelled += 1
                except Exception as e:
                    print(f"  Fout bij annuleren {o['id']}: {e}")
        except Exception as e:
            print(f"  Fout bij ophalen orders {symbol}: {e}")

    print(f"\nKlaar. {total_cancelled} order(s) geannuleerd.")


if __name__ == "__main__":
    main()
