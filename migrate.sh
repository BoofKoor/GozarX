#!/usr/bin/env bash
#
# GozarX server migration — move a running install to a new server with one command.
#
# Run it on the OLD server, as root, from the project directory:
#     ./migrate.sh 13.140.181.78            # root@ is assumed
#     ./migrate.sh ubuntu@13.140.181.78     # or any user with passwordless sudo
#
# The only manual step is the DNS change it asks for at the end. Everything else is automatic:
#   1. Prepare — no downtime. Installs Docker on the new server, copies the project directory
#      (code, .env, origin certificate, TLS overlay) and the images the old server is running, and
#      proves the new server is reachable on 80/443 and can reach the Remnawave panel and Telegram
#      — from inside a container too, which is where the bot actually runs.
#   2. Cutover — a few minutes offline. Stops the old stack, dumps Postgres and snapshots Redis,
#      restores both on the new server, requires every table's row count to match, then starts
#      the stack and checks it answers the way the old one did and that the app itself reaches
#      Telegram and the panel. ANY failure in this phase rolls back by itself: the new server's
#      volumes are dropped and the old stack, which this script never modifies, is started again.
#   3. DNS — prints the records to change, waits until the public URL is served by the new server,
#      has Telegram deliver the messages that queued up meanwhile, then removes the old containers
#      (the volumes, the dump and the Redis snapshot stay behind as a backup).
#
# The move does not depend on this terminal. Once the SSH connection is open (the one password
# prompt), the work runs in its own session and the terminal only shows its log, so closing the
# window or losing the SSH session to this server ends the view, not the move — `tail -f` on the
# log it names picks it back up. Ctrl-C asks to cancel: honoured before the cutover, ignored
# during it (a half-done cutover is worse than either outcome), and while waiting for the DNS
# switch it just stops waiting.
#
# Nothing in the app depends on the server's IP: the domain, the origin certificate, the Telegram
# webhook and the panel webhook all carry over unchanged.
#
# Optional env:
#   SSH_KEY=<file>        private key for the new server (default: ssh's own keys, else a password)
#   SSH_PORT=<port>       the new server's SSH port (default 22)
#   SKIP_PORT_CHECK=1     skip the inbound 80/443 probe (e.g. a firewall that only admits Cloudflare)
#   DNS_WAIT_MINUTES=<n>  how long phase 3 waits for the switch (default 120)
#
# Organised like install.sh — functions plus a guarded entrypoint, so it can be sourced in tests.

set -Eeuo pipefail

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
R_PROJ=/root/GozarX           # the project on the new server — `cd ~/GozarX` as root, as today
R_MIG=/root/gozarx-migration  # transfer scratch space on the new server
CUTOVER=0                     # 1 once the old stack has been stopped
LIVE=0                        # 1 once the new stack is verified and running: no rollback after it
PROBE=0                       # 1 while the inbound-port probe container runs on the new server
CTL_DIR=""                    # the ssh ControlMaster socket's directory
SSH_OPTS=()
MIG=""                        # this run's directory on the old server: log, dump, Redis snapshot
LOG=""

# ── Logging ───────────────────────────────────────────────────────────────────
if [ -t 2 ] || [ "${GOZARX_COLOR:-}" = 1 ]; then
    C_RESET=$'\033[0m'; C_BLUE=$'\033[34m'; C_GREEN=$'\033[32m'
    C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_BOLD=$'\033[1m'
else
    C_RESET=""; C_BLUE=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BOLD=""
