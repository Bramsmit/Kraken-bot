"""Repository root discovery (for state files and journals at project root)."""

from __future__ import annotations

from pathlib import Path


def repository_root() -> Path:
    """Directory containing ``pyproject.toml`` (falls back to parents of this file)."""
    here = Path(__file__).resolve()
    for cand in [here, *here.parents]:
        if (cand / "pyproject.toml").exists():
            return cand
    return here.parents[4]
