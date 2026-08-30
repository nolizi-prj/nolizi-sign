# Envelope usability fixes — view document, file reorder, signers-step prefill

Date: 2026-08-07. Three independent fixes driven by user feedback.

## 1. View document from the envelope detail page

**Problem.** After sending, the envelope detail page offers no way to open the
document. "Signed PDF"/"Certificate" appear only once the envelope completes;
while pending there is nothing.

**Design.** Every submission's underlying PDF already exists in storage:
`submission.template.pdf_key` (one-off sends create a hidden template too).

- Frontend: a "View document" button on `EnvelopeDetailView` in the header
  action row, visible for **every** envelope status and every viewer the page
  loads for, opening `/api/files/template-pdf/{template.id}` in a new tab.
  `SubmissionOut.template` already carries the id.
- Backend: extend `get_template_pdf` access — currently admins, the
  template's creator, submitters on any submission of the template, or an
  external signer via cookie — with **the sender (`created_by`) of any
  submission using the template**. (A sender using someone else's template
  without being a signer on it would otherwise 403.)

## 2. Reorder picked files in the send wizard

**Problem.** Step 1 merges the picked files "in this order" with no way to
rearrange; the only workaround is re-picking everything.

**Design.** Keep the `v-file-input` for picking (hide its chips); render the
picked files below it as a list, one row per file: filename, ↑/↓ buttons
(disabled at the ends), and a per-file remove button. Any reorder or removal
re-runs the existing merge flow (`onAdhocFilesChosen` path) with the new
order — the stale-response generation guard already handles overlapping
merges. Placed fields are already reset on re-pick; same applies on reorder.
A reorder to a single remaining PDF follows the existing single-PDF fast
path. The title keeps auto-deriving from the first file only when it is
still empty.

## 3. Signers-step assignment trap (the "33 fields" report)

**Problem.** A template whose role names are emails (e.g.
"ashish@pumasi.ai") renders empty assignment dropdowns whose *labels* look
like filled-in values, so senders don't realize Continue is disabled because
no person is assigned. There is **no field-count limit** — 33 fields was
never the cause.

**Design.** Auto-fill + explain:

- On template selection, any role whose name is an exact case-insensitive
  match of an existing user's **email** is pre-assigned to that user
  (editable/clearable as usual). No user creation, no partial matches.
- When Continue is disabled on the signers step, show a caption next to it
  naming the actual blocker: unassigned roles ("Assign a person to every
  signer role to continue"), an empty title, or an incomplete CC row.
  Applies to both template and one-off modes.

## Error handling

No new failure modes: the view-document button reuses an existing endpoint
(404/403 behave as today); re-merge failures surface through the existing
`extractBlobError` alert; prefill only touches client state.

## Testing

- Backend: tests for the new sender-access rule on `template-pdf`
  (sender-not-creator-not-submitter can fetch; unrelated user still 403).
- Frontend: `vue-tsc --noEmit` + `npm run build`; manual pass through the
  local run recipe for reorder, prefill, and the Continue captions.
