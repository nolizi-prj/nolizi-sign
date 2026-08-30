# SharePoint archive for completed envelopes

**Date:** 2026-08-01
**Status:** Approved design, pending implementation plan

## Goal

Mirror every completed envelope's artifacts (signed PDF + signature
certificate PDF) to a SharePoint document library, so signed documents are
discoverable and retained where the rest of Pumasi's files live.

SharePoint is an **archive/mirror only**. The Railway volume (`DATA_DIR`)
remains the source of truth: the app keeps serving downloads, the signing
flow never depends on SharePoint, and a Graph outage must never block or
fail an envelope's completion.

## Destination (already provisioned)

- SharePoint site **"Pumasi Operations"**
  (`https://pumasiinc.sharepoint.com/sites/Operations`), document library
  **"Legal"**, folder **`Signed_document_archive`**.
- App registration **EmailAutomationApp** (`MS_CLIENT_ID`) holds the
  `Sites.Selected` application permission with admin consent, and has been
  granted the **write** role on that site via
  `POST /sites/{site-id}/permissions` (done 2026-08-01).
- Visibility decision: everyone with access to the "Pumasi Operations"
  site can browse the whole archive. SharePoint permissions govern the
  archive; the app does not try to mirror per-envelope permissions.

New environment variables (Railway; empty in local dev, which disables the
feature entirely):

| Variable | Value |
| --- | --- |
| `SP_DRIVE_ID` | `b!yfEmPUN-7UyS1Z6xZQVh6YppZfIgzWZBnTKWVL9zhK0zexu6vG5qQ5PA-VUSVyeB` |
| `SP_ARCHIVE_FOLDER` | `Signed_document_archive` |

The drive id alone addresses the library (`/drives/{id}/...`); the site id
is not needed at runtime. Auth reuses the existing
`MS_TENANT_ID`/`MS_CLIENT_ID`/`MS_CLIENT_SECRET`.

## Folder layout

```
Signed_document_archive/
  {owner email}/                e.g. jane@pumasi.ai  (envelope creator)
    {year}/                     from completed_at, UTC, e.g. 2026
      {sanitized title} ({id})/ e.g. NDA - Acme Corp (42)/
        {UTC date} {sanitized title} ({id}) - signed.pdf
                                  e.g. 2026-08-02 NDA - Acme Corp (42) - signed.pdf
        {UTC date} {sanitized title} ({id}) - certificate.pdf
                                  (omitted when the envelope has no separate
                                   certificate — pre-issue-#15 envelopes)
```

Filenames are self-describing (date + title + id + artifact kind) because
archived files get downloaded, emailed, and surfaced by SharePoint search
detached from their folder. (Amended 2026-08-02; the original design used
bare `signed.pdf`/`certificate.pdf`.)

Title sanitization: replace characters SharePoint rejects in item names
(`" * : < > ? / \ |`, plus leading/trailing whitespace and trailing dots)
with `_`, collapse runs, and truncate the title segment to 100 characters.
The ` ({id})` suffix keeps folders unique regardless of sanitization.
Uploads use `@microsoft.graph.conflictBehavior=replace` so retries are
idempotent.

## Architecture

### New module: `backend/app/sharepoint.py`

Modeled directly on `mailer.py`'s contract:

- Public entry point `archive_submission(db, storage, submission, settings) -> bool`
  — never raises; any failure (missing config, token failure, HTTP error,
  oversized file) is logged (no document contents, titles, or tokens) and
  returns `False`.
- Reuses the module-level MSAL client-credentials machinery. The existing
  `mailer._get_msal_app`/`_acquire_token` move to a small shared module
  (`backend/app/graph.py`) imported by both `mailer` and `sharepoint`, so
  the two features share one token cache per credential triple.
- Upload per file: simple `PUT /drives/{drive}/root:/{path}:/content` for
  files ≤ 4 MB; `createUploadSession` + chunked upload above that (signed
  PDFs with scanned pages can exceed 4 MB).
