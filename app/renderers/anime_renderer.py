"""
Formats an `Anime` row into a Telegram-ready HTML message and inline
keyboard. Two length budgets matter here:

- Photo captions are capped at 1024 characters by Telegram.
- Plain text messages are capped at 4096.

`build_anime_detail_text()` takes the budget as a parameter so callers can
pick the right one depending on whether a poster photo is being sent.
"""

from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import Anime

PHOTO_CAPTION_LIMIT = 1024
TEXT_MESSAGE_LIMIT = 4096

_STATUS_EMOJI = {
    "RELEASING": "🟢 Airing",
    "FINISHED": "✅ Finished",
    "NOT_YET_RELEASED": "🕒 Upcoming",
    "CANCELLED": "❌ Cancelled",
    "HIATUS": "⏸️ On hiatus",
}

_FORMAT_LABELS = {
    "TV": "TV",
    "TV_SHORT": "TV Short",
    "MOVIE": "Movie",
    "SPECIAL": "Special",
    "OVA": "OVA",
    "ONA": "ONA",
    "MUSIC": "Music",
}


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    # Leave room for the ellipsis marker itself.
    return text[: max_chars - 1].rstrip() + "…"


def build_anime_detail_text(
    anime: Anime,
    max_chars: int,
    genre_names: list[str] | None = None,
    studio_names: list[str] | None = None,
) -> str:
    e = html.escape

    lines: list[str] = [f"🎬 <b>{e(anime.title)}</b>"]

    subtitle_bits = []
    if anime.english_title and anime.english_title != anime.title:
        subtitle_bits.append(e(anime.english_title))
    if anime.native_title and anime.native_title != anime.title:
        subtitle_bits.append(e(anime.native_title))
    if subtitle_bits:
        lines.append(" / ".join(subtitle_bits))

    lines.append("")  # blank line

    meta_bits = []
    if anime.format:
        meta_bits.append(_FORMAT_LABELS.get(anime.format, anime.format))
    if anime.status:
        meta_bits.append(_STATUS_EMOJI.get(anime.status, anime.status))
    if anime.season and anime.season_year:
        meta_bits.append(f"{anime.season.title()} {anime.season_year}")
    elif anime.season_year:
        meta_bits.append(str(anime.season_year))
    if meta_bits:
        lines.append(" · ".join(meta_bits))

    stat_bits = []
    if anime.score is not None:
        stat_bits.append(f"⭐ {anime.score}/10")
    if anime.rank:
        stat_bits.append(f"🏆 #{anime.rank} rated")
    if anime.episodes:
        stat_bits.append(f"📺 {anime.episodes} episodes")
    if anime.duration_minutes:
        stat_bits.append(f"⏱️ {anime.duration_minutes} min/ep")
    if stat_bits:
        lines.append(" · ".join(stat_bits))

    if anime.source_material:
        lines.append(f"📖 Source: {e(anime.source_material.replace('_', ' ').title())}")

    lines.append("")  # blank line before synopsis

    header_so_far = "\n".join(lines)
    # Reserve space for the header already built plus a trailing
    # genres/studios line and Telegram's own formatting overhead.
    reserved = len(header_so_far) + 80
    synopsis_budget = max(max_chars - reserved, 60)

    if anime.synopsis:
        synopsis = e(anime.synopsis.strip())
        lines.append(_truncate(synopsis, synopsis_budget))

    if genre_names:
        lines.append("")
        lines.append("🏷️ " + ", ".join(e(g) for g in genre_names))

    if studio_names:
        lines.append("🎨 " + ", ".join(e(s) for s in studio_names))

    text = "\n".join(lines)
    return _truncate(text, max_chars)


def build_anime_keyboard(
    anime: Anime,
    from_page: int | None = None,
    in_watchlist: bool = False,
    is_favorite: bool = False,
    current_rating: int | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    origin = str(from_page) if from_page is not None else "-"

    library_row = [
        InlineKeyboardButton(
            text="✅ In Watchlist" if in_watchlist else "➕ Watchlist",
            callback_data=f"wl:toggle:{anime.id}:{origin}",
        ),
        InlineKeyboardButton(
            text="💔 Unfavorite" if is_favorite else "❤️ Favorite",
            callback_data=f"fav:toggle:{anime.id}:{origin}",
        ),
        InlineKeyboardButton(
            text=f"⭐ Rated {current_rating}/10" if current_rating else "⭐ Rate",
            callback_data=f"rate:menu:{anime.id}:{origin}",
        ),
    ]
    rows.append(library_row)

    extras_row = [
        InlineKeyboardButton(text="📺 Episodes", callback_data=f"ep:list:{anime.id}:1:{origin}"),
        InlineKeyboardButton(text="🎭 Characters", callback_data=f"char:list:{anime.id}:1:{origin}"),
        InlineKeyboardButton(text="👥 Staff", callback_data=f"staff:list:{anime.id}:1:{origin}"),
    ]
    rows.append(extras_row)

    if anime.trailer_url:
        rows.append([InlineKeyboardButton(text="▶️ Trailer", url=anime.trailer_url)])

    if from_page is not None:
        rows.append(
            [InlineKeyboardButton(text="🔙 Back to results", callback_data=f"anime:back:{from_page}")]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)
