"""A node waiting for the admin's ✅: what the server and the panel said, and the admin's choices.

Adding a node is two jobs with a screen between them. ``node_prepare`` logs in, reads the
server and the panel, and leaves a ``NodeDraft`` in its job row; the console draws it as a summary
the admin can change (the name, the config profile, the country) before ✅ starts
``node_install``. The draft
carries everything a change needs — the ports the server already listens on, the names the panel
already has — so changing the profile or the name is decided here, without logging in again; the
install job checks all of it once more on the server before it changes anything.

Plain data (JSON in the job row and in FSM data), no secret: the password a login took is gone
before a draft exists.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from gozar.ops import node
from gozar.ops.errors import RemoteError
from gozar.ops.geo import known
from gozar.remnawave.ops import Profile


@dataclass
class ProfileChoice:
    uuid: str
    name: str
    inbounds: int
    ports: list[tuple[int, str]]
    nodes: int  # how many nodes already run it

    @classmethod
    def of(cls, p: Profile) -> ProfileChoice:
        return cls(p.uuid, p.name, len(p.inbounds), p.ports(), len(p.node_names))


@dataclass
class NodeDraft:
    server_id: int
    login: str  # "root@1.2.3.4" — how the bot logs in
    address: str  # what the panel will dial: the address the server answered on
    country: str  # ISO alpha-2, "XX" unknown
    name: str
    name_auto: bool  # still the suggested name (follows a country change)
    profiles: list[ProfileChoice]
    profile_uuid: str | None
    profile_why: str
    node_port: int
    ssh_port: int
    existing: str  # an install already there, replaced (with a backup) on ✅; "" = none
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)  # for the summary: os, arch, ram, disk…
    listeners: list[tuple[str, int, str, list[int]]] = field(default_factory=list)
    rn_pids: list[int] = field(default_factory=list)
    node_names: list[str] = field(default_factory=list)  # the panel's nodes when it was read
    key_ok: bool = True  # the bot's key logs in (no password needed for the install)
    sudo_kept: bool = False  # this login's sudo asks a password, kept sealed on the server row

    # ---- (de)serialising ---------------------------------------------------------------------
    def dump(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def load(cls, data: dict[str, Any]) -> NodeDraft:
        raw = dict(data)
        raw["profiles"] = [
            ProfileChoice(
                p["uuid"],
                p["name"],
                int(p["inbounds"]),
                [(int(a), str(b)) for a, b in p["ports"]],
                int(p["nodes"]),
            )
            for p in raw.get("profiles", [])
        ]
        raw["listeners"] = [
            (str(a), int(b), str(c), [int(x) for x in d]) for a, b, c, d in raw.get("listeners", [])
        ]
        known_fields = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in raw.items() if k in known_fields})

    @classmethod
    def from_prep(
        cls, prep: node.Prep, *, server_id: int, login: str, key_ok: bool, sudo_kept: bool
    ) -> NodeDraft:
        f = prep.facts
        names = [n.name for n in prep.nodes]
        return cls(
            server_id=server_id,
            login=login,
            address=prep.address,
            country=prep.geo.code if known(prep.geo.code) else "XX",
            name=node.suggest_name(prep.geo.code, names),
            name_auto=True,
            profiles=[ProfileChoice.of(p) for p in prep.usable_profiles],
            profile_uuid=prep.profile.uuid if prep.profile else None,
            profile_why=prep.profile_why,
            node_port=prep.node_port,
            ssh_port=prep.ssh_port,
            existing=prep.existing,
            blockers=list(prep.blockers),
            warnings=list(prep.warnings),
            conflicts=list(prep.conflicts),
            facts={
                "os": f.os_pretty or f.os_id,
                "arch": f.arch,
                "virt": f.virt,
                "mem_mb": f.mem_mb,
                "disk_mb": f.disk_mb,
                "docker": f.docker if f.has_docker else "",
                "ufw": f.ufw_active,
                "isp": prep.geo.isp,
            },
            listeners=[(x.proto, x.port, x.proc, list(x.pids)) for x in f.listeners],
            rn_pids=sorted(f.rn_pids),
            node_names=names,
            key_ok=key_ok,
            sudo_kept=sudo_kept,
        )

    # ---- what the admin can change ------------------------------------------------------------
    @property
    def profile(self) -> ProfileChoice | None:
        return next((p for p in self.profiles if p.uuid == self.profile_uuid), None)

    def _facts(self) -> node.NodeFacts:
        return node.NodeFacts(
            listeners=[
                node.Listener(proto, "", port, proc, tuple(pids))
                for proto, port, proc, pids in self.listeners
            ],
            rn_pids=set(self.rn_pids),
        )

    @property
    def _ignore(self) -> set[int]:
        # the node being replaced stops before the new one starts: its ports don't count
        return set(self.rn_pids) if self.existing else set()

    def choose_profile(self, uuid: str) -> bool:
        """Run ``uuid`` on the node; the ports it needs are checked against the server's again
        and the node's own port is picked anew. False for a profile the panel didn't offer."""
        choice = next((p for p in self.profiles if p.uuid == uuid), None)
        if choice is None:
            return False
        f = self._facts()
        self.profile_uuid = uuid
        self.profile_why = ""
        self.conflicts = node.port_conflicts(f, choice.ports, self._ignore)
        try:
            self.node_port = node.pick_node_port(f, choice.ports, self._ignore, self.ssh_port)
        except RemoteError as e:
            self.conflicts.append(e.message)
        return True

    def rename(self, name: str) -> str | None:
        """Why the panel would refuse ``name``, or None — and then it is the node's name."""
        name = " ".join(name.split())
        problem = node.name_problem(name, self.node_names)
        if problem is None:
            self.name = name
            self.name_auto = False
        return problem

    def set_country(self, code: str) -> None:
        self.country = code.upper() if known(code) else "XX"
        if self.name_auto:
            self.name = node.suggest_name(self.country, self.node_names)

    # ---- the verdict ---------------------------------------------------------------------------
    @property
    def problems(self) -> list[str]:
        """Everything that stops ✅ (each a sentence for the admin)."""
        out = list(self.blockers) + list(self.conflicts)
        if self.profile is None and not self.blockers:
            out.append("یه Config Profile با اینباند انتخاب کن")
        return out

    @property
    def ready(self) -> bool:
        return not self.problems

    def plan(self, panel_host: str) -> node.NodePlan:
        p = self.profile
        assert p is not None, "a draft without a profile has problems"
        return node.NodePlan(
            panel_host=panel_host,
            name=self.name,
            address=self.address,
            country=self.country,
            profile_uuid=p.uuid,
            profile_name=p.name,
            port=self.node_port,
            replace=bool(self.existing),
        )