- Feature flag: if `SP_DRIVE_ID` is empty, `archive_submission` returns
  `False` ("skipped") without logging errors — local dev and tests run
  with the feature off by default.

### Schema change (Alembic migration)

Two nullable columns on `submissions`:

- `archived_at TIMESTAMPTZ NULL` — set on successful upload of all
  artifacts.
- `archive_url VARCHAR(1024) NULL` — the SharePoint `webUrl` of the
  envelope's folder, for future UI use.

`archived_at IS NULL AND status = 'completed'` is the retry predicate; no
separate status enum is needed. Existing completed envelopes are naturally
backfilled by the daily sweep (below) because their `archived_at` is NULL.

### Triggers

1. **On completion (primary path):** in the same caller positions that send
   the completion email today (after `db.commit()`, once
   `finalize_if_ready` returned `FINALIZED` and status is `completed`) —
   the last signer's `/complete` and `POST /api/submissions/{id}/retry-completion`.
   Runs synchronously after the response-critical work is committed;
   failure only logs and leaves `archived_at` NULL.
2. **Daily sweep (retry + backfill):** `POST /api/jobs/daily` gains a step
   that selects completed submissions with `archived_at IS NULL AND
   signed_pdf_key IS NOT NULL`, attempts `archive_submission` for each, and
   reports `{"archived": n, "archive_failed": m}` in the response body.
   Best-effort like the backup steps: never raises, one failure doesn't
   stop the sweep. Skipped entirely (reported as `0`/`0`) when
   `SP_DRIVE_ID` is unset, so a disabled feature doesn't log a failure per
   envelope every day.

### Data flow (upload)

1. Read `signed.pdf` (and `certificate.pdf` if present) from `FileStorage`.
2. Acquire app-only Graph token (shared MSAL cache).
3. Ensure folder path exists implicitly — `PUT ...root:/{full path}/signed.pdf:/content`
   auto-creates intermediate folders; no separate folder-creation calls.
4. On success of **all** artifacts: set `archived_at = now(UTC)` and
   `archive_url`, commit (own short transaction; never inside the signing
   request's transaction).

### Error handling

- Same "never raise to callers" contract as `mailer.send`.
- No retry loop inside a single attempt (unlike mail's 3 retries) — the
  daily sweep is the retry mechanism, and completion-time latency should
  stay low. A single attempt with a 30 s httpx timeout per request.
- Logs: submission id and HTTP status only; never titles, emails in URLs
  beyond what the path requires, tokens, or file contents.

### Out of scope (YAGNI)

- Frontend "View in SharePoint" link (column exists; UI can come later).
- Archiving cancelled envelopes or original uploads.
- Deleting/moving SharePoint files when an envelope is deleted.
- Mirroring app permissions into SharePoint.
- A new audit event type (would require widening the DB check constraint;
  `archived_at` already records the fact).

## Testing

- Unit tests for the path builder/sanitizer (illegal characters, long
  titles, uniqueness via id suffix).
- `sharepoint.archive_submission` tests via `httpx.MockTransport` +
  monkeypatched token acquisition (same seams as `mailer` tests): success
  (small file PUT), large-file upload-session path, HTTP failure → `False`
  and no DB change, feature disabled → skipped.
- Completion-trigger test: last signer completes → archive attempted after
  commit; archive failure doesn't affect the response or envelope state.
- Daily-job test: sweep picks up completed-but-unarchived submissions,
  reports counts, tolerates per-item failure.
- No e2e/Playwright changes (no UI change).

## Operational notes

- `Sites.FullControl.All` must be removed from EmailAutomationApp now that
  the site grant exists (manual step in the Azure portal; the grant done on
  2026-08-01 survives removal).
- Rollout order: merge + deploy code (feature dormant) → set `SP_DRIVE_ID`
  and `SP_ARCHIVE_FOLDER` in Railway → next daily job backfills all
  existing completed envelopes.