fi
CURRENT_STEP=""
step() { CURRENT_STEP="$*"; printf '\n%s==>%s %s%s%s\n' "$C_BLUE" "$C_RESET" "$C_BOLD" "$*" "$C_RESET" >&2; }
phase() { CURRENT_STEP="$*"; printf '    %s\n' "$*" >&2; }
info() { printf '    %s\n' "$*" >&2; }
ok()   { printf '  %s✓%s %s\n' "$C_GREEN" "$C_RESET" "$*" >&2; }
warn() { printf '  %s!%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
die()  { printf '\n%serror:%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }
env_get() { grep -E "^$1=" "$PROJ/.env" | head -1 | cut -d= -f2- || true; }

# Helpers shared by BOTH machines: evaluated here, and prepended to every script run on the new
# server, so the two sides count rows and probe URLs in exactly the same way.
read -r -d '' COMMON <<'EOF' || true
dc() { (cd "$PROJ" && docker compose -f docker-compose.yml -f docker-compose.tls.yml "$@"); }
psql_in() { dc exec -T postgres sh -c 'psql -X -q -tA -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; }
# One line naming every table with its row count. Both sides must produce the same line.
table_counts() {
    psql_in <<'SQL'
select coalesce(string_agg(format('%s=%s', table_name, (xpath('/row/c/text()',
       query_to_xml(format('select count(*) as c from %I', table_name), false, true, '')))[1]::text),
       ',' order by table_name), '')
from information_schema.tables where table_schema = 'public' and table_type = 'BASE TABLE';
SQL
}
# HTTP status of https://HOST/PATH as served by THIS machine's nginx — DNS and Cloudflare bypassed.
code_of() {
    curl -sk -o /dev/null -w '%{http_code}' --max-time 8 --resolve "$1:443:127.0.0.1" "https://$1$2" \
        2>/dev/null || true
}
wait_code() {  # wait_code HOST PATH SECONDS — until THIS machine answers 200
    local end=$((SECONDS + $3))
    until [ "$(code_of "$1" "$2")" = 200 ]; do
        [ "$SECONDS" -lt "$end" ] || return 1
        sleep 3
    done
}
# The same Remnawave call the bot makes. The token goes in on stdin, never on the command line.
panel_code() {
    local url tok
    url="$(sed -n 's/^PANEL_BASE_URL=//p' "$PROJ/.env" | head -1)"
    tok="$(sed -n 's/^PANEL_API_TOKEN=//p' "$PROJ/.env" | head -1)"
    printf 'Authorization: Bearer %s\n' "$tok" \
        | curl -s -o /dev/null -w '%{http_code}' --max-time 15 -H @- "${url%/}/api/system/stats" \
            2>/dev/null || true
}
# The bot's two outbound calls, made from INSIDE a container: the server reaching Telegram says
# nothing about Docker's own outbound traffic (forwarding rules, MTU), and /health is a plain 200.
read -r -d '' EGRESS_PY <<'PY' || true
import os, urllib.request, urllib.error
def code(url, headers={}):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as r:
            return str(r.status)
    except urllib.error.HTTPError as e:
        return str(e.code)
    except Exception as e:
        return "000 (%s: %s)" % (type(e).__name__, getattr(e, "reason", e))
print("TG=" + code("https://api.telegram.org/bot" + os.environ.get("BOT_TOKEN", "") + "/getMe"))
print("PANEL=" + code(os.environ.get("PANEL_BASE_URL", "").rstrip("/") + "/api/system/stats",
                      {"Authorization": "Bearer " + os.environ.get("PANEL_API_TOKEN", "")}))
PY
# egress_check LPANEL LAUNCHER... — run the probe through LAUNCHER (`docker run … IMAGE`, or
# `dc exec -T app`) and name what the bot could not reach. Any answer from Telegram counts: the
# token is the one the old server already uses; the question is only whether traffic gets out.
egress_check() {
    local lpanel="$1" out tg panel
    shift
    out="$("$@" python -c "$EGRESS_PY" 2>&1 </dev/null || true)"
    tg="$(printf '%s\n' "$out" | sed -n 's/^TG=//p')"
    panel="$(printf '%s\n' "$out" | sed -n 's/^PANEL=//p')"
    if [ -z "$tg" ] || [ "${tg%% *}" = 000 ]; then
        echo "from inside a container the new server can't reach api.telegram.org: ${tg:-$out}" >&2
        return 1
    fi
    if [ "$lpanel" = 200 ] && [ "${panel%% *}" != 200 ]; then
        echo "from inside a container the new server gets '${panel:-nothing}' from the Remnawave panel (the old server gets 200)" >&2
        return 1
    fi
}
EOF

# ── Remote execution ──────────────────────────────────────────────────────────
set_ssh_opts() {
    SSH_OPTS=(-o "ControlPath=$CTL_DIR/c" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15
        -o ServerAliveInterval=20 -o ServerAliveCountMax=9 -p "${SSH_PORT:-22}")
    if [ -n "${SSH_KEY:-}" ]; then SSH_OPTS+=(-i "$SSH_KEY"); fi
}
rsh() { ssh "${SSH_OPTS[@]}" -o ControlMaster=no "$TARGET" "$@"; }

# remote [NAME=value ...] <<'EOF' ... EOF — run a bash script as root on the new server. The script
# travels as an ARGUMENT (base64), never on stdin, so no command inside it can swallow the rest.
remote() {
    local script kv b64
    script="set -Eeuo pipefail"$'\n'"PROJ=$R_PROJ MIG=$R_MIG"$'\n'
    for kv in "$@"; do script+="$(printf '%s=%q' "${kv%%=*}" "${kv#*=}")"$'\n'; done
    script+="$COMMON"$'\n'"$(cat)"
    b64="$(printf '%s' "$script" | base64 | tr -d '\n')"
    # shellcheck disable=SC2029  # expanded here on purpose: the remote side only decodes it
    rsh "$SUDO bash -c \"\$(echo $b64 | base64 -d)\"" </dev/null
}

# put_file LOCAL REMOTE — copy one file to the new server (paths without spaces).
put_file() {
    # shellcheck disable=SC2029
    rsh "$SUDO sh -c 'cat > $2'" <"$1"
}

close_ssh() {
    if [ -n "$CTL_DIR" ]; then
        ssh "${SSH_OPTS[@]}" -O exit "$TARGET" >/dev/null 2>&1 || true
        rm -rf "$CTL_DIR"
        CTL_DIR=""
    fi
}

# ── Steps ─────────────────────────────────────────────────────────────────────
usage() {
    cat >&2 <<'EOF'
Move this GozarX install to a new server. On the OLD server, as root, from the project directory:
    ./migrate.sh NEW_SERVER_IP          (logs in as root)
    ./migrate.sh user@NEW_SERVER_IP     (a user with passwordless sudo)
The only manual step is the DNS change it asks for at the end.
Optional env: SSH_KEY, SSH_PORT, SKIP_PORT_CHECK=1, DNS_WAIT_MINUTES.
EOF
    exit 2
}

parse_target() {
    TARGET="$1"
    case "$TARGET" in
        *@*) R_USER="${TARGET%%@*}"; R_HOST="${TARGET#*@}" ;;
        *) R_USER=root; R_HOST="$TARGET"; TARGET="root@$TARGET" ;;
    esac
    if [ -z "$R_USER" ] || [ -z "$R_HOST" ]; then usage; fi
    SUDO=""
    [ "$R_USER" = root ] || SUDO="sudo -n"
}

find_project() {
    local d
    for d in "${PROJECT_DIR:-}" "$SCRIPT_DIR" "$PWD" "$HOME/GozarX"; do
        if [ -n "$d" ] && [ -f "$d/docker-compose.yml" ] && [ -f "$d/.env" ]; then
            PROJ="$(cd "$d" && pwd)"
            return 0
        fi
    done
    die "run this from the GozarX project directory (no docker-compose.yml + .env found)"
}

# Read-only: find the project, read .env, and record what the old server answers today — which
# is what the new one must answer after the move.
local_preflight() {
    [ "$(id -u)" = 0 ] || die "run as root"
    have ssh || die "the ssh client is required"
    have setsid || die "setsid (util-linux) is required"
    docker compose version >/dev/null 2>&1 || die "docker compose is required"
    find_project
    eval "$COMMON"
    local f
    for f in .env docker-compose.tls.yml nginx/nginx.tls.conf nginx/certs/origin.pem nginx/certs/origin.key; do
        [ -f "$PROJ/$f" ] || die "missing $PROJ/$f — run this on the installed (old) server"
    done
    DOMAIN="$(env_get DOMAIN)"; SITE_DOMAIN="$(env_get SITE_DOMAIN)"; ADMIN_DOMAIN="$(env_get ADMIN_DOMAIN)"
    [ -n "$DOMAIN" ] || die "DOMAIN is empty in .env"
    PROJECT_NAME="$(dc config 2>/dev/null | sed -n 's/^name: *//p' | head -1 || true)"
    PROJECT_NAME="${PROJECT_NAME:-gozar}"
    dc exec -T postgres pg_isready -q </dev/null >/dev/null 2>&1 \
        || die "the old stack's database is not running — nothing to migrate (already moved?)"
    APP_IMAGE="$(docker inspect -f '{{.Config.Image}}' "$(dc ps -q app)" 2>/dev/null || true)"
    [ -n "$APP_IMAGE" ] || die "the old stack's app container is not running — nothing to migrate"

    CHECKS=""
    local site_host="${SITE_DOMAIN:-$DOMAIN}" c h p
    for c in "$DOMAIN|/health" "$DOMAIN|/admin/" "$site_host|/"; do
        h="${c%%|*}"; p="${c#*|}"
        if [ "$(code_of "$h" "$p")" = 200 ]; then
            CHECKS+="$c "
        elif [ "$p" = /health ]; then
            die "the old stack is not healthy (https://$h/health) — fix that before moving it"
        else
            warn "https://$h$p is not 200 on the old server either — it won't be checked after the move"
        fi
    done
}

open_ssh() {
    step "Connecting to $TARGET"
    CTL_DIR="$(mktemp -d /tmp/gozarx-migrate.XXXXXX)"
    set_ssh_opts
    info "if asked, enter the new server's password — once; the connection is reused after that"
    ssh "${SSH_OPTS[@]}" -o ControlMaster=yes -o ControlPersist=yes -fN "$TARGET" \
        || die "cannot SSH to $TARGET (check the address, the password or key, and port ${SSH_PORT:-22})"
    rsh "$SUDO true" </dev/null \
        || die "$R_USER on $R_HOST can't become root — use root, or a user with passwordless sudo"
    # A mistyped address that lands back on THIS machine would stop the only copy of the bot.
    local marker
    marker="$(mktemp /tmp/gozarx-migrate-self.XXXXXX)"
    # shellcheck disable=SC2029
    if rsh "test -e $marker" </dev/null; then
        rm -f "$marker"
        die "$R_HOST is this same server — pass the NEW server's address"
    fi
    rm -f "$marker"
    ok "connected"
}

check_cancel() {
    if [ -e "$MIG/cancel" ]; then die "cancelled — nothing was changed; the old server keeps running"; fi
}

remote_preflight() {
    step "Preparing the new server (no downtime yet)"
    remote PROJECT_NAME="$PROJECT_NAME" <<'EOF'
[ "$(uname -s)" = Linux ] || { echo "the new server is not Linux" >&2; exit 1; }
apt_get() { command -v apt-get >/dev/null 2>&1 && DEBIAN_FRONTEND=noninteractive apt-get -qq "$@" >/dev/null 2>&1; }
if ! command -v curl >/dev/null 2>&1; then apt_get update && apt_get install -y curl || true; fi
command -v curl >/dev/null 2>&1 || { echo "curl is missing on the new server and could not be installed" >&2; exit 1; }
if ! command -v docker >/dev/null 2>&1; then
    echo "    installing Docker (get.docker.com) — a minute or two" >&2
    curl -fsSL https://get.docker.com | sh >/root/gozarx-docker-install.log 2>&1 \
        || { tail -n 20 /root/gozarx-docker-install.log >&2; echo "Docker install failed" >&2; exit 1; }
fi
docker info >/dev/null 2>&1 || systemctl enable --now docker >/dev/null 2>&1 || service docker start >/dev/null 2>&1 || true
for _ in $(seq 30); do docker info >/dev/null 2>&1 && break; sleep 1; done
docker info >/dev/null 2>&1 || { echo "the Docker daemon is not running on the new server" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "the Docker Compose plugin is missing on the new server" >&2; exit 1; }
# git is only for future `git pull` deploys there; the move itself does not need it.
if ! command -v git >/dev/null 2>&1; then apt_get install -y git || { apt_get update && apt_get install -y git; } || true; fi
# Only ever touch the stack this script creates — never one that is already there.
existing="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT_NAME")$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT_NAME")"
if [ -n "$existing" ]; then
    echo "the new server already has a '$PROJECT_NAME' stack or volumes — refusing to touch them." >&2
    echo "if they are left over from an earlier attempt, remove them there with:" >&2
    echo "    cd $PROJ && docker compose -f docker-compose.yml -f docker-compose.tls.yml down -v" >&2
    exit 1
fi
mkdir -p "$MIG" && chmod 700 "$MIG"
EOF
    ok "Docker is ready on $R_HOST"
}

ship_project() {
    step "Copying the project (code, .env, origin certificate, TLS config)"
    remote <<'EOF'
if [ -e "$PROJ" ]; then mv "$PROJ" "$PROJ.before-migrate.$(date +%Y%m%d%H%M%S)"; fi
mkdir -p "$PROJ"
EOF
    tar -C "$PROJ" -czf - --exclude=node_modules --exclude=.venv --exclude=__pycache__ \
        --exclude=.pytest_cache --exclude=.ruff_cache --exclude=.next . \
        | rsh "$SUDO tar -C $R_PROJ -xzf -"
    ok "copied to $R_HOST:$R_PROJ"
}

remote_checks() {
    step "Checking the new server can do the job"
    LPANEL="$(panel_code)"   # what the old server gets from the panel — the bar the new one must meet
    remote LPANEL="$LPANEL" <<'EOF'
rpanel="$(panel_code)"
if [ "$LPANEL" = 200 ] && [ "$rpanel" != 200 ]; then
    echo "the new server can't use the Remnawave panel (HTTP $rpanel; the old server gets 200)." >&2
    echo "if the panel only admits known IPs, allow this server's IP there, then run again." >&2
    exit 1
fi
tg="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://api.telegram.org/ 2>/dev/null || true)"
[ "$tg" != 000 ] || { echo "the new server can't reach api.telegram.org" >&2; exit 1; }
busy="$(ss -Hltn '( sport = :80 or sport = :443 )' 2>/dev/null || true)"
[ -z "$busy" ] || { printf 'ports 80/443 are already in use on the new server:\n%s\n' "$busy" >&2; exit 1; }
avail_kb="$(df -Pk /var/lib/docker 2>/dev/null | awk 'NR == 2 {print $4}')"
[ "${avail_kb:-0}" -ge 4194304 ] || { echo "the new server needs at least 4 GB free disk" >&2; exit 1; }
EOF
    [ "$LPANEL" = 200 ] || warn "the panel answers HTTP $LPANEL from the old server too — not a blocker for the move"
    ok "panel and Telegram reachable, ports 80/443 free, disk ok"
}

probe_egress() {
    step "Checking the bot can reach Telegram and the panel from inside a container"
    remote LPANEL="$LPANEL" APP_IMAGE="$APP_IMAGE" <<'EOF'
if ! egress_check "$LPANEL" docker run --rm --env-file "$PROJ/.env" "$APP_IMAGE"; then
    echo "the server itself reaches them, so Docker's outbound traffic is what is blocked there —" >&2
    echo "typically a firewall rule on forwarded traffic, or a network MTU below 1500" >&2
    exit 1
fi
EOF
    ok "reachable from inside a container"
}

ship_images() {
    local la ra
    la="$(uname -m)"
    ra="$(rsh uname -m </dev/null)"
    if [ "$la" != "$ra" ]; then build_remote "$la" "$ra"; return; fi
    step "Copying the running images (the new server builds nothing)"
    local imgs=() img mb
    mapfile -t imgs < <({ dc config --images 2>/dev/null || dc config 2>/dev/null | sed -n 's/^ *image: *//p'; } \
        | tr -d '"' | sort -u)
    [ "${#imgs[@]}" -gt 0 ] || die "could not list the stack's images"
    for img in "${imgs[@]}"; do
        docker image inspect "$img" >/dev/null 2>&1 || { build_remote "$la" "$ra"; return; }
    done
    mb="$(docker image inspect -f '{{.Size}}' "${imgs[@]}" | awk '{s += $1} END {printf "%d", s / 1048576}')"
    info "${imgs[*]}"
    info "~${mb} MB before compression — a few minutes, the bot stays online meanwhile"
    docker save "${imgs[@]}" | gzip -1 | rsh "$SUDO docker load" >/dev/null
    ok "images loaded on the new server"
}

build_remote() {
    step "Building the images on the new server (it is $2; this server's $1 images can't run there)"
    info "several minutes — the bot stays online meanwhile"
    remote <<'EOF'
# A small VPS runs out of memory in the Next.js build; give it swap first.
mem_kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
swap_kb="$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)"
if [ "$mem_kb" -lt 2000000 ] && [ "$swap_kb" -eq 0 ] && [ ! -e /swapfile ]; then
    fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
    echo "    added a 2 GB swapfile for the build" >&2
fi
for try in 1 2 3; do
    if dc build >"$MIG/build.log" 2>&1 && dc pull postgres redis >>"$MIG/build.log" 2>&1; then exit 0; fi
    if [ "$try" != 3 ]; then echo "    build attempt $try failed — retrying" >&2; sleep $((try * 30)); fi
done
tail -n 30 "$MIG/build.log" >&2
exit 1
EOF
    ok "images built on the new server"
}

# Reachable from OUTSIDE on 80 and 443? A cloud firewall / security group would otherwise only
# show up after the cutover, as a DNS switch that never goes live. A throwaway web server on
# both ports, fetched from here, answers that before any downtime. Plain `docker run`, not
# `compose run`: compose would create the project's volumes, and an empty volume left by a
# failed first attempt would then trip the "already has a stack" guard on the retry.
probe_inbound() {
    if [ "${SKIP_PORT_CHECK:-0}" = 1 ]; then warn "skipping the inbound 80/443 check (SKIP_PORT_CHECK=1)"; return; fi
    step "Checking the new server is reachable on 80 and 443"
    PROBE=1
    remote APP_IMAGE="$APP_IMAGE" <<'EOF'
docker rm -f gozarx-migrate-probe >/dev/null 2>&1 || true
docker run -d --rm --name gozarx-migrate-probe -p 80:8080 -p 443:8080 "$APP_IMAGE" \
    python -m http.server 8080 --directory /tmp >/dev/null \
    || { echo "could not start a test web server on ports 80/443 of the new server" >&2; exit 1; }
EOF
    local p code failed=""
    for p in 80 443; do
        for _ in 1 2 3 4 5; do
            code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "http://$R_HOST:$p/" 2>/dev/null || true)"
            [ "$code" = 200 ] && break
            sleep 2
        done
        [ "$code" = 200 ] || failed+=" $p"
    done
    remote <<<'docker rm -f gozarx-migrate-probe >/dev/null 2>&1 || true'
    PROBE=0
    [ -z "$failed" ] || die "the new server is not reachable from outside on port(s)$failed — open 80 and 443 in its firewall / security group and run again (SKIP_PORT_CHECK=1 if it only admits Cloudflare)"
    ok "reachable from outside on 80 and 443"
}

