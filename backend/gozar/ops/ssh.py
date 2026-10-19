"""SSH access to one server: a password or a private key, as root or through sudo.

Every remote script is fed to ``bash -s`` on stdin, so nothing (passwords, keys) ever appears in a
remote command line or in ``ps``.

Host keys are pinned (trust on first use): the caller passes the key the server showed last time
(``pinned``); a server that now shows a different one is refused BEFORE any password is sent. After
the first successful login ``host_key`` is the key to remember. Where it is kept is the caller's
business (the console keeps it on the saved server's row).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import secrets
import shlex
from collections.abc import Callable
from dataclasses import dataclass

import asyncssh

from gozar.ops.errors import RemoteError

logger = logging.getLogger("gozar.ops.ssh")

PRELUDE = (
    "set -o pipefail\n"
    "export LC_ALL=C DEBIAN_FRONTEND=noninteractive "
    "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n"
)

__all__ = ["PRELUDE", "RemoteError", "Result", "SSHCreds", "Server"]

#: The host key a first login asks for, best first: the key that gets pinned.
HOST_KEY_ALGS = (
    "ssh-ed25519",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "rsa-sha2-512",
    "rsa-sha2-256",
    "ssh-rsa",
)


def host_key_algs(pinned: str | None) -> list[str]:
    """What to ask the server for: the pinned key's own type, so a server offering several keys
    is always compared on the same one (a negotiation that picked another type would read as a
    changed key); every type, best first, when nothing is pinned yet."""
    kind = pinned.split()[0] if pinned and pinned.split() else ""
    if kind == "ssh-rsa":
        return ["rsa-sha2-512", "rsa-sha2-256", "ssh-rsa"]
    if kind in HOST_KEY_ALGS:
        return [kind]
    return list(HOST_KEY_ALGS)


@dataclass
class SSHCreds:
    host: str
    port: int = 22
    username: str = "root"
    password: str | None = None
    private_key: str | None = None
    passphrase: str | None = None
    sudo_password: str | None = None  # a non-root user whose sudo asks a password (login is by key)

    def wipe(self) -> None:
        self.password = None
        self.private_key = None
        self.passphrase = None
        self.sudo_password = None

    def __repr__(self) -> str:  # never a secret in a log line or a traceback
        return f"SSHCreds({self.username}@{self.host}:{self.port})"


@dataclass
class Result:
    code: int
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.code == 0

    def tail(self, n: int = 15) -> str:
        text = (self.out.rstrip() + "\n" + self.err.rstrip()).strip()
        return "\n".join(text.splitlines()[-n:])


class Server:
    """One SSH-reachable server."""

    def __init__(
        self,
        creds: SSHCreds,
        label: str,
        *,
        pinned: str | None = None,
        debug: Callable[[str], None] | None = None,
    ) -> None:
        self.creds = creds
        self.label = label  # user-facing name, e.g. "DE-1"
        self.pinned = pinned  # the host key seen last time (OpenSSH public key text), if any
        self.host_key: str | None = None  # what the server showed this time
        self.first_seen = False  # no key was pinned before this login
        self.conn: asyncssh.SSHClientConnection | None = None
        self.sudo_mode: str | None = None  # None = root, "nopasswd", "password"
        self.public_ip: str | None = None  # the address we reached it on
        self.fingerprint: str | None = None
        self._debug = debug or (lambda _line: None)
        self._secrets: list[str] = []

    # ---- secrets never reach the debug log -----------------------------------------------------
    def add_secret(self, value: str | None) -> None:
        if value and len(value) >= 4:
            self._secrets.append(value)

    def redact(self, text: str) -> str:
        for s in self._secrets:
            text = text.replace(s, "***")
        return text

    def debug(self, line: str) -> None:
        self._debug(f"[{self.label}] {self.redact(line)}")

    # ---- connection ----------------------------------------------------------------------------
    @property
    def sudo_secret(self) -> str | None:
        """The password sudo takes (only when sudo_mode == "password")."""
        return self.creds.sudo_password or self.creds.password

    async def connect(self, timeout: int = 25) -> None:
        c = self.creds
        self.add_secret(c.password)
        self.add_secret(c.passphrase)
        self.add_secret(c.sudo_password)
        algs = host_key_algs(self.pinned)
        try:
            key = await asyncio.wait_for(
                asyncssh.get_server_host_key(c.host, c.port, server_host_key_algs=algs), timeout
            )
        except TimeoutError as e:
            raise RemoteError(
                f"به {c.host}:{c.port} وصل نشد (timeout). آی‌پی، پورت یا فایروال را بررسی کن",
                code="network",
            ) from e
        except (OSError, asyncssh.Error) as e:
            raise RemoteError(f"به {c.host}:{c.port} وصل نشد: {e}", code="network") from e
        if key is None:
            raise RemoteError(f"سرور {c.host}:{c.port} کلید SSH نشان نداد", code="network")
        shown = key.export_public_key().decode().strip()
        self.fingerprint = key.get_fingerprint("sha256")
        if self.pinned and self.pinned != shown:
            old = asyncssh.import_public_key(self.pinned).get_fingerprint("sha256")
            raise RemoteError(
                "⚠️ اثر انگشت SSH این سرور با دفعهٔ قبل فرق دارد؛ رمز فرستاده نشد",
                f"قبلی: {old}\nاکنون: {self.fingerprint}",
                code="hostkey",
            )
        self.first_seen = not self.pinned
        kw: dict = {
            "host": c.host,
            "port": c.port,
            "username": c.username,
            "known_hosts": ([key], [], []),  # accept exactly the key just checked
            "server_host_key_algs": algs,
            "agent_path": None,
            "config": None,
            "connect_timeout": timeout,
            "keepalive_interval": 20,
            "keepalive_count_max": 3,
        }
        if c.private_key:
            try:
                kw["client_keys"] = [asyncssh.import_private_key(c.private_key, c.passphrase)]
            except (asyncssh.KeyImportError, ValueError) as e:
                raise RemoteError(f"کلید خصوصی خوانده نشد: {e}", code="key") from e
            if c.password:
                kw["password"] = c.password
        else:
            kw["client_keys"] = ()
            kw["password"] = c.password
        try:
            self.conn = await asyncio.wait_for(asyncssh.connect(**kw), timeout + 5)
        except asyncssh.PermissionDenied as e:
            raise RemoteError(
                "ورود رد شد: نام کاربری یا رمز یا کلید اشتباه است", code="auth"
            ) from e
        except asyncssh.HostKeyNotVerifiable as e:
            raise RemoteError(
                "⚠️ کلید SSH سرور وسط اتصال عوض شد؛ رمز فرستاده نشد", str(e), code="hostkey"
            ) from e
        except TimeoutError as e:
            raise RemoteError(
                f"به {c.host}:{c.port} وصل نشد (timeout). آی‌پی، پورت یا فایروال را بررسی کن",
                code="network",
            ) from e
        except (OSError, asyncssh.Error) as e:
            raise RemoteError(f"به {c.host}:{c.port} وصل نشد: {e}", code="network") from e

        self.host_key = shown
        peer = self.conn.get_extra_info("peername")
        self.public_ip = peer[0] if peer else c.host

        who = await self._raw("id -u")
        if who.out.strip() == "0":
            self.sudo_mode = None
        elif (await self._raw("sudo -n true")).code == 0:
            self.sudo_mode = "nopasswd"
        elif (
            self.sudo_secret
            and (await self._raw("sudo -k -S -p '' true", input=self.sudo_secret + "\n")).code == 0
        ):
            self.sudo_mode = "password"
        else:
            await self.close()
            if c.sudo_password or c.password:
                raise RemoteError(
                    "این کاربر root نیست و دسترسی sudo هم ندارد. با root وارد شو", code="sudo"
                )
            raise RemoteError(f"کاربر {c.username} برای sudo رمز می‌خواهد", code="sudo")

    async def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            try:
                await asyncio.wait_for(self.conn.wait_closed(), 5)
            except Exception:  # noqa: BLE001 — closing is best effort
                pass
            self.conn = None

    async def __aenter__(self) -> Server:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
        self.creds.wipe()

    # ---- running things ------------------------------------------------------------------------
    async def _raw(self, command: str, input: str | None = None, timeout: int = 60) -> Result:  # noqa: A002
        assert self.conn is not None, "not connected"
        r = await self.conn.run(command, input=input, check=False, timeout=timeout)
        code = r.exit_status if r.exit_status is not None else -1
        return Result(code, str(r.stdout or ""), str(r.stderr or ""))

    async def run(
        self,
        script: str,
        *,
        timeout: int = 120,
        check: bool = True,
        what: str | None = None,
        secret_output: bool = False,
    ) -> Result:
        """Run a bash script as root (directly or through sudo). ``secret_output``: the output (a
        key, say) stays out of the debug log."""
        body = PRELUDE + script
        if self.sudo_mode is None:
            cmd, stdin = "bash -s", body
        elif self.sudo_mode == "nopasswd":
            cmd, stdin = "sudo -n bash -s", body
        else:  # -k: always ask, so the password line is always consumed by sudo
            cmd, stdin = "sudo -k -S -p '' bash -s", (self.sudo_secret or "") + "\n" + body
        short = script.strip().splitlines()[0][:120] if script.strip() else ""
        self.debug(f"$ {what or short}")
        try:
            r = await self._raw(cmd, input=stdin, timeout=timeout)
        except asyncssh.TimeoutError as e:
            raise RemoteError(
                f"«{what or short}» روی {self.label} بیشتر از {timeout} ثانیه طول کشید"
            ) from e
        except (asyncssh.Error, OSError) as e:
            raise RemoteError(f"ارتباط SSH با {self.label} قطع شد: {e}") from e
        if secret_output:
            self.debug(f"  -> rc={r.code} (output not logged)")
        elif r.out.strip() or r.err.strip():
            self.debug(f"  -> rc={r.code}\n{self.redact(r.tail(25))}")
        else:
            self.debug(f"  -> rc={r.code}")
        if check and r.code != 0:
            raise RemoteError(
                f"«{what or short}» روی {self.label} خطا داد (کد {r.code})",
                "" if secret_output else self.redact(r.tail()),
            )
        return r

    async def run_user(self, script: str, *, timeout: int = 60, what: str | None = None) -> Result:
        """Run a bash script as the login user itself (no sudo): for things in the user's own
        home, like ``~/.ssh/authorized_keys``."""
        first = script.strip().splitlines()[0][:120] if script.strip() else ""
        self.debug(f"$ (as {self.creds.username}) {what or first}")
        try:
            r = await self._raw("bash -s", input=PRELUDE + script, timeout=timeout)
        except asyncssh.TimeoutError as e:
            raise RemoteError(f"«{what}» روی {self.label} بیشتر از {timeout} ثانیه طول کشید") from e
        except (asyncssh.Error, OSError) as e:
            raise RemoteError(f"ارتباط SSH با {self.label} قطع شد: {e}") from e
        tail = f"\n{self.redact(r.tail(10))}" if (r.out.strip() or r.err.strip()) else ""
        self.debug(f"  -> rc={r.code}{tail}")
        return r

    @property
    def alive(self) -> bool:
        return self.conn is not None and not self.conn.is_closed()

    async def write_file(
        self, path: str, data: bytes | str, mode: int = 0o644, what: str | None = None
    ) -> None:
        """Write a file as root. Raw bytes go over the SSH channel into a private temp file (as
        the login user), then get installed in place as root."""
        raw = data.encode() if isinstance(data, str) else data
        tmp = f"/tmp/.gozar-{secrets.token_hex(6)}"
        self.debug(f"$ upload {len(raw)} bytes -> {path} ({what or ''})")
        assert self.conn is not None, "not connected"
        try:
            r = await self.conn.run(
                f"umask 077; cat > {tmp}", input=raw, encoding=None, check=False, timeout=600
            )
        except (asyncssh.Error, OSError) as e:
            raise RemoteError(f"ارتباط SSH با {self.label} وسط آپلود قطع شد: {e}") from e
        if r.exit_status != 0:
            err = (
                r.stderr.decode(errors="replace") if isinstance(r.stderr, bytes) else str(r.stderr)
            )
            raise RemoteError(f"آپلود {path} روی {self.label} نشد", err[-500:])
        q = shlex.quote(path)
        # sync: a state file written ~30 s before a power cut came back 0 bytes (tunnelbot's lab)
        await self.run(
            f"install -D -m {mode:o} {tmp} {q}; rc=$?; rm -f {tmp}; sync; exit $rc",
            timeout=120,
            what=what or f"نوشتن {path}",
        )

    async def read_file(self, path: str) -> str | None:
        r = await self.run(
            f"cat {shlex.quote(path)} 2>/dev/null", check=False, what=f"خواندن {path}"
        )
        return r.out if r.code == 0 else None

    async def sha256(self, path: str) -> str | None:
        r = await self.run(
            f"sha256sum {shlex.quote(path)} 2>/dev/null | cut -d' ' -f1", check=False, what="sha256"
        )
        h = r.out.strip()
        return h if re.fullmatch(r"[0-9a-f]{64}", h) else None

    async def upload_binary(self, path: str, data: bytes, mode: int = 0o755) -> bool:
        """Upload unless an identical file is already there. Returns True if uploaded."""
        want = hashlib.sha256(data).hexdigest()
        if await self.sha256(path) == want:
            return False
        await self.write_file(path, data, mode, what=f"آپلود {path}")
        if await self.sha256(path) != want:
            raise RemoteError(f"فایل {path} روی {self.label} ناقص آپلود شد (sha256 جور نیست)")
        return True
