# Specification

- The envelope owner may replace documents only while status is `draft` or
  `pending` and no submitter has status `signed`.
- The request accepts repeated `documents` fields and legacy singular `file`.
- Files are normalized and validated completely before database mutation.
- A replacement that would leave an existing field beyond the new final page
  is rejected; fields are never silently discarded or moved.
- New R2 objects are written before database references switch. Old originals,
  completed renditions, independent documents, and ad-hoc template objects are
  removed after the switch.
- The replacement updates the combined original, ordered manifest, page count,
  and ad-hoc template rendition and clears any stale completion artefact.
- Audit history records `document_replaced`, filenames, and page count.
- The UI accepts and orders multiple replacement documents.

Acceptance cases A-902 and A-903 cover successful replacement, cleanup,
ordering, audit evidence, field safety, and the signed-recipient guard.
