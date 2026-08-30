# Void language, per-user archive, and in-progress document preview

Date: 2026-08-09. Three DocuSign-alignment features the user accepted after
reviewing how DocuSign handles deletion and mid-flow visibility.

## 1. "Void" language

DocuSign's term for stopping an in-progress envelope is *void*; deleting
never truly destroys an envelope. Our "Cancel envelope" action is exactly
DocuSign's void, so the **user-facing language** changes to "Void
envelope"/"Voided" everywhere (buttons, dialogs, status chips, the external
signer's closed message). The backend status value stays ``cancelled`` —
no migration, no audit-history rewrite, API unchanged.

## 2. Per-user archive (hide, never delete)

Mirrors DocuSign's delete-is-hide model: any party to an envelope can
archive it out of their own views; nothing is destroyed and other
participants are unaffected. No user-facing true delete exists — real
purging would be a future admin retention policy.

- DB: ``submission_archives`` (submission_id, user_id, archived_at),
  unique per (submission, user). Alembic migration.
- API: ``POST /api/submissions/{id}/archive`` and ``/unarchive`` — allowed
  for the sender or any submitter; idempotent. ``SubmissionOut`` gains
  ``archived_by_me``.
- UI: the envelope browser gains an **Archived** sidebar view; archived
  envelopes disappear from Inbox/Sent/Completed/Action required. Row menu
  gains Archive / Unarchive. Archiving your own still-pending envelope
  asks whether to void it too (signers otherwise keep signing something
  you've hidden).

## 3. In-progress document preview

DocuSign shows each signer the document with all previous signers' data
and signatures already applied. Ours showed the bare unsigned PDF.

- ``stamping.build_signed_pdf`` accepts ``completed_at: datetime | None``;
  ``None`` watermarks pages "Pumasi Sign · Envelope {uid} · In progress"
  instead of "Completed {iso}".
- ``completion.build_preview_pdf(db, storage, submission) -> bytes``:
  completed envelope → the stored signed PDF; otherwise the template PDF
  with every *completed* submitter's fields stamped (labels included);
  no completed submitters → the bare template PDF (labels only).
- ``GET /api/files/document-preview/{submission_id}``: same access rule as
  signed-pdf (sender or submitter; external signer via the scoped cookie).
- UI: "View document" (envelope page, browser row menu) and the signing
  pages' base PDF switch from ``template-pdf/{template_id}`` to the
  preview endpoint — signer 2 sees signer 1's signature while signing.

Preview PDFs are generated on demand and not cached — internal-tool scale.

## Testing

Backend: stamping watermark variant; preview endpoint (partial content
visible via text extraction, access rules, external cookie); archive
endpoints (idempotence, authorization, ``archived_by_me``). Frontend:
type-check/build; full local e2e run; visual pass.
