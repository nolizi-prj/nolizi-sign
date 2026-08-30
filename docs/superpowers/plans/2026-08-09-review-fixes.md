# Cross-Feature Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every actionable finding from the 2026-08-09 cross-feature review (see the published report): 2 outright bugs, the void/CC/notification seam cluster, permission gaps, UI truthfulness, and the missing frontend test harness.

**Architecture:** All fixes land on branch `review-fixes` (based on `replace-document-filenames`, 4 commits ahead of main). Backend fixes go through the existing router/notifications/audit layers; one Alembic migration adds `submitters.first_notified_at`. Frontend fixes extract shared envelope-list logic into a new `utils/envelopes.ts` so the dashboard and browser agree, tested by a new vitest harness.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + pytest (Postgres :5433); Vue 3 + Vuetify + vue-tsc; vitest (new).

## Global Constraints

- Tests are Postgres-only; run `pytest` from `backend/` using the main checkout's venv (`../../../..`? no — use `/home/m/dev/pumasi-sign\backend\.venv` per worktree-shared-toolchains memory).
- Frontend: `npm ci` fresh in the worktree; `npx vue-tsc --noEmit` and `npm run build` must pass.
- `ruff check . && ruff format --check .` must pass in `backend/`.
- Commit after each task. Never push to main.

## Product decisions locked in (assumptions, user was away)

1. **Voided envelopes stay visible to recipients** — `mine=sign` stops excluding `cancelled`; the "Voided" filter becomes real. Rationale: silent disappearance was the complaint; declined already stays.
2. **CC recipients get Inbox visibility** — `mine=sign` includes `is_cc` rows, per the envelope-browser spec ("I'm a signer or CC"). The browser already renders a CC chip and excludes CC from action-needed.
3. **Void takes an optional reason**, stored in the audit `detail`, rendered in the timeline, included in the void notification email.
4. **Void notifies** every already-contacted non-CC signer + all CC recipients + the sender's own confirmation is unnecessary (they did it). External recipients get no portal link (same split as completion emails).
5. **Decline notifies** the sender (existing) plus all other already-contacted parties and CCs.
6. **Resend endpoint** is the bounce-recovery path: sender/admin can re-send a signer's invite; it resets `reminder_count` to 0 and `email_status`. Reminder-count-increments-on-failure behavior stays (prevents daily retry storms).
7. **`can_send` gates** correction-type actions (replace document, correct, replace signer, remind, resend). Void and retry-completion stay sender-or-admin (harm-reduction actions must not be blockable by role revocation).
8. **Replace-document clones are marked `is_adhoc=True`** so repeated replaces reuse the clone in place instead of accumulating orphans.
9. **Decline requires it to be your turn** (parity with complete). Opening a not-your-turn sign page no longer flips `opened`/writes audit.
10. **External signers can retrieve the signed PDF**: the code-request/verify flow also works for `completed`/`already_signed` envelopes; after verification the existing blocked-state UI (which already offers "View signed PDF") is shown.
11. **Deferred, not implemented** (need their own spec / already tracked): envelope expiry, durable record (cert/SharePoint) for voided/declined envelopes, issues #44–#48/#50 scope, pagination/bulk actions, SignView page virtualization, daily-reminder skip for archived-by-recipient (deliberately NOT changed: archiving is personal filing, not a decline).

---

### Task 1: Surgical bug fixes (backend)

**Files:**
- Modify: `backend/app/routers/submissions.py` (retry_completion ~:964; remind_submission ~:1006)
- Modify: `backend/app/signing.py` (decline ~:601; opened flip ~:313; role_names ~:334)
- Modify: `backend/app/models.py` (remove stale `TEMPLATE_FIELD_TYPES` :24; fix "six tables" header comment :1)
- Test: `backend/tests/test_submissions.py`, `backend/tests/test_signing.py`

**Steps:**
- [x] retry_completion: add `Submitter.is_cc.is_(False)` to the still-open count. Test: envelope + CC, force all signers completed but submission pending (simulate stamping failure), POST retry → 200 and completed.
- [x] remind_submission: allow admins (`created_by != user.id and not user.is_admin` → 403). Test: admin reminds another sender's envelope → 200.
- [x] decline_signing: enforce `_is_my_turn` → 409 like complete. Test: order-group-2 signer declines before group 1 → 409.
- [x] GET /sign: only flip `pending→opened` + audit when `_is_my_turn`. Test: not-your-turn GET leaves status pending, no `opened` audit event.
- [x] role_names: exclude `is_cc` rows. Test: CC recipient's name absent from signer view payload.
- [x] models.py: delete `TEMPLATE_FIELD_TYPES`, fix header comment. Grep confirms no references.
- [x] pytest + ruff, commit.

