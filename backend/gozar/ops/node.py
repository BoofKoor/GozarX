"""Turn a server into a Remnawave node over SSH and register it in a panel.

On the server (everything here is undone by `undo`):
  /opt/remnanode/docker-compose.yml  the official node compose (host network, NET_ADMIN, nofile);
                                     SECRET_KEY lives in .env next to it instead of inline
  /opt/remnanode/.env                NODE_PORT + SECRET_KEY, mode 0600 (the key holds a private key)
  /opt/remnanode/.gozar.json         what the bot did: panel, node uuid, ufw rules, backup dir
  Docker                             get.docker.com, or the distro's docker.io if that is blocked
  ufw                                allow rules for the node port and the inbound ports, only when
                                     ufw is active, only the ones that were missing (recorded)
A standard existing install (/opt/remnanode with a compose file) is replaced only after the admin
confirms it, and is moved to /opt/remnanode.bak-<time> first so `undo` can bring it back.
"""

from __future__ import annotations

import asyncio
import json
import re
import shlex
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field

import httpx

from gozar.ops.errors import RemoteError
from gozar.ops.geo import GeoInfo, country_name, flag_of, is_public, known
from gozar.ops.geo import lookup as geo_lookup
from gozar.ops.packages import apt_update, ensure_packages
from gozar.ops.report import Reporter
from gozar.ops.ssh import Server
from gozar.remnawave.ops import NodeInfo, OpsPanel, PanelError, Profile

NODE_DIR = "/opt/remnanode"
MARKER = f"{NODE_DIR}/.gozar.json"
DEFAULT_IMAGE = "remnawave/node:latest"
GHCR_IMAGE = "ghcr.io/remnawave/node:latest"  # same release, published by the Remnawave CI
NODE_PORT_CANDIDATES = [2222, *range(2223, 2260)]
MIN_DISK_MB = 900  # Docker + node image
LOW_DISK_MB = 2000
LOW_MEM_MB = 450
CONNECT_TIMEOUT = 180  # panel -> node
INBOUND_TIMEOUT = 60  # Xray binding the inbound ports after the panel sent the config


def image_candidates(node_image: str = "") -> list[str]:
    """The configured image; for the default one also the ghcr.io copy (Docker Hub rate-limits
    and refuses some countries, ghcr.io usually works there)."""
    img = (node_image or "").strip() or DEFAULT_IMAGE
    return [img, GHCR_IMAGE] if img == DEFAULT_IMAGE else [img]


# ======================================================================================
# facts
# ======================================================================================

FACTS_SCRIPT = r"""
. /etc/os-release 2>/dev/null
echo "os_id=${ID:-}"; echo "os_like=${ID_LIKE:-}"; echo "os_pretty=${PRETTY_NAME:-}"
echo "arch=$(uname -m)"
echo "systemd=$([ -d /run/systemd/system ] && echo 1 || echo 0)"
echo "apt=$(command -v apt-get >/dev/null 2>&1 && echo 1 || echo 0)"
echo "virt=$(systemd-detect-virt 2>/dev/null || echo none)"
echo "ufw=$(ufw status 2>/dev/null | grep '^Status: active' >/dev/null && echo 1 || echo 0)"
echo "mem_mb=$(awk '/^MemTotal:/{print int($2/1024)}' /proc/meminfo)"
echo "disk_mb=$(df -Pm / | awk 'NR==2{print $4}')"
if command -v docker >/dev/null 2>&1; then
  v=$(docker version --format '{{.Server.Version}}' 2>/dev/null); echo "docker=${v:-broken}"
  if docker compose version >/dev/null 2>&1; then echo "compose=plugin"
  elif command -v docker-compose >/dev/null 2>&1; then echo "compose=v1"; else echo "compose="; fi
  echo "rn_container=$(docker ps -a --filter 'name=^/remnanode$' --format '{{.State}}|{{.Status}}|{{.Image}}' 2>/dev/null | head -n 1)"
  echo "rn_workdir=$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' remnanode 2>/dev/null)"
  echo "rn_pids=$(docker top remnanode -eo pid 2>/dev/null | tail -n +2 | tr '\n' ' ')"
fi
echo "rn_dir=$([ -e /opt/remnanode ] && echo 1 || echo 0)"
echo "rn_compose=$(ls -1 /opt/remnanode/docker-compose.yml /opt/remnanode/docker-compose.yaml /opt/remnanode/compose.yml /opt/remnanode/compose.yaml 2>/dev/null | head -n 1)"
echo "@@marker"; cat /opt/remnanode/.gozar.json 2>/dev/null; echo
echo "@@tcp"; ss -Hltnp 2>/dev/null
echo "@@udp"; ss -Hlunp 2>/dev/null
echo "@@end"
"""

_PROC = re.compile(r'\("([^"]+)",pid=(\d+)')


@dataclass
class Listener:
    proto: str
    addr: str
    port: int
    proc: str
    pids: tuple[int, ...]


