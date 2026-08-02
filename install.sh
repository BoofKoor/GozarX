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

# ask_optional VAR "Label" "default" — like ask, but a blank answer is accepted (no re-prompt loop).
ask_optional() {
    local __var="$1" __label="$2" __default="${3:-}" __input=""
    if [ -n "${!__var:-}" ]; then return 0; fi
    if [ "${NONINTERACTIVE:-0}" = "1" ]; then printf -v "$__var" '%s' "$__default"; return 0; fi
    read -r -p "$__label [${__default:-blank}]: " __input </dev/tty || __input=""
    printf -v "$__var" '%s' "${__input:-$__default}"
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
    ask_optional ADMIN_DOMAIN "Separate admin domain (blank to serve on $DOMAIN)" "$(env_get ADMIN_DOMAIN)"
    ask_optional BACKUP_CHANNEL_ID "Telegram channel ID for DB backups (blank to disable)" "$(env_get BACKUP_CHANNEL_ID)"
    ask TZ_VALUE "Timezone" "$(env_get TZ || echo UTC)"
}

intake_site() {
    step "Website"
    # Same as $DOMAIN ⇒ website + panel share one host (panel under /admin). A DIFFERENT domain ⇒
    # the public site gets its own host and the panel/admin API are hidden there (served on $DOMAIN).
    ask SITE_DOMAIN "Website domain (same as $DOMAIN ⇒ shared; different ⇒ site on its own host, admin stays on $DOMAIN)" "$(env_get SITE_DOMAIN || echo "$DOMAIN")"
    ask_optional TURNSTILE_SITE_KEY "Cloudflare Turnstile site key (blank to disable)" "$(env_get TURNSTILE_SITE_KEY)"
    ask_optional TURNSTILE_SECRET "Cloudflare Turnstile secret (blank to disable)" "$(env_get TURNSTILE_SECRET)"
    ask VAPID_SUBJECT "Web Push contact for VAPID (mailto:…)" "$(env_get VAPID_SUBJECT || echo "mailto:admin@$DOMAIN")"
}

generate_secrets() {
    step "Generating secrets"
    # Reuse anything already in .env so re-runs never rotate live secrets — rotating
    # POSTGRES_PASSWORD against an initialised pg_data volume would lock out the DB.
    WEBHOOK_SECRET="$(env_get WEBHOOK_SECRET)";               WEBHOOK_SECRET="${WEBHOOK_SECRET:-$(gen_secret)}"
    WEBHOOK_HEADER_SECRET="$(env_get WEBHOOK_HEADER_SECRET)"; WEBHOOK_HEADER_SECRET="${WEBHOOK_HEADER_SECRET:-$(gen_secret)}"
    PANEL_WEBHOOK_SECRET="$(env_get PANEL_WEBHOOK_SECRET)";   PANEL_WEBHOOK_SECRET="${PANEL_WEBHOOK_SECRET:-$(gen_secret)}"
    ADMIN_JWT_SECRET="$(env_get ADMIN_JWT_SECRET)";           ADMIN_JWT_SECRET="${ADMIN_JWT_SECRET:-$(gen_secret)}"
    SITE_COOKIE_SECRET="$(env_get SITE_COOKIE_SECRET)";       SITE_COOKIE_SECRET="${SITE_COOKIE_SECRET:-$(gen_secret)}"
    POSTGRES_USER="$(env_get POSTGRES_USER)";                 POSTGRES_USER="${POSTGRES_USER:-gozar}"
    POSTGRES_DB="$(env_get POSTGRES_DB)";                     POSTGRES_DB="${POSTGRES_DB:-gozar}"
    POSTGRES_PASSWORD="$(env_get POSTGRES_PASSWORD)";         POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(gen_secret)}"
    # VAPID keypair is minted post-build (needs the app image); seed from any existing .env so the
    # first write_env has them set (set -u) and mint_vapid only generates when absent.
    VAPID_PRIVATE_KEY="$(env_get VAPID_PRIVATE_KEY)"
    VAPID_PUBLIC_KEY="$(env_get VAPID_PUBLIC_KEY)"
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

# ── Website ──
SITE_DOMAIN=$SITE_DOMAIN
SITE_COOKIE_SECRET=$SITE_COOKIE_SECRET
TURNSTILE_SECRET=$TURNSTILE_SECRET
TURNSTILE_SITE_KEY=$TURNSTILE_SITE_KEY
VAPID_PRIVATE_KEY=$VAPID_PRIVATE_KEY
VAPID_PUBLIC_KEY=$VAPID_PUBLIC_KEY
VAPID_SUBJECT=$VAPID_SUBJECT

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

