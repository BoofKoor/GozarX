# GozarX

A self-hosted **Telegram bot** that gives every user a **free daily trial VPN config** from a
[Remnawave](https://remna.st) panel — pick a language, claim one trial config per day for a chosen
location, and grow your daily traffic allowance by inviting friends. It ships with an **RTL Persian
React admin panel**, runs as a single Dockerized stack, and installs near zero-touch behind TLS.

GozarX is a **completely free tool** — there are no payments, wallets, or plans. Every user simply
gets a fresh trial config each day.

> Architecture, conventions, and the phased build plan live in **[CLAUDE.md](./CLAUDE.md)**.

---

## Features

### For users (the Telegram bot)
- **One free trial config per day**, provisioned live from your Remnawave panel.
- **Location picker** — choose from the locations in your trial squad (matched by remark name).
- **Change location** and **check status** (usage, time remaining, daily limit) any time.
- **Referrals** — invite friends to grow your daily traffic allowance, up to a configurable cap.
- **Reminders** when a config expires or hits its limit (driven by Remnawave webhook events).
- **Multilingual** — Persian / English / Russian, with all copy editable from the panel.

### For the owner (in-bot admin — `/admin`)
- Live **stats**, **broadcast** & **forward** to all users (run in a background worker).
- Per-user actions: **ban / unban**, **reclaim** today's claim, **zero referrals**.
- **Bulk reset** of traffic consumption, and **refresh locations** from the trial squad.

### Web admin panel (React, RTL)
- **First-run setup wizard** (trial squad, locations, referral economics).
- **Dashboard** with stats and a claims chart.
- **Users** — searchable, filterable list with per-user detail cards and actions.
- **Broadcast** — compose an HTML message and fan it out to every user.
- **Texts editor** — edit all bot copy per language.
- **Buttons editor** — rename, hide, and drag-drop reorder the bot's inline keyboards.
- **Settings** — edit the runtime economics without a redeploy.

### Operations
- **Nightly database backup** (`pg_dump` → gzip → a Telegram channel) via an arq cron.
- **Zero-touch installer** with Cloudflare Origin-certificate TLS.

---

## Tech stack
- **aiogram 3** (webhook) fed by a **FastAPI** ASGI app — one uvicorn process.
- **arq** worker (broadcasts, forwards, nightly backup) as a separate process.
- **PostgreSQL** (SQLAlchemy 2 async + Alembic) · **Redis** (FSM, cache, arq queue).
- **Remnawave** panel via API token (TLS verification on).
- **nginx** terminates TLS and serves the SPA; **Docker Compose** ties it together.
- Admin panel: **React 18 + TypeScript + Vite + Tailwind**, RTL, Vazirmatn.

```
Telegram ─┐                         ┌─ PostgreSQL
          ├─► nginx (TLS) ─► app ───┤
Browser ──┘     :443         (FastAPI│  ┌─ Redis ◄─┐
                              +aiogram)─┘          │
Remnawave ─► /panel-webhook ─►          arq worker ┘ (broadcasts, nightly pg_dump)
```

---

## Prerequisites
- A Linux server (root/sudo) with ports **80** and **443** open.
- A **domain on Cloudflare**.
- A **Telegram bot token** (from [@BotFather](https://t.me/BotFather)) and your owner Telegram
  numeric ID(s) (e.g. from [@userinfobot](https://t.me/userinfobot)).
- A **Remnawave panel** URL + API token.
- _(Optional, for backups)_ a Telegram channel with the bot added as an admin, and its channel ID.

---

## Installation

### 1. Cloudflare
1. **Origin certificate:** in your domain's dashboard go to **SSL/TLS → Origin Server →
   Create Certificate**. Keep the **Origin Certificate** (PEM) and the **Private Key** — you'll paste
   them during install.
2. **DNS:** add an **A record** for your domain pointing to the server's IP, and make it **Proxied**
   (orange cloud).
3. **SSL/TLS mode:** set it to **Full (strict)**.

### 2. Run the installer
```bash
git clone https://github.com/BoofKoor/GozarX.git
cd GozarX
sudo ./install.sh        # or: sudo make install
```

The installer is interactive and idempotent. It will, in order:
1. Install Docker if missing and check the Compose plugin.
2. Ask for your **domain**, then your **TLS certificate + private key** (paste each, then `Ctrl-D`).
3. Ask for the **bot token** (verified via Telegram), **owner IDs**, **panel URL + token**, and an
   **admin username + password**.
4. Generate every secret, write a `chmod 600` `.env`, build the images, and start the stack behind
   TLS.
5. Verify health, the admin login, and that the Telegram webhook registered.

Re-running `./install.sh` is safe — existing secrets and the Postgres password are **reused, never
rotated**, and an installed certificate can be kept.

### 3. Finish setup in the panel
Open `https://your-domain`, log in with the admin credentials you chose, and complete the **first-run
wizard** (trial squad, locations, referral economics). That's it — the bot is live.

---

## Operations

```bash
# Tail logs
docker compose -f docker-compose.yml -f docker-compose.tls.yml logs -f

# Update to the latest main and redeploy
git pull origin main
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d --build

# Re-run the installer (safe; reuses secrets)
sudo ./install.sh
```

- **Backups:** set `BACKUP_CHANNEL_ID` during install (and add the bot as a channel admin) to receive
  a nightly gzipped `pg_dump` at 03:00 UTC.
- **Runtime config** (trial squad, locations, daily limit, referral reward/cap, trial hours, ads) lives
  in the database and is edited from the panel — changing it never needs a redeploy. Only secrets and
  infrastructure are environment variables (see [`.env.example`](./.env.example)).

---

## Development

Run the stack locally over plain HTTP (no TLS overlay):
```bash
cp .env.example .env             # dummy values are enough to boot /health
docker compose up -d --build     # postgres, redis, app, worker, nginx
curl http://localhost/health     # {"status":"ok"}
```

Backend tooling uses **uv**:
```bash
cd backend
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest                    # DB-gated tests need TEST_DATABASE_URL set to a Postgres 16 DSN
```

Frontend (admin panel):
```bash
cd frontend/admin
npm ci
npm run build      # tsc -b + vite
npm run test       # vitest
```

Handy `make` targets: `make up`, `make logs`, `make test`, `make lint`, `make migrate`, `make down`.

---

## Project structure
```
backend/gozar/
  config/      settings (env) + logging
  db/          SQLAlchemy models + repositories + session
  remnawave/   panel API client (links parser, subscriptions, schemas)
  cache/       Redis pool
  services/    business logic (trial, referral, content, settings, admin, buttons)
  ui/          neutral catalogue + i18n labels + keyboard rendering
  bot/         aiogram dispatcher, middleware, handlers, keyboards
  web/         FastAPI app, webhooks, JWT admin API
  worker/      arq tasks (broadcast, forward, nightly backup)
backend/migrations/   Alembic (async)
frontend/admin/       React + TypeScript RTL panel
docker/               Dockerfile.backend + Dockerfile.frontend + entrypoint.sh
nginx/                reverse-proxy config
install.sh            zero-touch installer
```

---

## Security
- TLS verification is on for all panel calls; nginx terminates TLS with your Cloudflare Origin cert.
- The Telegram webhook is protected by a secret path segment **and** Telegram's secret-token header.
- The installer generates all secrets and writes `.env` as `chmod 600`; the TLS private key, the
  generated TLS overlay, and `nginx/nginx.tls.conf` are git-ignored (server-only).
- Secrets and full update/panel payloads are never logged.