@dataclass
class NodeFacts:
    os_id: str = ""
    os_like: str = ""
    os_pretty: str = ""
    arch: str = ""
    systemd: bool = False
    apt: bool = False
    virt: str = ""
    ufw_active: bool = False
    mem_mb: int = 0
    disk_mb: int = 0
    docker: str = ""  # server version | "broken" (CLI, no daemon) | "" (none)
    compose: str = ""  # "plugin" | "v1" | ""
    rn_container: str = ""  # "running|Up 3 days|remnawave/node:latest"
    rn_workdir: str = ""  # compose working dir of that container
    rn_pids: set[int] = field(default_factory=set)
    rn_dir: bool = False
    rn_compose: str = ""  # compose file inside /opt/remnanode
    marker: dict | None = None  # .gozar.json of an earlier install by this bot
    listeners: list[Listener] = field(default_factory=list)

    @property
    def apt_based(self) -> bool:
        return self.apt and (
            self.os_id in ("ubuntu", "debian")
            or "debian" in self.os_like
            or "ubuntu" in self.os_like
        )

    @property
    def has_docker(self) -> bool:
        return bool(self.docker) and self.docker != "broken"

    def owner(self, port: int, proto: str, ignore_pids: set[int] = frozenset()) -> str | None:
        for ls in self.listeners:
            if (
                ls.port == port
                and ls.proto == proto
                and not (ls.pids and set(ls.pids) <= ignore_pids)
            ):
                return ls.proc or "?"
        return None

    def used_ports(self, ignore_pids: set[int] = frozenset()) -> set[int]:
        return {ls.port for ls in self.listeners if not (ls.pids and set(ls.pids) <= ignore_pids)}


def _split_addr(local: str) -> tuple[str, int] | None:
    addr, _, port = local.rpartition(":")
    if not port.isdigit():
        return None
    return addr.strip("[]").split("%")[0].strip("[]"), int(port)


def parse_facts(text: str) -> NodeFacts:
    f = NodeFacts()
    section = None
    buckets: dict[str, list[str]] = {}
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.startswith("@@"):
            section = line[2:].strip()
            buckets.setdefault(section, [])
            continue
        if section:
            buckets[section].append(line)
            continue
        k, sep, v = line.partition("=")
        if not sep:
            continue
        v = v.strip()
        if k in ("systemd", "apt", "rn_dir"):
            setattr(f, k, v == "1")
        elif k == "ufw":
            f.ufw_active = v == "1"
        elif k in ("mem_mb", "disk_mb"):
            setattr(f, k, int(v) if v.isdigit() else 0)
        elif k == "rn_pids":
            f.rn_pids = {int(x) for x in v.split() if x.isdigit()}
        elif hasattr(f, k):
            setattr(f, k, v)
    marker = "\n".join(buckets.get("marker", [])).strip()
    if marker:
        try:
            f.marker = json.loads(marker)
        except ValueError:
            f.marker = {"unreadable": True}
    for proto in ("tcp", "udp"):
        for line in buckets.get(proto, []):
            parts = line.split()
            if len(parts) < 4:
                continue
            sp = _split_addr(parts[3])
            if not sp:
                continue
            procs = _PROC.findall(line)
            f.listeners.append(
                Listener(
                    proto,
                    sp[0],
                    sp[1],
                    procs[0][0] if procs else "",
                    tuple(int(p) for _, p in procs),
                )
            )
    return f


async def gather(srv: Server) -> NodeFacts:
    r = await srv.run(FACTS_SCRIPT, timeout=90, what="بررسی سرور نود")
    return parse_facts(r.out)


# ======================================================================================
# preparation (read only): everything the admin should see before confirming
# ======================================================================================


def pick_profile(profiles: list[Profile]) -> tuple[Profile | None, str]:
    """(profile, why). Two ways admins work:
    * one profile shared by many nodes -> the one most nodes use;
    * a profile per node (e.g. its own TLS subdomain) -> the admin makes the profile first, so the single
      profile that has no node yet is the one waiting for this server.
    The auto-made Default-Profile never wins a tie. The summary shows the choice; it can be changed."""
    usable = [p for p in profiles if p.inbounds]
    if not usable:
        return None, ""
    waiting = [p for p in usable if not p.node_names and p.name != "Default-Profile"]
    if len(waiting) == 1 and any(p.node_names for p in usable):
        return waiting[0], "تنها پروفایلی که هنوز نودی ندارد"
    best = max(
        usable, key=lambda p: (len(p.node_names), p.name != "Default-Profile", -usable.index(p))
    )
    return best, (
        f"{len(best.node_names)} نود دیگر هم همین را اجرا می‌کنند" if best.node_names else ""
    )


Ports = list[tuple[int, str]]  # (port, "tcp" | "udp") — what a profile's inbounds bind


def port_conflicts(f: NodeFacts, ports: Ports, ignore_pids: set[int]) -> list[str]:
    out = []
    for port, proto in ports:
        who = f.owner(port, proto, ignore_pids)
        if who:
            out.append(f"{port}/{proto} در دست «{who}» است")
    return out


def pick_node_port(f: NodeFacts, ports: Ports, ignore_pids: set[int], ssh_port: int) -> int:
    taken = f.used_ports(ignore_pids) | {ssh_port} | {p for p, _ in ports}
    for p in NODE_PORT_CANDIDATES:
        if p not in taken:
            return p
    raise RemoteError("هیچ پورت آزادی برای نود (2222 تا 2259) پیدا نشد")


