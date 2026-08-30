# UX redesign implementation plan — 2026-07-31

Implements the approved proposal from the DocuSeal UX review (see the
published artifact "Pumasi Sign — UX review & redesign proposal"). Seven
incremental commits, each leaving the app working.

## Scope decisions

- **Terminology**: UI says *envelope* (a sent signing request), *signer*
  (a person who must sign), *signer role* (a slot on a template). Code and
  API keep `submission`/`submitter` — translation happens in UI strings only.
- **Theme**: Pumasi accent `#0E6272` (deep teal) as Vuetify `primary`;
  light theme only for now (PDF-on-white product), `color-scheme: light`
  to fix the dark-OS native-input clash. Role colors move to a shared
  `utils/roleColors.ts`.
- **Ad-hoc sends** are PDF-only (client renders the file locally for field
  placement before anything is uploaded; docx/xlsx would need server-side
  conversion first — out of scope).
- **Ordering stays "any order"** per the spec; no sequential signing UI.

## Commits

1. **Plan doc** (this file).
2. **Theme + shell + toasts**: Vuetify theme tokens; `App.vue` — title
   links home, admin "Send" button, name hidden on xs; global toast store
   (`store/ui.ts`) + `<v-snackbar>` host in App.vue; `utils/roleColors.ts`;
   `style.css` color-scheme fix.
3. **Dashboard revamp**: sign-queue as cards with "Review & sign" CTA;
   "My signed documents" section (clear about still-pending envelopes);
   admin "Sent envelopes" table gains reminded-ago captions, "Needs
   attention" chip for bounced email, row link to the envelope detail page,
   toasts for remind/cancel/archive; real empty states with CTAs everywhere.
4. **Envelope detail page**: backend adds `last_reminded_at` +
   `reminder_count` to `SubmitterOut` and `GET /api/submissions/{id}/events`
   (sender/admin only) with tests; frontend adds `/envelopes/:id` —
   signer rows with per-signer status/timestamps, audit timeline,
   remind/cancel, retry-completion banner when stuck, signed-PDF download.
5. **Guided signing**: top progress bar ("field x of N · page y of z"),
   ordered field navigation with Back/Next + autoscroll and focus,
   done/active/todo visual states, review-and-consent dialog before
   complete, success card with download/who's-pending, aria-labels on all
   field inputs.
6. **Send wizard**: 3 steps (Document → Signers → Review & send).
   Document step: pick a template or upload a one-off PDF. One-off path
   places fields inline (reuses `FieldBox` + the builder's placement
   pattern) and posts to `/submissions/adhoc`.
7. **Builder**: page-thumbnail rail (shared pdf.js document cache in
   `PdfPage` so N pages ≠ N document loads); debounced autosave with
   "Saving… / All changes saved / Unsaved changes" state; route-leave +
   beforeunload guards; Send saves first; back link; preview-as-signer
   dialog (fields rendered read-only as a signer sees them).

## Verification

- `npm run build` (includes vue-tsc type-check) per frontend commit batch.
- `ruff check` + `pytest` for the backend change (needs the local
  Postgres test container from README).
- Manual flows aren't scriptable here; the PR stays draft for the user to
  click through dev.

---

## Execution update — 2026-07-31, second pass

Status after the first pass (PR #8, commits e066be4..b3c9900):

- **CI on PR #8**: backend ✅, frontend ✅, **e2e ❌** — the Playwright
  spec still encodes the old UX (builder Save button + "Saved." text,
  one-click Finish, "Envelope sent." toast + redirect to `/`), and the
  dashboard's new "Create your first template" empty-state button trips a
  strict-mode violation against the dialog's "Create" (substring match).
- **main moved**: `53d0cdb` (app-bar home link — superseded by ours) and
  `7044bfd` (EnvelopeComposeView: one-off sends via a new
  `useFieldPlacement` composable, shared roleColors, PdfPage `loaded`
  emit, and backend adhoc `message` support with tests — verified live).
  This overlaps our send wizard's ad-hoc path.

Integration plan to land everything:

1. **Merge origin/main into the branch** (single conflict pass; repo
   convention is merge PRs). Resolutions:
   - `PdfPage.vue`, `roleColors.ts`, `DashboardView.vue`, `router` — ours
     (ours already includes the `loaded` emit plus the document cache).
   - `submissions.py` / `test_submissions.py` — union (their adhoc
     `message` + our events endpoint).
2. **Consolidate one-off sends into the wizard** (one flow, not two):
   drop `EnvelopeComposeView` + its route/dashboard entry; adopt from it
   the `useFieldPlacement` composable (builder + wizard both use it), the
   optional message on ad-hoc sends, and its person-first recipients UX —
   auto `signer-N` roles under the hood, person names shown everywhere.
3. **Update the e2e spec to the new UX**: dialog-scoped Create click,
   autosave (wait for the PUT + "All changes saved") instead of Save,
   wizard steps (Continue → review → "Send envelope", land on
   `/envelopes/:id`), queue-card "Review & sign" entry, review dialog
   consent + "Sign & finish", dashboard "Completed" label.
4. Verify: `npm run build`, backend pytest, push, watch CI until green.
5. Mark PR #8 ready for review. Merging to main (= production deploy via
   Railway auto-deploy) stays a human decision.
