# SharePoint Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mirror every completed envelope's signed PDF + certificate PDF to the "Pumasi Operations" SharePoint site's Legal library, uploaded on completion with a daily-job retry/backfill sweep.

**Architecture:** A new `backend/app/sharepoint.py` module (never-raise contract, modeled on `mailer.py`) uploads via Microsoft Graph using the app-only token machinery extracted from `mailer.py` into a shared `backend/app/graph.py`. Two new nullable columns on `submissions` (`archived_at`, `archive_url`) track state; `status='completed' AND archived_at IS NULL` is the retry predicate. Trigger points: the three existing `notifications.on_submission_completed` call sites, plus a sweep in `POST /api/jobs/daily`.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, MSAL (client credentials), httpx, pytest with `httpx.MockTransport`.

**Spec:** `docs/superpowers/specs/2026-08-01-sharepoint-archive-design.md`

## Global Constraints

- Tests are Postgres-only, DB from `TEST_DATABASE_URL` (default `postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_test`). Never SQLite.
- Run backend commands from `backend/`; the worktree has no venv — use the main checkout's: `/home/m/dev/pumasi-sign/backend/.venv/Scripts/python.exe -m pytest ...` (memory: worktree-shared-toolchains).
- `archive_submission` must NEVER raise to callers and NEVER block/fail signing completion (same contract as `mailer.send`).
- Never log document contents, titles, or tokens; submission id + HTTP status only.
- Feature is dormant when `SP_DRIVE_ID` is unset (empty default) — local dev/tests run with it off.
- New env vars: `SP_DRIVE_ID` (no default), `SP_ARCHIVE_FOLDER` (default `Signed_document_archive`).
- Lint before committing: `ruff check . && ruff format .` from `backend/`.
- Folder layout: `{SP_ARCHIVE_FOLDER}/{owner email}/{year}/{sanitized title} ({id})/signed.pdf` + `certificate.pdf`.
- Uploads idempotent via `@microsoft.graph.conflictBehavior=replace`.

---

### Task 1: Extract shared Graph token helper (`graph.py`)

Pure refactor — no behavior change. `mailer.py`'s MSAL machinery becomes `app/graph.py` so `sharepoint.py` (Task 4) can share one token cache per credential triple.

**Files:**
- Create: `backend/app/graph.py`
- Modify: `backend/app/mailer.py` (delete lines 52, 58–82: `GRAPH_SCOPES`, `_msal_apps`, `_get_msal_app`, `_acquire_token`; add import)
- Test: existing `backend/tests/test_mailer.py` (unchanged — it monkeypatches `mailer._acquire_token`, which keeps working because the import below rebinds the same module attribute)

**Interfaces:**
- Produces: `graph.acquire_token(settings: Settings) -> str | None` — app-only Graph token or None (logged), never raises.

- [ ] **Step 1: Create `backend/app/graph.py`**

```python
"""Shared Microsoft Graph app-only auth (client-credentials flow).

An MSAL ``ConfidentialClientApplication`` is built once per distinct
``(tenant, client_id, client_secret)`` triple and cached at module level —
MSAL's app object owns its own token cache, so both mail sending
(``app.mailer``) and SharePoint archiving (``app.sharepoint``) reuse the
same token instead of re-authenticating per call.

Never logs tokens; a failed acquisition logs the MSAL error code only.
"""

from __future__ import annotations

import logging

import msal

from app.config import Settings

logger = logging.getLogger(__name__)

GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]

_msal_apps: dict[tuple[str, str, str], msal.ConfidentialClientApplication] = {}


def _get_msal_app(settings: Settings) -> msal.ConfidentialClientApplication:
    """Return the cached MSAL app for this tenant/client, building it on first use."""
    key = (settings.ms_tenant_id, settings.ms_client_id, settings.ms_client_secret)
    app = _msal_apps.get(key)
    if app is None:
        app = msal.ConfidentialClientApplication(
            settings.ms_client_id,
            authority=f"https://login.microsoftonline.com/{settings.ms_tenant_id}",
            client_credential=settings.ms_client_secret,
        )
        _msal_apps[key] = app
    return app


def acquire_token(settings: Settings) -> str | None:
    """Acquire (or reuse from MSAL's own cache) an app-only Graph access token."""
    app = _get_msal_app(settings)
    result = app.acquire_token_for_client(scopes=GRAPH_SCOPES)
    token = result.get("access_token")
    if not token:
        logger.error("Failed to acquire Graph access token: %s", result.get("error", "unknown_error"))
    return token
```