def existing_install(f: NodeFacts) -> tuple[str, bool]:
    """(what is there, can it be replaced safely)."""
    if not f.rn_container and not f.rn_dir:
        return "", True
    bits = []
    if f.rn_container:
        state, _, rest = f.rn_container.partition("|")
        status, _, image = rest.partition("|")
        bits.append(f"کانتینر remnanode ({status or state}, {image})")
    if f.rn_dir:
        bits.append("پوشهٔ /opt/remnanode" + (" با فایل compose" if f.rn_compose else ""))
    desc = " و ".join(bits)
    if f.rn_container and f.rn_workdir.rstrip("/") != NODE_DIR:
        where = f.rn_workdir or "بدون docker compose"
        return desc + f" — این کانتینر از /opt/remnanode نیست ({where})", False
    if f.rn_container and not f.rn_compose:
        return desc + " — فایل compose آن در /opt/remnanode نیست", False
    return desc, True


@dataclass
class Prep:
    facts: NodeFacts
    geo: GeoInfo
    address: str
    profiles: list[Profile]
    nodes: list[NodeInfo]
    profile: Profile | None
    node_port: int = 2222
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    existing: str = ""
    ssh_port: int = 22
    profile_why: str = ""  # why this profile was picked (shown to the admin)

    @property
    def usable_profiles(self) -> list[Profile]:
        return [p for p in self.profiles if p.inbounds]

    @property
    def replace(self) -> bool:
        return bool(self.existing)

    @property
    def ignore_pids(self) -> set[int]:
        return self.facts.rn_pids if self.replace else set()

    def choose(self, profile: Profile, why: str = "") -> None:
        self.profile = profile
        self.profile_why = why
        self.conflicts = port_conflicts(self.facts, profile.ports(), self.ignore_pids)
        self.node_port = pick_node_port(
            self.facts, profile.ports(), self.ignore_pids, self.ssh_port
        )

    @property
    def ok(self) -> bool:
        return not self.blockers and not self.conflicts and self.profile is not None


async def prepare(
    panel: OpsPanel,
    http: httpx.AsyncClient,
    srv: Server,
    profiles: list[Profile],
    nodes: list[NodeInfo],
    debug=None,
) -> Prep:
    f, g = await asyncio.gather(
        gather(srv), geo_lookup(http, srv.public_ip or srv.creds.host, debug=debug)
    )
    address = srv.public_ip or srv.creds.host
    prep = Prep(
        facts=f,
        geo=g,
        address=address,
        profiles=profiles,
        nodes=nodes,
        profile=None,
        ssh_port=srv.creds.port,
    )
    b, w = prep.blockers, prep.warnings
    if f.arch not in ("x86_64", "aarch64"):
        b.append(f"معماری {f.arch} است؛ ایمیج نود فقط برای x86_64 و arm64 ساخته می‌شود")
    if not f.has_docker and not (f.apt_based and f.systemd):
        b.append(
            f"Docker نصب نیست و نصب خودکارش فقط روی Ubuntu/Debian با systemd پشتیبانی می‌شود ({f.os_pretty or f.os_id})"
        )
    if f.docker == "broken":
        w.append("Docker نصب است ولی سرویسش جواب نمی‌دهد؛ ربات روشنش می‌کند")
    if f.disk_mb and f.disk_mb < MIN_DISK_MB:
        b.append(f"فضای خالی دیسک فقط {f.disk_mb}MB است؛ دست‌کم {MIN_DISK_MB}MB لازم است")
    elif f.disk_mb and f.disk_mb < LOW_DISK_MB and not f.has_docker:
        w.append(f"فضای خالی دیسک کم است ({f.disk_mb}MB)")
    if f.mem_mb and f.mem_mb < LOW_MEM_MB:
        w.append(f"رم سرور کم است ({f.mem_mb}MB)")
    if f.virt in ("openvz", "lxc", "lxc-libvirt") and not f.has_docker:
        w.append(f"مجازی‌سازی {f.virt} است؛ ممکن است Docker رویش درست کار نکند")
    if not is_public(address):
        w.append(f"آدرس {address} عمومی نیست؛ پنل باید بتواند به آن برسد")
    same = [n for n in nodes if n.address == address]
    if same:
        b.append(f"این آدرس همین حالا در پنل نود «{same[0].name}» است")
    m = f.marker or {}
    if (
        m.get("node_uuid")
        and m.get("panel_host") == panel.host
        and any(n.uuid == m["node_uuid"] for n in nodes)
    ):
        name = next(n.name for n in nodes if n.uuid == m["node_uuid"])
        if not same:
            b.append(f"این سرور همین حالا نود «{name}» در همین پنل است (با این ربات نصب شده)")
    prep.existing, replaceable = existing_install(f)
    if prep.existing and not replaceable:
        b.append(f"روی این سرور از قبل {prep.existing}. اول خودت حذفش کن، بعد دوباره امتحان کن")
    if not prep.usable_profiles:
        b.append("هیچ Config Profileی در پنل اینباند ندارد؛ اول در پنل یکی با اینباند بساز")
    else:
        prep.choose(*pick_profile(profiles))  # type: ignore[arg-type]
    return prep


