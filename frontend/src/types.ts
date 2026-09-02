/**
 * Shared TypeScript shapes mirroring the backend's Pydantic schemas
 * (see backend/app/schemas.py and backend/app/routers/auth.py).
 *
 * Keep these in sync by hand — there's no codegen step. When a backend
 * schema changes, update the matching interface here.
 */

export interface User {
  id: number;
  email: string;
  name: string;
  is_admin: boolean;
  is_external: boolean;
  can_send: boolean;
  role?: "owner" | "admin" | "member";
  provider?: "email" | "google" | "microsoft" | string;
}

export type FieldType =
  | "signature"
  | "initials"
  | "name"
  | "date"
  | "text"
  | "checkbox"
  | "dropdown"
  | "radio"
  | "attachment"
  | "label";

/** Canonical field-type list, in display order (mirrors the union above). */
export const FIELD_TYPES: FieldType[] = [
  "signature",
  "initials",
  "name",
  "date",
  "text",
  "checkbox",
  "dropdown",
  "radio",
  "attachment",
  "label",
];

export interface FieldDef {
  id: string;
  type: FieldType;
  /** Empty string for `label` fields — they're sender text, owned by no signer. */
  role: string;
  page: number;
  x: number;
  y: number;
  w: number;
  h: number;
  required: boolean;
  /**
   * `text`: optional prefill the signer sees (and may edit).
   * `label`: the sender-authored static text itself.
   */
  default_value?: string | null;
  /**
   * Sender-chosen text size in points (6–72) for text/label/name/date;
   * null/absent = automatic (0.6 × box height, capped at 14pt). Clamped to
   * the box height at render time and still shrunk to fit the box width.
   */
  font_size?: number | null;
  /** `dropdown`/`radio`: the choices the signer picks from (1–20, unique). Null otherwise. */
  options?: string[] | null;
  /** `text` only: a format the signer's input must match. Null otherwise. */
  validation?: "email" | "number" | null;
}

export interface TemplateOut {
  id: number;
  name: string;
  page_count: number;
  fields: FieldDef[];
  /** Ordered signer-role list; may include roles that have no fields yet. */
  roles: string[];
  created_at: string;
  /** Set only while this owner-controlled template is in the archive. */
  archived_at: string | null;
  /** Owner has one or more explicit shares, or viewer received an explicit share. */
  shared: boolean;
  /** Owners may edit; explicitly invited recipients may only use the template. */
  access: "owner" | "use";
  /** The template's creator — labels shared templates and gates edit actions client-side. */
  owner: UserBrief;
}

export interface UserBrief {
  id: number;
  name: string;
  email: string;
  is_external: boolean;
}

export interface TemplateBrief {
  id: number;
  name: string;
  /** One-off envelope: its roles are internal `signer-N` ids, never display text. */
  is_adhoc: boolean;
}

export type SubmitterStatus = "pending" | "opened" | "completed" | "declined";

export interface SubmitterOut {
  id: number;
  user: UserBrief;
  role: string;
  status: SubmitterStatus;
  signed_at: string | null;
  email_status: string | null;
  last_reminded_at: string | null;
  reminder_count: number;
  /** Routing-order group; equal values are reached in parallel, lower groups first. */
  order_index: number;
  /** CC recipient: emailed a copy when routing reaches them; never signs or blocks. */
  is_cc: boolean;
}

export type AuditEventType =
  | "created"
  | "sent"
  | "opened"
  | "signed"
  | "reminded"
  | "completed"
  | "cancelled"
  | "declined"
  | "corrected"
  | "expired";

export interface AuditEventOut {
  id: number;
  event: AuditEventType;
  created_at: string;
  actor: UserBrief | null;
  detail: Record<string, unknown> | null;
}

export type SubmissionStatus = "draft" | "pending" | "completed" | "cancelled" | "declined" | "expired";

export interface SubmissionOut {
  id: number;
  /** Random ID stamped on the signed PDF's watermark and certificate. */
  public_uid: string;
  title: string;
  message: string | null;
  status: SubmissionStatus;
  created_at: string;
  completed_at: string | null;
  /** Sender-chosen deadline; null = never expires. */
  expires_at: string | null;
  /** Per-envelope reminder policy (defaults: on, every 3 days). */
  reminders_enabled: boolean;
  reminder_interval_days: number;
  template: TemplateBrief;
  sender: UserBrief;
  submitters: SubmitterOut[];
  my_submitter_id: number | null;
  /** Whether the viewer archived this envelope out of their own lists (per-user hide). */
  archived_by_me: boolean;
  /** False for envelopes completed before the certificate became a separate artifact. */
  has_certificate: boolean;
}

/** One data field's entry in an envelope's form data (GET /submissions/{id}/form-data). */
export interface FormDataEntryOut {
  submitter_id: number;
  recipient: UserBrief;
  /** Empty string for ad-hoc envelopes (their signer-N roles are internal ids). */
  role: string;
  field_id: string;
  field_type: FieldType;
  page: number;
  /** Null until the owning recipient completes (or for optional fields left blank). */
  value: string | boolean | null;
  signed_at: string | null;
}

export interface FormDataOut {
  submission_id: number;
  public_uid: string;
  title: string;
  status: SubmissionStatus;
  entries: FormDataEntryOut[];
}

export interface SignSubmissionBrief {
  id: number;
  title: string;
  message: string | null;
  status: SubmissionStatus;
  /** Deadline shown on the signing page; the page treats a past value as expired. */
  expires_at: string | null;
}

export interface SignTemplateBrief {
  id: number;
  page_count: number;
  fields: FieldDef[];
}

/** Response shape for GET /api/sign/{submitterId}. */
export interface SignerViewOut {
  submission: SignSubmissionBrief;
  template: SignTemplateBrief;
  my_fields: string[];
  my_status: SubmitterStatus;
  /** False while earlier-order signers haven't finished — signing is blocked until then. */
  my_turn: boolean;
  saved_signature_id: number | null;
  /** role -> that submitter's display name, one entry per submitter on this submission. */
  role_names: Record<string, string>;
  disclosure: { version: string; text: string };
  /** The signer's display name (rendered into `name` fields). */
  my_name: string;
}

/** Response shape for GET /api/sign/token/{accessUid}. */
export interface SignTokenViewOut {
  status: "open" | "already_signed" | "completed" | "cancelled" | "declined" | "expired";
  title: string;
  sender_name: string;
  masked_email: string;
}
