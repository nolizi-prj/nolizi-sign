# Draft 2.0: wizard re-entry, DocuSign-complete Copy, and the draft bug sweep

Date: 2026-08-23. Status: approved design, pre-implementation.

## Terminology

The feature is called **"Copy"** everywhere, matching DocuSign: UI buttons
and toasts say "Copy", and the endpoints rename from
`POST /api/submissions/{id}/duplicate` / `POST /api/templates/{id}/duplicate`
to `POST /api/submissions/{id}/copy` / `POST /api/templates/{id}/copy`
(safe — the SPA is the only client and ships with the backend). New audit
events write the detail key `copied_from_submission_id`; rows written since
PR #68 keep their `duplicated_from_submission_id` key, which nothing
renders, so no migration or dual-read is needed.

## Problem

The Duplicate feature (PR #68) copies an envelope's data correctly, but the
draft it produces is barely editable: the envelope page only allows changing
the title, the message, the document file, and swapping one signer for
another person. Expiration, reminders, signing order, adding/removing
recipients, CC conversion, role assignment, and field placement are all
frozen at create time. DocuSign's "Create a Copy" — the model the user asked
for — produces a draft that reopens in the full prepare flow with everything
editable, and even carries recipient-entered field data (all but signatures,
initials, and signed dates) into the copy.

A code audit (2026-08-23) also found ten real defects in the draft path,
including one security gap. This project delivers the DocuSign-style
experience and fixes the sweep in one coherent change.

## Goals

1. A draft (including a fresh duplicate) opens in the Send wizard with
   every compose-time input editable: document, title, signers, roles,
   signing order, CC, message, expiration, reminders, field placement and
   field properties.
2. Duplicate copies as much as DocuSign does: document, recipients with
   order and CC flags, message, settings, field placements, and
   signer-entered text/dropdown/radio/checkbox values as editable prefills.
   Signatures, initials, auto-filled dates/names, and attachments are not
   copied.
3. Every audited draft-path bug is fixed (list below).

## Non-goals (deferred)

- Guarding `PUT /api/templates/{id}/fields` against mutating templates that
  in-flight (sent) envelopes reference. Mitigated here by send-time
  re-validation; a fuller fix (field snapshotting per envelope) is future
  work.
- A "Draft"-specific watermark on document previews (drafts currently show
  the "In progress" watermark).
- Editing an in-flight (pending) envelope's fields ("DocuSign Correct" for
  fields). This project only widens *draft* editing.

## Current-state findings (audit summary)

Editable on a draft today: `title`, `message` (via `PATCH
/api/submissions/{id}`, whose `SubmissionPatch` carries exactly those two
fields), the document file (`POST /{id}/replace-document`), and
replace-person (`PUT /{id}/submitters/{sid}`). Nothing else has a write
path after creation; `expires_at`/`reminders_*` are write-once in
`_create_submission`.

Bugs to fix (letters used throughout this spec):

- (a) Draft signer rows show a "Sent" chip (`signerStatusLabel` falls
  through to "Sent" for `pending`), on both the envelope page and browser
  rows.
- (b) A draft whose `expires_at` passes is permanently unsendable:
  `send_draft` 409s with "update it before sending" but no endpoint or UI
  can update it.
- (c) "Resend invite…" is offered on drafts and always 409s.
- (d) The Replace-signer dialog claims a fresh sign request is emailed —
  on drafts nothing is emailed.
- (e) The Replace-document dialog/toast claims signers will see/be notified
  of the new version — on drafts nobody is notified.
- (f) CC rows on a draft show "Copy queued" — nothing is queued.
- (g) A draft that lists its sender among the recipients appears in the
  sender's Inbox (`inView` checks `isRecipient` with no status filter).
- (h) Draft rows in the browser suppress the expiry caption
  (`expiryHint` requires `status === "pending"`), hiding the very value
  that will block Send.
- (i) Security: `GET /api/submissions/{id}`, `GET /{id}/events`, and
  `GET /api/files/document-preview/{id}` admit any listed submitter with no
  draft check, so a would-be recipient who guesses the URL can read an
  unsent draft. Lists and both signing paths already hide drafts.
- (j) `send_draft` re-validates only status and expiry; fields emptied or
  re-roled between save and send dispatch an unsignable envelope that
  create-time validation would have 422'd.
- (k) A sender who lost `can_send` can delete but not send/edit a draft —
  intentional asymmetry, to be documented in `delete_draft`'s docstring.

## Design

### Persistence model: recreate on save

The wizard never mutates a draft in place. "Edit draft" hydrates the wizard
from the draft; **Save as draft** and **Send** both run the existing
`POST /api/submissions/adhoc` create path (with `draft` true/false), and on
success the client deletes the superseded draft (`DELETE
/api/submissions/{id}`, ignoring failure — an orphaned draft is harmless
and deletable by hand). Consequences, accepted:

