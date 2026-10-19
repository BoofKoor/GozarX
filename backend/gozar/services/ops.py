"""The console's operations: logging into servers, the bot's own SSH key, and handing jobs to the
worker.

**Passwords are never kept.** A server's first login takes its password once: the bot then appends
its OWN ed25519 public key to that user's ``authorized_keys``, checks that a FRESH login with only
that key works (``key_ok``), and saves the server with its host key pinned. Every later login is by
key. The password reaches the worker through a short-lived, read-once Redis entry sealed with
VAULT_KEY (``hand_over`` / ``take_over``) — never the job row, never FSM data, never a log line —
and is wiped when the login is done. The one secret a server row may hold is the sudo password of a
non-root user whose sudo asks for one, sealed.

A job (``ops_jobs``) is written here at enqueue time; the worker (``worker/ops``) runs it.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import asyncssh
import httpx
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from gozar import vault
from gozar.db.models.ops import OpsJob, OpsJobStatus, OpsServer
from gozar.db.repositories.ops import OpsJobRepository, OpsKeyRepository, OpsServerRepository
from gozar.ops import access
from gozar.ops.errors import RemoteError
from gozar.ops.geo import lookup as geo_lookup
from gozar.ops.ssh import Server, SSHCreds

logger = logging.getLogger("gozar.services.ops")

BOT_KEY = "ssh_bot"
#: How long a password handed to the worker waits to be picked up.
SECRET_TTL = 600
#: The arq function every operation job runs through, and how long one may take.
JOB_FUNCTION = "ops_run"
JOB_TIMEOUT = 45 * 60


class JobKind:
    """What an ``ops_jobs`` row asks the worker to do (``services/ops_jobs`` does it)."""

    node_prepare = "node_prepare"  # log in, read the server and the panel → a NodeDraft
    node_install = "node_install"  # the confirmed draft → a node in the panel
    node_undo = "node_undo"  # reverse what an install got done
    server_add = "server_add"  # log in once with a password, install the bot's key, save it
    server_test = "server_test"  # log in with the bot's key, read the server
    server_forget = "server_forget"  # take the bot's key off the server, forget it
    panel_check = "panel_check"  # what the panel token may do


_HOST_RX = re.compile(
    r"^(?=.{1,253}$)([A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)
_USER_RX = re.compile(r"^[a-z_][a-z0-9_.-]{0,31}$", re.I)


def fingerprint(host_key: str | None) -> str:
    """``SHA256:…`` of a pinned host key (what ``ssh`` prints on a first login), '' if none."""
    if not host_key:
        return ""
    try:
        return asyncssh.import_public_key(host_key).get_fingerprint("sha256")
    except (asyncssh.KeyImportError, ValueError):
        return ""


def _secret_key(job_id: str) -> str:
    return f"ops:secret:{job_id}"


@dataclass(frozen=True, slots=True)
class Target:
    """Where to log in: ``root@1.2.3.4:22`` — the user and the port are optional."""

    host: str
    port: int = 22
    username: str = "root"

    @classmethod
    def parse(cls, text: str) -> Target | None:
        raw = text.strip().removeprefix("ssh://")
        user = "root"
        if "@" in raw:
            user, _, raw = raw.rpartition("@")
            if not _USER_RX.match(user):
                return None
        host, port = raw, 22
        if raw.startswith("["):  # [v6]:port
            inside, _, rest = raw[1:].partition("]")
            host = inside
            if rest.startswith(":") and rest[1:].isdigit():
                port = int(rest[1:])
        elif raw.count(":") == 1:
            host, _, p = raw.partition(":")
            if not p.isdigit():
                return None
            port = int(p)
        if not 1 <= port <= 65535:
            return None
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not _HOST_RX.match(host):
                return None
        return cls(host=host, port=port, username=user)

    @property
    def text(self) -> str:
        user = "" if self.username == "root" else f"{self.username}@"
        port = "" if self.port == 22 else f":{self.port}"
        return f"{user}{self.host}{port}"

    @classmethod
    def of(cls, server: OpsServer) -> Target:
        return cls(host=server.host, port=server.port, username=server.username)

    def params(self) -> dict[str, object]:
        return {"host": self.host, "port": self.port, "username": self.username}


async def hand_over(redis: Redis, job_id: str, secret: str) -> None:
    """Give the worker a secret for ONE job: sealed, read once, gone after ``SECRET_TTL``."""
    sealed = vault.seal(secret, f"ops-secret:{job_id}")
    await redis.set(_secret_key(job_id), sealed, ex=SECRET_TTL)


async def take_over(redis: Redis, job_id: str) -> str | None:
    """The job's secret (and it is gone from Redis): None when it expired or never was."""
    sealed = await redis.getdel(_secret_key(job_id))
    if not sealed:
        return None
    return vault.unseal(sealed, f"ops-secret:{job_id}")


