# SPEC 0011 — fail closed and retry envelope completion

**Intent:** [INTENT.md](INTENT.md)  
**Target:** canonical Cloudflare backend in `service/`

## S1 · Completion invariant

`finalize` returns whether an executed PDF was created. It must not set
`submissions.status = 'completed'`, set `completed_at`, write a `completed` audit
event, or send completion mail unless the original document was loaded and the
completed artifact was stored in R2 or the SQLite fallback.

When the original cannot be loaded, it records one `completion_failed` audit
event containing a stable reason and returns failure. The envelope stays pending
and the already-completed submitter rows stay completed.

## S2 · Signer response

When the last signer triggers completion and `finalize` reports failure, the
complete route returns HTTP 503 with an explanation that the signature was saved
but the final document could not be produced. It must not claim `completed`.

## S3 · Sender retry

`POST /api/submissions/:id/retry-completion` is owner-authorized through the
existing submission route. It:

- returns the current completed envelope without running `finalize` again when
  status is already `completed`;
- refuses other terminal states with 409;
- refuses when any non-CC signer is unfinished, or no signer exists, with 409;
- calls `finalize` for a pending envelope whose non-CC signers are all signed;
- returns the updated `SubmissionOut` on success;
- returns 503 and leaves the envelope pending on another failure.

## S4 · Acceptance cases

- **A-608 amended:** missing source → 503, pending, no completion time/artifact,
  no completed event, one `completion_failed` event, signed PDF remains 404.
- **A-610:** restore the source after A-608's position and retry → 200 completed,
  one completed artifact/event; retry again → 200 with no second event or write.

## S5 · Verification

Build and run the service suite and its ran-nothing guard, then run root
`npm test`. No deployment is part of this change.

