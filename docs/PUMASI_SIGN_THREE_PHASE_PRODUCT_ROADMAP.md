# Pumasi Sign: three-phase e-signature product roadmap

**Date:** 2026-09-01  
**Inputs reviewed:** DocuSign product captures from 2026-08-30, the clean-room UX
specification, the product/site research, existing implementation plans, and the
current Pumasi Sign repository.  
**Product principle:** reproduce useful workflow patterns, not competitor copy,
brand assets, or distinctive visual expression.

## 1. Outcome and positioning

Pumasi Sign should become a trustworthy, straightforward e-signature product for
teams that need to prepare, route, sign, prove, and retrieve agreements. The first
release should be judged on whether a real agreement can complete safely and
without assistance—not on how many enterprise settings pages it contains.

The product promise by phase is:

| Phase | Promise | Exit outcome |
| --- | --- | --- |
| **1 — Trustworthy signing core** | Send and complete a legally reviewable agreement with a low-friction experience | A sender and accountless recipient can finish the full lifecycle reliably |
| **2 — Repeatable team workflows** | Make frequent team sending faster, controllable, and visible | Teams can reuse, organize, administer, and monitor agreements at moderate scale |
| **3 — Platform and advanced workflows** | Integrate signing into other systems and support complex/high-assurance use cases | Pumasi Sign operates as an extensible agreement platform |

## 2. What the screenshot review shows

The strongest incumbent pattern is a lifecycle-oriented product, not a generic
document editor:

```text
Home / Agreements / Templates
              |
              v
Upload -> recipients -> fields -> preview -> send
                                            |
                                            v
email -> verify -> consent -> guided signing -> finish
                                            |
                                            v
status -> history -> signed PDF + certificate -> archive
```

### UI patterns worth adopting

- A small global navigation with Home, Agreements, Templates, and role-gated Admin.
- Focus-mode shells for preparation and signing, without distracting global chrome.
- A one-page setup screen grouped into Documents, Recipients, and Message.
- A three-pane field editor: recipient-aware field palette, document canvas, and
  page/document thumbnails.
- Recipient colors used consistently on cards, fields, and ownership controls.
- A status-oriented agreements manager with saved mental models: action required,
  in progress, completed, drafts, and archived/deleted.
- Contextual primary actions: Sign, Continue, Remind/Correct, or Download according
  to state, with secondary actions in an overflow menu.
- Guided signing that advances through required fields and makes the completion
  condition visible.
- Completion treated as an evidence package: document, certificate, and history.
- Separate personal settings and organization administration; ordinary users do
  not need to navigate enterprise controls.

### UX lessons to keep, improve, or omit

| Keep | Improve for Pumasi | Omit initially |
| --- | --- | --- |
| Clear lifecycle and status language | Fewer nested menus and fewer competing product shells | Upsell interruptions and locked-field clutter |
| Full-screen preparation/signing | Mobile-first signer experience and stronger accessibility | AI decoration without a validated user job |
| Inline validation before moving forward | Explicit autosave state and safe resume | Large admin surface before team demand exists |
| Reusable templates and role binding | Plain-language recipient routing visualization | Payments, offline signing, and niche custody flows |
| Guided required-field completion | Evidence and authentication details exposed clearly | Copying competitor colors, wording, or iconography |

## 3. Current Pumasi baseline

The repository already contains much of the core concept: drafts and lifecycle
statuses, upload/conversion, role-based templates, serial and parallel routing,
CC recipients, accountless email-code signing, signature adoption, guided fields,
reminders and expiration, correction/void/decline behavior, branding, audit events,
signed PDFs, completion certificates, signer attachments, and SharePoint archiving.

There is one release-critical architecture constraint: the repository has two
independent backends. Production uses `service/` (Cloudflare Worker), while many
deeper capabilities and tests exist in `backend/` (FastAPI). A roadmap item is not
"available" until it is implemented and verified in the production backend.

## 4. Phase 1 — trustworthy signing core

**Goal:** deliver the smallest complete, defensible, production-quality agreement
lifecycle. Phase 1 is the MVP and should receive usability testing before Phase 2.

### Product features

1. **Architecture and evidence foundation**
   - Decide and document the canonical backend; create one production capability
     matrix and close parity gaps for every Phase 1 feature.
   - Immutable original file, normalized signing PDF, completed file, SHA-256
     hashes, append-only audit events, and downloadable completion certificate.
   - Explicit consent/electronic-record disclosure with accepted version and time.
   - Secure, expiring, non-enumerable recipient links plus email verification code.
   - Challenge-scoped, one-time verification codes stored as hashes, with expiry,
     resend delay, persistent attempt limits, and generic failure responses.