cutover() {
    step "Cutover — the bot goes offline until the DNS switch"
    info "starting in 10 s — Ctrl-C now cancels; nothing has changed yet"
    for _ in 1 2 3 4 5 6 7 8 9 10; do check_cancel; sleep 1; done
    check_cancel
    CUTOVER=1
    info "(from here it can't be interrupted — it finishes or rolls back by itself)"

    local services
    phase "stopping the old stack"
    services="$(dc config --services | grep -vxE 'postgres|redis' | tr '\n' ' ')"
    # shellcheck disable=SC2086  # a list of service names
    dc stop $services
    phase "dumping the database"
    # shellcheck disable=SC2016  # expanded inside the postgres container, from its own env
    dc exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges' \
        </dev/null | gzip >"$MIG/gozar.sql.gz"
    zgrep -q 'PostgreSQL database dump complete' "$MIG/gozar.sql.gz" || die "the database dump is incomplete"
    OLD_COUNTS="$(table_counts)"
    [ -n "$OLD_COUNTS" ] || die "could not read the old row counts"
    dc stop redis postgres
    dc run --rm --no-deps -T -v "$MIG:/backup" redis sh -c 'tar czf /backup/redis.tgz -C /data .' </dev/null
    ok "old stack stopped — dump and Redis snapshot kept in $MIG"

    phase "restoring on the new server"
    put_file "$MIG/gozar.sql.gz" "$R_MIG/gozar.sql.gz"
    put_file "$MIG/redis.tgz" "$R_MIG/redis.tgz"
    local out
    out="$(remote <<'EOF'
dc run --rm --no-deps -T -v "$MIG:/backup" redis sh -c 'tar xzf /backup/redis.tgz -C /data' </dev/null >&2
dc up -d postgres >&2
# Only the FINAL server listens on TCP — the image's init-time server is socket-only — so this
# can't report ready while initdb is still running.
for _ in $(seq 120); do dc exec -T postgres pg_isready -h localhost -q </dev/null && break; sleep 1; done
gunzip -c "$MIG/gozar.sql.gz" | psql_in >/dev/null
echo "COUNTS=$(table_counts)"
EOF
)"
    NEW_COUNTS="$(printf '%s\n' "$out" | sed -n 's/^COUNTS=//p')"
    [ "$NEW_COUNTS" = "$OLD_COUNTS" ] \
        || die "row counts differ after the restore — old: $OLD_COUNTS · new: $NEW_COUNTS"
    ok "database and Redis restored — every table's row count matches ($(tr ',' '\n' <<<"$OLD_COUNTS" | wc -l) tables)"

    phase "starting the new stack"
    remote CHECKS="$CHECKS" LPANEL="$LPANEL" <<'EOF'
