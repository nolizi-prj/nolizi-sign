# DocuSeal architecture and product lessons for Pumasi Sign

**Review date:** 2026-09-01  
**Reference checkout:** `/home/m/dev/docuseal`  
**Method:** clean-room behavioral and architectural review. DocuSeal is AGPLv3
with additional terms; no DocuSeal source is copied into Pumasi.

## Executive conclusion

DocuSeal validates the overall Pumasi product direction, but its most valuable
lessons are below the visible feature list. A mature signing service needs
versioned inputs, durable work records, explicit delivery attempts, account
scoping, and recoverable asynchronous processing. Pumasi's Cloudflare Worker
can implement the same responsibilities without reproducing Rails, Sidekiq, or
Active Storage.

Pumasi should remain a Cloudflare-native product:

```text
Vue sender/signer UI
        |
Cloudflare Worker (routing, edge checks, health)
        |
SQLite Durable Object (workflow authority + durable outbox)
        |
R2 (immutable artifacts) + scheduled/alarm consumers
        |
mail / conversion / webhook / archive providers
```

The current single global Durable Object is acceptable for the private Phase 1
pilot, but organization tenancy must precede Phase 2 scale. Tenant ownership
must be explicit in every row and authorization query before introducing shared
templates, bulk send, API clients, or reporting.

## Repository structure observed

DocuSeal is a Rails monolith with several clearly separated responsibility
layers:

- Active Record models hold accounts, templates, versions, submissions,
  submitters, immutable completion summaries, events, webhooks, and attempts.
- Domain modules under `lib/` implement routing, PDF processing, certificate
  generation, template serialization/versioning, search, and integrations.
- Sidekiq jobs isolate completion processing, expiration, email, indexing, and
  each webhook event type.
- Active Storage abstracts local/S3/GCS/Azure artifacts and keeps attachment
  metadata/checksums separate from domain records.
- Rails controllers expose both human UI workflows and a documented API.
- Vue components implement the WYSIWYG builder and responsive signing ceremony.
- Request, job, and system specifications cover API, lifecycle, settings,
  builder, signing, storage, and webhook behavior.

This separation is more important than the language/framework choice.

## Domain-model lessons

### Account boundary

DocuSeal carries `account_id` through templates, submissions, submitters,
events, configs, searches, webhooks, and completion summaries. Pumasi currently
uses owner identity as its main boundary. Before Phase 2, introduce stable
organizations and memberships, then require organization scope in every owner
route and index.

### Snapshot mutable definitions

A submission snapshots template fields, schema, submitter definitions,
variables, and preferences. Template versions are content-addressed, and
recipient corrections have version records. This prevents a later template or
recipient edit from silently changing the meaning of a sent agreement.

Pumasi already copies fields/documents into envelopes, but should add:

- `template_versions` with content hash and author;
- `envelope_snapshots` or explicit snapshot version/hash columns;
- append-only `submitter_versions` for corrected name/email/role/order;
- evidence references to the exact snapshot used at send and completion.

### Artifact separation

Original/template documents, per-signer results, combined results, previews,
attachments, and audit trails are separate artifacts. Completed-document hashes
are queryable records rather than certificate text alone. Pumasi now has
original, completed, certificate, signer attachments, and SHA-256 evidence; it
should next add a durable artifact inventory with type, R2 key, size, hash,
generation state, and retention state.

### Explicit event vocabulary

DocuSeal distinguishes send, bounce, complaint, reminder, open, click,
verification, view, start, completion, decline, delegation, SMS, and KBA events.
Pumasi should keep its audit trail legally meaningful and introduce a separate
operational event stream for delivery and product telemetry. Provider delivery
events must not be confused with signer evidence.

## Lifecycle and edge cases

### Routing

DocuSeal handles free-order, preserved serial order, explicit parallel groups,
and viewers placed at routing stages. Invitations for the next group are sent
only after every required signer in the current group completes.

Pumasi supports serial/parallel order and CCs. Add tests for:

- parallel group completion with one slow signer;
- CC notification at start, at a routing group, and only at completion;
- optional/viewer-only envelopes;
- corrected recipient while waiting in a later group;
- expiration between group completion and next invitation;
- duplicate completion and notification retries.

### Completion and concurrency

DocuSeal uses unique completion/generation records, find-or-create behavior,
database predicates, and retryable jobs. Pumasi already fails closed and offers
completion retry, but completion is still a large synchronous operation.

Introduce an artifact-generation state machine:

```text
pending -> generating -> complete
                    \-> failed -> retrying -> complete
```

Each transition needs an attempt number, timestamps, error category, and stable
idempotency key. Only `complete` may move the envelope to completed or enqueue
completion notifications.

### Expiration

Scheduled expiration must re-check current state, archived/declined/completed
status, and the exact deadline associated with the scheduled work. Pumasi's
hourly sweep re-checks status/deadline; retain this invariant when alarms or
per-envelope jobs are introduced.

### File safety

