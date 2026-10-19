"""The panel's management API, for the console's operations: nodes and config profiles — what
installing a node needs (the locations' inbounds, squads and hosts come with them).

Separate from ``RemnawaveClient`` (the users' side) because an operation wants different answers:
not "the call failed" but WHY, in words the admin can act on — a missing scope named, a Cloudflare
page told apart from the panel, "a node with that name exists" (``PanelError.code``). Same shared
``httpx.AsyncClient``, TLS verification on, one bounded attempt per call (a wait for a node to
connect is a bounded poll, never a retry loop).

VERIFY: every endpoint below is from the Remnawave backend contract at tag 3.4.4 (``libs/contract``,
identical in 3.4.5) and was exercised by tunnelbot against a real 3.4.4 panel:
  * every endpoint is under /api and answers {"response": …}; auth "Authorization: Bearer <token>";
  * the proxy-check middleware drops the socket of a request without X-Forwarded-For AND
    "X-Forwarded-Proto: https" — a reverse proxy adds them; a direct http:// URL needs us to;
  * scopes (ScopesGuard): "*", "<resource>:*", "<resource>:read|write"; the guards run BEFORE
    validation, so an empty body answers 403 without the scope and 400 with it — how a scope is
    checked without changing anything;
  * nodes.name and nodes.address are UNIQUE (errorCode A033 / A034);
  * the scope each endpoint needs is the panel's own (GET /api/tokens/scopes): nodes:read|write,
    config-profiles:read, keygen:read.
2.x is not driven by these operations (the console says so): the bot's users' side keeps
supporting both majors through ``RemnawaveClient``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from gozar.ops.errors import RemoteError

logger = logging.getLogger("gozar.remnawave.ops")

#: What installing a node needs.
NODE_SCOPES = ("nodes:read", "nodes:write", "config-profiles:read", "keygen:read")
#: How each scope is asked without changing anything (a GET, or a write with an empty body).
SCOPE_PROBES = {
    "nodes:read": ("GET", "/api/nodes"),
    "nodes:write": ("POST", "/api/nodes"),
    "config-profiles:read": ("GET", "/api/config-profiles"),
    "keygen:read": ("GET", "/api/keygen"),
}

_TOKEN_HINT = (
    "در داشبورد پنل (Remnawave Settings ← API Tokens) توکنی با این دسترسی‌ها بساز، جای "
    "PANEL_API_TOKEN در فایل .env بگذار و ربات را ری‌استارت کن"
)


class PanelError(RemoteError):
    """``code``: network | proxyheaders | tls | blocked | auth | scope | notfound | name_taken |
    address_taken | bad | http."""

    def __init__(
        self, message: str, detail: str = "", code: str | None = None, status: int | None = None
    ) -> None:
        super().__init__(message, detail, code)
        self.status = status


@dataclass
class Inbound:
    uuid: str
    tag: str
    type: str = ""
    network: str | None = None
    security: str | None = None
    port: int | None = None
    raw: dict = field(default_factory=dict)

    def protocols(self) -> set[str]:
        """The transport protocols Xray binds for this inbound (port-conflict checks)."""
        net = (self.network or "").lower()
        typ = (self.type or "").lower()
        settings_net = str((self.raw.get("settings") or {}).get("network", "")).lower()
        if net in ("kcp", "mkcp", "quic", "hysteria", "hysteria2") or typ in (
            "wireguard",
            "hysteria",
            "hysteria2",
        ):
            return {"udp"}
        out = {"tcp"}
        if "udp" in settings_net:  # shadowsocks / dokodemo "tcp,udp"
            out.add("udp")
        if net == "xhttp" and "h3" in json.dumps(self.raw.get("streamSettings") or {}).lower():
            out.add("udp")
        return out


@dataclass
class Profile:
    uuid: str
    name: str
    inbounds: list[Inbound]
    node_names: list[str]

    def ports(self) -> list[tuple[int, str]]:
        seen: list[tuple[int, str]] = []
        for ib in self.inbounds:
            if ib.port:
                for proto in sorted(ib.protocols()):
                    if (ib.port, proto) not in seen:
                        seen.append((ib.port, proto))
        return seen


@dataclass
class NodeInfo:
    uuid: str
    name: str
    address: str
    port: int | None
    is_connected: bool = False
    is_connecting: bool = False
    is_disabled: bool = False
    last_status: str | None = None
    country: str = ""
    xray_version: str | None = None
    node_version: str | None = None
    users_online: int | None = None
    profile_uuid: str | None = None
    xray_uptime: int | None = None
    active_inbounds: list = field(default_factory=list)  # inbound uuids of the profile it runs

    @classmethod
    def from_api(cls, d: dict) -> NodeInfo:
        v = d.get("versions") or {}
        cp = d.get("configProfile") or {}
        return cls(
            uuid=d.get("uuid", ""),
            name=d.get("name", ""),
            address=d.get("address", ""),
            port=d.get("port"),
            is_connected=bool(d.get("isConnected")),
            is_connecting=bool(d.get("isConnecting")),
            is_disabled=bool(d.get("isDisabled")),
            last_status=d.get("lastStatusMessage"),
            country=d.get("countryCode") or "",
            xray_version=v.get("xray"),
            node_version=v.get("node"),
            users_online=d.get("usersOnline"),
            profile_uuid=cp.get("activeConfigProfileUuid"),
            xray_uptime=d.get("xrayUptime"),
            active_inbounds=[
                i.get("uuid") for i in cp.get("activeInbounds") or [] if isinstance(i, dict)
            ],
        )


def _api_message(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    msg = body.get("message")
    if isinstance(msg, list):
        msg = "; ".join(map(str, msg))
    errs = body.get("errors")
    if isinstance(errs, list) and errs:
        details = []
        for e in errs[:4]:
            if isinstance(e, dict):
                path = ".".join(map(str, e.get("path") or []))
                text = str(e.get("message", ""))
                details.append(f"{path}: {text}" if path else text)
        if details:
            msg = f"{msg or ''} ({'; '.join(details)})"
    return str(msg or "")


def _profile(p: dict) -> Profile:
    ibs = [
        Inbound(
            uuid=i["uuid"],
            tag=i.get("tag", ""),
            type=i.get("type") or "",
            network=i.get("network"),
            security=i.get("security"),
            port=i.get("port"),
            raw=i.get("rawInbound") or {},
        )
        for i in p.get("inbounds", [])
    ]
    return Profile(
        uuid=p["uuid"],
        name=p.get("name", ""),
        inbounds=ibs,
        node_names=[n.get("name", "") for n in p.get("nodes", [])],
    )


class OpsPanel:
    """The panel, for operations. ``name`` is how the admin knows it ("پنل")."""

    def __init__(
        self, http: httpx.AsyncClient, base_url: str, token: str, *, timeout: float = 20.0
    ) -> None:
        self._http = http
        self.base = base_url.rstrip("/")
        self._token = token
        self.timeout = timeout

    @property
    def host(self) -> str:
        return httpx.URL(self.base).host if self.base else ""

    def _headers(self) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "User-Agent": "gozar",
        }
        if self.base.startswith("http://"):  # straight to the panel's port: no proxy adds these
            h["X-Forwarded-For"] = "127.0.0.1"
            h["X-Forwarded-Proto"] = "https"
        return h

    def _err(
        self, msg: str, detail: str = "", code: str = "http", status: int | None = None
    ) -> PanelError:
        return PanelError(f"پنل: {msg}", detail, code=code, status=status)

    async def request(self, method: str, path: str, body: Any = None) -> Any:
        """The ``response`` field. Raises ``PanelError`` with a message the admin can act on."""
        if not self.base:
            raise self._err("آدرس پنل (PANEL_BASE_URL) تنظیم نشده", code="bad")
        try:
            r = await self._http.request(
                method, self.base + path, json=body, headers=self._headers(), timeout=self.timeout
            )
        except httpx.RemoteProtocolError as e:
            raise self._err(
                "اتصال را بی‌جواب بست. اگر آدرس مستقیم به پورت پنل است (مثل :3000) باید"
                " با http:// باشد؛ اگر پشت nginx/caddy است، آن باید X-Forwarded-For و"
                " X-Forwarded-Proto بفرستد",
                type(e).__name__,
                "proxyheaders",
            ) from e
        except httpx.ConnectError as e:
            if "CERTIFICATE" in str(e).upper() or "SSL" in str(e).upper():
                raise self._err("گواهی TLS پنل معتبر نیست", type(e).__name__, "tls") from e
            raise self._err(f"به {self.host} وصل نشد", type(e).__name__, "network") from e
        except httpx.TimeoutException as e:
            raise self._err(
                f"جواب نداد (بیشتر از {int(self.timeout)} ثانیه)", type(e).__name__, "network"
            ) from e
        except httpx.HTTPError as e:
            raise self._err(f"خطای شبکه: {type(e).__name__}", "", "network") from e
        logger.info("panel %s %s -> %s", method, path, r.status_code)
        return self._parse(method, path, r)

    def _parse(self, method: str, path: str, r: httpx.Response) -> Any:
        status, text = r.status_code, r.text
        body: Any = None
        if text.strip():
            try:
                body = json.loads(text)
            except ValueError:
                body = None
        if 200 <= status < 300:
            if status == 204 or not text.strip():
                return None
            if not isinstance(body, dict) or "response" not in body:
                raise self._err(
                    "جوابش JSON پنل نیست (احتمالاً صفحهٔ دیگری یا محافظی جلوی پنل است)",
                    "",
                    "bad",
                    status,
                )
            return body["response"]
        api_msg = _api_message(body)
        if body is None and status in (401, 403, 429, 503):  # a CDN / WAF page, not the panel
            raise self._err(
                f"یک فایروال یا Cloudflare جلوی پنل درخواست ربات را رد کرد ({status}؛ جواب"
                " HTML بود، نه از پنل). اگر Bot Fight Mode یا قانون WAF داری، برای آی‌پی سرور"
                " ربات استثنا بگذار",
                "",
                "blocked",
                status,
            )
        if status == 401:
            raise self._err(
                "توکن API رد شد (اشتباه، حذف‌شده یا منقضی). " + _TOKEN_HINT, api_msg, "auth", status
            )
        if status == 403:
            raise self._err(
                f"توکن API اجازهٔ این کار را ندارد ({method} {path}). " + _TOKEN_HINT,
                api_msg,
                "scope",
                status,
            )
        if status == 404 and body is None:
            raise self._err("مسیر API پیدا نشد (404). آدرس پنل درست است؟", "", "notfound", status)
        if isinstance(body, dict):
            code = body.get("errorCode")
            if code == "A033":
                raise self._err("نودی با همین نام در پنل هست", api_msg, "name_taken", status)
            if code == "A034":
                raise self._err("نودی با همین آدرس در پنل هست", api_msg, "address_taken", status)
        raise self._err(f"خطای {status}: {api_msg or '—'}", api_msg, "http", status)

    # ---- nodes ---------------------------------------------------------------------------------
    async def profiles(self) -> list[Profile]:
        r = await self.request("GET", "/api/config-profiles")
        return [_profile(p) for p in (r or {}).get("configProfiles", [])]

    async def nodes(self) -> list[NodeInfo]:
        r = await self.request("GET", "/api/nodes")
        return [NodeInfo.from_api(n) for n in (r or [])]

    async def node(self, uuid: str) -> NodeInfo:
        return NodeInfo.from_api(await self.request("GET", f"/api/nodes/{uuid}"))

    async def keygen(self) -> str:
        """The node's SECRET_KEY: base64 JSON with a private key in it — a secret."""
        r = await self.request("GET", "/api/keygen")
        key = (r or {}).get("secretKey") or ""
        if not key:
            raise self._err("پنل SECRET_KEY نداد (GET /api/keygen)", code="bad")
        return key

    async def create_node(
        self, *, name: str, address: str, port: int, country: str, profile: Profile
    ) -> NodeInfo:
        body = {
            "name": name,
            "address": address,
            "port": port,
            "countryCode": (country or "XX")[:2].upper(),
            "configProfile": {
                "activeConfigProfileUuid": profile.uuid,
                "activeInbounds": [i.uuid for i in profile.inbounds],
            },
        }
        return NodeInfo.from_api(await self.request("POST", "/api/nodes", body))

    async def delete_node(self, uuid: str) -> bool:
        """True when the node is gone (deleted now or already missing)."""
        try:
            await self.request("DELETE", f"/api/nodes/{uuid}")
        except PanelError as e:
            if e.status == 404:
                return True
            raise
        return True

    # ---- what the token may do -----------------------------------------------------------------
    async def can_write(self, path: str, method: str) -> None:
        """Raises ``PanelError(code=scope)`` when the token may not; changes nothing (an empty
        body fails validation, which runs only after the scope guard)."""
        try:
            await self.request(method, path, {})
        except PanelError as e:
            if e.status == 400 and e.code == "http":
                return
            raise
        raise self._err(
            f"{method} {path} با بدنهٔ خالی قبول شد! (نسخهٔ پنل ناشناخته است)", code="bad"
        )

    async def check_access(self) -> tuple[list[Profile], list[NodeInfo]]:
        """Everything installing a node needs, checked before touching any server."""
        profiles = await self.profiles()
        nodes = await self.nodes()
        await self.keygen()
        await self.can_write("/api/nodes", "POST")
        return profiles, nodes

    async def scopes_missing(self, scopes: tuple[str, ...] | None = None) -> list[str]:
        """The scopes this token lacks, asked without changing anything."""
        missing = []
        for scope in scopes or tuple(SCOPE_PROBES):
            method, path = SCOPE_PROBES[scope]
            try:
                await self.request(method, path, None if method == "GET" else {})
            except PanelError as e:
                if e.code == "scope":
                    missing.append(scope)
                    continue
                if method != "GET" and e.status == 400 and e.code == "http":
                    continue
                raise
            if method != "GET":
                raise self._err(f"{method} {path} با بدنهٔ خالی قبول شد!", code="bad")
        return missing
