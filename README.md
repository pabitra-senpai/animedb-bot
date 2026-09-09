# AnimeDB Bot

An IMDb-style anime database, discovery, search, and personal-library Telegram bot. AnimeDB Bot lets users search for anime, browse rich detail pages (synopsis, score, genres, studio, episodes, characters, staff), and maintain a personal watchlist, favorites, history, and 1–10 ratings — all backed by a self-owned PostgreSQL cache rather than live-querying third-party APIs on every request.

Metadata comes from public APIs — **AniList** as the primary source, with **Jikan** (MyAnimeList) as a search fallback and **Kitsu** for on-demand episode-title enrichment. This is a separate project from AniDubFlix: no shared branding, architecture, or schema, and no streaming or scraping.

> **Status: All 9 phases complete.** Search, rich detail views, episodes/characters/staff, personal library, discovery browsing, secondary-source fallback/enrichment, a background sync job, and an admin dashboard are implemented and tested. Every phase was verified end-to-end against a real PostgreSQL instance (not just SQLite mocks) as it was built. See [Project Status](#-project-status) for details.

---

## ✨ Features

**🔎 Search & Discovery**
- Local-cache-first anime search (`/search <title>`) — AniList primary, Jikan fallback when AniList returns nothing
- Trending, popular, top-rated, airing, upcoming, seasonal, and genre browsing

**📺 Anime Details & Episodes**
- Rich detail view: poster, synopsis, score, genres, studio, and more
- Episode listings with on-demand Kitsu title enrichment

**🧩 Characters & Staff**
- Character listings with voice actors
- Staff listings

**👤 Personal Library**
- Watchlist, favorites, and watch history, each with pagination
- 1–10 rating system with a dedicated rating picker

**🔄 API Fallback & Enrichment**
- AniList (primary) → Jikan (fallback on empty search) → Kitsu (on-demand episode-title enrichment)
- Each provider self-throttles independently; failures degrade gracefully to cached data

**⚙️ Background Sync**
- Periodic asyncio task refreshes the most-stale cached anime rows from AniList, no separate scheduler process

**🛡️ Admin Tools**
- Stats dashboard, confirm-before-send broadcast, manual sync trigger, ban/unban — all gated by Telegram user ID

---

## 📸 Screenshots / Demo

<!-- Add screenshots/GIFs here -->

---

## 🏗️ Architecture

Requests flow through distinct layers, each with a single responsibility:

```
Telegram → middlewares → handlers → services → repositories → PostgreSQL
                                        ↓
                              renderers (build the reply)
                                        ↓
                          external API clients (AniList / Jikan / Kitsu)
```

- **bot layer** (`app/bot/dispatcher.py`) — wires all routers and middlewares together
- **middlewares** — run on every update, in order: `db_session` (one `AsyncSession` per update), `user_middleware` (get-or-create `User`, syncs `is_admin`), `ban_check` (blocks banned users before any handler runs), `error_handling` (catches unhandled exceptions centrally)
- **filters** — `admin_filter.py` (`IsAdmin`) gates the admin router
- **handlers** — parse commands/callbacks and coordinate services + renderers; one module per feature area (search, discovery, library, profile, admin, etc.)
- **renderers** — pure functions that build Telegram message text/captions and inline keyboards from data, including library state (e.g. whether an anime is already in the watchlist)
- **services** — business logic: cache-first search, staleness/TTL policy, discovery queries, episode/character/staff listing logic, the background sync job, broadcast delivery
- **API clients** — one per provider (`anilist_client.py`, `jikan_client.py`, `kitsu_client.py`), each with its own rate limiter, retry/backoff, and normalizer that maps provider responses into the internal schema
- **repositories** — all database reads/writes, including upsert/dedup logic keyed by external IDs (`anilist_id`, `mal_id`, `kitsu_id`)
- **db/models** — SQLAlchemy declarative models; `models/__init__.py` is the central registry (import order matters for relationship resolution)
- **background sync** — a periodic task alongside the bot's event loop, independent of any request

<details>
<summary>Full project tree</summary>

```
app/
├── main.py                 # entrypoint: startup/shutdown, health server, polling OR webhook mode
├── config.py                # pydantic-settings configuration
├── bot/
│   ├── dispatcher.py
│   ├── middlewares/         # error_handling, db_session, user_middleware, ban_check
│   ├── filters/              # admin_filter.py (IsAdmin)
│   └── handlers/             # start, search, anime_extras, library, profile, discovery, admin
├── db/
│   ├── base.py               # declarative Base + TimestampMixin
│   ├── session.py             # async engine + session factory
│   ├── models/                # user, anime, anime_title, episode, genre, studio,
│   │                          # character, voice_actor, staff, user_watchlist,
│   │                          # user_favorite, user_history, user_rating
│   └── repositories/          # anime, character, staff, user, library, admin
├── renderers/                 # anime, search, episode, character, staff, library,
│                               # rating, profile, discovery, admin
├── services/
│   ├── anilist_client.py        # GraphQL client: rate limiting, retries, 429/403 handling
│   ├── metadata_normalizer.py   # AniList dicts -> internal schema
│   ├── cache_service.py         # staleness/TTL policy (pure functions)
│   ├── search_service.py        # validate -> local cache -> AniList -> Jikan fallback -> upsert
│   ├── episode_service.py       # computed episode-page display logic
│   ├── character_service.py     # cache-first character listing
│   ├── staff_service.py         # cache-first staff listing
│   ├── discovery_service.py     # trending/popular/top-rated/airing/upcoming/seasonal/genre
│   ├── jikan_client.py          # REST client: fallback when AniList search returns nothing
│   ├── jikan_normalizer.py      # Jikan dict -> internal schema
│   ├── kitsu_client.py          # JSON:API client: on-demand episode-title enrichment
│   ├── kitsu_normalizer.py      # Kitsu episode resource -> NormalizedEpisode + title matching
│   ├── kitsu_enrichment_service.py  # resolves kitsu_id once, upserts episode titles
│   ├── sync_job.py              # periodic background re-sync of stale Anime rows (also used by /sync)
│   └── broadcast_service.py     # per-recipient send with flood-wait/blocked-bot handling
└── utils/                       # logging.py (structured JSON), text.py (title normalization)
alembic/
├── env.py                      # async-aware, reads DATABASE_URL from Settings
└── versions/                   # phase2 initial schema, timezone-aware fix,
                                 # phase5 character/VA/staff, phase6 watchlist/favorites/history
                                 # (phases 7–8 added no new columns — confirmed via empty
                                 # autogenerate diffs)
tests/                           # ~30 test files — see Testing section below
```

</details>

---

## 🔌 API Providers

| Provider | Role | Status | Notes |
|---|---|---|---|
| **AniList** (GraphQL) | Primary metadata | ✅ Implemented | No key required. Currently rate-limited to 30 req/min (temporary degraded state per AniList's docs as of writing; nominal limit is 90/min). `ANILIST_RATE_LIMIT_PER_MINUTE` defaults to a conservative 25. |
| **Jikan** (MyAnimeList) | Secondary / fallback | ✅ Implemented | REST, `api.jikan.moe/v4`, no key required. Used only when AniList search returns zero results. Informal limit ~3 req/sec; `JIKAN_RATE_LIMIT_PER_MINUTE` defaults to 30. |
| **Kitsu** | Episode-title enrichment | ✅ Implemented | JSON:API, `kitsu.io/api/edge`, no key required for public reads. On-demand only, triggered when an episode list page has zero titled episodes, with a deliberately conservative title-matching heuristic. `KITSU_RATE_LIMIT_PER_MINUTE` defaults to 10. |
| **SIMKL** | Cross-service ID mapping | ⏳ Deferred | Requires a signup-gated API key (`SIMKL_API_KEY` placeholder exists in config); its docs recently moved and endpoint shapes weren't verified — deferred rather than guessed at. |

Rate limits and implementation status should be re-checked against each provider's current docs before raising the configured limits.

---

## 💾 Database & Caching

- **PostgreSQL 16** is the system of record; all AniList (and Jikan/Kitsu-sourced) metadata is normalized and stored locally rather than fetched fresh on every request.
- **Async SQLAlchemy** (`app/db/session.py`) provides the engine and session factory; one `AsyncSession` is opened per Telegram update via `DbSessionMiddleware`.
- **Alembic** manages schema migrations. `alembic/env.py` reads `DATABASE_URL` from the same `Settings` object the bot uses, so there's no separate configuration to keep in sync.
- **Cache-first search**: `search_service.py` checks the local database first; if it already has ≥5 matching titles for a query, AniList is not called at all. AniList failures degrade gracefully to whatever's cached rather than erroring out.
- **Upsert / dedup**: every AniList result is upserted into `anime_repository.py`, keyed by `anilist_id` — repeated syncs update the same row instead of duplicating it. Character, voice actor, and staff repositories follow the same pattern.
- **Staleness / TTL**: `cache_service.is_stale()` compares each row's `last_synced_at` against `CACHE_TTL_ANIME` / `CACHE_TTL_SEARCH` to decide when a refresh is needed.
- **Background synchronization**: see [Health & Background Jobs](#-health--background-jobs) below.

---

## 🤖 Bot Commands

### User Commands

| Command | Description |
|---|---|
| `/start` | Welcome message; also handles `anime_<id>` deep links |
| `/help` | List available commands |
| `/search <title>` | Search for an anime by title (e.g. `/search One Piece`) |
| `/watchlist` | View your watchlist |
| `/favorites` | View your favorites |
| `/history` | View your watch history |
| `/profile` | View your profile stats |
| `/settings` | Adjust your settings |
| `/trending` | Currently trending anime |
| `/popular` | All-time popular anime |
| `/top` (alias `/toprated`) | Top-rated anime |
| `/airing` | Currently airing anime |
| `/upcoming` | Upcoming anime |
| `/seasonal` | Browse by season |
| `/genres` | Browse by genre |

From an anime's detail view, inline buttons handle everything else — adding to watchlist/favorites, rating (1–10), and paging through episodes, characters, staff, related anime, and recommendations.

### Admin Commands

Gated by `IsAdmin` (Telegram user ID in `ADMIN_IDS`); also listed via `/admin` or `/help` for admins.

| Command | Description |
|---|---|
| `/stats` | Total users, admins, banned users, cached anime, and watchlist/favorites/history/ratings counts |
| `/broadcast <message>` | Previews the recipient count and requires an explicit ✅ Confirm tap before sending; skips banned users; handles per-recipient flood-wait/blocked-bot errors without aborting the run |
| `/sync` | Runs one background-sync pass immediately (same logic as the periodic job) |
| `/ban <telegram_user_id>` | Bans a user (blocked at the middleware level, before any handler runs) |
| `/unban <telegram_user_id>` | Unbans a user |

---

## ⚙️ Configuration

All variables are documented in [`.env.example`](.env.example).

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `BOT_TOKEN` | ✅ Yes | — | Bot token from [@BotFather](https://t.me/BotFather) |
| `DATABASE_URL` | ✅ Yes | — | `postgresql+asyncpg://user:pass@host:5432/db` |
| `ADMIN_IDS` | No | — | Comma-separated Telegram user IDs |
| `ENVIRONMENT` | No | `production` | `development` or `production` |
| `LOG_LEVEL` | No | `INFO` | Log verbosity |
| `PORT` | No | `8080` | Health server port |
| `ANILIST_RATE_LIMIT_PER_MINUTE` | No | `25` | Conservative — see [API Providers](#-api-providers) |
| `ANILIST_REQUEST_TIMEOUT_SECONDS` | No | `10.0` | AniList request timeout |
| `JIKAN_RATE_LIMIT_PER_MINUTE` | No | `30` | Jikan fallback rate limit |
| `KITSU_RATE_LIMIT_PER_MINUTE` | No | `10` | Kitsu enrichment rate limit |
| `BACKGROUND_SYNC_ENABLED` | No | `true` | Toggle the periodic sync task |
| `BACKGROUND_SYNC_INTERVAL_SECONDS` | No | `3600` | Time between sync passes (1 hour) |
| `BACKGROUND_SYNC_BATCH_SIZE` | No | `20` | Rows refreshed per sync pass |

Redis, webhook (`WEBHOOK_URL`, `WEBHOOK_SECRET`), and `SIMKL_API_KEY` variables are read but unused until later phases wire them up (webhook variables are the exception — see [Deployment](#️-deployment) — they're active whenever `WEBHOOK_URL` is set).

---

## 🚀 Getting Started

```bash
# 1. Clone the repository
git clone <repo-url> && cd animedb-bot

# 2. Create your .env
cp .env.example .env
# edit .env: set BOT_TOKEN (from @BotFather) and DATABASE_URL

# 3. Create a virtual environment
python -m venv .venv && source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Set up PostgreSQL — see below

# 6. Run migrations
python -m alembic upgrade head

# 7. Start the bot
python -m app.main
```

You should see JSON (or plain-text, in `development`) startup logs, then the bot will respond to `/start`, `/help`, `/search <title>`, and the rest of the [command reference](#-bot-commands) in Telegram. Try `/search One Piece`, open a result, and tap ➕ Watchlist or ⭐ Rate.

---

## 🐘 PostgreSQL Setup

PostgreSQL 16 is required. Docker Compose (below) is the easiest path. For a local install instead:

```bash
createdb animedb
```

Then point `DATABASE_URL` at it and run `python -m alembic upgrade head` to apply the schema (`users`, `anime`, `anime_titles`, `genres`, `anime_genres`, `studios`, `anime_studios`, `episodes`, plus later-phase tables for characters, staff, and the personal-library features). This has been verified end-to-end against a real PostgreSQL 16 instance: autogenerate, upgrade on an empty DB, downgrade, and an ORM insert/query round-trip across all relationships.

---

## 🐳 Docker

```bash
docker compose up --build
```

Starts the bot, a PostgreSQL 16 container, and a Redis 7 container.

---

## ☁️ Deployment

Deploy via the included [`render.yaml`](render.yaml) Blueprint (Render → New → Blueprint → point at this repo). It provisions:

- A free-tier managed PostgreSQL database
- A **Web Service** running the bot in **webhook mode** (see [Polling vs Webhook](#-polling-vs-webhook) for why this is the default)
- `preDeployCommand: python -m alembic upgrade head` — migrations run automatically on every deploy, before the new instance starts serving
- `DATABASE_URL` wired to the managed database automatically (`fromDatabase.connectionString` — Render hands out a plain `postgres://` URL, and `Settings` rewrites it to the `postgresql+asyncpg://` scheme SQLAlchemy's async engine needs)
- `healthCheckPath: /health` for zero-downtime deploys

After the Blueprint's first deploy, three values need setting manually in the Render dashboard (marked `sync: false` / `generateValue: true` in `render.yaml` so nothing sensitive is committed):

1. `BOT_TOKEN`
2. `ADMIN_IDS`
3. `WEBHOOK_URL` — Render only assigns the service's public URL *after* the first deploy, so this is a two-step process:
   1. Deploy once with `WEBHOOK_URL` left blank — the service starts in polling mode as a harmless fallback.
   2. Copy the assigned URL (e.g. `https://animedb-bot.onrender.com`) from the dashboard, set `WEBHOOK_URL` to that URL plus a path (e.g. `/webhook/tg`), and save. Render redeploys, and `app/main.py` registers the webhook with Telegram automatically on startup.

`WEBHOOK_SECRET` is generated automatically. No UptimeRobot or artificial keep-alive traffic is used or required.

---

## 🔁 Polling vs Webhook

**Webhook mode, deployed as a Render Web Service, is the default** — specifically because Render removed the free instance type for Background Workers in 2026. Free instances are only available for Web Services, Postgres, and Render's Redis-compatible cache now; a polling Background Worker needs at least the paid Starter plan.

| | Long polling (Background Worker) | Webhook (Web Service) |
|---|---|---|
| Render free tier | ❌ Paid plan only | ✅ Compatible |
| Public URL / TLS / secret to manage | No | Yes |
| Update handling on restart | Resumes where it left off; `drop_pending_updates=True` only clears backlog | Telegram may retry against a briefly-down URL mid-deploy |
| Cold starts | None | Free instance sleeps after inactivity; wakes on Telegram's webhook push (few seconds extra latency) |
| Steady-state latency | Continuous long-poll connection | Lower once warm |
| Moving parts | Fewer, for a single-instance bot | Webhook registration, secret verification |

`render.yaml` includes a commented block showing exactly what to change to switch to polling on a paid plan.

**How webhook mode works in this codebase:** `Settings.use_webhook` becomes `True` automatically whenever `WEBHOOK_URL` is set. `app/main.py` branches on this at startup: it registers the webhook with Telegram (`bot.set_webhook`, passing `secret_token=WEBHOOK_SECRET`) and mounts aiogram's `SimpleRequestHandler` on the same aiohttp app that already serves `/health`, instead of starting the polling loop. Telegram echoes `WEBHOOK_SECRET` back in the `X-Telegram-Bot-Api-Secret-Token` header on every request; aiogram verifies it automatically and rejects anything else.

---

## 🩺 Health & Background Jobs

**Health endpoint** — `GET /health` on `PORT` (default `8080`) returns `{"status": "ok"}`, confirmed by actually starting the process and curling it during development. It reports process health only — no self-pinging or outbound "keep-alive" traffic. Used by Render's health checks and the Dockerfile's `HEALTHCHECK` directive.

**Background sync** — a periodic asyncio task (`app/services/sync_job.py`) runs alongside the bot's polling loop, no separate scheduler process or extra dependency. Each pass:

1. Finds the `BACKGROUND_SYNC_BATCH_SIZE` most-stale `Anime` rows (oldest `last_synced_at` first, per `CACHE_TTL_ANIME`)
2. Refreshes them from AniList via `get_anime_by_id`

Controlled by `BACKGROUND_SYNC_ENABLED`, `BACKGROUND_SYNC_INTERVAL_SECONDS`, and `BACKGROUND_SYNC_BATCH_SIZE`. Shuts down cleanly alongside the rest of the process on SIGINT/SIGTERM. The same logic backs the admin `/sync` command for an on-demand run.

---

## 🚦 Rate Limiting & Reliability

Each external client self-throttles with its own sliding-window limiter — no shared/global limiter, since each provider's limit is independent:

- **AniList** — `ANILIST_RATE_LIMIT_PER_MINUTE`, conservative 25/min (AniList is currently in a degraded 30/min state — see [API Providers](#-api-providers))
- **Jikan** — `JIKAN_RATE_LIMIT_PER_MINUTE`, 30/min
- **Kitsu** — `KITSU_RATE_LIMIT_PER_MINUTE`, a conservative 10/min since it's an optional enrichment path

All three retry with exponential backoff on 429/5xx responses and respect `Retry-After` headers where provided.

---

## 🛡️ Security

- Secrets (`BOT_TOKEN`, `DATABASE_URL`, `WEBHOOK_SECRET`, etc.) are read only from environment variables — never hardcoded, never committed (`render.yaml` marks `BOT_TOKEN`/`ADMIN_IDS` `sync: false`)
- Unhandled exceptions in handlers are caught centrally (`ErrorHandlingMiddleware`) so users see a generic message and the bot process never crashes from a single bad update
- Full stack traces go to structured logs only, never to the user
- In webhook mode, every incoming request is verified against `WEBHOOK_SECRET` via Telegram's `X-Telegram-Bot-Api-Secret-Token` header (handled by aiogram's `SimpleRequestHandler`); requests without a matching header are rejected before reaching any handler
- Admin commands are gated by Telegram user ID (`ADMIN_IDS`), never by username (usernames can change/be reused)
- Banned users are blocked at the middleware level (`BanCheckMiddleware`), before any handler or database write runs

---

## 🧪 Testing

Roughly 30 test files cover models, repositories, services, renderers, middleware, and API clients.

| Category | Coverage | Requires live DB? |
|---|---|---|
| Models | `test_models.py` | ❌ In-memory SQLite |
| API clients | `test_anilist_client.py`, `test_jikan_client.py`, `test_kitsu.py` | ❌ Mocked HTTP transport |
| Normalizers | `test_metadata_normalizer.py` | ❌ |
| Repositories | `test_anime_repository.py`, `test_anime_repository_jikan.py`, `test_character_repository.py`, `test_staff_repository.py`, `test_user_repository.py`, `test_library_repository.py`, `test_admin_repository.py` | ❌ |
| Services | `test_search_service.py`, `test_character_service.py`, `test_staff_service.py`, `test_episode_service.py`, `test_discovery_service.py`, `test_cache_service.py`, `test_broadcast_service.py` | ❌ |
| Renderers | `test_anime_renderer.py`, `test_search_renderer.py`, `test_extras_renderers.py`, `test_library_renderers.py`, `test_discovery_renderer.py`, `test_admin_renderer.py` | ❌ |
| Bot wiring | `test_admin_middleware_and_filter.py`, `test_start_deep_link.py`, `test_send_anime_detail.py`, `test_main_webhook.py`, `test_config.py` | ❌ |
| Background sync | `test_sync_job.py` | ✅ Runs against real PostgreSQL via `get_session()` |

Fixtures live in `tests/fixtures/anilist_samples.py`. Run the suite with `pytest` (see `pytest.ini`).

---

## 🔐 Admin System

Set `ADMIN_IDS` in `.env` to a comma-separated list of Telegram user IDs (never usernames — those can change). Anyone listed gets `is_admin` set the next time they message the bot, no manual DB edit needed, and it stays in sync from then on — remove an ID from `ADMIN_IDS` and that user is demoted on their next interaction.

See [Admin Commands](#admin-commands) above for the full command reference. Notably, `/broadcast` always previews the recipient count and requires an explicit ✅ Confirm tap before sending, skips banned users automatically, and handles per-recipient flood-wait or blocked-bot errors without aborting the whole run.

---

## 🔄 API Attribution / Terms

None of the integrated providers currently require in-app attribution as a condition of API access, as far as their public documentation states at the time of writing — but API terms change, so re-check before relying on this:

- **AniList**: [docs.anilist.co](https://docs.anilist.co) — rate limits are the main constraint (see [API Providers](#-api-providers)); no specific attribution clause found in the current public docs.
- **Jikan**: [docs.api.jikan.moe](https://docs.api.jikan.moe) — an unofficial MyAnimeList API; crediting "Data from MyAnimeList via Jikan" is a common courtesy in projects that use it, though not stated as a hard requirement.
- **Kitsu**: [kitsu.docs.apiary.io](https://kitsu.docs.apiary.io) — used only for optional episode-title enrichment in this project.

---

## 🐛 Troubleshooting

| Problem | Possible Cause | Solution |
|---|---|---|
| Bot doesn't respond | Invalid `BOT_TOKEN`, or the process failed to start polling | Check `BOT_TOKEN` is correct and the process logs show `bot_starting_polling` with no errors after it |
| `ValueError` on startup about `BOT_TOKEN` | Token doesn't match the expected format | The token must look like `123456:ABC-DEF...` (numeric ID, colon, secret) |
| Port already in use | Another process is bound to the configured port | Change `PORT` in `.env` |

---

## 🔧 Updating the Bot

```bash
git pull
pip install -r requirements.txt   # or rebuild the Docker image
python -m alembic upgrade head    # apply any new migrations
```

Then restart the process. On Render, this is automatic on every push if auto-deploy is enabled — `preDeployCommand` in `render.yaml` runs the migration before the new instance takes over.

---

## 📁 Project Status

**✅ Completed (Phases 1–9):** search, rich detail views, episodes/characters/staff, personal library (watchlist/favorites/history/ratings), discovery browsing, secondary-source fallback (Jikan) and enrichment (Kitsu), background sync job, admin dashboard. Every phase was verified end-to-end against a real PostgreSQL instance, not just SQLite mocks. A few real bugs surfaced and were fixed along the way — a timezone-naive column in Phase 3, a test-data collision in Phase 7.

**⏳ Deferred:** SIMKL cross-service ID mapping — left unimplemented rather than guessed at, pending a verified API key and current docs (see [API Providers](#-api-providers)).

---

## 📄 License

No `LICENSE` file is currently present in this repository.
