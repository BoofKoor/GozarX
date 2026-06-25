# Gozar v2

A Telegram bot that gives each user a free **daily trial VPN config** from a
[Remnawave](https://remna.st) panel, with referrals that grow the daily traffic
allowance, plus an RTL (Persian) React admin panel. Single Dockerized stack;
near zero-touch install.

> Architecture, conventions, and the phased build plan live in **[CLAUDE.md](./CLAUDE.md)**.

## Stack
- **aiogram 3** (webhook) on a **FastAPI** ASGI app (single uvicorn process)
- **arq** worker (broadcasts, backups) · **PostgreSQL** (SQLAlchemy 2 async + Alembic) · **Redis**
- **Remnawave** panel via API token · **nginx** reverse proxy (+ auto-TLS in the installer)
- Admin panel: **React + TypeScript**, RTL, Vazirmatn (Phase 7)

## Layout
```
backend/gozar/   # Python package: config · web · bot · services · remnawave · db · worker
backend/migrations/  # Alembic (async)
docker/          # Dockerfile.backend + entrypoint.sh
nginx/           # reverse proxy config
frontend/        # React admin panel (Phase 7)
```

## Quick start (dev)
```bash
cp .env.example .env          # fill in values (dummy values are fine to boot Phase 0)
docker compose up -d --build  # postgres, redis, app, worker, nginx
curl http://localhost/health  # {"status":"ok"}
```

## Common commands
```bash
make up        # build + start everything
make logs      # tail logs
make test      # run backend tests
make lint      # ruff check
make down      # stop
```
Backend tooling uses **uv**: `cd backend && uv sync` then `uv run pytest` / `uv run ruff check .`.

## Status
Phase 0 — repo skeleton, settings, logging, Docker stack, and a `/health` route.
See the build phases in [CLAUDE.md](./CLAUDE.md).
