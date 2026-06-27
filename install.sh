#!/usr/bin/env bash
#
# GozarX zero-touch installer (Phase 9).
#
# Run on a fresh server from the repo root:
#     sudo ./install.sh           # or:  make install
#
# It installs Docker if needed, collects the few human inputs (domain first, then
# your TLS certificate — e.g. a Cloudflare Origin Certificate), generates every
# secret, writes a chmod-600 .env, builds + starts the stack behind TLS, and
# verifies health, migrations, the admin login, and the Telegram webhook.
#
# Re-running is safe: existing secrets and the Postgres password are reused (never
# rotated), and an already-installed certificate can be kept.
#
# The script is organised as functions with a guarded entrypoint, so the file can
# be sourced in tests to exercise the generators without running an install.

set -euo pipefail

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
CERT_DIR="$SCRIPT_DIR/nginx/certs"
CERT_FILE="$CERT_DIR/origin.pem"
KEY_FILE="$CERT_DIR/origin.key"
TLS_COMPOSE="$SCRIPT_DIR/docker-compose.tls.yml"
TLS_NGINX="$SCRIPT_DIR/nginx/nginx.tls.conf"

# ── Logging ───────────────────────────────────────────────────────────────────
if [ -t 2 ]; then
    C_RESET=$'\033[0m'; C_BLUE=$'\033[34m'; C_GREEN=$'\033[32m'
    C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_BOLD=$'\033[1m'
else
    C_RESET=""; C_BLUE=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BOLD=""
fi
step() { printf '\n%s==>%s %s%s%s\n' "$C_BLUE" "$C_RESET" "$C_BOLD" "$*" "$C_RESET" >&2; }
info() { printf '    %s\n' "$*" >&2; }
ok()   { printf '  %s✓%s %s\n' "$C_GREEN" "$C_RESET" "$*" >&2; }
warn() { printf '  %s!%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
die()  { printf '\n%serror:%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; exit 1; }

# ── Small utilities ───────────────────────────────────────────────────────────
have() { command -v "$1" >/dev/null 2>&1; }

# A URL-safe, .env-safe random secret (hex never needs escaping in a URL or YAML).
gen_secret() { openssl rand -hex 32; }

# Read a single key's current value out of an existing .env (empty if absent).
env_get() {
    [ -f "$ENV_FILE" ] || return 0
    grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- || true
}

# Docker Compose interpolates env-file values, so a literal '$' (bcrypt hashes are
# full of them) must be doubled to survive into the container. See write_env.
escape_dollar() { printf '%s' "$1" | sed 's/\$/$$/g'; }

# ask VAR "Label" "default"  — keeps an existing env value, else prompts (from the
# terminal, so it works under `curl ... | bash`), else falls back to the default.
ask() {
    local __var="$1" __label="$2" __default="${3:-}" __input=""
    if [ -n "${!__var:-}" ]; then return 0; fi
    if [ "${NONINTERACTIVE:-0}" = "1" ]; then
        [ -n "$__default" ] || die "missing required value $__var (non-interactive)"
        printf -v "$__var" '%s' "$__default"; return 0
    fi
    if [ -n "$__default" ]; then
        read -r -p "$__label [$__default]: " __input </dev/tty || __input=""
        __input="${__input:-$__default}"
    else
        while [ -z "$__input" ]; do
            read -r -p "$__label: " __input </dev/tty || __input=""
        done
    fi
    printf -v "$__var" '%s' "$__input"
}

# ask_secret VAR "Label" — hidden, entered twice, must match.
ask_secret() {
    local __var="$1" __label="$2" __a="" __b=""
    if [ -n "${!__var:-}" ]; then return 0; fi
    [ "${NONINTERACTIVE:-0}" = "1" ] && die "missing required secret $__var (non-interactive)"
    while :; do
        read -r -s -p "$__label: " __a </dev/tty; printf '\n' >&2
        read -r -s -p "Confirm: " __b </dev/tty; printf '\n' >&2
        [ -n "$__a" ] && [ "$__a" = "$__b" ] && break
        warn "empty or mismatched — try again"
    done
    printf -v "$__var" '%s' "$__a"
}

# confirm "Question?" "y|n"
confirm() {
    local q="$1" def="${2:-y}" ans=""
    [ "${NONINTERACTIVE:-0}" = "1" ] && { [ "$def" = "y" ]; return; }
    local hint; [ "$def" = "y" ] && hint="Y/n" || hint="y/N"
    read -r -p "$q [$hint]: " ans </dev/tty || ans=""
    ans="${ans:-$def}"
    case "$ans" in [Yy]*) return 0 ;; *) return 1 ;; esac
}

