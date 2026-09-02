# INTENT 0012 — make reusable templates work on Cloudflare

The Vue template experience was built against FastAPI, while the canonical
Worker only listed and created partial JSON templates. The real UI uploads
multipart files, autosaves fields, shares, copies, archives, and saves successful
envelopes as templates. Those calls currently fail or are absent.

This change completes that contract in `service/`, preserves independent PDF
bytes for copies, and makes shared templates visible and sendable without giving
non-owners mutation rights.