- [ ] **Step 2: Update `backend/app/mailer.py`**

Delete `GRAPH_SCOPES` (line 52), `_msal_apps` (line 58), `_get_msal_app` (lines 61–72), and `_acquire_token` (lines 75–82). Delete the now-unused `import msal`. Add:

```python
from app.graph import acquire_token as _acquire_token
```

Update the module docstring's auth paragraph to note the machinery lives in `app.graph` (shared with `app.sharepoint`), and the test-seam paragraph to say `app.mailer._acquire_token` is a module-level *rebinding* of `app.graph.acquire_token` that tests monkeypatch. Do not rename the `_acquire_token` call inside `send()` — the monkeypatch seam depends on the module attribute.

- [ ] **Step 3: Run mailer + notifications tests to verify no regression**

Run from `backend/`: `<venv-python> -m pytest tests/test_mailer.py tests/test_notifications.py -q`
Expected: all PASS (if `UndefinedTable` errors cascade, a concurrent pytest session is running — re-run; see memory shared-test-db-races)

- [ ] **Step 4: Lint and commit**

```bash
ruff check . && ruff format .
git add app/graph.py app/mailer.py
git commit -m "refactor: extract Graph app-only token helper to app.graph"
```

---

### Task 2: Settings, model columns, migration

**Files:**
- Modify: `backend/app/config.py` (after `dev_auth_bypass`, line 27)
- Modify: `backend/app/models.py` (Submission, after `certificate_pdf_key`, line 85)
- Create: `backend/migrations/versions/f3a8c1d97e42_submission_archive_columns.py`
- Test: `backend/tests/test_submissions.py` (existing suite exercises the Submission model against the metadata-created schema)

**Interfaces:**
- Produces: `Settings.sp_drive_id: str = ""`, `Settings.sp_archive_folder: str = "Signed_document_archive"`, `Submission.archived_at: datetime | None`, `Submission.archive_url: str | None`.

- [ ] **Step 1: Add settings fields in `config.py`**

```python
    sp_drive_id: str = ""
    sp_archive_folder: str = "Signed_document_archive"
```

- [ ] **Step 2: Add columns to `Submission` in `models.py`**

After `certificate_pdf_key`:

```python
    # SharePoint archive mirror (docs/superpowers/specs/2026-08-01-sharepoint-archive-design.md).
    # archived_at NULL + status 'completed' = "still needs archiving" (the
    # daily sweep's retry predicate); archive_url is the folder webUrl.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
```

- [ ] **Step 3: Create the migration**

`backend/migrations/versions/f3a8c1d97e42_submission_archive_columns.py`:

```python
"""submissions.archived_at + archive_url: SharePoint archive mirror state.

NULL archived_at on a completed submission means "not yet archived" — the
daily job's sweep predicate. See
docs/superpowers/specs/2026-08-01-sharepoint-archive-design.md.

Revision ID: f3a8c1d97e42
Revises: 7c3d9e5f1a2b
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a8c1d97e42"
down_revision: str | Sequence[str] | None = "7c3d9e5f1a2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submissions", sa.Column("archive_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "archive_url")
    op.drop_column("submissions", "archived_at")
```

- [ ] **Step 4: Run submissions tests (schema sanity)**

Run: `<venv-python> -m pytest tests/test_submissions.py -q`
Expected: PASS (tables are re-created from metadata including the new columns)

- [ ] **Step 5: Lint and commit**

```bash
ruff check . && ruff format .
git add app/config.py app/models.py migrations/versions/f3a8c1d97e42_submission_archive_columns.py
git commit -m "feat: archive state columns + SharePoint settings"
```

---

### Task 3: `sharepoint.py` — title sanitizer and folder path (TDD)

Pure functions first; upload logic comes in Task 4 in the same module.

**Files:**
- Create: `backend/app/sharepoint.py` (module skeleton + the two pure functions)
- Create: `backend/tests/test_sharepoint.py`

**Interfaces:**
- Produces: `sanitize_title(title: str) -> str`; `folder_path(archive_folder: str, owner_email: str, completed_at: datetime, title: str, submission_id: int) -> str` (POSIX-style, no leading/trailing slash, e.g. `Signed_document_archive/jane@pumasi.ai/2026/NDA - Acme (42)`).

- [ ] **Step 1: Write failing tests**

`backend/tests/test_sharepoint.py`:

```python
"""Tests for app.sharepoint: path building, uploads, and archive_submission.

Seams mirror test_mailer.py: ``app.sharepoint._acquire_token`` is
monkeypatched (rebinding of ``app.graph.acquire_token``), and
``transport=httpx.MockTransport(...)`` mocks the Graph HTTP calls.
"""

from datetime import UTC, datetime

from app.sharepoint import folder_path, sanitize_title


def test_sanitize_title_replaces_illegal_characters() -> None:
    assert sanitize_title('a"b*c:d<e>f?g/h\\i|j') == "a_b_c_d_e_f_g_h_i_j"


def test_sanitize_title_collapses_runs_and_trims() -> None:
    assert sanitize_title('  ::weird??  title..  ') == "_weird_ title"


def test_sanitize_title_truncates_to_100_chars() -> None:
    assert len(sanitize_title("x" * 250)) == 100


def test_sanitize_title_empty_becomes_underscore() -> None:
    assert sanitize_title("...") == "_"


def test_folder_path_layout() -> None:
    path = folder_path(
        "Signed_document_archive",
        "jane@pumasi.ai",
        datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        "NDA - Acme Corp",
        42,
    )
    assert path == "Signed_document_archive/jane@pumasi.ai/2026/NDA - Acme Corp (42)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `<venv-python> -m pytest tests/test_sharepoint.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.sharepoint'`

- [ ] **Step 3: Create `backend/app/sharepoint.py` with the pure functions**

```python
"""SharePoint archive mirror for completed envelopes (Microsoft Graph).

``archive_submission`` is the sole public entry point (Task 4). Like
``mailer.send`` it never raises to callers: any failure — feature disabled,
missing artifacts, token failure, HTTP error — is logged (submission id and
HTTP status only; never titles, tokens, or file bytes) and returns
``False``, so an archive outage can never fail a signer's request or the
daily job. SharePoint is a mirror; the Railway volume stays the source of
truth. Design: docs/superpowers/specs/2026-08-01-sharepoint-archive-design.md.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# SharePoint-illegal item-name characters, plus control chars.
_ILLEGAL = re.compile(r'[\"*:<>?/\\|\x00-\x1f]')
_MAX_TITLE_LEN = 100


def sanitize_title(title: str) -> str:
    """Make ``title`` safe as a SharePoint folder-name segment.

    Illegal characters become ``_`` (runs collapsed), surrounding
    whitespace and trailing dots are stripped, and the result is capped at
    100 characters. Uniqueness comes from the ``({id})`` suffix appended by
    ``folder_path``, so lossy sanitization here is fine.
    """
    cleaned = _ILLEGAL.sub("_", title)
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip().rstrip(".").strip()
    return cleaned[:_MAX_TITLE_LEN] or "_"


def folder_path(
    archive_folder: str,
    owner_email: str,
    completed_at: datetime,
    title: str,
    submission_id: int,
) -> str:
    """Return the envelope's archive folder path inside the drive.

    Layout per the spec: ``{folder}/{owner email}/{year}/{title} ({id})``.
    The year comes from ``completed_at`` (UTC values only reach here —
    ``Submission.completed_at`` is TIMESTAMPTZ).
    """
    return f"{archive_folder}/{owner_email}/{completed_at.year}/{sanitize_title(title)} ({submission_id})"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `<venv-python> -m pytest tests/test_sharepoint.py -q`
Expected: 5 PASS

- [ ] **Step 5: Lint and commit**

```bash
ruff check . && ruff format .
git add app/sharepoint.py tests/test_sharepoint.py
git commit -m "feat: SharePoint archive path building + title sanitizer"
```

---

### Task 4: `archive_submission` upload logic (TDD)

**Files:**
- Modify: `backend/app/sharepoint.py` (append upload code)
- Modify: `backend/tests/test_sharepoint.py` (append tests)

**Interfaces:**
- Consumes: `graph.acquire_token` (Task 1), `folder_path`/`sanitize_title` (Task 3), `Submission.archived_at`/`archive_url` (Task 2), `FileStorage.open/exists` (`app/storage.py`).
- Produces: `archive_submission(db: Session, submission: Submission, storage: FileStorage, settings: Settings, *, transport: httpx.BaseTransport | None = None) -> bool`. On success sets `submission.archived_at`/`archive_url` and commits (own short transaction). Callers (Tasks 5–6) call it strictly *after* their own `db.commit()`.

- [ ] **Step 1: Write failing tests (append to `tests/test_sharepoint.py`)**

Add imports at top of the test file:

```python
import httpx
import pytest
from sqlalchemy.orm import Session