async def active_job(session: AsyncSession, chat_id: int) -> OpsJob | None:
    """The job this admin chat is waiting on, if any — one at a time per chat. A row that can no
    longer be in flight is closed on the way: ``queued`` past the secret's lifetime (the worker
    never took it), ``running`` past the job timeout (its worker died without a restart)."""
    repo = OpsJobRepository(session)
    job = await repo.running(chat_id)
    if job is None:
        return None
    now = datetime.now(UTC)
    if job.status == OpsJobStatus.queued and (now - job.created_at).total_seconds() > SECRET_TTL:
        await repo.finish(job, ok=False, error="کار هیچ‌وقت شروع نشد (worker در دسترس نبود)")
        return None
    started = job.started_at or job.created_at
    if job.status == OpsJobStatus.running and (now - started).total_seconds() > JOB_TIMEOUT + 60:
        await repo.finish(job, ok=False, error="کار نیمه‌کاره ماند (worker از کار افتاد)")
        return None
    return job


async def enqueue(
    session: AsyncSession,
    redis: Redis,
    arq: object,
    *,
    kind: str,
    params: dict,
    chat_id: int,
    message_id: int | None,
    lang: str,
    admin_id: int,
    secret: str | None = None,
) -> OpsJob:
    """Record the job, hand over its secret, commit, then queue it. The commit comes first: the
    worker reads the row in its own session, and a row it cannot see yet is a job that vanished."""
    job = await OpsJobRepository(session).create(
        kind=kind,
        chat_id=chat_id,
        message_id=message_id,
        lang=lang,
        params=params,
        created_by=admin_id,
    )
    if secret is not None:
        await hand_over(redis, job.id, secret)
    await session.commit()
    await arq.enqueue_job(JOB_FUNCTION, job.id, _job_id=f"ops:{job.id}")  # type: ignore[attr-defined]
    return job


