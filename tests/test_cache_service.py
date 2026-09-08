from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.models import Anime
from app.services.cache_service import is_stale


def test_never_synced_is_stale() -> None:
    anime = Anime(title="X", last_synced_at=None)
    assert is_stale(anime, ttl_seconds=3600) is True


def test_recently_synced_is_not_stale() -> None:
    anime = Anime(title="X", last_synced_at=datetime.now(timezone.utc) - timedelta(seconds=10))
    assert is_stale(anime, ttl_seconds=3600) is False


def test_old_sync_is_stale() -> None:
    anime = Anime(title="X", last_synced_at=datetime.now(timezone.utc) - timedelta(hours=2))
    assert is_stale(anime, ttl_seconds=3600) is True


def test_naive_datetime_treated_as_utc() -> None:
    # SQLite round-trips can strip tzinfo; the policy must not crash on it.
    anime = Anime(title="X", last_synced_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=10))
    assert is_stale(anime, ttl_seconds=3600) is False
