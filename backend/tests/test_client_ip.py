"""The per-IP guards must key off an address the caller cannot choose.

Regression for a rate-limit bypass: uvicorn runs with ``--proxy-headers --forwarded-allow-ips '*'``
and resolves ``request.client.host`` from the LEFTMOST ``X-Forwarded-For`` entry, while nginx
*appended* to whatever chain arrived. Sending ``X-Forwarded-For: <anything>`` therefore let a caller
pick their own identity for every per-IP guard — the /claim (40/min) and push-subscribe (60/h)
backstops fell to a rotating header, and ``ip_bucket`` (the shared-IP abuse signal) could be
scattered so no two requests ever grouped together.

``client_ip`` now reads ``CF-Connecting-IP``, which Cloudflare sets and overwrites on proxied
traffic, and nginx overwrites ``X-Forwarded-For`` with ``$remote_addr`` so a caller-supplied chain
never reaches uvicorn at all.
"""

from __future__ import annotations

from starlette.datastructures import Headers

from gozar.web.routes.public.identity import client_ip, ip_bucket


class _Client:
    def __init__(self, host: str) -> None:
        self.host = host


class _Request:
    """Just the surface client_ip touches: headers + the connection peer."""

    def __init__(self, headers: dict[str, str], peer: str | None = "10.0.0.9") -> None:
        self.headers = Headers(headers)
        self.client = _Client(peer) if peer else None


def test_prefers_the_cloudflare_header() -> None:
    assert client_ip(_Request({"cf-connecting-ip": "203.0.113.7"})) == "203.0.113.7"


def test_header_lookup_is_case_insensitive() -> None:
    assert client_ip(_Request({"CF-Connecting-IP": "203.0.113.7"})) == "203.0.113.7"


def test_falls_back_to_the_peer_without_the_header() -> None:
    assert client_ip(_Request({})) == "10.0.0.9"


def test_a_forged_x_forwarded_for_is_ignored() -> None:
    """The old bypass: XFF is never consulted, so it cannot become the rate-limit key."""
    req = _Request({"x-forwarded-for": "1.2.3.4, 5.6.7.8"}, peer="10.0.0.9")
    assert client_ip(req) == "10.0.0.9"


def test_junk_cf_header_falls_back_instead_of_becoming_a_key() -> None:
    """A non-IP value must not survive as its own bucket — that would restore the bypass."""
    for junk in ("not-an-ip", "", "   ", "203.0.113.7, 5.6.7.8", "<script>"):
        assert client_ip(_Request({"cf-connecting-ip": junk})) == "10.0.0.9"


def test_no_peer_and_no_header_is_a_stable_placeholder() -> None:
    assert client_ip(_Request({}, peer=None)) == "0.0.0.0"


def test_ip_bucket_groups_by_network_and_follows_the_trusted_header() -> None:
    secret = "s"
    # Same /24 → same bucket (grouping, not tracking).
    a = ip_bucket(_Request({"cf-connecting-ip": "203.0.113.7"}), secret)
    b = ip_bucket(_Request({"cf-connecting-ip": "203.0.113.200"}), secret)
    assert a == b
    # Different network → different bucket.
    c = ip_bucket(_Request({"cf-connecting-ip": "198.51.100.7"}), secret)
    assert c != a
    # A forged XFF cannot move a caller between buckets any more.
    forged = ip_bucket(
        _Request({"cf-connecting-ip": "203.0.113.7", "x-forwarded-for": "198.51.100.7"}), secret
    )
    assert forged == a
