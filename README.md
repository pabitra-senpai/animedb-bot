# AnimeDB Bot

An IMDb-style anime database, discovery, search, and personal-library
Telegram bot. Metadata comes from public APIs (AniList primary; Jikan,
Kitsu, and SIMKL as secondary/enrichment sources) and is cached in our own
PostgreSQL database. This is a separate project from AniDubFlix — no
shared branding, architecture, or schema, and no streaming/scraping.

> **Status: All 9 phases complete.** Search, rich detail views,
> episodes/characters/staff, personal library (watchlist/favorites/
> history/ratings), discovery browsing, secondary-source fallback/
> enrichment (Jikan/Kitsu), a background sync job, and an admin
> dashboard are all implemented and tested — see section 3 for what
> lives where. Every phase was verified end-to-end against a real
> PostgreSQL instance (not just SQLite mocks) as it was built; a few
> real bugs surfaced and got fixed along the way (a timezone-naive
> column in Phase 3, a test-data collision in Phase 7 — see git history
> / the phase-by-phase notes below each section for specifics). SIMKL
> was deliberately left unimplemented (see section 4) rather than
> guessed at without a verified API key and current docs.

## 1. Project overview

Users search for anime (`/search One Piece`) and get a polished Telegram
message with poster, formatted details, and inline navigation — episodes,
characters, staff, related anime, recommendations, trailers, ratings, and
a personal watchlist/favorites/history.

## 2. Features

- Anime search with local-cache-first lookup, AniList primary + Jikan fallback
- Rich anime detail view (poster, synopsis, score, genres, studio, ...)
- Episodes (with on-demand Kitsu title enrichment), characters, staff
- Personal watchlist, favorites, history, 1–10 ratings
- Trending / popular / top-rated / airing / upcoming / seasonal / genre browsing
- Admin dashboard: stats, broadcast, manual sync trigger, ban/unban

## 3. Architecture

