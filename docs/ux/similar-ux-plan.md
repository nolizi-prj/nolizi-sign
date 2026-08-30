# Similar-UX plan: closing the gap to the incumbent

Companion to [`incumbent-ux-spec.md`](incumbent-ux-spec.md) (the clean-room
behavior spec distilled from the 2026-08-30 signed-in tour). This maps that
spec against what Pumasi Sign already has and sequences the rest into phases.
Steward direction (2026-08-30): "introduce similar UI and UX; multi-phase."

Ground rule carried over from the spec: we copy **flows and behaviors**, never
expression — no incumbent copy, colors, icons, or distinctive visual identity.

## Already covered (no work needed)

| Spec item | Where it lives today |
|---|---|
| Envelope state machine (draft/pending/completed/voided/declined/expired) | backend `models.py`, statuses drive all lists |
| Status-rail manager with search + status/sender/date filters, contextual row actions + kebab | `EnvelopeBrowser.vue` (Inbox/Drafts/Sent/Completed/Action required/Expiring/Needs attention/Archived) |
| Guided signing: reading-order field tour, back/next dock, finish gated on completion, review-and-consent dialog | `SignView.vue` |
| Adopt-signature: draw / type / upload tabs + saved-signature reuse | `SignaturePad.vue` |
| Templates with placeholder roles, role→person binding at use time, no re-tagging | `SendView.vue` template mode, `TemplateBuilderView.vue` |
| Signing order (steppers, parallel groups) + CC recipients | `SendView.vue` |
| Per-envelope reminders (interval) + expiration with warning views | wizard options + daily job |
| Audit timeline + certificate artifact | `EnvelopeDetailView.vue`, `/api/files/certificate/{id}` |
| Branding (logo + accent color) | `BrandingView.vue` |
| Autosave + implicit-draft behavior in the builder | `TemplateBuilderView.vue` |

## Phase 1 — high-visibility alignment, frontend-only (this branch)

1. **Home hero + quick actions** (spec §2): hero band with greeting and three
   actions — get signatures, sign a document yourself, create a template.
   Self-sign is the "I'm the only signer" preset on the wizard (spec item 19).
2. **Download modal** (spec item 11): completed envelopes get a Download
   primary action offering Document and Certificate of completion — replaces
   the bare signed-PDF icon. (Combine-into-one-PDF: Phase 3, needs backend merge.)
3. **Thumbnail page rail in the wizard's place-fields step** (spec §4): parity
   with the template builder; kills blind chevron paging.
4. **Floating field mini-toolbar** (spec §4): selected field shows
   required-toggle / duplicate / delete right at the field, not only in the
   side panel.
5. **Empty states with CTAs** (spec item 22) on the envelope browser views.

## Phase 2 — focus mode and the setup page

- Full-screen wizard + signing shells (global chrome hidden, X-to-exit,
  primary actions in the wizard header) — spec §1 shell 2.
- Accordion one-page envelope setup (documents / recipients / message on one
  page with inline validation) replacing paged steps 1–2 — spec item 8.
- Drag-from-palette ghost placement + zoom toolbar on the tagging canvas.
- Routing-order visualization ("view" link on the signing-order toggle).
- Multi-document envelopes end-to-end (upload cards with page counts) —
  needs backend: envelope↔documents 1:N, stamping across files.

## Phase 3 — signature identity and records depth

- "Choose" tab in the adopt modal: generated signature styles from name +
  initials, live preview, persisted style (spec §5) — plus the signature
  frame ("signed by" + envelope/party ID) burned into the stamped PDF,
  behind an account setting (spec §8 signature framing). Backend: stamping.
- Certificate data-model completion against spec §6 (per-signer security
  level, adoption method, viewed timestamps, integrity notations).
- Download: combine-into-one-PDF + zip for multi-select.
- Post-sign share loop: share-by-email modal with tokenized download links
  (spec item 12) — the growth loop; needs a share endpoint.

## Phase 4 — onboarding, admin defaults, retention

- Onboarding checklist (n/5 progress, live updates) + first-run coach marks.
- Account-level defaults: reminders/expiration, auto-navigation mode,
  signing-permission toggles, date-format pickers (spec §8).
- Folders + soft-delete (Deleted view) if archive proves insufficient.
- Document retention purge policy (simplified).

## Explicitly not copied

Plan-gating/upsell surfaces (Pumasi Sign is unmetered — that's the point),
SMS delivery premium gating, payment fields, enterprise admin noise
(permission profiles, CORS console, API usage center), AI-assist decorations.
