"""
Freshness policy for cached Anime rows.

Kept as pure functions (no DB/HTTP) so the policy is trivially unit
testable and reusable from both the search flow and later background
sync jobs (Phase 7).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import Anime


def is_stale(anime: Anime, ttl_seconds: int) -> bool:
    """True if `anime` has never been synced, or was synced longer ago than
    the given TTL."""
    if anime.last_synced_at is None:
        return True

    last_synced = anime.last_synced_at
    if last_synced.tzinfo is None:
        last_synced = last_synced.replace(tzinfo=timezone.utc)

    age = datetime.now(timezone.utc) - last_synced
    return age.total_seconds() > ttl_seconds