```
app/
├── main.py              # entrypoint: startup/shutdown, health server, polling OR webhook mode
├── config.py             # pydantic-settings configuration
├── bot/
│   ├── dispatcher.py      # wires routers + middlewares together
│   ├── middlewares/
│   │   ├── error_handling.py
│   │   ├── db_session.py       # one AsyncSession per update
│   │   ├── user_middleware.py  # get-or-create User per update, injects `user`, syncs is_admin
│   │   └── ban_check.py        # blocks banned users before any handler runs
│   ├── filters/
│   │   └── admin_filter.py     # IsAdmin — gates the admin router
│   └── handlers/
│       ├── start.py         # /start (+ anime_<id> deep links), /help
│       ├── search.py        # /search, pagination + detail-view callbacks
│       ├── anime_extras.py  # episode/character/staff list callbacks
│       ├── library.py       # /watchlist /favorites /history + toggle/rating callbacks
│       ├── profile.py       # /profile, /settings
│       ├── discovery.py     # /trending /popular /top /airing /upcoming /seasonal /genres
│       └── admin.py         # /stats /broadcast /sync /ban /unban (IsAdmin-gated)
├── db/
│   ├── base.py             # declarative Base + TimestampMixin
│   ├── session.py          # async engine + session factory
│   ├── models/
│   │   ├── __init__.py     # central model registry (import order matters)
│   │   ├── user.py
│   │   ├── anime.py
│   │   ├── anime_title.py
│   │   ├── episode.py
│   │   ├── genre.py          # Genre, AnimeGenre
│   │   ├── studio.py         # Studio, AnimeStudio
│   │   ├── character.py      # Character, AnimeCharacter
│   │   ├── voice_actor.py    # VoiceActor, CharacterVoiceActor
│   │   ├── staff.py          # Staff, AnimeStaff
│   │   ├── user_watchlist.py
│   │   ├── user_favorite.py
│   │   ├── user_history.py
│   │   └── user_rating.py
│   └── repositories/
│       ├── anime_repository.py       # upsert/dedup for AniList anime + episode data
│       ├── character_repository.py   # upsert/dedup for character + VA data
│       ├── staff_repository.py       # upsert/dedup for staff data
│       ├── user_repository.py        # get-or-create User, syncs is_admin from config
│       ├── library_repository.py     # watchlist/favorites/history/ratings CRUD
│       └── admin_repository.py       # bot-wide stats, active-user list, ban/unban
├── renderers/
│   ├── anime_renderer.py      # anime detail text/caption + keyboard (incl. library state)
│   ├── search_renderer.py     # search-results list + pagination keyboard
│   ├── episode_renderer.py    # episode list + pagination/back keyboard
│   ├── character_renderer.py  # character list + pagination/back keyboard
│   ├── staff_renderer.py      # staff list + pagination/back keyboard
│   ├── library_renderer.py    # watchlist/favorites/history list + pagination
│   ├── rating_renderer.py     # 1-10 rating picker
│   ├── profile_renderer.py    # /profile stats, /settings toggle
│   ├── discovery_renderer.py  # trending/popular/etc list + genre menu
│   └── admin_renderer.py      # stats text, broadcast preview/confirm/result
├── services/
│   ├── anilist_client.py      # GraphQL client: rate limiting, retries, 429/403 handling
│   ├── metadata_normalizer.py  # AniList dicts -> internal schema shapes (anime/episodes/characters/staff)
│   ├── cache_service.py        # staleness/TTL policy (pure functions)
│   ├── search_service.py       # validate -> local cache -> AniList -> Jikan fallback -> upsert
│   ├── episode_service.py      # computed episode-page display logic
│   ├── character_service.py    # cache-first character listing
│   ├── staff_service.py        # cache-first staff listing
│   ├── discovery_service.py    # trending/popular/top-rated/airing/upcoming/seasonal/genre
│   ├── jikan_client.py         # REST client: fallback when AniList search returns nothing
│   ├── jikan_normalizer.py     # Jikan dict -> internal schema shapes
│   ├── kitsu_client.py         # JSON:API client: on-demand episode-title enrichment
│   ├── kitsu_normalizer.py     # Kitsu episode resource -> NormalizedEpisode + title matching
│   ├── kitsu_enrichment_service.py  # resolves kitsu_id once, upserts episode titles
│   ├── sync_job.py             # periodic background re-sync of stale Anime rows (also used by /sync)
│   └── broadcast_service.py    # per-recipient send with flood-wait/blocked-bot handling
└── utils/
    ├── logging.py          # structured JSON logging
    └── text.py              # title normalization
alembic/
├── env.py                 # async-aware, reads DATABASE_URL from Settings
└── versions/
    ├── ..._phase2_initial_schema...py
    ├── ..._fix_last_synced_at_to_be_timezone_aware.py
    ├── ..._phase5_character_voice_actor_staff_models.py
    └── ..._phase6_user_watchlist_favorites_history_...py
    # (Phases 7 and 8 added no new columns — mal_id/kitsu_id/is_admin/
    # is_banned already existed since Phase 2 — both confirmed via
    # empty autogenerate diffs)
tests/
    ├── test_config.py
    ├── test_models.py            # in-memory SQLite, no live DB needed
    ├── test_anilist_client.py    # mocked HTTP transport, no live network
    ├── test_metadata_normalizer.py
    ├── test_anime_repository.py
    ├── test_anime_repository_jikan.py
    ├── test_character_repository.py
    ├── test_staff_repository.py
    ├── test_user_repository.py
    ├── test_library_repository.py
    ├── test_admin_repository.py
    ├── test_admin_renderer.py
    ├── test_admin_middleware_and_filter.py
    ├── test_broadcast_service.py
    ├── test_cache_service.py
    ├── test_search_service.py
    ├── test_character_service.py
    ├── test_staff_service.py
    ├── test_episode_service.py
    ├── test_discovery_service.py
    ├── test_discovery_renderer.py
    ├── test_jikan_client.py
    ├── test_kitsu.py
    ├── test_sync_job.py          # runs against real Postgres via get_session()
    ├── test_anime_renderer.py
    ├── test_search_renderer.py
    ├── test_extras_renderers.py
    ├── test_library_renderers.py
    ├── test_start_deep_link.py
    ├── test_send_anime_detail.py
    ├── test_main_webhook.py
    └── fixtures/anilist_samples.py
```

## 4. API providers