# Everything but the worker first. The worker is the only part that acts on its own (reminders,
# sweeps, backups), so it starts once the rest is proven — a rollback never races it.
dc up -d $(dc config --services | grep -vx worker) >&2
for c in $CHECKS; do
    host="${c%%|*}"; path="${c#*|}"
    if ! wait_code "$host" "$path" 180; then
        echo "https://$host$path does not answer 200 on the new server" >&2
        dc logs --tail=30 app nginx >&2 || true
        exit 1
    fi
    echo "  ✓ https://$host$path → 200 on the new server" >&2
done
# The bot's real work is outbound — answering Telegram, provisioning on the panel — which none of
# the URLs above exercise. Probe it from the app container itself before calling the move done.
for try in 1 2 3; do
    if egress_check "$LPANEL" dc exec -T app 2>"$MIG/egress.err"; then break; fi
    if [ "$try" = 3 ]; then cat "$MIG/egress.err" >&2; exit 1; fi
    sleep 5
done
echo "  ✓ the app reaches Telegram and the panel" >&2
dc up -d >&2
rm -f "$MIG/gozar.sql.gz" "$MIG/redis.tgz" "$MIG/egress.err"
EOF
    LIVE=1
    if [ -e "$MIG/cancel" ]; then
        rm -f "$MIG/cancel"
        info "(the cancel request arrived after the cutover had started, so it was not applied)"
    fi
    ok "the new server is serving — it goes public with the DNS switch"
}

