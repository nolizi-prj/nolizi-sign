# DocuSign UI/UX Parity & Workflow Architecture Specification (Revised)

**Spec ID**: `SPEC-SIGN-2026-08-30-DOCUSIGN-PARITY-V2`  
**Status**: REVISED PER CLAUDE PEER REVIEW  
**Target Repository**: `pumasi-sign` (`frontend/`)  
**Author**: Pumasi Design & Engineering Team  

---

## 1. Intent & Scope Delta

Building on the existing `pumasi-sign` architecture (`roleColors.ts`, `EnvelopeBrowser.vue`, `audit.py`), this specification defines the precise deltas to achieve seamless DocuSign UI/UX parity:

1. **Floating Guided "START / NEXT" Navigator (`SignView.vue`)**:
   - Prominent floating action tag assisting signers across long multi-page documents.
   - Smooth auto-scrolling to next unfulfilled required field with `{ preventScroll: true }` focus ordering.
   - Respects `prefers-reduced-motion` and includes `aria-live="polite"` counter for accessibility.
2. **Customized Signature Adoption Pad (`SignaturePad.vue`)**:
   - **Ink Color Selection**: Classic Navy Blue (`#1A56DB`) and Pitch Black (`#111827`) for new draws and typed signatures.
   - **Deterministic Calligraphy Font Gallery**: 4 distinct cursive styles with pre-rendering font readiness checks (`Caveat`, `Dancing Script`, `Great Vibes`, `Sacramento`) and standard system cursive fallbacks.
   - **Legal Compliance Consent Disclaimer** displayed uniformly across internal and external signing flows.
3. **Fast In-Modal Audit History (`EnvelopeBrowser.vue`)**:
   - Instant modal view for envelope audit logs directly from the row action menu, providing rapid inspection without full-page navigation.
   - Distinct, status-gated actions for `Void` (sent/pending envelopes) and `Delete` (drafts only).
4. **Dashboard Hero Drag-and-Drop Dropzone (`DashboardView.vue`)**:
   - Click-and-drag hero dropzone gated by `auth.canSend`.
   - Global document dragover/drop preventers to prevent browser navigation escapes.
   - In-memory handoff composable to transition dropped file seamlessly into `SendView.vue`.

---

## 2. Component Technical Specifications

### 2.1 Guided Signing Navigator (`frontend/src/views/SignView.vue`)
- **Floating Guide Tag (`.pf-guided-tag`)**:
  - Pinned on the document viewport (bottom/side) with subtle pulse animation (disabled when `prefers-reduced-motion: reduce`).
  - **Dynamic State Labels**:
    - Unstarted (0 required fields complete): `▶ START` (DocuSign Golden Amber `#D97706` / `#F59E0B`).
    - In-Progress: `NEXT ▶ (X required left)` (DocuSign Blue `#1A56DB`).
    - Complete: `✔ REVIEW & FINISH` (Forest Green `#059669`).
  - **Interaction & A11y**:
    - Clicking the tag triggers `focus({ preventScroll: true })` on the target input element, followed by smooth `scrollIntoView({ behavior: 'smooth', block: 'center' })`.
    - Counter rendered inside `<span aria-live="polite">` for screen readers.

### 2.2 Signature Adoption Pad (`frontend/src/components/SignaturePad.vue`)
- **Draw Tab Ink Toggles**:
  - Ink choice radio/chips: `Navy Blue (#1A56DB)` and `Black (#111827)`.
  - Configures `pad.penColor` dynamically on selection.
  - Smooth stroke dynamics: `minWidth: 1.5`, `maxWidth: 3.5`, `throttle: 16`.
- **Type Tab Calligraphy Gallery**:
  - Selectable style cards displaying live preview of typed name/initials.
  - Styles:
    1. *Classic Cursive* (`'Caveat', cursive, sans-serif`)
    2. *Elegant Script* (`'Dancing Script', cursive, sans-serif`)
    3. *Formal Calligraphy* (`'Great Vibes', cursive, serif`)
    4. *Casual Signature* (`'Sacramento', cursive, sans-serif`)
  - Ensures canvas `fillText` executes cleanly with fallback font stacks.
- **Legal Compliance Consent Disclaimer**:
  - Clear statutory disclaimer: `"By clicking Adopt and Sign, I agree that the signature and initials will be the electronic representation of my signature for all purposes when I or my agent use them on documents."`

### 2.3 Agreements In-Modal Audit History (`frontend/src/components/EnvelopeBrowser.vue`)
- **Action Dropdown**:
  - Preserves standard primary actions while adding `...` menu with `View Audit History` modal, `Resend Reminder`, and status-gated `Void Envelope` / `Delete Draft`.
- **Audit Timeline Modal (`v-dialog`)**:
  - Renders chronological event list (`created`, `sent`, `viewed`, `signed`, `completed`, `declined`, `voided`) with timestamp localization, submitter identity, and recorded IP addresses.

### 2.4 Dashboard Hero Dropzone (`frontend/src/views/DashboardView.vue`)
- Gated to senders (`auth.canSend`).
- Features click-to-browse file picker and dragover hover effects.
- Uses `draftFileHandoff` store to pass selected `File` into `SendView.vue`.

---

## 3. Acceptance Criteria

- **AC-1 (Guided Navigation & A11y)**: In `SignView.vue`, clicking the floating guide tag focuses the target required input and scrolls smoothly without aborting scroll. Respects `prefers-reduced-motion`.
- **AC-2 (Signature Customization & Ink)**: In `SignaturePad.vue`, drawing with blue ink produces `#1A56DB` strokes; typing renders cursive styles with legal disclaimer visible.
- **AC-3 (In-Modal Audit History)**: In `EnvelopeBrowser.vue`, clicking `History` opens the audit events timeline in a modal without navigating away from the dashboard.
- **AC-4 (Hero Dropzone)**: In `DashboardView.vue`, dragging and dropping a PDF transitions to `SendView.vue` with the document preloaded.
- **AC-5 (Build & Typecheck)**: `npm --prefix frontend run build` passes with 0 TypeScript and 0 Vite errors.
