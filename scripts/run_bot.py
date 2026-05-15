#!/usr/bin/env python3
"""Run the Kraken range bot once (with retries), same as ``python -m rangebot.main``."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rangebot.main import main

if __name__ == "__main__":
    main()
