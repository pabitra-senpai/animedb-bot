"""
Staff repository: upserts Staff rows and the AnimeStaff role links scoped
to a specific anime.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnimeStaff, Staff
from app.services.metadata_normalizer import NormalizedStaffEdge


async def _get_or_create_staff(session: AsyncSession, edge: NormalizedStaffEdge) -> Staff:
    result = await session.execute(select(Staff).where(Staff.anilist_id == edge.staff_anilist_id))
    staff = result.scalar_one_or_none()
    if staff is None:
        staff = Staff(
            anilist_id=edge.staff_anilist_id,
            name_full=edge.name_full,
            name_native=edge.name_native,
            image_url=edge.image_url,
        )
        session.add(staff)
        await session.flush()
    else:
        staff.name_full = edge.name_full
        staff.name_native = edge.name_native
        staff.image_url = edge.image_url
    return staff


async def upsert_staff_edge(session: AsyncSession, anime_id: int, edge: NormalizedStaffEdge) -> Staff:
    staff = await _get_or_create_staff(session, edge)

    link_result = await session.execute(
        select(AnimeStaff).where(
            AnimeStaff.anime_id == anime_id,
            AnimeStaff.staff_id == staff.id,
            AnimeStaff.role == edge.role,
        )
    )
    if link_result.scalar_one_or_none() is None:
        session.add(AnimeStaff(anime_id=anime_id, staff_id=staff.id, role=edge.role))

    return staff


async def get_cached_staff_count(session: AsyncSession, anime_id: int) -> int:
    result = await session.execute(select(AnimeStaff).where(AnimeStaff.anime_id == anime_id))
    return len(result.scalars().all())


async def get_cached_staff_page(
    session: AsyncSession, anime_id: int, page: int, per_page: int
) -> list[AnimeStaff]:
    offset = (page - 1) * per_page
    result = await session.execute(
        select(AnimeStaff)
        .where(AnimeStaff.anime_id == anime_id)
        .order_by(AnimeStaff.id)
        .offset(offset)
        .limit(per_page)
    )
    return list(result.scalars().all())