| Provider | Role | Notes |
|---|---|---|
| AniList (GraphQL) | Primary metadata — Phase 3 | No key required for public queries. **Currently rate-limited to 30 req/min** (temporary degraded state per docs.anilist.co/guide/rate-limiting as of this writing — nominal limit is 90/min). `ANILIST_RATE_LIMIT_PER_MINUTE` defaults to a conservative 25; re-check AniList's status page before raising it. |
| Jikan (MyAnimeList) | Secondary/fallback — **implemented in Phase 7** | REST, `api.jikan.moe/v4`, no key required. Used only when AniList search returns zero results. Rate limit informally ~3 req/sec; `JIKAN_RATE_LIMIT_PER_MINUTE` defaults conservatively to 30 — re-check `docs.api.jikan.moe` before raising it. |
| Kitsu | Episode-title enrichment — **implemented in Phase 7** | JSON:API, `kitsu.io/api/edge`, no key required for public reads. On-demand only (triggered when an episode list page has zero titled episodes), with a deliberately conservative title-matching heuristic. `KITSU_RATE_LIMIT_PER_MINUTE` defaults very conservatively to 10. |
| SIMKL | Cross-service ID mapping — **not implemented** | Requires a signup-gated API key (`SIMKL_API_KEY` placeholder exists in config) and its docs recently moved to a new site whose exact endpoint shapes weren't verified — deferred rather than guessed. |

Search follows a cache-first strategy (`app/services/search_service.py`):
if the local DB already has ≥5 matching titles, AniList is not called at
all. AniList failures degrade gracefully to whatever's cached rather than
erroring out.

## 5. Environment variables

See [`.env.example`](.env.example). Required for Phase 1:

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | yes | From @BotFather |
| `DATABASE_URL` | yes | `postgresql+asyncpg://user:pass@host:5432/db` |
| `ADMIN_IDS` | no | Comma-separated Telegram user IDs |
| `ENVIRONMENT` | no | `development` or `production` (default `production`) |
| `LOG_LEVEL` | no | Default `INFO` |
| `PORT` | no | Health server port, default `8080` |
| `ANILIST_RATE_LIMIT_PER_MINUTE` | no | Default `25` (conservative — see API providers section) |
| `ANILIST_REQUEST_TIMEOUT_SECONDS` | no | Default `10.0` |
| `JIKAN_RATE_LIMIT_PER_MINUTE` | no | Default `30` |
| `KITSU_RATE_LIMIT_PER_MINUTE` | no | Default `10` |
| `BACKGROUND_SYNC_ENABLED` | no | Default `true` |
| `BACKGROUND_SYNC_INTERVAL_SECONDS` | no | Default `3600` (1 hour) |
| `BACKGROUND_SYNC_BATCH_SIZE` | no | Default `20` |

Redis, webhook, and SIMKL variables are read but unused
until later phases wire them up.

## 6. Local setup

```bash
git clone <repo-url> && cd animedb-bot
cp .env.example .env
# edit .env: set BOT_TOKEN (from @BotFather) and DATABASE_URL
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 7. PostgreSQL setup

Local Docker (below) is the easiest path. To use a local install instead,
create a PostgreSQL 16 database matching `DATABASE_URL`, e.g.:

```bash
createdb animedb
```

## 8. Database migrations

```bash
# apply all migrations to an empty database
python -m alembic upgrade head

# after changing/adding a model, generate a new migration
python -m alembic revision --autogenerate -m "describe the change"

# roll back one revision
python -m alembic downgrade -1
```

`alembic/env.py` reads `DATABASE_URL` from the same `Settings` the bot
uses — no separate configuration to keep in sync. Phase 2 ships the
initial schema: `users`, `anime`, `anime_titles`, `genres`,
`anime_genres`, `studios`, `anime_studios`, `episodes`. This has been
verified end-to-end against a real PostgreSQL 16 instance: autogenerate,
upgrade on an empty DB, downgrade, and an ORM insert/query round-trip
across all relationships.

## 9. BotFather setup

1. Message [@BotFather](https://t.me/BotFather) → `/newbot`
2. Follow the prompts, copy the token into `BOT_TOKEN`
3. Optionally set a description, about text, and profile picture

## 10. Running locally

```bash
python -m app.main
```

You should see JSON (or plain-text, in `development`) startup logs, then
the bot will respond to `/start`, `/help`, `/search <title>`,
`/watchlist`, `/favorites`, `/history`, `/profile`, `/settings`,
`/trending`, `/popular`, `/top`, `/airing`, `/upcoming`, `/seasonal`,
and `/genres` in Telegram — try `/search One Piece`, open a result, and
tap ➕ Watchlist or ⭐ Rate. If your Telegram user ID is in `ADMIN_IDS`,
you'll also have `/stats`, `/broadcast`, `/sync`, `/ban`, and `/unban`
(see section 18).

## 11. Docker setup

```bash
docker compose up --build
```

This starts the bot, a PostgreSQL 16 container, and a Redis 7 container.

## 12. Render deployment

Deploy via the included `render.yaml` Blueprint (Render → New →
Blueprint → point at this repo). It provisions:

- A free-tier managed PostgreSQL database
- A **Web Service** running this bot in **webhook mode** (see section
  13 for why this — not a polling Background Worker — is the default)
- `preDeployCommand: python -m alembic upgrade head` — migrations run
  automatically on every deploy, before the new instance starts serving
- `DATABASE_URL` wired to the managed database automatically
  (`fromDatabase.connectionString` — Render hands out a plain
  `postgres://` URL, and `Settings` rewrites it to the
  `postgresql+asyncpg://` scheme SQLAlchemy's async engine needs, so no
  manual edit is required)