def name_problem(name: str, names: Iterable[str]) -> str | None:
    """Why the panel would refuse ``name`` for a new node (``names``: the nodes it has)."""
    units = len(name.encode("utf-16-le")) // 2  # the panel counts JavaScript string length
    if units < 3:
        return "نام باید دست‌کم ۳ کاراکتر باشد"
    if units > 30:
        return "نام حداکثر ۳۰ کاراکتر می‌تواند باشد"
    if name in set(names):
        return f"نودی به نام «{name}» در پنل هست"
    return None


def suggest_name(code: str, names: Iterable[str]) -> str:
    """The flag, then the country's name — «🇩🇪 آلمان», then «🇩🇪 آلمان 2» when that is taken
    (the owner's naming, the same as the locations'). «نود 1» when the country is unknown."""
    taken = set(names)
    if known(code):
        base = f"{flag_of(code)} {country_name(code)}"
        if base not in taken:
            return base
        i = 2
    else:
        base, i = "نود", 1
    while f"{base} {i}" in taken:
        i += 1
    return f"{base} {i}"


# ======================================================================================
# install
# ======================================================================================


@dataclass
class NodePlan:
    panel_host: str
    name: str
    address: str
    country: str
    profile_uuid: str
    profile_name: str = ""
    port: int = 2222
    replace: bool = False
    image: str = ""
    backup_dir: str = ""
    node_uuid: str = ""
    ufw_rules: list[str] = field(default_factory=list)
    docker_installed: bool = False
    files_written: bool = False
    created: str = ""
    complete: bool = False

    def marker(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=1)


@dataclass
class NodeResult:
    plan: NodePlan
    node: NodeInfo | None = None
    inbounds_up: dict[int, bool] = field(default_factory=dict)


def compose_yaml(image: str, ulimits: bool = True) -> str:
    out = [
        "# Remnawave node — official compose (made by gozar). SECRET_KEY is in .env (mode 600).",
        "services:",
        "  remnanode:",
        f"    image: {image}",
        "    container_name: remnanode",
        "    hostname: remnanode",
        "    network_mode: host",
        "    restart: always",
        "    cap_add:",
        "      - NET_ADMIN",
    ]
    if ulimits:
        out += ["    ulimits:", "      nofile:", "        soft: 1048576", "        hard: 1048576"]
    out += ["    env_file:", "      - .env", ""]
    return "\n".join(out)


GET_DOCKER = r"""
curl -fsSL --retry 3 --connect-timeout 15 --max-time 180 https://get.docker.com -o /tmp/gozar-get-docker.sh \
  || { echo "@@FETCH_FAILED"; exit 3; }
sh /tmp/gozar-get-docker.sh > /tmp/gozar-get-docker.log 2>&1; rc=$?
rm -f /tmp/gozar-get-docker.sh
tail -n 20 /tmp/gozar-get-docker.log
exit $rc
"""

DOCKER_UP = r"""
systemctl enable --now docker >/dev/null 2>&1 || service docker start >/dev/null 2>&1
for i in $(seq 1 30); do docker info >/dev/null 2>&1 && { docker version --format '{{.Server.Version}}'; exit 0; }; sleep 2; done
docker info 2>&1 | tail -n 5; exit 1
"""

COMPOSE_DETECT = r"""
if docker compose version >/dev/null 2>&1; then echo "docker compose"
elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; fi
"""

COMPOSE_PKG = r"""
for p in docker-compose-plugin docker-compose-v2 docker-compose; do
  apt-cache show "$p" >/dev/null 2>&1 && { echo "$p"; exit 0; }
done
"""


async def _compose_cmd(srv: Server) -> str:
    return (await srv.run(COMPOSE_DETECT, check=False, what="پیدا کردن docker compose")).out.strip()


