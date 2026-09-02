# Architecture decision: Cloudflare is the canonical Pumasi Sign platform

**Decision date:** 2026-09-01  
**Status:** Accepted by the product owner  
**Scope:** Application development; this decision does not by itself authorize a
production deployment or destructive data migration.

## Decision

Pumasi Sign will be developed and released from `frontend/` and the canonical
Cloudflare backend in `service/`. Cloudflare R2 stores document artifacts and
Durable Object SQLite remains the current transactional application store.

`backend/` is the legacy Railway/FastAPI implementation. It remains temporarily
as a behavioral and test reference while required capabilities are ported. New
product features must target `service/`. A FastAPI-only implementation does not
make a feature available to users.

## Why

- The live domain already runs `service/` and the frontend it serves.
- The Worker already supports the core envelope lifecycle, accountless signing,
  OAuth, R2 files, Office conversion through Microsoft Graph, audit events, PDF
  completion, and email notifications.
- One canonical backend prevents behavior, tests, and security fixes from
  diverging across two products.
- Cloudflare removes routine server and filesystem operations while leaving an
  escape hatch for specialized document processing.

## Development rules

1. Every product issue names `service/` as its backend target unless it is
   explicitly a legacy-reference task.
2. Backend acceptance tests for new product behavior run against Worker code.
3. Frontend work is complete only when its required API contract exists in the
   Worker and is covered by a lifecycle test.
4. Production claims require deployment and live verification; a merged commit
   is not a release.
5. `backend/` receives no new feature work except security-critical maintenance
   or work required to extract and verify legacy behavior.
6. Do not delete `backend/` until the retirement gate below is met.

## Near-term storage decision

Keep the current Durable Object SQLite and R2 design during Phase 1. Do not
perform a D1 migration merely to modernize the diagram. The current single
Durable Object is acceptable for the private alpha, but its traffic, database
size, latency, and contention must be observable.

Introduce organization/envelope sharding or D1 only when measurements or Phase 2
query/reporting needs justify it. A migration requires a separate design covering
tenant isolation, identifiers, backfill, rollback, and evidence preservation.

## Heavy processing rule

Keep authorization, workflow transitions, hashing, ordinary PDF stamping, and R2
operations in Cloudflare. Continue using Microsoft Graph for Office conversion.
If OCR, LibreOffice, malware scanning, or large PDF processing becomes necessary,
put it behind an authenticated asynchronous job boundary. Evaluate a managed
service or Cloudflare Container first and a small hosted container service second.
A home desktop is not a production dependency.

## Required environments

Use separate local, staging, and production resources. Staging and production
must not share document buckets, state namespaces, OAuth callbacks, secrets, or
email behavior. Feature branches do not deploy into the production Worker.

## Legacy retirement gate

The FastAPI backend may be archived or removed only when:

- the production capability matrix has no required FastAPI-only feature;
- Worker lifecycle/browser tests cover Phase 1 critical paths and exceptions;
- production data backup and restore have been demonstrated;
- documentation and CI no longer use FastAPI as product evidence; and
- the product owner approves the explicit retirement change.

