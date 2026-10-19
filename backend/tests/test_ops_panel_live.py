"""``OpsPanel`` against a REAL Remnawave panel (opt-in): ``GOZAR_LIVE_PANEL`` is its base URL
(``http://127.0.0.1:3000`` straight to the backend works — the client adds the forwarding headers),
``GOZAR_LIVE_PANEL_TOKEN`` a token with every scope and ``GOZAR_LIVE_PANEL_RO_TOKEN`` one with only
``nodes:read``. Run against 3.4.4: what a node install asks of the panel, and how it says no.

It creates a node at a TEST-NET address and deletes it again.
"""

from __future__ import annotations

import os
import secrets

import httpx
import pytest
import pytest_asyncio

from gozar.remnawave.ops import NODE_SCOPES, SCOPE_PROBES, OpsPanel, PanelError

BASE = os.environ.get("GOZAR_LIVE_PANEL", "")
TOKEN = os.environ.get("GOZAR_LIVE_PANEL_TOKEN", "")
RO_TOKEN = os.environ.get("GOZAR_LIVE_PANEL_RO_TOKEN", "")

pytestmark = pytest.mark.skipif(not (BASE and TOKEN), reason="set GOZAR_LIVE_PANEL(+_TOKEN)")


@pytest_asyncio.fixture
async def http():
    async with httpx.AsyncClient(trust_env=False) as client:
        yield client


async def test_what_an_install_needs_is_there(http) -> None:
    panel = OpsPanel(http, BASE, TOKEN)
    profiles, nodes = await panel.check_access()
    usable = [p for p in profiles if p.inbounds]
    assert usable, "the panel seeds a Default-Profile with an inbound"
    assert all(ib.uuid and ib.tag for p in usable for ib in p.inbounds)
    assert usable[0].ports()  # (port, proto) pairs for the conflict check
    key = await panel.keygen()
    assert len(key) > 100  # base64 JSON with a private key in it
    assert await panel.scopes_missing() == []


async def test_a_limited_token_is_named_scope_by_scope(http) -> None:
    if not RO_TOKEN:
        pytest.skip("GOZAR_LIVE_PANEL_RO_TOKEN not set")
    panel = OpsPanel(http, BASE, RO_TOKEN)
    missing = await panel.scopes_missing()
    assert set(missing) == set(SCOPE_PROBES) - {"nodes:read"}
    assert set(NODE_SCOPES) - {"nodes:read"} <= set(missing)
    with pytest.raises(PanelError) as e:
        await panel.check_access()
    assert e.value.code == "scope" and e.value.status == 403


async def test_a_wrong_token_is_auth(http) -> None:
    with pytest.raises(PanelError) as e:
        await OpsPanel(http, BASE, "not-a-token").nodes()
    assert e.value.code == "auth"


async def test_a_node_is_created_refused_twice_and_deleted(http) -> None:
    panel = OpsPanel(http, BASE, TOKEN)
    profile = next(p for p in await panel.profiles() if p.inbounds)
    address = f"203.0.113.{secrets.randbelow(200) + 20}"
    name = f"🇩🇪 آلمان {secrets.randbelow(900) + 100}"
    node = await panel.create_node(
        name=name, address=address, port=2222, country="de", profile=profile
    )
    try:
        assert node.uuid and node.name == name and node.address == address
        assert node.country == "DE" and node.port == 2222
        again = await panel.node(node.uuid)
        assert again.profile_uuid == profile.uuid
        assert set(again.active_inbounds) == {ib.uuid for ib in profile.inbounds}
        assert node.uuid in {n.uuid for n in await panel.nodes()}
        with pytest.raises(PanelError) as e:
            await panel.create_node(
                name=name, address="203.0.113.250", port=2222, country="DE", profile=profile
            )
        assert e.value.code == "name_taken"
        with pytest.raises(PanelError) as e:
            await panel.create_node(
                name=name + "x", address=address, port=2222, country="DE", profile=profile
            )
        assert e.value.code == "address_taken"
    finally:
        assert await panel.delete_node(node.uuid)
    assert await panel.delete_node(node.uuid)  # already gone reads as gone
    assert node.uuid not in {n.uuid for n in await panel.nodes()}
