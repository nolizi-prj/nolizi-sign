# Incumbent UX Specification (behavior-level)

**Source:** signed-in product tour of the leading e-signature incumbent, captured 2026-08-30.
**Purpose:** clean-room wall for Pumasi Sign. This document describes flows, screens, states,
and interaction patterns at pattern level only. It deliberately contains no copy, colors,
logos, or visual identity from the incumbent. Status/label vocabulary used here (Sent,
Completed, Drafts, envelope, template, recipient, role) is industry-generic.

**Capture limitations (stated up front, referenced throughout):**

- The tour account was a free account. Actually *sending* an envelope to a third party is
  paywalled behind a trial-upsell modal, so the post-send confirmation screen, a populated
  "waiting for others" list, correction/resend flows, and the **remote recipient's**
  email-entry signing ceremony were **not observed**. The signing ceremony section below is
  based on the self-sign path, which uses the same signing surface.
- No envelope *detail* page (per-envelope history/timeline view) was captured; recipient
  status was only observed at list-row level and in the completion certificate PDF.
- Several admin pages were captured mid-load or as error pages; where a screen was
  ambiguous this is flagged rather than guessed.

---

## 1. Information architecture

**Top-level nav (persistent horizontal top bar):**

- Product mark (left) → Home
- `Home` — landing dashboard
- `Agreements` — the envelope manager (inbox/list views)
- `Templates` — template library and builder
- `Reports` — appears in the nav only for accounts/roles where reporting is enabled
  (observed present in the admin user's session, absent in the free session)
- `Admin` — account administration console (separate shell, see §8)
- Right cluster: plan-upsell button, "view plans" link, a tasks/checklist icon, help icon
  (with unread-dot badge), and an avatar chip (initials) opening the profile menu.

**Profile menu (avatar dropdown):** identity block (display name, email, account number),
then: manage profile, preferences, feedback, log out. "Manage profile" opens a separate
**personal settings shell** with its own left rail: profile, privacy & security, connected
apps, identity, signatures, stamps, language & region.

**Three distinct app shells** share the top nav but have different chrome:

1. **Main app** (Home / Agreements / Templates): content page with contextual left rail.
2. **Full-screen wizards** (envelope setup, template creation, field tagging, signing):
   the global nav disappears entirely; a minimal wizard header takes over with close (X),
   breadcrumb/step title, and primary/secondary actions on the right. This is a deliberate
   focus mode — the user exits via X (back to where they started) or by completing the flow.
3. **Admin console** and **personal settings**: left-rail settings layouts with grouped
   section headings.

**Movement model:** sending starts from Home (primary CTA) or from the Agreements list
("create envelope" button in empty state); templates start from the Templates section;
either path enters the full-screen wizard shell and returns to a list view on completion.

## 2. Home dashboard

**Layout:** a full-width hero band (dark accent background) with a centered greeting
("welcome back, {name}" pattern) and a centered row of three quick-action buttons:

1. **Get signatures** (primary; starts the send-envelope wizard)
2. **Sign a document** (self-sign / sign-what-you-upload flow)
3. **Create a template**

Below the hero: a content zone. In the observed **empty/new account state** it shows a
single onboarding card — illustration, headline encouraging the first send, one-line
explanation, and a link-style CTA that also starts the send wizard. Below that: help links
(guide, mobile app, community/support) and a footer (language selector, legal links).

**Pending-action summary / status tiles:** not observed in the empty account. The hero
shows a loading spinner where a summary module would render, so it is presumed that an
active account shows pending-action content there — **unconfirmed; do not copy blindly.**
For Pumasi Sign: design an "action required / waiting for others / recently completed"
counts module in that slot, with the empty state falling back to the onboarding card.

**Onboarding checklist (cross-cutting):** a dismissible "get started" banner sits under
the top nav on list pages: progress bar, "n/5 actions completed", the next suggested
action as a button, and a close X. A tasks icon in the top nav reopens the full checklist
as a modal: progress bar plus five rows (send a document, sign up, adopt your signature,
create a template, upload profile photo), each with icon, one-line description, chevron;
completed rows get a checkmark and muted styling. Checklist state updates as the user
completes actions anywhere in the product (observed advancing 1/5 → 2/5 → 4/5 during the
tour).

## 3. Agreements manager (inbox)

**Layout:** contextual left rail + list content.

**Left rail taxonomy:**

- Prominent "start" button at top (launches send wizard).
- Views: **All agreements**, **Drafts**, **In progress**, **Completed**, **Deleted**.
- **Folders** node (user-created folders; overflow menu on the node for folder management).
- Below a divider, feature entries: workflows, agreement manager (both flagged "new"),
  bulk-send and web-form entries shown with a lock glyph when plan-gated.
- Bottom of rail: a toggle between "new navigation" and a legacy navigation (the legacy
  variant folds status views under sent/inbox-style groupings). Pumasi Sign needs only one
  navigation; the important part is the status-view taxonomy above.

**List header:** page title, then a filter toolbar:

- Search input (searches envelopes by name/party).
- Date-range filter chip with a default window ("last 6 months" pattern) and an inline X
  to clear it.
- `Status` dropdown, `Sender` dropdown, `Quick views` dropdown, `Advanced search`
  disclosure, and a `Clear all` action.
- A layout/density toggle icon at the right end of the header row.

**Table columns:** [row checkbox] | Name (two-line cell: envelope subject on line 1,
"To: {recipient(s)}" on line 2) | Status (icon + label, e.g. Completed with a check
badge) | Last change (date + time on two lines) | [primary contextual action button] |
[overflow kebab menu].

**Per-row actions:** the primary button is status-dependent — observed `Download` for a
completed envelope; expect `Sign` for action-required and `Correct`/`Remind` variants for
sent envelopes (not observed — the free account could not send). A kebab opens more
actions (menu contents not captured open; treat exact action set per status as a design
decision: move-to-folder, view history, void, duplicate are the industry-standard set).

**Bulk behavior:** header select-all checkbox + per-row checkboxes exist; the bulk action
bar itself was not observed (list had one row). Provide at minimum bulk download/move/delete.

**Pagination:** results-per-page dropdown (5/10/25/50) + page indicator with prev/next
chevrons.

**Empty state:** an illustrated card with a short orientation paragraph ("your sent and
received envelopes live here" idea) and a "create envelope" button. Search with no result
was not explicitly captured.

**Search behavior:** typing a term filters the list to matches while retaining filter
chips (observed with a filename search). Filters and search compose.

**Deleted view:** exists as a first-class status view (soft-delete / trash pattern).
Restore behavior not observed.

## 4. Prepare & send flow (the envelope wizard)

Full-screen wizard, two macro-steps with a breadcrumb: **Set up envelope → Add fields**
(then a preview/send stage inside step 2). Header: X (close/abandon), step title,
help/settings icons, and the primary button `Next: add fields` (step 1) or
`Preview` / `Back` / `Send` (step 2). Drafts are implicitly created — an abandoned
envelope appeared in the templates/drafts lists as "[Untitled]" — but an explicit
"save and close" button was only observed in the *template* variant of this wizard;
the envelope variant relies on X-close + implicit draft.

### Step 1 — Set up envelope (single page, three collapsible sections)

Vertical accordion with three sections, each expandable/collapsible via chevron:

1. **Add documents.** A wide drop zone ("drop files here or Upload" pattern) with an
   `Upload` split-button (dropdown for other sources — cloud sources presumed, not
   opened). After upload, the file renders as a thumbnail card at left of the drop zone:
   first-page preview image, filename, page count, kebab menu, and hover overlay actions
   (view; X to remove appears as a top-right chip on hover). Multi-document envelopes
   are supported (drop zone remains after first file).
2. **Add recipients.** Contents:
   - Checkbox: "I'm the only signer" (converts flow to self-sign).
   - Checkbox: "set signing order" + a "view" link that opens a routing-order
     visualization. When enabled, each recipient card gains a numeric order stepper box
     on its left.
   - Recipient card(s): Name field (required, with contact-picker icon), Delivery method
     (required) as checkboxes — Email and SMS, SMS decorated with a premium/plan glyph and
     disabled on free plan; selecting neither shows an inline validation error row with
     error icon ("select a delivery method" idea). Email field (required), phone field
     (for SMS, with country-code prefix). At right of the card: a recipient-type dropdown
     (default "needs to sign"; other types — e.g. receives-a-copy — behind this dropdown)
     and a `Customize` dropdown (per-recipient options such as access authentication;
     contents not captured open).
   - `Add recipient` split-button appends more cards.
3. **Add message.** Collapsed by default; contains subject and message body (observed in
   the template-use variant: subject prefilled with "{action}: {filename}" pattern, with
   a 100-char counter; message textarea with 10000-char counter).

Below the accordion: **reminder frequency** dropdown with info tooltip (envelope-level
reminder setting; disabled/plan-gated in the free account).

Validation gates progression: `Next: add fields` errors visibly if a recipient lacks
delivery method, etc.

### Step 2 — Add fields (the tagging canvas)

Three-zone layout:

- **Left rail — field palette.** Top: recipient selector dropdown (chip with recipient
  initials + name, tinted with that recipient's assignment color) — fields placed while a
  recipient is selected belong to them. Below: a field-library dropdown ("standard fields"
  default), then grouped field buttons:
  - *Signature group:* Signature, Initials, Date signed (plus Stamp in the self-sign
    variant).
  - *Contact info:* Name, Email, Company, Title.
  - *Inputs:* Text, Checkbox, Dropdown, Radio.
  - *Actions:* Approve, Decline.
  - *Other:* Note, Formula, Attachment, Payment.
  Plan-gated fields carry a lock or premium glyph; several have "more info" affordances.
- **Center — document canvas.** Rendered pages at a zoom level (zoom dropdown in a
  toolbar above the canvas; toolbar also has quick-edit (inline PDF editing), undo/redo,
  copy/paste of fields, and an actions dropdown). Fields are **dragged from the palette
  and dropped** onto the page; while dragging, a ghost of the field follows the cursor.
- **Right rail — document/page navigator.** Collapsible panel listing each document with
  filename, page count, and page thumbnails (with per-page kebab). A "return to top"
  link. A small pointer/marker on the thumbnail mirrors field placement.

**Placed-field interaction:** selecting a placed field shows resize handles and a
floating mini-toolbar directly beneath it: recipient-assignment chip (dropdown to
reassign), Required toggle, duplicate icon, delete icon, and a settings (gear) icon
opening the full per-field properties panel. Fields are colored by assigned recipient.

**Preview / send:** `Preview` renders the recipient's view. The final `Send` action was
paywalled in the captured account (the send button opened a trial/plan modal with a
2-step checkout), so the **sent-confirmation screen was not observed**. Design guidance:
after send, return to the agreements list with the envelope in the sent/in-progress view
plus a confirmation toast.

**First-run education:** the wizard uses dismissible dark coach-mark popovers anchored to
key controls (upload zone, palette, finish button), each with a short line and
continue/hide-all buttons — one at a time, in sequence.

## 5. Signing ceremony (recipient experience)

Observed variant: **self-sign** ("sign a document" from Home → upload modal (same
thumbnail + drop zone pattern, `Cancel`/`Sign` buttons) → full-screen signing surface).
The remote-recipient email entry and consent/disclosure step were **not observed** (the
certificate for this envelope records that the e-signature disclosure was "not offered",
confirming a consent step exists as a configurable stage for sent envelopes).

**Signing surface layout:**

- Slim top bar: instructional text (left), primary `Finish` button (right; also a
  dropdown next to it for finish-later/decline-type options — not opened) and an overflow
  menu.
- **Left rail — signer field palette** (self-sign only): Signature, Initials, Stamp,
  Date signed, Name, Company, Title, Text, Checkbox. In a sent-envelope ceremony this
  rail is replaced by guided navigation over sender-placed fields.
- **Center:** document at fit width, 100% default zoom.
- **Right rail — utility icons:** AI summarize, search-in-document, page-thumbnails
  toggle, download, print; zoom controls bottom-right.
- Footer: powered-by mark, language selector, legal links (this surface is the one
  third parties see, hence branding/footer here).

**Guided navigation:** coach-marks instruct "place and complete fields / fill everything
before finishing." Auto-navigation between required fields is an account setting
(§8: page-only vs navigate-required vs navigate-all patterns), implying the ceremony has
a next-field stepper that walks the signer through required fields; a persistent hint
("press enter to complete required fields") was captured. **Start/next tab behavior was
not directly screenshotted** in a sent-envelope context.

**Adopt-signature modal** (first time a signature field is completed, also reachable from
personal settings): title ("create your signature" idea), Full name and Initials inputs
(prefilled, editable — regenerates previews), three tabs:

1. **Choose** — a radio list of generated signature styles; each row shows the full
   signature (cursive font render inside a bracket frame with a "signed by" label above
   and a truncated unique ID below) and the matching initials mark.
2. **Draw** — freehand canvas (not screenshotted open, tab present).
3. **Upload** — image upload (tab present).

Below: a legal consent sentence (agreeing the marks are the user's electronic signature),
`Create` (primary) and `Cancel`. Adopted signatures render on documents as the styled
name + frame + unique-ID string; multiple saved signature styles are supported and listed
in personal settings with per-row action menus.

**Applying fields while signing:** clicking a signature field stamps the adopted
signature; a date-signed field auto-fills the current date (rendered with a highlight
while editable); placed items can be deleted via an X badge before finishing.

**Finish sequence:** `Finish` → a completion coach-mark ("save the document; share next")
→ a **share modal**: multi-email input (enter-to-chip), subject prefilled
("here is your signed document: {filename}" pattern), optional message with 250-char
counter, `No thanks` / `Send` buttons. Each share recipient gets an email with a free
download link. Declining the share still completes the envelope.

**Post-sign state:** user returns to the agreements list; the envelope appears in
All/Completed with status Completed, timestamped, with a `Download` row action, and the
onboarding checklist advances.

## 6. Completed envelope & records

**List-level:** completed rows show a status badge (check icon + Completed), last-change
timestamp, and `Download` as the primary action.

**Download modal:** "select which files" checklist —

- **All** (n files)
- **Document** (the completed PDF)
- **Certificate of completion** (separate PDF)
- Separate option: **combine all PDFs into a single file** (checkbox)
- `Download` button. Delivered as a zip when multiple files are selected.

**Completed document PDF:** the original document with signature imprints burned in.
Each signature imprint renders as: a small "signed by" caption, the adopted signature
(cursive style), a bracket frame on the left edge, and a truncated envelope/party ID
string beneath. Auto-dated fields render as plain text dates.

**Certificate of completion (one page per envelope; the authoritative audit record).**
Fields observed:

- Envelope ID (GUID), overall status, subject line, source-envelope ref.
- Counts: document pages, certificate pages, signatures, initials.
- Envelope originator (name + email + IP address), auto-navigation setting,
  envelope-ID-stamping setting, time zone.
- **Record tracking:** original creation timestamp, holder (name/email), storage location.
- **Signer events table:** per signer — name, email, security level (e.g. email +
  account auth), an image of the signature applied, signature-adoption method
  (e.g. pre-selected style / drawn), signing IP address, and timestamps for
  Sent / Viewed / Signed; a note of the signing mode (e.g. free-form).
- Whether the electronic-record-and-signature disclosure was offered/accepted.
- Empty-but-present sections for other recipient types: in-person signer, editor, agent,
  intermediary, certified-delivery, carbon-copy, witness, notary events.
- **Envelope summary events:** Sent (hashed/encrypted), Certified delivered
  (security checked), Signing complete, Completed — each timestamped.
- Payment events section.

This certificate structure is the compliance backbone; Pumasi Sign should reproduce the
*data model* (event log with actor, IP, timestamp, security level, signature image,
hash/integrity notation) — not the incumbent's layout.

**Envelope detail page** (click-through from a row): **not captured**; expected content
is the same event data rendered as an in-app timeline plus recipient status chips —
treat layout as open design.

## 7. Templates

**Library view:** contextual left rail — Create-template button (top), then grouped views:
My templates, Shared with me, Favorites (+ show-more expanding to All templates, Deleted,
Folders, Shared folders), then plan-flagged entries (workflow templates, template
gallery/starter-templates browser).

**List:** search, date filter, advanced search, clear; sortable columns:
[checkbox] | favorite star | Name | Owner | Created date | Last change | Folders |
primary `Use` button | kebab menu. Row pattern matches the agreements list (same
pagination controls). Kebab menu contents were not captured open.

**Empty state:** illustrated card explaining templates ("save documents, placeholder
recipients and fields for reuse" idea) with create-template and browse-starter-templates
actions.

**Create-template flow:** same wizard shell as the envelope, with differences:

- Header gains **Save and close** (explicit draft save) alongside `Next: add fields`.
- Top of page 1: **Template name** input and **Template description** textarea (optional).
- Documents section may be decorated with an AI-assist note (uploads scanned to suggest
  fields).
- **Recipients are roles:** each recipient card leads with a **Role** input (free-text
  placeholder-recipient label, e.g. a "client signer" style role). Name/email become
  optional prefills; delivery method, recipient-type dropdown, customize dropdown, and
  signing order work as in the envelope. Validation requires at least one role or a
  named recipient before proceeding to fields.
- **Field tagging:** identical canvas; the recipient selector shows the role, and placed
  fields bind to roles.
- Saving (save-and-close from either step) lands the template in the library.
  A template abandoned before naming persists as "[Untitled]".

**Using a template:** `Use` on a row opens a **use-time page** (lighter-weight than the
wizard): template name in header, `Advanced edit` (reopens the full wizard for one-off
changes) and `Send` buttons top-right. Body: recipient card per role — role label shown
as the card title, sender fills Name and Email (delivery pre-set), can customize; then
the message section (subject prefilled from template, editable, with counters); a
read-only document preview thumbnail on the right. Send goes straight out — no re-tagging
step for the sender.

## 8. Settings/admin worth copying

The admin console is a separate shell: left rail with the admin's name + account ID at
top, an Overview page (search-a-setting/find-a-user widget, notifications feed, resource
links), and grouped sections. Worth copying for a small product:

**Reminders & expiration defaults (account level):**

- Master toggle: allow senders to override account defaults.
- Reminders: enable automatic reminders; days-before-first-reminder; days-between-
  reminders; optional cap on number of reminders.
- Expiration: days before request expires (required, e.g. default 120); days of warning
  to signers before expiration.
- Save / cancel footer.

**Signing settings (account level; shapes the recipient ceremony):**

- Auto-navigation mode dropdown: page-only / navigate required fields / navigate blank
  required fields / navigate all fields / page-then-navigate variants.
- Responsive (mobile-friendly) signing: enable + default-view dropdown (optimize for
  device / mobile-only / desktop-only).
- Recipient permissions checkboxes: require a decline reason; allow sign-on-paper (+
  sender override); allow mobile signing; allow reassigning signing responsibility (+
  sender override); allow editing documents; allow account creation; offline mobile
  signing; confirm-before-leaving-session prompt; remind-to-finish prompt.
- Delegation: allow delegated signers.
- Document formatting: date format picker for the date-signed field (large preset list +
  custom), time format picker (including none).
- Signature framing: apply frame (the "signed by" bracket + ID) vs plain signature.
- Envelope delivery: attach documents to the completion email; attach certificate to the
  envelope; self-signed-notification delivery as PDF vs link; embedded-signer email
  suppression options.

**Signature adoption (personal settings):** signatures page listing adopted
signature/initial pairs with per-row action menus and an add-signature button (opens the
adopt modal, §5). Also stamps management.

**Branding surface:** account-level branding page (plan-gated in the captured account;
shown as an upsell). Behavior to copy: sender can apply a logo and a color theme to
envelopes, templates, and notification emails. Keep it to logo + accent color for
Pumasi Sign.

**Regional settings:** account default time zone, default date/time format (same preset
list), default language; per-user override toggle; date-signed field language/timezone
resolution (recipient's vs account default).

**Custom metadata:** document custom fields and envelope custom fields — admin-defined
fields (name, type, shared flag, required flag) used to classify envelopes; both pages
are simple CRUD tables with search/filter and empty states.

**Document retention:** optional policy — keep completed/declined/voided documents N
days, then queue for purge; options to strip fields/metadata and redact PII; plus a
targeted per-envelope purge. (Worth a simplified version.)

**Skip as enterprise noise:** permission profiles/groups, custody transfer, comments
admin, connect/webhooks UI, API usage center, CORS, audit-log console, bulk actions,
value calculator. (Webhooks matter for the product API but need no admin UI copy.)

**Notification settings:** an email-preferences page exists in the admin rail
(not captured open). Provide per-user toggles for the standard notification events.

## 9. Interaction & polish inventory

- **Coach-mark onboarding:** sequential dark popovers with continue / hide-all, anchored
  to controls, shown only on first use of each surface; every surface remains fully
  usable underneath.
- **Persistent onboarding checklist:** progress banner + modal checklist that updates
  live as actions complete anywhere (see §2).
- **Accordion wizard** rather than paged steps for envelope setup: all three sections on
  one page, collapse/expand, single primary "next" that validates all sections.
- **Inline validation** with icon + red text row directly under the offending control
  (e.g. missing delivery method), triggered on attempted progression.
- **Implicit drafts:** closing a wizard silently persists an untitled draft; explicit
  save-and-close exists in the template variant.
- **Drag ghost + drop feedback** on the tagging canvas; placed fields get selection
  handles + floating mini-toolbar; duplicate/delete/required directly on the toolbar.
- **Recipient color-coding** connecting the recipient selector chip and their fields.
- **Character counters** under subject/message inputs (n/100, n/10000, n/250).
- **Split buttons** for upload (source picker) and add-recipient.
- **Two-line table cells** (name over recipients; date over time) to keep rows compact.
- **Status-contextual primary row action** (download vs sign) plus a kebab for the rest.
- **Filter chips with inline clear** and a global clear-all; default date window applied.
- **Loading states:** centered spinner in content zones; skeleton "loading…" rows in the
  rail during data fetch. (Also observed: hard API rate-limit errors surfacing as raw
  alert banners — an anti-pattern; Pumasi Sign should queue/retry instead.)
- **Empty states everywhere:** every list (agreements, templates, custom fields,
  webhooks, CORS) has an illustration/explainer + primary CTA; none are blank tables.
- **Full-screen focus modes** for prepare/tag/sign with a minimal header; X returns to
  origin.
- **Session-scoped upsell modals** at plan boundaries (send, SMS delivery, premium
  fields) with a feature-comparison table — the gating pattern (lock/premium glyphs on
  disabled controls) is worth copying even if Pumasi Sign's tiers differ.
- **Blocking progress modals** with spinner + label for slow mutations (template
  creation).
- **Mobile behavior:** responsive signing is a first-class account setting (device-
  optimized vs forced views); document viewer has zoom controls and fit-width default.
- **Keyboard:** enter-to-chip in multi-email input; "press enter to complete required
  fields" hint in signing; column headers are real buttons (sortable, a11y-labeled);
  skip-to-main-content link present.
- **Post-completion share loop:** the finish flow immediately offers sharing the signed
  PDF by email — a growth loop worth keeping.

## 10. Prioritized "similar UX" checklist

Ranked by how much each behavior defines the product feel. Tags: **trivial**
(CRUD/forms/lists), **moderate** (real logic but specifiable), **hard**
(algorithmic/subtle correctness).

1. **Drag-and-drop field tagging canvas** with per-recipient assignment, resize,
   required toggle, floating field toolbar, page-accurate coordinates — **hard**
   (coordinate mapping across zoom levels + PDF render fidelity is the product).
2. **Signature imprinting into the final PDF** (adopted style + frame + unique ID +
   auto-date), producing a flattened completed document — **hard**.
3. **Certificate of completion generation** with full event log (sent/viewed/signed
   timestamps, IPs, security level, adoption method, integrity notations) — **moderate**
   (specifiable; correctness matters).
4. **Adopt-signature modal**: choose (generated styles from name/initials) / draw /
   upload tabs, live preview, legal consent, persistence of multiple styles —
   **moderate** (draw canvas + style generation).
5. **Guided signing navigation**: auto-advance through required fields, finish gating on
   completion, configurable navigation mode — **moderate**.
6. **Envelope state machine**: draft → sent → delivered/viewed → completed, plus
   declined/voided/expired, driving list placement, row actions, and notifications —
   **moderate** (the core domain logic; specify exhaustively).
7. **Status-tabbed agreements manager**: all/drafts/in-progress/completed/deleted rail,
   filter chips + search + date window, two-line rows, status-contextual primary action +
   kebab — **trivial/moderate** (list is trivial; contextual action matrix is moderate).
8. **One-page accordion send wizard** (documents / recipients / message) with inline
   validation and implicit drafts — **moderate**.
9. **Templates with placeholder roles**: role-based recipient cards, fields bound to
   roles, use-time page where the sender only fills name/email + message and sends —
   **moderate** (role→recipient binding at instantiation).
10. **Signing-order UI**: order steppers on recipient cards + routing visualization,
    sequential vs parallel delivery — **moderate**.
11. **Download modal** with document / certificate / combine-into-one options (zip for
    multi-file) — **trivial** (PDF merge is a library call).
12. **Post-sign share loop**: share modal with multi-email chips, prefilled subject,
    free download links for recipients — **trivial/moderate** (tokenized download links).
13. **Reminder & expiration engine**: account defaults + per-envelope override, first
    reminder after N days, repeat every M days, cap, expiration with pre-warning —
    **moderate** (scheduling correctness across time zones).
14. **Email notifications** for send/view/sign/complete with attach-PDF vs link options —
    **moderate**.
15. **Coach-mark first-run tours + persistent onboarding checklist** with live progress —
    **trivial/moderate**.
16. **Upload pipeline**: drop zone + multi-doc thumbnails with page counts, remove/view,
    multi-source upload button — **moderate** (PDF page rendering).
17. **Field palette taxonomy**: signature/initials/date-signed; name/email/company/title;
    text/checkbox/dropdown/radio; approve/decline; note/attachment — **trivial**
    (each field type's signing-time behavior is a small spec item).
18. **Per-field properties**: required flag, recipient reassignment, duplicate, delete,
    settings panel (validation/formatting for text fields) — **moderate**.
19. **Self-sign path**: "I'm the only signer" short-circuit + sign-a-document entry that
    skips recipient entry and opens the signing surface directly — **trivial** given
    5–6 exist.
20. **Date/time/format regional settings** applied to the date-signed field (account
    default + per-user override + recipient-locale resolution) — **moderate**.
21. **Soft delete (deleted view) and folders** for envelopes and templates — **trivial**.
22. **Empty states with CTA on every list** — **trivial**, disproportionate polish value.
23. **Account-level signing-permission toggles** (decline reason required, reassignment,
    mobile, leave-session confirmation) — **trivial** to build, **moderate** to honor
    correctly in the ceremony.
24. **Branding**: logo + accent color applied to signing surface and emails — **trivial**.
25. **Document retention purge policy** (N-day purge queue, metadata stripping) —
    **moderate**; defer if needed.

---

### Open questions / not determinable from artifacts

1. Post-send confirmation screen and populated sent/in-progress list states (send was
   paywalled in the captured account).
2. Remote recipient ceremony entry: email content, access link handling, consent/
   disclosure screen, decline flow, finish-later.
3. Envelope detail page (in-app history timeline, recipient status chips, resend/void
   controls).
4. Contents of the row kebab menus (agreements + templates) and the recipient
   `Customize` dropdown (per-recipient auth options).
5. Bulk-action bar behavior when rows are selected.
6. Draw/upload tabs of the adopt-signature modal (not opened in capture).
7. Correction/void/resend flows and their states.
8. Advanced-search panel contents.