# ── Steps ─────────────────────────────────────────────────────────────────────
preflight() {
    step "Preflight"
    [ "$(id -u)" = "0" ] || die "run as root (sudo ./install.sh)"
    [ "$(uname -s)" = "Linux" ] || die "this installer targets Linux servers"
    have openssl || die "openssl is required"
    have curl || die "curl is required"
    if ! have docker; then
        info "Docker not found — installing via get.docker.com…"
        curl -fsSL https://get.docker.com | sh || die "Docker install failed"
    fi
    docker compose version >/dev/null 2>&1 || die "the Docker Compose plugin is required"
    docker info >/dev/null 2>&1 || die "the Docker daemon is not running"
    ok "root, Docker, and Compose are ready"
}

intake_domain() {
    step "Domain"
    ask DOMAIN "Public domain (no scheme, e.g. gozarx.example.com)" "$(env_get DOMAIN)"
    info "Panel + bot will be served at https://$DOMAIN"
    if pub="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null)"; then
        info "This server's public IP is $pub — point your DNS here (Cloudflare: proxied / orange-cloud)."
    fi
}

intake_tls() {
    step "TLS certificate"
    mkdir -p "$CERT_DIR"
    if [ -s "$CERT_FILE" ] && [ -s "$KEY_FILE" ] && validate_cert_key quiet; then
        if confirm "A valid certificate is already installed — keep it?"; then
            ok "reusing existing certificate"; return 0
        fi
    fi
    info "Paste your TLS certificate and private key (e.g. a Cloudflare Origin Certificate)."
    local cert key
    while :; do
        cert="$(acquire_pem "certificate (PEM, the Origin Certificate)" "${TLS_CERT:-}")"
        printf '%s\n' "$cert" | openssl x509 -noout >/dev/null 2>&1 && break
        warn "not a valid PEM certificate — try again"; TLS_CERT=""
    done
    while :; do
        key="$(acquire_pem "private key (PEM)" "${TLS_KEY:-}")"
        printf '%s\n' "$key" | openssl pkey -noout >/dev/null 2>&1 && break
        warn "not a valid PEM private key — try again"; TLS_KEY=""
    done
    printf '%s\n' "$cert" >"$CERT_FILE"
    printf '%s\n' "$key" >"$KEY_FILE"
    chmod 644 "$CERT_FILE"; chmod 600 "$KEY_FILE"
    validate_cert_key || die "certificate/key validation failed"
    ok "certificate installed to $CERT_FILE"
}

# Source PEM from a file path, inline env content, or an interactive paste.
acquire_pem() {
    local label="$1" src="${2:-}"
    if [ -n "$src" ] && [ -f "$src" ]; then cat "$src"; return 0; fi
    if [ -n "$src" ]; then printf '%s\n' "$src"; return 0; fi
    printf 'Paste the %s, then press Enter and Ctrl-D:\n' "$label" >&2
    cat </dev/tty
}

# Parse both, confirm the key matches the cert, and (soft) that it covers the domain.
validate_cert_key() {
    local quiet="${1:-}"
    openssl x509 -in "$CERT_FILE" -noout >/dev/null 2>&1 || { [ "$quiet" = quiet ] || warn "certificate not parseable"; return 1; }
    openssl pkey -in "$KEY_FILE" -noout >/dev/null 2>&1 || { [ "$quiet" = quiet ] || warn "private key not parseable"; return 1; }
    local cpub kpub
    cpub="$(openssl x509 -in "$CERT_FILE" -noout -pubkey 2>/dev/null)"
    kpub="$(openssl pkey -in "$KEY_FILE" -pubout 2>/dev/null)"
    if [ -z "$cpub" ] || [ "$cpub" != "$kpub" ]; then
        [ "$quiet" = quiet ] || warn "certificate and key do not match"
        return 1
    fi
    if [ "$quiet" != quiet ] && [ -n "${DOMAIN:-}" ]; then
        openssl x509 -in "$CERT_FILE" -noout -checkhost "$DOMAIN" >/dev/null 2>&1 \
            || warn "certificate does not appear to cover $DOMAIN (continuing)"
    fi
    return 0
}

