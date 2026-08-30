# DocuSign-parity Features 1–6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring Pumasi Sign to DocuSign parity on six fronts: envelope expiration, configurable reminders, new field types (dropdown/radio/attachment + text validation), upload-image signatures, draft envelopes, and shared templates.

**Architecture:** Each feature is a vertical slice (migration → model → schema → router → notifications/stamping → frontend) landed as its own commit(s) on branch `worktree-docusign-features-1-6`, stacked on PR #61 (`0dd19d0`). Backend-first with pytest per slice; frontend follows with vue-tsc/build/vitest. Migrations chain from head `e1c5b7a94d20`.

**Tech Stack:** FastAPI + SQLAlchemy 2 + Alembic + Postgres (JSONB/TIMESTAMPTZ, tests Postgres-only), reportlab/pypdf stamping, Vue 3 + Vuetify + vite/vitest.

## Global Constraints

- Tests: main-checkout venv binaries with cwd in worktree `backend/` (`C:\...\pumasi-sign\backend\.venv\Scripts\python.exe -m pytest`); dedicated DB `TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_test_ds16` (create first via `docker exec sign-test-pg psql -U postgres -c "CREATE DATABASE pumasi_sign_test_ds16"`).
- Lint: `ruff check . && ruff format --check .` clean before every commit.
- Frontend: `npm ci --no-audit --no-fund` fresh in worktree; `npx vue-tsc --noEmit`, `npx vitest run`, `npm run build` all green before frontend commits.
- Keep `frontend/src/types.ts` hand-synced with `backend/app/schemas.py`.
- All new mail hooks: called **after** the route's own `db.commit()`, never under a row lock; never raise on mail failure.
- Status/audit-event string sets live in `models.py` (`SUBMISSION_STATUSES`, `AUDIT_EVENTS`) with CHECK constraints — every new status/event needs a migration that recreates the constraint.
- "Envelope" is the user-facing word for submission; voiding language per PR #59/#61.

---

### Task 1: Envelope expiration — backend

**Files:**
- Create: `backend/migrations/versions/f2a6b8c1d4e0_submission_expiration.py` (down_revision `e1c5b7a94d20`)
- Modify: `backend/app/models.py` (SUBMISSION_STATUSES += "expired"; AUDIT_EVENTS += "expired"; `Submission.expires_at`, `Submission.expiry_warned_at` TIMESTAMPTZ nullable)
- Modify: `backend/app/schemas.py` (`SubmissionCreate.expires_at: datetime | None = None`; `SubmissionOut.expires_at: datetime | None`)
- Modify: `backend/app/routers/submissions.py` (accept/validate expires_at in both create paths — must be > now; adhoc via `expires_at: str | None = Form(None)` ISO parse; block correct/remind/resend on expired via existing `status != "pending"` 409s — no change needed there)
- Modify: `backend/app/routers/signing.py` (lazy expire: `_expire_if_due(db, submission)` — if pending and `expires_at <= now`, flip under the existing row lock in `/complete` & `/decline`; in `get_sign_view`/`_token_status` treat past-due as expired for display without writing)
- Modify: `backend/app/notifications.py` (`on_submission_expired(db, submission, settings)` — same contacted-party fan-out as `on_submission_cancelled`, sender included, no actor; `send_expiry_warnings(db, settings) -> int` — pending envelopes with `expires_at - now <= 2 days`, not yet warned → email currently-due, not-completed signers + sender, set `expiry_warned_at`)
- Modify: `backend/app/routers/jobs.py` (`run_expirations(db, settings) -> int`: flip past-due pending envelopes to "expired" + audit + notify; call both new sweeps from `run_daily_job`, add `"expired": int, "expiry_warnings": int` to response)
- Test: `backend/tests/test_expiration.py`

**Interfaces:**
- Produces: `Submission.expires_at/expiry_warned_at`; status literal `"expired"`; audit event `"expired"`; `notifications.on_submission_expired`, `notifications.send_expiry_warnings`; jobs response keys `expired`, `expiry_warnings`.
- Warning window constant: `EXPIRY_WARNING_DAYS = 2` in `notifications.py`.

**Steps:**
- [ ] Write failing tests: create-with-expiry roundtrip (+422 for past date); daily job expires past-due envelope (status, audit event, mail called); warning sent once (expiry_warned_at set, second run sends nothing); signer `/complete` on past-due envelope 409s and flips status; non-expired paths untouched.
- [ ] Migration: add columns; drop/recreate `ck_submissions_status` and `ck_audit_events_event` with the new value sets.
- [ ] Implement model/schema/router/notifications/jobs changes.
- [ ] `pytest tests/test_expiration.py` green, then full suite + ruff.
- [ ] Commit `feat: envelope expiration with deadline warnings (backend)`.

