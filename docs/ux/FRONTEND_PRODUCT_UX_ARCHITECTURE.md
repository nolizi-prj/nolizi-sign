# Pumasi Sign frontend and UX architecture

**Updated:** 2026-09-01

## Product direction

Use the familiar e-signature mental model established by DocuSign—agreements,
recipients, fields, routing, review, send, and guided signing—without copying its
visual identity, wording, or accumulated enterprise complexity. Adopt DocuSeal's
focused builder/signing surfaces and OpenSign's practical document, bulk-send,
contact, Drive, and preference ideas where they improve a measured user job.

The interface should optimize two very different users:

- the sender, who repeatedly prepares, monitors, corrects, and retrieves work;
- the recipient, who may visit once on a phone and must understand, trust, and
  complete the request without learning the product.

## Shell model

Three layouts prevent one navigation system from serving incompatible jobs:

1. **Public:** marketing, login, privacy, and terms own their page chrome.
2. **Workspace:** persistent desktop navigation and a mobile drawer for Home,
   Agreements, Templates, and progressively disclosed administration.
3. **Focus:** preparation, template editing, and signing remove workspace
   navigation and preserve only brand, task context, save/exit, and task actions.

Future Phase 2 modules fit the workspace shell in this order: Contacts, Reports,
Documents/Vault, then Admin. They should appear only when implemented and useful;
disabled navigation and upgrade clutter are not placeholders.

## Core journeys

### Prepare and send

```text
Choose/upload documents
  -> order and validate
  -> add recipients and routing
  -> place recipient-owned fields
  -> preview each recipient's view
  -> review message/settings
  -> send or save draft
```

- Accept multiple files in one picker and repeated additions.
- Keep document order visible through every later step.
- Autosave changes and expose `Saving`, `Saved`, and actionable failure state.
- Keep advanced settings collapsed until requested.
- Validate at the point of correction and provide a final problem summary.
- Never lose fields silently when a document is replaced or reordered.

### Sign

```text
Recognize request
  -> verify identity
  -> review disclosure and documents
  -> guided required fields
  -> review/finish confirmation
  -> retrieve completed evidence
```

- Mobile is a first-class layout, not a shrunken desktop canvas.
- The primary action communicates the next unfinished task.
- Field navigation announces progress and validation errors accessibly.
- Signature adoption explains reuse and distinguishes signature from initials.
- Decline, finish later, and download are visible but do not compete with Finish.

### Manage agreements

- Home shows a small action queue, clear quick starts, and operational summaries.
- Agreements provides stable saved views, search, filters, and one consistent
  table/card action model.
- Agreement detail is the source of truth for progress, documents, evidence,
  delivery state, corrections, reminders, and exception actions.
- Status text says what happens next: `Waiting for Alex`, `Needs your signature`,
  `Delivery failed`, rather than exposing only database status words.

## Component boundaries for future development

- `App.vue`: layouts and global navigation only.
- `AgreementBrowser`: saved views, filtering, responsive table/card behavior.
- `DocumentSet`: upload, conversion, ordering, replacement, page ranges.
- `RecipientRouting`: signer/CC/approver rows and serial/parallel visualization.
- `FieldEditor`: palette, canvas, ownership, properties, keyboard placement,
  undo/redo, and per-recipient preview.
- `SigningCeremony`: verification, consent, progress, field steps, finish.
- `EvidencePanel`: artifacts, hashes, certificate, audit and delivery timelines.

Network state belongs in feature stores/composables rather than visual components.
Domain terms and status mappings remain centralized so tables, email, detail, and
signing screens cannot describe the same state differently.

## Design-system principles

- Original Pumasi colors and typography; competitor screenshots guide hierarchy,
  density, and interaction conventions only.
- One primary action per region, descriptive verbs, and dangerous actions isolated
  in overflow menus with confirmation.
- 44px minimum mobile targets, visible focus, semantic landmarks, reduced-motion
  support, sufficient contrast, and meaningful empty/loading/error states.
- Use color as reinforcement, never as the only status signal.
- Prefer calm neutral work surfaces with branding concentrated in identity and
  primary actions so customer brand colors do not impair readability.

## Delivery sequence

1. Workspace/public/focus shells and responsive dashboard foundation.
2. Document-first setup with explicit ordered document cards and autosave state.
3. Recipient/routing editor and progressive settings.
4. Field editor hierarchy, keyboard support, undo/redo, and recipient preview.
5. Mobile signing ceremony and completion/retrieval experience.
6. Agreement detail and manager delivery/error states.
7. Phase 2 templates, contacts, bulk send, reports, vault, and admin modules.

Every slice requires unit tests for state rules, a Worker-backed happy and failure
path, and desktop/mobile browser screenshots before it is considered available.