intake_telegram() {
    step "Telegram bot"
    ask BOT_TOKEN "Bot token (from @BotFather)" "$(env_get BOT_TOKEN)"
    local me
    if me="$(curl -fsS --max-time 8 "https://api.telegram.org/bot${BOT_TOKEN}/getMe" 2>/dev/null)" \
        && printf '%s' "$me" | grep -q '"ok":true'; then
        BOT_USERNAME="$(printf '%s' "$me" | sed -n 's/.*"username":"\([^"]*\)".*/\1/p')"
        ok "verified bot @$BOT_USERNAME"
    else
        warn "could not verify the token via Telegram (network?) — enter the username manually"
        ask BOT_USERNAME "Bot username (without @)" "$(env_get BOT_USERNAME)"
    fi
    ask OWNERS "Owner Telegram IDs (comma-separated)" "$(env_get OWNERS)"
}

intake_panel() {
    step "Remnawave panel"
    ask PANEL_BASE_URL "Panel base URL (https://panel.example.com)" "$(env_get PANEL_BASE_URL)"
    ask PANEL_API_TOKEN "Panel API token" "$(env_get PANEL_API_TOKEN)"
}

intake_admin() {
    step "Admin panel login"
    ask ADMIN_USERNAME "Admin username" "$(env_get ADMIN_USERNAME || echo admin)"
    ask_secret ADMIN_PASSWORD "Admin password"
}

intake_optional() {
    step "Optional settings"
    ask ADMIN_DOMAIN "Separate admin domain (blank to serve on $DOMAIN)" "$(env_get ADMIN_DOMAIN || echo '')"
    ask BACKUP_CHANNEL_ID "Telegram channel ID for DB backups (blank to disable)" "$(env_get BACKUP_CHANNEL_ID || echo '')"
    ask TZ_VALUE "Timezone" "$(env_get TZ || echo UTC)"
}

generate_secrets() {
    step "Generating secrets"
    # Reuse anything already in .env so re-runs never rotate live secrets — rotating
    # POSTGRES_PASSWORD against an initialised pg_data volume would lock out the DB.
    WEBHOOK_SECRET="$(env_get WEBHOOK_SECRET)";               WEBHOOK_SECRET="${WEBHOOK_SECRET:-$(gen_secret)}"
    WEBHOOK_HEADER_SECRET="$(env_get WEBHOOK_HEADER_SECRET)"; WEBHOOK_HEADER_SECRET="${WEBHOOK_HEADER_SECRET:-$(gen_secret)}"
    PANEL_WEBHOOK_SECRET="$(env_get PANEL_WEBHOOK_SECRET)";   PANEL_WEBHOOK_SECRET="${PANEL_WEBHOOK_SECRET:-$(gen_secret)}"
    ADMIN_JWT_SECRET="$(env_get ADMIN_JWT_SECRET)";           ADMIN_JWT_SECRET="${ADMIN_JWT_SECRET:-$(gen_secret)}"
    POSTGRES_USER="$(env_get POSTGRES_USER)";                 POSTGRES_USER="${POSTGRES_USER:-gozar}"
    POSTGRES_DB="$(env_get POSTGRES_DB)";                     POSTGRES_DB="${POSTGRES_DB:-gozar}"
    POSTGRES_PASSWORD="$(env_get POSTGRES_PASSWORD)";         POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(gen_secret)}"
    ok "secrets ready (existing values preserved)"
}

# Write the full .env. ADMIN_PASSWORD_HASH is filled on the second call (post-mint).
write_env() {
    local hash_escaped="${1:-}"
    local tmp; tmp="$(mktemp)"
    cat >"$tmp" <<EOF
# Generated by install.sh — keep private (chmod 600). Re-run install.sh to update.

# ── Telegram bot ──
BOT_TOKEN=$BOT_TOKEN
BOT_USERNAME=$BOT_USERNAME
OWNERS=$OWNERS
DOMAIN=$DOMAIN
ADMIN_DOMAIN=$ADMIN_DOMAIN

# ── Webhook security ──
WEBHOOK_SECRET=$WEBHOOK_SECRET
WEBHOOK_HEADER_SECRET=$WEBHOOK_HEADER_SECRET
PANEL_WEBHOOK_SECRET=$PANEL_WEBHOOK_SECRET

# ── Remnawave panel ──
PANEL_BASE_URL=$PANEL_BASE_URL
PANEL_API_TOKEN=$PANEL_API_TOKEN

# ── PostgreSQL ──
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=$POSTGRES_DB
DATABASE_URL=postgresql+asyncpg://$POSTGRES_USER:$POSTGRES_PASSWORD@postgres:5432/$POSTGRES_DB

# ── Redis ──
REDIS_URL=redis://redis:6379/0

# ── Admin panel / API ──
ADMIN_JWT_SECRET=$ADMIN_JWT_SECRET
ADMIN_USERNAME=$ADMIN_USERNAME
# bcrypt hash; '\$' is doubled so Compose passes it through verbatim.
ADMIN_PASSWORD_HASH=$hash_escaped

# ── Misc ──
LOG_LEVEL=INFO
LOG_JSON=false
TZ=$TZ_VALUE
BACKUP_CHANNEL_ID=$BACKUP_CHANNEL_ID
EOF
    mv "$tmp" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
}

build_images() {
    step "Building images (this can take a few minutes)"
    docker compose build || die "docker compose build failed"
    ok "images built"
}

mint_admin_hash() {
    step "Minting admin password hash"
    local hash
    # Reuse the built backend image's bcrypt; password via env (never argv/logs);
    # --no-deps so we don't spin up Postgres/Redis just to hash a string.
    hash="$(docker compose run --rm --no-deps -T -e ADMIN_PASSWORD="$ADMIN_PASSWORD" app \
        python -c 'import bcrypt,os;print(bcrypt.hashpw(os.environ["ADMIN_PASSWORD"].encode(),bcrypt.gensalt()).decode())' \
        2>/dev/null | tr -d '\r\n')"
    case "$hash" in
        \$2*) ok "hash minted" ;;
        *) die "failed to mint admin password hash" ;;
    esac
    write_env "$(escape_dollar "$hash")"   # rewrite .env with the (escaped) hash in place
}

