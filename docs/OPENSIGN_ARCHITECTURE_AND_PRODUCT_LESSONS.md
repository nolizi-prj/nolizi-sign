# OpenSign architecture and product lessons for Pumasi Sign

**Review date:** 2026-09-01  
**Reference checkout:** `/home/m/dev/opensign`  
**Method:** clean-room behavioral and architectural review. OpenSign is AGPLv3;
no OpenSign source or visual assets are copied into Pumasi Sign.

## Executive conclusion

OpenSign confirms that the planned three-phase product surface is broad enough:
templates, ordered routing, OTP, bulk send, contacts, a document vault, email
customization, reports, API/integrations, and digital certificates all appear in
a mature open-source implementation. Its strongest lesson is architectural:
features implemented with privileged database access still require an explicit,
server-derived authorization and state-transition boundary.

Pumasi should retain its Cloudflare-native structure and use the Durable Object
as the workflow authority. It should not reproduce OpenSign's Parse/Mongo model.

## Repository structure observed

- A JavaScript monorepo contains a React/Vite client and a Parse Server backend.
- MongoDB/Parse classes represent documents, templates, contacts, users,
  signatures, tenants, OTPs, reports, and preferences.
- Cloud Functions implement document creation, signing, duplication, forwarding,
  bulk creation, mail, reporting, signed URLs, and certificate generation.
- before/after-save hooks apply defaults, metadata, and Parse ACLs.
- `pdf-lib` plus a PKCS#12 signer produces executed PDFs and certificates.
- S3-compatible object storage or local Parse files hold artifacts; short-lived
  signed URLs mediate downloads.
- The React application has separate builder, signing, bulk-send, email-editor,
  Drive, report, preference, and verification components.
- Database migrations show product evolution, including decline reasons, OTP,
  BCC/CC, redirect URLs, signature types, pen colors, email editing, normalized
  email, and strict signing order.

## Features and UX worth learning from

- A saved signature can include signature, initials, stamp, name, and pen-color
  preferences.
- Routing distinguishes ordinary send-in-order behavior from strict enforcement;
  the signer endpoint rechecks prior completion rather than relying on email order.
- Bulk send reports partial failures to the sender and limits concurrency.
- Contacts, templates, Drive folders, reports, and filename/date/timezone settings
  support repeated daily use after the signing core is established.
- Viewer, approver, signer, and prefill roles are reflected in routing and
  completion behavior.
- Forwarding a completed copy, completion redirects, BCC/CC, customizable sender
  identity, and mail-template variables cover common operational requests.
- The client includes page reordering, prefill, zoom/pinch behavior, guided
  previous/next navigation, draft handling, and localization.

These patterns should be expressed in Pumasi's own UI system and terminology.

## Edge cases and architecture lessons

### Authorization must precede privileged access

Several OpenSign functions query or save with Parse's master key and then apply
endpoint-specific checks. Some accept a document, contact, or user identifier
from request parameters. That makes every function responsible for rebuilding
the authorization boundary correctly.

Pumasi should keep deriving the owner or signer from its authenticated cookie,
scope every query to that principal and envelope, return 404 for cross-tenant
objects, and reserve privileged storage access for implementation—not identity.
Phase 2 organization tenancy needs explicit `organization_id` columns and
membership predicates, not UI-only roles or after-save ACL repair.

### Completion is a state machine, not an event count

OpenSign's signing path appends mutable audit entries, compares completion-event
counts with relevant placeholders, writes a new PDF, uploads it, changes the
document, then sends notifications and generates a certificate. A crash between
those steps can leave an ambiguous partially completed record.

Pumasi already verifies each submitter row, fails closed if artifact generation
fails, hashes artifacts, and exposes retry-completion. The next improvement is an
explicit, idempotent generation record with `pending/generating/failed/complete`
state and attempt history. Only the final committed state may enqueue completion
notifications.

### OTP must be challenge-scoped and consumable

OpenSign's general OTP record is keyed by email and the reviewed implementation
does not visibly enforce expiry, attempt limits, or one-time consumption in the
verification function. Pumasi's codes are scoped to a login or submitter,
expire, are consumed, and have persistent request/verification limits. Preserve
those properties; add a hashed-code migration before public launch so plaintext
codes do not remain in storage.

