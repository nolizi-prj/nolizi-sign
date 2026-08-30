"""Tests for POST /api/feedback: validation, rate limiting, mail delegation.

The endpoint is unauthenticated by design (the button renders on every
page, including login). ``mailer.send`` is monkeypatched at the module
attribute, which the router shares via ``from app import mailer``.
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app import mailer
from app.config import Settings
from app.routers import feedback

PNG_BYTES = b"\x89PNG\r\n\x1a\n fake image content"


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> None:
    feedback._recent_by_ip.clear()


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Capture mailer.send calls; every send reports success."""
    calls: list[dict] = []

    def fake_send(settings, to, subject, html_body, attachments=None, **kwargs):
        calls.append({"to": to, "subject": subject, "body": html_body, "attachments": attachments})
        return True

    monkeypatch.setattr(mailer, "send", fake_send)
    return calls


@pytest.fixture
def feedback_client(make_client: Callable[[Settings | None], TestClient]) -> TestClient:
    return make_client(Settings(feedback_email="legal@pumasi.ai"))


def test_message_only_sends_email_and_returns_204(feedback_client: TestClient, sent: list[dict]) -> None:
    response = feedback_client.post("/api/feedback", data={"message": "Love the app!\n<3"})

    assert response.status_code == 204
    assert len(sent) == 1
    assert sent[0]["to"] == ["legal@pumasi.ai"]
    assert sent[0]["subject"] == "Pumasi Sign feedback"
    # HTML-escaped, newline becomes <br>, nothing else in the body
    assert sent[0]["body"] == "<p>Love the app!<br>&lt;3</p>"
    assert sent[0]["attachments"] == []


def test_context_is_rendered_escaped_after_the_message(feedback_client: TestClient, sent: list[dict]) -> None:
    response = feedback_client.post(
        "/api/feedback",
        data={
            "message": "Broken here",
            "context": '{"Page": "/envelopes/12", "User": "Jo <jo@pumasi.ai>", "Viewport": "1440x900"}',
        },
    )

    assert response.status_code == 204
    body = sent[0]["body"]
    assert body.startswith("<p>Broken here</p>")
    assert "Page" in body
    assert "/envelopes/12" in body
    # User-controlled values are HTML-escaped.
    assert "Jo &lt;jo@pumasi.ai&gt;" in body
    assert "<jo@pumasi.ai>" not in body
    assert "1440x900" in body


def test_invalid_context_json_returns_400(feedback_client: TestClient, sent: list[dict]) -> None:
    response = feedback_client.post(
        "/api/feedback",
        data={"message": "hi", "context": "not json"},
    )

    assert response.status_code == 400
    assert sent == []


def test_non_string_context_values_return_400(feedback_client: TestClient, sent: list[dict]) -> None:
    response = feedback_client.post(
        "/api/feedback",
        data={"message": "hi", "context": '{"Page": ["a", "b"]}'},
    )

    assert response.status_code == 400
    assert sent == []


def test_oversized_context_returns_400(feedback_client: TestClient, sent: list[dict]) -> None:
    response = feedback_client.post(
        "/api/feedback",
        data={"message": "hi", "context": '{"Page": "' + "x" * 5000 + '"}'},
    )

    assert response.status_code == 400
    assert sent == []