- `healthCheckPath: /health` for zero-downtime deploys

After the Blueprint's first deploy, three things need setting manually
in the Render dashboard (marked `sync: false` / `generateValue: true`
in `render.yaml` so nothing sensitive is committed):

1. `BOT_TOKEN`
2. `ADMIN_IDS`
3. `WEBHOOK_URL` — Render only assigns your service's public URL
   *after* the first deploy, so this is necessarily a two-step process;
   see the comment block at the bottom of `render.yaml` for the exact
   steps. `WEBHOOK_SECRET` is generated automatically.

No UptimeRobot or artificial keep-alive traffic is used or required.

## 13. Polling vs webhook decision

**Webhook mode, deployed as a Render Web Service, is the default here
— specifically because Render removed the free instance type for
Background Workers in 2026.** Free instances are only available for
Web Services, Postgres, and Render's Redis-compatible cache now; a
polling Background Worker needs at least the paid Starter plan. If
you're on a paid plan already, long polling is simpler (see below) and
`render.yaml` includes a commented block showing exactly what to change
to switch to it.

Trade-offs of each, for reference:

**Long polling** (Background Worker, paid-plan-only on Render as of
this writing):
- No public URL, TLS certificate, or webhook secret to manage
- No risk of Telegram retrying/dropping updates against a URL that's
  briefly down mid-deploy — the bot just resumes polling where it left
  off (`drop_pending_updates=True` only clears the *backlog*, not
  updates during a normal restart)
- Fewer moving parts for a single-instance bot

**Webhook** (Web Service, free-tier compatible):
- Free to run on Render as of this writing
- A free instance sleeps after inactivity and cold-starts on the next
  request — Telegram's webhook push wakes it, with a few seconds of
  extra latency on the first message after idle time
- Lower latency than polling once warm, and no continuous outbound
  long-poll connection to maintain

How webhook mode works in this codebase: `Settings.use_webhook` becomes
`True` automatically whenever `WEBHOOK_URL` is set —
`app/main.py` branches on this at startup: it registers the webhook
with Telegram (`bot.set_webhook`, passing `secret_token=WEBHOOK_SECRET`)
and mounts aiogram's `SimpleRequestHandler` on the same aiohttp app
that already serves `/health`, instead of starting the polling loop.
Telegram echoes `WEBHOOK_SECRET` back in the
`X-Telegram-Bot-Api-Secret-Token` header on every request; aiogram
verifies it automatically and rejects anything else — so the path
itself doesn't need to be secret, but keep it unguessable anyway.

## 14. Health endpoint

`GET /health` on `PORT` (default `8080`) returns `{"status": "ok"}` —
confirmed working by actually starting the process and curling it
during development, not just reading the code. It reports process
health only — it does not ping itself or generate any outbound
"keep-alive" traffic. Used by Render's health checks (Web Service mode)
and the Dockerfile's `HEALTHCHECK` directive.

## 15. Background jobs

A periodic asyncio task (`app/services/sync_job.py`) runs alongside the
bot's polling loop — no separate scheduler process or extra dependency.
Each pass finds the `BACKGROUND_SYNC_BATCH_SIZE` most-stale `Anime` rows
(oldest `last_synced_at` first, per `CACHE_TTL_ANIME`) and refreshes
them from AniList via `get_anime_by_id`. Controlled by
`BACKGROUND_SYNC_ENABLED` / `BACKGROUND_SYNC_INTERVAL_SECONDS` /
`BACKGROUND_SYNC_BATCH_SIZE` (see Environment variables). Shuts down
cleanly alongside the rest of the process on SIGINT/SIGTERM.

## 16. Rate limiting

