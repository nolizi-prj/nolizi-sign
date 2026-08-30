"""Tests for app.http_utils.client_ip: X-Forwarded-For parsing.

Builds a bare ``starlette.requests.Request`` directly from a minimal ASGI
scope rather than going through a full app/route — ``client_ip`` only reads
``request.headers`` and ``request.client``, so no DB/app machinery is
needed.
"""

from starlette.requests import Request

from app.http_utils import client_ip


def _request(headers: dict[str, str], client_host: str | None = "10.0.0.1") -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_host, 12345) if client_host is not None else None,
    }
    return Request(scope)


def test_client_ip_uses_rightmost_xff_entry_not_the_first() -> None:
    """Regression test: the first XFF entry is attacker-controlled (a signer
    can send their own X-Forwarded-For header); only the entry the trusted
    last-hop proxy (Railway) itself appended — the right-most one — is
    safe to trust.
    """
    request = _request({"x-forwarded-for": "203.0.113.99, 198.51.100.7"})

    assert client_ip(request) == "198.51.100.7"


def test_client_ip_single_xff_entry() -> None:
    request = _request({"x-forwarded-for": "198.51.100.7"})

    assert client_ip(request) == "198.51.100.7"


def test_client_ip_strips_whitespace_around_entries() -> None:
    request = _request({"x-forwarded-for": "203.0.113.99 ,  198.51.100.7  "})

    assert client_ip(request) == "198.51.100.7"


def test_client_ip_falls_back_to_request_client_without_xff() -> None:
    request = _request({})

    assert client_ip(request) == "10.0.0.1"


def test_client_ip_none_when_no_client_and_no_xff() -> None:
    request = _request({}, client_host=None)

    assert client_ip(request) is None