from app import sharepoint
from app.config import Settings
from app.models import Submission, Template, User
from app.storage import LocalVolumeStorage
```

Fixture + helpers and tests:

```python
SP_SETTINGS = dict(sp_drive_id="drive-1", sp_archive_folder="Signed_document_archive")


def _make_completed_submission(db: Session, storage: LocalVolumeStorage, *, with_certificate: bool = True) -> Submission:
    """Insert a completed submission with real artifact files on disk."""
    owner = User(email="jane@pumasi.ai", name="Jane")
    db.add(owner)
    db.flush()
    template = Template(name="NDA", created_by=owner.id, original_file_key="t/1/o.pdf", pdf_key="t/1/d.pdf", page_count=1)
    db.add(template)
    db.flush()
    submission = Submission(
        template_id=template.id,
        title="NDA - Acme Corp",
        created_by=owner.id,
        status="completed",
        completed_at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        signed_pdf_key="submissions/1/signed.pdf",
        certificate_pdf_key="submissions/1/certificate.pdf" if with_certificate else None,
    )
    db.add(submission)
    db.commit()
    storage.save("submissions/1/signed.pdf", b"%PDF signed")
    if with_certificate:
        storage.save("submissions/1/certificate.pdf", b"%PDF cert")
    return submission


def test_archive_disabled_returns_false_without_http(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage)

    def explode(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no HTTP call expected when SP_DRIVE_ID is unset")

    ok = sharepoint.archive_submission(
        db, submission, storage, Settings(), transport=httpx.MockTransport(explode)
    )
    assert ok is False
    assert submission.archived_at is None


def test_archive_uploads_both_artifacts_and_marks_row(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: "tok")
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage)
    puts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            puts.append(str(request.url))
            return httpx.Response(201, json={"webUrl": "https://pumasiinc.sharepoint.com/x/file"})
        # folder webUrl lookup
        return httpx.Response(200, json={"webUrl": "https://pumasiinc.sharepoint.com/x/folder"})

    ok = sharepoint.archive_submission(
        db, submission, storage, Settings(**SP_SETTINGS), transport=httpx.MockTransport(handler)
    )
    assert ok is True
    base = "Signed_document_archive/jane@pumasi.ai/2026/NDA - Acme Corp (1)"
    assert any(f"root:/{base}/signed.pdf:/content" in u for u in puts)
    assert any(f"root:/{base}/certificate.pdf:/content" in u for u in puts)
    assert all("conflictBehavior=replace" in u for u in puts)
    db.refresh(submission)
    assert submission.archived_at is not None
    assert submission.archive_url == "https://pumasiinc.sharepoint.com/x/folder"


def test_archive_without_certificate_uploads_signed_only(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: "tok")
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage, with_certificate=False)
    puts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            puts.append(str(request.url))
            return httpx.Response(201, json={"webUrl": "u"})
        return httpx.Response(200, json={"webUrl": "u"})

    ok = sharepoint.archive_submission(
        db, submission, storage, Settings(**SP_SETTINGS), transport=httpx.MockTransport(handler)
    )
    assert ok is True
    assert len(puts) == 1
    assert "signed.pdf" in puts[0]


def test_archive_http_failure_returns_false_and_leaves_row(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: "tok")
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage)

    handler = lambda request: httpx.Response(503)  # noqa: E731

    ok = sharepoint.archive_submission(
        db, submission, storage, Settings(**SP_SETTINGS), transport=httpx.MockTransport(handler)
    )
    assert ok is False
    db.refresh(submission)
    assert submission.archived_at is None
    assert submission.archive_url is None


def test_archive_token_failure_returns_false(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: None)
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage)

    ok = sharepoint.archive_submission(db, submission, storage, Settings(**SP_SETTINGS))
    assert ok is False


