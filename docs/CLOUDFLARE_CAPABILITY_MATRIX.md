# Cloudflare production capability matrix

**Baseline date:** 2026-09-01  
**Canonical backend:** `service/`  
**Legacy reference:** `backend/`

`Available` means implemented in Worker source. It does not mean that the current
commit has been deployed.

## Phase 1 capability baseline

| Capability | Worker status | Next action |
| --- | --- | --- |
| Vue application served with API | Available | Keep Worker asset/API routing test |
| Email-code login; Google/Microsoft OAuth | Available | Expand abuse and delivery failure coverage |
| Per-user authorization/scoping | Available | Add cross-owner negative HTTP cases |
| Organization/team tenancy | Missing | Phase 2; define tenant model before sharding |
| Ordered multi-document envelopes, upload and merge | Available in source | Add deployed R2 integration coverage |
| Broad Office/OpenDocument/text/email/image conversion | Available in source | Microsoft Graph credentials required except PDF, PNG/JPEG, TXT/CSV |
| Office-to-PDF conversion through Graph | Available | Test timeout, failure, and remote cleanup |
| Immutable originals and artifact hashes | Available in source | Verify R2 artifacts in staging |
| Draft create/resume/edit/delete | Available | Add full Worker route coverage |
| Signers, CC, serial/parallel order | Available | Expand routing lifecycle cases |
| Corrections, reminder/resend, expiration | Available | Test schedules, caps, and audit consequences |
| Void/cancel, decline, archive, copy | Available | Keep terminal-state and byte-isolation tests |
| Replace ordered documents | Available in source | Verify correction and R2 cleanup in staging |
| Retry failed completion | Available in source | Verify in staging before marking released |
| Template list/create/use | Available in source | Verify in staging before marking released |
| Template get/update/share/copy/archive | Available in source | Verify in staging before marking released |
| Save envelope as template | Available in source | Verify in staging before marking released |
| Accountless signer link and code | Available | Add expiry, attempt, and rate-limit cases |
| Consent/disclosure evidence | Available in source | Verify certificate rendering in staging |
| Guided required-field signing | Frontend available | Add Worker-backed browser test |
| Draw/type/upload/reuse signature | Available | Add authorization and artifact coverage |
| Signer attachment field | Available in source | Verify in staging before marking released |
| Safe signer-attachment filenames | Available in source | Verify deceptive-extension rejection in staging |
| Completed stamped PDF | Available | Continue deterministic multi-signer tests |
| Separate completion certificate | Available in source | Verify download and hashes in staging |
| Append-only audit events | Available | Prove no public mutation route; cover exceptions |
| Envelope detail/events/form data | Available | Add owner/signer authorization cases |
| Branding | Available | Add recipient-shell rendering test |
| Admin/team permissions | Missing | Phase 2 after organization model |
| SharePoint completion archive | Missing | Phase 2 asynchronous integration |

## Ordered Cloudflare migration backlog

### Milestone 1 — prove the existing production core

1. Add a Worker-backed HTTP/browser lifecycle suite; the FastAPI Playwright suite
   is not production evidence.
2. Cover R2, Graph conversion failure/cleanup, and mail seams.
3. Verify hashes, consent, certificate, and audit immutability requirements.
4. Isolated staging Worker, Durable Object, R2 bucket, domain, and secrets were
   deployed on 2026-09-01. Public liveness/readiness and OAuth initiation passed;
   complete and retain the full browser lifecycle release record.

### Milestone 2 — close visible frontend contract gaps

1. Complete template get/update/share/copy/archive and save-as-template.
2. Implement retry-completion with idempotent completion and audit behavior.
3. Implement signer attachments end to end.
4. Implement replace-document with explicit handling for existing fields.

### Milestone 3 — production readiness

1. Tune and observe persistent limits covering login, signer-code, document writes, standalone conversion, and feedback in staging.
2. Execute the documented backup/export and restore drill for state and R2
   artifacts (`docs/operations/CLOUDFLARE_RELEASE_AND_RECOVERY.md`).
3. Readiness and structured failure logs are available in source; configure
   Cloudflare monitors/alerts and retain a staging drill record.
4. Threat-model, accessibility, and security review of sender/signer paths.
5. Add a durable notification outbox and explicit completion-generation attempts;
   synchronous best-effort mail is not sufficient for Phase 1 release.

## Definition of done for each ported capability

- Worker route and storage behavior implemented.
- Authorization, invalid state, and retry behavior tested.
- Audit/evidence consequences specified and tested.
- Frontend covers loading, empty, success, and actionable failure states.
- Worker tests and frontend typecheck/build pass.
- Staging lifecycle verification passes.
- This matrix is updated in the same change.
