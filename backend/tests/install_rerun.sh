#!/usr/bin/env bash
# install.sh re-run paths, with docker/curl stubbed and every path redirected to a temp dir. Run by
# test_install_script.py; the installer runs on production servers, and its re-run is what broke.
set -uo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/install.sh"
set +e # the sourced script turned on errexit; assertions below report instead of exiting

T="$(mktemp -d)"
ENV_FILE="$T/.env"
CERT_DIR="$T/certs"; mkdir -p "$CERT_DIR"
CERT_FILE="$CERT_DIR/origin.pem"; KEY_FILE="$CERT_DIR/origin.key"
TLS_COMPOSE="$T/docker-compose.tls.yml"; TLS_NGINX="$T/nginx.tls.conf"
DOCKER_CALLS="$T/docker.calls"; : >"$DOCKER_CALLS"
docker() { printf '%s\n' "$*" >>"$DOCKER_CALLS"; return 0; }
curl() { printf '200'; }

fails=0
check() { if eval "$2"; then printf 'ok   %s\n' "$1"; else printf 'FAIL %s\n' "$1"; fails=$((fails + 1)); fi; }

# An installed .env: a managed set, a hand-added key, the SEO token, and edited log settings.
cat >"$ENV_FILE" <<'ENV'
BOT_TOKEN=123:abc
DOMAIN=example.com
ADMIN_USERNAME=root
ADMIN_PASSWORD_HASH=$$2b$$12$$abcdefghijklmnopqrstuv
GOOGLE_SITE_VERIFICATION=g-token-1
CUSTOM_FLAG=on
LOG_LEVEL=DEBUG
LOG_JSON=true
ENV

# ── env_or: the default applies to an ABSENT key, the value wins otherwise ──
check "env_or falls back for an absent key" '[ "$(env_or TZ UTC)" = "UTC" ]'
check "env_or keeps a present value" '[ "$(env_or ADMIN_USERNAME admin)" = "root" ]'

# ── intake_admin, non-interactive, hash installed, no password given → keep ──
NONINTERACTIVE=1
unset ADMIN_PASSWORD
ADMIN_USERNAME=""
intake_admin 2>/dev/null
check "a re-run without ADMIN_PASSWORD keeps the password" '[ -z "${ADMIN_PASSWORD+x}" ] || [ -z "$ADMIN_PASSWORD" ]'
check "the username default comes from .env" '[ "$ADMIN_USERNAME" = "root" ]'

# The values write_env interpolates.
BOT_TOKEN=123:abc DOMAIN=example.com
BOT_USERNAME=bot OWNERS=1 ADMIN_DOMAIN="" WEBHOOK_SECRET=w WEBHOOK_HEADER_SECRET=h
PANEL_WEBHOOK_SECRET=p PANEL_BASE_URL=https://panel PANEL_API_TOKEN=t POSTGRES_USER=gozar
POSTGRES_PASSWORD=pg POSTGRES_DB=gozar ADMIN_JWT_SECRET=j SITE_DOMAIN=example.com
SITE_COOKIE_SECRET=c TURNSTILE_SECRET="" TURNSTILE_SITE_KEY="" VAPID_PRIVATE_KEY=vp
VAPID_PUBLIC_KEY=vq VAPID_SUBJECT=mailto:a@b TZ_VALUE=UTC BACKUP_CHANNEL_ID=""
GOOGLE_SITE_VERIFICATION="$(env_get GOOGLE_SITE_VERIFICATION)"

# ── first write (main flow) keeps the WORKING hash ──
write_env "$(env_get ADMIN_PASSWORD_HASH)"
check "first write keeps the installed hash verbatim" \
    'grep -qx "ADMIN_PASSWORD_HASH=\$\$2b\$\$12\$\$abcdefghijklmnopqrstuv" "$ENV_FILE"'
check "GOOGLE_SITE_VERIFICATION survives" 'grep -qx "GOOGLE_SITE_VERIFICATION=g-token-1" "$ENV_FILE"'
check "a hand-added key is carried over" 'grep -qx "CUSTOM_FLAG=on" "$ENV_FILE"'
check "edited LOG_LEVEL survives" 'grep -qx "LOG_LEVEL=DEBUG" "$ENV_FILE"'
check "edited LOG_JSON survives" 'grep -qx "LOG_JSON=true" "$ENV_FILE"'
check "the kept section holds ONLY the unmanaged key" \
    '[ "$(sed -n "/^# ── Kept from/,\$p" "$ENV_FILE" | grep -c "=")" = 1 ]'
check ".env stays chmod 600" '[ "$(stat -c %a "$ENV_FILE")" = "600" ]'

# ── mint_admin_hash with a kept password: no docker call, hash unchanged, nothing duplicated ──
: >"$DOCKER_CALLS"
mint_admin_hash 2>/dev/null
check "a kept password mints nothing" '[ ! -s "$DOCKER_CALLS" ]'
check "the hash is unchanged after the rewrite" \
    'grep -qx "ADMIN_PASSWORD_HASH=\$\$2b\$\$12\$\$abcdefghijklmnopqrstuv" "$ENV_FILE"'
check "a carried key is not duplicated by the second write" '[ "$(grep -c "^CUSTOM_FLAG=" "$ENV_FILE")" = "1" ]'
check "every key appears once" '[ -z "$(sed -n "s/=.*//p" "$ENV_FILE" | sort | uniq -d)" ]'

# ── a fresh install still needs a password ──
rm -f "$ENV_FILE"
unset ADMIN_PASSWORD
( intake_admin ) 2>/dev/null
check "a fresh non-interactive install without ADMIN_PASSWORD refuses" '[ $? -ne 0 ]'

# ── --tls-only renders from .env and restarts nginx ──
cat >"$ENV_FILE" <<'ENV'
DOMAIN=admin.example.com
SITE_DOMAIN=www.example.com
ADMIN_DOMAIN=
ENV
openssl req -x509 -newkey rsa:2048 -nodes -keyout "$KEY_FILE" -out "$CERT_FILE" -days 1 \
    -subj "/CN=admin.example.com" >/dev/null 2>&1
DOMAIN="" SITE_DOMAIN="" ADMIN_DOMAIN=""
: >"$DOCKER_CALLS"
tls_only 2>/dev/null
check "--tls-only renders the split layout from .env" 'grep -q "www.example.com" "$TLS_NGINX"'
check "--tls-only restarts nginx" 'grep -q "restart nginx" "$DOCKER_CALLS"'

# ── bring_up restarts nginx after up ──
: >"$DOCKER_CALLS"
bring_up 2>/dev/null
check "bring_up restarts nginx after up" \
    '[ "$(sed -n 1p "$DOCKER_CALLS" | grep -c "up -d --build")" = 1 ] && grep -q "restart nginx" "$DOCKER_CALLS"'

rm -rf "$T"
printf '\n%s failure(s)\n' "$fails"
[ "$fails" = 0 ]
