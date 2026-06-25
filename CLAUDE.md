# CLAUDE.md — Gozar v2

## What this is
A Telegram bot that gives each user a free **daily trial VPN config** from a Remnawave panel.
Users pick a language, claim one trial config per day for a chosen location, and grow their daily
traffic allowance by inviting friends. An RTL (Persian) React admin panel manages settings, content,
users, and broadcasts. Everything is Dockerized and installs near zero-touch.

## Architecture (fixed — do not change without asking)
- **One ASGI process:** aiogram 3 (Router + FSM) on **webhook**, fed by a **FastAPI** app under
  uvicorn (`--factory --proxy-headers`, behind nginx). FastAPI hosts:
  - `POST /tg/{secret}` — verify the secret path segment **and** Telegram's
    `X-Telegram-Bot-Api-Secret-Token` header, then `dp.feed_update(...)`.
  - `POST /panel-webhook` — Remnawave user events (expired / limited).
  - `/api/...` — admin REST API (JWT).
  - `GET /health`.
- **arq worker:** a separate process/container for broadcasts, forwards, and the pg_dump backup cron.
- **Remnawave** panel via API token (Bearer). One shared `httpx.AsyncClient`; TLS verification **on**.
- **PostgreSQL** + SQLAlchemy 2 async + Alembic. **Redis** for aiogram FSM, content/settings cache,
  and the arq queue.
- **nginx** terminates TLS, routes `/api` + the webhooks to the app, and serves the SPA static build;
  a **certbot companion** issues/renews Let's Encrypt certs (wired in the installer).
- **Runtime config lives in the DB** (`settings` / `content` tables), edited from the panel —
  changing it never needs a redeploy. Only secrets/infra are env vars.

## Layout & layering
Import package is `gozar` (under `backend/`). Imports flow **one direction only**:
`web/` + `bot/` (delivery) → `services/` (logic) → `db/repositories` + `remnawave/` + `cache/` (infra)
→ `config/`. Services never import delivery code, so the arq worker reuses logic without pulling in
FastAPI/aiogram. The boot sequence (`docker/entrypoint.sh`) is stable forever:
`alembic upgrade head` → `python -m gozar.seed` → `uvicorn gozar.web.app:create_app --factory`.

## Conventions (non-negotiable)
- Python 3.12, **async throughout**. **Logging only — never `print()` (ruff T201). Never log tokens or
  full payloads.**
- **Zero import side effects.** Config via `get_settings()` (lru_cache); never instantiate settings or
  touch DB/network at import time. Secrets are `SecretStr`.
- **All DB access through repositories.** One middleware opens **a single AsyncSession per update**
  and injects the loaded user + repos; handlers never open their own session and never re-query the
  same user twice.
- **Callback data is namespaced, matched by exact prefix** (`config:open`, `loc:pick:3`, `menu:back`).
  Never unanchored substring regex.
- **User-facing copy comes from the `content` table** via `content.text(key, lang, **tokens)`;
  placeholders are `{token}`, substituted only when provided. Never `str.replace` on message text.
- **Fixed UI chrome (button labels)** lives in a small **in-code i18n map**, not the DB.
- **Match a chosen location to its config by remark NAME, not list index.**
- **No process-global mutable state for per-user data** — per-user state in FSM/DB; shared caches in
  Redis, keyed properly.
- **Panel calls are single, bounded attempts** — log and move on; never `while result is None: retry`.
- **Broadcasts run in the arq worker**, never inside a handler. A broadcast removes a user **only** on
  a genuine "bot blocked / deactivated" error — never on transient failures.
- **Admin multi-step flows use aiogram FSM (Redis)**, never a module-global dict.
- **Use the configured referral reward everywhere** — never hardcode reward/cap numbers.
- **Remnawave: VERIFY every endpoint** against the live OpenAPI (`{PANEL_BASE_URL}/api`) before wiring;
  mark each with `# VERIFY:` and provide fallbacks rather than hardcoding response field names.

## Lessons from v1 (bugs designed out — see conventions above)
1. No destructive side effects on import (old `config.py` ran `delete_user()` + `create_tables()`).
2. No process-global mutable per-user state (old global location list → race → wrong config).
3. Match location → config by remark NAME, not `links[index]`.
4. No mass-deletion on errors (broadcast removes a user only on blocked/deactivated, never transient).
5. No unbounded panel retry loops (old `while result is None: retry` hung when the panel was down).
6. Derive locations from the trial squad, not a hardcoded "template user".
7. Admin multi-step flows in aiogram FSM, not a module-global dict.
8. Use the configured referral reward everywhere (old status screen hardcoded ×100).
9. Broadcasts in the arq worker, so the bot stays responsive on webhook.
10. Reminders via Remnawave webhook events, not by parsing `#Expired`/`#Limited` text from a channel.

## Data model
- `users`: telegram_id (PK bigint) · status enum(available/active_config/banned) · language enum ·
  referral_count · panel_username · reminder_enabled bool · referred_by bigint · created_at tz.
- `config_logs`: id · user_id FK · location · created_at tz (one row per claim).
- `content`: unique (key, language) → body text. Editable bot copy.
- `settings`: key → value string. Runtime values (trial squad, locations, daily_limit_mb,
  referral_reward_mb, referral_reward_limit, trial_hours, ads_enabled) — set via the first-run wizard,
  editable from the panel. NOT env vars.

## Dev workflow
- Deps via **uv** (`uv sync`, `uv add <pkg>`). Lint/format with **ruff**; gate every change with
  `ruff check`, `python -m py_compile` / `pyflakes` before committing.
- Migrations via Alembic (`make migrate` to autogenerate, `make upgrade`). The app entrypoint runs
  `alembic upgrade head` → `python -m gozar.seed` → uvicorn on boot.
- Run locally with `docker compose up` from a filled `.env` (copy `.env.example`).
- **One feature branch + one PR per phase**; keep each PR independently reviewable.
- **Re-read this file at the start of every session. Plan → confirm → implement.**

## Build phases
0 Skeleton + this file + settings + logging + compose + .env.example; app boots `/health`.
1 DB models + Alembic initial migration + repositories.
2 Remnawave client (VERIFY markers) + content/settings service (Redis-cached) + seed.
3 Bot core on webhook: dispatcher + middleware + i18n + keyboards + /start + language + menu nav.
4 Core flow: trial provisioning + config claim + location picker + change location + status.
5 Referral + settings (language/reminder) + reminders via Remnawave webhook receiver.
6 Admin (FSM): stats, broadcast/forward (arq worker), ban, reset limits, refresh locations.
7 Admin API (JWT) + React/TS RTL panel: first-run setup wizard, dashboard, users/content/broadcast.
8 DB backup job (arq cron: pg_dump → Telegram channel). Tests: location matching, referral cap, content render.
9 Zero-touch installer (install.sh): Docker, DNS A-record + propagation wait, auto-TLS, secrets, compose up, health/migration/webhook verify.

## Security
- TLS verification on for all panel calls. Installer auto-generates secrets; `.env` is chmod 600.
- Webhook protected by the secret path segment + Telegram secret_token header.
- Never log secrets or full update/panel payloads.