render_tls_nginx() {
    cat >"$TLS_NGINX" <<'EOF'
# Generated by install.sh — TLS reverse proxy (server-only; not committed).
# Browser → Cloudflare (edge cert) → origin (this cert). Set Cloudflare SSL/TLS to "Full (strict)".

upstream gozar_app { server app:8000; }

# Redirect plain HTTP to HTTPS.
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;
    server_name _;

    ssl_certificate     /etc/nginx/certs/origin.pem;
    ssl_certificate_key /etc/nginx/certs/origin.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_session_cache   shared:SSL:10m;

    client_max_body_size 2m;

    location /tg/ {
        proxy_pass http://gozar_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /panel-webhook {
        proxy_pass http://gozar_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://gozar_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /health {
        proxy_pass http://gozar_app;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        root /usr/share/nginx/html;
        try_files $uri /index.html;
    }
}
EOF
}

render_tls_compose() {
    cat >"$TLS_COMPOSE" <<'EOF'
# Generated by install.sh — TLS overlay (server-only; not committed). Adds 443 +
# the origin cert + the TLS nginx config to the base nginx service.
# Use:  docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d --build
services:
  nginx:
    ports:
      - "443:443"
    volumes:
      - ./nginx/nginx.tls.conf:/etc/nginx/conf.d/default.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
EOF
}

generate_tls() {
    step "Generating TLS config"
    render_tls_nginx
    render_tls_compose
    ok "wrote ${TLS_NGINX#"$SCRIPT_DIR"/} and ${TLS_COMPOSE#"$SCRIPT_DIR"/}"
}