rollback() {
    printf '\n' >&2
    warn "the cutover failed — rolling back (a minute or two; the old server comes back as it was)"
    if remote <<'EOF' >/dev/null 2>&1
dc down -v --remove-orphans
rm -f "$MIG/gozar.sql.gz" "$MIG/redis.tgz"
EOF
    then
        info "new server cleaned up"
    else
        warn "could not clean up the new server — before retrying, run there:"
        warn "    cd $R_PROJ && docker compose -f docker-compose.yml -f docker-compose.tls.yml down -v"
    fi
    dc up -d >&2
    if wait_code "$DOMAIN" /health 180; then
        ok "the old server is serving again — nothing was lost"
    else
        warn "the old stack did not come back healthy — see: docker compose -f docker-compose.yml -f docker-compose.tls.yml logs app"
    fi
    warn "the reason is above; the full log is $LOG"
}

dns_switch() {
    local hosts=("$DOMAIN") h
    for h in "$SITE_DOMAIN" "$ADMIN_DOMAIN"; do
        if [ -n "$h" ] && [[ " ${hosts[*]} " != *" $h "* ]]; then hosts+=("$h"); fi
    done
    printf '\n%s%s  Your one manual step — Cloudflare → DNS → Records:%s\n\n' "$C_BOLD" "$C_YELLOW" "$C_RESET" >&2
    for h in "${hosts[@]}"; do
        printf '      %-40s  A  →  %s   (keep it Proxied, orange cloud)\n' "$h" "$R_HOST" >&2
    done
    printf '\n      Delete any AAAA record for these names; leave every other record alone.\n' >&2
    printf '      Waiting for the switch — this finishes by itself once it is live.\n\n' >&2

    local left=("${hosts[@]}") next code last=$SECONDS
    local deadline=$((SECONDS + ${DNS_WAIT_MINUTES:-120} * 60))
    while :; do
        next=()
        for h in "${left[@]}"; do
            # The old stack is stopped, so a 200 here can only come from the new server.
            code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$h/health" 2>/dev/null || true)"
            if [ "$code" = 200 ]; then
                ok "$h is now served by the new server"
                if [ "$h" = "$DOMAIN" ]; then kick_webhook; fi
            else
                next+=("$h")
            fi
        done
        [ "${#next[@]}" -gt 0 ] || break
        left=("${next[@]}")
        if [ -e "$MIG/cancel" ] || [ "$SECONDS" -ge "$deadline" ]; then
            warn "stopped waiting for: ${left[*]}"
            warn "the new server is live — change the records whenever you're ready; nothing else is needed."
            exit 1
        fi
        if [ $((SECONDS - last)) -ge 60 ]; then info "still waiting for: ${left[*]}"; last=$SECONDS; fi
        sleep 10
    done
}

