# Envelope Public UID Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stamp a random, non-enumerable `public_uid` (uuid4 hex) into the signed-PDF watermark and signature certificate instead of the sequential submission ID, so counterparties can't estimate envelope volume.

**Architecture:** New `public_uid` column on `submissions` (Python-side uuid4 default, migration backfills existing rows). `stamping.py`'s two pure builders take the UID instead of the integer ID for display; `completion.py` passes `submission.public_uid`. `SubmissionOut` exposes the UID and the envelope detail page shows it. Integer PK stays for routes, FKs, and storage keys.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 typed ORM, Alembic, pypdf/reportlab, Pydantic v2, Vue 3 + Vuetify + TypeScript.

**Spec:** `docs/superpowers/specs/2026-07-31-envelope-public-uid-design.md`

## Global Constraints

- Tests are Postgres-only; run from `backend/` with the venv at `backend/.venv`. Test DB URL comes from `TEST_DATABASE_URL` (default `postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_test`).
- If pytest fails with cascading `UndefinedTable` errors, a concurrent pytest session is racing the shared DB — re-run before diagnosing.
- Lint: `ruff check . && ruff format --check .` from `backend/`; type-check frontend with `npx vue-tsc --noEmit` from `frontend/`.
- Watermark copy (exact): `Pumasi Sign · Envelope {public_uid} · Completed {iso}`. Certificate copy (exact): `Submission: {title} (Envelope {public_uid})`.
- Never stamp the sequential integer ID into the watermark or certificate.

---

### Task 1: `Submission.public_uid` column + migration

**Files:**
- Modify: `backend/app/models.py` (Submission class, ~line 64)
- Create: `backend/migrations/versions/d4f8c2e6a9b1_submission_public_uid.py`
- Test: `backend/tests/test_submissions.py` (new test at end of file)

