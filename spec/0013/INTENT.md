# INTENT 0013 — signer-supplied supporting files

Attachment fields are visible in the signer UI, but the Cloudflare API has no
upload route and completion treats an attachment id as ordinary text. Implement
the secure round trip and include supplied PDF/image pages in the executed
agreement before its certificate.

