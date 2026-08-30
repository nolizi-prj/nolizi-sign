"""Tests for app.mailer.send: Graph request shape, retry/backoff, and fast-fail paths.

Two independent seams are used (see mailer.py's module docstring):
``app.mailer._acquire_token`` is monkeypatched to skip real MSAL/network
auth, and ``transport=httpx.MockTransport(...)`` mocks the actual Graph
``sendMail`` call. ``sleep`` is injected as a plain list-appending callable
so retry tests run instantly instead of waiting 1s/4s/16s for real.
"""

import base64
import json

import httpx
import pytest

from app import mailer
from app.config import Settings


def _settings() -> Settings:
    return Settings(
        ms_tenant_id="tenant-id",
        ms_client_id="client-id",
        ms_client_secret="client-secret",
        mail_sender="sender@pumasi.ai",
    )


def test_send_success_builds_expected_graph_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mailer, "_acquire_token", lambda settings: "test-token")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(202)

    ok = mailer.send(
        _settings(),
        ["a@example.com", "b@example.com"],
        "Subject line",
        "<p>hi</p>",
        [("doc.pdf", b"%PDF-1.4 fake pdf bytes", "application/pdf")],
        transport=httpx.MockTransport(handler),
    )

    assert ok is True
    assert captured["url"] == "https://graph.microsoft.com/v1.0/users/sender@pumasi.ai/sendMail"
    assert captured["authorization"] == "Bearer test-token"

    body = captured["body"]
    assert body["saveToSentItems"] is True
    message = body["message"]
    assert message["subject"] == "Subject line"
    assert message["body"] == {"contentType": "HTML", "content": "<p>hi</p>"}
    assert message["toRecipients"] == [
        {"emailAddress": {"address": "a@example.com"}},
        {"emailAddress": {"address": "b@example.com"}},
    ]
    attachment = message["attachments"][0]
    assert attachment["@odata.type"] == "#microsoft.graph.fileAttachment"
    assert attachment["name"] == "doc.pdf"
    assert attachment["contentType"] == "application/pdf"
    assert base64.b64decode(attachment["contentBytes"]) == b"%PDF-1.4 fake pdf bytes"


def test_send_without_attachments_omits_attachments_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mailer, "_acquire_token", lambda settings: "test-token")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(202)

    mailer.send(_settings(), ["a@example.com"], "s", "<p></p>", transport=httpx.MockTransport(handler))

    assert "attachments" not in captured["body"]["message"]


def test_send_attachment_content_type_lands_in_graph_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mailer, "_acquire_token", lambda settings: "test-token")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(202)

    mailer.send(
        _settings(),
        ["a@example.com"],
        "s",
        "<p></p>",
        [("screenshot.png", b"\x89PNG fake image bytes", "image/png")],
        transport=httpx.MockTransport(handler),
    )

    attachment = captured["body"]["message"]["attachments"][0]
    assert attachment["name"] == "screenshot.png"
    assert attachment["contentType"] == "image/png"


def test_send_retries_on_500_three_times_then_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mailer, "_acquire_token", lambda settings: "test-token")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500)

    sleeps: list[float] = []
    ok = mailer.send(
        _settings(),
        ["a@example.com"],
        "s",
        "<p></p>",
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )

    assert ok is False
    assert calls["n"] == 4  # 1 initial attempt + 3 retries
    assert sleeps == [1.0, 4.0, 16.0]


def test_send_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mailer, "_acquire_token", lambda settings: "test-token")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429)
        return httpx.Response(202)

    sleeps: list[float] = []
    ok = mailer.send(
        _settings(),
        ["a@example.com"],
        "s",
        "<p></p>",
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )

    assert ok is True
    assert calls["n"] == 3
    assert sleeps == [1.0, 4.0]


def test_send_retries_on_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mailer, "_acquire_token", lambda settings: "test-token")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(202)

    sleeps: list[float] = []
    ok = mailer.send(
        _settings(),
        ["a@example.com"],
        "s",
        "<p></p>",
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )

    assert ok is True
    assert calls["n"] == 2
    assert sleeps == [1.0]


def test_send_non_retryable_4xx_fails_immediately_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mailer, "_acquire_token", lambda settings: "test-token")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    sleeps: list[float] = []
    ok = mailer.send(
        _settings(),
        ["a@example.com"],
        "s",
        "<p></p>",
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )

    assert ok is False
    assert calls["n"] == 1
    assert sleeps == []


def test_send_returns_false_without_any_network_call_when_not_configured() -> None:
    # No transport/acquire_token stub is provided — if this attempted a real
    # call it would raise (MockTransport isn't set, real httpx.Client would
    # try actual network I/O) rather than just returning False quietly.
    ok = mailer.send(Settings(), ["a@example.com"], "s", "<p></p>")
    assert ok is False


def test_send_returns_false_when_token_acquisition_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mailer, "_acquire_token", lambda settings: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(202)

    ok = mailer.send(_settings(), ["a@example.com"], "s", "<p></p>", transport=httpx.MockTransport(handler))

    assert ok is False
    assert calls["n"] == 0


def test_send_returns_false_with_no_recipients(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mailer, "_acquire_token", lambda settings: "test-token")
    ok = mailer.send(_settings(), [], "s", "<p></p>")
    assert ok is False
