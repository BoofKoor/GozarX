#!/usr/bin/env sh
# Stable app boot sequence — identical across all phases.
# Migrations and seed are safe no-ops until later phases add content.
set -eu

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] seeding defaults"
python -m gozar.seed

# Optional autoreload for local dev (set RELOAD=1 in docker-compose.override.yml).
RELOAD_ARG=""
if [ "${RELOAD:-0}" = "1" ]; then
    RELOAD_ARG="--reload"
fi

echo "[entrypoint] starting uvicorn"
exec uvicorn gozar.web.app:create_app --factory \
    --host 0.0.0.0 --port 8000 \
    --proxy-headers --forwarded-allow-ips '*' \
    ${RELOAD_ARG}