DocuSeal rejects a broad dangerous-extension list for signer uploads in addition
to content handling. Pumasi validates PDF/PNG/JPEG magic bytes, which is stronger
than extension alone, but should also:

- reject dangerous and misleading filenames;
- normalize Unicode filenames and strip control characters;
- cap image dimensions/page count and decompressed PDF complexity;
- add malware scanning before external distribution for enterprise use;
- quarantine an upload until normalization succeeds.

### Email and delivery

Mature delivery distinguishes queued, provider accepted, delivered, bounced,
complained, opened, and clicked. Pumasi currently sends synchronously/best-effort
and logs failures. Phase 1 needs durable send attempts and retry status; provider
bounce/complaint ingestion can follow in Phase 2.

### Identity and correction

Recipient corrections must preserve the old identity and invalidate old access
where appropriate. Evidence should say who was originally invited, what changed,
who changed it, and which verified identity signed. Never rewrite historical
events to contain the new address.

## UI/UX lessons

Useful patterns to adopt in Pumasi's own visual language:

- Mobile-specific field placement and signing controls rather than shrinking the
  desktop builder.
- Dedicated field-step components with one validation contract per type.
- Accessible overlay areas that follow document order and expose field purpose,
  state, and errors to assistive technology.
- Revisions/history in the template builder.
- Document crop/reorder/replace workflows that preserve or explicitly invalidate
  field coordinates.
- Signing steps for verification, attachment, signature/initials, review, and
  completion instead of one undifferentiated form.
- Preview modes that show conditional visibility and each recipient's view.

Pumasi should not adopt unsupported legal/compliance marketing language merely
because another product displays it.

## Integration lessons

### API

DocuSeal exposes templates, submissions, submitters, documents, attachments,
events, merge, and verify operations. Pumasi Phase 3 should provide versioned
resources, scoped credentials, idempotency keys, cursor pagination, stable error
codes, and an explicit sandbox. Browser routes must not become the public API by
accident.

### Webhooks

The reference design stores webhook endpoints encrypted, filters subscriptions,
uses a stable event UUID, signs payloads, records every attempt/response, and
retries completion events with exponential backoff.

Pumasi should use a Durable Object outbox:

1. Commit domain transition and outbox row atomically.
2. A scheduled/alarm consumer claims a due delivery.
3. Send a versioned payload with event ID, timestamp, and HMAC signature.
4. Record status/latency/safe response excerpt.
5. Retry with bounded exponential backoff and jitter.
6. Allow operator replay without creating a new domain event.

### Storage and providers

Provider adapters should sit behind narrow interfaces. R2 remains canonical for
Pumasi documents; SharePoint/OneDrive/Google Drive are asynchronous destinations,
not alternate workflow authorities.

## Revised phase boundaries

### Phase 1: trustworthy signing core

Keep all currently implemented functions, including ordered multi-document
envelopes. Add these release blockers:

1. Field-specific signature/initials artifacts (implemented in source).
2. Durable completion-generation state and attempts.
3. Durable email outbox with retry and visible delivery failures.
4. Envelope/recipient snapshot hashes and immutable correction history.
5. Artifact inventory and verification endpoint/tool.
6. Filename/content hardening and complexity limits.
7. Worker-backed browser lifecycle, mobile accessibility audit, alerting, and
   demonstrated DO+R2 recovery drill.

### Phase 2: repeatable team workflows

Order the phase by dependency:

1. Organizations, memberships, roles, tenant-scoped storage/query invariants.
2. Template versions, revisions, folders, ownership, sharing, and publishing.
3. Contacts, recipient history, and reusable custom fields.
4. Bulk send with row isolation, idempotency, cancellation, and result export.
5. Public template links with abuse controls and optional verification.
6. Conditional/calculated fields and small, explainable routing rules.
7. Delegation/reassignment/approvals with immutable identity versions.
8. Delivery events, bounce/complaint handling, reporting, retention, and admin.

### Phase 3: platform and advanced assurance

Order the phase around one durable integration substrate:

1. Outbox foundation, signed webhooks, attempts, replay, and event versioning.
2. Versioned REST API, scoped service accounts/OAuth, idempotency, and sandbox.
3. Embedded sender/signer SDKs with origin and redirect allowlists.
4. Storage/CRM/automation integrations through asynchronous adapters.
5. SMS/voice/ID verification providers with assurance-level evidence.
6. SAML/OIDC SSO, SCIM, domain claiming, and enterprise session policy.
7. Regional storage/retention controls and higher-assurance signature providers.
8. Advanced operational analytics and SLA instrumentation.

## Immediate engineering backlog

1. Complete Phase 1 live staging lifecycle and accessibility evidence.
2. Add completion-generation attempt records and make notifications consume an
   outbox rather than run inside the signing request.
3. Add immutable recipient correction versions and snapshot hash to certificate.
4. Add artifact inventory/hash verification and backup export tooling.
5. Add upload filename/content hardening tests.
6. Design the organization/tenant schema before any Phase 2 feature work.

