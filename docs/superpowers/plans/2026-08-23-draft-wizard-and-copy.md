# Draft Wizard Re-entry, DocuSign "Copy", and Draft Bug Sweep — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drafts (including copies of envelopes) reopen in the full Send wizard with everything editable; "Copy" matches DocuSign (standalone draft carrying signer-entered values as prefills); ten audited draft-path bugs are fixed.

**Architecture:** Recreate-on-save — the wizard hydrates from a draft, and Save/Send run the existing `POST /api/submissions/adhoc` create path, then delete the superseded draft client-side. No new endpoints, no migrations. The Copy endpoints always deep-clone into an ad-hoc template so copies are standalone and prefills have a private home.

**Tech Stack:** FastAPI + SQLAlchemy + pytest (Postgres on :5433 required); Vue 3 + Vuetify + vitest; Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-08-23-draft-wizard-and-duplicate-design.md`

## Global Constraints

- The feature's user-facing and code name is **"Copy"** (buttons, toasts, endpoints `POST /api/submissions/{id}/copy` and `POST /api/templates/{id}/copy`, audit detail key `copied_from_submission_id`). Old audit rows keep `duplicated_from_submission_id`; nothing reads either key, so no dual-read.
- Backend tests are Postgres-only; run from `backend/` with `.\.venv\Scripts\python -m pytest`. Start Docker Desktop + `docker start sign-test-pg` if :5433 is down.
- `tests/test_external_signing.py::test_request_code_survives_mail_failure_under_dev_bypass` fails on `main` locally — pre-existing, ignore it; every other test must pass.
- Lint: `.\.venv\Scripts\python -m ruff check .` and `ruff format --check .` from `backend/`; frontend type-check via `npm run build` (vue-tsc) from `frontend/`.
- vue-tsc does NOT catch unimported identifiers used only in `<template>` — every identifier you add to a Vue template must be verified present in that SFC's `<script setup>`.
- Copied prefills: only field types `text`, `dropdown`, `radio`, `checkbox`; never `signature`, `initials`, `date`, `name`, `attachment`, `label`. Checkbox prefill representation is the string `"true"`.
- Drafts must never be visible to their would-be recipients until sent.

---

### Task 1: Rename duplicate → copy (backend + frontend + tests)

Purely mechanical rename; behavior unchanged. PR #68 shipped `/duplicate`; the SPA is the only client and ships with the backend, so renaming is safe.

**Files:**
- Modify: `backend/app/routers/submissions.py` (route `"/{submission_id}/duplicate"`, function `duplicate_submission`, `created_detail={"duplicated_from_submission_id": source.id}`)
- Modify: `backend/app/routers/templates.py` (route `"/{template_id}/duplicate"`, function `duplicate_template`)
- Modify: `backend/tests/test_submissions.py` (the `# --- duplicate ---` section: URLs and the audit-key assertion; keep test names but s/duplicate/copy/)
- Modify: `backend/tests/test_templates.py` (the `# --- duplicate ---` section: URLs; s/duplicate/copy/ in names)
- Modify: `frontend/src/views/EnvelopeDetailView.vue` (`duplicateEnvelope` handler: URL + button label "Duplicate" → "Copy", toast)
- Modify: `frontend/src/views/TemplatesView.vue` (`duplicateTemplate` handler: URL + button label)

**Interfaces:**
- Produces: `POST /api/submissions/{id}/copy` → 201 `SubmissionOut` (draft); `POST /api/templates/{id}/copy` → 201 `TemplateOut`; audit detail key `copied_from_submission_id`. Frontend handlers renamed `copyEnvelope` / `copyTemplate`. Later tasks use these names.

- [ ] **Step 1: Update the backend tests to the new paths/keys (failing first).** In `backend/tests/test_submissions.py`, in every test of the duplicate section change `f"/api/submissions/{...}/duplicate"` → `f"/api/submissions/{...}/copy"`, rename `test_duplicate_*` → `test_copy_*`, and change the audit assertion to `event.detail["copied_from_submission_id"] == created["id"]`. In `backend/tests/test_templates.py` likewise: `/duplicate` → `/copy`, `test_duplicate_*` → `test_copy_*`.