### Task 2: Void honesty (reason + notification + visibility)

**Files:**
- Modify: `backend/app/schemas.py` (new `SubmissionCancelIn(reason: str | None, max_length=500)`)
- Modify: `backend/app/routers/submissions.py` (cancel_submission ~:852; list filter :403)
- Create: `notifications.on_submission_cancelled(db, submission, actor, reason)` in `backend/app/notifications.py`
- Modify: `frontend/src/views/EnvelopeDetailView.vue` (void dialog + timeline `cancelled` branch), `frontend/src/views/DashboardView.vue` (void dialog)
- Test: `backend/tests/test_submissions.py`, `backend/tests/test_notifications.py`

**Steps:**
- [x] cancel accepts optional JSON body `{reason}`; audit detail `{"reason": ...}` when present.
- [x] on_submission_cancelled: recipients = non-CC submitters with `email_status IS NOT NULL` and status not completed... include those who signed too (their signature is now void) + all CC rows; internal/external split like completion emails; subject "Voided: {title}"; body includes actor name + reason if any. Called after commit in cancel route.
- [x] `mine=sign`: drop the `status != "cancelled"` filter. Tests: voided envelope appears in recipient list; void emails sent to contacted signers + CCs, not to uncontacted order-group-2 signers.
- [x] Frontend: reason textarea in both void dialogs (optional); POST body; timeline shows `Voided by X — "reason"`.
- [x] pytest + ruff, commit.

### Task 3: CC visibility + validation

**Files:**
- Modify: `backend/app/routers/submissions.py` (list :403 include CC; `_validate_role_mapping` :123 dedupe + cap)
- Test: `backend/tests/test_submissions.py`

**Steps:**
- [x] `mine=sign` includes `is_cc` rows. Test: CC-only recipient sees envelope in `mine=sign`; their `my_submitter` has `is_cc=True`.
- [x] Creation validation: 422 on duplicate `user_id` across all recipients (signers + CC); 422 on >10 CC rows. Tests for both.
- [x] pytest, commit.

### Task 4: Notification correctness (corrections, decline, reminder clock)

**Files:**
- Modify: `backend/app/notifications.py` (decline fan-out ~:253; `_is_overdue` ~:272; new correction notifiers)
- Modify: `backend/app/routers/submissions.py` (replace_document ~:609, replace_submitter ~:805 call notifiers)
- Modify: `backend/app/models.py` + new Alembic migration: `submitters.first_notified_at TIMESTAMPTZ NULL`, backfilled to the submission's `created_at` for rows with `email_status IS NOT NULL`.
- Modify: `backend/app/mailer.py` callers that mark `email_status="sent"` → also stamp `first_notified_at` if null (find the exact set-points: notify_created, on_submitter_completed unlock, replace_submitter, resend).
- Test: `backend/tests/test_notifications.py`, `backend/tests/test_submissions.py`

