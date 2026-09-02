# Specification

- The signing view returns the current immutable disclosure version and text.
- Completion requires `consent_accepted: true` and that exact version before
  any signer state or evidence write.
- One immutable consent row stores submitter/envelope, full disclosure text and
  version, acceptance UTC time, IP, user agent, combined reviewed PDF SHA-256,
  and the ordered per-document filename/page-count/SHA-256 manifest.
- The appended certificate names each signer's disclosure version, acceptance
  time, and reviewed-document hash.
- Completion extracts and stores the certificate as a separate one-page PDF,
  records its SHA-256 beside original/completed hashes, and exposes it only to
  the owner and envelope participants at `/api/files/certificate/:id`.
- Draft deletion removes the certificate object when present.

Acceptance cases A-960 and A-961 cover the server gate, stored evidence,
separate artifact, authorization, and certificate hash.