mint_vapid() {
    # Mint the Web Push VAPID keypair (raw base64url EC P-256, the format pywebpush/browsers want)
    # inside the built app image — same pattern as mint_admin_hash. Reuse-if-present; failure is
    # non-fatal (push simply stays disabled). Runs after build_images, before mint_admin_hash's
    # write_env so the keys land in .env.
    if [ -n "$VAPID_PRIVATE_KEY" ] && [ -n "$VAPID_PUBLIC_KEY" ]; then
        ok "reusing existing VAPID keypair"
        return 0
    fi
    step "Minting Web Push (VAPID) keypair"
    local out
    out="$(docker compose run --rm --no-deps -T app python -c '
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
k = ec.generate_private_key(ec.SECP256R1())
b = lambda x: base64.urlsafe_b64encode(x).rstrip(b"=").decode()
print(b(k.private_numbers().private_value.to_bytes(32, "big")))
print(b(k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)))
' 2>/dev/null || true)"
    VAPID_PRIVATE_KEY="$(printf '%s\n' "$out" | sed -n '1p' | tr -d '\r')"
    VAPID_PUBLIC_KEY="$(printf '%s\n' "$out" | sed -n '2p' | tr -d '\r')"
    if [ -n "$VAPID_PRIVATE_KEY" ] && [ -n "$VAPID_PUBLIC_KEY" ]; then
        ok "VAPID keypair minted"
    else
        warn "VAPID mint failed — Web Push stays disabled (set VAPID_* in .env later)"
    fi
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
    # Domain separation: when the public website has its own hostname (SITE_DOMAIN) distinct from the
    # admin/bot domain (DOMAIN), render TWO server blocks — the admin panel + Telegram bot + API stay
    # on DOMAIN (plus any ADMIN_DOMAIN alias), while the website gets its own default_server block
    # with /admin and /api/admin hidden. Otherwise the single-domain layout (admin under /admin).
    # Re-running the installer regenerates this from .env, so the split is permanent, not a manual
    # server-only edit.
    if [ -n "${SITE_DOMAIN:-}" ] && [ "$SITE_DOMAIN" != "$DOMAIN" ]; then
        local admin_names="$DOMAIN"
        if [ -n "${ADMIN_DOMAIN:-}" ] && [ "$ADMIN_DOMAIN" != "$DOMAIN" ] \
            && [ "$ADMIN_DOMAIN" != "$SITE_DOMAIN" ]; then
            admin_names="$DOMAIN $ADMIN_DOMAIN"
        fi
        render_tls_nginx_split "$admin_names"
    else
        render_tls_nginx_single
    fi
}

