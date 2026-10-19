"""The console's operations: saved servers, the bot's own SSH key, and one row per job.

``ops_servers``: every server the bot logged into once. After that login the bot's own ed25519 key
is in the login user's ``authorized_keys`` (``key_ok``) and no password is ever asked again — none
is kept. The server's host key is pinned here (trust on first use), so a server that later shows a
different one is refused before anything is sent. ``sudo_password`` exists only for a non-root user
whose sudo asks for one, and is SEALED (``gozar.vault``).

``ops_keys``: the bot's own SSH key pair (private half sealed).

``ops_jobs``: a job is SSH work the worker does while a console message shows its progress. Written
at ENQUEUE time by the handler and completed by the worker — like ``broadcast_logs``, so a job that
never ran shows as stuck on ``queued`` instead of vanishing, and a worker that died mid-job leaves
one marked ``interrupted`` at its next start. ``params`` holds no secret, ever.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class OpsServer(Base):
    __tablename__ = "ops_servers"
    __table_args__ = (UniqueConstraint("host", "port", "username", name="uq_ops_servers_login"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: What the admin calls it ("DE-1"), unique; the country's code and a number by default.
    label: Mapped[str] = mapped_column(String(64), unique=True)
    host: Mapped[str] = mapped_column(String(255))  # what the admin typed: an IP or a name
    port: Mapped[int] = mapped_column(Integer, default=22, server_default=text("22"))
    username: Mapped[str] = mapped_column(String(64), default="root", server_default="root")
    ip: Mapped[str] = mapped_column(String(64), default="", server_default="")  # what we reached
    country: Mapped[str] = mapped_column(String(2), default="XX", server_default="XX")
    os: Mapped[str] = mapped_column(String(128), default="", server_default="")
    #: The pinned host key (OpenSSH public key text) — trust on first use.
    host_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: A fresh login with ONLY the bot's key worked when it was installed.
    key_ok: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    #: Sealed; only for a non-root user whose sudo asks a password.
    sudo_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def address(self) -> str:
        user = "" if self.username == "root" else f"{self.username}@"
        port = "" if self.port == 22 else f":{self.port}"
        return f"{user}{self.host}{port}"


class OpsKey(Base):
    __tablename__ = "ops_keys"

    name: Mapped[str] = mapped_column(String(32), primary_key=True)  # "ssh_bot"
    private: Mapped[str] = mapped_column(Text)  # sealed
    public: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OpsJobStatus:
    queued = "queued"
    running = "running"
    ok = "ok"
    failed = "failed"
    interrupted = "interrupted"  # the worker died mid-job (closed at its next start)


class OpsJob(Base):
    __tablename__ = "ops_jobs"
    __table_args__ = (Index("ix_ops_jobs_created_at", text("created_at DESC")),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # random hex
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(
        String(16), default=OpsJobStatus.queued, server_default=OpsJobStatus.queued
    )
    #: Where the job reports: the console message it took over.
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lang: Mapped[str] = mapped_column(String(2), default="fa", server_default="fa")
    params: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