### Signing order is enforced at action time

Emailing only the next signer improves UX but is not authorization. OpenSign's
later strict-order addition illustrates why the completion endpoint must reject
an early signer even if they possess an old or forwarded link. Pumasi already
does this with `submitterTurn`; retain the check on decline and every future
approver/delegation action as well as completion.

### Audit evidence and product telemetry are different

OpenSign stores view/sign activities in a document array, updating an existing
view entry for a contact. That is convenient for UI but loses repeated-view
history and makes concurrent array updates vulnerable to lost events. Pumasi's
append-only event rows are a better evidence base. Delivery attempts, page
views, opens, and clicks should use a separate operational stream with privacy
limits rather than inflate or rewrite the legal audit trail.

### Files need object binding and safe names

Short signed-URL TTLs are useful, but a URL parameter must be proven to belong
to the authorized document before it is signed. Object keys should be stable and
opaque rather than inferred only from a URL basename. Upload filenames must be
treated as untrusted metadata. Pumasi now verifies attachment bytes and, under
spec 0023, rejects misleading extensions and normalizes stored names.

### Background work must be durable

OpenSign contains concurrency controls and failure summaries for bulk send, but
many notification calls are best-effort and some are intentionally not awaited.
Pumasi Phase 1 should implement a durable email outbox with stable idempotency
keys, attempt rows, exponential retry, terminal failure visibility, and provider
message IDs. Phase 2 bulk send should create one isolated envelope per row and a
batch summary; one row must never roll back or expose another.

### Test breadth is part of the architecture

The inspected OpenSign server specification is largely the Parse starter test,
and the root test script states that tests are not configured. The feature set
therefore should not be treated as evidence that lifecycle, tenant, retry, and
concurrency cases are safe. Pumasi should continue requiring Worker contract
tests plus staging/browser evidence for every production capability.

## Improvements to Pumasi's phased plan

### Phase 1 additions or clarifications

- Add hashed, challenge-scoped verification codes while retaining expiry,
  consumption, resend delay, and attempt limits.
- Add a durable notification outbox and expose failed-delivery state to senders.
- Add completion-generation state/attempt records before moving stamping async.
- Enforce byte-derived attachment types and safe filenames (implemented in
  spec 0023); later add size/page/decompression limits and malware quarantine.
- Test routing authorization at invitation, view, decline, complete, resend,
  correction, and download—not merely in the UI.
- Preserve every view/evidence event append-only; aggregate for display without
  rewriting source events.

### Phase 2 refinements

- Treat contacts as organization-scoped suggestions, with normalized email and
  duplicate/merge behavior.
- Add per-account date, timezone, download-filename, sender-name, and signature
  preferences alongside shared templates and roles.
- Design the document vault as views over artifact metadata and retention state,
  not a second copy of envelope files.
- Bulk-send previews must validate every row and show queued/created/failed state,
  cancellation, safe retry, and per-row isolation.
- Add forwarding/delegation only with explicit custody, authorization, access
  revocation, and audit semantics.

### Phase 3 refinements

- Webhooks need signed, versioned events, per-endpoint delivery attempts, replay,
  backoff, disablement after persistent failure, and a debugger.
- Redirect URLs must be allowlisted per application/account and never accepted
  blindly from a document request.
- Integration downloads must resolve an artifact by authorized ID and then mint
  a short-lived URL; clients may not submit arbitrary storage URLs for signing.
- Digital certificate support should be provider/key-version aware and record
  which key signed which artifact without exposing key material.

## Recommended next implementation sequence

1. Durable email outbox and delivery status.
2. Explicit completion-generation state and idempotent attempts.
3. Immutable envelope/recipient snapshot versions and artifact inventory.
4. Full Worker-backed mobile lifecycle and cross-principal authorization suite.
5. Staging R2/Graph/mail recovery drills and retained release evidence.

OpenSign's Drive, contacts, bulk send, email editor, reports, and integrations
remain valuable Phase 2/3 references, but none should displace these Phase 1
trust and recovery controls.
