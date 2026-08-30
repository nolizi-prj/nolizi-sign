/**
 * UI vocabulary helpers. The API speaks `submission`/`submitter`; the UI
 * speaks `envelope`/`signer` (see docs/superpowers/plans/2026-07-31-ux-redesign-plan.md).
 * These helpers keep status wording and colors consistent across views.
 */
import type { SubmissionStatus, SubmitterStatus, TemplateBrief, User } from "../types";

/** The app-wide "person label" convention for signer pickers and review lists. */
export function userLabel(user: Pick<User, "name" | "email">): string {
  return `${user.name} (${user.email})`;
}

/**
 * A signer's role for display, or null for one-off envelopes — their roles
 * are internal `signer-N` bookkeeping ids that must never reach the UI
 * (the signer's real name is always shown separately).
 */
export function displayRole(template: Pick<TemplateBrief, "is_adhoc">, role: string): string | null {
  return template.is_adhoc ? null : role;
}

/** Signer-status chip label: what a sender wants to know at a glance.
 *  Pass the envelope's status so a draft's untouched signers read
 *  "Not sent yet" instead of the post-send "Sent". */
export function signerStatusLabel(status: SubmitterStatus, envelopeStatus?: SubmissionStatus): string {
  if (status === "completed") return "Signed";
  if (status === "opened") return "Opened";
  if (status === "declined") return "Declined";
  if (envelopeStatus === "draft") return "Not sent yet";
  return "Sent";
}

export function signerStatusColor(status: SubmitterStatus): string {
  if (status === "completed") return "success";
  if (status === "opened") return "warning";
  if (status === "declined") return "error";
  return "grey";
}

export function envelopeStatusLabel(status: SubmissionStatus): string {
  if (status === "draft") return "Draft";
  if (status === "completed") return "Completed";
  // DocuSign's term — the backend status value stays "cancelled".
  if (status === "cancelled") return "Voided";
  if (status === "declined") return "Declined";
  if (status === "expired") return "Expired";
  return "In progress";
}

export function envelopeStatusColor(status: SubmissionStatus): string {
  if (status === "draft") return "info";
  if (status === "completed") return "success";
  if (status === "cancelled") return "grey";
  if (status === "declined") return "error";
  if (status === "expired") return "orange";
  return "warning";
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** "just now", "3h ago", "2d ago" — for reminder/sent captions. */
export function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
