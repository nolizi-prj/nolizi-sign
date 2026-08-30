# Sender roles, envelope correction, safe signer entry, feedback paste

**Date:** 2026-08-03
**Status:** Approved design (Pumasi Team, 2026-08-03), pending implementation plan

Four related changes, one release:

- **A. Sender role** — every Pumasi user can send envelopes by default;
  admins can revoke per user.
- **B. Envelope correction** — the envelope's sender or an admin can
  correct a pending envelope: signer email/name, replace a signer, title,
  message.
- **C. Safe signer entry** — typing an email in the send wizard never
  silently creates a signer (fixes the `signer@pumasi.ai`/`.co`
  partial-capture bug).
- **D. Feedback paste** — the feedback dialog accepts pasted screenshots.

## A. Sender role (`can_send`)

Three effective roles from two flags — no role enum:

| Effective role | Condition | Abilities |
| --- | --- | --- |
| Admin | `is_admin` | everything, incl. admin console + revoking send |
| Sender (default internal) | `can_send AND NOT is_external` | send envelopes, templates, signer picker, sign |
| Sign-only | external user, or internal with `can_send=false` | sign what they're sent |

- Migration: `users.can_send BOOLEAN NOT NULL server_default 'true'`.
  External users keep the column true but are excluded by the guard —
  `is_external` always wins.
- New dependency `require_sender` in `app/auth.py`: the current user if
  `is_admin or (can_send and not is_external)`, else 403.
- Re-gate from `require_admin` → `require_sender`:
  - `POST /api/submissions` (create), `POST /api/submissions/adhoc`,
    `POST /api/submissions/adhoc/merged-document`
  - every route in `routers/templates.py`
  - `GET /api/users`, `POST /api/users` (signer picker + external
    provisioning; accepted consequence: any sender sees the user directory
    and can provision external signers)
- Stays admin-only: `PUT /api/users/{id}` admin-flag changes, admin
  console, `dev-signing-links`.
- Already correct (they use `current_user` + their own creator/visibility
  checks): cancel, remind, retry-completion, detail/list visibility — no
  changes there.
- `GET /api/auth/me` gains `can_send` (effective value:
  `is_admin or (can_send and not is_external)` exposed as `can_send`, so
  the frontend needs no duplicated logic).
- Frontend: Send/Templates UI (dashboard actions, routes) shown only when
  `me.can_send`; Admin Users page gains a per-user "Can send" toggle
  (internal users only; disabled for externals).

## B. Envelope correction (pending envelopes only)

Authorization for all correction endpoints: envelope creator or admin.
Completed/cancelled envelopes are immutable. Every correction records a
`corrected` audit event (actor = the corrector) with a `detail` JSON of
what changed: changed field names, and for signer swaps / contact fixes
the from/to user ids and emails — emails belong in the trail here, since
the audit log is only visible to the envelope's sender and admins and
"which address did this go to" is the whole point of correcting it.

1. **Edit title/message:** `PATCH /api/submissions/{id}` with
   `{title?, message?}`. Title: non-empty, ≤255 after trim. The document
   and fields are NOT editable — signing may have started; a wrong
   document means cancel + resend.
2. **Correct an external signer's contact info:** extend
   `PUT /api/users/{id}` — payload becomes
   `{is_admin?, name?, email?, can_send?}`:
   - `is_admin`/`can_send` changes: admin-only (existing self-demotion
     guard stays).
   - `name`/`email` changes: allowed for any sender, but ONLY on external
     users (`is_external`) — internal emails are the SSO login key and
     stay locked. New email must not belong to another user (409) and must
     still be an external domain (422 otherwise — an "internal" user
     created by email edit would bypass SSO provisioning).
   - Email format re-validated server-side (pydantic EmailStr or the
     existing pattern).
   - Effect is immediate for all their pending envelopes (reminders and
     sign links go to the corrected address; the emailed access link
     still works — same person, same token).
