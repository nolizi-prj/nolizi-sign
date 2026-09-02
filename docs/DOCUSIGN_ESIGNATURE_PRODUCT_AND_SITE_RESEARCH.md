# DocuSign eSignature: product and public-site research

**Research date:** 2026-09-01  
**Purpose:** A product, UX, content, and information-architecture reference for
building Pumasi Sign. This is not a request to clone DocuSign's code, copy, or
visual identity. It records publicly described capabilities, identifies the
job each capability performs, and translates the findings into an original
product direction.

## 1. Executive summary

DocuSign presents eSignature as one part of a larger agreement-management
platform. The eSignature feature page is organized into two layers:

1. **Product capabilities:** document creation, sending, signing, identity,
   reporting, compliance, and retention.
2. **Platform capabilities:** reliability, security, international operation,
   administration, and extensibility.

That split is important. A credible e-signature product is not only a PDF
editor with a signature field. It is a stateful evidence system: it prepares a
document, defines participants and permissions, authenticates them, records
their actions, seals the result, and retains enough evidence to defend the
transaction later.

The public website supports that story through several connected content
systems:

- product pages explain what the software does;
- solution pages translate features into department and industry outcomes;
- pricing and trial paths convert self-service buyers;
- enterprise contact paths serve complex buyers;
- customer stories and research provide social proof;
- Trust Center, legality, status, and safety content reduce risk;
- integrations and developer content make the product feel extensible;
- templates, education, support, community, and releases support adoption.

For Pumasi Sign, the right lesson is not to reproduce the entire surface at
once. The strongest path is to perfect the core evidence chain—prepare, route,
authenticate, sign, seal, audit, and retrieve—then add reusable workflows,
team controls, integrations, and advanced compliance in explicit stages.

## 2. Sources and research boundaries

Primary pages reviewed:

- [eSignature detailed features](https://www.docusign.com/products/electronic-signature/features)
- [DocuSign home page](https://www.docusign.com/)
- [Products catalog](https://www.docusign.com/products)
- [Solutions](https://www.docusign.com/solutions)
- [Resource Center](https://www.docusign.com/resources)
- [Integrations catalog](https://www.docusign.com/integrations)
- [Developer Center](https://developers.docusign.com/)
- [Trust Center](https://www.docusign.com/trust)
- [eSignature plans](https://ecom.docusign.com/en-US/plans-and-pricing/esignature)
- [Advanced recipient routing](https://www.docusign.com/blog/developers/advanced-recipient-routing-your-esignature-integrations)
- [Bulk sending at scale](https://www.docusign.com/blog/developers/bulk-sending-scale)

The feature names below are summarized from public DocuSign descriptions.
Availability can vary by plan, account configuration, geography, or release
state. A feature appearing on a marketing page does not establish its legal or
technical suitability for Pumasi Sign. Compliance claims need independent
legal and security review before Pumasi makes similar claims.

Pricing figures and quantitative competitor comparisons are intentionally not
duplicated here. The dated competitor-pricing register remains
[`roadmap/MARKET.md`](../roadmap/MARKET.md).

## 3. Product model and core concepts

### 3.1 Agreement lifecycle

A complete e-signature workflow can be modeled as:

```text
Create/import -> prepare -> add recipients -> assign roles and fields
-> configure routing/authentication -> send -> view/authenticate/sign
-> complete or decline -> seal/certify -> distribute/store/report
```

Exceptions are first-class states, not edge cases:

- correct a sent but incomplete transaction;
- resend a notification;
- pause or delay routing;
- reassign or delegate responsibility;
- void or expire a transaction;
- let a recipient decline;
- recover from failed delivery;
- retain a full history of the exception and its resolution.

### 3.2 Principal objects

DocuSign commonly calls a transaction container an **envelope**. An
implementation inspired by this category needs at least these domain objects:

| Object | Responsibility |
| --- | --- |
| Agreement/envelope | Transaction boundary, status, sender, documents, recipients, and evidence |
| Document | Original bytes, normalized rendering, order, visibility, and completed artifact |
| Recipient | Person or role, routing position, delivery channel, permissions, and status |
| Field/tab | Type, coordinates or anchor, recipient ownership, validation, and value |
| Workflow | Serial/parallel rules, conditions, pauses, deadlines, and post-completion actions |
| Authentication challenge | Method, attempts, result, timestamp, and provider evidence |
| Event | Append-only record of material actions and system transitions |
| Template | Reusable documents, fields, roles, routing, messages, and defaults |
| Brand | Sender-facing and recipient-facing visual/message configuration |
| Organization/account | Users, groups, policy, security, domains, and retention settings |
| Completion package | Signed documents, certificate, audit trail, hashes, and related attachments |

## 4. Detailed eSignature feature inventory

### 4.1 Document creation and preparation

#### Document generation

Generate personalized agreements from structured data rather than manually
editing a file for every recipient. Useful behaviors include conditional
clauses, repeating table rows, formatted values, and data pulled from systems
of record.

**Product implication:** keep source data and generated document versions
traceable. The system should be able to explain which template and input data
produced the artifact that was sent.

#### File ingestion and normalization

The public feature page describes support for common office documents, PDFs,
spreadsheets, text, and other formats. Documents are normalized into a stable
signing representation.

**Required behaviors:**

- detect file type and reject dangerous or unsupported content safely;
- preserve page geometry and font rendering as reliably as possible;
- store the immutable original separately from the normalized version;
- show conversion failures before the user prepares fields;
- hash and version every material artifact.

#### PDF form conversion

Recognize existing PDF form controls and convert them into signer fields. This
reduces preparation work but needs a review step because field ownership,
required status, and semantics may not be inferable.

#### Fields and reusable custom fields

The category includes signature, initials, full name, title, company, date,
text, numeric and currency inputs, checkbox, radio, dropdown, note, attachment,
and drawing/markup concepts.

Each field needs:

- recipient/role ownership;
- required, optional, or read-only state;
- stable page coordinates and responsive representation;
- validation and formatting rules;
- visibility rules;
- recorded value and completion event;
- accessibility name, instructions, and keyboard order.

Reusable custom fields allow organizations to save frequently used labels,
validation, and styling.

#### Automatic field placement

Anchor fields to nearby text so they move when the document changes. Modern
versions can also detect likely agreement type and suggest appropriate fields.

**Risk:** automatic placement should remain a suggestion until the sender
confirms it. A misplaced signature field can invalidate the workflow's intent.

#### Cloud document import

Import from common cloud-storage and productivity providers. The deeper design
problem is permission-safe OAuth, revocation, file-version selection, and
clear handling of links versus copied bytes.

#### Self-service forms

DocuSign describes two related patterns:

- **PowerForms:** public or shareable, template-driven signing flows where the
  signer may not be known in advance;
- **Web Forms:** interactive data collection that can dynamically populate an
  agreement, be prefilled through APIs, and be embedded in another product.

For Pumasi, this means treating "collect data, then generate and sign" as a
distinct experience from "upload a finished PDF and add fields."

#### Supplemental documents and acknowledgments

Attach disclosures, terms, or supporting material separately from the main
agreement, require viewing or acknowledgment, and preserve that event in the
evidence record.

#### Data integration, validation, and field logic

Advanced preparation includes:

- prefill from external systems;
- write completed data back to external systems;
- typed validation for email, phone, date, postal code, identifiers, or custom
  regular expressions;
- conditional fields that appear based on earlier answers;
- calculated fields;
- locked fields;
- linked fields whose values stay synchronized;
- downstream editing with explicit acceptance or initials from affected
  parties.

This turns a PDF overlay into a small rules engine. The rules and their
evaluations belong in the audit history.

### 4.2 Sending, routing, and workflow

#### Recipient roles

Participants may sign, approve, receive a copy, edit, witness, supply an
attachment, or manage on someone else's behalf. Permissions must be explicit
and narrower than account-level access.

#### Serial, parallel, and mixed routing

- **Serial:** each participant acts after the previous participant.
- **Parallel:** several participants can act at the same routing step.
- **Mixed:** combines both models.

The workflow engine should compute who is currently actionable and never
notify or expose documents to a later recipient prematurely.

#### Conditional and advanced routing

Select recipients or approval paths based on agreement data. Public developer
material also describes pausing a workflow so an external process can run or a
scheduled condition can be met before routing continues.

Examples include amount-based approval, department-based assignment, and
additional review for exceptional terms.

**Evidence requirement:** record the rule version, evaluated inputs, result,
and resulting route. Otherwise the system cannot explain why a person did or
did not receive the agreement.

#### Templates

Reusable templates can preserve documents, fields, recipient roles, routing,
messages, authentication requirements, and other settings. Team-shared
templates require ownership, permissions, versioning, publishing, and safe
updates that do not mutate transactions already sent.

#### Bulk send

Merge a recipient/data list into a template and create an independent
transaction for each row. Operational capabilities include validation,
preview, failure reporting, retry, and batch-level actions while keeping each
recipient's agreement isolated.

#### Delays, reminders, deadlines, and expiration

Configure delays between steps, recurring reminders, final warnings, and
automatic expiration. Store schedules in a timezone-safe form and audit every
notification attempt.

#### Shared access and delegation

Allow authorized people to draft, send, correct, void, or organize another
user's transactions. Delegation must identify both the actor and the person or
organization on whose behalf the actor operated.

#### Per-document visibility

In a multi-document transaction, recipients may see different subsets. The
authorization check must occur on every document fetch, preview, and download,
not only in the UI.

#### Correction after sending

Before completion, authorized senders may need to fix recipient details,
fields, or documents. The system should preserve before/after state, determine
whether prior actions must be repeated, and notify affected recipients.

#### Delivery and status events

Delivery can use email and, on supported products, mobile messaging channels.
Status is exposed in the web application and through webhook-style event
delivery. A robust event system needs signed callbacks, idempotency keys,
retry policy, ordering guidance, and a replay/reconciliation mechanism.

#### Payments

Some workflows combine signing and payment. This introduces a separate
payment-provider state machine: authorization, success, failure, refund,
dispute, and reconciliation. Payment data should remain with a compliant
provider; the agreement platform stores references and business outcomes.

#### Offline and legacy return paths

Mobile clients may queue sending or signing while offline and synchronize
later. Public materials also mention legacy return methods for specialized
workflows. Both require conflict handling and a clear evidence model.

### 4.3 Signing experience

#### Accountless signing

The recipient should generally be able to review and sign through a secure
link without creating a product account. The experience should explain the
sender, document purpose, authentication step, electronic-record consent, and
how to obtain the completed copy.

#### Guided completion

The signing UI should:

- start with a concise disclosure and consent step where required;
- show document progress and required-field count;
- guide the signer to the next required field;
- distinguish read-only, optional, and required inputs;
- offer clear finish/submit semantics;
- prevent submission until requirements are satisfied;
- present a completion receipt and download path.

#### Signature adoption

Typical methods include typed style, drawn mark, uploaded image, or managed
digital-signature credential. The UI must distinguish the visual mark from the
underlying evidence that associates a person with the transaction.

#### Responsive and mobile signing

A responsive signing view may provide a mobile-optimized interpretation of
the document while preserving access to the authoritative page rendering.
Collapsible sections, logical page breaks, and readable field layouts improve
completion on small screens.

#### Mobile applications and offline signing

Native apps can prepare, send, sign, and sync transactions. Offline signing is
high risk: the client must protect cached documents, establish trustworthy
time and identity evidence, handle revocation, and reject stale workflows.

#### In-person signing

Support a device handoff or hosted session in which several people sign in the
same physical location. The UI must clearly switch identity and prevent one
person's adopted signature from carrying into the next person's session.

#### Collaboration

Transaction-bound comments reduce email back-and-forth and retain conversation
history with the agreement. Notifications, visibility, mentions, resolution,
and export/retention policy are part of the feature—not just the comment box.

#### Branding

Organizations can customize recipient emails and signing pages with logos,
colors, links, and message content. Safety constraints should retain a stable
platform identity, verified sender details, and anti-phishing cues.

#### Accessibility

Accessibility must cover the full journey: email, authentication, disclosure,
document navigation, fields, signature adoption, error handling, submission,
and completed-document access. The normalized page image alone is not an
accessible document model.

#### AI-assisted reading

The public page describes summaries and agreement-specific questions. If
Pumasi adds similar tools, answers should be clearly non-authoritative,
grounded in the exact document version, permission-filtered, and excluded from
the signed terms unless deliberately incorporated.

### 4.4 Signer identity and authentication

DocuSign's public feature inventory describes a ladder of assurance methods:

| Method | What it demonstrates | Main limitation |
| --- | --- | --- |
| Email-link access | Control of the invited mailbox/link | Forwarding and mailbox compromise |
| Sender-provided access code | Knowledge of a separately shared secret | Sender distribution practices |
| SMS one-time code | Access to a phone number | SIM swap, forwarding, and recycled numbers |
| Phone challenge | Ability to complete a voice/phone flow | Similar telecom risks and accessibility |
| Federated identity/SSO | Authentication by a trusted identity provider | Depends on federation policy and account lifecycle |
| Knowledge-based questions | Match to data held by a provider | Geography, privacy, data quality, and accessibility |
| Government ID/eID verification | Document/eID checks and identity matching | Cost, false results, jurisdiction, and biometric/privacy obligations |
| Digital certificate | Control of a signing credential | Credential issuance and custody determine assurance |

Authentication should be configurable per recipient or workflow risk. The
audit record needs method, provider, result, time, attempt history, and policy
version without storing unnecessary sensitive data.

Identity verification is not the same as legal authority. A product may know
who a person is and still not know whether they can bind a company. Authority,
capacity, consent, and document intent need separate treatment.

### 4.5 Reporting and operational visibility

The public feature page groups reporting into real-time status, transaction and
recipient reports, account-level activity, and export.

An operational dashboard should answer:

- Which transactions need my action?
- Which are waiting on someone else?
- Which notifications failed?
- Which are nearing expiration?
- Where do completion rates or cycle times fall?
- Which templates or teams create errors?
- What happened to a specific transaction?

Exports require authorization, redaction, audit logging, asynchronous job
handling, and safe expiry of generated files. Analytics should not become a
backdoor around document visibility rules.

### 4.6 Compliance and evidentiary features

#### Consent and disclosure

Present the applicable electronic-record and signature disclosure and capture
consent or withdrawal. Preserve the exact disclosure version shown.

#### Immutable audit trail

Record material events such as creation, upload, field assignment, send,
delivery attempt, view, authentication, consent, signature, decline,
correction, completion, download, and administrative action.

Each event should include:

- transaction and document version;
- actor and acting authority;
- event type and outcome;
- trustworthy server timestamp;
- relevant client/network metadata under a documented privacy policy;
- previous/next status where applicable;
- an integrity mechanism that makes silent alteration detectable.

#### Tamper evidence and completion certificate

Seal completed artifacts and provide a certificate summarizing participants,
events, timestamps, authentication, and document digests. The certificate is a
human-readable evidence index; cryptographic verification must not depend on
trusting the printed page alone.

#### Digital signatures

Certificate-backed signatures may be needed for regional or industry rules.
This requires standards expertise, credential providers, long-term validation,
revocation evidence, trusted timestamps, and careful PDF signature handling.

#### Draft watermarking

Visually distinguish drafts or incomplete copies from completed artifacts.
Watermarking supplements—rather than replaces—cryptographic version control.

#### Regulation-specific configuration

DocuSign markets configurations for regulated contexts. Pumasi should never
reduce this to a checkbox labeled "compliant." Each target regime needs scoped
requirements, contracts, operational controls, validation evidence, incident
processes, and legal review.

### 4.7 Archiving, retention, and post-signature actions

#### Secure storage and retrieval

Retain completed documents and evidence with tenant isolation, encryption,
version integrity, access logging, backup/restore, and tested retrieval.

#### Retention and purge policy

Allow organizations to define retention periods, legal holds, advance notices,
and defensible deletion. Separate database deletion from object-storage purge,
derived previews, search indexes, analytics, backups, and provider copies.

#### Email archiving

Regulated customers may need copies of transaction email routed to an archive.
Preserve message identifiers, delivery result, recipients, and relation to the
transaction.

#### Authoritative copy and custody

Certain negotiable instruments require a controlled authoritative copy and
documented custody transfers. This is a specialized product domain and should
not be inferred merely from ordinary immutable storage.

#### Download/retrieve and external archive

Support one-time and recurring exports to approved storage. Jobs should be
restartable, idempotent, observable, and verifiable by hash.

#### Post-completion automation

Rules can archive the completion package, export field data, begin another
workflow, or trigger a subsequent agreement. Store execution history and
provide retry and dead-letter handling.

### 4.8 Platform capabilities

#### Availability and status transparency

An agreement service needs public status, incident communication, service
health history, graceful degradation, recovery objectives, and operational
ownership. Marketing an uptime target is not a substitute for measured SLOs
and tested recovery.

#### Security

The baseline includes encryption in transit and at rest, tenant isolation,
least privilege, secret management, malware scanning, secure previews,
tamper-evident artifacts, abuse controls, threat monitoring, dependency
management, incident response, and independent assurance.

Recipient-facing anti-phishing design is especially important because signing
links arrive unsolicited and can be imitated.

#### International use

International operation involves interface and email localization, locale-safe
names and addresses, time zones, data residency, regional identity methods,
signature standards, accessibility, privacy, and jurisdiction-specific legal
analysis.

#### Administration and controls

Enterprise administration includes:

- users, groups, roles, and granular privileges;
- delegated administrators;
- feature and policy controls;
- authentication and password policy;
- SSO and automated user provisioning;
- verified domains;
- centralized management across accounts or regions;
- bulk user and setting operations;
- complete administrator audit logs.

#### APIs, webhooks, embedded flows, and sandbox

The platform surface includes programmatic envelope creation, recipient and
field configuration, embedded signing/sending, status callbacks, OAuth-based
authorization, SDKs/examples, and an isolated developer environment.

A Pumasi API should be versioned, idempotent, rate-limited, tenant-safe, and
observable. The developer experience also needs test identities, sample
documents, webhook replay, request logs, clear error codes, and a migration
policy.

#### Prebuilt integrations

The public site uses a searchable integration catalog spanning CRM, HR,
productivity, identity, storage, and industry tools. The strategic value is
distribution: users complete an agreement without leaving their system of
record.

## 5. Public website architecture

### 5.1 Global navigation

The public navigation separates four buyer questions:

- **Products:** What can the platform do?
- **Solutions:** Does it fit my department, industry, or company size?
- **Resources:** Can I learn, validate, and get help?
- **Enterprise / pricing:** How do I buy?

Utility links provide search, support, document access/login, and sales
contact. Mega menus expose a wide catalog while grouping links by buyer intent.

### 5.2 Product content system

The site has a platform overview, individual product pages, detailed feature
pages, use cases, guided tours/demos, integrations, APIs, mobile app content,
and a filterable product catalog. The catalog describes products as either
preconfigured applications for a business need or reusable platform
capabilities.

This lets one capability appear in several narratives without forcing every
visitor through the technical feature inventory.

### 5.3 Solution content system

Solutions are segmented by:

- department, such as sales, HR, legal, procurement, and customer experience;
- industry, such as financial services, insurance, real estate, government,
  healthcare, and life sciences;
- company size, notably enterprise and small-to-medium organizations;
- use case and workflow outcome.

The page pattern is outcome first, relevant capability second, proof and CTA
third. Product pages say "what"; solution pages say "why for me."

### 5.4 Education and trust content

The resource ecosystem includes blog posts, guides, research, webinars, demos,
solution briefs, customer stories, legality guidance, releases, roadmap,
templates, training, support, community, events, and partner material.

The Trust Center is a distinct risk-reduction destination with security,
compliance, legal, privacy, alerts, status, and a controlled trust portal. This
separation makes trust material discoverable to security and procurement
reviewers without overloading the main product pitch.

### 5.5 Developer and ecosystem content

Developer content and integrations are first-class acquisition surfaces, not
footer afterthoughts. The public architecture supports:

- API discovery and documentation;
- sample applications and SDK guidance;
- developer account/sandbox onboarding;
- partner and extension-app programs;
- an integration catalog with search and filters;
- install and learn-more paths for individual integrations.

### 5.6 Conversion paths

Several calls to action serve different readiness levels:

- start a trial;
- send a sample or try a lightweight experience;
- view plans or buy a self-service plan;
- contact sales for enterprise needs;
- take a guided tour or view a demo;
- access existing documents or sign in;
- explore a specific product, solution, or resource.

The important design principle is continuity: each page has a primary next
step aligned with its visitor's likely intent, plus a lower-commitment path.

## 6. Visual and interaction design analysis

This section is an observation and inference from the public page structure,
content ordering, and image treatment—not a claim about DocuSign's internal
design system.

### 6.1 Hierarchy

Pages generally use:

1. a compact global announcement and utility layer;
2. a large global header/mega navigation;
3. optional product-local navigation;
4. a clear hero with one dominant promise and CTA;
5. social proof or selected feature highlights;
6. modular sections with product UI, photography, or cards;
7. deeper proof, resources, and conversion CTA;
8. a large multi-column footer.

The eSignature feature page adds a local tab row and a linked table of contents
before a long, categorized feature inventory. This is appropriate for a
high-intent evaluator who wants completeness more than a short sales pitch.

### 6.2 Content rhythm

The site alternates short outcome-oriented headlines with supporting copy,
product screenshots, customer logos, measured customer outcomes, and CTAs.
Long inventories are broken into semantic groups rather than presented as one
undifferentiated grid.

### 6.3 Reusable page modules

Likely reusable modules include:

- announcement bar;
- utility navigation and mega menu;
- product sub-navigation;
- hero with image or product UI;
- logo strip;
- feature cards;
- alternating text/media rows;
- filterable catalog;
- customer proof/stat panel;
- testimonial carousel;
- resource cards;
- trust/compliance callout;
- primary/secondary CTA band;
- structured footer.

### 6.4 Copy system

Headlines focus on business movement, simplicity, speed, control, and trust.
Technical language appears deeper in the page, after the business promise is
established. Feature descriptions usually combine the capability with its
benefit in a small amount of copy.

For Pumasi, copy should be original and evidence-based. Avoid unsupported
superlatives, vague compliance promises, and competitor price statements
outside the dated market register.

### 6.5 Trust through interface design

Trust is reinforced through repetition across the site:

- recognizable customer evidence;
- explicit access to security and system status;
- legality and compliance education;
- clear support/document-access links;
- product screenshots rather than only abstract illustrations;
- consistent CTAs and navigation;
- visible developer and integration ecosystems.

For an e-signature product, the signing page itself must be calmer than the
marketing site. It should minimize navigation, clearly identify the sender,
display security cues, and focus attention on document review and consent.

## 7. Recommended Pumasi public-site sitemap

```text
/
├── product/
│   ├── esignature/
│   ├── features/
│   ├── templates/
│   ├── security-and-evidence/
│   ├── integrations/
│   └── api/
├── solutions/
│   ├── hr/
│   ├── sales/
│   ├── legal/
│   └── small-teams/
├── templates/
│   ├── nda/
│   ├── offer-letter/
│   ├── contractor-agreement/
│   └── consent-form/
├── pricing/
├── trust/
│   ├── security/
│   ├── privacy/
│   ├── legal/
│   ├── accessibility/
│   └── status/
├── resources/
│   ├── guides/
│   ├── customer-stories/
│   ├── release-notes/
│   └── help/
├── developers/
│   ├── docs/
│   ├── api-reference/
│   ├── webhooks/
│   └── sandbox/
├── sign-in/
└── start/
```

Only publish destinations with truthful content. Empty enterprise-looking
pages weaken trust more than a smaller, complete site.

## 8. Recommended Pumasi product roadmap

### Phase A: trustworthy core

Goal: complete a simple agreement safely and retrieve defensible evidence.

- stable upload and PDF normalization;
- signer-assigned signature, initials, name, date, text, and checkbox fields;
- serial and parallel recipients;
- accountless recipient link plus verification challenge;
- explicit consent and clear finish action;
- immutable lifecycle with decline, void, expire, resend, and correction rules;
- server-side event history;
- original and completed document hashes;
- tamper-evident completion package and certificate;
- secure recipient download and sender dashboard;
- accessible desktop and mobile web signing;
- notification delivery logs and retry;
- baseline tenant isolation, rate limits, malware controls, backup, and recovery.

### Phase B: repeatable team workflows

- versioned templates and recipient roles;
- team-shared templates with permissions;
- reminders, deadlines, and expiration policy;
- organization branding with anti-phishing guardrails;
- additional validated field types;
- document visibility controls;
- delegated access and organization roles;
- transaction search, filters, and operational reports;
- retention settings and complete administrator audit history.

### Phase C: automation and ecosystem

- bulk send with row validation and batch operations;
- conditional routing and workflow pauses;
- self-service public forms;
- API-created and embedded signing flows;
- signed, retryable webhooks with replay tooling;
- cloud-storage and system-of-record integrations;
- post-completion actions;
- developer sandbox, examples, and request logs.

### Phase D: higher-assurance and regulated workflows

- multiple identity-verification providers;
- certificate-backed digital signatures and trusted timestamps;
- regional signature profiles and data-residency options;
- compliance-specific configurations validated with counsel and auditors;
- authoritative-copy/custody products only if a concrete market requires them;
- native/offline clients only after the web evidence model is mature.

### Phase E: assisted intelligence

- field suggestions with mandatory sender review;
- document classification;
- grounded signer summary and questions;
- agreement-data extraction and portfolio search;
- privacy, permission, provenance, evaluation, and human-review controls.

## 9. Feature priority framework

Use four gates before accepting a feature:

1. **Evidence:** Does it preserve or weaken the ability to prove what happened?
2. **Security:** What new data, identity, authorization, or abuse surface does
   it introduce?
3. **Workflow value:** Does it remove recurring work for the target small-team
   audience?
4. **Operational cost:** Can Pumasi support, observe, recover, and explain it?

Suggested priority:

| Priority | Capability group | Reason |
| --- | --- | --- |
| Must | lifecycle, fields, routing, recipient access, audit, seal, retrieval | Defines the product and its evidence chain |
| Should | templates, reminders, branding, team access, visibility, reports | Makes repeated organizational use practical |
| Next | bulk, conditional routing, forms, API, webhooks, integrations | Enables scale and distribution after the core is stable |
| Later | payments, advanced ID, digital-signature profiles, regulated custody | High value but materially increases legal and operational scope |
| Cautious | AI reading, automatic fields, offline signing | Useful only with strong provenance, review, and conflict controls |

## 10. Critical non-functional requirements

### Security and privacy

- authorization at every document and event boundary;
- encryption and managed key rotation;
- short-lived, revocable recipient sessions;
- secure email-link and OTP handling;
- safe file parsing and isolated preview generation;
- append-only or independently verifiable audit storage;
- minimal collection and bounded retention of identity/network metadata;
- secret scanning, dependency controls, incident response, and abuse reporting.

### Reliability

- idempotent send, sign, complete, and webhook operations;
- durable state transitions with concurrency control;
- retryable queues and dead-letter inspection;
- recovery testing for metadata and object storage;
- explicit SLOs for signing, completion, download, and notification paths;
- public, honest incident communication when serving external users.

### Accessibility

- keyboard-complete preparation and signing;
- semantic field descriptions and logical focus order;
- screen-reader-accessible document alternative;
- adequate contrast, zoom, and error identification;
- no authentication method as the sole path if it excludes a user;
- accessibility checks in component tests and end-to-end signing flows.

### Legal and evidence

- versioned consent and disclosure;
- clear attribution of actor, authority, intent, and document version;
- trustworthy timestamps and consistent time-zone display;
- defensible correction and void semantics;
- signed artifact verification independent of mutable application data;
- counsel-reviewed claims per jurisdiction and use case.

## 11. What not to copy

- DocuSign's name, marks, color system, icons, illustrations, screenshots, or
  wording;
- page layouts reproduced so closely that users could confuse the products;
- proprietary terminology where a clear generic term works better;
- enterprise breadth before Pumasi can operate the underlying services;
- compliance claims inferred from feature similarity;
- plan packaging or feature gates that conflict with Pumasi's evidence-based
  positioning.

The useful material to adopt is conceptual: a lifecycle-centered domain model,
layered identity assurance, explicit evidence, reusable workflow primitives,
trust content, and buyer-oriented information architecture.

## 12. Definition of a credible first release

A first release is credible when a skeptical reviewer can complete this test:

1. Upload a supported document and see an accurate rendering.
2. Assign required fields to two recipients with a defined routing order.
3. Send and verify that only the actionable recipient receives access.
4. Authenticate and sign from a mobile browser without creating an account.
5. Decline, resend, expire, and correct separate test transactions and observe
   valid, irreversible state transitions.
6. Complete a transaction and download the exact completed document plus a
   certificate and event history.
7. Independently verify the artifact hashes.
8. Confirm that another tenant and an unauthorized recipient cannot fetch any
   document, preview, event, or export.
9. Restore the transaction from backup and reproduce the same evidence.
10. Use the entire signer path with keyboard and screen reader.

Everything beyond that is valuable. These behaviors are foundational.