- A draft's envelope id (and `public_uid`) changes on each save. Drafts are
  never shared externally, so nothing breaks.
- An edited draft becomes a standalone one-off envelope even if it was
  created from a reusable template — matching how DocuSign copies behave.
  The reusable template itself is never touched.
- There is exactly one validation/creation code path; draft editing can
  never drift from compose.

### Backend changes

1. **Duplicate always produces a standalone ad-hoc draft.**
   `POST /api/submissions/{id}/duplicate` deep-copies the source's template
   (via the existing `clone_template`) with `is_adhoc=True` for *every*
   source, template-based included. This makes the copy fully editable and
   gives value-prefills somewhere safe to live.

2. **Duplicate carries signer-entered values as prefills.** For each source
   field of type `text`, `dropdown`, `radio`, or `checkbox`, if the source
   submitter assigned to that field's role entered a value
   (`Submitter.values[field_id]`), the cloned field's `default_value` is
   set to it. `signature`, `initials`, `date`, `name`, `attachment`, and
   `label` fields are skipped (auto-filled or non-copyable, per DocuSign).
   Boolean checkbox values map to the checkbox prefill representation the
   signing UI already understands.

3. **Draft access control (i).** `_get_submission_authorized` (and the
   file-serving equivalents for document preview) deny non-sender
   submitters access to `status="draft"` envelopes: draft detail, events,
   and preview become sender-or-admin-only until sent. Existing behavior
   for pending/completed envelopes is unchanged.

4. **Send-time re-validation (j).** `send_draft` re-runs
   `_validate_role_mapping` (and users-exist) against the template's
   current fields before dispatch, returning the same 422s as create.

5. **Docstring for (k)** on `delete_draft`, stating the intentional
   asymmetry.

No schema/model migrations. No new endpoints.

### Frontend changes

1. **Wizard draft mode.** New route `/send/draft/:draftId` (name
   `send-draft`, `props: true`); `SendView` accepts `draftId?: string`.
   On mount with `draftId` it fetches:
   - `GET /api/submissions/{draftId}` → title, message, expires_at,
     reminders, submitters (user, role, order_index, is_cc), template id;
   - `GET /api/templates/{templateId}` → fields (with prefills);
   - `GET /api/files/template-pdf/{templateId}` → the stored, un-watermarked
     PDF, loaded as the wizard's ad-hoc document.
   It hydrates the ad-hoc wizard state: document preview, signer rows in
   order (CC rows included), ordered-signing flag from `order_index` spread,
   message, expiration (a **past** date loads cleared, with a hint saying
   the old deadline passed), reminder settings, and the field list keyed to
   the same roles. The user walks the same four steps; Save as draft /
   Send behave per the persistence model above. Guard: only the draft's
   sender (still holding `can_send`) or an admin may load it; a non-draft
   id redirects to the envelope page.

2. **Duplicate lands in the wizard.** The envelope page's Duplicate button
   navigates to `send-draft` with the new id instead of the detail page.

3. **Entry points.** The draft banner on the envelope page gains **Edit
   draft** (primary) next to Send now/Delete; browser Draft rows get an
   "Edit draft" action; a past-expiry draft's banner warns that the
   deadline passed and points at Edit draft (fixing (b) end-to-end).

4. **Bug sweep UI fixes.**
   - (a) Signer chips on draft envelopes read "Not sent yet" (label decided
     at the call sites, which know the envelope status).
   - (c) Resend invite hidden on drafts.
   - (d)(e) Replace-signer / Replace-document dialog and toast copy becomes
     draft-aware (no email claims).
   - (f) CC chips on drafts read "Not sent yet".
   - (g) `inView(row, "inbox")` excludes drafts.
   - (h) `expiryHint` also renders for drafts (including overdue styling).

### Error handling

- Wizard load failures (deleted draft, no access) surface the existing
  error alert and link back to the dashboard.
- On Save/Send, creation errors keep the user in the wizard with state
  intact (existing behavior); the old draft is deleted only after a 201.
- Duplicate of a source whose stored PDF is missing keeps the existing
  clean 409.

### Testing

- Backend TDD: duplicate-always-adhoc; value→prefill mapping (each copied
  type, each skipped type, values from the right submitter's role);
  draft access denial for non-sender submitters on detail/events/preview
  (and continued access for sender/admin); send-draft 422 on emptied or
  re-roled fields; docstring-only change for (k) needs no test.
- Frontend vitest: `inView` inbox/draft exclusion; label helpers for the
  new "Not sent yet" states if extracted into `labels.ts`.
- New Playwright e2e: compose → Save as draft → Edit draft (change signer
  set, expiration, move a field) → Send → sign → complete.
- Live browser walkthrough before merge (duplicate → wizard → edit
  everything → send).

## Rollout

Single PR. No migrations, no env changes, no cron impact. Existing drafts
created before this change work in the new wizard (they are ordinary
drafts; template-based ones become one-offs on first edit, per the
persistence model).
