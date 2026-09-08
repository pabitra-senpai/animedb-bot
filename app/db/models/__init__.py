"""
Importing this module registers every model against `Base.metadata`.

Alembic's env.py imports this module (not individual model files) so
autogenerate always sees the complete schema. Add new model modules here
as they're created in later phases.
"""

from app.db.base import Base
from app.db.models.anime import Anime
from app.db.models.anime_title import AnimeTitle
from app.db.models.character import AnimeCharacter, Character
from app.db.models.episode import Episode
from app.db.models.genre import AnimeGenre, Genre
from app.db.models.staff import AnimeStaff, Staff
from app.db.models.studio import AnimeStudio, Studio
from app.db.models.user import User
from app.db.models.user_favorite import UserFavorite
from app.db.models.user_history import UserHistory
from app.db.models.user_rating import UserRating
from app.db.models.user_watchlist import UserWatchlist
from app.db.models.voice_actor import CharacterVoiceActor, VoiceActor

__all__ = [
    "Base",
    "Anime",
    "AnimeTitle",
    "Episode",
    "Genre",
    "AnimeGenre",
    "Studio",
    "AnimeStudio",
    "User",
    "Character",
    "AnimeCharacter",
    "VoiceActor",
    "CharacterVoiceActor",
    "Staff",
    "AnimeStaff",
    "UserWatchlist",
    "UserFavorite",
    "UserHistory",
    "UserRating",
]