**Steps:**
- [x] Decline: notify sender + other contacted non-CC signers + CCs (skip the decliner).
- [x] Document swap: email contacted, not-yet-signed non-CC signers "the document was replaced — review before signing" (no one has signed by the endpoint's own guard, so recipients = contacted signers).
- [x] Signer swap: email the removed signer "you have been replaced; the link no longer works" (only if they had been contacted).
- [x] Migration + model column; `_is_overdue` uses `first_notified_at or submission.created_at`.
- [x] Tests: group-2 signer first notified day 8 is NOT overdue on day 9; removed contacted signer gets email; document-swap email goes to contacted signers only.
- [x] pytest + alembic upgrade on test DB, commit.

### Task 5: Resend (bounce recovery)

**Files:**
- Modify: `backend/app/routers/submissions.py` (new route `POST /{id}/submitters/{submitter_id}/resend`)
- Modify: `backend/app/notifications.py` (reuse the single-submitter invite sender)
- Modify: `frontend/src/views/EnvelopeDetailView.vue` (Resend button on signer rows, prominent when bounced)
- Test: `backend/tests/test_submissions.py`

**Steps:**
- [x] Route: sender(with can_send)/admin; envelope pending; target not completed/declined, `recipient_due` (their turn); resets `reminder_count=0`, `email_status=None`, then sends invite (stamps `email_status`, `first_notified_at`). Audit event `reminded` with `detail={"resend": true}`... reuse existing audit vocabulary (no enum change).
- [x] Tests: bounced signer (email_status=failed, reminder_count=3) → resend 200, email sent, counters reset; resend for not-your-turn signer → 409.
- [x] Frontend button + toast; pytest; commit.

### Task 6: Permission guards

**Files:**
- Modify: `backend/app/routers/submissions.py` (can_send checks on replace_document, correct_submission, replace_submitter, remind, resend)
- Modify: `frontend/src/router/index.ts` (admin meta + guard; catch-all 404)
- Create: `frontend/src/views/NotFoundView.vue`
- Modify: `frontend/src/views/AdminUsersView.vue` (in-view isAdmin gate like TemplatesView)
- Test: `backend/tests/test_submissions.py`

**Steps:**
- [x] Backend: sender-without-can_send → 403 on the five correction-type endpoints (admin unaffected; cancel/retry untouched). Tests: revoked sender 403 on remind + replace_submitter; still 200 on cancel.
- [x] Router: `meta: { requiresAdmin: true }` on `/admin/users`, guard redirects non-admins to `/`; `/:pathMatch(.*)*` → NotFoundView with a "Back to dashboard" link.
- [x] vue-tsc + build; commit.

### Task 7: UI truthfulness (dashboard cards, turn state, archive on detail)

**Files:**
- Create: `frontend/src/utils/envelopes.ts` — pure helpers extracted from `EnvelopeBrowser.vue`: `mySubmitter`, `actionNeeded` (status==="pending" && me && !me.is_cc && me.status!=="completed" && !archived_by_me && myTurn), `myTurn(submission)` (order-group logic, mirrors EnvelopeDetailView's waitingForTurn), `matchesSearch`, `inView`.
- Modify: `frontend/src/components/EnvelopeBrowser.vue` (use helpers; null-safe search — the crash fix; "Waiting for turn" chip instead of "Sign now" when not my turn)
- Modify: `frontend/src/views/DashboardView.vue` (`waitingForSignature` uses `actionNeeded`; greeting count === badge count)
- Modify: `frontend/src/views/EnvelopeDetailView.vue` (archived badge + archive/unarchive action; use shared `myTurn`)
- Test: vitest (Task 9) covers the helpers.

**Steps:**
- [x] Extract helpers; search accepts `string | null` and normalizes.
- [x] Dashboard cards/count and browser badge derive from the same `actionNeeded`.
- [x] Browser row: `myTurn===false` → grey "Waiting for turn" instead of primary "Sign now".
- [x] Detail: show "Archived" chip when `archived_by_me`, menu action Archive/Unarchive calling existing endpoints.
- [x] vue-tsc + build; commit.

### Task 8: External signer experience

**Files:**
- Modify: `backend/app/signing.py` (allow request-code/verify when token status is `completed`/`already_signed`)
- Modify: `frontend/src/views/ExternalSignView.vue` (completed/already_signed cards offer "verify to download"; request-code failure no longer forces phase="code")
- Modify: `frontend/src/views/SendView.vue` (template mode: combobox + Add-signer dialog, same as one-off)
- Test: `backend/tests/test_external_signing.py`

**Steps:**
- [x] Backend: code flow permitted for completed envelopes; signing endpoints still blocked; signed-pdf works via cookie (already does). Test: completed envelope → request-code 200 → verify 200 → GET signed-pdf with cookie 200.
- [x] ExternalSignView: completed card shows "Email me a code to download the signed document"; after verify, SignView blocked state (already offers the PDF). Error on request-code keeps landing phase.
- [x] SendView: signer rows in template mode use the same combobox + add-by-email dialog as one-off mode.
- [x] vue-tsc + build + pytest; commit.

### Task 9: Replace-document clone reuse + vitest harness

**Files:**
- Modify: `backend/app/routers/submissions.py` (clone `is_adhoc=True` ~:585)
- Modify: `frontend/package.json` (+vitest), Create: `frontend/vitest.config.ts`, `frontend/src/utils/__tests__/envelopes.spec.ts`, `labels.spec.ts`
- Modify: `.github/workflows/ci.yaml` (run vitest in frontend job)
- Test: `backend/tests/test_submissions.py` (second replace reuses clone)

**Steps:**
- [x] Clone marked `is_adhoc=True`; test: replace twice → template id unchanged after 2nd replace, storage keys overwritten, no third template row.
- [x] vitest: cover actionNeeded/myTurn/matchesSearch/inView incl. `search=null` regression, and labels.ts void naming.
- [x] CI job runs `npx vitest run`.
- [x] All checks; commit.

### Task 10: Docs drift quick fixes + final verification

**Files:**
- Modify: `docs/superpowers/specs/2026-07-30-internal-esign-design.md` (YAGNI list, roles, table count annotations — short "superseded" notes, not a rewrite)
- Modify: `docs/superpowers/specs/2026-08-05-send-flow-features-design.md` (CC section: superseded-by-PR-#38 note)

**Steps:**
- [x] Add dated "Superseded" callouts.
- [x] Full suite: backend pytest, ruff, vue-tsc, npm run build, vitest.
- [x] Commit, push branch, open draft PR against main noting it stacks on `replace-document-filenames`.
