"""The console's SSH logins against a REAL sshd (opt-in: ``GOZAR_LIVE_SSH=1`` and the
``gozar-test-sshd`` image — Ubuntu 24.04 + openssh-server with root, a password-sudo user, a
NOPASSWD-sudo user and one without sudo). Needs ``TEST_DATABASE_URL`` too: a login saves the server.

What it proves on a real server: one password login installs the bot's own key and the next login
needs only that key; the host key is pinned and a different one is refused; sudo is detected and a
sudo password is kept only sealed; the bot's key comes back off; no password reaches a debug line.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess

import asyncssh
import httpx
import pytest
import pytest_asyncio

from gozar import vault
from gozar.db.repositories.ops import OpsServerRepository
from gozar.ops import access, node
from gozar.ops.errors import RemoteError
from gozar.services.ops import OpsService, Target

pytestmark = pytest.mark.skipif(
    os.environ.get("GOZAR_LIVE_SSH") != "1" or shutil.which("docker") is None,
    reason="live sshd test: set GOZAR_LIVE_SSH=1 (needs docker + the gozar-test-sshd image)",
)

PORT = 52222
NAME = "gozar-test-sshd-run"
KEY = vault.parse_key(vault.new_key_text())
PASSWORDS = ("rootpass-123", "alicepass-456", "bobpass-789", "carolpass-000")


def _docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False)


@pytest.fixture(scope="module")
def sshd():
    _docker("rm", "-f", NAME)
    run = _docker("run", "-d", "--name", NAME, "-p", f"127.0.0.1:{PORT}:22", "gozar-test-sshd")
    if run.returncode != 0:
        pytest.skip(f"could not start the sshd container: {run.stderr.strip()}")
    yield "127.0.0.1", PORT
    _docker("rm", "-f", NAME)


@pytest_asyncio.fixture
async def ops(session, sshd, monkeypatch):
    monkeypatch.setattr(vault, "_key", lambda key=None: KEY)
    for _ in range(40):  # sshd takes a moment after the container starts
        try:
            await asyncssh.get_server_host_key(*sshd)
            break
        except (OSError, asyncssh.Error):
            await asyncio.sleep(0.25)
    async with httpx.AsyncClient() as http:
        yield OpsService(session, http)


def _lines() -> tuple[list[str], object]:
    lines: list[str] = []
    return lines, lines.append


async def test_one_password_login_installs_the_bots_key_and_then_the_key_alone_logs_in(
    ops, sshd, session
) -> None:
    host, port = sshd
    lines, debug = _lines()
    srv, row, line = await ops.login_new(Target(host, port, "root"), "rootpass-123", debug=debug)
    async with srv:
        assert srv.sudo_mode is None and "نصب شد" in line
        assert (await srv.run("id -u")).out.strip() == "0"
        assert srv.creds.password is None  # wiped once the key was in
    assert row.key_ok and row.label == "SRV-1" and row.country == "XX"
    assert row.host_key.startswith("ssh-ed25519 ")  # the best type the server offers is pinned
    assert row.sudo_password is None
    await session.commit()

    # the next login: no password at all, the host key pinned
    srv = await ops.connect_saved(row, debug=debug)
    async with srv:
        assert srv.creds.password is None and srv.first_seen is False
        assert (await srv.run("id -u")).out.strip() == "0"
        keys, ours = await access.keys_info(srv, await ops.bot_public())
        assert ours and keys == 1

    # a second password login finds the key already there, and the same row
    srv, again, line = await ops.login_new(Target(host, port, "root"), "rootpass-123")
    async with srv:
        assert again.id == row.id and "از قبل بود" in line
    assert not any(p in x for x in lines for p in PASSWORDS)


async def test_a_different_host_key_is_refused_before_any_password_is_sent(ops, sshd) -> None:
    host, port = sshd
    srv, row, _line = await ops.login_new(Target(host, port, "root"), "rootpass-123")
    await srv.close()
    other = asyncssh.generate_private_key("ssh-ed25519").export_public_key().decode().strip()
    row.host_key = other
    with pytest.raises(RemoteError) as e:
        await ops.connect_saved(row)
    assert e.value.code == "hostkey" and "SHA256:" in e.value.detail
    with pytest.raises(RemoteError) as e:  # a password login to the same server: refused too
        await ops.login_new(Target(host, port, "root"), "rootpass-123")
    assert e.value.code == "hostkey"
    await OpsServerRepository(ops._session).unpin(row)
    srv = await ops.connect_saved(row)  # accepted: the new key is pinned again
    await srv.close()
    assert row.host_key == srv.host_key


async def test_a_password_sudo_user_works_through_sudo_and_its_password_stays_sealed(
    ops, sshd
) -> None:
    host, port = sshd
    lines, debug = _lines()
    srv, row, _line = await ops.login_new(Target(host, port, "alice"), "alicepass-456", debug=debug)
    async with srv:
        assert srv.sudo_mode == "password"
        assert (await srv.run("id -u")).out.strip() == "0"
    assert row.sudo_password and "alicepass" not in row.sudo_password
    srv = await ops.connect_saved(row, debug=debug)  # key login, sudo from the sealed copy
    async with srv:
        assert srv.creds.password is None and srv.sudo_mode == "password"
        assert (await srv.run("whoami")).out.strip() == "root"
        assert (await srv.run_user("whoami")).out.strip() == "alice"
    assert not any(p in x for x in lines for p in PASSWORDS)


async def test_nopasswd_sudo_keeps_nothing_and_no_sudo_is_refused(ops, sshd) -> None:
    host, port = sshd
    srv, row, _line = await ops.login_new(Target(host, port, "carol"), "carolpass-000")
    async with srv:
        assert srv.sudo_mode == "nopasswd"
    assert row.sudo_password is None and row.key_ok
    with pytest.raises(RemoteError) as e:
        await ops.login_new(Target(host, port, "bob"), "bobpass-789")
    assert e.value.code == "sudo"


async def test_a_wrong_password_is_auth_and_a_removed_key_clears_key_ok(ops, sshd) -> None:
    host, port = sshd
    with pytest.raises(RemoteError) as e:
        await ops.login_new(Target(host, port, "root"), "wrong-password")
    assert e.value.code == "auth"
    srv, row, _line = await ops.login_new(Target(host, port, "root"), "rootpass-123")
    async with srv:
        assert await access.remove_key(srv, await ops.bot_public())
        assert not await access.remove_key(srv, await ops.bot_public())
    with pytest.raises(RemoteError) as e:
        await ops.connect_saved(row)
    assert e.value.code == "auth" and row.key_ok is False


async def test_a_real_servers_facts_are_read(ops, sshd) -> None:
    host, port = sshd
    srv, _row, _line = await ops.login_new(Target(host, port, "root"), "rootpass-123")
    async with srv:
        f = await node.gather(srv)
    assert f.os_id == "ubuntu" and f.arch in ("x86_64", "aarch64") and f.apt
    assert f.owner(22, "tcp") == "sshd" and not f.has_docker and not f.rn_dir
    assert f.mem_mb > 0 and f.disk_mb > 0
