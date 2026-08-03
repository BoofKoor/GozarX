"""The site's location list must be EXACTLY the configured squad's, and it must be LIVE.

Regressions locked here, all reported from production ("the site still doesn't read the assigned
squad, it can list other squads' hosts, and it isn't up to date"):

1. name mismatch — the allowlist held RAW host remarks while the subscription map is keyed by the
   RENDERED remark on the link. A host remark carrying a "{{...}}" token therefore never matched,
   the intersection came out empty, and because empty used to mean "keep everything" every host
   leaked through.
2. stale by construction — the picker read a stored snapshot that only an admin button rewrote, so
   a host added/renamed/removed in Remnawave stayed invisible indefinitely.
3. silent substitution — picking a location the squad no longer served delivered the FIRST link in
   the map instead: a config for a different country, looking exactly like success.
"""

from __future__ import annotations

import json

import fakeredis.aioredis
import pytest

from gozar.cache.redis import site_squad_locations_key
from gozar.db.models.site_device import SiteDevice
from gozar.db.repositories.site_claim import SiteClaimRepository
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.remnawave.errors import RemnawaveError
from gozar.remnawave.links import normalize_remark
from gozar.remnawave.schemas import Host, HostInbound, InternalSquad, SquadInbound
from gozar.services.settings_service import SettingsService, SiteSettingKey
from gozar.services.site_trial import LocationUnavailable, SiteTrialService

SETTINGS_KEY = "cache:settings"
_BASE = {
    SiteSettingKey.SITE_TRIAL_SQUAD: "sq-site",
    SiteSettingKey.SITE_LOCATIONS: "",
    SiteSettingKey.SITE_TRIAL_HOURS: "24",
}


class _Panel:
    """Panel stub whose squad derivation and subscription map can disagree — the real-world case."""

    def __init__(self, squad: list[str] | None = None, error: Exception | None = None) -> None:
        self._squad = squad or []
        self._error = error
        self.calls = 0

    async def squad_location_names(self, squad_uuid):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return list(self._squad)


async def _svc(session, panel, **overrides) -> SiteTrialService:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(SETTINGS_KEY, json.dumps({**_BASE, **overrides}))
    return SiteTrialService(
        panel,
        SettingsService(session, redis),
        SiteClaimRepository(session),
        SiteRewardRepository(session),
        redis,
    )


# --- 1. name normalisation ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("host_remark", "link_remark"),
    [
        ("آلمان {{TRAFFIC_USED}}", "آلمان"),  # template token rendered away
        ("Germany  {{DAYS_LEFT}} ", "Germany"),  # token + stray spacing
        ("آلمان", "آلمان "),  # trailing space only
        ("Germany", "GERMANY"),  # case
    ],
)
def test_normalize_remark_joins_the_two_spellings(host_remark: str, link_remark: str) -> None:
    assert normalize_remark(host_remark) == normalize_remark(link_remark)


def test_normalize_remark_keeps_distinct_locations_distinct() -> None:
    assert normalize_remark("Germany") != normalize_remark("Ukraine")
    assert normalize_remark("آلمان") != normalize_remark("ترکیه")


async def test_templated_host_remark_still_filters_correctly(session) -> None:
    """The exact production shape: the squad reports a templated remark, the link carries the
    rendered one. Pre-fix the intersection was empty -> fail-open -> every host shown."""
    panel = _Panel(squad=["آلمان {{TRAFFIC_USED}}"])
    svc = await _svc(session, panel)
    links = {"آلمان": "vless://de#de", "ترکیه": "vless://tr#tr"}

    assert await svc._filter_locations(links) == {"آلمان": "vless://de#de"}


# --- 2. liveness --------------------------------------------------------------------------------


async def test_squad_locations_are_cached_then_reused(session) -> None:
    """Live, but not one panel round-trip per pageview."""
    panel = _Panel(squad=["Germany"])
    svc = await _svc(session, panel)

    assert await svc.squad_locations() == ["Germany"]
    assert await svc.squad_locations() == ["Germany"]
    assert panel.calls == 1  # second read served from the 60s cache


async def test_panel_outage_falls_back_to_last_good_not_empty(session) -> None:
    """A blip must not empty the picker: the newest successful derivation stands in."""
    panel = _Panel(squad=["Germany", "Ukraine"])
    svc = await _svc(session, panel)
    assert await svc.squad_locations() == ["Germany", "Ukraine"]

    # Expire the short-lived cache, then break the panel.
    squad = await svc._settings.get(SiteSettingKey.SITE_TRIAL_SQUAD)
    await svc._redis.delete(site_squad_locations_key(squad))
    svc._panel = _Panel(error=RemnawaveError("down"))

    assert await svc.squad_locations() == ["Germany", "Ukraine"]


