"""In-app feedback: emails the message (+ optional screenshot and context).

Open to anyone — no auth dependency — because the feedback button renders
on every page, including login and signing pages. Abuse control is a
module-level per-IP rate limit; in-memory is sufficient because the app
runs as a single uvicorn process on Railway (restarts reset it, which is
acceptable).

The original spec kept the email to user-provided content only; per the
2026-08-05 request, the frontend now also sends a ``context`` field (page
URL, signed-in user, browser, viewport — all assembled client-side and
shown to the user as what will be included) rendered as a table after the
message. Everything is HTML-escaped; the dict shape is validated but the
keys/values are otherwise free-form, since the client controls them either
way.
"""

from __future__ import annotations

import html
import json
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile

from app import mailer
from app.auth import get_settings
from app.config import Settings
from app.http_utils import client_ip

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

MAX_MESSAGE_CHARS = 5000
MAX_CONTEXT_CHARS = 4000
MAX_CONTEXT_ENTRIES = 12
# Graph sendMail caps the whole JSON request at 4 MB; base64 inflates the
# image by ~4/3, so 3 MB of raw bytes is the safe ceiling for one attachment.
MAX_SCREENSHOT_BYTES = 3 * 1024 * 1024
ALLOWED_SCREENSHOT_TYPES = {"image/png": ".png", "image/jpeg": ".jpg"}
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW_SECONDS = 600.0

_recent_by_ip: dict[str, deque[float]] = defaultdict(deque)


def _rate_limited(ip: str, now: float) -> bool:
    """Record one submission attempt from ``ip``; True if over the limit.

    Timestamps come from ``time.monotonic()`` so wall-clock adjustments
    can't widen or shrink the window. Rejected attempts are not recorded —
    only accepted submissions count against the cap.
    """
    timestamps = _recent_by_ip[ip]
    while timestamps and now - timestamps[0] >= RATE_LIMIT_WINDOW_SECONDS:
        timestamps.popleft()
    if not timestamps:
        # Nothing left after the sweep: drop the entry instead of leaving an
        # empty deque parked in the dict forever. defaultdict recreates it
        # (empty) on the next line if this IP shows up again.
        del _recent_by_ip[ip]
        timestamps = _recent_by_ip[ip]
    if len(timestamps) >= RATE_LIMIT_MAX:
        return True
    timestamps.append(now)
    return False


def _parse_context(raw: str) -> dict[str, str]:
    """Validate the context form field: a small, flat JSON dict of strings."""
    if len(raw) > MAX_CONTEXT_CHARS:
        raise HTTPException(status_code=400, detail=f"Context must be at most {MAX_CONTEXT_CHARS} characters.")
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Context must be valid JSON.") from exc
    if (
        not isinstance(parsed, dict)
        or len(parsed) > MAX_CONTEXT_ENTRIES
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in parsed.items())
    ):
        raise HTTPException(status_code=400, detail="Context must be a small JSON object of strings.")
    return parsed


def _context_html(context: dict[str, str]) -> str:
    rows = "".join(
        f'<tr><td style="padding:2px 12px 2px 0;color:#555;white-space:nowrap">{html.escape(key)}</td>'
        f"<td>{html.escape(value)}</td></tr>"
        for key, value in context.items()
    )
    return f'<hr><p style="margin-bottom:4px"><strong>Context</strong></p><table>{rows}</table>'


@router.post("", status_code=204)
def submit_feedback(
    request: Request,
    message: str = Form(),
    screenshot: UploadFile | None = File(None),
    context: str | None = Form(None),
    settings: Settings = Depends(get_settings),
) -> Response:
    text = message.strip()
    if not text or len(text) > MAX_MESSAGE_CHARS:
        raise HTTPException(status_code=400, detail=f"Message must be 1-{MAX_MESSAGE_CHARS} characters.")

    context_dict = _parse_context(context) if context else None

    attachments: list[tuple[str, bytes, str]] = []
    if screenshot is not None:
        content_type = screenshot.content_type or ""
        if content_type not in ALLOWED_SCREENSHOT_TYPES:
            raise HTTPException(status_code=415, detail="Screenshot must be a PNG or JPEG image.")
        data = screenshot.file.read(MAX_SCREENSHOT_BYTES + 1)
        if len(data) > MAX_SCREENSHOT_BYTES:
            raise HTTPException(status_code=413, detail="Screenshot must be 3 MB or smaller.")
        attachments.append((f"screenshot{ALLOWED_SCREENSHOT_TYPES[content_type]}", data, content_type))

    ip = client_ip(request) or "unknown"
    if _rate_limited(ip, time.monotonic()):
        raise HTTPException(status_code=429, detail="Too many feedback submissions; please try again later.")

    body = "<p>" + html.escape(text).replace("\n", "<br>") + "</p>"
    if context_dict:
        body += _context_html(context_dict)
    ok = mailer.send(settings, [settings.feedback_email], "Pumasi Sign feedback", body, attachments)
    if not ok:
        raise HTTPException(status_code=503, detail="Could not send feedback, please try again later.")
    return Response(status_code=204)
