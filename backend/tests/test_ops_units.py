"""The console's operations, the parts that need no server: sealing secrets, reading an SSH
address, a node draft's choices, node names, and the read-once password hand-over."""

from __future__ import annotations

import pytest

from gozar import vault
from gozar.ops import node
from gozar.ops.geo import GeoInfo
from gozar.ops.report import OK, PENDING, Reporter
from gozar.remnawave.ops import Inbound, NodeInfo, Profile
from gozar.services import ops as ops_service
from gozar.services.node_draft import NodeDraft
from gozar.services.ops import Target

KEY = vault.parse_key(vault.new_key_text())


# ---- vault -------------------------------------------------------------------------------------
def test_a_sealed_value_opens_only_for_its_purpose_and_key() -> None:
    token = vault.seal("hunter2", "ops-sudo:a:22:u", key=KEY)
    assert token.startswith(vault.PREFIX) and "hunter2" not in token
    assert vault.unseal(token, "ops-sudo:a:22:u", key=KEY) == "hunter2"
    with pytest.raises(vault.VaultError):
        vault.unseal(token, "ops-sudo:b:22:u", key=KEY)  # copied to another server's row
    with pytest.raises(vault.VaultError):
        vault.unseal(token, "ops-sudo:a:22:u", key=vault.parse_key(vault.new_key_text()))
    with pytest.raises(vault.VaultError):
        vault.unseal(token[:-6] + "AAAAAA", "ops-sudo:a:22:u", key=KEY)
    assert vault.seal("x", "p", key=KEY) != vault.seal("x", "p", key=KEY)  # a fresh nonce


def test_vault_key_text_is_checked() -> None:
    with pytest.raises(vault.VaultError):
        vault.parse_key("too-short")
    with pytest.raises(vault.VaultError):
        vault.parse_key("!!!not base64!!!")
    assert len(vault.parse_key(vault.new_key_text().rstrip("="))) == 32  # padding optional


# ---- an SSH address ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("1.2.3.4", ("1.2.3.4", 22, "root")),
        (" root@1.2.3.4:2222 ", ("1.2.3.4", 2222, "root")),
        ("ubuntu@node.example.com", ("node.example.com", 22, "ubuntu")),
        ("ssh://deploy@node.example.com:22", ("node.example.com", 22, "deploy")),
        ("[2001:db8::1]:2200", ("2001:db8::1", 2200, "root")),
        ("2001:db8::1", ("2001:db8::1", 22, "root")),
    ],
)
def test_an_ssh_address_is_read(text: str, want: tuple) -> None:
    t = Target.parse(text)
    assert t is not None and (t.host, t.port, t.username) == want


@pytest.mark.parametrize(
    "text",
    ["", "root@", "1.2.3.4:0", "1.2.3.4:70000", "1.2.3.4:ssh", "bad host", "a;rm -rf /@1.2.3.4",
     "-oProxyCommand=x@1.2.3.4", "node_example", "root@1.2.3.4 && id"],
)  # fmt: skip
def test_what_is_not_an_ssh_address_is_refused(text: str) -> None:
    assert Target.parse(text) is None


def test_an_address_prints_back_without_its_defaults() -> None:
    assert Target("1.2.3.4").text == "1.2.3.4"
    assert Target("h.example.com", 2222, "ubuntu").text == "ubuntu@h.example.com:2222"


# ---- node names --------------------------------------------------------------------------------
def test_a_node_is_named_by_its_flag_then_its_country() -> None:
    assert node.suggest_name("DE", []) == "🇩🇪 آلمان"
    assert node.suggest_name("DE", ["🇩🇪 آلمان"]) == "🇩🇪 آلمان 2"
    assert node.suggest_name("DE", ["🇩🇪 آلمان", "🇩🇪 آلمان 2"]) == "🇩🇪 آلمان 3"
    assert node.suggest_name("XX", []) == "نود 1"
    assert node.suggest_name("ZW", []) == "🇿🇼 ZW"  # no Persian name in the table: its code


def test_the_panels_name_rules_count_javascript_length() -> None:
    assert node.name_problem("ab", []) is not None
    assert node.name_problem("🇩🇪", []) is None  # 4 UTF-16 units
    assert node.name_problem("🇩🇪" * 8, []) is not None  # 32 units
    assert node.name_problem("🇩🇪 آلمان", ["🇩🇪 آلمان"]) is not None


# ---- a node draft ------------------------------------------------------------------------------
def _profile(uuid: str, name: str, ports: list[int], nodes: list[str]) -> Profile:
    return Profile(
        uuid, name, [Inbound(f"i{p}", f"t{p}", "vless", "tcp", None, p) for p in ports], nodes
    )


