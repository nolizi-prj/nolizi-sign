# Cloudflare release and recovery runbook

**Scope:** the production backend in `service/` only. The FastAPI application in
`backend/` is not a production recovery source.

## Service-level objectives for the Phase 1 pilot

- `/api/health` is liveness: the Worker runtime can answer.
- `/api/ready` is readiness: the Worker can query its Durable Object SQLite
  store and list the bound R2 bucket. It returns 503 without dependency details
  when either check fails.
- Alert after two consecutive readiness failures or any failed scheduled expiry
  invocation. During the private pilot, a human must acknowledge the alert.
- Preserve completed agreements and evidence indefinitely until a reviewed
  retention policy exists. Do not infer deletion policy from envelope status.

## Isolated staging environment

Do not point a staging Worker at either production storage binding. Before the
first staging deployment, create:

1. the configured `pumasi-sign-staging` Worker and
   `https://sign-staging.pumasi.ai` URL;
2. a distinct SQLite Durable Object namespace;
3. the distinct `pumasi-sign-documents-staging` R2 bucket;
4. staging-only OAuth redirect URLs, Graph credentials, mail sender, and secrets;
5. a Cloudflare monitor for `/api/ready` and log/notification rules for 5xx,
   `readiness.failed`, and failed cron invocations.

The Wrangler `env.staging` block declares these names. A missing binding must
make readiness fail; never fall back to production. Deploying is an operator
action and is not performed by the test suite.

## Pre-release gate

### Product version and release identity

`VERSION` is the single authoritative human-readable product version and uses
Semantic Versioning while the product is pre-1.0:

- patch (`0.2.1`) for backward-compatible fixes;
- minor (`0.3.0`) for meaningful backward-compatible capabilities;
- major (`1.0.0`) for the reviewed public-stability milestone or an incompatible change.

Prepare a release only through:

```sh
npm run version:set -- 0.2.1
npm run version:check
```

The command synchronizes both deployable package manifests and the Worker's
compiled version constant. Vite reads `VERSION` directly and embeds the product
version, Git commit, UTC build time, and deployment environment. CI rejects any
version drift. Feedback reports carry this build identity, and `/api/health`
plus `/api/ready` report the product version deployed by the Worker.

After staging verification, commit the synchronized version, tag that exact
commit as `v<version>`, and deploy that commit to production. Record the Git tag,
full commit SHA, Cloudflare staging and production Version IDs, UTC deployment
times, and operator in the release record. A Cloudflare Version ID identifies an
edge artifact; it does not replace the product version or Git tag.

Build the SPA in `frontend/`, but always run Wrangler from `service/`:

```sh
cd frontend && PUMASI_DEPLOY_ENV=staging npm run build
cd ../service && npx wrangler deploy --env staging
```

Do not deploy from `frontend/`; the Cloudflare Vite plugin generates a separate
preview-Worker configuration there, which is not the service behind the Pumasi
Sign domains.

**Staging provisioned:** 2026-09-01. The public home page, `/api/health`,
`/api/ready`, and Google/Microsoft OAuth initiation passed immediately after
deployment. Full lifecycle, accessibility, alerting, and restore-drill evidence
remain required below.

Run from the repository root:

```sh
npm run version:check
npm test
git diff --check
```

Then deploy to staging and verify, using non-production users and documents:

- liveness and readiness return 200;
- PDF and Office conversion, ordered multi-document upload, field placement,
  accountless verification, consent, serial signing, and completion;
- original, completed PDF, and separate certificate download successfully;
- locally calculated SHA-256 values match the hashes shown by the application;
- correct, remind, decline, void, expiration, failed conversion, and failed
  completion/retry paths;
- an unrelated account cannot retrieve any document or certificate;
- mobile keyboard/screen-reader completion and visible focus;
- no unexpected 5xx or secrets/document contents in Worker logs.

Record the staging deployment version, time, tester, envelope IDs, artifact
hashes, and result. Production promotion requires a second person to review the
record during the pilot.

## Backup boundary

Recovery has two independent parts:

- Durable Object SQLite state: Cloudflare point-in-time recovery bookmarks cover
  the object database for the provider's documented window.
- R2 artifacts: Durable Object recovery does not restore document objects. Copy
  R2 objects to a separately controlled backup bucket or external object store.

A backup is not successful until an inventory (key, size, checksum/etag, backup
time) is stored outside the source bucket and a sample can be restored and
hash-verified. Use credentials restricted to the source and backup buckets; do
not place them in this repository or Worker variables.

## Recovery procedure

1. Declare the incident, stop deployments, record the UTC detection time, Worker
   version, affected envelope IDs, current Durable Object bookmark, and R2
   inventory. Preserve logs.
2. Put the service into maintenance at the edge or otherwise prevent writes.
   Confirm `/api/ready` is not being used as a write gate by clients.
3. Select a recovery timestamp immediately before the first known bad write.
   Retain the pre-restore bookmark so the restore itself can be reversed.
4. Restore the production Durable Object using Cloudflare's point-in-time
   recovery workflow. Never test this first in production.
5. Restore missing or damaged R2 keys from the independent backup inventory.
   Do not overwrite a differing object until its current bytes and metadata have
   been preserved for investigation.
6. Verify readiness, row/artifact references, and SHA-256 hashes for every
   affected original, completed PDF, and certificate. Exercise downloads through
   the authorized application routes, not directly from a public bucket.
7. Run one controlled lifecycle in staging, then a read-only production smoke
   check. Re-enable writes only after two-person review.
8. Record recovery point, recovered keys, verification output, data-loss window,
   and follow-up actions. Notify affected users if the incident policy requires.

## Required restore drill

At least quarterly and before the Phase 1 public release, restore a staging
Durable Object to a chosen bookmark and restore a sampled R2 inventory into a
fresh staging bucket. Verify database counts plus artifact hashes and downloads.
Record actual recovery time and maximum data-loss window. A written procedure
without this evidence does not satisfy the Phase 1 exit criterion.

## Current external blockers

The repository cannot create account resources, configure monitors, export the
production R2 bucket, or execute a staging PITR drill without Cloudflare account
access and named staging resources. Those operator steps remain release gates.
