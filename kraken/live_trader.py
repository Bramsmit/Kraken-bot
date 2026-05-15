"""Compatibility entrypoint — canonical implementation: ``rangebot.main``."""

from __future__ import annotations

from rangebot.main import main, run_once
from rangebot.strategy.signals import (
    select_top_symbols_for_range,
    select_top_symbols_kraken,
)

__all__ = [
    "main",
    "run_once",
    "select_top_symbols_for_range",
    "select_top_symbols_kraken",
]

if __name__ == "__main__":
    main()
