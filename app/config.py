"""
Application configuration.

All configuration is loaded from environment variables (see .env.example).
Never hardcode secrets here.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Telegram ---
    bot_token: str = Field(..., alias="BOT_TOKEN")
    admin_ids: str = Field(default="", alias="ADMIN_IDS")

    # --- Environment / logging ---
    environment: str = Field(default="production", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Database ---
    database_url: str = Field(..., alias="DATABASE_URL")

    # --- Redis (optional) ---
    redis_url: str | None = Field(default=None, alias="REDIS_URL")

    # --- Metadata providers ---
    anilist_api_url: str = Field(
        default="https://graphql.anilist.co", alias="ANILIST_API_URL"
    )
    jikan_base_url: str = Field(
        default="https://api.jikan.moe/v4", alias="JIKAN_BASE_URL"
    )
    kitsu_base_url: str = Field(
        default="https://kitsu.io/api/edge", alias="KITSU_BASE_URL"
    )
    simkl_api_key: str | None = Field(default=None, alias="SIMKL_API_KEY")

    # --- Cache TTLs (seconds) ---
    cache_ttl_search: int = Field(default=3600, alias="CACHE_TTL_SEARCH")
    cache_ttl_anime: int = Field(default=21600, alias="CACHE_TTL_ANIME")
    cache_ttl_airing: int = Field(default=900, alias="CACHE_TTL_AIRING")

    # --- AniList client ---
    # NOTE: AniList's nominal limit is 90/min, but as of this writing the API
    # is in a degraded state capped at 30/min (see docs.anilist.co/guide/
    # rate-limiting). Default kept conservative; raise via env once AniList
    # restores full capacity — verify current status before raising this.
    anilist_rate_limit_per_minute: int = Field(default=25, alias="ANILIST_RATE_LIMIT_PER_MINUTE")
    anilist_request_timeout_seconds: float = Field(default=10.0, alias="ANILIST_REQUEST_TIMEOUT_SECONDS")

    # --- Jikan client (secondary/fallback) ---
    jikan_rate_limit_per_minute: int = Field(default=30, alias="JIKAN_RATE_LIMIT_PER_MINUTE")
    jikan_request_timeout_seconds: float = Field(default=10.0, alias="JIKAN_REQUEST_TIMEOUT_SECONDS")

    # --- Kitsu client (episode-title enrichment, opt-in/best-effort) ---
    kitsu_rate_limit_per_minute: int = Field(default=10, alias="KITSU_RATE_LIMIT_PER_MINUTE")
    kitsu_request_timeout_seconds: float = Field(default=10.0, alias="KITSU_REQUEST_TIMEOUT_SECONDS")

    # --- Background sync job ---
    background_sync_enabled: bool = Field(default=True, alias="BACKGROUND_SYNC_ENABLED")
    background_sync_interval_seconds: int = Field(default=3600, alias="BACKGROUND_SYNC_INTERVAL_SECONDS")
    background_sync_batch_size: int = Field(default=20, alias="BACKGROUND_SYNC_BATCH_SIZE")

    # --- Webhook (optional; polling used if unset) ---
    webhook_url: str | None = Field(default=None, alias="WEBHOOK_URL")
    webhook_secret: str | None = Field(default=None, alias="WEBHOOK_SECRET")
    port: int = Field(default=8080, alias="PORT")

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        if not v or ":" not in v:
            raise ValueError(
                "BOT_TOKEN looks invalid. Expected format: '123456:ABC-DEF...'"
            )
        return v

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Render (and Heroku-style) managed Postgres add-ons hand out
        `postgres://` or `postgresql://` connection strings — SQLAlchemy's
        async engine needs the `postgresql+asyncpg://` driver prefix.
        Rewriting it here means the value straight from Render's
        `fromDatabase.connectionString` just works, no manual edit needed."""
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    @property
    def admin_id_set(self) -> set[int]:
        """Parsed, validated set of admin Telegram user IDs."""
        ids: set[int] = set()
        for raw in self.admin_ids.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                ids.add(int(raw))
            except ValueError:
                # Invalid entries are ignored rather than crashing startup;
                # this is logged by the caller if needed.
                continue
        return ids

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def use_webhook(self) -> bool:
        return bool(self.webhook_url)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Import and call this, don't instantiate Settings directly."""
    return Settings()  # type: ignore[call-arg]