async def ensure_docker(srv: Server, f: NodeFacts, st) -> tuple[bool, str]:
    """Returns (installed_now, compose command)."""
    installed = False
    if not f.has_docker and f.docker != "broken":
        _, disabled = await apt_update(
            srv, st.note
        )  # get.docker.com dies on a broken third-party repo
        if disabled:
            st.warn("ریپوی خراب غیرفعال شد: " + ", ".join(disabled))
        await ensure_packages(srv, ["curl", "ca-certificates"], st.note)
        await st.note("نصب از get.docker.com …")
        r = await srv.run(GET_DOCKER, timeout=1800, check=False, what="get.docker.com")
        if (
            r.code != 0
            and (await srv.run("command -v docker", check=False, what="docker نصب شد؟")).code == 0
        ):
            st.warn("اسکریپت get.docker.com با خطا تمام شد ولی Docker نصب شد")
        elif r.code != 0:
            why = (
                "دانلود get.docker.com نشد"
                if "@@FETCH_FAILED" in r.out
                else "اسکریپت get.docker.com خطا داد"
            )
            srv.debug(f"{why}; falling back to the distro packages")
            if (
                "@@FETCH_FAILED" not in r.out
            ):  # a half-run script leaves a docker repo that may 403 forever
                await srv.run(
                    "command -v docker >/dev/null 2>&1 || rm -f /etc/apt/sources.list.d/docker.list "
                    "/etc/apt/sources.list.d/docker.sources",
                    check=False,
                    what="پاک کردن ریپوی نیمه‌کارهٔ docker",
                )
            await st.note(f"{why}؛ نصب docker.io از ریپوی خود سیستم‌عامل …")
            await ensure_packages(srv, ["docker.io"], st.note)
            st.warn(f"{why}؛ docker.io از ریپوی سیستم‌عامل نصب شد")
        installed = True
    up = await srv.run(DOCKER_UP, timeout=120, check=False, what="روشن کردن Docker")
    if up.code != 0:
        raise RemoteError(
            f"سرویس Docker روی {srv.label} بالا نیامد (مجازی‌سازی: {f.virt})", up.tail(8)
        )
    compose = await _compose_cmd(srv)
    if not compose:
        if not f.apt_based:
            raise RemoteError(
                "docker compose روی سرور نیست و نصب خودکارش فقط روی Ubuntu/Debian ممکن است"
            )
        pkg = (await srv.run(COMPOSE_PKG, check=False, what="پیدا کردن پکیج compose")).out.strip()
        if not pkg:  # package lists may never have been fetched on a fresh image
            await apt_update(srv, st.note)
            pkg = (
                await srv.run(COMPOSE_PKG, check=False, what="پیدا کردن پکیج compose")
            ).out.strip()
        if not pkg:
            raise RemoteError("پکیج docker compose در ریپوهای سرور پیدا نشد")
        await ensure_packages(srv, [pkg], st.note)
        compose = await _compose_cmd(srv)
        if not compose:
            raise RemoteError(f"{pkg} نصب شد ولی docker compose کار نمی‌کند")
    await st.note(
        f"Docker {up.out.strip().splitlines()[-1] if up.out.strip() else ''} • {compose}"
        + (" (تازه نصب شد)" if installed else " (از قبل بود)")
    )
    return installed, compose


async def pull_image(srv: Server, candidates: list[str], st) -> str:
    errors = []
    for img in candidates:
        await st.note(img)
        r = await srv.run(
            f"docker pull {shlex.quote(img)} 2>&1 | tail -n 6",
            timeout=1800,
            check=False,
            what=f"docker pull {img}",
        )
        if r.code == 0:
            if errors:
                st.warn(f"{candidates[0]} دانلود نشد؛ از {img} گرفته شد")
            return img
        errors.append(f"{img}:\n{r.tail(4)}")
    raise RemoteError("دانلود ایمیج نود نشد (Docker Hub و ghcr.io هر دو)", "\n\n".join(errors))


def _wait_port_script(port: int) -> str:
    return rf"""
st=""
for i in $(seq 1 60); do
  st=$(docker inspect -f '{{{{.State.Status}}}} {{{{.RestartCount}}}}' remnanode 2>/dev/null)
  if ss -Hltn "sport = :{port}" 2>/dev/null | grep . >/dev/null; then echo "@@UP $st"; exit 0; fi
  set -- $st
  case "$1" in exited|dead) break;; esac
  [ "${{2:-0}}" -ge 3 ] && break
  sleep 2
done
echo "@@DOWN $st"; docker logs --tail 30 remnanode 2>&1 | tail -n 30; exit 1
"""


LISTEN_PORTS = "ss -Hltn 2>/dev/null | awk '{print \"tcp\", $4}'; ss -Hlun 2>/dev/null | awk '{print \"udp\", $4}'"


async def listening(srv: Server) -> set[tuple[str, int]]:
    r = await srv.run(LISTEN_PORTS, check=False, what="پورت‌های باز")
    out = set()
    for line in r.out.splitlines():
        proto, _, local = line.partition(" ")
        sp = _split_addr(local.strip())
        if sp:
            out.add((proto, sp[1]))
    return out


async def ufw_allow(srv: Server, rule: str) -> bool:
    """True if WE added the rule (an identical rule the admin had is left alone and not recorded)."""
    if not re.fullmatch(r"\d{1,5}(/(tcp|udp))?", rule):
        raise ValueError(rule)
    r = await srv.run(
        f"if ufw status 2>/dev/null | grep -E '^{rule}[[:space:]]+ALLOW' >/dev/null; then echo HAD; "
        f"else ufw allow {rule} >/dev/null && echo ADDED; fi",
        check=False,
        what=f"ufw allow {rule}",
    )
    return "ADDED" in r.out


async def tcp_probe(host: str, port: int, timeout: float = 6) -> bool:
    try:
        _, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    except (OSError, TimeoutError):
        return False
    w.close()
    try:
        await asyncio.wait_for(w.wait_closed(), 3)
    except Exception:  # noqa: BLE001
        pass
    return True


def _rule(port: int, protos: set[str]) -> str:
    return str(port) if protos >= {"tcp", "udp"} else f"{port}/{next(iter(protos))}"


