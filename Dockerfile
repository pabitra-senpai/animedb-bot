FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps needed by asyncpg/psycopg-style builds, plus curl for the
# HEALTHCHECK below (kept minimal otherwise).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Render (and most PaaS) inject PORT; default kept for local runs.
ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Render's Docker runtime does not support overriding the container
# command via `startCommand` in render.yaml (Docker-runtime services must
# define their command here). Migrations are run as part of this CMD,
# before the bot starts, so they still apply on every deploy —
# including on Render's free tier, where `preDeployCommand` isn't
# available.
CMD ["sh", "-c", "python -m alembic upgrade head && python -m app.main"]