- [ ] **Step 2: Run to verify they fail.**
Run (from `backend/`): `.\.venv\Scripts\python -m pytest tests\test_submissions.py tests\test_templates.py -q -k copy`
Expected: every renamed test FAILS (404/405 — route doesn't exist yet).

- [ ] **Step 3: Rename the backend routes.** In `backend/app/routers/submissions.py`: decorator → `@router.post("/{submission_id}/copy", response_model=SubmissionOut, status_code=201)`, function → `def copy_submission(`, docstring first line → `"""DocuSign-style "Copy": a new draft with the source's document,` and `created_detail={"copied_from_submission_id": source.id},`. In `backend/app/routers/templates.py`: decorator → `@router.post("/{template_id}/copy", response_model=TemplateOut, status_code=201)`, function → `def copy_template(`.

- [ ] **Step 4: Run to verify green.**
Run: `.\.venv\Scripts\python -m pytest tests\test_submissions.py tests\test_templates.py -q`
Expected: PASS (all).

- [ ] **Step 5: Rename the frontend.** In `frontend/src/views/EnvelopeDetailView.vue`: rename `duplicating` → `copying`, `duplicateEnvelope` → `copyEnvelope`, URL → `` `/submissions/${submission.value.id}/copy` ``, toast → `"Copy created as a draft."`, button text `Duplicate` → `Copy` (keep `prepend-icon="mdi-content-duplicate"`), and update the `@click`/`:loading` bindings to the new names. In `frontend/src/views/TemplatesView.vue`: rename `duplicatingId` → `copyingId`, `duplicateTemplate` → `copyTemplate`, URL → `` `/templates/${template.id}/copy` ``, button text → `Copy`, bindings updated.

- [ ] **Step 6: Type-check.**
Run (from `frontend/`): `npm run build`
Expected: success. Also manually confirm both templates reference only renamed identifiers (vue-tsc won't catch template-only mistakes).

- [ ] **Step 7: Commit.**
```bash
git add backend/app/routers/submissions.py backend/app/routers/templates.py backend/tests/test_submissions.py backend/tests/test_templates.py frontend/src/views/EnvelopeDetailView.vue frontend/src/views/TemplatesView.vue
git commit -m "refactor: rename duplicate to Copy (DocuSign terminology)"
```

---

### Task 2: Copy always produces a standalone ad-hoc draft

**Files:**
- Modify: `backend/app/routers/submissions.py` (`copy_submission`: drop the `if template.is_adhoc` conditional)
- Test: `backend/tests/test_submissions.py`

**Interfaces:**
- Consumes: `clone_template(db, settings, source, *, owner_id, name, is_adhoc)` from `app.routers.templates` (already imported).
- Produces: every copy's `SubmissionOut.template.id` differs from the source's; the clone has `is_adhoc=True`. Task 3 mutates this clone's fields.

- [ ] **Step 1: Write the failing test** (in the copy section of `test_submissions.py`):
```python
def test_copy_of_template_envelope_is_standalone(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """Copies detach from reusable templates so editing them can't touch the original."""
    from app.models import Template

    template_id = _upload_template(admin_client, ["Signer 1"])
    created = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "From template",
            "signers": [{"role": "Signer 1", "user_id": _me_id(user_client)}],
        },
    ).json()

    body = admin_client.post(f"/api/submissions/{created['id']}/copy").json()

    assert body["template"]["id"] != template_id
    clone = db.get(Template, body["template"]["id"])
    source = db.get(Template, template_id)
    assert clone.is_adhoc is True
    assert clone.fields == source.fields
    assert clone.pdf_key != source.pdf_key
```
Also update the existing `test_copy_envelope_creates_draft_copy` assertion `assert body["template"]["id"] == template_id` → `assert body["template"]["id"] != template_id`.

- [ ] **Step 2: Run to verify it fails.**
Run: `.\.venv\Scripts\python -m pytest tests\test_submissions.py -q -k "copy_of_template_envelope or copy_envelope_creates"`
Expected: the new test FAILS (`template.id == template_id`).

- [ ] **Step 3: Implement.** In `copy_submission`, replace:
```python
    template = source.template
    if template.is_adhoc:
        template = clone_template(
            db,
            settings,
            template,
            owner_id=sender.id,
            name=template.name,
            is_adhoc=True,
        )
```
with:
```python
    # Every copy is standalone (DocuSign behavior): a deep ad-hoc clone,
    # never a reference — so editing the copy can't touch a reusable
    # template, and value-prefills (below) have a private home.
    template = clone_template(
        db,
        settings,
        source.template,
        owner_id=sender.id,
        name=source.template.name,
        is_adhoc=True,
    )
```

- [ ] **Step 4: Run the copy tests.**
Run: `.\.venv\Scripts\python -m pytest tests\test_submissions.py tests\test_templates.py -q`
Expected: PASS.

- [ ] **Step 5: Commit.**
```bash
git add backend/app/routers/submissions.py backend/tests/test_submissions.py
git commit -m "feat: envelope Copy always detaches into a standalone ad-hoc draft"
```

---

### Task 3: Copy carries signer-entered values as field prefills

**Files:**
- Modify: `backend/app/routers/submissions.py` (new helper `_fields_with_copied_values`, called from `copy_submission`)
- Test: `backend/tests/test_submissions.py`

**Interfaces:**
- Consumes: the ad-hoc `template` clone from Task 2 (`template.fields` is a `list[dict]`); `source.submitters` (each has `.role`, `.values: dict[str, Any]`).
- Produces: `_fields_with_copied_values(fields: list[dict], values_by_role: dict[str, dict]) -> list[dict]` — pure, returns a new list. Copies into `default_value`: `text` (str, clamped to 500 chars), `dropdown`/`radio` (str that is one of the field's `options`), `checkbox` (`True` → `"true"`). Everything else untouched.

- [ ] **Step 1: Write the failing test:**
```python
def test_copy_carries_entered_values_as_prefills(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """DocuSign-style: text/dropdown/radio/checkbox survive the copy as prefills;
    signature/date/name (auto-filled or non-copyable) do not."""
    from app.models import Submitter, Template

    user_id = _me_id(user_client)
    fields = [
        {"id": "sig", "type": "signature", "role": "Signer 1", "page": 0,
         "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.05, "required": True},
        {"id": "txt", "type": "text", "role": "Signer 1", "page": 0,
         "x": 0.1, "y": 0.2, "w": 0.2, "h": 0.05, "required": False},
        {"id": "dd", "type": "dropdown", "role": "Signer 1", "page": 0,
         "x": 0.1, "y": 0.3, "w": 0.2, "h": 0.05, "required": False,
         "options": ["A", "B"]},
        {"id": "cb", "type": "checkbox", "role": "Signer 1", "page": 0,
         "x": 0.1, "y": 0.4, "w": 0.05, "h": 0.05, "required": False},
        {"id": "dt", "type": "date", "role": "Signer 1", "page": 0,
         "x": 0.1, "y": 0.5, "w": 0.2, "h": 0.05, "required": False},
    ]
    import json
    resp = admin_client.post(
        "/api/submissions/adhoc",
        data={
            "title": "Values source",
            "signers_json": f'[{{"role": "Signer 1", "user_id": {user_id}}}]',
            "fields_json": json.dumps(fields),
        },
        files={"file": ("sample.pdf", (FIXTURES / "sample.pdf").read_bytes(), "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    source = resp.json()
    # Simulate the signer having filled things in.
    submitter = db.get(Submitter, source["submitters"][0]["id"])
    submitter.values = {"sig": "sig-1", "txt": "hello world", "dd": "B", "cb": True, "dt": "2026-08-23"}
    db.commit()

    body = admin_client.post(f"/api/submissions/{source['id']}/copy").json()

    copied = {f["id"]: f for f in db.get(Template, body["template"]["id"]).fields}
    assert copied["txt"]["default_value"] == "hello world"
    assert copied["dd"]["default_value"] == "B"
    assert copied["cb"]["default_value"] == "true"
    assert copied["sig"].get("default_value") in (None, "")
    assert copied["dt"].get("default_value") in (None, "")


def test_copy_ignores_invalid_or_foreign_values(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """A dropdown value not among the options, and values belonging to a
    different role's submitter, are not copied."""
    from app.models import Submitter, Template

    user_id = _me_id(user_client)
    fields = [
        {"id": "dd", "type": "dropdown", "role": "Signer 1", "page": 0,
         "x": 0.1, "y": 0.3, "w": 0.2, "h": 0.05, "required": False,
         "options": ["A", "B"]},
    ]
    import json
    source = admin_client.post(
        "/api/submissions/adhoc",
        data={
            "title": "Bad values source",
            "signers_json": f'[{{"role": "Signer 1", "user_id": {user_id}}}]',
            "fields_json": json.dumps(fields),
        },
        files={"file": ("sample.pdf", (FIXTURES / "sample.pdf").read_bytes(), "application/octet-stream")},
    ).json()
    submitter = db.get(Submitter, source["submitters"][0]["id"])
    submitter.values = {"dd": "Z"}  # not an option
    db.commit()

    body = admin_client.post(f"/api/submissions/{source['id']}/copy").json()

    copied = {f["id"]: f for f in db.get(Template, body["template"]["id"]).fields}
    assert copied["dd"].get("default_value") in (None, "")
```

- [ ] **Step 2: Run to verify both fail.**
Run: `.\.venv\Scripts\python -m pytest tests\test_submissions.py -q -k "carries_entered or invalid_or_foreign"`
Expected: FAIL (`default_value` is None).

- [ ] **Step 3: Implement.** In `backend/app/routers/submissions.py`, add above `copy_submission`:
```python
# Field types whose signer-entered values a Copy carries forward as
# editable prefills (DocuSign behavior). Signature/initials are personal,
# date/name auto-fill at signing, attachments are files — none copy.
_COPYABLE_VALUE_TYPES = {"text", "dropdown", "radio", "checkbox"}
_PREFILL_MAX_LENGTH = 500  # FieldDef.default_value's limit


def _fields_with_copied_values(fields: list[dict], values_by_role: dict[str, dict]) -> list[dict]:
    """Return a copy of ``fields`` with signer-entered values as ``default_value`` prefills."""
    result = []
    for field in fields:
        field = dict(field)
        value = values_by_role.get(field.get("role", ""), {}).get(field["id"])
        if field.get("type") in _COPYABLE_VALUE_TYPES and value is not None:
            if field["type"] == "checkbox":
                if value is True:
                    field["default_value"] = "true"
            elif field["type"] in ("dropdown", "radio"):
                if isinstance(value, str) and value in (field.get("options") or []):
                    field["default_value"] = value
            elif isinstance(value, str) and value.strip():
                field["default_value"] = value[:_PREFILL_MAX_LENGTH]
        result.append(field)
    return result
```
Then in `copy_submission`, right after the `clone_template(...)` call, add:
```python
    values_by_role = {s.role: s.values for s in source.submitters if not s.is_cc}
    template.fields = _fields_with_copied_values(template.fields, values_by_role)
```
(Reassigning `template.fields` — not mutating in place — is required for SQLAlchemy to detect the JSONB change.)

- [ ] **Step 4: Run to verify green, plus the whole submissions file.**
Run: `.\.venv\Scripts\python -m pytest tests\test_submissions.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit.**
Run: `.\.venv\Scripts\python -m ruff check . --fix; .\.venv\Scripts\python -m ruff format .`
```bash
git add backend/app/routers/submissions.py backend/tests/test_submissions.py
git commit -m "feat: Copy carries signer-entered values as field prefills"
```

---

### Task 4: Draft access control — drafts are sender/admin-only until sent

**Files:**
- Modify: `backend/app/routers/submissions.py:491-513` (`_get_submission_authorized`)
- Modify: `backend/app/routers/files.py` (`get_document_preview` ~line 216; `get_template_pdf` ~line 100)
- Test: `backend/tests/test_drafts.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: for `status == "draft"`, `GET /api/submissions/{id}`, `GET /api/submissions/{id}/events`, `GET /api/files/document-preview/{id}`, and the submitter-arm of `GET /api/files/template-pdf/{tid}` all 403 anyone who is merely a listed submitter. Sender (and admin where already admitted) unchanged.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_drafts.py`; reuse that file's existing helpers for creating a draft — read the file first and follow its patterns for creating a draft addressed to `user_client`):
```python
def test_draft_hidden_from_recipient_by_direct_url(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """A would-be recipient must not read an unsent draft via any direct URL."""
    draft = _make_draft(admin_client, user_client)  # use/adapt this file's existing draft factory
    template_id = draft["template"]["id"]

    assert user_client.get(f"/api/submissions/{draft['id']}").status_code == 403
    assert user_client.get(f"/api/submissions/{draft['id']}/events").status_code == 403
    assert user_client.get(f"/api/files/document-preview/{draft['id']}").status_code == 403
    assert user_client.get(f"/api/files/template-pdf/{template_id}").status_code == 403

    # The sender still sees everything.
    assert admin_client.get(f"/api/submissions/{draft['id']}").status_code == 200
    assert admin_client.get(f"/api/files/document-preview/{draft['id']}").status_code == 200

    # Once sent, the recipient regains access.
    assert admin_client.post(f"/api/submissions/{draft['id']}/send").status_code == 200
    assert user_client.get(f"/api/submissions/{draft['id']}").status_code == 200
    assert user_client.get(f"/api/files/document-preview/{draft['id']}").status_code == 200
```
If `test_drafts.py` has no reusable draft factory, define `_make_draft` in the test module: `_upload_template`-style template create + `POST /api/submissions` with `"draft": true` and the user as Signer 1 (copy the shape used elsewhere in that file).

- [ ] **Step 2: Run to verify it fails.**
Run: `.\.venv\Scripts\python -m pytest tests\test_drafts.py -q -k hidden_from_recipient`
Expected: FAIL (200 != 403 on the first assertion).

- [ ] **Step 3: Implement.**
In `_get_submission_authorized` (`submissions.py`), change the final check to:
```python
    is_sender = submission.created_by == user.id
    is_submitter = any(s.user_id == user.id for s in submission.submitters)
    # Drafts are invisible to their would-be recipients until sent — being
    # listed on an unsent draft grants nothing.
    if submission.status == "draft":
        is_submitter = False
    if not (is_sender or is_submitter):
        raise HTTPException(status_code=403, detail="Forbidden")
```
In `files.py` `get_document_preview`, extend the session-user branch:
```python
    if user is not None:
        is_sender = submission.created_by == user.id
        # Unsent drafts are sender-only (recipients haven't been notified).
        if submission.status == "draft" and not is_sender:
            raise HTTPException(status_code=403, detail="Forbidden")
        if not is_sender and not _is_submitter(db, submission_id=submission_id, user_id=user.id):
            raise HTTPException(status_code=403, detail="Forbidden")
```
In `files.py` `get_template_pdf`, find the `party_on_template` query and add a status condition so a *submitter* qualifies only through non-draft submissions while a *sender* qualifies through any of their own (read the actual query first; the shape is an outerjoin of Submitter on Submission filtered by template id). Express it as:
```python
            party_on_template = db.scalar(
                select(Submission.id)
                .outerjoin(Submitter, Submitter.submission_id == Submission.id)
                .where(
                    Submission.template_id == template_id,
                    or_(
                        Submission.created_by == user.id,
                        and_(Submitter.user_id == user.id, Submission.status != "draft"),
                    ),
                )
                .limit(1),
            )
```
(adjust imports: `and_` from sqlalchemy if not present; keep the rest of the function unchanged).

- [ ] **Step 4: Run the draft + files + submissions suites.**
Run: `.\.venv\Scripts\python -m pytest tests\test_drafts.py tests\test_submissions.py tests\test_files.py -q`
Expected: PASS (if `tests\test_files.py` doesn't exist, run the whole suite instead).

- [ ] **Step 5: Commit.**
```bash
git add backend/app/routers/submissions.py backend/app/routers/files.py backend/tests/test_drafts.py
git commit -m "fix: unsent drafts are sender-only — close direct-URL access for recipients"
```

---

### Task 5: Send-draft re-validation + delete_draft docstring

**Files:**
- Modify: `backend/app/routers/submissions.py` (`send_draft` ~line 1074; `delete_draft` docstring ~line 1131)
- Test: `backend/tests/test_drafts.py`

**Interfaces:**
- Consumes: `_validate_role_mapping(template, signers)` and `SignerIn` (both already in the module).
- Produces: `POST /{id}/send` returns the same 422s as create when the template's current fields no longer validate against the draft's signers.

- [ ] **Step 1: Write the failing test:**
```python
def test_send_draft_revalidates_fields(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """Fields emptied between save and send must 422, not dispatch an unsignable envelope."""
    draft = _make_draft(admin_client, user_client)
    template_id = draft["template"]["id"]

    # Gut the template's fields after the draft was saved.
    resp = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": [], "roles": []})
    assert resp.status_code == 200, resp.text

    send = admin_client.post(f"/api/submissions/{draft['id']}/send")

    assert send.status_code == 422
    assert send.json()["detail"]
```

- [ ] **Step 2: Run to verify it fails.**
Run: `.\.venv\Scripts\python -m pytest tests\test_drafts.py -q -k revalidates`
Expected: FAIL (200 != 422).

- [ ] **Step 3: Implement.** In `send_draft`, move the `submitters` fetch up and validate before flipping the status. Replace:
```python
    submission.status = "pending"
    ip = client_ip(request)
    submitters = db.scalars(
        select(Submitter).where(Submitter.submission_id == submission_id).order_by(Submitter.id),
    ).all()
```
with:
```python
    submitters = db.scalars(
        select(Submitter).where(Submitter.submission_id == submission_id).order_by(Submitter.id),
    ).all()
    # Re-validate against the template's *current* fields: they may have
    # changed since the draft was saved, and dispatching an envelope whose
    # signers have nothing to sign is the exact condition create rejects.
    template = db.get(Template, submission.template_id)
    signer_inputs = [
        SignerIn(role=s.role, user_id=s.user_id, order=s.order_index, is_cc=s.is_cc) for s in submitters
    ]
    try:
        _validate_role_mapping(template, signer_inputs)
    except HTTPException:
        db.rollback()
        raise

    submission.status = "pending"
    ip = client_ip(request)
```
Then append to `delete_draft`'s docstring (after "…voided instead (the trail is the record).")):
```
    Deliberately looser than send/correct (which require the sender to still
    hold ``can_send``): a revoked sender may still clean up their own unsent
    drafts — deletion sends nothing and alters no record anyone else has.
```

- [ ] **Step 4: Run the full backend suite.**
Run: `.\.venv\Scripts\python -m pytest -q`
Expected: only the known pre-existing `test_request_code_survives_mail_failure_under_dev_bypass` failure.

- [ ] **Step 5: Commit.**
```bash
git add backend/app/routers/submissions.py backend/tests/test_drafts.py
git commit -m "fix: send-draft revalidates role/field mapping; document delete_draft's looser gate"
```

---

### Task 6: Frontend helper bug fixes — labels, Inbox leak, expiry caption

**Files:**
- Modify: `frontend/src/utils/labels.ts` (`signerStatusLabel`, ~line 23)
- Modify: `frontend/src/utils/envelopes.ts` (`inView`, ~line 91)
- Modify: `frontend/src/components/EnvelopeBrowser.vue` (`expiryHint` ~line 155; signer chip call site)
- Modify: `frontend/src/views/EnvelopeDetailView.vue` (signer chip ~line 720; `ccStatusLabel` ~line 96)
- Test: `frontend/src/utils/labels.spec.ts`, `frontend/src/utils/envelopes.spec.ts`

**Interfaces:**
- Produces: `signerStatusLabel(status: SubmitterStatus, envelopeStatus?: SubmissionStatus): string` — returns `"Not sent yet"` when `envelopeStatus === "draft"` and the signer hasn't completed. `inView(row, "inbox")` excludes drafts.

- [ ] **Step 1: Write the failing vitest cases.** In `labels.spec.ts` add:
```typescript
it('labels a draft signer "Not sent yet", not "Sent"', () => {
  expect(signerStatusLabel("pending", "draft")).toBe("Not sent yet");
  expect(signerStatusLabel("pending", "pending")).toBe("Sent");
  expect(signerStatusLabel("pending")).toBe("Sent");
});
```
In `envelopes.spec.ts` add (follow that file's existing row-building helpers; if it builds rows from fixture `SubmissionOut` objects, reuse them):
```typescript
it("keeps unsent drafts out of the Inbox even when the sender is a recipient", () => {
  const row = makeRow({ status: "draft", senderIsMe: true, iAmRecipient: true });
  expect(inView(row, "inbox")).toBe(false);
  expect(inView(row, "drafts")).toBe(true);
});
```
(Adapt `makeRow` to the spec file's existing fixture pattern — read it first; if none exists, construct a minimal `EnvelopeRow` literal.)

- [ ] **Step 2: Run to verify they fail.**
Run (from `frontend/`): `npm run test:unit`
Expected: the two new cases FAIL.

- [ ] **Step 3: Implement the helpers.** `labels.ts`:
```typescript
/** Signer-status chip label: what a sender wants to know at a glance.
 *  Pass the envelope's status so a draft's untouched signers read
 *  "Not sent yet" instead of the post-send "Sent". */
export function signerStatusLabel(status: SubmitterStatus, envelopeStatus?: SubmissionStatus): string {
  if (status === "completed") return "Signed";
  if (status === "opened") return "Opened";
  if (status === "declined") return "Declined";
  if (envelopeStatus === "draft") return "Not sent yet";
  return "Sent";
}
```
`envelopes.ts` line 91:
```typescript
  // Inbox is things sent *to* you — a draft was sent to nobody, including
  // a sender who addressed themselves.
  if (key === "inbox") return row.isRecipient && row.submission.status !== "draft";
```

- [ ] **Step 4: Update the call sites.** In `EnvelopeDetailView.vue` line ~721: `{{ signerStatusLabel(signer.status, submission.status) }}`. In `EnvelopeBrowser.vue`, find the signer chip that calls `signerStatusLabel(...)` (search the file) and pass the row's envelope status the same way. In `EnvelopeDetailView.vue` `ccStatusLabel` add a draft branch:
```typescript
function ccStatusLabel(cc: SubmissionOut["submitters"][number]): string {
  if (submission.value?.status === "completed") return "Received signed PDF";
  if (submission.value?.status === "draft") return "Not sent yet";
  if (cc.email_status != null) return "Copy sent";
  return "Copy queued";
}
```
In `EnvelopeBrowser.vue` `expiryHint`:
```typescript
/** "Expires <date>" caption for open envelopes and drafts with a deadline —
 *  a draft's (possibly past) deadline will gate its own Send. */
function expiryHint(row: Row): string | null {
  const s = row.submission;
  if ((s.status !== "pending" && s.status !== "draft") || !s.expires_at) return null;
  return `Expires ${formatDate(s.expires_at)}`;
}
```

- [ ] **Step 5: Run vitest + build.**
Run: `npm run test:unit` then `npm run build`
Expected: all green.

- [ ] **Step 6: Commit.**
```bash
git add frontend/src/utils/labels.ts frontend/src/utils/labels.spec.ts frontend/src/utils/envelopes.ts frontend/src/utils/envelopes.spec.ts frontend/src/components/EnvelopeBrowser.vue frontend/src/views/EnvelopeDetailView.vue
git commit -m "fix: draft-aware labels, Inbox excludes drafts, draft rows show expiry"
```

---

### Task 7: Draft dead-ends — hide Resend, draft-aware dialog copy

**Files:**
- Modify: `frontend/src/views/EnvelopeDetailView.vue` (resend menu item ~line 735; replace-signer dialog ~line 929; replace-document dialog ~line 838 and its toast ~line 310)

**Interfaces:** none new (template/copy changes only).

- [ ] **Step 1: Hide Resend on drafts.** On the resend `v-list-item` (~line 735) add `v-if="!isDraft"`:
```html
                      <v-list-item
                        v-if="!isDraft"
                        prepend-icon="mdi-email-sync-outline"
                        :title="signer.email_status === 'failed' ? 'Resend invite (bounced)…' : 'Resend invite…'"
                        :disabled="resendingId === signer.id"
                        @click="resendInvite(signer)"
                      />
```

- [ ] **Step 2: Draft-aware replace-signer dialog body.** Find the dialog text (~line 929) that reads `Replacing "…" sends a fresh sign request to the new signer and invalidates the old signing link.` and wrap it:
```html
          <template v-if="isDraft">
            Replacing "{{ replaceTarget?.user.name }}" updates who will be asked to sign when you
            send this draft. Nothing is emailed until then.
          </template>
          <template v-else>
            Replacing "{{ replaceTarget?.user.name }}" sends a fresh sign request to the new signer
            and invalidates the old signing link.
          </template>
```
(Read the dialog first and keep its exact interpolation variable — if the name variable differs from `replaceTarget`, use the real one.)

- [ ] **Step 3: Draft-aware replace-document copy.** Dialog body (~line 838): keep the existing text for pending, add a draft variant:
```html
          <p class="text-body-2 text-medium-emphasis mb-3">
            <template v-if="isDraft">
              The new file replaces this draft's document; all signature fields keep their current
              positions. Nobody is notified — the draft hasn't been sent.
            </template>
            <template v-else>
              The new file replaces the document for everyone; all signature fields keep their
              current positions. Only possible while nobody has signed yet.
            </template>
          </p>
```
And the toast in the replace handler (~line 310):
```typescript
    ui.toast(isDraft.value ? "Document replaced in the draft." : "Document replaced — signers will see the new version.");
```

- [ ] **Step 4: Build.**
Run: `npm run build`
Expected: success; manually re-check the template only uses identifiers that exist in the script (`isDraft` exists at ~line 47).

- [ ] **Step 5: Commit.**
```bash
git add frontend/src/views/EnvelopeDetailView.vue
git commit -m "fix: no Resend on drafts; replace-signer/document dialogs stop claiming emails on drafts"
```

---

### Task 8: SendView draft mode — route + hydration

The wizard learns to load an existing draft. Roles are remapped to the wizard's `signer-N` convention so create-time validation passes on re-save.

**Files:**
- Modify: `frontend/src/router/index.ts` (new route)
- Modify: `frontend/src/views/SendView.vue` (props, hydration)

**Interfaces:**
- Consumes: `GET /api/submissions/{id}` (`SubmissionOut`: `title`, `message`, `status`, `expires_at`, `reminders_enabled`, `reminder_interval_days`, `template.id`, `submitters[]` with `user.id`, `role`, `order_index`, `is_cc`), `GET /api/templates/{id}` (`TemplateOut.fields`), `GET /api/files/template-pdf/{id}` (blob).
- Produces: route name `"send-draft"` at path `/send/draft/:draftId`; `SendView` props `{ templateId?: string; draftId?: string }`; a module-scope `draftSourceId` ref that Task 9 reads in `send()`. Tasks 9–10 navigate with `router.push({ name: "send-draft", params: { draftId: String(id) } })`.

- [ ] **Step 1: Add the route.** In `frontend/src/router/index.ts`, after the `send` route:
```typescript
  {
    path: "/send/draft/:draftId",
    name: "send-draft",
    component: () => import("../views/SendView.vue"),
    props: true,
  },
```

- [ ] **Step 2: Extend SendView props and add hydration.** Change line 36 to:
```typescript
const props = defineProps<{ templateId?: string; draftId?: string }>();
```
Add near the ad-hoc state (~line 128):
```typescript
/** When editing an existing draft: its id — Task "send" deletes it after
 *  the replacement envelope is created (recreate-on-save; see the spec). */
const draftSourceId = ref<number | null>(null);
/** Set when the loaded draft's expiration had already passed. */
const draftExpiryCleared = ref(false);
```
Add this function after `load()` (~line 720), and call it from `load()` when `props.draftId` is set (after templates/users load, instead of the `templateId` branch):
```typescript
/** Hydrate the wizard from an existing draft (recreate-on-save model).
 *  The draft's roles — template names or signer-N — are remapped to this
 *  wizard's own signer-N-by-row-index convention so the fields and the
 *  signers_json the wizard eventually submits agree. */
async function loadDraft(draftId: string): Promise<void> {
  const { data: draft } = await http.get<SubmissionOut>(`/submissions/${draftId}`);
  if (draft.status !== "draft") {
    ui.toast("That envelope is no longer a draft.");
    await router.push({ name: "envelope-detail", params: { id: draftId } });
    return;
  }
  const [{ data: template }, pdfRes] = await Promise.all([
    http.get<TemplateOut>(`/templates/${draft.template.id}`),
    http.get<Blob>(`/files/template-pdf/${draft.template.id}`, { responseType: "blob" }),
  ]);

  mode.value = "adhoc";
  draftSourceId.value = draft.id;
  title.value = draft.title;
  message.value = draft.message ?? "";
  remindersEnabled.value = draft.reminders_enabled;
  reminderInterval.value = draft.reminder_interval_days;
  if (draft.expires_at) {
    const iso = draft.expires_at.slice(0, 10);
    if (iso <= todayIso) {
      draftExpiryCleared.value = true; // deadline already passed — start fresh
    } else {
      expiryDate.value = iso;
    }
  }

  const signers = draft.submitters
    .filter((s) => !s.is_cc)
    .sort((a, b) => a.order_index - b.order_index || a.id - b.id);
  const ccs = draft.submitters.filter((s) => s.is_cc);
  adhocRecipients.value = signers.map((s) => s.user.id);
  adhocOrderNums.value = signers.map((s) => s.order_index + 1);
  ccRows.value = ccs.map((s) => ({ userId: s.user.id, orderNum: s.order_index + 1 }));
  signInOrder.value = draft.submitters.some((s) => s.order_index > 0);

  // Old role name -> this wizard's signer-N for that row.
  const roleMap = new Map(signers.map((s, i) => [s.role, adhocRole(i)]));
  adhocFields.value = template.fields.map((f) => ({
    ...f,
    role: roleMap.get(f.role) ?? f.role,
  }));

  const file = new File([pdfRes.data], `${title.value || "document"}.pdf`, { type: "application/pdf" });
  adhocFile.value = file;
  adhocPdfUrl.value = URL.createObjectURL(file);
  step.value = 1;
}
```
In `load()`, replace the `if (props.templateId) { ... }` block with:
```typescript
    if (props.draftId) {
      await loadDraft(props.draftId);
    } else if (props.templateId) {
      const found = templatesRes.data.find((t) => String(t.id) === props.templateId);
      if (found) {
        selectTemplate(found);
      } else {
        errorMessage.value = "That template couldn't be found (it may have been archived).";
      }
    }
```
Add a hint in the template near the expiry input (the block around line ~1140 with the expiry `v-text-field`): under it insert
```html
                <p v-if="draftExpiryCleared" class="text-caption text-warning mb-0">
                  This draft's previous expiration date had already passed, so it was cleared —
                  pick a new one or leave it empty.
                </p>
```
Import `TemplateOut`/`SubmissionOut` types if not already imported in the SFC (check the existing `import type {...} from "../types"` line — `TemplateOut`, `SubmissionOut`, and `User` are already there).

- [ ] **Step 3: Type-check + template identifier audit.**
Run: `npm run build`
Expected: success. Manually verify `draftExpiryCleared` (used in template) exists in script.

- [ ] **Step 4: Commit.**
```bash
git add frontend/src/router/index.ts frontend/src/views/SendView.vue
git commit -m "feat: Send wizard loads an existing draft (route /send/draft/:draftId)"
```

---

### Task 9: SendView — save/send replaces the old draft

**Files:**
- Modify: `frontend/src/views/SendView.vue` (`send()` ~line 728)

**Interfaces:**
- Consumes: `draftSourceId` from Task 8; `DELETE /api/submissions/{id}` (existing).
- Produces: recreate-on-save behavior; both "Save as draft" and "Send" replace the loaded draft.

- [ ] **Step 1: Implement.** In `send()`, after `created = data;` resolution and *before* the toast block, add:
```typescript
    // Recreate-on-save: the freshly created envelope supersedes the draft we
    // loaded from. Delete it only after the create succeeded; if the delete
    // fails the leftover draft is harmless and user-deletable.
    if (draftSourceId.value !== null) {
      await http.delete(`/submissions/${draftSourceId.value}`).catch(() => {});
      draftSourceId.value = null;
    }
```
Also update the draft toast (line ~791) to reflect editing:
```typescript
    if (asDraft) {
      ui.toast("Draft saved — send it whenever you're ready.");
    }
```
(unchanged text is fine; the important part is the delete above).

- [ ] **Step 2: Build.**
Run: `npm run build`
Expected: success.

- [ ] **Step 3: Commit.**
```bash
git add frontend/src/views/SendView.vue
git commit -m "feat: saving or sending an edited draft replaces the original (recreate-on-save)"
```

---

### Task 10: Entry points + prefill seeding for copied values

**Files:**
- Modify: `frontend/src/views/EnvelopeDetailView.vue` (draft banner ~line 650; `copyEnvelope` navigation)
- Modify: `frontend/src/components/EnvelopeBrowser.vue` (draft row action)
- Modify: `frontend/src/views/SignView.vue` (prefill seeding ~line 106)

**Interfaces:**
- Consumes: route `send-draft` (Task 8); `copyEnvelope` (Task 1).
- Produces: "Edit draft" buttons; Copy lands in the wizard; dropdown/radio/checkbox prefills seed at signing.

- [ ] **Step 1: Draft banner gains "Edit draft" and a past-expiry warning.** Replace the banner (~line 650-667) with:
```html
      <v-alert v-if="isDraft && canManage" type="info" class="mb-4" prominent icon="mdi-file-edit-outline">
        This envelope is a draft — recipients haven't been notified. Edit it to change the
        document, signers, fields, or settings before sending.
        <template v-if="draftExpiryPassed">
          <br />Its expiration date has already passed — edit the draft to set a new one before
          sending.
        </template>
        <template #append>
          <v-btn
            color="primary"
            variant="flat"
            prepend-icon="mdi-pencil"
            :to="{ name: 'send-draft', params: { draftId: String(submission.id) } }"
          >
            Edit draft
          </v-btn>
          <v-btn
            color="primary"
            variant="tonal"
            class="ml-2"
            :loading="sendingDraft"
            :disabled="draftExpiryPassed"
            @click="sendNow"
          >
            Send now
          </v-btn>
          <v-btn
            color="error"
            variant="text"
            class="ml-2"
            :disabled="sendingDraft"
            @click="deleteDraftDialog = true"
          >
            Delete
          </v-btn>
        </template>
      </v-alert>
```
Add to the script (near `isDraft`, ~line 47):
```typescript
/** A draft whose deadline already passed can't be dispatched — the send
 *  endpoint 409s. Editing the draft clears/replaces the date. */
const draftExpiryPassed = computed(
  () =>
    isDraft.value &&
    !!submission.value?.expires_at &&
    new Date(submission.value.expires_at).getTime() <= Date.now(),
);
```

- [ ] **Step 2: Copy lands in the wizard.** In `copyEnvelope` (Task 1's rename), change the navigation from `envelope-detail` to:
```typescript
    ui.toast("Copy created as a draft — review and edit it before sending.");
    await router.push({ name: "send-draft", params: { draftId: String(data.id) } });
```
(and drop the `await load();` that followed — the wizard route unmounts this view).

- [ ] **Step 3: Browser draft rows get "Edit draft".** In `EnvelopeBrowser.vue`, find the draft row's primary "Send" button (~line 344) and add next to it (visible under the same draft condition):
```html
            <v-btn
              size="small"
              variant="text"
              prepend-icon="mdi-pencil"
              :to="{ name: 'send-draft', params: { draftId: String(row.submission.id) } }"
            >
              Edit
            </v-btn>
```
(Read the surrounding block first and match its `v-if` condition and row variable name exactly.)

- [ ] **Step 4: Seed non-text prefills at signing.** In `SignView.vue` (~line 106-116), extend the seeding block:
```typescript
    if (field.type === "checkbox" && !(field.id in fieldValues)) {
      fieldValues[field.id] = field.default_value === "true";
    }
    ...
    // Selects need a real "" to show the Choose… placeholder; a sender/copy
    // prefill wins when it's still one of the options.
    if ((field.type === "dropdown" || field.type === "radio") && !(field.id in fieldValues)) {
      fieldValues[field.id] =
        field.default_value && (field.options ?? []).includes(field.default_value) ? field.default_value : "";
    }
```
(The `...` marks the untouched date/name/text lines between — keep them; only the checkbox line changes from `= false` and the dropdown/radio line gains the default_value branch.)

- [ ] **Step 5: Build + vitest.**
Run: `npm run build` then `npm run test:unit`
Expected: green. Manually verify every new template identifier (`draftExpiryPassed`) exists in script.

- [ ] **Step 6: Commit.**
```bash
git add frontend/src/views/EnvelopeDetailView.vue frontend/src/components/EnvelopeBrowser.vue frontend/src/views/SignView.vue
git commit -m "feat: Edit-draft entry points, Copy opens the wizard, copied prefills seed at signing"
```

---

### Task 11: Playwright e2e — save draft → edit in wizard → send → sign

**Files:**
- Create: `frontend/e2e/draft-edit-flow.spec.ts`

**Interfaces:**
- Consumes: the e2e harness (`frontend/e2e/constants.ts`, existing helpers in `frontend/e2e/sign-flow.spec.ts` — read that file first and reuse its login/compose helpers verbatim where possible).

- [ ] **Step 1: Write the test.** Model it on `sign-flow.spec.ts`'s existing structure (login helper, upload fixture path, field-placement drag). Scenario:
```typescript
import { expect, test } from "@playwright/test";
// reuse the login/compose helpers from sign-flow.spec.ts (import or copy per that file's local conventions)

test("draft can be edited in the wizard and then sent", async ({ page }) => {
  // 1. login as admin, go to /send, upload the sample PDF, add one signer
  //    (the admin themselves), place a signature field, and click "Save as draft".
  // 2. Expect to land on /envelopes/:id with the draft banner; click "Edit draft".
  // 3. Expect the wizard at /send/draft/:id with the title prefilled; change the
  //    title to "Edited draft e2e", advance through steps (document already
  //    loaded), and click "Send".
  // 4. Expect a new envelope id (the old draft was replaced), status In progress,
  //    and the Drafts view no longer lists the old draft.
  // 5. Open /sign/:submitterId, sign the field, Finish; envelope completes.
});
```
Write it fully — the comments above are the storyboard; every step must be real Playwright code following the idioms already used in `sign-flow.spec.ts` (`getByRole`, upload via `setInputFiles`, the drag-to-place pattern with `page.mouse`).

- [ ] **Step 2: Run the e2e suite locally.**
Run (from `frontend/`, after `npm run build`; Docker Postgres must be up, DB `pumasi_sign_e2e` exists): `npx playwright test`
Expected: all specs pass including the new one.

- [ ] **Step 3: Commit.**
```bash
git add frontend/e2e/draft-edit-flow.spec.ts
git commit -m "test: e2e for save-draft, edit-in-wizard, send, sign"
```

---

### Task 12: Full verification, live walkthrough, ship

- [ ] **Step 1: Full backend suite + lint.** From `backend/`: `.\.venv\Scripts\python -m pytest -q` (only the known pre-existing failure allowed), `ruff check .`, `ruff format --check .`.
- [ ] **Step 2: Frontend build + vitest + e2e.** From `frontend/`: `npm run build`, `npm run test:unit`, `npx playwright test`.
- [ ] **Step 3: Live walkthrough** (uvicorn on :8080 with DEV_AUTH_BYPASS per the local recipe; drive with the Playwright browser): copy a sent envelope → verify it opens in the wizard with title/signers/expiry/reminders/fields hydrated → change a signer and move a field → Save as draft → reopen via Edit draft → Send → sign and confirm the copied text prefill appears in the signing view.
- [ ] **Step 4: Update docs.** CLAUDE.md key-facts: mention drafts reopen in the wizard (recreate-on-save) and Copy semantics if the existing wording contradicts it.
- [ ] **Step 5: PR + merge per the user's standing instruction** (push branch, `gh pr create`, merge when green, watch CI on main).