2. **Prepare and send**
   - PDF and common Office/image upload with conversion progress and actionable
     failure messages.
   - Ordered multi-document envelopes: upload together or separately, reorder,
     replace safely before signing, navigate by document, and preserve a
     per-document evidence manifest.
   - Recipients who need to sign plus CC recipients; serial and parallel order.
   - Subject/message, expiration, reminders, and send preview.
   - Fields: signature, initials, name, email, company, title, date, text,
     checkbox, radio, dropdown, label/note, and attachment.
   - Required/optional, recipient ownership, validation, resize, move, duplicate,
     and delete.
   - Autosaved drafts, resume, duplicate, correct recipient/details, resend,
     remind, void, and decline with reason.

3. **Signing and completion**
   - Accountless responsive signing on desktop and mobile.
   - Review/consent gate, clear signer identity, and document download before or
     after signing according to sender policy.
   - Start/Next guided navigation, required-field progress, validation summary,
     finish confirmation, and safe finish-later behavior.
   - Draw, type, upload, and reuse signature/initials; accessible keyboard path.
   - Completion emails to participants and access to signed PDF, certificate, and
     human-readable history.
   - Durable notification outbox with idempotency, retries, delivery state, and
     sender-visible terminal failures; email acceptance is not audit evidence.

4. **Agreement management**
   - Home quick actions: Send for signature, Sign yourself, Create template.
   - Dashboard counts for Action required, Waiting, Drafts, and Completed.
   - Agreement views for All, Action required, In progress, Completed, Drafts,
     Declined/Voided/Expired, and Archived.
   - Search and filters for name/recipient, status, sender, and date.
   - Envelope detail with recipient progress, timeline, documents, and contextual
     actions.

### UI/UX deliverables

- Original Pumasi design tokens and component library: typography, spacing,
  colors, focus states, status badges, buttons, form controls, dialogs, toasts,
  skeletons, and empty/error states.
- Desktop sender shell and responsive signer shell meeting WCAG 2.2 AA targets.
- One-page setup accordion and focus-mode field editor.
- Three-pane field placement with page rail, zoom, recipient selector, drag/drop,
  keyboard placement, floating field toolbar, undo/redo, and visible autosave state.
- First-use help limited to short, dismissible contextual hints.

### Phase 1 exit criteria

- A new sender can send a one-document, two-signer ordered agreement without help.
- An accountless signer can verify, consent, complete, and download on a phone.
- Correct, remind, decline, void, expiration, and conversion-error paths are tested.
- Completed bytes and certificate hashes verify; audit events cannot be edited via
  an application route.
- No critical or high accessibility failures in the sender and signer journeys.
- Production-backend integration tests and browser tests cover the lifecycle;
  monitoring, backup/recovery, rate limiting, and security review are complete.

## 5. Phase 2 — repeatable team workflows

**Goal:** turn the reliable core into a daily team product.

### Product features

- Multi-document enhancements: combined/ZIP download, per-document visibility
  rules, and bulk document actions (the ordered envelope core ships in Phase 1).
- Templates with placeholder roles, versions, ownership, shared/team libraries,
  folders, duplicate, archive, and safe publishing.
- Contacts/address book and recent recipient suggestions.
- Bulk send from CSV with validation, preview, per-row isolation, batch results,
  retry, and cancellation.
- Public template links/self-service forms for known templates, protected with
  rate limits, expiration, and optional access controls.
- Conditional fields, calculated fields, reusable custom fields, regex/type
  validation, and prefilled/locked values.
- Delegation/reassignment, signer replacement, approver role, and conditional
  routing for a deliberately small rule set.
- Organization users, groups, sender permission, template permission, basic roles
  (owner/admin/sender/viewer), and custody transfer when a user leaves.
- Account defaults for reminders, expiration, date/locale, signer navigation,
  branding, email content, download-filename format, sender identity, signature
  preferences, timezone, and retention.
- Operational reporting: volume, completion rate/time, outstanding recipients,
  failed delivery, expiration, and CSV export.
- Folders, soft delete/restore, bulk move/download/archive, and configurable
  retention with legal-hold-safe behavior.
- A document vault implemented as organized views over the artifact inventory,
  avoiding duplicate or independently mutable copies of executed evidence.

### UI/UX deliverables

- Template library with ownership/status filters, card/table view, and clear role
  binding when a template is used.
- Visual routing editor for serial, parallel, approval, and conditional steps.
- Bulk-send validation workspace that exposes row-level errors before creation.
- Admin shell that progressively discloses settings by role and includes global
  search; do not reproduce a dense enterprise menu wholesale.
- Saved views and table density preferences for high-volume users.
- Onboarding checklist, sample template, and contextual education driven by actual
  incomplete tasks rather than a generic product tour.

### Phase 2 exit criteria

- A team can publish a shared template and send 100 isolated agreements from CSV.
- Permission tests prove users cannot read or mutate another team's private data.
- Multi-document output, field coordinates, audit history, and download packages
  remain correct through conversion and completion.
