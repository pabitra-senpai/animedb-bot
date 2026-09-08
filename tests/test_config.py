import pytest

from app.config import Settings


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123456:ABCDEF")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("ADMIN_IDS", "111,222, 333")

    settings = Settings()

    assert settings.bot_token == "123456:ABCDEF"
    assert settings.admin_id_set == {111, 222, 333}
    assert settings.is_production is True  # default environment
    assert settings.use_webhook is False


def test_invalid_bot_token_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "not-a-valid-token")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")

    with pytest.raises(ValueError):
        Settings()


def test_malformed_admin_id_is_skipped_not_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("ADMIN_IDS", "111,not-a-number,222")

    settings = Settings()

    assert settings.admin_id_set == {111, 222}


def test_database_url_postgres_scheme_rewritten_to_asyncpg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123456:ABCDEF")
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host:5432/db")

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://u:p@host:5432/db"


def test_database_url_postgresql_scheme_rewritten_to_asyncpg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123456:ABCDEF")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://u:p@host:5432/db"


def test_database_url_already_asyncpg_left_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123456:ABCDEF")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@host:5432/db")

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://u:p@host:5432/db"


def test_use_webhook_false_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)
    settings = Settings()
    assert settings.use_webhook is False


def test_use_webhook_true_when_webhook_url_set(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("WEBHOOK_URL", "https://example.onrender.com/webhook")
    settings = Settings()
    assert settings.use_webhook is True
