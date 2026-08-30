# Feedback Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "Feedback" button on every page of Pumasi Sign that emails user-submitted feedback (message + optional screenshot) to `legal@pumasi.ai`.

**Architecture:** A new unauthenticated `POST /api/feedback` endpoint validates the submission, rate-limits per IP in memory, and delegates to the existing Graph mailer. The mailer's attachment API gains a content-type element so screenshots aren't mislabeled as PDFs. The frontend adds one self-contained dialog component activated from the app bar.

**Tech Stack:** FastAPI, pytest (Postgres test DB on :5433), Microsoft Graph sendMail (mocked in tests), Vue 3 + Vuetify 3.13, axios.

Spec: `docs/superpowers/specs/2026-08-01-feedback-button-design.md`.

## Global Constraints

- Work on the existing `feedback-button` branch (already created).
- Message ≤ **5,000** chars (after strip, non-empty). Screenshot: `image/png` or `image/jpeg` only, ≤ **3 MB** (3 * 1024 * 1024 bytes). Rate limit: **5** submissions per rolling **600 s** per IP.
- Error codes: 400 bad message, 415 wrong type, 413 too big, 429 rate limited, 503 mail failed. Success: **204**.
- The email contains ONLY the user's message (HTML-escaped) and the screenshot. No URL, user identity, or browser metadata.
- Email subject: `Pumasi Sign feedback`. Recipient: `settings.feedback_email` (env `FEEDBACK_EMAIL`, default `legal@pumasi.ai`).
- Backend lint must pass: `ruff check . && ruff format --check .` (run from `backend/`, venv at `backend/.venv`).
- Tests are Postgres-only; run `pytest` from `backend/`. Never SQLite.
- Frontend must pass `npx vue-tsc --noEmit` (from `frontend/`).
- Toast copy on success: `Thanks for the feedback!`

---

### Task 1: Mailer attachments carry a content type

`mailer.send` currently takes attachments as `(filename, bytes)` pairs and hardcodes `contentType: "application/pdf"`. Change to `(filename, bytes, content_type)` triples everywhere. No behavior change for existing PDF emails.

**Files:**
- Modify: `backend/app/mailer.py` (`_build_message_body`, `send` signature + docstring)
- Modify: `backend/app/notifications.py:130-138` (`on_submission_completed`)
- Test: `backend/tests/test_mailer.py` (update 2 call sites, add 1 test)
- Test: `backend/tests/test_notifications.py:364` (unpack triple)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `mailer.send(settings, to: list[str], subject: str, html: str, attachments: list[tuple[str, bytes, str]] | None = None, *, transport=None, sleep=time.sleep) -> bool` — the third tuple element is the MIME content type. Task 2 relies on this exact signature.

- [ ] **Step 1: Update the existing mailer test to the triple form and add a content-type test**

In `backend/tests/test_mailer.py`, change the attachment argument in `test_send_success_builds_expected_graph_request` (line 44):

```python
        [("doc.pdf", b"%PDF-1.4 fake pdf bytes", "application/pdf")],
```

Then add this test after `test_send_without_attachments_omits_attachments_key`:

```python
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
```

- [ ] **Step 2: Run mailer tests to verify they fail**

Run (from `backend/`): `pytest tests/test_mailer.py -v`
Expected: `test_send_success_builds_expected_graph_request` and the new test FAIL (`ValueError: too many values to unpack` inside `_build_message_body`, or `contentType == "application/pdf"` assertion failure).

- [ ] **Step 3: Change `mailer.py` to triples**

In `backend/app/mailer.py`, replace `_build_message_body` (lines 85-106) with:

```python
def _build_message_body(
    to: list[str],
    subject: str,
    html: str,
    attachments: list[tuple[str, bytes, str]],
) -> dict:
    message: dict = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": html},
        "toRecipients": [{"emailAddress": {"address": address}} for address in to],
    }
    if attachments:
        message["attachments"] = [
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": name,
                "contentType": content_type,
                "contentBytes": base64.b64encode(data).decode("ascii"),
            }
            for name, data, content_type in attachments
        ]
    return {"message": message, "saveToSentItems": True}
```