async def test_unknown_squad_is_none_not_empty(session) -> None:
    """None ('we don't know') and [] ('nothing') are different answers — conflating them is what
    turned an empty allowlist into 'keep every host'."""
    svc = await _svc(session, _Panel(squad=["Germany"]), **{SiteSettingKey.SITE_TRIAL_SQUAD: ""})
    assert await svc.squad_locations() is None


# --- 3. empty means empty, unknown means keep-all -------------------------------------------------


async def test_unknown_allowlist_keeps_every_link(session) -> None:
    """Panel unreachable and nothing stored: don't punish the user for our outage."""
    svc = await _svc(session, _Panel(error=RemnawaveError("down")))
    links = {"Germany": "a", "Ukraine": "b"}
    assert await svc._filter_locations(links) == links


async def test_squad_serving_nothing_filters_everything(session) -> None:
    """A real [] from the panel is a verdict, not a licence to show every host."""
    svc = await _svc(session, _Panel(squad=[]))
    assert await svc._filter_locations({"Germany": "a", "Ukraine": "b"}) == {}


# --- 4. never substitute a different country ------------------------------------------------------


def test_pick_matches_exactly_then_normalised_then_gives_up() -> None:
    links = {"آلمان": "vless://de#de", "Ukraine": "vless://ua#ua"}

    assert SiteTrialService._pick(links, "آلمان") == ("آلمان", "vless://de#de")
    # the picker offered the templated spelling; the link map has the rendered one
    assert SiteTrialService._pick(links, "آلمان {{TRAFFIC_USED}}") == ("آلمان", "vless://de#de")
    # NOT in the map -> None. Pre-fix this returned the first entry, i.e. a different country.
    assert SiteTrialService._pick(links, "Turkey") is None


def test_pick_never_returns_an_arbitrary_first_entry() -> None:
    """Guards the specific old line `return next(iter(links.items()))`."""
    links = {"Germany": "vless://de#de", "Ukraine": "vless://ua#ua"}
    for missing in ("Turkey", "", "Germanyy", "🇩🇪"):
        assert SiteTrialService._pick(links, missing) is None


async def test_claim_reports_available_names_when_the_pick_is_gone(session) -> None:
    panel = _Panel(squad=["Germany"])
    svc = await _svc(session, panel)
    device = SiteDevice(uuid="dev-loc-1")
    session.add(device)
    await session.flush()

    result = await svc._deliver(
        device, {"Germany": "vless://de#de"}, None, "Ukraine", changed=False
    )
    assert isinstance(result, LocationUnavailable)
    assert result.available == ["Germany"]


# --- 5. panel-side scoping ------------------------------------------------------------------------


def _host(remark: str, inbound: str, *, disabled: bool = False, hidden: bool = False) -> Host:
    return Host(
        uuid=f"h-{remark}",
        remark=remark,
        isDisabled=disabled,
        isHidden=hidden,
        inbound=HostInbound(configProfileInboundUuid=inbound),
    )


def test_host_schema_reads_is_hidden_and_defaults_false() -> None:
    assert _host("x", "i", hidden=True).is_hidden is True
    # A panel build that never sends the field must behave exactly as before.
    assert Host.model_validate({"uuid": "u", "remark": "x"}).is_hidden is False


async def test_squad_derivation_excludes_hidden_and_foreign_hosts() -> None:
    """A hidden host is absent from the subscription, so offering it can only produce a dead pick;
    a host on another squad's inbound must never appear at all."""
    from gozar.remnawave.client import RemnawaveClient

    squad = InternalSquad(uuid="sq-1", name="trial", inbounds=[SquadInbound(uuid="in-1")])
    hosts = [
        _host("Germany", "in-1"),
        _host("Hidden-DE", "in-1", hidden=True),
        _host("Disabled-DE", "in-1", disabled=True),
        _host("OtherSquad", "in-2"),  # different inbound entirely
    ]

    client = RemnawaveClient.__new__(RemnawaveClient)

    async def _squads():
        return [squad]

    async def _hosts():
        return hosts

    client.list_internal_squads = _squads  # type: ignore[method-assign]
    client.list_hosts = _hosts  # type: ignore[method-assign]

    assert await RemnawaveClient.squad_location_names(client, "sq-1") == ["Germany"]