- Admin changes and workflow-rule evaluations are auditable.
- Reporting totals reconcile with lifecycle data and can be exported accessibly.

## 6. Phase 3 — platform and advanced workflows

**Goal:** support embedded, integrated, international, and higher-assurance signing.

### Product features

- Versioned public API, scoped OAuth/service accounts, idempotency, sandbox,
  usage logs, SDK examples, and developer documentation.
- Signed webhooks with retry, replay protection, delivery logs, test events, and
  event versioning.
- Embedded sending and signing; embeddable self-service forms with redirect and
  callback controls.
- Integrations starting from measured demand: SharePoint/OneDrive maturity,
  Google Drive, Dropbox, CRM, and workflow automation connectors.
- Advanced routing: external workflow pause/resume, dynamic recipients, scheduled
  delays, and richer conditional branches.
- Higher-assurance authentication options such as SMS/voice OTP, knowledge or ID
  verification through vetted providers, and configurable assurance policies.
- Digital-signature/certificate-provider support where customer/legal requirements
  justify it; region-specific evidence and data-residency options.
- SSO (SAML/OIDC), SCIM, domain claiming, MFA policy, granular permission profiles,
  admin audit export, IP/session controls, and enterprise retention/legal hold.
- Advanced analytics and reliability controls: webhook/API dashboards, audit
  export, regional status, incident communication, and SLA instrumentation.
- Assisted preparation only after the core is measured: PDF-form conversion,
  anchor-text placement, suggested fields, agreement summary, and risk extraction,
  always reviewable and never silently authoritative.

### UI/UX deliverables

- Developer center with quickstart, API explorer, webhook debugger, keys/scopes,
  sandbox switcher, logs, and production-readiness checklist.
- Integration catalog organized by user job, with permission and data-flow details.
- Policy builder that explains authentication and retention impact in plain language.
- Accessible responsive administration for large organizations, including search,
  change review, and confirmation for high-impact settings.

### Phase 3 exit criteria

- A third-party app can create, embed, observe, and retrieve an agreement without
  manual intervention, using documented and versioned contracts.
- Webhooks tolerate duplicate/out-of-order delivery and expose diagnosable logs.
- Enterprise identity lifecycle and permission controls pass independent security
  assessment.
- Every advanced authentication method records provider result and assurance level
  in the evidence package without exposing unnecessary personal data.

## 7. Cross-phase requirements

These are not backlog features; they are release conditions in every phase:

- **Security and privacy:** least privilege, encrypted transport/storage, secret
  rotation, malware/file validation, abuse protection, data minimization, and
  tenant isolation.
- **Evidence:** immutable artifacts, explicit versioning, trusted timestamps,
  participant/action attribution, and reproducible certificate verification.
- **Reliability:** idempotent transitions, retry-safe mail/jobs, conversion and
  stamping observability, backups, restore drills, and documented incident handling.
- **Accessibility:** keyboard-only operation, screen-reader names/order, focus
  management, reduced motion, sufficient contrast, and mobile reflow.
- **Internationalization:** timezone-aware event display, locale/date format,
  Unicode names/content, and translatable sender/signer email and UI copy.
- **Product analytics:** funnel events for upload, setup validation, field placement,
  send, verify, consent, required-field completion, finish, and failure—without
  collecting document contents or signature images.
- **Legal review:** obtain jurisdiction-specific counsel before marketing legal,
  regulatory, identity, or compliance claims.

## 8. Recommended development order inside Phase 1

1. Execute the accepted Cloudflare architecture decision and capability/test matrix.
2. Evidence chain, immutable envelope/recipient snapshots, artifact inventory,
   completion-generation state, and security threat model.
3. Recipient verification and mobile signing ceremony.
4. Prepare/send focus flow and field editor usability.
5. Agreements manager, detail/history, and exception actions.
6. Durable email delivery/outbox, accessibility, lifecycle browser tests,
   observability, and recovery validation.
7. Private pilot, measured usability fixes, then broader release.

## 9. Product metrics

Use a small set that measures task success rather than screen activity:

- Median time from upload to send.
- Setup validation failure rate and field-placement undo/error rate.
- Recipient email delivery, verification, and completion rates.
- Median time from first open to completion, segmented by mobile/desktop.
- Agreements requiring correction, reminder, decline, or support.
- Certificate/download success and artifact verification failures.
- Template reuse and bulk-send error rate in Phase 2.
- API/webhook success, retry, and support rate in Phase 3.

## 10. Explicit non-goals for the first release

- Cloning DocuSign, Adobe Acrobat Sign, or SignWell visual identity or wording.
- Payments, AI summarization, offline/mobile native apps, notarization, qualified
  digital signatures, marketplace breadth, or complex industry compliance claims.
- Building every admin setting visible in enterprise competitor screenshots.
- Calling the product legally compliant solely because it has signatures and an
  audit log.