render_tls_nginx_single() {
    cat >"$TLS_NGINX" <<'EOF'
# Generated by install.sh — TLS reverse proxy (server-only; not committed).
# Browser → Cloudflare (edge cert) → origin (this cert). Set Cloudflare SSL/TLS to "Full (strict)".

upstream gozar_app { server app:8000; }
upstream gozar_site { server site:3100; }

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
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /panel-webhook {
        proxy_pass http://gozar_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://gozar_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /health {
        proxy_pass http://gozar_app;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Admin SPA under /admin/ (Vite base "/admin/", copied to html/admin by Dockerfile.frontend).
    location = /admin { return 301 /admin/; }
    location /admin/ {
        root /usr/share/nginx/html;
        try_files $uri /admin/index.html;
    }

    # Everything else -> the Next.js website.
    location / {
        proxy_pass http://gozar_site;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
}

# Split layout: admin+bot+API on $admin_names; public website on its own default_server block.
# Uses an UNQUOTED heredoc so the domain names interpolate — every nginx runtime variable is
# therefore escaped as \$ so the shell leaves it verbatim.
render_tls_nginx_split() {
    local admin_names="$1"
    cat >"$TLS_NGINX" <<EOF
# Generated by install.sh — TLS reverse proxy (server-only; not committed).
# Domain-split: admin panel + Telegram bot + API on [$admin_names]; public website on $SITE_DOMAIN.
# Browser → Cloudflare (edge cert) → origin (this cert). Set Cloudflare SSL/TLS to "Full (strict)".

upstream gozar_app { server app:8000; }
upstream gozar_site { server site:3100; }

# Redirect plain HTTP to HTTPS.
server {
    listen 80;
    server_name _;
    return 301 https://\$host\$request_uri;
}

# ── Admin panel + Telegram bot + API (private domain) ──
server {
    listen 443 ssl;
    http2 on;
    server_name $admin_names;

    ssl_certificate     /etc/nginx/certs/origin.pem;
    ssl_certificate_key /etc/nginx/certs/origin.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_session_cache   shared:SSL:10m;

    client_max_body_size 2m;

    location /tg/ {
        proxy_pass http://gozar_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location = /panel-webhook {
        proxy_pass http://gozar_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /api/ {
        proxy_pass http://gozar_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location = /health {
        proxy_pass http://gozar_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Admin SPA under /admin/ (Vite base "/admin/", copied to html/admin by Dockerfile.frontend).
    location = /admin { return 301 /admin/; }
    location /admin/ {
        root /usr/share/nginx/html;
        try_files \$uri /admin/index.html;
    }

    # This host only serves the panel — send its root to /admin/.
    location / { return 301 /admin/; }
}

# ── Public website (default_server — also answers any unmatched Host) ──
server {
    listen 443 ssl default_server;
    http2 on;
    server_name $SITE_DOMAIN;

    ssl_certificate     /etc/nginx/certs/origin.pem;
    ssl_certificate_key /etc/nginx/certs/origin.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_session_cache   shared:SSL:10m;

    client_max_body_size 2m;

    # The admin panel and admin API are NOT exposed on the public domain.
    location = /admin { return 404; }
    location /admin/ { return 404; }
    location = /api/admin { return 404; }
    location /api/admin/ { return 404; }

    # Public (device-scoped) site API still proxies to the app.
    location /api/ {
        proxy_pass http://gozar_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location = /health {
        proxy_pass http://gozar_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Everything else -> the Next.js website.
    location / {
        proxy_pass http://gozar_site;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
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

    # 1b) Website root + admin panel. Under domain separation the website lives on SITE_DOMAIN and
    #     /admin is hidden there; otherwise both share $DOMAIN (panel under /admin).
    if [ -n "${SITE_DOMAIN:-}" ]; then
        local site_host="$DOMAIN" split=""
        [ "$SITE_DOMAIN" != "$DOMAIN" ] && { site_host="$SITE_DOMAIN"; split=1; }
        local scode="" acode
        for _ in $(seq 10); do
            scode="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 \
                --resolve "$site_host:443:127.0.0.1" "https://$site_host/" 2>/dev/null || true)"
            [ "$scode" = "200" ] && break
            sleep 2
        done
        [ "$scode" = "200" ] && ok "https://$site_host/ (website) → 200" \
            || warn "website root got '${scode:-none}' — see: docker compose logs site"
        acode="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 \
            --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/admin/" 2>/dev/null || true)"
        [ "$acode" = "200" ] && ok "https://$DOMAIN/admin/ (panel) → 200" \
            || warn "admin panel got '${acode:-none}'"
        # Under separation, the panel must be hidden on the public host (expect 404).
        if [ -n "$split" ]; then
            local hcode
            hcode="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 \
                --resolve "$SITE_DOMAIN:443:127.0.0.1" "https://$SITE_DOMAIN/admin/" 2>/dev/null || true)"
            [ "$hcode" = "404" ] && ok "https://$SITE_DOMAIN/admin/ hidden → 404" \
                || warn "admin panel NOT hidden on the public host (got '${hcode:-none}', expected 404)"
        fi
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
    local site_url="https://$DOMAIN" cf_dns="$DOMAIN"
    if [ -n "${SITE_DOMAIN:-}" ] && [ "$SITE_DOMAIN" != "$DOMAIN" ]; then
        site_url="https://$SITE_DOMAIN"
        cf_dns="$DOMAIN and $SITE_DOMAIN"
    fi
    cat >&2 <<EOF

  Website     : $site_url
  Admin panel : https://$DOMAIN/admin   (login: $ADMIN_USERNAME)
  Bot         : @$BOT_USERNAME
  Config      : $ENV_FILE   (chmod 600 — keep private)

  Website     : configure the trial squad, locations & economy in the panel's
                'وب‌سایت' section. Turnstile + Web Push are optional (blank ⇒ off).

  Cloudflare  : DNS records for $cf_dns must be Proxied (orange cloud);
                SSL/TLS mode = Full (strict).

  Panel hook  : In the Remnawave panel, enable the webhook and point it at
                  https://$DOMAIN/panel-webhook
                with secret = PANEL_WEBHOOK_SECRET from $ENV_FILE and the
                user.limited + user.expired events ON. Without this, expiry/limit
                reminders rely solely on the worker's reconcile sweep (every 15m).

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
    intake_site
    generate_secrets
    write_env ""          # initial .env (empty hash) so `docker compose run` can read it
    build_images
    mint_vapid            # mint the VAPID keypair in the built image, before the .env rewrite
    mint_admin_hash       # rewrites .env with the real hash + the minted VAPID keys
    generate_tls
    bring_up
    verify
    report
}

# Guarded entrypoint — `source install.sh` (for tests) defines the functions without running.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
