# Specification

- Login and signer code requests: at most 10 per email/submitter and source IP
  in a rolling hour, in addition to the existing one-minute resend guard.
- Login and signer verification: at most 6 attempts per identity and source IP
  in a rolling 15 minutes.
- Document creation, conversion, replacement, template upload, signature image,
  and signer attachment writes: at most 30 per authenticated principal (or
  anonymous source IP) in a rolling 10 minutes.
- Identifiers are SHA-256 hashed before persistence.
- Rejections return HTTP 429 and a positive `Retry-After` header and do not
  consume valid codes or parse upload bodies.
- Events older than 24 hours are pruned opportunistically.

Acceptance cases A-950 through A-952 cover email/IP rotation resistance,
signer isolation, persistence, headers, and early upload refusal.