Each external client self-throttles with its own sliding-window limiter
(no shared/global limiter needed since each provider's limit is
independent): AniList (`ANILIST_RATE_LIMIT_PER_MINUTE`, conservative
25/min — AniList is currently in a degraded 30/min state, see section 4),
Jikan (`JIKAN_RATE_LIMIT_PER_MINUTE`, 30/min), Kitsu
(`KITSU_RATE_LIMIT_PER_MINUTE`, a conservative 10/min since it's an
optional enrichment path). All three also retry with exponential backoff
on 429/5xx and respect `Retry-After` headers where provided.

## 17. API caching

Every AniList result is upserted into PostgreSQL (`anime_repository.py`),
keyed by `anilist_id` — repeated syncs update the same row rather than
duplicating it. `cache_service.is_stale()` compares `last_synced_at`
against `CACHE_TTL_ANIME`/`CACHE_TTL_SEARCH` to decide when a row needs
refreshing; background refresh jobs that use this land in Phase 7. The
search flow itself skips AniList entirely once the local cache already
has enough matching results for a query.

## 18. Admin setup

Set `ADMIN_IDS` in `.env` to a comma-separated list of Telegram user IDs
(never usernames — those can change). Anyone listed gets `is_admin` set
the next time they message the bot (no manual DB edit needed), and it
stays in sync with the config from then on — remove an ID from
`ADMIN_IDS` and that user is demoted on their next interaction.

Admin commands (see `/help` as an admin, or `/admin`):

- `/stats` — total users, admins, banned users, cached anime, and
  watchlist/favorites/history/ratings counts
- `/broadcast <message>` — previews the recipient count and requires an
  explicit ✅ Confirm tap before sending; skips banned users
  automatically; handles per-recipient flood-wait and blocked-bot errors
  without aborting the whole run
- `/sync` — runs one background-sync pass immediately (the same logic
  the periodic job uses — see section 15)
- `/ban <telegram_user_id>` / `/unban <telegram_user_id>` — banned users
  are blocked at the middleware level, before any handler runs

## 19. Troubleshooting

- **Bot doesn't respond**: check `BOT_TOKEN` is correct and the process
  logs show `bot_starting_polling` with no errors after it.
- **`ValueError` on startup about `BOT_TOKEN`**: the token must look like
  `123456:ABC-DEF...` (numeric ID, colon, secret).
- **Port already in use**: change `PORT` in `.env`.

## 20. Security notes

- Secrets (`BOT_TOKEN`, `DATABASE_URL`, `WEBHOOK_SECRET`, etc.) are read
  only from environment variables — never hardcoded, never committed
  (`render.yaml` marks `BOT_TOKEN`/`ADMIN_IDS` `sync: false` for this
  reason).
- Unhandled exceptions in handlers are caught centrally
  (`ErrorHandlingMiddleware`) so users see a generic message and the
  bot process itself never crashes from a single bad update.
- Full stack traces go to structured logs only, never to the user.
- In webhook mode, every incoming request is verified against
  `WEBHOOK_SECRET` via Telegram's `X-Telegram-Bot-Api-Secret-Token`
  header (handled by aiogram's `SimpleRequestHandler`) — requests
  without a matching header are rejected before reaching any handler.
- Admin commands are gated by Telegram user ID (`ADMIN_IDS`), never by
  username (usernames can change/be reused). Banned users are blocked
  at the middleware level (`BanCheckMiddleware`), before any handler or
  database write runs.

## 21. API attribution / terms

None of the integrated providers currently require in-app attribution
as a condition of API access, as far as their public documentation
states at the time of writing — but API terms change, so re-check
before relying on this:

- AniList: [docs.anilist.co](https://docs.anilist.co) — rate limits are
  the main constraint (see section 4); no specific attribution clause
  was found in the current public docs.
- Jikan: [docs.api.jikan.moe](https://docs.api.jikan.moe) — an
  unofficial MyAnimeList API; crediting "Data from MyAnimeList via
  Jikan" is a common courtesy in projects that use it, though not
  stated as a hard requirement.
- Kitsu: [kitsu.docs.apiary.io](https://kitsu.docs.apiary.io) — used
  only for optional episode-title enrichment in this project.

## 22. How to update the bot

Pull the latest code, re-run `pip install -r requirements.txt` (or
rebuild the Docker image), run `python -m alembic upgrade head` to apply
any new migrations, then restart the process. On Render, this is
automatic on every push if auto-deploy is enabled — `preDeployCommand`
in `render.yaml` runs the migration before the new instance takes over.
