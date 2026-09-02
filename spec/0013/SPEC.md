# SPEC 0013 — Cloudflare signer attachments

- Accept PDF/PNG/JPEG by magic bytes, not claimed MIME type; maximum 10 MB with
  R2 and 1 MB in the SQLite fallback.
- Upload requires the signer session, an active envelope, and an attachment
  field owned by that signer.
- An attachment id used at completion must belong to that submitter.
- Stamp the attachment filename in its field and append its pages before the
  final certificate page.
- Permit the sender and that envelope's verified signer to download the file.
- Draft deletion removes attachment objects and rows.
- Tests cover round trip, cross-signer rejection, bad bytes, and authorization.