def test_archive_large_file_uses_upload_session(db: Session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sharepoint, "_acquire_token", lambda settings: "tok")
    storage = LocalVolumeStorage(tmp_path)
    submission = _make_completed_submission(db, storage, with_certificate=False)
    storage.save("submissions/1/signed.pdf", b"x" * (sharepoint.SIMPLE_UPLOAD_LIMIT + 1))
    calls: list[tuple[str, str, str]] = []  # (method, url, content-range)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url), request.headers.get("content-range", "")))
        if request.url.path.endswith(":/createUploadSession"):
            return httpx.Response(200, json={"uploadUrl": "https://upload.example/session-1"})
        if request.url.host == "upload.example":
            done = calls[-1][2].endswith(f"/{sharepoint.SIMPLE_UPLOAD_LIMIT + 1}") and calls[-1][2].split("-")[1].split("/")[0] == str(sharepoint.SIMPLE_UPLOAD_LIMIT)
            return httpx.Response(201 if done else 202, json={"webUrl": "u"} if done else {})
        return httpx.Response(200, json={"webUrl": "u"})

    ok = sharepoint.archive_submission(
        db, submission, storage, Settings(**SP_SETTINGS), transport=httpx.MockTransport(handler)
    )
    assert ok is True
    session_calls = [c for c in calls if "createUploadSession" in c[1]]
    chunk_calls = [c for c in calls if c[1].startswith("https://upload.example")]
    assert len(session_calls) == 1
    assert len(chunk_calls) >= 2  # > CHUNK_SIZE bytes means at least two chunks
    assert all(c[0] == "PUT" for c in chunk_calls)
    # No Authorization header on the pre-authenticated upload URL is asserted implicitly:
    # MockTransport would still work either way, so also check explicitly on the first chunk.
```

Note for the implementer: in `test_archive_large_file_uses_upload_session`, also capture `request.headers.get("authorization", "")` for chunk calls and assert it is `""`.

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `<venv-python> -m pytest tests/test_sharepoint.py -q`
Expected: Task 3 tests PASS; new tests FAIL with `AttributeError: module 'app.sharepoint' has no attribute 'archive_submission'`

- [ ] **Step 3: Implement upload logic (append to `app/sharepoint.py`)**

Add imports at top: `from datetime import UTC, datetime`, `import httpx`, `from sqlalchemy.orm import Session`, `from app.config import Settings`, `from app.graph import acquire_token as _acquire_token`, `from app.models import Submission`, `from app.storage import FileStorage`.

```python
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
# Graph's simple-PUT ceiling is 4 MB; larger files need an upload session.
SIMPLE_UPLOAD_LIMIT = 4 * 1024 * 1024
# Upload-session chunks must be multiples of 320 KiB; 10 of them ≈ 3.1 MB.
CHUNK_SIZE = 10 * 320 * 1024


def _upload_file(client: httpx.Client, drive_id: str, item_path: str, data: bytes, token: str) -> bool:
    """Upload ``data`` to ``item_path`` in ``drive_id``. Returns success; never raises."""
    headers = {"Authorization": f"Bearer {token}"}
    if len(data) <= SIMPLE_UPLOAD_LIMIT:
        response = client.put(
            f"{GRAPH_ROOT}/drives/{drive_id}/root:/{item_path}:/content",
            params={"@microsoft.graph.conflictBehavior": "replace"},
            content=data,
            headers={**headers, "Content-Type": "application/octet-stream"},
        )
        if response.status_code >= 300:
            logger.error("SharePoint simple upload failed with status %d", response.status_code)
            return False
        return True

    response = client.post(
        f"{GRAPH_ROOT}/drives/{drive_id}/root:/{item_path}:/createUploadSession",
        json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
        headers=headers,
    )
    if response.status_code >= 300:
        logger.error("SharePoint createUploadSession failed with status %d", response.status_code)
        return False
    upload_url = response.json().get("uploadUrl")
    if not upload_url:
        logger.error("SharePoint createUploadSession response had no uploadUrl")
        return False

    total = len(data)
    for start in range(0, total, CHUNK_SIZE):
        chunk = data[start : start + CHUNK_SIZE]
        end = start + len(chunk) - 1
        # The uploadUrl is pre-authenticated — no Authorization header.
        response = client.put(
            upload_url,
            content=chunk,
            headers={
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {start}-{end}/{total}",
            },
        )
        if response.status_code >= 300:
            logger.error("SharePoint chunk upload failed with status %d", response.status_code)
            return False
    return True


