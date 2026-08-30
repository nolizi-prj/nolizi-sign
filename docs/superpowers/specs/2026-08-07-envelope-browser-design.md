# DocuSign-style envelope browser with search and filters

Date: 2026-08-07. Driven by user feedback: the dashboard's two envelope
lists ("My signed documents", "Sent envelopes") have different features,
there is no search, and the user wants a DocuSign-like interface
(sidebar views + one consistent table). Closes issue #43 (dashboard
search).

## Design

The dashboard keeps its greeting and "Waiting on you" action cards; the
two lists below are replaced by one envelope browser.

**Data.** Client-side merge of the existing `GET /submissions?mine=sign`
and `?mine=sent` responses (deduped by id — an envelope can be both).
No backend changes.

**Sidebar views** (count badges): Inbox (I'm a signer or CC), Sent (I
sent it; only for `canSend` users, like today's Sent list), Completed
(status completed, either relationship), Action required (my submitter
status ≠ completed on a pending envelope). Sidebar collapses to
horizontal chips on small screens.

**Table** (same columns in every view): Name — link to envelope detail,
plus the bounced-email "Needs attention" chip; Participants — per-signer
status chips (CC rows shown as "CC"); Status — envelope status chip, or
"Waiting on you" when it's my turn; Last change — the latest of
created/signed/reminded/completed timestamps, sortable, default sort
descending. Row actions: "Sign now" when waiting on me, "Signed PDF"
when completed, History always; an overflow menu adds Remind and Cancel
(sender or admin, pending envelopes only — same rules as the envelope
page) and View document.

**Search + filters** above the table: keyword search (case-insensitive
substring over title, sender name/email, participant names/emails),
status dropdown, sender dropdown (distinct senders in the loaded data),
sent-date from/to pickers, and a clear-all button. All filtering is
client-side.

Templates keep their existing card below the browser, unchanged.

## Testing

`vue-tsc --noEmit` + `npm run build`; CI e2e (compose flow reads the
dashboard after sending). Filter/search interactions verified manually.