**Interfaces:**
- Produces: `Submission.public_uid: Mapped[str]` — 32-char lowercase hex, unique, NOT NULL, auto-generated on insert. Tasks 2–4 rely on this attribute name.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_submissions.py` (uses the file's existing `_upload_template` and `_me_id` helpers and its existing `from app.models import ... Submission ...` import; add `import re` to the imports):

```python
def test_submission_gets_random_public_uid(
    admin_client: TestClient,
    user_client: TestClient,
    db,
) -> None:
    """public_uid is generated on insert: 32 lowercase hex chars (uuid4), unique per row."""
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])

    ids = []
    for title in ("One", "Two"):
        resp = admin_client.post(
            "/api/submissions",
            json={
                "template_id": template_id,
                "title": title,
                "signers": [{"role": "Signer 1", "user_id": user_id}],
            },
        )
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])

    first, second = (db.get(Submission, submission_id) for submission_id in ids)
    assert re.fullmatch(r"[0-9a-f]{32}", first.public_uid)
    assert re.fullmatch(r"[0-9a-f]{32}", second.public_uid)
    assert first.public_uid != second.public_uid
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `.venv/Scripts/python -m pytest tests/test_submissions.py::test_submission_gets_random_public_uid -v`
Expected: FAIL — `'public_uid' is an invalid keyword`-style TypeError or AttributeError (column doesn't exist).

- [ ] **Step 3: Add the column to the model**

In `backend/app/models.py`, add `import uuid` to the imports, then inside `Submission` directly under `id`:

```python
    # Random, non-enumerable ID stamped on externally shared artifacts
    # (watermark, certificate) instead of the sequential PK, so recipients
    # can't infer envelope volume. PK stays for routes/FKs/storage keys.
    public_uid: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, default=lambda: uuid.uuid4().hex
    )
```

- [ ] **Step 4: Write the migration**

Create `backend/migrations/versions/d4f8c2e6a9b1_submission_public_uid.py` (current head is `7c3d9e5f1a2b`):

```python
"""submissions.public_uid: random non-enumerable ID for external artifacts.

Stamped into the signed-PDF watermark and signature certificate instead of
the sequential PK so recipients can't infer envelope volume. Backfills
existing rows with fresh uuid4 hex via gen_random_uuid() (Postgres 13+).

Revision ID: d4f8c2e6a9b1
Revises: 7c3d9e5f1a2b
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f8c2e6a9b1"
down_revision: str | Sequence[str] | None = "7c3d9e5f1a2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("public_uid", sa.String(length=32), nullable=True))
    op.execute("UPDATE submissions SET public_uid = replace(gen_random_uuid()::text, '-', '')")
    op.alter_column("submissions", "public_uid", nullable=False)
    op.create_unique_constraint("uq_submissions_public_uid", "submissions", ["public_uid"])


def downgrade() -> None:
    op.drop_constraint("uq_submissions_public_uid", "submissions", type_="unique")
    op.drop_column("submissions", "public_uid")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_submissions.py::test_submission_gets_random_public_uid -v`
Expected: PASS. (The test schema comes from `Base.metadata.create_all`, so the model change alone drives it; the migration is for real DBs.)

- [ ] **Step 6: Verify the migration runs against a scratch Postgres DB**

pytest never runs Alembic (conftest uses `create_all`), so exercise the migration directly:

```powershell
# from backend/, PowerShell
& "C:\Program Files\PostgreSQL\bin\psql" --% -h localhost -p 5433 -U postgres -c "DROP DATABASE IF EXISTS pumasi_sign_migration_check" -c "CREATE DATABASE pumasi_sign_migration_check"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_migration_check"
.venv\Scripts\alembic upgrade head
Remove-Item Env:DATABASE_URL
```

(If `psql` isn't on PATH at that location, create/drop the DB with a one-liner through the venv's Python and sqlalchemy against the `postgres` maintenance DB instead — autocommit `CREATE DATABASE`.)
Expected: `upgrade  7c3d9e5f1a2b -> d4f8c2e6a9b1` with no error. Backfill is a no-op on the empty DB; its SQL is still parsed/executed.

- [ ] **Step 7: Run the full backend suite + lint**

Run: `.venv/Scripts/python -m pytest` and `.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .`
Expected: all pass — the Python-side default means every existing `Submission(...)` construction site keeps working.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models.py backend/migrations/versions/d4f8c2e6a9b1_submission_public_uid.py backend/tests/test_submissions.py
git commit -m "feat: add Submission.public_uid (random uuid4 hex, backfilled)"
```

---

### Task 2: Stamp the UID in watermark + certificate

**Files:**
- Modify: `backend/app/stamping.py:49-58` (`build_signed_pdf` signature + docstring + line 88), `backend/app/stamping.py:116-150` (`build_certificate_pdf` signature + line 150)
- Modify: `backend/app/completion.py:169-186` (both call sites)
- Test: `backend/tests/test_stamping.py`

**Interfaces:**
- Consumes: `Submission.public_uid` from Task 1.
- Produces: `build_signed_pdf(..., *, envelope_uid: str, completed_at: datetime)` and `build_certificate_pdf(..., *, submission_title: str, envelope_uid: str, template_name: str, is_adhoc: bool = False)` — the keyword-only `submission_id: int` parameter is **removed** from both (it was display-only; grep confirms `completion.py` holds the only production call sites).

- [ ] **Step 1: Update the tests to expect the UID (failing first)**

In `backend/tests/test_stamping.py`, add a module-level constant next to `COMPLETED_AT`:

```python
ENVELOPE_UID = "4f5c2e91b7a04d3e9c12ab34cd56ef78"
```

Then in **every** `build_signed_pdf(...)` call in the file, replace `submission_id=<n>,` with `envelope_uid=ENVELOPE_UID,`, and in every `build_certificate_pdf(...)` call replace `submission_id=<n>,` with `envelope_uid=ENVELOPE_UID,`. Update the assertions that check the stamped text:

- `test_build_signed_pdf_watermarks_every_document_page` (line ~182): replace `assert "Envelope #99" in text` with:

```python
        assert f"Envelope {ENVELOPE_UID}" in text
        assert "Envelope #" not in text
```

- `test_build_signed_pdf_watermarks_unusually_small_page_without_raising` (line ~200): replace `assert "Envelope #7" in reader.pages[0].extract_text()` with:

```python
    assert f"Envelope {ENVELOPE_UID}" in reader.pages[0].extract_text()
```

- `test_build_certificate_pdf_contains_signers_and_audit_trail` (line ~119): replace `assert "42" in cert_text` with:

```python
    assert f"(Envelope {ENVELOPE_UID})" in cert_text
```

  Note: pypdf's `extract_text()` can wrap long lines; if the parenthesized assertion proves flaky, assert `ENVELOPE_UID in cert_text` instead — the UID itself is the requirement.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_stamping.py -v`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'envelope_uid'` on every updated test.

- [ ] **Step 3: Update `stamping.py`**

In `build_signed_pdf`: change the keyword-only parameter `submission_id: int` to `envelope_uid: str`, change line 88 to:

```python
    watermark_text = f"Pumasi Sign · Envelope {envelope_uid} · Completed {_iso(completed_at)}"
```

and update the docstring line mentioning `Envelope #<id>` to `Envelope <uid>`, noting the UID is `Submission.public_uid` (random, so the stamp doesn't reveal envelope volume).

In `build_certificate_pdf`: change the keyword-only parameter `submission_id: int` to `envelope_uid: str` and change line 150 to:

```python
    for line in _wrap(f"Submission: {submission_title} (Envelope {envelope_uid})", 95):
```

- [ ] **Step 4: Update `completion.py` call sites**

In `_build_and_save_signed_pdf` (lines 169–186): replace `submission_id=submission.id,` with `envelope_uid=submission.public_uid,` in **both** the `build_signed_pdf` and `build_certificate_pdf` calls. Storage keys (`_signed_pdf_key(submission.id)` etc.) are unchanged — they're internal.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_stamping.py tests/test_signing.py tests/test_submissions.py -v`
Expected: PASS (test_signing/test_submissions exercise the completion path end-to-end).

- [ ] **Step 6: Full suite + lint**

Run: `.venv/Scripts/python -m pytest` and `.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/stamping.py backend/app/completion.py backend/tests/test_stamping.py
git commit -m "feat: stamp random envelope UID in watermark/certificate, not sequential ID"
```

---

### Task 3: Expose `public_uid` in the API

**Files:**
- Modify: `backend/app/schemas.py:182-197` (`SubmissionOut`)
- Test: `backend/tests/test_submissions.py`

**Interfaces:**
- Consumes: `Submission.public_uid` (Task 1).
- Produces: `SubmissionOut.public_uid: str` — present in every submission response (list, detail, create). Task 4's frontend types mirror this.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_submissions.py`:

```python
def test_submission_response_includes_public_uid(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """API responses expose the random public_uid so the stamped ID can be looked up."""
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "UID exposure",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert re.fullmatch(r"[0-9a-f]{32}", created["public_uid"])

    fetched = admin_client.get(f"/api/submissions/{created['id']}").json()
    assert fetched["public_uid"] == created["public_uid"]
```

(`_me_id`, `_upload_template`, and `import re` are already in place after Task 1.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_submissions.py::test_submission_response_includes_public_uid -v`
Expected: FAIL with `KeyError: 'public_uid'`.

- [ ] **Step 3: Add the field to `SubmissionOut`**

In `backend/app/schemas.py`, inside `SubmissionOut` directly under `id: int`:

```python
    public_uid: str
```

(`from_attributes=True` picks it up from the ORM object; no router changes needed.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_submissions.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + lint, then commit**

Run: `.venv/Scripts/python -m pytest` and `.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .`
Expected: all pass.

```bash
git add backend/app/schemas.py backend/tests/test_submissions.py
git commit -m "feat: expose submission public_uid in API responses"
```

---

### Task 4: Show the UID on the envelope detail page

**Files:**
- Modify: `frontend/src/types.ts:88-101` (`SubmissionOut` interface)
- Modify: `frontend/src/views/EnvelopeDetailView.vue:213-215` (metadata line under the title)

**Interfaces:**
- Consumes: `SubmissionOut.public_uid: string` from Task 3.

- [ ] **Step 1: Add the field to the TS interface**

In `frontend/src/types.ts`, inside `interface SubmissionOut` directly under `id: number;`:

```typescript
  /** Random ID stamped on the signed PDF's watermark and certificate. */
  public_uid: string;
```

- [ ] **Step 2: Display it on the detail page**

In `frontend/src/views/EnvelopeDetailView.vue`, directly after the "Sent by …" metadata line (`:213-215`, the `text-body-2` block ending `· completed {{ formatDateTime(submission.completed_at) }}`), add a second metadata line:

```html
      <div class="text-body-2 text-medium-emphasis mt-1">
        Envelope ID: <span class="font-mono">{{ submission.public_uid }}</span>
        <v-btn
          icon="mdi-content-copy"
          size="x-small"
          variant="text"
          density="comfortable"
          aria-label="Copy envelope ID"
          @click="copyUid"
        />
      </div>
```

and in the `<script setup>` section add:

```typescript
async function copyUid(): Promise<void> {
  if (submission.value) await navigator.clipboard.writeText(submission.value.public_uid);
}
```

Check how the component references the loaded submission (`submission.value` vs a different ref name) and match it. If the project has no `font-mono` utility class, use `style="font-family: monospace"` on the span instead — check for existing monospace usage first and copy that idiom.

- [ ] **Step 3: Type-check and build**

Run (from `frontend/`): `npx vue-tsc --noEmit` then `npm run build`
Expected: both clean. (If `node_modules` is missing in this worktree, run `npm ci` first — per project convention worktrees get a fresh `npm ci`.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types.ts frontend/src/views/EnvelopeDetailView.vue
git commit -m "feat: show envelope public UID on detail page"
```

---

### Task 5: Final verification

- [ ] **Step 1: Backend suite + lint** — from `backend/`: `.venv/Scripts/python -m pytest` and `.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .` — all pass.
- [ ] **Step 2: Frontend** — from `frontend/`: `npx vue-tsc --noEmit` and `npm run build` — clean.
- [ ] **Step 3: Grep guard** — `grep -rn "Envelope #" backend/app frontend/src` returns nothing (the sequential form is gone from production code).
- [ ] **Step 4: Push and open draft PR** — push the worktree branch, `gh pr create --draft` summarizing spec + implementation.