def _prep(listeners: list[tuple[str, int, str]]) -> node.Prep:
    facts = node.NodeFacts(
        os_pretty="Ubuntu 24.04",
        arch="x86_64",
        listeners=[
            node.Listener(proto, "0.0.0.0", port, proc, (100,)) for proto, port, proc in listeners
        ],
    )
    profiles = [
        _profile("p1", "Main", [443], ["n1", "n2"]),
        _profile("p2", "Other", [8443, 2222], ["n3"]),  # (a profile with no node would win)
        Profile("p3", "Empty", [], []),
    ]
    nodes = [NodeInfo("u1", "🇩🇪 آلمان", "198.51.100.1", 2222)]
    prep = node.Prep(
        facts=facts,
        geo=GeoInfo("203.0.113.7", "DE", "Germany", "Hetzner", "test"),
        address="203.0.113.7",
        profiles=profiles,
        nodes=nodes,
        profile=None,
    )
    prep.choose(*node.pick_profile(profiles))
    return prep


def test_a_draft_starts_from_what_the_server_and_panel_said() -> None:
    draft = NodeDraft.from_prep(
        _prep([("tcp", 22, "sshd")]), server_id=3, login="root@h", key_ok=True, sudo_kept=False
    )
    assert draft.name == "🇩🇪 آلمان 2"  # the panel already has «🇩🇪 آلمان»
    assert draft.profile_uuid == "p1" and draft.node_port == 2222
    assert [p.uuid for p in draft.profiles] == ["p1", "p2"]  # one without inbounds isn't offered
    assert draft.ready
    again = NodeDraft.load(draft.dump())
    assert again == draft


def test_choosing_a_profile_rechecks_its_ports_against_the_server() -> None:
    draft = NodeDraft.from_prep(
        _prep([("tcp", 8443, "nginx")]), server_id=3, login="h", key_ok=True, sudo_kept=False
    )
    assert draft.ready
    assert draft.choose_profile("p2")
    assert draft.conflicts == ["8443/tcp در دست «nginx» است"]
    assert draft.node_port == 2223  # 2222 is one of the profile's own ports
    assert not draft.ready
    assert not draft.choose_profile("nope")
    assert draft.choose_profile("p1") and draft.ready


def test_renaming_follows_the_panels_rules_and_a_country_moves_a_suggested_name() -> None:
    draft = NodeDraft.from_prep(_prep([]), server_id=3, login="h", key_ok=True, sudo_kept=False)
    draft.set_country("NL")
    assert draft.name == "🇳🇱 هلند" and draft.country == "NL"
    assert draft.rename("🇩🇪 آلمان") is not None  # taken in the panel
    assert draft.rename("  my   node ") is None
    assert draft.name == "my node" and not draft.name_auto
    draft.set_country("FI")
    assert draft.name == "my node"  # an admin's own name stays
    draft.set_country("??")
    assert draft.country == "XX"


def test_a_draft_turns_into_the_install_plan() -> None:
    draft = NodeDraft.from_prep(_prep([]), server_id=3, login="h", key_ok=True, sudo_kept=False)
    plan = draft.plan("panel.example.com")
    assert (plan.name, plan.address, plan.port, plan.profile_uuid) == (
        draft.name,
        "203.0.113.7",
        2222,
        "p1",
    )
    assert plan.replace is False and plan.panel_host == "panel.example.com"


# ---- the reporter ------------------------------------------------------------------------------
async def test_a_second_plan_keeps_the_steps_already_done() -> None:
    rep = Reporter()
    await rep.plan([("login", "ورود")])
    async with rep.stage("login"):
        pass
    await rep.plan([("check", "بررسی"), ("login", "again")])
    assert [(s.key, s.status) for s in rep.steps] == [("login", OK), ("check", PENDING)]


# ---- the read-once hand-over -------------------------------------------------------------------
class _Redis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value
        self.ttl[key] = ex or 0

    async def getdel(self, key: str) -> str | None:
        return self.data.pop(key, None)


async def test_a_password_reaches_the_worker_sealed_and_only_once(monkeypatch) -> None:
    monkeypatch.setattr(vault, "_key", lambda key=None: KEY)
    redis = _Redis()
    await ops_service.hand_over(redis, "job1", "s3cret pass")  # type: ignore[arg-type]
    stored = redis.data["ops:secret:job1"]
    assert "s3cret" not in stored and redis.ttl["ops:secret:job1"] == ops_service.SECRET_TTL
    assert await ops_service.take_over(redis, "job1") == "s3cret pass"  # type: ignore[arg-type]
    assert await ops_service.take_over(redis, "job1") is None  # type: ignore[arg-type]
    # sealed for job1, it doesn't open as another job's
    await ops_service.hand_over(redis, "job1", "x")  # type: ignore[arg-type]
    redis.data["ops:secret:job2"] = redis.data.pop("ops:secret:job1")
    with pytest.raises(vault.VaultError):
        await ops_service.take_over(redis, "job2")  # type: ignore[arg-type]
