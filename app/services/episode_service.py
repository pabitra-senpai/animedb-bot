"""
Episode list display logic. Deliberately avoids materializing placeholder
Episode rows for shows with huge episode counts (One Piece, Sazae-san) —
it computes the visible page from `Anime.episodes` (the known total) and
overlays whatever real Episode rows exist (titles/thumbnails synced from
AniList's streamingEpisodes, currently only the recent-ish episodes for
most shows; full historical episode data arrives with Kitsu in Phase 7).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime, Episode


@dataclass
class EpisodeDisplay:
    number: int
    title: str | None
    air_date: date | None


async def get_episode_page(
    session: AsyncSession, anime: Anime, page: int, per_page: int = 10
) -> tuple[list[EpisodeDisplay], bool]:
    result = await session.execute(select(Episode).where(Episode.anime_id == anime.id))
    real_by_number = {e.episode_number: e for e in result.scalars().all()}

    total = anime.episodes

    if total:
        start = (page - 1) * per_page + 1
        if start > total:
            return [], False
        end = min(start + per_page - 1, total)
        numbers = list(range(start, end + 1))
        has_next = end < total
    else:
        # Unknown total (e.g. still airing without a confirmed count) —
        # only show episodes we actually have synced data for.
        sorted_numbers = sorted(real_by_number.keys())
        offset = (page - 1) * per_page
        numbers = sorted_numbers[offset : offset + per_page]
        has_next = len(sorted_numbers) > offset + per_page
        if not numbers:
            return [], False

    display = [
        EpisodeDisplay(
            number=n,
            title=real_by_number[n].title if n in real_by_number else None,
            air_date=real_by_number[n].air_date if n in real_by_number else None,
        )
        for n in numbers
    ]
    return display, has_next
