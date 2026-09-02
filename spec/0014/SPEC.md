# Specification

- `POST /api/submissions/adhoc` accepts repeated `documents` multipart fields.
- Every file is normalized independently to PDF and stored in
  `submission_documents` with a stable zero-based order, page count, and page
  start in the combined rendition.
- The ordered combined PDF remains the field-coordinate and stamping surface.
- `GET /api/submissions/:id/documents` returns the ordered document manifest.
- `GET /api/files/submission-document/:id` returns one normalized document only
  to the sender or an envelope signer.
- The legacy singular `file` field continues to work.
- Deleting a draft removes its independent document objects and rows.
- The send wizard accepts repeated selections, removal, and order changes and
  submits the original ordered files rather than only the merged preview.

Acceptance cases A-900 and A-901 cover ordering, page boundaries, independent
download, and authorization.