# While the bot's domain still pointed at the stopped old server, Telegram queued every message and
# spaced its retries further apart after each failure — so a bot that already works can stay silent
# for minutes after the switch. Registering the same webhook again makes Telegram retry at once,
# and the queue is kept (drop_pending_updates stays false).
kick_webhook() {
    local tok resp
    tok="$(env_get BOT_TOKEN)"
    resp="$(curl -s --max-time 15 "https://api.telegram.org/bot$tok/setWebhook" \
        --data-urlencode "url=https://$DOMAIN/tg/$(env_get WEBHOOK_SECRET)" \
        --data-urlencode "secret_token=$(env_get WEBHOOK_HEADER_SECRET)" 2>/dev/null || true)"
    if printf '%s' "$resp" | grep -Eq '"ok": *true'; then
        ok "Telegram asked to deliver the messages that queued up during the switch"
    else
        warn "couldn't re-register the webhook with Telegram — it will still retry on its own"
    fi
}

# Wait (up to two minutes) for Telegram to hand that queue over, and say how it went.
report_webhook() {
    local tok hook="" pending="" err
    tok="$(env_get BOT_TOKEN)"
    for _ in $(seq 24); do
        hook="$(curl -fsS --max-time 10 "https://api.telegram.org/bot$tok/getWebhookInfo" 2>/dev/null || true)"
        pending="$(printf '%s' "$hook" | grep -oE '"pending_update_count": *[0-9]+' | grep -oE '[0-9]+$' || true)"
        if [ -z "$pending" ] || [ "$pending" -le 3 ]; then break; fi
        sleep 5
    done
    if [ -z "$pending" ]; then
        warn "couldn't read the webhook status from Telegram — send /start to the bot to check"
    elif ! printf '%s' "$hook" | grep -Eq "\"url\": *\"https://${DOMAIN//./\\.}/tg/"; then
        warn "Telegram's webhook does not point at https://$DOMAIN/tg/… — send /start to the bot to check"
    elif [ "$pending" -le 3 ]; then
        ok "Telegram webhook → https://$DOMAIN/tg/… — its queue is delivered, the bot is answering"
    else
        err="$(printf '%s' "$hook" | grep -oE '"last_error_message": *"[^"]*"' \
            | sed -E 's/^"last_error_message": *"//; s/"$//' || true)"
        warn "Telegram still holds $pending messages for the bot${err:+ — its last error: $err}"
        warn "it keeps retrying them; send /start to the bot to check"
    fi
}

finish() {
    dc down >/dev/null 2>&1 || true   # the old containers go; its volumes stay as a backup
    report_webhook
    printf '\n%s%s GozarX now runs on %s %s\n' "$C_BOLD" "$C_GREEN" "$R_HOST" "$C_RESET" >&2
    cat >&2 <<EOF

  Deploys    : on the NEW server now — the same commands as before (cd ~/GozarX …)
  Backup     : $MIG on this server — the database dump and Redis snapshot from the cutover
  This server: its containers are removed and its volumes kept; delete it once you're happy
EOF
}

on_err() {
    # Once, from the main shell: a failure inside $(…) surfaces again when its caller fails.
    [ "$BASH_SUBSHELL" = 0 ] || return 0
    printf '  %s!%s stopped while: %s\n' "$C_RED" "$C_RESET" "$CURRENT_STEP" >&2
}

on_exit() {
    local rc=$?
    set +e
    trap '' INT TERM PIPE   # nothing may cut a rollback short
    trap - EXIT ERR
    if [ "$CUTOVER" = 1 ] && [ "$LIVE" = 0 ]; then
        rollback
        rc=1
    fi
    if [ "$PROBE" = 1 ]; then
        remote <<<'docker rm -f gozarx-migrate-probe >/dev/null 2>&1 || true' >/dev/null 2>&1 || true
    fi
    close_ssh
    echo "$rc" >"$MIG/exit-code"
    exit "$rc"
}

# The move itself, in its own session with no terminal: no Ctrl-C or hangup can reach it or the
# ssh/docker commands it runs (both catch those signals themselves, so ignoring them is not
# enough). Its output goes to the log, which the foreground shows.
work() {
    MIG="$GOZARX_MIG"; LOG="$MIG/migrate.log"; CTL_DIR="$GOZARX_CTL_DIR"
    echo "$$" >"$MIG/worker.pid"
    set_ssh_opts
    trap on_exit EXIT
    trap 'exit 143' TERM   # an admin's `kill` still ends in a clean rollback
    trap on_err ERR
    local_preflight
    remote_preflight
    check_cancel
    ship_project
    check_cancel
    remote_checks
    check_cancel
    ship_images
    check_cancel
    probe_inbound
    check_cancel
    probe_egress
    cutover
    close_ssh
    dns_switch
    finish
}

# The foreground — the only part tied to this terminal. It checks this server, opens the SSH
# connection (so a password is typed once, here), starts the move in its own session and shows
# its log until it ends. Ctrl-C asks the move to cancel; a second one only stops watching.
watch() {
    printf '%s%s GozarX migration → %s %s\n' "$C_BOLD" "$C_BLUE" "$R_HOST" "$C_RESET" >&2
    step "Checking this (old) server"
    local_preflight
    ok "project $PROJ · domain $DOMAIN"
    MIG="$HOME/gozarx-migration-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$MIG"
    chmod 700 "$MIG"
    LOG="$MIG/migrate.log"
    : >"$LOG"
    trap close_ssh EXIT   # until the worker owns the connection
    open_ssh

    local color=0 worker="" rc
    [ -z "$C_RESET" ] || color=1
    GOZARX_MIGRATE_WORKER=1 GOZARX_MIG="$MIG" GOZARX_CTL_DIR="$CTL_DIR" GOZARX_COLOR="$color" \
        setsid bash "$SCRIPT_PATH" "$TARGET" </dev/null >>"$LOG" 2>&1 &
    for _ in $(seq 100); do
        if [ -s "$MIG/worker.pid" ]; then worker="$(cat "$MIG/worker.pid")"; break; fi
        sleep 0.2
    done
    [ -n "$worker" ] || die "the move did not start — see $LOG"
    trap - EXIT           # the worker closes the connection when it is done
    info "the move runs on its own from here — losing this window won't stop it. Follow it with:"
    info "    tail -f $LOG"

    CANCELS=0
    trap on_watch_int INT
    tail -n +1 -f --pid="$worker" "$LOG" 2>/dev/null || true
    while kill -0 "$worker" 2>/dev/null; do tail -n 0 -f --pid="$worker" "$LOG" 2>/dev/null || sleep 1; done
    rc="$(cat "$MIG/exit-code" 2>/dev/null || echo 1)"
    exit "$rc"
}

on_watch_int() {
    CANCELS=$((CANCELS + 1))
    if [ "$CANCELS" -gt 1 ]; then
        printf '\n  stopped watching — the move carries on. Follow it with:  tail -f %s\n' "$LOG" >&2
        exit 130
    fi
    touch "$MIG/cancel"
    printf '\n  ! cancel requested — press Ctrl-C again to just stop watching\n' >&2
}

main() {
    case "${1:-}" in "" | -h | --help) usage ;; esac
    parse_target "$1"
    if [ "${GOZARX_MIGRATE_WORKER:-}" = 1 ]; then work; else watch; fi
}

# Guarded entrypoint — `source migrate.sh` (for tests) defines the functions without running.
# The `exit` sits inside the block bash has already read, so a file changed on disk while a move
# runs (a `git pull` in this directory) is never read past this point.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
    exit
fi
