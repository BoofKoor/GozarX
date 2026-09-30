"""ButtonService — snapshot caching/invalidation, set/reset, editor merge (real DB + fakeredis)."""

from __future__ import annotations

import fakeredis.aioredis

from gozar.cache.redis import BUTTON_CONFIGS_KEY
from gozar.db.models.enums import Language
from gozar.services.button_service import ButtonService


def _svc(session) -> tuple[ButtonService, fakeredis.aioredis.FakeRedis]:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return ButtonService(session, redis), redis


async def test_snapshot_empty_defaults(session) -> None:
    svc, _ = _svc(session)
    snap = await svc.snapshot()
    assert snap.label("menu_config", Language.fa) is None
    assert snap.is_visible("menu_config") is True
    assert snap.row("menu_config") is None
    assert snap.position("menu_config") is None


async def test_set_then_snapshot_reflects_override(session) -> None:
    svc, _ = _svc(session)
    await svc.set("menu_config", labels={"fa": "x"}, is_visible=False, row_index=2, position=1)
    snap = await svc.snapshot()
    assert snap.label("menu_config", Language.fa) == "x"
    assert snap.label("menu_config", Language.en) is None  # partial override
    assert snap.is_visible("menu_config") is False
    assert snap.row("menu_config") == 2
    assert snap.position("menu_config") == 1


async def test_cache_is_served_until_invalidated(session) -> None:
    svc, redis = _svc(session)
    await svc.snapshot()  # populates the cache
    assert await redis.get(BUTTON_CONFIGS_KEY) is not None
    # A direct repo write bypassing set() must NOT appear until the cache is invalidated.
    await svc._repo.upsert(
        "menu_help", labels={"en": "Z"}, is_visible=True, row_index=None, position=None
    )
    assert (await svc.snapshot()).label("menu_help", Language.en) is None  # stale cache
    await svc.invalidate()
    assert (await svc.snapshot()).label("menu_help", Language.en) == "Z"  # reloaded


async def test_set_appearance_preserves_order(session) -> None:
    svc, _ = _svc(session)
    await svc.set("menu_config", labels=None, is_visible=True, row_index=3, position=2)
    await svc.set_appearance("menu_config", labels={"fa": "L"}, is_visible=False)
    snap = await svc.snapshot()
    assert snap.label("menu_config", Language.fa) == "L"
    assert snap.is_visible("menu_config") is False
    assert snap.row("menu_config") == 3  # order override preserved
    assert snap.position("menu_config") == 2


async def test_reorder_preserves_appearance(session) -> None:
    svc, _ = _svc(session)
    await svc.set("menu_help", labels={"en": "H"}, is_visible=False, row_index=None, position=None)
    await svc.reorder([("menu_help", 1, 0), ("menu_config", 0, 0)])
    snap = await svc.snapshot()
    assert snap.row("menu_help") == 1 and snap.position("menu_help") == 0
    assert snap.label("menu_help", Language.en) == "H"  # appearance preserved
    assert snap.is_visible("menu_help") is False
    assert snap.row("menu_config") == 0  # a fresh override for the reordered default button


async def test_reorder_skips_critical_keys(session) -> None:
    svc, _ = _svc(session)
    await svc.reorder([("back", 9, 9), ("menu_config", 1, 0)])
    snap = await svc.snapshot()
    assert snap.row("back") is None  # critical: no order override written (pinned)
    assert snap.row("menu_config") == 1  # non-critical reordered
    backs = [b for b in await svc.list_for_editor() if b.key == "back"]
    assert backs and all(
        b.effective_row == b.default_row and b.effective_position == b.default_position
        for b in backs
    )


async def test_reset_removes_override(session) -> None:
    svc, _ = _svc(session)
    await svc.set("apps", labels={"fa": "Y"}, is_visible=True, row_index=None, position=None)
    assert (await svc.snapshot()).label("apps", Language.fa) == "Y"
    await svc.reset("apps")
    assert (await svc.snapshot()).label("apps", Language.fa) is None


async def test_list_for_editor_merges_default_and_override(session) -> None:
    svc, _ = _svc(session)
    await svc.set(
        "menu_config", labels={"fa": "سفارشی"}, is_visible=True, row_index=None, position=None
    )
    by_key = {(i.key, i.screen): i for i in await svc.list_for_editor()}

    mc = by_key[("menu_config", "main_menu")]
    assert mc.default_label["fa"] == "📥 دریافت کانفیگ امروز"
    assert mc.effective_label["fa"] == "سفارشی"
    assert mc.effective_label["en"] == mc.default_label["en"]  # en untouched
    assert mc.customized is True

    apps = by_key[("apps", "help")]
    assert apps.customized is False
    assert apps.effective_label["fa"] == apps.default_label["fa"]

    # `back` is shared chrome — appears on several screens and is always critical.
    backs = [i for i in await svc.list_for_editor() if i.key == "back"]
    assert len(backs) > 1
    assert all(b.is_critical for b in backs)


async def test_an_order_set_on_one_screen_leaves_the_others_alone(session) -> None:
    # change_location sits on landing, config_delivered and status; the override table is keyed by
    # the button alone, so arranging it on one screen used to rearrange all three.
    svc, _ = _svc(session)
    await svc.reorder([("change_location", 1, 1)], screen="landing")
    snap = await svc.snapshot()
    assert snap.row("change_location", "landing") == 1
    assert snap.position("change_location", "landing") == 1
    assert snap.row("change_location", "status") is None  # still the catalogue default
    by = {(b.screen, b.key): b for b in await svc.list_for_editor()}
    assert by[("landing", "change_location")].effective_row == 1
    assert by[("status", "change_location")].effective_row == 0


async def test_hiding_on_one_screen_hides_there_only(session) -> None:
    svc, _ = _svc(session)
    await svc.set_appearance(
        "change_location", labels={"en": "Move"}, is_visible=False, screen="status"
    )
    snap = await svc.snapshot()
    assert snap.is_visible("change_location", "status") is False
    assert snap.is_visible("change_location", "landing") is True
    # The label is the button's name everywhere.
    assert snap.label("change_location", Language.en) == "Move"


async def test_an_edit_is_invalidated_again_after_the_commit(session) -> None:
    # Deleted only before the commit, a bot update in between re-cached the OLD rows for the TTL.
    from gozar.cache.redis import SESSION_INVALIDATE_KEY

    svc, _ = _svc(session)
    await svc.reorder([("menu_help", 0, 1)], screen="main_menu")
    assert BUTTON_CONFIGS_KEY in session.sync_session.info.get(SESSION_INVALIDATE_KEY, set())