class OpsService:
    """Logins and saved servers, over one session (the worker's, per job)."""

    def __init__(self, session: AsyncSession, http: httpx.AsyncClient) -> None:
        self._session = session
        self._http = http
        self.servers = OpsServerRepository(session)
        self._keys = OpsKeyRepository(session)

    # ---- the bot's own key ---------------------------------------------------------------------
    async def bot_key(self) -> asyncssh.SSHKey:
        row = await self._keys.get(BOT_KEY)
        if row is None:
            key = asyncssh.generate_private_key("ssh-ed25519", comment="gozar")
            private = vault.seal(key.export_private_key().decode(), f"ops-key:{BOT_KEY}")
            public = key.export_public_key().decode().strip()
            try:
                async with self._session.begin_nested():
                    row = await self._keys.put(BOT_KEY, private, public)
            except IntegrityError:  # another job made it a moment ago: use that one
                row = await self._keys.get(BOT_KEY)
                assert row is not None
        return asyncssh.import_private_key(vault.unseal(row.private, f"ops-key:{BOT_KEY}"))

    async def bot_public(self) -> str:
        return (await self.bot_key()).export_public_key().decode().strip()

    # ---- logins --------------------------------------------------------------------------------
    def _sudo_purpose(self, server: OpsServer) -> str:
        return f"ops-sudo:{server.host}:{server.port}:{server.username}"

    async def connect_saved(self, server: OpsServer, *, debug=None) -> Server:  # noqa: ANN001
        """Log into a saved server with the bot's key (its host key pinned). Raises RemoteError:
        ``auth`` = the key is no longer accepted (``key_ok`` is cleared), ``hostkey`` = the server
        shows another host key, ``sudo`` = its sudo now wants a password we don't have."""
        sudo = None
        if server.sudo_password:
            with contextlib.suppress(vault.VaultError):
                sudo = vault.unseal(server.sudo_password, self._sudo_purpose(server))
        key = await self.bot_key()
        creds = SSHCreds(
            host=server.host,
            port=server.port,
            username=server.username,
            private_key=key.export_private_key().decode(),
            sudo_password=sudo,
        )
        srv = Server(creds, server.label, pinned=server.host_key, debug=debug)
        try:
            await srv.connect()
        except RemoteError as e:
            if e.code == "auth":
                server.key_ok = False
                await self._session.flush()
            raise
        if not server.host_key:  # accepted a new key (🔄 trust): pin what it showed now
            server.host_key = srv.host_key
        server.last_login_at = datetime.now(UTC)
        server.ip = srv.public_ip or server.ip
        await self._session.flush()
        return srv

    async def login_new(
        self,
        target: Target,
        password: str,
        *,
        sudo_password: str | None = None,
        debug=None,  # noqa: ANN001
    ) -> tuple[Server, OpsServer, str]:
        """Log in with a password ONCE, install the bot's key, check it, and save the server.
        Returns the connected server, its row, and a line for the admin. The password is wiped
        from the credentials as soon as the key is in place."""
        existing = await self.servers.find(target.host, target.port, target.username)
        creds = SSHCreds(
            host=target.host,
            port=target.port,
            username=target.username,
            password=password,
            sudo_password=sudo_password,
        )
        label = existing.label if existing else target.host
        srv = Server(creds, label, pinned=existing.host_key if existing else None, debug=debug)
        await srv.connect()
        try:
            return await self._install_key(srv, target, existing)
        except BaseException:
            await srv.close()
            srv.creds.wipe()
            raise

    async def _install_key(
        self, srv: Server, target: Target, existing: OpsServer | None
    ) -> tuple[Server, OpsServer, str]:
        public, key = await self.bot_public(), await self.bot_key()

        async def put_key() -> tuple[access.KeyInstall | None, str | None]:
            try:
                ki = await access.install_key(srv, public)
            except RemoteError as e:
                return None, e.message
            host_key = srv.conn.get_server_host_key() if srv.conn else None
            why = await access.key_login_works(
                target.host, target.port, target.username, key, host_key
            )
            return ki, why

        async def country() -> str:
            if existing is not None and existing.country not in ("", "XX"):
                return existing.country
            return (await geo_lookup(self._http, srv.public_ip or target.host, seconds=5)).code

        (ki, why), code = await asyncio.gather(put_key(), country())
        key_ok = ki is not None and why is None
        row = await self._remember(srv, existing, target, code, key_ok)
        if key_ok:
            line = "🔑 کلید ربات " + ("نصب شد" if ki.added else "از قبل بود و کار می‌کند")
            line += "؛ از این به بعد بدون رمز وصل می‌شوم"
        else:
            line = f"⚠️ کلید ربات کار نکرد ({why or '?'})؛ دفعهٔ بعد هم رمز لازم است"
        # from here on the session runs on the key and the typed password goes — except as the
        # sudo password of a user whose sudo asks for one (this session's sudo needs it; the row
        # keeps it sealed for the next)
        if srv.sudo_mode == "password" and not srv.creds.sudo_password:
            srv.creds.sudo_password = srv.creds.password
        srv.creds.password = None
        return srv, row, line

    async def _remember(
        self, srv: Server, existing: OpsServer | None, target: Target, code: str, key_ok: bool
    ) -> OpsServer:
        row = existing
        if row is None:
            row = OpsServer(
                label=await self.servers.next_label(code),
                host=target.host,
                port=target.port,
                username=target.username,
            )
            await self.servers.add(row)
        row.ip = srv.public_ip or ""
        row.country = code or "XX"
        row.host_key = srv.host_key
        row.key_ok = key_ok
        row.last_login_at = datetime.now(UTC)
        if srv.sudo_mode == "password" and srv.sudo_secret:
            row.sudo_password = vault.seal(srv.sudo_secret, self._sudo_purpose(row))
        await self._session.flush()
        return row