async def install(
    panel: OpsPanel, srv: Server, plan: NodePlan, rep: Reporter, images: list[str]
) -> NodeResult:
    steps = [("check", "بررسی دوباره سرور و پنل")]
    if plan.replace:
        steps.append(("old", "کنار گذاشتن نود قبلی (با بکاپ)"))
    steps += [
        ("docker", "Docker"),
        ("image", "دانلود ایمیج نود"),
        ("config", "کانفیگ نود (SECRET_KEY از پنل)"),
        ("start", "اجرای نود روی سرور"),
        ("firewall", "فایروال (ufw)"),
        ("panel", "ثبت نود در پنل"),
        ("connect", "وصل شدن پنل به نود"),
        ("inbounds", "بالا آمدن اینباندها روی سرور"),
        ("save", "ذخیره"),
    ]
    await rep.plan(steps, header=f"🖥 افزودن نود «{plan.name}» به پنل")
    rep.context["node_plan"] = plan
    plan.created = time.strftime("%Y-%m-%d %H:%M:%S")
    result = NodeResult(plan)

    # ---------------------------------------------------------------- check (things may have changed)
    async with rep.stage("check") as st:
        f = await gather(srv)
        profiles, nodes = await asyncio.gather(panel.profiles(), panel.nodes())
        profile = next((p for p in profiles if p.uuid == plan.profile_uuid), None)
        if profile is None or not profile.inbounds:
            raise RemoteError(f"پروفایل «{plan.profile_name}» دیگر در پنل نیست یا اینباند ندارد")
        problem = name_problem(plan.name, [n.name for n in nodes])
        if problem:
            raise RemoteError(problem)
        if any(n.address == plan.address for n in nodes):
            raise RemoteError(f"آدرس {plan.address} همین حالا در پنل ثبت است")
        desc, replaceable = existing_install(f)
        if desc and not plan.replace:
            raise RemoteError(f"روی سرور تازه {desc} پیدا شد؛ از اول شروع کن")
        if desc and not replaceable:
            raise RemoteError(f"روی سرور {desc}")
        ignore = f.rn_pids if plan.replace else set()
        bad = port_conflicts(f, profile.ports(), ignore)
        if f.owner(plan.port, "tcp", ignore):
            bad.append(
                f"{plan.port}/tcp (پورت نود) در دست «{f.owner(plan.port, 'tcp', ignore)}» است"
            )
        if bad:
            raise RemoteError("پورت‌های لازم روی سرور آزاد نیستند: " + "، ".join(bad))
        await st.note(
            f"🐧 {f.os_pretty} • {f.arch} • Docker: {f.docker if f.has_docker else 'نصب نیست'}"
        )

    # ---------------------------------------------------------------- old install aside
    if plan.replace:
        async with rep.stage("old") as st:
            backup = f"{NODE_DIR}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
            down = ""
            if f.rn_compose:
                compose = await _compose_cmd(srv) or "docker compose"
                down = f"cd {NODE_DIR} && {compose} -f {shlex.quote(f.rn_compose)} down 2>&1 | tail -n 5\n"
            r = await srv.run(
                down + "cd /\n"
                "if docker ps -a --filter 'name=^/remnanode$' --format '{{.Names}}' 2>/dev/null | grep -x remnanode >/dev/null; then\n"
                "  docker start remnanode >/dev/null 2>&1; echo '@@STILL'; exit 0\nfi\n"
                f"if [ -e {NODE_DIR} ]; then mv {NODE_DIR} {backup} && echo '@@MOVED'; else echo '@@NODIR'; fi",
                timeout=300,
                check=False,
                what="متوقف کردن نود قبلی",
            )
            if "@@STILL" in r.out:
                raise RemoteError("کانتینر remnanode قبلی متوقف نشد؛ چیزی عوض نشد", r.tail(8))
            if "@@MOVED" in r.out:
                plan.backup_dir = backup
            elif "@@NODIR" not in r.out:
                raise RemoteError(f"جابه‌جا کردن {NODE_DIR} نشد", r.tail(8))
            f = await gather(srv)
            bad = port_conflicts(f, profile.ports(), set())
            if bad:
                raise RemoteError(
                    "بعد از متوقف کردن نود قبلی هم این پورت‌ها آزاد نشدند: " + "، ".join(bad)
                )
            await st.note(
                f"بکاپ: {plan.backup_dir}" if plan.backup_dir else "نود قبلی دیگر آن‌جا نبود"
            )

    # ---------------------------------------------------------------- docker
    async with rep.stage("docker") as st:
        plan.docker_installed, compose = await ensure_docker(srv, f, st)

    # ---------------------------------------------------------------- image
    async with rep.stage("image") as st:
        plan.image = await pull_image(srv, images, st)
        await st.note(plan.image)

    # ---------------------------------------------------------------- config
    async with rep.stage("config") as st:
        secret = await panel.keygen()
        srv.add_secret(secret)
        plan.files_written = True  # from here on undo removes /opt/remnanode (it is ours now)
        await srv.write_file(MARKER, plan.marker(), 0o600, what="ذخیرهٔ وضعیت")
        await srv.write_file(
            f"{NODE_DIR}/.env",
            f"NODE_PORT={plan.port}\nSECRET_KEY={secret}\n",
            0o600,
            what="نوشتن .env (SECRET_KEY)",
        )
        await srv.write_file(
            f"{NODE_DIR}/docker-compose.yml",
            compose_yaml(plan.image),
            0o644,
            what="نوشتن docker-compose.yml",
        )
        await st.note(f"{NODE_DIR} • NODE_PORT={plan.port}")

    # ---------------------------------------------------------------- start
    async with rep.stage("start") as st:
        up_cmd = f"cd {NODE_DIR} && {compose} up -d 2>&1 | tail -n 15"
        r = await srv.run(up_cmd, timeout=600, check=False, what="docker compose up -d")
        if r.code != 0 and re.search(r"rlimit|ulimit|RLIMIT_NOFILE", r.out + r.err):
            await srv.write_file(
                f"{NODE_DIR}/docker-compose.yml",
                compose_yaml(plan.image, ulimits=False),
                0o644,
                what="docker-compose.yml بدون ulimits",
            )
            r = await srv.run(
                up_cmd, timeout=600, check=False, what="docker compose up -d (بدون ulimits)"
            )
            if r.code == 0:
                st.warn(
                    f"این سرور اجازهٔ nofile=1048576 نداد (مجازی‌سازی {f.virt})؛ بدون ulimits اجرا شد"
                )
        if r.code != 0:
            raise RemoteError("docker compose up نشد", r.tail(12))
        w = await srv.run(
            _wait_port_script(plan.port), timeout=240, check=False, what=f"منتظر پورت {plan.port}"
        )
        if w.code != 0:
            raise RemoteError(f"remnanode بالا آمد ولی روی پورت {plan.port} گوش نمی‌دهد", w.tail(15))
        await st.note(f"remnanode روی پورت {plan.port}/tcp منتظر پنل است")

    # ---------------------------------------------------------------- firewall
    if not f.ufw_active:
        await rep.skip("firewall", "ufw خاموش است")
    else:
        async with rep.stage("firewall") as st:
            wanted = [f"{plan.port}/tcp"]
            for port, protos in _inbound_protos(profile).items():
                wanted.append(_rule(port, protos))
            for rule in wanted:
                if await ufw_allow(srv, rule):
                    plan.ufw_rules.append(rule)
            await srv.write_file(MARKER, plan.marker(), 0o600, what="ذخیرهٔ وضعیت")
            await st.note(
                "اضافه شد: " + (", ".join(plan.ufw_rules) or "هیچ (همه از قبل باز بودند)")
            )

    # ---------------------------------------------------------------- panel
    async with rep.stage("panel") as st:
        node = await panel.create_node(
            name=plan.name,
            address=plan.address,
            port=plan.port,
            country=plan.country,
            profile=profile,
        )
        plan.node_uuid = node.uuid
        await srv.write_file(MARKER, plan.marker(), 0o600, what="ذخیرهٔ وضعیت")
        await st.note(
            f"{plan.address}:{plan.port} • {plan.country} • پروفایل {profile.name} "
            f"({len(profile.inbounds)} اینباند)"
        )

    # ---------------------------------------------------------------- connect
    async with rep.stage("connect") as st:
        t0 = time.monotonic()
        last = None
        while time.monotonic() - t0 < CONNECT_TIMEOUT:
            try:
                node = await panel.node(plan.node_uuid)
            except PanelError as e:
                if e.code != "network":
                    raise
                await asyncio.sleep(3)
                continue
            if node.is_connected:
                break
            if node.last_status and node.last_status != last:
                last = node.last_status
                await st.note(last[:120])
            await asyncio.sleep(3)
        result.node = node
        if not node.is_connected:
            reach = await tcp_probe(plan.address, plan.port)
            hint = (
                f"از سرور ربات پورت {plan.port} نود باز بود؛ پس احتمالاً پنل از سرور خودش به {plan.address}:{plan.port} نمی‌رسد"
                if reach
                else f"از سرور ربات هم پورت {plan.port} نود بسته است؛ فایروال دیتاسنتر و سرور را بررسی کن"
            )
            raise RemoteError(
                f"پنل بعد از {CONNECT_TIMEOUT} ثانیه به نود وصل نشد — {hint}",
                f"lastStatusMessage: {node.last_status or '-'}",
            )
        await st.note(f"وصل شد • Xray {node.xray_version or '?'} • نود {node.node_version or '?'}")

    # ---------------------------------------------------------------- inbounds bound by Xray
    async with rep.stage("inbounds") as st:
        want = {(proto, port) for port, proto in profile.ports()}
        t0 = time.monotonic()
        have: set = set()
        while time.monotonic() - t0 < INBOUND_TIMEOUT:
            have = await listening(srv)
            if want <= have:
                break
            await asyncio.sleep(3)
        for port, proto in profile.ports():
            result.inbounds_up[port] = result.inbounds_up.get(port, True) and (proto, port) in have
        missing = sorted(p for p, ok in result.inbounds_up.items() if not ok)
        tags = {ib.port: ib.tag for ib in profile.inbounds if ib.port}
        if missing:
            st.warn(
                "بالا نیامدند: "
                + "، ".join(f"{tags.get(p, '?')} ({p})" for p in missing)
                + " — لاگ: docker logs remnanode"
            )
        await st.note(
            " • ".join(f"{tags.get(p, '?')} {p} ✓" for p, ok in result.inbounds_up.items() if ok)
            or "هیچ اینباندی بالا نیامد"
        )

    async with rep.stage("save"):
        plan.complete = True
        await srv.write_file(MARKER, plan.marker(), 0o600, what="ذخیرهٔ وضعیت")
    return result