3. **Replace a signer:** `PUT /api/submissions/{id}/submitters/{sid}` with
   `{user_id}`:
   - Target submitter must not be `completed` (a captured signature is
     immutable); new user must not already be a submitter on the envelope.
   - Resets the submitter: `status='pending'`, `values={}`,
     `opened/signed` state cleared, reminder counters reset.
   - **Regenerates `access_uid`** when the new signer is external (and
     nulls it for internal) so the previously emailed link is dead — the
     old recipient must not be able to open the new signer's session.
   - Sends the sign-request email to the new signer (reuse the
     single-submitter path inside `notifications.on_submission_created`,
     extracting a helper if needed), sets `email_status`.
4. Frontend (`EnvelopeDetailView`, visible when pending AND viewer is
   creator or admin):
   - Pencil next to title/message → small edit dialog → PATCH.
   - Per-signer overflow menu: "Correct contact info…" (external signers
     only: name + email dialog → `PUT /users/{id}`), "Replace signer…"
     (user picker dialog → the new submitter endpoint).
   - Audit timeline renders `corrected` events.

Migration: widen the `audit_events` check constraint to include
`'corrected'` (drop + recreate constraint).

## C. Safe signer entry (send wizard)

- Tighten `EMAIL_PATTERN` to require a 2+ char TLD:
  `/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/`.
- Free-typed text in the signer combobox NEVER creates a user directly:
  - exact match to an existing user's email → assign, as today;
  - anything else valid-shaped → open the (existing, reworked) "Add
    signer" dialog with **email prefilled and editable** + name field
    (required for external domains, optional for internal — placeholder
    name applies), and only its Confirm button POSTs `/users`;
  - invalid text → inline hint, nothing created.
  This eliminates the Vuetify combobox blur/menu-close phantom-commit
  class entirely — no commit path creates users anymore.
- The reworked dialog is the same one used when the backend answers
  "External signer requires a name" (that flow collapses into the dialog
  since the dialog now always collects the name first).

## D. Feedback screenshot paste

- `FeedbackDialog.vue`: `@paste` on the dialog card reads
  `event.clipboardData` items, takes the first `image/png` or
  `image/jpeg` item as the screenshot (constructing a named `File`, e.g.
  `pasted-screenshot.png`), replacing any current selection.
- Thumbnail preview with a remove (×) button once a screenshot is present
  (from either paste or the existing file input, which stays).
- Existing limits unchanged (3 MB, png/jpeg, one screenshot); backend
  untouched.

## Testing

- A: `require_sender` unit tests (sender ok, sign-only 403, external 403,
  admin ok even with `can_send=false`); re-gated routes accept a
  non-admin sender (spot-check one route per router) and reject a
  `can_send=false` user; admin console toggle round-trip; `/me` shape.
- B: PATCH title/message (authz matrix: creator ok, other sender 403,
  admin ok, completed envelope 409); user contact edit (external ok via
  sender, internal email edit 403/422, duplicate email 409,
  internal-domain email on external user 422); replace signer (resets
  state, regenerates/nulls access_uid, old access_uid 404s, completed
  submitter 409, duplicate signer 409, email sent, audit event recorded).
- C: no HTTP user-creation on blur-like commits (component logic factored
  so the decision is testable), regex rejects 1-char TLD. Covered by
  vue-tsc + e2e happy path if cheap; primary safety is that creation now
  requires an explicit dialog confirm.
- D: type-check + manual verification (clipboard events are impractical
  in CI e2e).

## Rollout / data cleanup

- Migrations run automatically on deploy (two: `can_send`, audit
  constraint) — both backward-compatible.
- No env var changes.
- Post-deploy: correct the real `signer@pumasi.ai` user to
  `signer@pumasi.ai` via the new UI (dogfood), and check prod for a
  stray `signer@pumasi.ai` user; fix or remove via SQL if present.