In `send`, change the parameter annotation (line 114) to:

```python
    attachments: list[tuple[str, bytes, str]] | None = None,
```

and update the docstring sentence about attachments (lines 122-124) to:

```python
    ``to`` is a list of recipient email addresses; ``attachments`` is a
    list of ``(filename, bytes, content_type)`` triples, each sent as a
    Graph ``fileAttachment`` with that content type.
```

- [ ] **Step 4: Update the two non-mailer call/assert sites**

In `backend/app/notifications.py`, `on_submission_completed` (lines 130-138), change:

```python
    attachments: list[tuple[str, bytes, str]] = []
    if submission.signed_pdf_key:
        try:
            pdf_bytes = storage.open(submission.signed_pdf_key)
        except FileNotFoundError:
            logger.warning("Signed PDF missing in storage for submission_id=%s", submission.id)
        else:
            filename = f"{_safe_filename(submission.title)}-signed.pdf"
            attachments.append((filename, pdf_bytes, "application/pdf"))
```

In `backend/tests/test_notifications.py` line 364, change:

```python
    filename, data, content_type = calls[0]["attachments"][0]
```

and add directly below it (after the existing assertions on `filename`/`data`):

```python
    assert content_type == "application/pdf"
```

- [ ] **Step 5: Run the affected tests and lint; verify they pass**

Run (from `backend/`): `pytest tests/test_mailer.py tests/test_notifications.py -v && ruff check . && ruff format --check .`
Expected: all PASS, lint clean.

- [ ] **Step 6: Commit**

```bash
git add backend/app/mailer.py backend/app/notifications.py backend/tests/test_mailer.py backend/tests/test_notifications.py
git commit -m "refactor: mailer attachments carry an explicit content type"
```

---

### Task 2: `POST /api/feedback` endpoint

**Files:**
- Modify: `backend/app/config.py` (add `feedback_email` setting)
- Create: `backend/app/routers/feedback.py`
- Modify: `backend/app/main.py` (register router)
- Modify: `README.md` (env-var table row)
- Test: `backend/tests/test_feedback.py`

**Interfaces:**
- Consumes: `mailer.send(settings, to, subject, html, attachments)` with `(filename, bytes, content_type)` triples (Task 1); `get_settings` dependency from `app.auth`; `make_client` fixture from `tests/conftest.py`.
- Produces: `POST /api/feedback` accepting `multipart/form-data` with fields `message` (str, required) and `screenshot` (file, optional); returns 204 on success. Task 3 posts to it. Module-level `_recent_by_ip` dict (tests clear it between runs).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_feedback.py`:

```python
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


def test_mailer_failure_returns_503(
    feedback_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mailer, "send", lambda *args, **kwargs: False)
    response = feedback_client.post("/api/feedback", data={"message": "hi"})
    assert response.status_code == 503
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `backend/`): `pytest tests/test_feedback.py -v`
Expected: collection error — `ImportError: cannot import name 'feedback' from 'app.routers'`.

- [ ] **Step 3: Add the setting**

In `backend/app/config.py`, after `app_base_url: str = ""` (line 26), add:

```python
    feedback_email: str = "legal@pumasi.ai"
```

- [ ] **Step 4: Write the router**

Create `backend/app/routers/feedback.py`:

```python
"""Anonymous in-app feedback: emails the message (+ optional screenshot).

Open to anyone — no auth dependency — because the feedback button renders
on every page, including login and signing pages. Abuse control is a
module-level per-IP rate limit; in-memory is sufficient because the app
runs as a single uvicorn process on Railway (restarts reset it, which is
acceptable). Per the design spec, the email contains ONLY user-provided
content: no page URL, no user identity, no browser metadata.
"""

from __future__ import annotations

import html
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile

from app import mailer
from app.auth import get_settings
from app.config import Settings

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

MAX_MESSAGE_CHARS = 5000
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
    if len(timestamps) >= RATE_LIMIT_MAX:
        return True
    timestamps.append(now)
    return False


@router.post("", status_code=204)
async def submit_feedback(
    request: Request,
    message: str = Form(),
    screenshot: UploadFile | None = File(None),
    settings: Settings = Depends(get_settings),
) -> Response:
    text = message.strip()
    if not text or len(text) > MAX_MESSAGE_CHARS:
        raise HTTPException(status_code=400, detail=f"Message must be 1-{MAX_MESSAGE_CHARS} characters.")

    attachments: list[tuple[str, bytes, str]] = []
    if screenshot is not None:
        content_type = screenshot.content_type or ""
        if content_type not in ALLOWED_SCREENSHOT_TYPES:
            raise HTTPException(status_code=415, detail="Screenshot must be a PNG or JPEG image.")
        data = await screenshot.read()
        if len(data) > MAX_SCREENSHOT_BYTES:
            raise HTTPException(status_code=413, detail="Screenshot must be 3 MB or smaller.")
        attachments.append((f"screenshot{ALLOWED_SCREENSHOT_TYPES[content_type]}", data, content_type))

    client_ip = request.client.host if request.client else "unknown"
    if _rate_limited(client_ip, time.monotonic()):
        raise HTTPException(status_code=429, detail="Too many feedback submissions; please try again later.")

    body = "<p>" + html.escape(text).replace("\n", "<br>") + "</p>"
    ok = mailer.send(settings, [settings.feedback_email], "Pumasi Sign feedback", body, attachments)
    if not ok:
        raise HTTPException(status_code=503, detail="Could not send feedback, please try again later.")
    return Response(status_code=204)
```

- [ ] **Step 5: Register the router**

In `backend/app/main.py`, add to the router imports (alphabetical, after the `files` import on line 13):

```python
from app.routers.feedback import router as feedback_router
```

and after `app.include_router(files_router)` (line 49):

```python
    app.include_router(feedback_router)
```

- [ ] **Step 6: Run the tests and lint; verify they pass**

Run (from `backend/`): `pytest tests/test_feedback.py -v && ruff check . && ruff format --check .`
Expected: all 9 tests PASS, lint clean. If `ruff format --check` flags the new files, run `ruff format .` and re-check.

- [ ] **Step 7: Document the env var**

In `README.md`, in the environment-variable table (the one containing `APP_BASE_URL`, around line 139), add a row:

```markdown
| `FEEDBACK_EMAIL` | Recipient for in-app feedback submissions (default `legal@pumasi.ai`) |
```

- [ ] **Step 8: Run the full backend suite**