def _inbound_protos(profile: Profile) -> dict[int, set[str]]:
    out: dict[int, set[str]] = {}
    for port, proto in profile.ports():
        out.setdefault(port, set()).add(proto)
    return out


# ======================================================================================
# undo (after a failure, or when the admin wants it gone)
# ======================================================================================

REMOVE_OURS = r"""
M=/opt/remnanode/.gozar.json
[ -f "$M" ] || { echo "@@NOMARKER"; exit 0; }
grep -F "\"created\": \"$CREATED\"" "$M" >/dev/null || { echo "@@OTHER"; exit 0; }
cd /opt/remnanode && { docker compose down 2>&1 || docker-compose down 2>&1; } | tail -n 5
docker rm -f remnanode >/dev/null 2>&1
cd / && rm -rf /opt/remnanode && echo "@@REMOVED"
"""


UNREACHABLE = "سرور در دسترس نیست"


async def undo(
    panel: OpsPanel | None, srv: Server | None, plan: NodePlan, rep: Reporter
) -> list[str]:
    """Reverse whatever `install` got done. Every step runs even if an earlier one failed.
    Returns what could NOT be undone (shown to the admin). ``srv`` None: the server can't be
    reached — the panel side is still undone and the server's part is named as left."""
    steps = [("panel", "حذف نود از پنل"), ("server", "حذف remnanode از سرور")]
    if plan.backup_dir:
        steps.append(("restore", "برگرداندن نود قبلی"))
    steps.append(("firewall", "حذف قوانین ufw"))
    await rep.plan(steps, header=f"🧹 برگرداندن نصب نود «{plan.name}»")
    left: list[str] = []

    async with rep.stage("panel") as st:
        if not plan.node_uuid:
            await st.note("ثبت نشده بود")
        elif panel is None:
            left.append(f"نود «{plan.name}» در پنل")
            st.warn("پنل در دسترس نیست؛ دستی حذفش کن")
        else:
            try:
                await panel.delete_node(plan.node_uuid)
                plan.node_uuid = ""
                await st.note("حذف شد")
            except RemoteError as e:
                left.append(f"نود «{plan.name}» در پنل")
                st.warn(e.message)

    async with rep.stage("server") as st:
        if not plan.files_written:
            await st.note("چیزی نصب نشده بود")
        elif srv is None:
            left.append(f"{NODE_DIR} روی سرور")
            st.warn(UNREACHABLE)
        else:
            try:
                r = await srv.run(
                    f"CREATED={shlex.quote(plan.created)}\n" + REMOVE_OURS,
                    timeout=300,
                    check=False,
                    what="حذف /opt/remnanode",
                )
                if "@@REMOVED" in r.out or "@@NOMARKER" in r.out:
                    plan.files_written = False
                    await st.note(
                        "کانتینر و /opt/remnanode پاک شدند" if "@@REMOVED" in r.out else "نبود"
                    )
                elif "@@OTHER" in r.out:
                    st.warn("/opt/remnanode از نصب دیگری است؛ دست نخورد")
                else:
                    left.append(f"{NODE_DIR} روی سرور")
                    st.warn("حذف /opt/remnanode نشد: " + r.tail(3))
            except RemoteError as e:
                left.append(f"{NODE_DIR} روی سرور")
                st.warn(e.message)

    if plan.backup_dir:
        async with rep.stage("restore") as st:
            b = shlex.quote(plan.backup_dir)
            try:
                if srv is None:
                    raise RemoteError(UNREACHABLE)
                r = await srv.run(
                    f"[ -d {b} ] || {{ echo '@@NOBACKUP'; exit 0; }}\n"
                    f"[ -e {NODE_DIR} ] && {{ echo '@@BUSY'; exit 0; }}\n"
                    f"mv {b} {NODE_DIR} && cd {NODE_DIR} && "
                    "f=$(ls -1 docker-compose.yml docker-compose.yaml compose.yml compose.yaml 2>/dev/null | head -n 1); "
                    'if [ -n "$f" ]; then { docker compose -f "$f" up -d 2>&1 || docker-compose -f "$f" up -d 2>&1; } '
                    "| tail -n 5; fi; echo '@@RESTORED'",
                    timeout=600,
                    check=False,
                    what="برگرداندن نود قبلی",
                )
            except RemoteError as e:
                r = None
                st.warn(e.message)
            if r is not None and "@@RESTORED" in r.out:
                await st.note(f"{plan.backup_dir} → {NODE_DIR} و دوباره روشن شد")
                plan.backup_dir = ""
            elif r is not None and "@@NOBACKUP" in r.out:
                st.warn(f"بکاپ {plan.backup_dir} پیدا نشد")
            else:
                left.append(f"بکاپ نود قبلی: {plan.backup_dir}")
                st.warn(f"برنگشت؛ بکاپ دست نخورده: {plan.backup_dir}")

    async with rep.stage("firewall") as st:
        done = []
        for rule in list(plan.ufw_rules):
            try:
                if srv is None:
                    raise RemoteError(UNREACHABLE)
                await srv.run(
                    f"ufw delete allow {rule} >/dev/null 2>&1 || true",
                    check=False,
                    what=f"ufw delete {rule}",
                )
                plan.ufw_rules.remove(rule)
                done.append(rule)
            except RemoteError as e:
                left.append(f"قانون ufw {rule}")
                st.warn(e.message)
        await st.note(", ".join(done) if done else "قانونی اضافه نشده بود")
    return left
