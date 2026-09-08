"""
Character repository: upserts Character/VoiceActor rows and the
AnimeCharacter/CharacterVoiceActor links scoped to a specific anime.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnimeCharacter, Character, CharacterVoiceActor, VoiceActor
from app.services.metadata_normalizer import NormalizedCharacterEdge, NormalizedVoiceActor


async def _get_or_create_character(session: AsyncSession, edge: NormalizedCharacterEdge) -> Character:
    result = await session.execute(
        select(Character).where(Character.anilist_id == edge.character_anilist_id)
    )
    character = result.scalar_one_or_none()
    if character is None:
        character = Character(
            anilist_id=edge.character_anilist_id,
            name_full=edge.name_full,
            name_native=edge.name_native,
            image_url=edge.image_url,
        )
        session.add(character)
        await session.flush()
    else:
        character.name_full = edge.name_full
        character.name_native = edge.name_native
        character.image_url = edge.image_url
    return character


async def _get_or_create_voice_actor(session: AsyncSession, va: NormalizedVoiceActor) -> VoiceActor:
    result = await session.execute(select(VoiceActor).where(VoiceActor.anilist_id == va.anilist_id))
    voice_actor = result.scalar_one_or_none()
    if voice_actor is None:
        voice_actor = VoiceActor(
            anilist_id=va.anilist_id,
            name_full=va.name_full,
            name_native=va.name_native,
            image_url=va.image_url,
        )
        session.add(voice_actor)
        await session.flush()
    else:
        voice_actor.name_full = va.name_full
        voice_actor.name_native = va.name_native
        voice_actor.image_url = va.image_url
    return voice_actor


async def upsert_character_edge(
    session: AsyncSession, anime_id: int, edge: NormalizedCharacterEdge
) -> Character:
    character = await _get_or_create_character(session, edge)

    link_result = await session.execute(
        select(AnimeCharacter).where(
            AnimeCharacter.anime_id == anime_id, AnimeCharacter.character_id == character.id
        )
    )
    link = link_result.scalar_one_or_none()
    if link is None:
        session.add(AnimeCharacter(anime_id=anime_id, character_id=character.id, role=edge.role))
    else:
        link.role = edge.role

    for va in edge.voice_actors:
        voice_actor = await _get_or_create_voice_actor(session, va)
        cva_result = await session.execute(
            select(CharacterVoiceActor).where(
                CharacterVoiceActor.anime_id == anime_id,
                CharacterVoiceActor.character_id == character.id,
                CharacterVoiceActor.voice_actor_id == voice_actor.id,
                CharacterVoiceActor.language == va.language,
            )
        )
        if cva_result.scalar_one_or_none() is None:
            session.add(
                CharacterVoiceActor(
                    anime_id=anime_id,
                    character_id=character.id,
                    voice_actor_id=voice_actor.id,
                    language=va.language,
                )
            )

    return character


async def get_cached_character_count(session: AsyncSession, anime_id: int) -> int:
    result = await session.execute(select(AnimeCharacter).where(AnimeCharacter.anime_id == anime_id))
    return len(result.scalars().all())


async def get_cached_characters_page(
    session: AsyncSession, anime_id: int, page: int, per_page: int
) -> list[AnimeCharacter]:
    """Ordered by primary key ascending, which matches AniList's original
    ordering since links are inserted in the order the API returns them."""
    offset = (page - 1) * per_page
    result = await session.execute(
        select(AnimeCharacter)
        .where(AnimeCharacter.anime_id == anime_id)
        .order_by(AnimeCharacter.id)
        .offset(offset)
        .limit(per_page)
    )
    return list(result.scalars().all())


async def get_voice_actor_names(
    session: AsyncSession, anime_id: int, character_ids: list[int]
) -> dict[int, str]:
    if not character_ids:
        return {}
    result = await session.execute(
        select(CharacterVoiceActor).where(
            CharacterVoiceActor.anime_id == anime_id,
            CharacterVoiceActor.character_id.in_(character_ids),
        )
    )
    mapping: dict[int, str] = {}
    for link in result.scalars().all():
        mapping.setdefault(link.character_id, link.voice_actor.name_full)  # first VA wins
    return mapping
