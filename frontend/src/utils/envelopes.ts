/**
 * Pure envelope-list logic shared by the envelope browser and the dashboard,
 * so "waiting on you" means the same thing everywhere (the action-required
 * badge, the dashboard cards, and the greeting count previously used three
 * different rules). Kept free of Vue imports so it's unit-testable.
 */
import type { SubmissionOut, SubmitterOut } from "../types";

/** The viewer's own submitter row, if they're a recipient. */
export function mySubmitter(submission: SubmissionOut): SubmitterOut | null {
  return submission.submitters.find((s) => s.id === submission.my_submitter_id) ?? null;
}

/** Ordered signing: it's `signer`'s turn once every lower-group signer
 *  (CC rows never gate routing) has completed. */
export function isTurnOf(submission: SubmissionOut, signer: SubmitterOut): boolean {
  return submission.submitters.every(
    (peer) => peer.is_cc || peer.order_index >= signer.order_index || peer.status === "completed",
  );
}

/** The envelope needs the viewer's signature *right now*: pending, they're a
 *  signer (not CC), they haven't signed, and it's their turn. */
export function actionNeeded(submission: SubmissionOut): boolean {
  const me = mySubmitter(submission);
  return (
    submission.status === "pending" &&
    me !== null &&
    !me.is_cc &&
    me.status !== "completed" &&
    isTurnOf(submission, me)
  );
}

/** The viewer will need to sign, but earlier signers haven't finished yet. */
export function waitingForMyTurn(submission: SubmissionOut): boolean {
  const me = mySubmitter(submission);
  return (
    submission.status === "pending" &&
    me !== null &&
    !me.is_cc &&
    me.status !== "completed" &&
    !isTurnOf(submission, me)
  );
}

/** Dashboard action cards: actionNeeded minus envelopes the viewer archived. */
export function actionRequired(submission: SubmissionOut): boolean {
  return actionNeeded(submission) && !submission.archived_by_me;
}

/** Latest of created/signed/reminded/completed — ISO strings sort lexically. */
export function lastChange(submission: SubmissionOut): string {
  let latest = submission.completed_at ?? submission.created_at;
  for (const s of submission.submitters) {
    if (s.signed_at && s.signed_at > latest) latest = s.signed_at;
    if (s.last_reminded_at && s.last_reminded_at > latest) latest = s.last_reminded_at;
  }
  return latest;
}

export interface EnvelopeRow {
  submission: SubmissionOut;
  isSender: boolean;
  isRecipient: boolean;
  waitingOnMe: boolean;
  waitingForTurn: boolean;
  hasBounced: boolean;
  lastChange: string;
}

export function toRow(submission: SubmissionOut, myId: number | null): EnvelopeRow {
  return {
    submission,
    isSender: submission.sender.id === myId,
    isRecipient: submission.my_submitter_id !== null,
    waitingOnMe: actionNeeded(submission),
    waitingForTurn: waitingForMyTurn(submission),
    hasBounced: submission.submitters.some((s) => s.email_status === "failed"),
    lastChange: lastChange(submission),
  };
}

/** DocuSign's "Expiring Soon" window: pending envelopes due within six days. */
const EXPIRING_SOON_DAYS = 6;

/** Pending with a deadline at most six days out — past-due included, since a
 *  deadline the daily sweep hasn't flipped yet is the most urgent of all. */
export function expiringSoon(submission: SubmissionOut, now: Date = new Date()): boolean {
  if (submission.status !== "pending" || !submission.expires_at) return false;
  const cutoff = now.getTime() + EXPIRING_SOON_DAYS * 24 * 60 * 60 * 1000;
  return new Date(submission.expires_at).getTime() <= cutoff;
}

export type ViewKey =
  | "inbox"
  | "drafts"
  | "sent"
  | "completed"
  | "action"
  | "expiring"
  | "attention"
  | "archived";

export function inView(row: EnvelopeRow, key: ViewKey, now: Date = new Date()): boolean {
  // Archiving is a per-user hide: archived envelopes live only in the
  // Archived view and vanish from every other one.
  if (key === "archived") return row.submission.archived_by_me;
  if (row.submission.archived_by_me) return false;
  // Inbox is things sent *to* you — a draft was sent to nobody, including
  // a sender who addressed themselves.
  if (key === "inbox") return row.isRecipient && row.submission.status !== "draft";
  // DocuSign-style stages: unsent drafts live in Drafts, not Sent.
  if (key === "drafts") return row.isSender && row.submission.status === "draft";
  if (key === "sent") return row.isSender && row.submission.status !== "draft";
  if (key === "completed") return row.submission.status === "completed";
  if (key === "expiring") return expiringSoon(row.submission, now);
  // A bounced recipient is the sender's to fix (correct contact + resend);
  // only live envelopes are actionable.
  if (key === "attention") return row.isSender && row.submission.status === "pending" && row.hasBounced;
  return row.waitingOnMe;
}

/** Case-insensitive match on title, sender, any participant, or the envelope
 *  ID (the stamp people paste back from a watermarked PDF). `needle` must
 *  already be trimmed + lowercased. */
export function matchesSearch(row: EnvelopeRow, needle: string): boolean {
  const s = row.submission;
  if (s.title.toLowerCase().includes(needle)) return true;
  if (s.public_uid.toLowerCase().includes(needle)) return true;
  if (s.sender.name.toLowerCase().includes(needle) || s.sender.email.toLowerCase().includes(needle)) {
    return true;
  }
  return s.submitters.some(
    (sub) =>
      sub.user.name.toLowerCase().includes(needle) || sub.user.email.toLowerCase().includes(needle),
  );
}

/** Normalize a search-box model: Vuetify's clearable ✕ sets it to null. */
export function normalizeSearch(value: string | null | undefined): string {
  return (value ?? "").trim().toLowerCase();
}
