"""Public account handle (``GZ-…``): format, mint-on-create uniqueness, lookup, and its use as the
referral code in ``?ref=`` links (handle OR legacy uuid → the inviter's device uuid).

Generator/format checks are DB-free; the repo + endpoint checks are DB-gated.
"""

from __future__ import annotations

import re

from gozar.db.handles import new_handle, normalize_handle
from gozar.db.models.site_device import SiteDevice
from gozar.db.repositories.site_device import SiteDeviceRepository

_HANDLE_RE = re.compile(r"^GZ-[23456789ABCDEFGHJKMNPQRSTVWXYZ]{6}$")


# --- generator (DB-free) ------------------------------------------------------------------------


def test_handle_format_and_unambiguous_charset() -> None:
    for _ in range(200):
        h = new_handle()
        assert _HANDLE_RE.match(h), h
        # no visually ambiguous characters
        assert not set("01ILOU") & set(h[3:])


def test_normalize_handle_uppercases_and_trims() -> None:
    assert normalize_handle("  gz-7k3f9a ") == "GZ-7K3F9A"


# --- repository (DB-gated) ----------------------------------------------------------------------


async def test_create_mints_unique_handle(session) -> None:
    repo = SiteDeviceRepository(session)
    a = await repo.create("11111111-1111-1111-1111-111111111111")
    b = await repo.create("22222222-2222-2222-2222-222222222222")
    assert a.handle and b.handle and a.handle != b.handle
    assert _HANDLE_RE.match(a.handle)


async def test_get_by_handle_is_case_insensitive(session) -> None:
    repo = SiteDeviceRepository(session)
    device = await repo.create("33333333-3333-3333-3333-333333333333")
    found = await repo.get_by_handle(device.handle.lower())  # incoming ?ref= may be lower-cased
    assert found is not None and found.uuid == device.uuid
    assert await repo.get_by_handle("GZ-NOPE99") is None


async def test_handle_collision_retries(session, monkeypatch) -> None:
    repo = SiteDeviceRepository(session)
    taken = await repo.create("44444444-4444-4444-4444-444444444444")

    # Force the generator to return the taken handle once, then a fresh one — create must retry
    # past the collision rather than raise.
    outputs = iter([taken.handle, "GZ-FRESH2"])
    monkeypatch.setattr("gozar.db.repositories.site_device.new_handle", lambda: next(outputs))
    other = await repo.create("55555555-5555-5555-5555-555555555555")
    assert other.handle == "GZ-FRESH2"


async def test_referral_by_handle_resolves_to_inviter_uuid(session) -> None:
    """A ``?ref=<handle>`` link stores the inviter's UUID in ``referred_by`` (so referral credit,
    which looks the inviter up by PK, keeps working)."""
    repo = SiteDeviceRepository(session)
    inviter = await repo.create("66666666-6666-6666-6666-666666666666")

    from types import SimpleNamespace

    from gozar.web.routes.public.identity import _referrer

    new_uuid = "77777777-7777-7777-7777-777777777777"
    request = SimpleNamespace(query_params={"ref": inviter.handle})
    resolved = await _referrer(request, repo, new_uuid)
    assert resolved == inviter.uuid  # the UUID, not the handle

    # A legacy uuid ref is taken as-is; an unknown handle earns no credit.
    request_uuid = SimpleNamespace(query_params={"ref": inviter.uuid})
    assert await _referrer(request_uuid, repo, new_uuid) == inviter.uuid
    request_bad = SimpleNamespace(query_params={"ref": "GZ-ZZZZZZ"})
    assert await _referrer(request_bad, repo, new_uuid) is None


async def test_created_device_persists_handle_column(session) -> None:
    repo = SiteDeviceRepository(session)
    await repo.create("88888888-8888-8888-8888-888888888888")
    row = await session.get(SiteDevice, "88888888-8888-8888-8888-888888888888")
    assert row is not None and row.handle and row.handle.startswith("GZ-")
