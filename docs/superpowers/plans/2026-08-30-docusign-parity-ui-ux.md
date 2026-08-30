# Implementation Plan: DocuSign UI/UX Parity & Workflow Enhancements (Revised)

**Plan ID**: `PLAN-SIGN-2026-08-30-DOCUSIGN-PARITY-V2`  
**Status**: REVISED PER CLAUDE PEER REVIEW  
**Spec Reference**: [`docs/superpowers/specs/2026-08-30-docusign-parity-ui-ux-design.md`](../specs/2026-08-30-docusign-parity-ui-ux-design.md)  
**Target Repository**: `pumasi-sign`  

---

## 1. Work Breakdown Structure

### Task 1: SignaturePad.vue Customization & Cursive Styles
- Add `inkColor` state (`#1A56DB` vs `#111827`) for both drawing and typing.
- Enhance `SignaturePadLib` with stroke smoothing parameters (`minWidth: 1.5`, `maxWidth: 3.5`, `throttle: 16`).
- Add 4 cursive calligraphy font options in the Type tab (`Caveat`, `Dancing Script`, `Great Vibes`, `Sacramento`) with robust system fallbacks.
- Add legal binding disclosure consent banner.

### Task 2: SignView.vue Floating "START / NEXT" Guided Navigator
- Add floating sticky tag `.pf-guided-tag` on document viewport:
  - `▶ START` when 0 required fields completed (Amber `#D97706`).
  - `NEXT ▶ (X left)` when in-progress (DocuSign Blue `#1A56DB`).
  - `✔ REVIEW & FINISH` when all required fields complete (Green `#059669`).
- Use `{ preventScroll: true }` on `focus()` followed by smooth scrolling to avoid scroll cancellation.
- Add `prefers-reduced-motion` media queries and `aria-live="polite"` on counter.

### Task 3: EnvelopeBrowser.vue In-Modal Audit History & Action Menu
- Add `v-dialog` for `historyModalOpen` rendering real-time audit event timeline without navigating away.
- Ensure `Void` is gated to sent/pending envelopes, and `Delete` is gated to drafts.

### Task 4: DashboardView.vue Hero Drag-and-Drop Dropzone
- Create `frontend/src/store/draftHandoff.ts` composable/store to hold dropped `File`.
- Add drag-and-drop zone to Dashboard hero section gated on `auth.canSend`.
- Prevent accidental browser file drops on document body.
- Route into `SendView.vue` and initialize upload from handoff store.

---

## 2. Verification Steps

1. Run `npm --prefix frontend run build` (`vue-tsc -b && vite build`) to ensure 0 type errors.
2. Verify all UI components in browser.
