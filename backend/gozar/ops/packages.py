"""Installing packages with apt, surviving the things that broke during manual setup:
broken third-party repos (404 / unsigned), dpkg locks held by unattended-upgrades,
and never pulling in iptables-persistent (which removes ufw)."""

from __future__ import annotations

import re
import shlex

from gozar.ops.errors import RemoteError
from gozar.ops.ssh import Server

OFFICIAL_HOSTS = (
    "archive.ubuntu.com",
    "security.ubuntu.com",
    "ports.ubuntu.com",
    "deb.debian.org",
    "security.debian.org",
    "mirrors.",
    "mirror.",
)

APT_UPDATE = r"""
for i in $(seq 1 60); do
  out=$(apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=20 update 2>&1); rc=$?
  case "$out" in *"Could not get lock"*|*"Unable to lock"*) sleep 10; continue ;; esac
  break
done
echo "$out"; exit $rc
"""

_BAD_REPO = [
    re.compile(r"The repository '(\S+)\s[^']*' does not have a Release file"),
    re.compile(r"The repository '(\S+)\s[^']*' is not signed"),
    re.compile(r"The repository '(\S+)\s[^']*' no longer has a Release file"),
]


_FAILED_FETCH = re.compile(r"Failed to fetch (\S+?)/dists/\S+\s+(?:40[0-9]|410)\b")


def parse_bad_repos(output: str) -> list[str]:
    urls: list[str] = []
    found = [m.group(1) for rx in _BAD_REPO for m in rx.finditer(output)]
    found += [m.group(1) for m in _FAILED_FETCH.finditer(output)]
    for url in found:
        url = url.rstrip("/")
        if url not in urls:
            urls.append(url)
    return urls


async def missing_packages(srv: Server, pkgs: list[str]) -> list[str]:
    script = (
        "for p in " + " ".join(shlex.quote(p) for p in pkgs) + "; do "
        'st=$(dpkg-query -W -f=\'${Status}\' "$p" 2>/dev/null); [ "$st" = \'install ok installed\' ] || echo "$p"; done'
    )
    r = await srv.run(script, what="چک پکیج‌ها")
    return r.out.split()


_SAFE_URL = re.compile(r"^https?://[A-Za-z0-9._~:/%+@=-]+$")
_MAIN_FILES = re.compile(r"/(ubuntu|debian)\.sources$")


def file_uris(text: str) -> set[str]:
    """Every repository URI in a .list or deb822 .sources file."""
    uris: set[str] = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith(("deb ", "deb-src ")):
            toks = line.split()[1:]
            if toks and toks[0].startswith("["):
                while toks and not toks[0].endswith("]"):
                    toks = toks[1:]
                toks = toks[1:]
            if toks:
                uris.add(toks[0].rstrip("/"))
        elif line.lower().startswith("uris:"):
            uris.update(u.rstrip("/") for u in line.split(":", 1)[1].split())
    return uris


async def disable_repos(srv: Server, urls: list[str]) -> list[str]:
    """Rename third-party files in sources.list.d whose repositories are ALL broken.
    Never touches /etc/apt/sources.list or the distro's ubuntu/debian.sources, and never a file
    that still has a working repository in it (that could take the main mirror away)."""
    bad = {u for u in urls if _SAFE_URL.match(u) and not any(h in u for h in OFFICIAL_HOSTS)}
    if not bad:
        return []
    r = await srv.run(
        "ls -1 /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources 2>/dev/null || true",
        what="فهرست ریپوها",
    )
    disabled: list[str] = []
    for path in r.out.split():
        if _MAIN_FILES.search(path) or not re.fullmatch(
            r"/etc/apt/sources\.list\.d/[A-Za-z0-9._-]+", path
        ):
            continue
        text = await srv.read_file(path) or ""
        uris = file_uris(text)
        if uris and uris <= bad:
            await srv.run(
                f"mv -f {shlex.quote(path)} {shlex.quote(path)}.disabled-by-gozar",
                what=f"غیرفعال کردن {path}",
            )
            disabled.append(path.rsplit("/", 1)[-1])
    return disabled


async def apt_update(srv: Server, on_note=None):
    """apt-get update; a third-party repo that is broken for good (404 / unsigned) gets its file in
    sources.list.d disabled and the update is retried. Returns (result, disabled_repo_files)."""
    if on_note:
        await on_note(f"{srv.label}: apt update")
    disabled: list[str] = []
    upd = await srv.run(APT_UPDATE, timeout=900, check=False, what="apt-get update")
    if upd.code != 0:
        bad = parse_bad_repos(upd.out + upd.err)
        if bad:
            disabled = await disable_repos(srv, bad)
            upd = await srv.run(
                APT_UPDATE, timeout=900, check=False, what="apt-get update (دوباره)"
            )
    return upd, disabled


async def ensure_packages(
    srv: Server, pkgs: list[str], on_note=None
) -> tuple[list[str], list[str]]:
    """Install whatever is missing. Returns (installed, disabled_repo_files)."""
    missing = await missing_packages(srv, pkgs)
    if not missing:
        return [], []
    upd, disabled = await apt_update(srv, on_note)
    if on_note:
        await on_note(f"{srv.label}: نصب {' '.join(missing)}")
    inst = await srv.run(
        "apt-get install -y --no-install-recommends -o DPkg::Lock::Timeout=900 "
        "-o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold "
        + " ".join(shlex.quote(p) for p in missing)
        + " 2>&1",
        timeout=1800,
        check=False,
        what="apt-get install",
    )
    if inst.code != 0:
        hint = "" if upd.code == 0 else "\napt update هم خطا داده بود:\n" + upd.tail(6)
        raise RemoteError(f"نصب {' '.join(missing)} روی {srv.label} نشد", inst.tail(12) + hint)
    still = await missing_packages(srv, missing)
    if still:
        raise RemoteError(f"بعد از نصب هم {' '.join(still)} روی {srv.label} نیست", inst.tail(12))
    return missing, disabled