def test_screenshot_is_attached_with_its_content_type(feedback_client: TestClient, sent: list[dict]) -> None:
    response = feedback_client.post(
        "/api/feedback",
        data={"message": "See attached"},
        files={"screenshot": ("shot.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 204
    assert sent[0]["attachments"] == [("screenshot.png", PNG_BYTES, "image/png")]


def test_empty_message_returns_400(feedback_client: TestClient, sent: list[dict]) -> None:
    response = feedback_client.post("/api/feedback", data={"message": "   "})
    assert response.status_code == 400
    assert sent == []


def test_too_long_message_returns_400(feedback_client: TestClient, sent: list[dict]) -> None:
    response = feedback_client.post("/api/feedback", data={"message": "x" * 5001})
    assert response.status_code == 400
    assert sent == []


def test_wrong_screenshot_type_returns_415(feedback_client: TestClient, sent: list[dict]) -> None:
    response = feedback_client.post(
        "/api/feedback",
        data={"message": "hi"},
        files={"screenshot": ("evil.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 415
    assert sent == []


def test_oversized_screenshot_returns_413(feedback_client: TestClient, sent: list[dict]) -> None:
    big = b"x" * (3 * 1024 * 1024 + 1)
    response = feedback_client.post(
        "/api/feedback",
        data={"message": "hi"},
        files={"screenshot": ("big.png", big, "image/png")},
    )
    assert response.status_code == 413
    assert sent == []


def test_sixth_submission_within_window_returns_429(feedback_client: TestClient, sent: list[dict]) -> None:
    for _ in range(5):
        assert feedback_client.post("/api/feedback", data={"message": "hi"}).status_code == 204

    response = feedback_client.post("/api/feedback", data={"message": "hi"})

    assert response.status_code == 429
    assert len(sent) == 5


def test_mailer_failure_returns_503(feedback_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mailer, "send", lambda *args, **kwargs: False)
    response = feedback_client.post("/api/feedback", data={"message": "hi"})
    assert response.status_code == 503


def test_spoofed_leftmost_xff_does_not_get_a_fresh_rate_limit_bucket(
    feedback_client: TestClient,
    sent: list[dict],
) -> None:
    """Regression for keying the rate limit on the spoofable ``X-Forwarded-For``
    entry (see app.http_utils.client_ip).

    Under TestClient there's no real reverse proxy in front, so:
    - Unheaded requests fall back to ``request.client.host``, which is the
      fixed ``("testclient", 50000)`` TestClient uses for every request made
      through the same instance — that's the "trusted last-hop" stand-in for
      the 5 baseline submissions below.
    - In production (Dockerfile runs uvicorn with ``--proxy-headers
      --forwarded-allow-ips '*'``), that same middleware rewrites
      ``request.client.host`` to the *left-most* ``X-Forwarded-For`` entry —
      attacker-controlled — which is exactly finding 1's bug: keying on
      ``request.client.host`` lets an attacker mint a fresh bucket per
      request just by sending their own header.

    So this test simulates that rewritten ``request.client`` (a second
    ``TestClient`` wrapping the same app with ``client=`` set to the spoofed
    IP, standing in for what uvicorn's proxy-headers middleware would have
    already done) alongside the raw header the app actually reads: the
    attacker's fake left-most entry followed by the real, trusted right-most
    one (here, ``"testclient"``, matching what the unheaded baseline calls
    resolved to). ``client_ip()`` must read the header directly and take the
    right-most entry — landing in the *same* bucket as the baseline — so the
    6th submission is still rejected even though ``request.client.host`` was
    spoofed to a brand-new value.
    """
    for _ in range(5):
        assert feedback_client.post("/api/feedback", data={"message": "hi"}).status_code == 204

    spoofed_client = TestClient(feedback_client.app, client=("1.2.3.4", 12345))
    response = spoofed_client.post(
        "/api/feedback",
        data={"message": "hi"},
        headers={"X-Forwarded-For": "1.2.3.4, testclient"},
    )

    assert response.status_code == 429
    assert len(sent) == 5


def test_max_length_message_is_accepted(feedback_client: TestClient, sent: list[dict]) -> None:
    response = feedback_client.post("/api/feedback", data={"message": "x" * feedback.MAX_MESSAGE_CHARS})

    assert response.status_code == 204
    assert len(sent) == 1


def test_max_size_screenshot_is_accepted(feedback_client: TestClient, sent: list[dict]) -> None:
    at_limit = b"x" * feedback.MAX_SCREENSHOT_BYTES
    response = feedback_client.post(
        "/api/feedback",
        data={"message": "hi"},
        files={"screenshot": ("shot.png", at_limit, "image/png")},
    )

    assert response.status_code == 204
    assert sent[0]["attachments"] == [("screenshot.png", at_limit, "image/png")]


def test_rejected_requests_do_not_consume_a_rate_limit_slot(feedback_client: TestClient, sent: list[dict]) -> None:
    for _ in range(5):
        assert feedback_client.post("/api/feedback", data={"message": "   "}).status_code == 400

    response = feedback_client.post("/api/feedback", data={"message": "hi"})

    assert response.status_code == 204
    assert len(sent) == 1
