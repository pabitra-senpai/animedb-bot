from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.search import send_anime_detail
from app.db.models import Anime, AnimeGenre, Genre, User
from app.db.repositories.library_repository import list_history


class _StubMessage:
    """Duck-types the subset of aiogram.types.Message that send_anime_detail uses."""

    def __init__(self, fail_photo: bool = False) -> None:
        self.fail_photo = fail_photo
        self.photo_calls: list[dict] = []
        self.text_calls: list[dict] = []

    async def answer_photo(self, photo, caption, reply_markup=None):
        if self.fail_photo:
            raise RuntimeError("simulated Telegram API failure")
        self.photo_calls.append({"photo": photo, "caption": caption, "reply_markup": reply_markup})

    async def answer(self, text, reply_markup=None):
        self.text_calls.append({"text": text, "reply_markup": reply_markup})


async def _make_user(session: AsyncSession) -> User:
    user = User(telegram_user_id=1, first_name="Pabitra")
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_sends_photo_when_poster_available(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", poster_url="https://example.com/poster.jpg")
    session.add(anime)
    await session.flush()
    user = await _make_user(session)
    await session.commit()

    target = _StubMessage()
    await send_anime_detail(target, anime, session, user, from_page=1)

    assert len(target.photo_calls) == 1
    assert target.text_calls == []
    assert target.photo_calls[0]["photo"] == "https://example.com/poster.jpg"


@pytest.mark.asyncio
async def test_falls_back_to_text_when_no_poster(session: AsyncSession) -> None:
    anime = Anime(title="Untitled", poster_url=None)
    session.add(anime)
    await session.flush()
    user = await _make_user(session)
    await session.commit()

    target = _StubMessage()
    await send_anime_detail(target, anime, session, user, from_page=None)

    assert target.photo_calls == []
    assert len(target.text_calls) == 1
    assert "Untitled" in target.text_calls[0]["text"]


@pytest.mark.asyncio
async def test_falls_back_to_text_when_photo_send_fails(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", poster_url="https://example.com/broken.jpg")
    session.add(anime)
    await session.flush()
    user = await _make_user(session)
    await session.commit()

    target = _StubMessage(fail_photo=True)
    await send_anime_detail(target, anime, session, user, from_page=1)

    assert target.photo_calls == []
    assert len(target.text_calls) == 1
    assert "One Piece" in target.text_calls[0]["text"]


@pytest.mark.asyncio
async def test_includes_genre_names_in_caption(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", poster_url="https://example.com/poster.jpg")
    genre = Genre(name="Adventure")
    session.add_all([anime, genre])
    await session.flush()
    session.add(AnimeGenre(anime_id=anime.id, genre_id=genre.id))
    user = await _make_user(session)
    await session.commit()

    target = _StubMessage()
    await send_anime_detail(target, anime, session, user, from_page=None)

    assert "Adventure" in target.photo_calls[0]["caption"]


@pytest.mark.asyncio
async def test_records_history_on_view(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", poster_url="https://example.com/poster.jpg")
    session.add(anime)
    await session.flush()
    user = await _make_user(session)
    await session.commit()

    target = _StubMessage()
    await send_anime_detail(target, anime, session, user, from_page=None)
    await session.commit()

    items, _ = await list_history(session, user.id, page=1, per_page=10)
    assert len(items) == 1
    assert items[0].anime_id == anime.id


@pytest.mark.asyncio
async def test_caption_reflects_watchlist_and_rating_state(session: AsyncSession) -> None:
    from app.db.repositories.library_repository import set_rating, toggle_watchlist

    anime = Anime(title="One Piece", poster_url="https://example.com/poster.jpg")
    session.add(anime)
    await session.flush()
    user = await _make_user(session)
    await toggle_watchlist(session, user.id, anime.id)
    await set_rating(session, user.id, anime.id, 9)
    await session.commit()

    target = _StubMessage()
    await send_anime_detail(target, anime, session, user, from_page=None)

    keyboard = target.photo_calls[0]["reply_markup"]
    library_row_texts = [b.text for b in keyboard.inline_keyboard[0]]
    assert "✅ In Watchlist" in library_row_texts
    assert "⭐ Rated 9/10" in library_row_texts