### Task 2: Envelope expiration — frontend

**Files:**
- Modify: `frontend/src/types.ts` (`SubmissionStatus` += "expired"; `SubmissionOut.expires_at: string | null`)
- Modify: `frontend/src/views/SendView.vue` (optional expiry date input in the options/message step; sends `expires_at` as end-of-day local → ISO; both template & adhoc payloads)
- Modify: `frontend/src/components/EnvelopeBrowser.vue` (Expired status chip/filter; "Expires <date>" hint on pending rows with expiry)
- Modify: `frontend/src/views/EnvelopeDetailView.vue` (expiry line + Expired status rendering)
- Modify: `frontend/src/utils/envelopes.ts` + `frontend/src/utils/__tests__` vitest specs (expired = never waiting-on-you; status label/color "Expired")

**Steps:**
- [ ] Types, send wizard input, browser/detail rendering, utils + vitest.
- [ ] `vue-tsc`, `vitest run`, `build` green.
- [ ] Commit `feat: envelope expiration (frontend)`.

### Task 3: Configurable reminders — backend

**Files:**
- Create: `backend/migrations/versions/a9c3e5f7b1d2_reminder_settings.py` (down_revision = Task 1's revision)
- Modify: `backend/app/models.py` (`Submission.reminders_enabled` bool server_default "true"; `Submission.reminder_interval_days` int server_default "3")
- Modify: `backend/app/schemas.py` (`SubmissionCreate.reminders_enabled: bool = True`, `reminder_interval_days: int = Field(3, ge=1, le=30)`; both on `SubmissionOut`)
- Modify: `backend/app/routers/submissions.py` (persist on both create paths; adhoc via Form fields)
- Modify: `backend/app/notifications.py` (`_is_overdue(submitter, min_days)` — when called from the daily sweep, `min_days` comes from `submitter.submission.reminder_interval_days`; `_eligible_submitters` gains `use_submission_interval: bool` (daily) vs explicit `min_days` (manual remind keeps 0); daily query also filters `Submission.reminders_enabled.is_(True)`; manual remind ignores the toggle — sender explicitly asked)
- Test: `backend/tests/test_reminder_settings.py`

**Interfaces:**
- Produces: `Submission.reminders_enabled/reminder_interval_days`; `SubmissionCreate`/`SubmissionOut` fields of the same names. `REMINDER_MIN_DAYS` stays as the default constant; `REMINDER_MAX = 3` unchanged.

**Steps:**
- [ ] Failing tests: interval=1 envelope reminded on day 1 while default envelope isn't; reminders_enabled=false skipped by daily sweep but manual `/remind` still works; create validates 1..30.
- [ ] Migration + implementation.
- [ ] Suite + ruff green; commit `feat: per-envelope reminder settings (backend)`.

### Task 4: Configurable reminders — frontend

**Files:**
- Modify: `frontend/src/types.ts`, `frontend/src/views/SendView.vue` (options section: "Automatic reminders" switch + interval select [1,2,3,5,7,14] "every N days", default on/3)
- Modify: `frontend/src/views/EnvelopeDetailView.vue` (show "Reminders: every N days / off" line)

**Steps:**
- [ ] Implement; vue-tsc/build green; commit `feat: reminder settings (frontend)`.

### Task 5: New field types — backend (dropdown, radio, attachment, text validation)

**Files:**
- Create: `backend/migrations/versions/c7d1f3a9e5b4_submitter_attachments.py` (table `attachments`: id PK, submitter_id FK ondelete CASCADE, field_id str, filename str(255), file_key str(1024), content_type str(100), size int, created_at)
- Modify: `backend/app/models.py` (`Attachment` model)
- Modify: `backend/app/schemas.py` (FieldDef.type += "dropdown"|"radio"|"attachment"; `options: list[str] | None` — required non-empty (≤20 items, each 1..100 chars, unique) for dropdown/radio, normalized None otherwise; `validation: Literal["email","number"] | None` — text only, None otherwise; `AttachmentOut {attachment_id, filename}`)
- Modify: `backend/app/routers/signing.py` (`POST /{submitter_id}/attachment` multipart — pdf/png/jpg by magic bytes, ≤10MB, key `attachments/{submitter_id}/{uuid}.{ext}`, 409 unless open for signing; `_validate_values`: dropdown/radio value ∈ options; attachment value = int id owned by this submitter; text with validation "email" → EMAIL_RE fullmatch, "number" → float() parses)
- Modify: `backend/app/stamping.py` (dropdown/radio → `_draw_text` chosen value; attachment → `_draw_text` "[Attached: {filename}]" — filename passed via new `attachment_names: dict[str, str]` param mapping str(attachment_id) → filename on `build_signed_pdf`)
- Modify: `backend/app/completion.py` (gather attachment rows for completed submitters; pass names to stamping; append attachment pages to the signed PDF: PDFs via PdfReader pages, images via one reportlab page each, letter-size, aspect-fit; separator page not needed)
- Modify: `backend/app/routers/files.py` (document-preview path passes attachment_names too — check call sites of build_signed_pdf)
- Test: `backend/tests/test_field_types.py`

**Interfaces:**
- Produces: FieldDef `options`/`validation`; `Attachment` model; `POST /api/sign/{id}/attachment` → `{attachment_id, filename}`; `build_signed_pdf(..., attachment_names: dict[str, str] | None = None)`.

**Steps:**
- [ ] Failing tests: FieldDef validation matrix; attachment upload happy/oversize/wrong-magic/wrong-submitter; complete with dropdown value not in options 422; email/number validation 422s; completed PDF page count grows by appended attachment; stamped text note present.
- [ ] Migration + implementation (read `completion.py` first).
- [ ] Suite + ruff; commit `feat: dropdown, radio, attachment fields + text validation (backend)`.

### Task 6: New field types — frontend

**Files:**
- Modify: `frontend/src/types.ts` (FieldType += 3; FIELD_TYPES order: after checkbox, before label; FieldDef.options/validation)
- Modify: `frontend/src/composables/useFieldPlacement.ts` (default sizes: dropdown/radio like text; attachment like signature-ish box)
- Modify: `frontend/src/components/FieldPropertiesPanel.vue` (dropdown/radio: options editor — `v-combobox multiple chips` bound to options, min 1 enforced on save; text: validation select None/Email/Number)
- Modify: `frontend/src/components/FieldBox.vue` (icons/labels for new types)
- Modify: `frontend/src/views/SignView.vue` (dropdown → v-select in field popover; radio → v-radio-group; attachment → file input uploading via new api call, shows filename chip; client-side email/number validation with error text; required gating includes new types)
- Modify: `frontend/src/api.ts` (uploadAttachment(submitterId, file) → POST multipart)
- Modify: `frontend/src/views/TemplateBuilderView.vue` + `frontend/src/views/SendView.vue` (palette shows new field types — verify they use FIELD_TYPES)

**Steps:**
- [ ] Implement; vue-tsc/vitest/build; commit `feat: dropdown, radio, attachment fields + validation (frontend)`.

### Task 7: Upload-image signature

**Files:**
- Modify: `frontend/src/components/SignaturePad.vue` (third tab "Upload": `<input type="file" accept="image/png,image/jpeg">`; draw onto an offscreen canvas capped at 800×300 (aspect-fit, transparent background) → PNG data URL; guard >1MB output by downscaling; error text for non-image)

**Steps:**
- [ ] Implement; vue-tsc/build; commit `feat: upload-image signature tab`.

### Task 8: Draft envelopes — backend

**Files:**
- Create: `backend/migrations/versions/b5e9d2c7a3f1_draft_status.py` (recreate `ck_submissions_status` with "draft")
- Modify: `backend/app/models.py` (SUBMISSION_STATUSES += "draft")
- Modify: `backend/app/schemas.py` (`SubmissionCreate.draft: bool = False`)
- Modify: `backend/app/routers/submissions.py`:
  - create paths: when draft → `status="draft"`, write only `created` audit (no `sent` events), skip `on_submission_created`; adhoc via `draft: bool = Form(False)`
  - `POST /{id}/send`: sender-with-can_send/admin (`_require_correction_rights`), row-lock, 409 unless draft; flip to pending, write `sent` audit per submitter, post-commit `on_submission_created`
  - `DELETE /{id}`: sender/admin, 409 unless draft; delete audit events, submitters (cascade), submission; if template is_adhoc → delete storage files + template row
  - `mine=sign` branch: exclude `Submission.status == "draft"`
  - correction endpoints (patch/replace-document/replace-submitter): allow status in ("pending", "draft"); replace_submitter on a draft must NOT email the new signer (no email_status set — gate `recipient_due` send on `submission.status == "pending"`)
- Modify: `backend/app/routers/signing.py` (`_get_submitter_authorized`: 404 when `submission.status == "draft"`; `_token_status`: treat draft as 404 via same guard — check `_get_submitter_by_access_uid` call sites)
- Test: `backend/tests/test_drafts.py`

**Interfaces:**
- Produces: status literal `"draft"`; `POST /api/submissions/{id}/send`; `DELETE /api/submissions/{id}`; `SubmissionCreate.draft`.

**Steps:**
- [ ] Failing tests: draft create sends no mail + no sent audit; signer's mine=sign hides it; sign view 404s; /send flips + emails + audit; delete removes rows/files; delete/send on non-draft 409; corrections work on drafts without email.
- [ ] Migration + implementation.
- [ ] Suite + ruff; commit `feat: draft envelopes (backend)`.

### Task 9: Draft envelopes — frontend

**Files:**
- Modify: `frontend/src/types.ts` ("draft" status), `frontend/src/api.ts` (sendDraft, deleteDraft, draft flag on create calls)
- Modify: `frontend/src/views/SendView.vue` ("Save as draft" secondary button on the final step → create with draft:true → route to envelope detail)
- Modify: `frontend/src/components/EnvelopeBrowser.vue` (Drafts sidebar view: sent-by-me + status draft, with count; row actions Send/Delete with confirm)
- Modify: `frontend/src/views/EnvelopeDetailView.vue` (Draft banner: "This envelope is a draft — recipients haven't been notified." + Send now / Delete buttons)
- Modify: `frontend/src/utils/envelopes.ts` + vitest (draft label/color; never waiting-on-you; not "in progress")

**Steps:**
- [ ] Implement; vue-tsc/vitest/build; commit `feat: draft envelopes (frontend)`.

### Task 10: Shared templates — backend

**Files:**
- Create: `backend/migrations/versions/d8b4f6a2c9e3_template_shared.py` (templates.shared bool server_default "false")
- Modify: `backend/app/models.py` (`Template.shared`)
- Modify: `backend/app/schemas.py` (`TemplateOut.shared: bool`, `TemplateOut.owner: UserBrief` via validation_alias "creator", `TemplateSharingUpdate {shared: bool}`)
- Modify: `backend/app/routers/templates.py`:
  - `list_templates`: own OR (shared & not adhoc & not archived), eager-load creator, order by id
  - `get_template`: owner, admin, or shared → readable (send wizard needs fields)
  - `update_fields`/`archive`: stay owner/admin only
  - `PUT /{id}/sharing`: owner/admin toggles
- Modify: `backend/app/routers/submissions.py` (`create_submission`: allow `template.shared` senders)
- Test: `backend/tests/test_shared_templates.py`

**Interfaces:**
- Produces: `Template.shared`; `PUT /api/templates/{id}/sharing`; TemplateOut.shared/owner.

**Steps:**
- [ ] Failing tests: non-owner sees shared template in list + can GET + can send from it; cannot edit fields/archive/toggle (403); unshared stays 403/404-invisible.
- [ ] Migration + implementation.
- [ ] Suite + ruff; commit `feat: shared templates (backend)`.

### Task 11: Shared templates — frontend

**Files:**
- Modify: `frontend/src/types.ts` (TemplateOut.shared/owner)
- Modify: `frontend/src/views/TemplatesView.vue` (share toggle on own cards; "Shared by {owner.name}" chip + hidden edit/archive on others')
- Modify: `frontend/src/views/SendView.vue` / from-template menu (shared templates included — verify data source is GET /api/templates)

**Steps:**
- [ ] Implement; vue-tsc/build; commit `feat: shared templates (frontend)`.

### Task 12: Final verification & PR

- [ ] Full backend suite + ruff; full frontend vue-tsc + vitest + build.
- [ ] Migration chain sanity: fresh DB `alembic upgrade head`.
- [ ] Update `docs/` design notes if a spec section is superseded; update CLAUDE.md key facts (statuses, new routes) if warranted.
- [ ] Push branch, open draft PR titled "feat: expiration, reminder settings, new field types, upload signature, drafts, shared templates".

## Self-Review Notes

- Constraint recreation happens in three migrations (expired, draft, audit "expired") — each recreates from the then-current model constants; keep `SUBMISSION_STATUSES` single source and copy the literal tuple current at that migration.
- `build_signed_pdf` gains an optional kwarg — the document-preview endpoint (files.py) and completion.py are the two call sites; both must pass attachment names (preview may pass {} when lazy).
- Draft + expiration interplay: a draft with `expires_at` in the past must not be expired by the cron (query filters status=="pending") and `/send` of a past-expiry draft should 409 ("expiry date has passed — edit it first").
- Reminders + drafts: `_eligible_submitters` filters `Submission.status == "pending"` already — drafts safe.
- Radio is a single-box choice field (options list, stamped as text) — positioned per-option radio groups deliberately out of scope; noted in PR body.