Run (from `backend/`): `pytest`
Expected: all PASS (LibreOffice conversion tests may auto-skip; that's normal). If unrelated `UndefinedTable` cascades appear, a concurrent pytest session may be sharing the DB — re-run once before investigating.

- [ ] **Step 9: Commit**

```bash
git add backend/app/config.py backend/app/routers/feedback.py backend/app/main.py backend/tests/test_feedback.py README.md
git commit -m "feat: anonymous feedback endpoint that emails legal@pumasi.ai"
```

---

### Task 3: Feedback button + dialog in the SPA

**Files:**
- Create: `frontend/src/components/FeedbackDialog.vue`
- Modify: `frontend/src/App.vue` (app-bar button, outside the logged-in block)

**Interfaces:**
- Consumes: `POST /api/feedback` (Task 2, multipart fields `message`/`screenshot`); shared axios instance `http` (`baseURL: "/api"`) and `extractError` from `frontend/src/utils/http.ts`; `useUiStore().toast(message)` from `frontend/src/store/ui.ts`.
- Produces: `<FeedbackDialog />` — a self-contained component rendering its own activator button plus the dialog. Nothing else consumes it.

- [ ] **Step 1: Write the component**

Create `frontend/src/components/FeedbackDialog.vue`:

```vue
<script setup lang="ts">
import { computed, ref } from "vue";
import { useUiStore } from "../store/ui";
import http, { extractError } from "../utils/http";

const ui = useUiStore();

const open = ref(false);
const message = ref("");
// Vuetify 3's v-file-input may model a single File or an array depending on
// version/props, so accept both and normalize in `screenshotFile`.
const screenshot = ref<File | File[] | null>(null);
const submitting = ref(false);
const error = ref("");

const MAX_SCREENSHOT_BYTES = 3 * 1024 * 1024;

const screenshotFile = computed<File | null>(() => {
  const value = screenshot.value;
  if (Array.isArray(value)) return value[0] ?? null;
  return value;
});

function cancel(): void {
  open.value = false;
  message.value = "";
  screenshot.value = null;
  error.value = "";
}

async function submit(): Promise<void> {
  const file = screenshotFile.value;
  if (file && file.size > MAX_SCREENSHOT_BYTES) {
    error.value = "Screenshot must be 3 MB or smaller.";
    return;
  }
  submitting.value = true;
  error.value = "";
  try {
    const form = new FormData();
    form.append("message", message.value);
    if (file) form.append("screenshot", file);
    await http.post("/feedback", form);
    cancel();
    ui.toast("Thanks for the feedback!");
  } catch (err) {
    error.value = extractError(err);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <v-btn variant="text" prepend-icon="mdi-message-alert-outline" @click="open = true">
    Feedback
  </v-btn>
  <v-dialog v-model="open" max-width="480">
    <v-card title="Feedback for the app">
      <v-card-text>
        <v-alert v-if="error" type="error" density="compact" class="mb-3">{{ error }}</v-alert>
        <v-textarea
          v-model="message"
          label="What's working? What isn't?"
          rows="5"
          counter="5000"
          maxlength="5000"
          autofocus
        />
        <v-file-input
          v-model="screenshot"
          label="Screenshot (optional)"
          accept="image/png,image/jpeg"
          prepend-icon="mdi-image"
          density="comfortable"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="submitting" @click="cancel">Cancel</v-btn>
        <v-btn color="primary" :disabled="!message.trim()" :loading="submitting" @click="submit">
          Send
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
```

- [ ] **Step 2: Mount it in the app bar**

In `frontend/src/App.vue`:

Add to the imports in `<script setup>` (after the `SignaturePad`-style component import pattern — there are currently no component imports, so put it after the store imports on line 5):

```typescript
import FeedbackDialog from "./components/FeedbackDialog.vue";
```

In the template, insert the component on its own line directly after `<v-spacer />` (line 32), **before** the `<template v-if="auth.me">` block so it renders for everyone:

```vue
      <v-spacer />
      <FeedbackDialog />
      <template v-if="auth.me">
```

- [ ] **Step 3: Type-check and build**

Run (from `frontend/`): `npx vue-tsc --noEmit && npm run build`
Expected: both succeed with no errors. If `vue-tsc` rejects the `v-file-input` model type, adjust the `screenshot` ref's type to what the error demands (keeping the array/single normalization in `screenshotFile`).

- [ ] **Step 4: Smoke-test in the running app**

From `backend/` (venv active, local Postgres running): start the app with `DEV_AUTH_BYPASS=1` per the README's local-dev section, open the login page (logged out), and confirm the Feedback button shows and the dialog opens, requires a message, and — without mail configured locally — submitting shows the 503 message "Could not send feedback, please try again later." inline in the dialog. That inline error IS the expected local outcome (no Graph credentials locally); it proves the full request path works.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/FeedbackDialog.vue frontend/src/App.vue
git commit -m "feat: feedback button and dialog on every page"
```

---

## Self-review notes

- Spec coverage: frontend dialog (Task 3), endpoint + validation + rate limit + 503 (Task 2), mailer content-type change (Task 1), `FEEDBACK_EMAIL` setting + README row (Task 2), tests per spec's testing section (Tasks 1-3). Out-of-scope items untouched.
- The spec's validation table lists the rate limit after screenshot checks; the router implements that exact order (rejected requests don't consume rate-limit slots).
- Type consistency: `(filename, bytes, content_type)` triples appear identically in Tasks 1 and 2; `attachments == []` (not `None`) in the happy-path test matches the router always passing a list.
