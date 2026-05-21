#!/usr/bin/env python3
"""Reset ``.kraken_trade_state.json`` (entries, notified ids, fee tally)."""

from __future__ import annotations

import os

from rangebot.exchange.kraken.state_and_fills import save_kraken_state
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


def reset_kraken_trade_state() -> None:
    save_kraken_state(
        entries={},
        notified_trade_ids=[],
        cumulative_kraken_fees_usd=0.0,
    )


def main() -> None:
    _load_dotenv_if_present()
    reset_kraken_trade_state()
    path = repository_root() / ".kraken_trade_state.json"
    print(f"✅ Kraken trade state gereset: {path}")


if __name__ == "__main__":
    main()
