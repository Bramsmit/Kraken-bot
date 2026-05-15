"""Small time helpers (UTC)."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Current UTC ``datetime`` with tzinfo set."""
    return datetime.now(timezone.utc)