bring_up() {
    step "Starting the stack"
    docker compose -f docker-compose.yml -f "$TLS_COMPOSE" up -d --build \
        || die "docker compose up failed"
    ok "containers started"
}

verify() {
    step "Verifying"
    # 1) App health via the origin directly (-k: the origin cert isn't browser-trusted;
    #    --resolve: hit this server, bypassing Cloudflare). Health implies migrations ran
    #    (the entrypoint runs `alembic upgrade head` before uvicorn).
    local code=""
    for _ in $(seq 30); do
        code="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 \
            --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/health" 2>/dev/null || true)"
        [ "$code" = "200" ] && break
        sleep 2
    done
    if [ "$code" = "200" ]; then
        ok "https://$DOMAIN/health → 200"
    else
        warn "health did not return 200 (got '${code:-none}') — see: docker compose logs app"
    fi

    # 2) Admin login round-trip — proves the bcrypt hash survived Compose's interpolation.
    local login
    login="$(curl -sk --max-time 8 --resolve "$DOMAIN:443:127.0.0.1" \
        -H 'Content-Type: application/json' \
        -d "{\"username\":\"$ADMIN_USERNAME\",\"password\":\"$ADMIN_PASSWORD\"}" \
        "https://$DOMAIN/api/admin/auth/login" 2>/dev/null || true)"
    if printf '%s' "$login" | grep -q 'access_token'; then
        ok "admin login works"
    else
        warn "admin login check failed — verify ADMIN_* in .env"
    fi

    # 3) Telegram webhook — the app self-registers it on boot; confirm with getWebhookInfo.
    sleep 3
    local info_json
    info_json="$(curl -fsS --max-time 8 "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" 2>/dev/null || true)"
    if printf '%s' "$info_json" | grep -q "/tg/"; then
        if printf '%s' "$info_json" | grep -qE '"last_error_message":"[^"]+"'; then
            warn "webhook is set but Telegram reports an error — check DNS/TLS (Cloudflare Full strict)"
        else
            ok "Telegram webhook registered to https://$DOMAIN/tg/…"
        fi
    else
        warn "webhook not registered yet — check the bot token and that https://$DOMAIN is reachable"
    fi
}

report() {
    printf '\n%s%s GozarX is installed %s\n' "$C_BOLD" "$C_GREEN" "$C_RESET" >&2
    cat >&2 <<EOF

  Admin panel : https://$DOMAIN   (login: $ADMIN_USERNAME)
  Bot         : @$BOT_USERNAME
  Config      : $ENV_FILE   (chmod 600 — keep private)

  Cloudflare  : DNS record for $DOMAIN must be Proxied (orange cloud);
                SSL/TLS mode = Full (strict).

  Logs        : docker compose -f docker-compose.yml -f docker-compose.tls.yml logs -f
  Update      : git pull && docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d --build
  Re-run      : sudo ./install.sh   (safe; reuses secrets)

  Finish setup in the panel's first-run wizard (trial squad, locations, economics).
EOF
}

main() {
    case "${1:-}" in
        -h | --help)
            cat >&2 <<'EOF'
GozarX installer. Run as root from the repo root:  sudo ./install.sh

Prompts for a domain and a TLS certificate (e.g. Cloudflare Origin Certificate),
then the Telegram/panel/admin details, and brings the stack up behind TLS.

Non-interactive: set NONINTERACTIVE=1 and provide values via environment
variables (DOMAIN, BOT_TOKEN, OWNERS, PANEL_BASE_URL, PANEL_API_TOKEN,
ADMIN_PASSWORD, TLS_CERT, TLS_KEY — the last two may be file paths or PEM text).
EOF
            exit 0
            ;;
    esac
    printf '%s%s GozarX installer %s\n' "$C_BOLD" "$C_BLUE" "$C_RESET" >&2
    preflight
    intake_domain
    intake_tls
    intake_telegram
    intake_panel
    intake_admin
    intake_optional
    generate_secrets
    write_env ""          # initial .env (empty hash) so `docker compose run` can read it
    build_images
    mint_admin_hash       # rewrites .env with the real hash
    generate_tls
    bring_up
    verify
    report
}

# Guarded entrypoint — `source install.sh` (for tests) defines the functions without running.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
