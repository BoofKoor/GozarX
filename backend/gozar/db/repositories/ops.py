"""Repositories for the console's operations — the only path to ``ops_servers``, ``ops_keys`` and
``ops_jobs``. Values stay as stored: sealing and unsealing is the service's job."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update

from gozar.db.models.ops import OpsJob, OpsJobStatus, OpsKey, OpsServer
from gozar.db.repositories.base import BaseRepository


class OpsServerRepository(BaseRepository):
    async def get(self, server_id: int) -> OpsServer | None:
        return await self.session.get(OpsServer, server_id)

    async def all(self) -> list[OpsServer]:
        rows = await self.session.scalars(select(OpsServer).order_by(OpsServer.label))
        return list(rows.all())

    async def find(self, host: str, port: int, username: str | None = None) -> OpsServer | None:
        """A saved server by the address typed (or the IP it answered on) + port (+ user)."""
        q = select(OpsServer).where(
            or_(OpsServer.host == host, OpsServer.ip == host), OpsServer.port == port
        )
        if username is not None:
            q = q.where(OpsServer.username == username)
        return (await self.session.scalars(q.order_by(OpsServer.id))).first()

    async def by_addresses(self, addresses: set[str]) -> dict[str, OpsServer]:
        """address (host or ip) → saved server, for every address in ``addresses``."""
        if not addresses:
            return {}
        rows = await self.session.scalars(
            select(OpsServer).where(or_(OpsServer.host.in_(addresses), OpsServer.ip.in_(addresses)))
        )
        out: dict[str, OpsServer] = {}
        for s in rows.all():
            for a in (s.host, s.ip):
                if a in addresses:
                    out.setdefault(a, s)
        return out

    async def label_taken(self, label: str, except_id: int | None = None) -> bool:
        q = select(func.count()).select_from(OpsServer).where(OpsServer.label == label)
        if except_id is not None:
            q = q.where(OpsServer.id != except_id)
        return bool(await self.session.scalar(q))

    async def next_label(self, country: str) -> str:
        """``DE-1``, ``DE-2``, … (``SRV-n`` when the country is unknown) — the first one free."""
        base = country.upper() if country and country.upper() != "XX" else "SRV"
        taken = set(
            (
                await self.session.scalars(
                    select(OpsServer.label).where(OpsServer.label.like(f"{base}-%"))
                )
            ).all()
        )
        n = 1
        while f"{base}-{n}" in taken:
            n += 1
        return f"{base}-{n}"

    async def add(self, server: OpsServer) -> OpsServer:
        self.session.add(server)
        await self.session.flush()
        return server

    async def delete(self, server: OpsServer) -> None:
        await self.session.delete(server)
        await self.session.flush()

    async def unpin(self, server: OpsServer) -> None:
        """Forget the pinned host key (the admin accepted a new one): the next login pins
        whatever the server shows then."""
        server.host_key = None
        await self.session.flush()


class OpsKeyRepository(BaseRepository):
    async def get(self, name: str) -> OpsKey | None:
        return await self.session.get(OpsKey, name)

    async def put(self, name: str, private: str, public: str) -> OpsKey:
        row = OpsKey(name=name, private=private, public=public)
        self.session.add(row)
        await self.session.flush()
        return row


class OpsJobRepository(BaseRepository):
    async def create(
        self,
        *,
        kind: str,
        chat_id: int,
        message_id: int | None,
        lang: str,
        params: dict,
        created_by: int,
    ) -> OpsJob:
        """Record a job at ENQUEUE time, before the worker touches it."""
        row = OpsJob(
            id=secrets.token_hex(8),
            kind=kind,
            chat_id=chat_id,
            message_id=message_id,
            lang=lang,
            params=params,
            created_by=created_by,
            status=OpsJobStatus.queued,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, job_id: str) -> OpsJob | None:
        return await self.session.get(OpsJob, job_id)

    async def start(self, job: OpsJob) -> None:
        job.status = OpsJobStatus.running
        job.started_at = datetime.now(UTC)
        await self.session.flush()

    async def finish(
        self,
        job: OpsJob,
        *,
        ok: bool,
        result: dict | None = None,
        error: str | None = None,
        status: str | None = None,
    ) -> None:
        """Close the job ``ok`` / ``failed`` (or ``status``: ``interrupted``). ``result`` None
        keeps what the worker recorded on the way."""
        job.status = status or (OpsJobStatus.ok if ok else OpsJobStatus.failed)
        if result is not None:
            job.result = result
        job.error = error
        job.finished_at = datetime.now(UTC)
        await self.session.flush()

    async def running(self, chat_id: int) -> OpsJob | None:
        """A job still queued or running for this chat (one at a time per admin chat)."""
        q = (
            select(OpsJob)
            .where(
                OpsJob.chat_id == chat_id,
                OpsJob.status.in_((OpsJobStatus.queued, OpsJobStatus.running)),
            )
            .order_by(OpsJob.created_at.desc())
        )
        return (await self.session.scalars(q)).first()

    async def fail_interrupted(self) -> list[OpsJob]:
        """Nothing runs while a worker is starting, so a job still ``running`` is one whose worker
        died under it: close it as ``interrupted`` (its message says so) instead of leaving it
        "in flight" forever. Returns those rows."""
        rows = list(
            (
                await self.session.scalars(
                    select(OpsJob).where(OpsJob.status == OpsJobStatus.running)
                )
            ).all()
        )
        if rows:
            await self.session.execute(
                update(OpsJob)
                .where(OpsJob.id.in_([r.id for r in rows]))
                .values(status=OpsJobStatus.interrupted, finished_at=datetime.now(UTC))
            )
        return rows