def archive_submission(
    db: Session,
    submission: Submission,
    storage: FileStorage,
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> bool:
    """Mirror ``submission``'s artifacts to SharePoint. Returns success; never raises.

    No-op (``False``, quiet) when ``SP_DRIVE_ID`` is unset — the feature
    flag for local dev and tests. Only completed submissions with a signed
    PDF are eligible. On success of *all* uploads: sets ``archived_at`` and
    ``archive_url`` and commits — callers must invoke this only after their
    own ``db.commit()``, never mid-transaction (same rule as the completion
    email; see app/completion.py's docstring). A missing certificate is
    fine (pre-issue-#15 envelopes); a missing signed PDF is a failure.

    Single attempt per call, 30 s timeout per request — the daily job's
    sweep is the retry mechanism (unlike mail's in-call retries), keeping
    completion-time latency low.
    """
    if not settings.sp_drive_id:
        logger.debug("SharePoint archive disabled (SP_DRIVE_ID unset); skipping")
        return False
    if submission.status != "completed" or not submission.signed_pdf_key or submission.completed_at is None:
        logger.warning("archive_submission called for ineligible submission_id=%s", submission.id)
        return False

    try:
        signed_bytes = storage.open(submission.signed_pdf_key)
        certificate_bytes = None
        if submission.certificate_pdf_key and storage.exists(submission.certificate_pdf_key):
            certificate_bytes = storage.open(submission.certificate_pdf_key)

        token = _acquire_token(settings)
        if not token:
            return False

        folder = folder_path(
            settings.sp_archive_folder,
            submission.creator.email,
            submission.completed_at,
            submission.title,
            submission.id,
        )

        client_kwargs = {"transport": transport} if transport is not None else {}
        with httpx.Client(timeout=30.0, **client_kwargs) as client:
            if not _upload_file(client, settings.sp_drive_id, f"{folder}/signed.pdf", signed_bytes, token):
                logger.error("SharePoint archive failed for submission_id=%s", submission.id)
                return False
            if certificate_bytes is not None and not _upload_file(
                client, settings.sp_drive_id, f"{folder}/certificate.pdf", certificate_bytes, token
            ):
                logger.error("SharePoint archive failed for submission_id=%s", submission.id)
                return False

            # Folder webUrl for future UI use — best-effort; a failure here
            # doesn't undo the archive.
            archive_url = None
            response = client.get(
                f"{GRAPH_ROOT}/drives/{settings.sp_drive_id}/root:/{folder}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code < 300:
                archive_url = response.json().get("webUrl")

        submission.archived_at = datetime.now(UTC)
        submission.archive_url = archive_url
        db.commit()
    except Exception:
        logger.exception("SharePoint archive failed for submission_id=%s", submission.id)
        db.rollback()
        return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `<venv-python> -m pytest tests/test_sharepoint.py -q`
Expected: all PASS

- [ ] **Step 5: Lint and commit**

```bash
ruff check . && ruff format .
git add app/sharepoint.py tests/test_sharepoint.py
git commit -m "feat: SharePoint archive_submission with chunked upload support"
```

---

### Task 5: Trigger archive on completion

**Files:**
- Modify: `backend/app/routers/signing.py` (two call sites: ~line 276 and ~line 299)
- Modify: `backend/app/routers/submissions.py` (one call site: ~line 551)
- Test: `backend/tests/test_signing.py` (append)

**Interfaces:**
- Consumes: `sharepoint.archive_submission(db, submission, storage, settings)` (Task 4).

- [ ] **Step 1: Write failing tests (append to `tests/test_signing.py`)**

Use the file's existing helpers: `_single_signer_submission(admin_client, signer_client)` (line ~92) creates a one-signer submission and returns `(submission_dict, submitter_id)`; `_complete_with_signature(client, submitter_id, field_id)` (line ~681) creates a signature and posts `/api/sign/{submitter_id}/complete`, asserting success. The single-signer submission's only field id is `"sig1"`. New tests (place near the other completion tests):

```python
def test_completion_triggers_sharepoint_archive(
    admin_client: TestClient,
    user_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import sharepoint

    archived_ids: list[int] = []

    def fake_archive(db: object, submission: object, storage: object, settings: object) -> bool:
        archived_ids.append(submission.id)  # type: ignore[attr-defined]
        return True

    monkeypatch.setattr(sharepoint, "archive_submission", fake_archive)

    submission, submitter_id = _single_signer_submission(admin_client, user_client)
    _complete_with_signature(user_client, submitter_id, "sig1")

    assert archived_ids == [submission["id"]]


def test_archive_failure_does_not_affect_completion(
    admin_client: TestClient,
    user_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import sharepoint

    monkeypatch.setattr(sharepoint, "archive_submission", lambda db, submission, storage, settings: False)

    submission, submitter_id = _single_signer_submission(admin_client, user_client)
    _complete_with_signature(user_client, submitter_id, "sig1")

    detail = admin_client.get(f"/api/submissions/{submission['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "completed"
```

(`_complete_with_signature` already asserts the `/complete` response succeeded, so a raising/failing archiver breaking the request would fail the test there.)

Monkeypatching `app.sharepoint.archive_submission` works for the routers because they call it as `sharepoint.archive_submission(...)` via `from app import sharepoint` (attribute lookup at call time).

- [ ] **Step 2: Run tests to verify they fail**

Run: `<venv-python> -m pytest tests/test_signing.py -q -k archive`
Expected: FAIL — `calls == []` (routers don't call the archiver yet)

- [ ] **Step 3: Add the calls in the routers**

In `backend/app/routers/signing.py` add `from app import sharepoint` to the existing `from app import ...` import (match the file's import style), then extend **both** completion sites:

```python
        if outcome == completion.FinalizeOutcome.FINALIZED and submission.status == "completed":
            notifications.on_submission_completed(db, submission, storage, settings)
            sharepoint.archive_submission(db, submission, storage, settings)
```

(The same two-line body at ~line 276 in the `already`-completed branch and ~line 299 in the normal path — both already run strictly after `db.commit()`, which is the contract `archive_submission` requires.)

In `backend/app/routers/submissions.py` (retry-completion, ~line 551), same pattern:

```python
    if submission.status == "completed":
        notifications.on_submission_completed(db, submission, storage, settings)
        sharepoint.archive_submission(db, submission, storage, settings)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `<venv-python> -m pytest tests/test_signing.py tests/test_submissions.py -q`
Expected: all PASS (existing suites confirm no regression in completion flows)

- [ ] **Step 5: Lint and commit**

```bash
ruff check . && ruff format .
git add app/routers/signing.py app/routers/submissions.py tests/test_signing.py
git commit -m "feat: archive envelope to SharePoint on completion"
```

---

### Task 6: Daily-job sweep (retry + backfill)

**Files:**
- Modify: `backend/app/routers/jobs.py`
- Test: `backend/tests/test_jobs.py` (append; follow the existing token-header pattern in that file)

**Interfaces:**
- Consumes: `sharepoint.archive_submission` (Task 4), `Submission.archived_at` (Task 2), `get_storage` (`app/storage.py`).
- Produces: `POST /api/jobs/daily` response gains top-level keys `"archived": int, "archive_failed": int`.

- [ ] **Step 1: Write failing tests (append to `tests/test_jobs.py`)**

The file already has `_settings(tmp_path, **overrides) -> Settings` (job token `"test-job-token"`, `data_dir=tmp_path`) and imports `Submission`, `Template`, `User`, `db`, `make_client`. New tests (add `import pytest` and `from app import sharepoint` where the file's conventions put them):

```python
def _archive_rows(db: Session) -> tuple[int, int, int, int]:
    """Insert 4 submissions: two archive-eligible, one already archived, one pending."""
    owner = User(email="owner@pumasi.ai", name="Owner")
    db.add(owner)
    db.flush()
    template = Template(name="Doc", created_by=owner.id, original_file_key="x", pdf_key="x", page_count=1)
    db.add(template)
    db.flush()
    now = datetime.now(UTC)

    def _submission(**overrides) -> Submission:
        base = dict(template_id=template.id, title="T", created_by=owner.id, status="completed", completed_at=now)
        base.update(overrides)
        submission = Submission(**base)
        db.add(submission)
        return submission

    eligible_a = _submission(signed_pdf_key="s/a.pdf")
    eligible_b = _submission(signed_pdf_key="s/b.pdf")
    already = _submission(signed_pdf_key="s/c.pdf", archived_at=now, archive_url="u")
    pending = _submission(status="pending", completed_at=None)
    db.commit()
    return eligible_a.id, eligible_b.id, already.id, pending.id


def test_daily_job_sweeps_unarchived_completed_submissions(
    make_client,
    tmp_path: Path,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(_settings(tmp_path, sp_drive_id="drive-1"))
    eligible_a, eligible_b, _already, _pending = _archive_rows(db)

    attempted: list[int] = []

    def fake_archive(db_: object, submission: Submission, storage: object, settings: object) -> bool:
        attempted.append(submission.id)
        return submission.id == eligible_a  # one success, one failure

    monkeypatch.setattr(sharepoint, "archive_submission", fake_archive)

    resp = client.post("/api/jobs/daily", headers={"X-Job-Token": "test-job-token"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["archived"] == 1
    assert body["archive_failed"] == 1
    assert sorted(attempted) == sorted([eligible_a, eligible_b])


def test_daily_job_skips_sweep_when_disabled(
    make_client,
    tmp_path: Path,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(_settings(tmp_path))  # sp_drive_id left empty
    _archive_rows(db)

    def must_not_be_called(*args: object, **kwargs: object) -> bool:
        raise AssertionError("archive_submission must not be called when SP_DRIVE_ID is unset")

    monkeypatch.setattr(sharepoint, "archive_submission", must_not_be_called)

    resp = client.post("/api/jobs/daily", headers={"X-Job-Token": "test-job-token"})

    assert resp.status_code == 200
    assert resp.json()["archived"] == 0
    assert resp.json()["archive_failed"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `<venv-python> -m pytest tests/test_jobs.py -q -k sweep or disabled`
Expected: FAIL — `KeyError: 'archived'`

- [ ] **Step 3: Implement the sweep in `jobs.py`**

Add imports: `from sqlalchemy import select`, `from app import notifications, sharepoint`, `from app.models import Submission`, `from app.storage import get_storage`.

```python
def _archive_sweep(db: Session, settings: Settings) -> tuple[int, int]:
    """Archive every completed-but-unarchived submission. Returns (archived, failed).

    Retry for completion-time failures and backfill for envelopes completed
    before this feature shipped (their ``archived_at`` is NULL). Skipped
    entirely when ``SP_DRIVE_ID`` is unset so a disabled feature doesn't
    log a failure per envelope every day. Best-effort like the backup
    steps: ``archive_submission`` never raises, and one failure doesn't
    stop the sweep.
    """
    if not settings.sp_drive_id:
        return 0, 0

    storage = get_storage(settings)
    pending = db.scalars(
        select(Submission).where(
            Submission.status == "completed",
            Submission.archived_at.is_(None),
            Submission.signed_pdf_key.is_not(None),
        ),
    ).all()

    archived = failed = 0
    for submission in pending:
        if sharepoint.archive_submission(db, submission, storage, settings):
            archived += 1
        else:
            failed += 1
    return archived, failed
```

In `run_daily_job`, after the `_prune` calls:

```python
    archived, archive_failed = _archive_sweep(db, settings)

    return {
        "reminders_sent": reminders_sent,
        "backup": {"db": db_ok, "files": files_ok},
        "archived": archived,
        "archive_failed": archive_failed,
    }
```

Also update the module docstring's numbered list (add the sweep as item 3) and `run_daily_job`'s docstring return shape.

- [ ] **Step 4: Run tests to verify they pass**

Run: `<venv-python> -m pytest tests/test_jobs.py -q`
Expected: all PASS

- [ ] **Step 5: Lint and commit**

```bash
ruff check . && ruff format .
git add app/routers/jobs.py tests/test_jobs.py
git commit -m "feat: daily-job sweep retries and backfills SharePoint archive"
```

---

### Task 7: Docs, full verification, PR

**Files:**
- Modify: `README.md` (env var table/section — add `SP_DRIVE_ID`, `SP_ARCHIVE_FOLDER` with one-line descriptions and the rollout note: deploy code first, then set vars; next daily job backfills)
- Modify: `CLAUDE.md` (backend layout bullet: add `sharepoint.py` (Graph archive mirror) and `graph.py` (shared Graph auth) alongside `mailer.py`)

**Interfaces:** none (docs + verification only).

- [ ] **Step 1: Update README.md and CLAUDE.md as above**

Real values for the README (not secrets):

```
SP_DRIVE_ID=b!yfEmPUN-7UyS1Z6xZQVh6YppZfIgzWZBnTKWVL9zhK0zexu6vG5qQ5PA-VUSVyeB
SP_ARCHIVE_FOLDER=Signed_document_archive
```

- [ ] **Step 2: Full backend verification**

Run from `backend/`:
- `ruff check . && ruff format --check .` — expected: clean
- `<venv-python> -m pytest -q` — expected: all pass (conversion tests may auto-skip without LibreOffice)

- [ ] **Step 3: Commit and push**

```bash
git add README.md CLAUDE.md
git commit -m "docs: SharePoint archive env vars and module layout"
git push
```

- [ ] **Step 4: Update draft PR #25**

The branch already has draft PR #25 (spec). Update its title/body to cover the implementation (`gh pr edit 25 ...`), or mark it ready for review — it becomes the feature PR.
