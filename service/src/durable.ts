/**
 * Pumasi Sign Durable Object — auth, tenancy, envelopes, and signing.
 *
 * Two principals, two cookies:
 *  - `sign_session`  — an account owner (sender). Random token in `sessions`.
 *  - `sign_signer`   — an external signer, scoped to one submitter. Random
 *    token in `signer_sessions`, minted by the emailed-code verify step.
 *
 * All owner data is scoped by the session user; signer routes are scoped by
 * the submitter the cookie names. Signing links are capability URLs
 * (`/sign/t/<access token>`) but opening one only shows title + masked email —
 * the document itself is behind the emailed 6-digit code.
 *
 * The API mirrors the FastAPI reference app's contract (the Vue frontend was
 * written against it): /users, /templates, /submissions (+adhoc, actions),
 * /sign/token/*, /sign/:id, /files/*.
 */

import { PDFDocument } from 'pdf-lib';
import { stampAndCertifyPdf, PlacedField, SignerInfo } from './core/stamping.js';
import { sendMail, mailConfigured, MailEnv } from './mail.js';
import { R2SignStorage } from './storage/r2.js';
import { convertOfficeToPdfViaGraph, SUPPORTED_OFFICE_FORMATS } from './convert/graph.js';

export interface Env extends MailEnv {
  SIGN_SERVICE: DurableObjectNamespace;
  BASE_URL?: string;
  DOCUMENTS?: any; // R2 bucket binding
  MS_GRAPH_TENANT_ID?: string;
  MS_GRAPH_CLIENT_ID?: string;
  MS_GRAPH_CLIENT_SECRET?: string;
  MS_GRAPH_DRIVE_ID?: string;
  GOOGLE_OAUTH_CLIENT_ID?: string;
  GOOGLE_OAUTH_CLIENT_SECRET?: string;
  MS_OAUTH_CLIENT_ID?: string;
  MS_OAUTH_CLIENT_SECRET?: string;
}

const SESSION_TTL_DAYS = 30;
const SIGNER_TTL_HOURS = 24;
const CODE_TTL_MIN = 15;
const RESEND_GUARD_SEC = 60;
// With R2 the ceiling is generous; without it, PDFs live in DO SQLite rows (2MB hard limit).
const MAX_PDF_BYTES_R2 = 20_000_000;
const MAX_PDF_BYTES_SQLITE = 1_500_000;

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

const json = (data: unknown, status = 200, extra: Record<string, string> = {}) =>
  Response.json(data, { status, headers: { ...corsHeaders, ...extra } });

const newToken = (): string => {
  const b = new Uint8Array(32);
  crypto.getRandomValues(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
};

const sixDigits = (): string => {
  const b = new Uint32Array(1);
  crypto.getRandomValues(b);
  return String(100000 + (b[0] % 900000));
};

const readCookie = (req: Request, name: string): string | undefined => {
  const raw = req.headers.get('cookie') || '';
  for (const part of raw.split(/;\s*/)) {
    const eq = part.indexOf('=');
    if (eq > 0 && part.slice(0, eq) === name) return part.slice(eq + 1);
  }
  return undefined;
};

const setCookie = (name: string, value: string, maxAgeSec: number): string =>
  `${name}=${value}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAgeSec}`;

const maskEmail = (email: string): string => {
  const [local, domain] = email.split('@');
  if (!domain) return email;
  const keep = local.slice(0, Math.min(2, local.length));
  return `${keep}${'*'.repeat(Math.max(1, local.length - keep.length))}@${domain}`;
};

const dataUrlToBytes = (dataUrl: string): Uint8Array | null => {
  const comma = dataUrl.indexOf(',');
  if (comma < 0) return null;
  try {
    const raw = atob(dataUrl.slice(comma + 1));
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return bytes;
  } catch {
    return null;
  }
};

/** Internal submitter status → the frontend's SubmitterStatus. */
const outSubmitterStatus = (s: string): string => (s === 'signed' ? 'completed' : s);

/**
 * The three statuses an envelope never leaves: it has been executed, refused
 * or voided, and every later write is destroying a record rather than making
 * one. `draft` and `pending` are the only statuses a transition may move.
 * spec/0006 §S2.
 */
const isTerminal = (status: unknown): boolean =>
  status === 'completed' || status === 'declined' || status === 'cancelled';

interface UserRow {
  id: string;
  email: string;
  name: string;
  provider: string;
}

export class PumasiSignService implements DurableObject {
  private sql: SqlStorage;

  constructor(private state: DurableObjectState, private env: Env) {
    this.sql = state.storage.sql;
    this.initSchema();
  }

  private initSchema() {
    this.sql.exec(`
      CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        provider TEXT DEFAULT 'email',
        avatar_url TEXT,
        created_at TEXT
      );

      CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT
      );

      CREATE TABLE IF NOT EXISTS signer_sessions (
        token TEXT PRIMARY KEY,
        submitter_id TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT
      );

      CREATE TABLE IF NOT EXISTS recipients (
        id TEXT PRIMARY KEY,
        owner_email TEXT NOT NULL,
        email TEXT NOT NULL,
        name TEXT NOT NULL,
        created_at TEXT,
        UNIQUE(owner_email, email)
      );

      CREATE TABLE IF NOT EXISTS org_branding (
        id TEXT PRIMARY KEY,
        owner_id TEXT UNIQUE NOT NULL,
        company_name TEXT NOT NULL DEFAULT 'Pumasi Sign',
        logo_data_url TEXT,
        primary_color TEXT NOT NULL DEFAULT '#1A56DB',
        welcome_message TEXT DEFAULT 'Please review and sign this document.',
        created_at TEXT,
        updated_at TEXT
      );

      CREATE TABLE IF NOT EXISTS auth_codes (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        code TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT
      );

      CREATE TABLE IF NOT EXISTS templates (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_by TEXT,
        pdf_blob BLOB,
        page_count INTEGER DEFAULT 1,
        fields_json TEXT,
        is_adhoc INTEGER DEFAULT 0,
        is_shared INTEGER DEFAULT 0,
        created_at TEXT,
        archived_at TEXT
      );

      CREATE TABLE IF NOT EXISTS submissions (
        id TEXT PRIMARY KEY,
        public_uid TEXT UNIQUE,
        title TEXT NOT NULL,
        message TEXT,
        created_by TEXT,
        status TEXT DEFAULT 'draft',
        original_pdf_blob BLOB,
        completed_pdf_blob BLOB,
        completed_at TEXT,
        expires_at TEXT,
        created_at TEXT,
        updated_at TEXT
      );

      CREATE TABLE IF NOT EXISTS submitters (
        id TEXT PRIMARY KEY,
        submission_id TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT,
        signing_order INTEGER DEFAULT 1,
        token TEXT UNIQUE NOT NULL,
        status TEXT DEFAULT 'pending',
        is_external INTEGER DEFAULT 1,
        signed_at TEXT,
        ip_address TEXT,
        user_agent TEXT,
        signature_blob BLOB,
        created_at TEXT
      );

      CREATE TABLE IF NOT EXISTS submission_fields (
        id TEXT PRIMARY KEY,
        submission_id TEXT NOT NULL,
        submitter_id TEXT NOT NULL,
        type TEXT NOT NULL,
        page INTEGER NOT NULL,
        x REAL NOT NULL,
        y REAL NOT NULL,
        width REAL NOT NULL,
        height REAL NOT NULL,
        value TEXT
      );

      CREATE TABLE IF NOT EXISTS signatures (
        id TEXT PRIMARY KEY,
        submitter_id TEXT NOT NULL,
        image_blob BLOB,
        created_at TEXT
      );

      CREATE TABLE IF NOT EXISTS audit_events (
        id TEXT PRIMARY KEY,
        submission_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        actor_email TEXT,
        actor_name TEXT,
        ip_address TEXT,
        details_json TEXT,
        created_at TEXT
      );
    `);

    // Columns added after first deploy — each guarded, SQLite has no IF NOT EXISTS for columns.
    const alters = [
      `ALTER TABLE submissions ADD COLUMN page_count INTEGER DEFAULT 1`,
      `ALTER TABLE submissions ADD COLUMN template_id TEXT`,
      `ALTER TABLE submissions ADD COLUMN reminders_enabled INTEGER DEFAULT 1`,
      `ALTER TABLE submissions ADD COLUMN reminder_interval_days INTEGER DEFAULT 3`,
      `ALTER TABLE submissions ADD COLUMN archived_at TEXT`,
      `ALTER TABLE submitters ADD COLUMN recipient_id TEXT`,
      `ALTER TABLE submitters ADD COLUMN is_cc INTEGER DEFAULT 0`,
      `ALTER TABLE submitters ADD COLUMN last_reminded_at TEXT`,
      `ALTER TABLE submitters ADD COLUMN reminder_count INTEGER DEFAULT 0`,
      `ALTER TABLE submission_fields ADD COLUMN required INTEGER DEFAULT 1`,
      `ALTER TABLE submission_fields ADD COLUMN font_size REAL`,
      `ALTER TABLE submission_fields ADD COLUMN options_json TEXT`,
      `ALTER TABLE submission_fields ADD COLUMN default_value TEXT`,
      `ALTER TABLE submission_fields ADD COLUMN field_role TEXT`,
      `ALTER TABLE templates ADD COLUMN roles_json TEXT`,
      `ALTER TABLE submissions ADD COLUMN original_pdf_key TEXT`,
      `ALTER TABLE submissions ADD COLUMN completed_pdf_key TEXT`,
      `ALTER TABLE templates ADD COLUMN pdf_key TEXT`,
    ];
    for (const stmt of alters) {
      try { this.sql.exec(stmt); } catch { /* already applied */ }
    }
  }

  // ── helpers ─────────────────────────────────────────────────────────────

  private one<T = any>(query: string, ...bindings: unknown[]): T | undefined {
    return Array.from(this.sql.exec(query, ...bindings))[0] as T | undefined;
  }

  private all<T = any>(query: string, ...bindings: unknown[]): T[] {
    return Array.from(this.sql.exec(query, ...bindings)) as T[];
  }

  private audit(submissionId: string, eventType: string, actorEmail: string, actorName: string, ip?: string, details?: unknown) {
    this.sql.exec(
      `INSERT INTO audit_events (id, submission_id, event_type, actor_email, actor_name, ip_address, details_json, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      `evt-${crypto.randomUUID().slice(0, 8)}`,
      submissionId, eventType, actorEmail, actorName, ip ?? null,
      details ? JSON.stringify(details) : null,
      new Date().toISOString(),
    );
  }

  /** The owner behind the sign_session cookie, or undefined. */
  private sessionUser(req: Request): UserRow | undefined {
    const token = readCookie(req, 'sign_session');
    if (!token) return undefined;
    const row = this.one(
      `SELECT u.id, u.email, u.name, u.provider FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token = ? AND s.expires_at > ?`,
      token, new Date().toISOString(),
    );
    return row as UserRow | undefined;
  }

  /** The submitter behind the sign_signer cookie, or undefined. */
  private signerSubmitterId(req: Request): string | undefined {
    const token = readCookie(req, 'sign_signer');
    if (!token) return undefined;
    const row = this.one<{ submitter_id: string }>(
      `SELECT submitter_id FROM signer_sessions WHERE token = ? AND expires_at > ?`,
      token, new Date().toISOString(),
    );
    return row?.submitter_id;
  }

  /** May this request act as this submitter? Signer cookie, or an owner session with the same email. */
  private authorizedForSubmitter(req: Request, submitterId: string): boolean {
    if (this.signerSubmitterId(req) === submitterId) return true;
    const user = this.sessionUser(req);
    if (!user) return false;
    const sub = this.one<{ email: string }>(`SELECT email FROM submitters WHERE id = ?`, submitterId);
    return Boolean(sub && sub.email.toLowerCase() === user.email.toLowerCase());
  }

  /** May this request read this submission's documents? The owner, or any of its submitters. */
  private authorizedForSubmission(req: Request, submissionId: string): boolean {
    const sub = this.one<{ created_by: string }>(`SELECT created_by FROM submissions WHERE id = ?`, submissionId);
    if (!sub) return false;
    const user = this.sessionUser(req);
    if (user && user.email.toLowerCase() === String(sub.created_by).toLowerCase()) return true;
    const signerId = this.signerSubmitterId(req);
    if (!signerId) return false;
    const mine = this.one(`SELECT id FROM submitters WHERE id = ? AND submission_id = ?`, signerId, submissionId);
    return Boolean(mine);
  }

  private baseUrl(): string {
    return this.env.BASE_URL || 'https://sign.pumasi.ai';
  }

  // ── document storage: R2 when bound, DO SQLite blobs otherwise ─────────

  private docs(): R2SignStorage | null {
    return this.env.DOCUMENTS ? new R2SignStorage(this.env.DOCUMENTS) : null;
  }

  private maxPdfBytes(): number {
    return this.docs() ? MAX_PDF_BYTES_R2 : MAX_PDF_BYTES_SQLITE;
  }

  /** Store PDF bytes; returns the R2 key, or null when R2 is unbound (caller falls back to a blob column). */
  private async storePdf(prefix: string, id: string, bytes: Uint8Array): Promise<string | null> {
    const store = this.docs();
    if (!store) return null;
    const key = `${prefix}/${id}.pdf`;
    await store.putDocument(key, bytes, 'application/pdf');
    return key;
  }

  /** Read a PDF that may live in R2 (key) or in a legacy blob column. */
  private async loadPdf(key: string | null | undefined, blob: unknown): Promise<Uint8Array | null> {
    if (key) {
      const got = await this.docs()?.getDocument(String(key));
      if (got) return got.data;
    }
    if (blob) return new Uint8Array(blob as ArrayBuffer);
    return null;
  }

  private async graphConfig(): Promise<{ tenantId: string; clientId: string; clientSecret: string; driveId: string } | null> {
    const { MS_GRAPH_TENANT_ID, MS_GRAPH_CLIENT_ID, MS_GRAPH_CLIENT_SECRET, MS_GRAPH_DRIVE_ID } = this.env;
    if (!MS_GRAPH_TENANT_ID || !MS_GRAPH_CLIENT_ID || !MS_GRAPH_CLIENT_SECRET || !MS_GRAPH_DRIVE_ID) return null;
    return { tenantId: MS_GRAPH_TENANT_ID, clientId: MS_GRAPH_CLIENT_ID, clientSecret: MS_GRAPH_CLIENT_SECRET, driveId: MS_GRAPH_DRIVE_ID };
  }

  private async mailOrLog(to: string, subject: string, text: string, html?: string): Promise<boolean> {
    try {
      await sendMail(this.env, { to, subject, text, html });
      return true;
    } catch (err) {
      console.warn(`[mail] send to ${to} failed: ${(err as Error).message}`);
      return false;
    }
  }

  /** The one HTML shell every notification uses — consistent structure helps inbox placement. */
  private mailHtml(heading: string, paragraphs: string[], opts?: { cta?: { label: string; url: string }; code?: string }): string {
    const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const body = paragraphs.map((p) => `<p style="margin:0 0 14px;color:#333f4d;font-size:15px;line-height:1.55">${esc(p)}</p>`).join('');
    const code = opts?.code
      ? `<p style="margin:18px 0;text-align:center"><span style="display:inline-block;background:#f1f5fb;border:1px solid #d8e2f0;border-radius:8px;padding:12px 28px;font-size:28px;letter-spacing:8px;font-weight:700;color:#1a2b3c">${esc(opts.code)}</span></p>`
      : '';
    const cta = opts?.cta
      ? `<p style="margin:22px 0;text-align:center"><a href="${opts.cta.url}" style="background:#1A56DB;color:#ffffff;text-decoration:none;padding:12px 28px;border-radius:8px;font-size:15px;font-weight:600;display:inline-block">${esc(opts.cta.label)}</a></p><p style="margin:0 0 14px;color:#8a97a5;font-size:12px;text-align:center;word-break:break-all">Or paste this link into your browser:<br>${esc(opts.cta.url)}</p>`
      : '';
    return `<!doctype html><html><body style="margin:0;padding:0;background:#f6f8fa">
<div style="max-width:520px;margin:0 auto;padding:32px 16px;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
  <div style="text-align:center;margin-bottom:18px"><span style="font-size:18px;font-weight:700;color:#1A56DB">Pumasi Sign</span></div>
  <div style="background:#ffffff;border:1px solid #e3e8ee;border-radius:12px;padding:28px">
    <h1 style="margin:0 0 16px;font-size:19px;color:#101828">${esc(heading)}</h1>
    ${body}${code}${cta}
  </div>
  <p style="text-align:center;color:#98a2b3;font-size:12px;margin:16px 0 0">Sent by Pumasi Sign · sign.pumasi.ai<br>If you weren't expecting this email, you can safely ignore it.</p>
</div></body></html>`;
  }

  /** Issue a 6-digit code for `key`, or explain why not yet. */
  private issueCode(key: string): { code: string } | { error: string } {
    const now = Date.now();
    const recent = this.one<{ created_at: string }>(
      `SELECT created_at FROM auth_codes WHERE email = ? ORDER BY created_at DESC LIMIT 1`, key,
    );
    if (recent && now - Date.parse(recent.created_at) < RESEND_GUARD_SEC * 1000) {
      return { error: 'A code was just sent. Wait a minute before requesting another.' };
    }
    this.sql.exec(`DELETE FROM auth_codes WHERE email = ? OR expires_at < ?`, key, new Date(now).toISOString());
    const code = sixDigits();
    this.sql.exec(
      `INSERT INTO auth_codes (id, email, code, expires_at, created_at) VALUES (?, ?, ?, ?, ?)`,
      `code-${crypto.randomUUID().slice(0, 8)}`, key, code,
      new Date(now + CODE_TTL_MIN * 60_000).toISOString(), new Date(now).toISOString(),
    );
    return { code };
  }

  private consumeCode(key: string, code: string): boolean {
    const row = this.one<{ id: string }>(
      `SELECT id FROM auth_codes WHERE email = ? AND code = ? AND expires_at > ?`,
      key, code, new Date().toISOString(),
    );
    if (!row) return false;
    this.sql.exec(`DELETE FROM auth_codes WHERE email = ?`, key);
    return true;
  }

  /** Field rows → the frontend's FieldDef shape. Role comes from the stored field_role or the owning submitter. */
  private fieldDefs(submissionId: string): any[] {
    const roleById = new Map(
      this.all<{ id: string; role: string }>(`SELECT id, role FROM submitters WHERE submission_id = ?`, submissionId)
        .map((s) => [s.id, s.role || 'Signer']),
    );
    return this.all(
      `SELECT id, submitter_id, type, page, x, y, width, height, value, required, font_size, options_json, default_value, field_role
         FROM submission_fields WHERE submission_id = ?`, submissionId,
    ).map((f: any) => ({
      id: f.id,
      type: f.type,
      role: f.type === 'label' ? '' : (f.field_role || roleById.get(f.submitter_id) || ''),
      page: f.page,
      x: f.x, y: f.y, w: f.width, h: f.height,
      required: Boolean(f.required),
      default_value: f.default_value ?? null,
      font_size: f.font_size ?? null,
      options: f.options_json ? JSON.parse(f.options_json) : null,
    }));
  }

  private submitterTurn(submitter: { submission_id: string; signing_order: number }): boolean {
    const blocking = this.one<{ n: number }>(
      `SELECT COUNT(*) AS n FROM submitters WHERE submission_id = ? AND signing_order < ? AND status NOT IN ('signed') AND is_cc = 0`,
      submitter.submission_id, submitter.signing_order,
    );
    return (blocking?.n ?? 0) === 0;
  }

  /** Email the pending non-CC signers whose turn it now is. */
  private async inviteCurrentTurn(submissionId: string, onlySubmitterId?: string): Promise<void> {
    const sub = this.one<any>(`SELECT id, title, created_by FROM submissions WHERE id = ?`, submissionId);
    if (!sub) return;
    const sender = this.one<UserRow>(`SELECT id, email, name, provider FROM users WHERE email = ?`, sub.created_by);
    const senderName = sender?.name || sub.created_by;
    const pending = this.all<any>(
      `SELECT id, name, email, token, signing_order FROM submitters
        WHERE submission_id = ? AND status = 'pending' AND is_cc = 0 ORDER BY signing_order ASC`, submissionId,
    );
    if (!pending.length) return;
    const firstOrder = pending[0].signing_order;
    const targets = onlySubmitterId
      ? pending.filter((p) => p.id === onlySubmitterId)
      : pending.filter((p) => p.signing_order === firstOrder);
    for (const s of targets) {
      const link = `${this.baseUrl()}/sign/t/${s.token}`;
      const ok = await this.mailOrLog(
        s.email,
        `${senderName} sent you "${sub.title}" to sign`,
        `Hello ${s.name},\n\n${senderName} has requested your signature on "${sub.title}".\n\nReview and sign here:\n${link}\n\nYou will be asked for a verification code sent to this email address before the document opens.\n\n— Pumasi Sign`,
        this.mailHtml(`${senderName} sent you a document to sign`, [
          `Hello ${s.name},`,
          `${senderName} has requested your signature on "${sub.title}".`,
          `You will be asked for a verification code sent to this email address before the document opens.`,
        ], { cta: { label: 'Review & sign', url: link } }),
      );
      if (ok) {
        this.audit(submissionId, 'invite_sent', s.email, s.name);
        this.sql.exec(
          `UPDATE submitters SET last_reminded_at = ?, reminder_count = reminder_count + 1 WHERE id = ?`,
          new Date().toISOString(), s.id,
        );
      }
    }
  }

  // ── directory: the sender's recipients ─────────────────────────────────

  private userBriefFor(owner: UserRow, email: string, name: string, recipientId?: string) {
    const isOwner = email.toLowerCase() === owner.email.toLowerCase();
    return {
      id: isOwner ? owner.id : (recipientId ?? email),
      email,
      name,
      is_external: !isOwner,
    };
  }

  private directoryUsers(owner: UserRow): any[] {
    const rows = this.all<any>(
      `SELECT id, email, name FROM recipients WHERE owner_email = ? ORDER BY name ASC`, owner.email,
    );
    return [
      { id: owner.id, email: owner.email, name: owner.name, is_admin: true, is_external: false, can_send: true },
      ...rows.map((r) => ({ id: r.id, email: r.email, name: r.name, is_admin: false, is_external: true, can_send: false })),
    ];
  }

  /** Resolve a wizard user_id (owner id or recipient id) to {email, name, recipientId}. */
  private resolveDirectoryUser(owner: UserRow, userId: string): { email: string; name: string; recipientId?: string } | undefined {
    if (userId === owner.id) return { email: owner.email, name: owner.name };
    const r = this.one<any>(`SELECT id, email, name FROM recipients WHERE id = ? AND owner_email = ?`, userId, owner.email);
    if (r) return { email: r.email, name: r.name, recipientId: r.id };
    return undefined;
  }

  // ── outbound shapes ────────────────────────────────────────────────────

  private templateOut(owner: UserRow, t: any): any {
    const fields = t.fields_json ? JSON.parse(t.fields_json) : [];
    const roles = t.roles_json
      ? JSON.parse(t.roles_json)
      : [...new Set(fields.map((f: any) => f.role).filter((r: string) => r))];
    return {
      id: t.id,
      name: t.name,
      page_count: t.page_count || 1,
      fields,
      roles,
      created_at: t.created_at,
      shared: Boolean(t.is_shared),
      owner: { id: owner.id, name: owner.name, email: owner.email, is_external: false },
    };
  }

  private submissionOut(viewer: UserRow, sub: any): any {
    const submitters = this.all<any>(
      `SELECT id, name, email, role, signing_order, status, signed_at, is_cc, recipient_id, last_reminded_at, reminder_count
         FROM submitters WHERE submission_id = ? ORDER BY signing_order ASC, created_at ASC`, sub.id,
    );
    const mine = submitters.find((s) => s.email.toLowerCase() === viewer.email.toLowerCase());
    const tpl = sub.template_id
      ? this.one<any>(`SELECT id, name, is_adhoc FROM templates WHERE id = ?`, sub.template_id)
      : undefined;
    const sender = this.one<UserRow>(`SELECT id, email, name, provider FROM users WHERE email = ?`, sub.created_by);
    return {
      id: sub.id,
      public_uid: sub.public_uid,
      title: sub.title,
      message: sub.message || null,
      status: sub.status,
      created_at: sub.created_at,
      completed_at: sub.completed_at || null,
      expires_at: sub.expires_at || null,
      reminders_enabled: Boolean(sub.reminders_enabled ?? 1),
      reminder_interval_days: sub.reminder_interval_days ?? 3,
      template: tpl
        ? { id: tpl.id, name: tpl.name, is_adhoc: Boolean(tpl.is_adhoc) }
        : { id: sub.id, name: sub.title, is_adhoc: true },
      sender: sender
        ? { id: sender.id, name: sender.name, email: sender.email, is_external: false }
        : { id: sub.created_by, name: sub.created_by, email: sub.created_by, is_external: false },
      submitters: submitters.map((s) => ({
        id: s.id,
        user: {
          // The wizard reloads drafts by directory user id — the owner's is their account id.
          id: s.recipient_id || (sender && s.email.toLowerCase() === sender.email.toLowerCase() ? sender.id : s.email),
          name: s.name, email: s.email,
          is_external: s.email.toLowerCase() !== sub.created_by.toLowerCase(),
        },
        role: s.role || 'Signer',
        status: outSubmitterStatus(s.status),
        signed_at: s.signed_at || null,
        email_status: null,
        last_reminded_at: s.last_reminded_at || null,
        reminder_count: s.reminder_count ?? 0,
        order_index: s.signing_order ?? 0,
        is_cc: Boolean(s.is_cc),
      })),
      my_submitter_id: mine?.id ?? null,
      archived_by_me: Boolean(sub.archived_at),
      has_certificate: Boolean(sub.completed_pdf_key || sub.completed_pdf_blob),
    };
  }

  /** Create submitter rows + resolved field rows for a new submission. */
  private createSubmittersAndFields(
    owner: UserRow, submissionId: string,
    signers: Array<{ role: string; user_id: string; order?: number; is_cc?: boolean }>,
    fields: any[], now: string,
  ): { error?: string } {
    const byRole = new Map<string, string>();
    for (const s of signers) {
      const resolved = this.resolveDirectoryUser(owner, String(s.user_id));
      if (!resolved) return { error: `Unknown recipient: ${s.user_id}` };
      const subId = `subtr-${crypto.randomUUID().slice(0, 8)}`;
      this.sql.exec(
        `INSERT INTO submitters (id, submission_id, name, email, role, signing_order, token, status, is_cc, recipient_id, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)`,
        subId, submissionId, resolved.name, resolved.email.toLowerCase(),
        s.role || 'Signer', Number(s.order) || 0, newToken(),
        s.is_cc ? 1 : 0, resolved.recipientId ?? null, now,
      );
      if (!s.is_cc) byRole.set(s.role, subId);
    }
    for (const f of fields || []) {
      const ownerSubmitter = f.type === 'label' ? '' : (byRole.get(f.role) ?? '');
      if (f.type !== 'label' && !ownerSubmitter) continue; // field for an unassigned role
      this.sql.exec(
        `INSERT INTO submission_fields (id, submission_id, submitter_id, type, page, x, y, width, height, value, required, font_size, options_json, default_value, field_role)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        `fld-${crypto.randomUUID().slice(0, 8)}`,
        submissionId, ownerSubmitter, f.type, Number(f.page) || 0,
        Number(f.x) || 0, Number(f.y) || 0, Number(f.w ?? f.width) || 0, Number(f.h ?? f.height) || 0,
        '', f.required === false ? 0 : 1, f.font_size ?? null,
        f.options ? JSON.stringify(f.options) : null, f.default_value ?? null, f.role ?? null,
      );
    }
    return {};
  }

  // ── request dispatch ────────────────────────────────────────────────────

  async fetch(req: Request): Promise<Response> {
    const url = new URL(req.url);
    const path = url.pathname;
    const method = req.method;
    try {
      return await this.route(req, url, path, method);
    } catch (err) {
      console.warn(`[sign] ${method} ${path} failed: ${(err as Error).message}`);
      return json({ error: 'Internal error' }, 500);
    }
  }

  /** Find-or-create the account for a verified email, and mint a session cookie header. */
  private establishSession(email: string, name: string, provider: string): { user: UserRow; cookie: string } {
    let user = this.one<UserRow>(`SELECT id, email, name, provider FROM users WHERE email = ?`, email);
    const now = new Date().toISOString();
    if (!user) {
      const userId = `usr-${crypto.randomUUID().slice(0, 8)}`;
      this.sql.exec(
        `INSERT INTO users (id, email, name, provider, created_at) VALUES (?, ?, ?, ?, ?)`,
        userId, email, name, provider, now,
      );
      this.sql.exec(
        `INSERT INTO org_branding (id, owner_id, company_name, primary_color, created_at, updated_at)
         VALUES (?, ?, ?, '#1A56DB', ?, ?)`,
        `org-${crypto.randomUUID().slice(0, 8)}`, userId, `${name}'s Workspace`, now, now,
      );
      user = { id: userId, email, name, provider };
    }
    const token = newToken();
    this.sql.exec(
      `INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)`,
      token, user.id, new Date(Date.now() + SESSION_TTL_DAYS * 86400_000).toISOString(), now,
    );
    return { user, cookie: setCookie('sign_session', token, SESSION_TTL_DAYS * 86400) };
  }

  private oauthProvider(name: string): { authUrl: string; tokenUrl: string; clientId?: string; clientSecret?: string } | null {
    if (name === 'google') {
      return {
        authUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
        tokenUrl: 'https://oauth2.googleapis.com/token',
        clientId: this.env.GOOGLE_OAUTH_CLIENT_ID,
        clientSecret: this.env.GOOGLE_OAUTH_CLIENT_SECRET,
      };
    }
    if (name === 'microsoft') {
      return {
        authUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
        tokenUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
        clientId: this.env.MS_OAUTH_CLIENT_ID,
        clientSecret: this.env.MS_OAUTH_CLIENT_SECRET,
      };
    }
    return null;
  }

  private async route(req: Request, url: URL, path: string, method: string): Promise<Response> {
    // ── OAuth sign-in (Google / Microsoft) ────────────────────────────────
    const oauthMatch = path.match(/^\/api\/auth\/oauth\/(google|microsoft)(\/callback)?$/);
    if (oauthMatch && method === 'GET') {
      const provider = this.oauthProvider(oauthMatch[1]);
      if (!provider?.clientId || !provider.clientSecret) {
        return json({ error: `${oauthMatch[1]} sign-in is not configured on this deployment.` }, 503);
      }
      const redirectUri = `${this.baseUrl()}/api/auth/oauth/${oauthMatch[1]}/callback`;

      if (!oauthMatch[2]) {
        const rawNext = url.searchParams.get('next') || '/';
        const next = rawNext.startsWith('/') && !rawNext.startsWith('//') ? rawNext : '/';
        const state = newToken().slice(0, 32);
        this.sql.exec(
          `INSERT INTO auth_codes (id, email, code, expires_at, created_at) VALUES (?, ?, ?, ?, ?)`,
          `oauth-${crypto.randomUUID().slice(0, 8)}`, `oauth:${state}`, JSON.stringify({ next }),
          new Date(Date.now() + 10 * 60_000).toISOString(), new Date().toISOString(),
        );
        const q = new URLSearchParams({
          client_id: provider.clientId,
          redirect_uri: redirectUri,
          response_type: 'code',
          scope: 'openid email profile',
          state,
          prompt: 'select_account',
        });
        return new Response(null, { status: 302, headers: { Location: `${provider.authUrl}?${q}` } });
      }

      // callback
      const state = url.searchParams.get('state') || '';
      const code = url.searchParams.get('code') || '';
      const row = this.one<any>(
        `SELECT code FROM auth_codes WHERE email = ? AND expires_at > ?`,
        `oauth:${state}`, new Date().toISOString(),
      );
      if (!row || !code) {
        return new Response(null, { status: 302, headers: { Location: '/login' } });
      }
      this.sql.exec(`DELETE FROM auth_codes WHERE email = ?`, `oauth:${state}`);
      const next = (() => { try { return JSON.parse(String(row.code)).next || '/'; } catch { return '/'; } })();

      const tokenRes = await fetch(provider.tokenUrl, {
        method: 'POST',
        headers: { 'content-type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          code,
          client_id: provider.clientId,
          client_secret: provider.clientSecret,
          redirect_uri: redirectUri,
          grant_type: 'authorization_code',
        }),
      });
      if (!tokenRes.ok) {
        console.warn(`[oauth] ${oauthMatch[1]} exchange failed: ${tokenRes.status} ${(await tokenRes.text()).slice(0, 200)}`);
        return new Response(null, { status: 302, headers: { Location: '/login' } });
      }
      const tok = (await tokenRes.json()) as { id_token?: string };
      // The id_token came directly from the provider's token endpoint over TLS —
      // its payload is trustworthy without local signature verification.
      const seg = tok.id_token?.split('.')[1];
      let claims: any = {};
      try {
        claims = JSON.parse(atob((seg || '').replace(/-/g, '+').replace(/_/g, '/')));
      } catch { /* fall through to the check below */ }
      const email = String(claims.email || claims.preferred_username || '').trim().toLowerCase();
      if (!email || !email.includes('@') || claims.email_verified === false) {
        return new Response(null, { status: 302, headers: { Location: '/login' } });
      }
      const name = String(claims.name || email.split('@')[0]).slice(0, 120);
      const { cookie } = this.establishSession(email, name, oauthMatch[1]);
      return new Response(null, { status: 302, headers: { Location: next, 'Set-Cookie': cookie } });
    }

    // ── auth ──────────────────────────────────────────────────────────────
    if (path === '/api/auth/login/request' && method === 'POST') {
      const body: any = await req.json();
      const email = String(body.email || '').trim().toLowerCase();
      if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
        return json({ error: 'Please enter a valid email address' }, 400);
      }
      if (!mailConfigured(this.env)) {
        return json({ error: 'Email delivery is not configured on this deployment.' }, 503);
      }
      const issued = this.issueCode(email);
      if ('error' in issued) return json({ error: issued.error }, 429);
      const ok = await this.mailOrLog(
        email,
        'Your Pumasi Sign verification code',
        `Your verification code is: ${issued.code}\n\nIt expires in ${CODE_TTL_MIN} minutes. If you did not request this, ignore this email.\n\n— Pumasi Sign`,
        this.mailHtml('Your verification code', [
          `Enter this code to sign in. It expires in ${CODE_TTL_MIN} minutes.`,
        ], { code: issued.code }),
      );
      if (!ok) return json({ error: 'Could not send the verification email. Try again shortly.' }, 502);
      return json({ ok: true, email, message: 'Verification code sent. Check your email.' });
    }

    if (path === '/api/auth/login/verify' && method === 'POST') {
      const body: any = await req.json();
      const email = String(body.email || '').trim().toLowerCase();
      const code = String(body.code || '').trim();
      if (!this.consumeCode(email, code)) {
        return json({ error: 'Invalid or expired verification code' }, 401);
      }

      const displayName = String(body.name || email.split('@')[0].replace(/[._]/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()));
      const { user, cookie } = this.establishSession(email, displayName, 'email');
      const branding = this.one(`SELECT company_name, logo_data_url, primary_color, welcome_message FROM org_branding WHERE owner_id = ?`, user.id);
      return json(
        {
          ok: true,
          user: { id: user.id, email: user.email, name: user.name, is_admin: true, is_external: false, can_send: true },
          branding: branding || { company_name: 'Pumasi Sign', primary_color: '#1A56DB' },
        },
        200,
        { 'Set-Cookie': cookie },
      );
    }

    if (path === '/api/auth/me' && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      return json({ id: user.id, email: user.email, name: user.name, is_admin: true, is_external: false, can_send: true });
    }

    if (path === '/api/auth/logout' && method === 'POST') {
      const token = readCookie(req, 'sign_session');
      if (token) this.sql.exec(`DELETE FROM sessions WHERE token = ?`, token);
      return json({ ok: true }, 200, { 'Set-Cookie': setCookie('sign_session', '', 0) });
    }

    // ── owner: branding ───────────────────────────────────────────────────
    if (path === '/api/branding' && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const branding = this.one(`SELECT company_name, logo_data_url, primary_color, welcome_message FROM org_branding WHERE owner_id = ?`, user.id);
      return json(branding || { company_name: 'Pumasi Sign', primary_color: '#1A56DB', welcome_message: null, logo_data_url: null });
    }

    if (path === '/api/branding' && method === 'PUT') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const body: any = await req.json();
      const now = new Date().toISOString();
      const existing = this.one<{ id: string }>(`SELECT id FROM org_branding WHERE owner_id = ?`, user.id);
      if (existing) {
        this.sql.exec(
          `UPDATE org_branding SET company_name = ?, logo_data_url = ?, primary_color = ?, welcome_message = ?, updated_at = ? WHERE owner_id = ?`,
          String(body.company_name || 'Pumasi Sign').slice(0, 120),
          body.logo_data_url ?? null,
          String(body.primary_color || '#1A56DB').slice(0, 20),
          body.welcome_message != null ? String(body.welcome_message).slice(0, 500) : null,
          now, user.id,
        );
      } else {
        this.sql.exec(
          `INSERT INTO org_branding (id, owner_id, company_name, logo_data_url, primary_color, welcome_message, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
          `org-${crypto.randomUUID().slice(0, 8)}`, user.id,
          String(body.company_name || 'Pumasi Sign').slice(0, 120),
          body.logo_data_url ?? null,
          String(body.primary_color || '#1A56DB').slice(0, 20),
          body.welcome_message != null ? String(body.welcome_message).slice(0, 500) : null,
          now, now,
        );
      }
      const branding = this.one(`SELECT company_name, logo_data_url, primary_color, welcome_message FROM org_branding WHERE owner_id = ?`, user.id);
      return json(branding);
    }

    // ── owner: recipient directory (the wizard's "users") ─────────────────
    if (path === '/api/users' && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      return json(this.directoryUsers(user));
    }

    if (path === '/api/users' && method === 'POST') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const body: any = await req.json();
      const email = String(body.email || '').trim().toLowerCase();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return json({ error: 'A valid email is required' }, 400);
      if (email === user.email.toLowerCase()) {
        return json({ id: user.id, email: user.email, name: user.name, is_admin: true, is_external: false, can_send: true });
      }
      const existing = this.one<any>(`SELECT id, email, name FROM recipients WHERE owner_email = ? AND email = ?`, user.email, email);
      if (existing) {
        return json({ id: existing.id, email: existing.email, name: existing.name, is_admin: false, is_external: true, can_send: false });
      }
      const id = `rcp-${crypto.randomUUID().slice(0, 8)}`;
      const name = String(body.name || email.split('@')[0]).slice(0, 120);
      this.sql.exec(
        `INSERT INTO recipients (id, owner_email, email, name, created_at) VALUES (?, ?, ?, ?, ?)`,
        id, user.email, email, name, new Date().toISOString(),
      );
      return json({ id, email, name, is_admin: false, is_external: true, can_send: false }, 201);
    }

    // ── owner: templates ──────────────────────────────────────────────────
    if (path === '/api/templates' && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const rows = this.all<any>(
        `SELECT id, name, page_count, fields_json, roles_json, is_shared, is_adhoc, created_at FROM templates
          WHERE created_by = ? AND archived_at IS NULL AND is_adhoc = 0 ORDER BY created_at DESC`, user.email,
      );
      return json(rows.map((t) => this.templateOut(user, t)));
    }

    if (path === '/api/templates' && method === 'POST') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const body: any = await req.json();
      const id = `tpl-${crypto.randomUUID().slice(0, 8)}`;
      const pdfBytes = body.pdfBase64 ? dataUrlToBytes(`,${body.pdfBase64}`) : null;
      const pdfKey = pdfBytes ? await this.storePdf('templates', id, pdfBytes) : null;
      this.sql.exec(
        `INSERT INTO templates (id, name, created_by, pdf_blob, pdf_key, page_count, fields_json, roles_json, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        id, String(body.name || 'Untitled Template'), user.email, pdfKey ? null : pdfBytes, pdfKey,
        Number(body.pageCount ?? body.page_count) || 1, JSON.stringify(body.fields || []),
        JSON.stringify(body.roles || []), new Date().toISOString(),
      );
      const t = this.one<any>(`SELECT id, name, page_count, fields_json, roles_json, is_shared, created_at FROM templates WHERE id = ?`, id);
      return json(this.templateOut(user, t), 201);
    }

    const tplMatch = path.match(/^\/api\/templates\/([A-Za-z0-9_-]+)$/);
    if (tplMatch && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const t = this.one<any>(
        `SELECT id, name, page_count, fields_json, roles_json, is_shared, created_at FROM templates WHERE id = ? AND created_by = ?`,
        tplMatch[1], user.email,
      );
      if (!t) return json({ error: 'Template not found' }, 404);
      return json(this.templateOut(user, t));
    }

    if (path.match(/^\/api\/files\/template-pdf\/[A-Za-z0-9_-]+$/) && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const id = path.split('/').pop()!;
      const t = this.one<any>(`SELECT name, pdf_blob, pdf_key FROM templates WHERE id = ? AND created_by = ?`, id, user.email);
      const bytes = t ? await this.loadPdf(t.pdf_key, t.pdf_blob) : null;
      if (!bytes) return json({ error: 'Not found' }, 404);
      return new Response(bytes.buffer as ArrayBuffer, {
        headers: { 'Content-Type': 'application/pdf', ...corsHeaders },
      });
    }

    // ── owner: merge picked files into the one PDF fields get placed on ───
    if (path === '/api/submissions/adhoc/merged-document' && method === 'POST') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const form = await req.formData();
      const files = form.getAll('files').filter((f): f is File => f instanceof File);
      if (!files.length) return json({ error: 'No files uploaded' }, 400);

      const merged = await PDFDocument.create();
      for (const file of files) {
        const bytes = new Uint8Array(await file.arrayBuffer());
        const lower = file.name.toLowerCase();
        const ext = lower.split('.').pop() || '';
        if (lower.endsWith('.pdf')) {
          const src = await PDFDocument.load(bytes).catch(() => null);
          if (!src) return json({ error: `"${file.name}" is not a readable PDF.` }, 422);
          const pages = await merged.copyPages(src, src.getPageIndices());
          for (const p of pages) merged.addPage(p);
        } else if (/\.(png|jpe?g)$/.test(lower)) {
          const img = lower.endsWith('.png') ? await merged.embedPng(bytes) : await merged.embedJpg(bytes);
          const page = merged.addPage([612, 792]);
          const scale = Math.min(552 / img.width, 712 / img.height, 1);
          page.drawImage(img, {
            x: (612 - img.width * scale) / 2,
            y: (792 - img.height * scale) / 2,
            width: img.width * scale,
            height: img.height * scale,
          });
        } else if (SUPPORTED_OFFICE_FORMATS.has(ext)) {
          const cfg = await this.graphConfig();
          if (!cfg) {
            return json({ error: `"${file.name}": Office conversion is not configured on this deployment. Convert to PDF first.` }, 422);
          }
          const pdfBytes = await convertOfficeToPdfViaGraph(bytes, ext, cfg);
          if (!pdfBytes) {
            return json({ error: `"${file.name}" could not be converted. Check the file opens in Office, or convert it to PDF yourself.` }, 422);
          }
          const src = await PDFDocument.load(pdfBytes).catch(() => null);
          if (!src) return json({ error: `"${file.name}": conversion produced an unreadable PDF.` }, 422);
          const pages = await merged.copyPages(src, src.getPageIndices());
          for (const p of pages) merged.addPage(p);
        } else {
          return json({ error: `"${file.name}": PDF, Office documents (Word, PowerPoint, Excel), PNG, and JPG are supported.` }, 422);
        }
      }
      const out = await merged.save();
      if (out.length > this.maxPdfBytes()) {
        return json({ error: `The combined document is too large (${Math.round(this.maxPdfBytes() / 1_000_000)}MB limit).` }, 413);
      }
      return new Response(out.buffer as ArrayBuffer, {
        headers: { 'Content-Type': 'application/pdf', ...corsHeaders },
      });
    }

    // ── owner: create one-off envelope from an uploaded PDF ───────────────
    if (path === '/api/submissions/adhoc' && method === 'POST') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const form = await req.formData();
      const file = form.get('file');
      if (!(file instanceof File)) return json({ error: 'A document file is required' }, 400);
      const pdfBytes = new Uint8Array(await file.arrayBuffer());
      if (pdfBytes.length > this.maxPdfBytes()) {
        return json({ error: `The document is too large (${Math.round(this.maxPdfBytes() / 1_000_000)}MB limit).` }, 413);
      }
      const doc = await PDFDocument.load(pdfBytes).catch(() => null);
      if (!doc) return json({ error: 'The uploaded file is not a readable PDF.' }, 422);

      const title = String(form.get('title') || 'Untitled Agreement').slice(0, 200);
      const message = form.get('message') != null ? String(form.get('message')).slice(0, 2000) : null;
      const expiresAt = form.get('expires_at') ? String(form.get('expires_at')) : null;
      const remindersEnabled = String(form.get('reminders_enabled') ?? 'true') === 'true';
      const reminderInterval = Number(form.get('reminder_interval_days')) || 3;
      const isDraft = String(form.get('draft') ?? 'false') === 'true';
      let signers: any[] = [];
      let fields: any[] = [];
      try {
        signers = JSON.parse(String(form.get('signers_json') || '[]'));
        fields = JSON.parse(String(form.get('fields_json') || '[]'));
      } catch {
        return json({ error: 'signers_json / fields_json is not valid JSON' }, 400);
      }
      if (!signers.some((s) => !s.is_cc)) return json({ error: 'At least one signer is required' }, 400);

      const now = new Date().toISOString();
      const pageCount = doc.getPageCount();

      // The backing adhoc template lets a draft reload into the wizard later.
      const tplId = `tpl-${crypto.randomUUID().slice(0, 8)}`;
      const tplKey = await this.storePdf('templates', tplId, pdfBytes);
      this.sql.exec(
        `INSERT INTO templates (id, name, created_by, pdf_blob, pdf_key, page_count, fields_json, roles_json, is_adhoc, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)`,
        tplId, title, user.email, tplKey ? null : pdfBytes, tplKey, pageCount, JSON.stringify(fields),
        JSON.stringify([...new Set(fields.map((f: any) => f.role).filter(Boolean))]), now,
      );

      const id = `sub-${crypto.randomUUID().slice(0, 10)}`;
      const pdfKey = await this.storePdf('originals', id, pdfBytes);
      this.sql.exec(
        `INSERT INTO submissions (id, public_uid, title, message, created_by, status, original_pdf_blob, original_pdf_key, page_count, template_id,
                                  reminders_enabled, reminder_interval_days, expires_at, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        id, crypto.randomUUID().slice(0, 8), title, message, user.email,
        isDraft ? 'draft' : 'pending', pdfKey ? null : pdfBytes, pdfKey, pageCount, tplId,
        remindersEnabled ? 1 : 0, reminderInterval, expiresAt, now, now,
      );

      const created = this.createSubmittersAndFields(user, id, signers, fields, now);
      if (created.error) return json({ error: created.error }, 400);

      this.audit(id, isDraft ? 'created' : 'sent', user.email, user.name);
      if (!isDraft) await this.inviteCurrentTurn(id);
      const sub = this.one<any>(`SELECT * FROM submissions WHERE id = ?`, id);
      return json(this.submissionOut(user, sub), 201);
    }

    // ── owner: create envelope from a saved template ──────────────────────
    if (path === '/api/submissions' && method === 'POST') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const body: any = await req.json();
      const tpl = this.one<any>(
        `SELECT id, name, pdf_blob, pdf_key, page_count, fields_json FROM templates WHERE id = ? AND created_by = ?`,
        String(body.template_id || ''), user.email,
      );
      if (!tpl) return json({ error: 'Template not found' }, 404);
      const signers: any[] = body.signers || [];
      if (!signers.some((s) => !s.is_cc)) return json({ error: 'At least one signer is required' }, 400);

      const now = new Date().toISOString();
      const isDraft = Boolean(body.draft);
      const id = `sub-${crypto.randomUUID().slice(0, 10)}`;
      const tplPdf = await this.loadPdf(tpl.pdf_key, tpl.pdf_blob);
      const pdfKey = tplPdf ? await this.storePdf('originals', id, tplPdf) : null;
      this.sql.exec(
        `INSERT INTO submissions (id, public_uid, title, message, created_by, status, original_pdf_blob, original_pdf_key, page_count, template_id,
                                  reminders_enabled, reminder_interval_days, expires_at, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        id, crypto.randomUUID().slice(0, 8),
        String(body.title || tpl.name).slice(0, 200), body.message ?? null, user.email,
        isDraft ? 'draft' : 'pending', pdfKey ? null : tplPdf, pdfKey, tpl.page_count || 1, tpl.id,
        body.reminders_enabled === false ? 0 : 1, Number(body.reminder_interval_days) || 3,
        body.expires_at ?? null, now, now,
      );

      const fields = tpl.fields_json ? JSON.parse(tpl.fields_json) : [];
      const created = this.createSubmittersAndFields(user, id, signers, fields, now);
      if (created.error) return json({ error: created.error }, 400);

      this.audit(id, isDraft ? 'created' : 'sent', user.email, user.name);
      if (!isDraft) await this.inviteCurrentTurn(id);
      const sub = this.one<any>(`SELECT * FROM submissions WHERE id = ?`, id);
      return json(this.submissionOut(user, sub), 201);
    }

    // ── owner: envelope lists ─────────────────────────────────────────────
    if (path === '/api/submissions' && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const mine = url.searchParams.get('mine') || 'sent';
      let subs: any[];
      if (mine === 'sign') {
        subs = this.all<any>(
          `SELECT s.* FROM submissions s
            WHERE s.id IN (SELECT submission_id FROM submitters WHERE email = ? AND is_cc = 0)
              AND s.created_by != ?
            ORDER BY s.created_at DESC`, user.email.toLowerCase(), user.email,
        );
      } else {
        subs = this.all<any>(
          `SELECT * FROM submissions WHERE created_by = ? ORDER BY created_at DESC`, user.email,
        );
      }
      return json(subs.map((s) => this.submissionOut(user, s)));
    }

    // ── owner: envelope detail + actions ──────────────────────────────────
    const subMatch = path.match(/^\/api\/submissions\/([A-Za-z0-9_-]+)(?:\/(.+))?$/);
    if (subMatch) {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const id = subMatch[1];
      const action = subMatch[2];
      const sub = this.one<any>(`SELECT * FROM submissions WHERE (id = ? OR public_uid = ?) AND created_by = ?`, id, id, user.email);
      if (!sub) return json({ error: 'Submission not found' }, 404);
      const now = new Date().toISOString();

      if (method === 'GET' && !action) return json(this.submissionOut(user, sub));

      if (method === 'GET' && action === 'events') {
        return json(this.all<any>(
          `SELECT id, event_type, actor_email, actor_name, details_json, created_at FROM audit_events WHERE submission_id = ? ORDER BY created_at ASC`,
          sub.id,
        ).map((e) => ({
          id: e.id,
          event: e.event_type === 'invite_sent' ? 'sent'
            : e.event_type === 'signer_verified' ? 'opened'
            : e.event_type === 'created_draft' ? 'created'
            : e.event_type,
          created_at: e.created_at,
          actor: e.actor_email
            ? { id: e.actor_email, name: e.actor_name || e.actor_email, email: e.actor_email, is_external: e.actor_email.toLowerCase() !== user.email.toLowerCase() }
            : null,
          detail: e.details_json ? JSON.parse(e.details_json) : null,
        })));
      }

      if (method === 'GET' && action === 'form-data') {
        const submitters = new Map(this.all<any>(
          `SELECT id, name, email, role, recipient_id, signed_at FROM submitters WHERE submission_id = ?`, sub.id,
        ).map((s) => [s.id, s]));
        const entries = this.all<any>(
          `SELECT id, submitter_id, type, page, value FROM submission_fields WHERE submission_id = ? AND type != 'label'`, sub.id,
        ).flatMap((f) => {
          const s = submitters.get(f.submitter_id);
          if (!s) return [];
          return [{
            submitter_id: s.id,
            recipient: { id: s.recipient_id || s.email, name: s.name, email: s.email, is_external: true },
            role: s.role || '',
            field_id: f.id,
            field_type: f.type,
            page: f.page,
            value: f.type === 'checkbox' ? f.value === 'true' : (f.value || null),
            signed_at: s.signed_at || null,
          }];
        });
        return json({ submission_id: sub.id, public_uid: sub.public_uid, title: sub.title, status: sub.status, entries });
      }

      if (method === 'GET' && action === 'pdf') {
        const pdfData = (await this.loadPdf(sub.completed_pdf_key, sub.completed_pdf_blob))
          ?? (await this.loadPdf(sub.original_pdf_key, sub.original_pdf_blob));
        if (!pdfData) return json({ error: 'PDF content not available' }, 404);
        return new Response(pdfData.buffer as ArrayBuffer, {
          headers: {
            'Content-Type': 'application/pdf',
            'Content-Disposition': `inline; filename="${String(sub.title).replace(/[^a-zA-Z0-9_-]/g, '_')}.pdf"`,
            ...corsHeaders,
          },
        });
      }

      if (method === 'PATCH' && !action) {
        const body: any = await req.json();
        this.sql.exec(
          `UPDATE submissions SET title = ?, message = ?, updated_at = ? WHERE id = ?`,
          String(body.title ?? sub.title).slice(0, 200),
          body.message != null ? String(body.message).slice(0, 2000) : null,
          now, sub.id,
        );
        this.audit(sub.id, 'corrected', user.email, user.name);
        return json(this.submissionOut(user, this.one<any>(`SELECT * FROM submissions WHERE id = ?`, sub.id)));
      }

      if (method === 'DELETE' && !action) {
        if (sub.status !== 'draft') return json({ error: 'Only drafts can be deleted' }, 409);
        for (const key of [sub.original_pdf_key, sub.completed_pdf_key]) {
          if (key) await this.docs()?.deleteDocument(String(key)).catch(() => {});
        }
        if (sub.template_id) {
          const t = this.one<any>(`SELECT pdf_key FROM templates WHERE id = ? AND is_adhoc = 1`, sub.template_id);
          if (t?.pdf_key) await this.docs()?.deleteDocument(String(t.pdf_key)).catch(() => {});
        }
        this.sql.exec(`DELETE FROM submission_fields WHERE submission_id = ?`, sub.id);
        this.sql.exec(`DELETE FROM submitters WHERE submission_id = ?`, sub.id);
        this.sql.exec(`DELETE FROM audit_events WHERE submission_id = ?`, sub.id);
        this.sql.exec(`DELETE FROM submissions WHERE id = ?`, sub.id);
        if (sub.template_id) this.sql.exec(`DELETE FROM templates WHERE id = ? AND is_adhoc = 1`, sub.template_id);
        return json({ ok: true });
      }

      if (method === 'POST' && (action === 'send' || action === 'remind')) {
        if (sub.status === 'draft') {
          this.sql.exec(`UPDATE submissions SET status = 'pending', updated_at = ? WHERE id = ?`, now, sub.id);
          this.audit(sub.id, 'sent', user.email, user.name);
        } else if (sub.status !== 'pending') {
          return json({ error: 'This envelope is not awaiting signatures' }, 409);
        } else {
          this.audit(sub.id, 'reminded', user.email, user.name);
        }
        await this.inviteCurrentTurn(sub.id);
        return json({ ok: true });
      }

      if (method === 'POST' && action === 'cancel') {
        // A finished envelope is not voidable: the row would come to say
        // `cancelled` about an agreement whose certificate says `completed`.
        // spec/0006 §S2a; refusal is this route's neighbours' idiom (:1231).
        if (isTerminal(sub.status)) return json({ error: 'This envelope is already closed' }, 409);
        const body: any = await req.json().catch(() => ({}));
        this.sql.exec(`UPDATE submissions SET status = 'cancelled', updated_at = ? WHERE id = ?`, now, sub.id);
        this.audit(sub.id, 'cancelled', user.email, user.name, undefined, body.reason ? { reason: String(body.reason) } : undefined);
        return json({ ok: true });
      }

      if (method === 'POST' && action === 'archive') {
        this.sql.exec(`UPDATE submissions SET archived_at = ? WHERE id = ?`, now, sub.id);
        return json({ ok: true });
      }

      if (method === 'POST' && action === 'unarchive') {
        this.sql.exec(`UPDATE submissions SET archived_at = NULL WHERE id = ?`, sub.id);
        return json({ ok: true });
      }

      if (method === 'POST' && action === 'copy') {
        const newId = `sub-${crypto.randomUUID().slice(0, 10)}`;
        // Each envelope owns its bytes — a shared R2 key would be deleted with either copy.
        const srcPdf = await this.loadPdf(sub.original_pdf_key, sub.original_pdf_blob);
        const newKey = srcPdf ? await this.storePdf('originals', newId, srcPdf) : null;
        this.sql.exec(
          `INSERT INTO submissions (id, public_uid, title, message, created_by, status, original_pdf_blob, original_pdf_key, page_count, template_id,
                                    reminders_enabled, reminder_interval_days, expires_at, created_at, updated_at)
           SELECT ?, ?, title, message, created_by, 'draft', ?, ?, page_count, template_id,
                  reminders_enabled, reminder_interval_days, NULL, ?, ? FROM submissions WHERE id = ?`,
          newId, crypto.randomUUID().slice(0, 8), newKey ? null : srcPdf, newKey, now, now, sub.id,
        );
        const idMap = new Map<string, string>();
        for (const s of this.all<any>(`SELECT * FROM submitters WHERE submission_id = ?`, sub.id)) {
          const nid = `subtr-${crypto.randomUUID().slice(0, 8)}`;
          idMap.set(s.id, nid);
          this.sql.exec(
            `INSERT INTO submitters (id, submission_id, name, email, role, signing_order, token, status, is_cc, recipient_id, created_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)`,
            nid, newId, s.name, s.email, s.role, s.signing_order, newToken(), s.is_cc ?? 0, s.recipient_id ?? null, now,
          );
        }
        for (const f of this.all<any>(`SELECT * FROM submission_fields WHERE submission_id = ?`, sub.id)) {
          this.sql.exec(
            `INSERT INTO submission_fields (id, submission_id, submitter_id, type, page, x, y, width, height, value, required, font_size, options_json, default_value, field_role)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?)`,
            `fld-${crypto.randomUUID().slice(0, 8)}`, newId, idMap.get(f.submitter_id) ?? '',
            f.type, f.page, f.x, f.y, f.width, f.height,
            f.required ?? 1, f.font_size ?? null, f.options_json ?? null, f.default_value ?? null, f.field_role ?? null,
          );
        }
        this.audit(newId, 'created', user.email, user.name, undefined, { copied_from: sub.id });
        return json(this.submissionOut(user, this.one<any>(`SELECT * FROM submissions WHERE id = ?`, newId)), 201);
      }

      const resendMatch = action?.match(/^submitters\/([A-Za-z0-9_-]+)\/resend$/);
      if (method === 'POST' && resendMatch) {
        const target = this.one<any>(`SELECT id, status FROM submitters WHERE id = ? AND submission_id = ?`, resendMatch[1], sub.id);
        if (!target) return json({ error: 'No such signer' }, 404);
        if (target.status !== 'pending') return json({ error: 'That signer has already finished' }, 409);
        await this.inviteCurrentTurn(sub.id, target.id);
        return json({ ok: true });
      }

      if (method === 'POST' && (action === 'save-as-template' || action === 'retry-completion' || action === 'replace-document')) {
        return json({ error: 'Not implemented yet in this edition' }, 501);
      }

      return json({ error: 'Endpoint not found' }, 404);
    }

    // ── signer: token landing / code / verify ─────────────────────────────
    const tokenMatch = path.match(/^\/api\/sign\/token\/([A-Za-z0-9_-]+)(?:\/(request-code|verify))?$/);
    if (tokenMatch) {
      const accessUid = tokenMatch[1];
      const sub = this.one<any>(
        `SELECT id, submission_id, name, email, role, status, signing_order FROM submitters WHERE token = ?`, accessUid,
      );
      if (!sub) return json({ error: 'This signing link is not valid.' }, 404);
      const submission = this.one<any>(
        `SELECT id, title, message, status, created_by, expires_at FROM submissions WHERE id = ?`, sub.submission_id,
      );
      if (!submission) return json({ error: 'This signing link is not valid.' }, 404);

      const tokenStatus =
        submission.status === 'cancelled' ? 'cancelled'
        : sub.status === 'declined' || submission.status === 'declined' ? 'declined'
        : submission.status === 'completed' ? 'completed'
        : sub.status === 'signed' ? 'already_signed'
        : 'open';

      if (!tokenMatch[2] && method === 'GET') {
        const sender = this.one<UserRow>(`SELECT id, email, name, provider FROM users WHERE email = ?`, submission.created_by);
        return json({
          status: tokenStatus,
          title: submission.title,
          sender_name: sender?.name || submission.created_by,
          masked_email: maskEmail(sub.email),
        });
      }

      if (tokenMatch[2] === 'request-code' && method === 'POST') {
        if (tokenStatus === 'cancelled' || tokenStatus === 'declined') {
          return json({ error: 'This envelope is no longer active.' }, 410);
        }
        if (!mailConfigured(this.env)) return json({ error: 'Email delivery is not configured.' }, 503);
        const issued = this.issueCode(`signer:${sub.id}`);
        if ('error' in issued) return json({ error: issued.error }, 429);
        const ok = await this.mailOrLog(
          sub.email,
          `Your verification code for "${submission.title}"`,
          `Your verification code is: ${issued.code}\n\nEnter it on the signing page to open the document. It expires in ${CODE_TTL_MIN} minutes.\n\n— Pumasi Sign`,
          this.mailHtml('Your verification code', [
            `Enter this code on the signing page to open "${submission.title}". It expires in ${CODE_TTL_MIN} minutes.`,
          ], { code: issued.code }),
        );
        if (!ok) return json({ error: 'Could not send the verification email. Try again shortly.' }, 502);
        return json({ ok: true });
      }

      if (tokenMatch[2] === 'verify' && method === 'POST') {
        const body: any = await req.json();
        if (!this.consumeCode(`signer:${sub.id}`, String(body.code || '').trim())) {
          return json({ error: 'Invalid or expired verification code' }, 401);
        }
        const token = newToken();
        this.sql.exec(
          `INSERT INTO signer_sessions (token, submitter_id, expires_at, created_at) VALUES (?, ?, ?, ?)`,
          token, sub.id, new Date(Date.now() + SIGNER_TTL_HOURS * 3600_000).toISOString(), new Date().toISOString(),
        );
        this.audit(sub.submission_id, 'signer_verified', sub.email, sub.name, req.headers.get('cf-connecting-ip') || undefined);
        return json({ submitter_id: sub.id }, 200, {
          'Set-Cookie': setCookie('sign_signer', token, SIGNER_TTL_HOURS * 3600),
        });
      }
    }

    // ── signer: the signing session itself ────────────────────────────────
    const signMatch = path.match(/^\/api\/sign\/([A-Za-z0-9_-]+)(?:\/(signature|complete|decline))?$/);
    if (signMatch && signMatch[1] !== 'token') {
      const submitterId = signMatch[1];
      if (!this.authorizedForSubmitter(req, submitterId)) {
        return json({ error: 'Not authorized for this signing session' }, 401);
      }
      const me = this.one<any>(
        `SELECT id, submission_id, name, email, role, status, signing_order, is_cc FROM submitters WHERE id = ?`, submitterId,
      );
      if (!me) return json({ error: 'Unknown signer' }, 404);
      const submission = this.one<any>(
        `SELECT id, title, message, status, created_by, expires_at, page_count FROM submissions WHERE id = ?`, me.submission_id,
      );
      if (!submission) return json({ error: 'Unknown submission' }, 404);

      if (!signMatch[2] && method === 'GET') {
        const fields = this.fieldDefs(submission.id);
        const myFieldIds = new Set(this.all<{ id: string }>(
          `SELECT id FROM submission_fields WHERE submission_id = ? AND submitter_id = ?`, submission.id, me.id,
        ).map((r) => r.id));
        const roleNames: Record<string, string> = {};
        for (const s of this.all<any>(`SELECT name, role FROM submitters WHERE submission_id = ? AND is_cc = 0`, submission.id)) {
          roleNames[s.role || 'Signer'] = s.name;
        }
        const savedSig = this.one<{ id: string }>(
          `SELECT id FROM signatures WHERE submitter_id = ? ORDER BY created_at DESC LIMIT 1`, me.id,
        );
        return json({
          submission: {
            id: submission.id,
            title: submission.title,
            message: submission.message,
            status: submission.status,
            expires_at: submission.expires_at,
          },
          template: { id: submission.id, page_count: submission.page_count || 1, fields },
          my_fields: fields.filter((f: any) => myFieldIds.has(f.id)).map((f: any) => f.id),
          my_status: outSubmitterStatus(me.status),
          my_turn: this.submitterTurn(me),
          saved_signature_id: savedSig?.id ?? null,
          role_names: roleNames,
          my_name: me.name,
        });
      }

      if (signMatch[2] === 'signature' && method === 'POST') {
        const body: any = await req.json();
        const bytes = typeof body.image === 'string' ? dataUrlToBytes(body.image) : null;
        if (!bytes || bytes.length > 512 * 1024) {
          return json({ error: 'Signature image is missing or too large' }, 400);
        }
        const sigId = `sig-${crypto.randomUUID().slice(0, 8)}`;
        this.sql.exec(
          `INSERT INTO signatures (id, submitter_id, image_blob, created_at) VALUES (?, ?, ?, ?)`,
          sigId, me.id, bytes, new Date().toISOString(),
        );
        return json({ signature_id: sigId });
      }

      if (signMatch[2] === 'complete' && method === 'POST') {
        // `completed` belongs here too: without it a CC recipient -- who never
        // held the envelope open (:1479's `AND is_cc = 0`) -- signs afterwards,
        // runs finalize() a second time and writes a second `completed` audit
        // event, re-stamping the executed PDF where one is present.
        // spec/0006 §S2b.
        if (isTerminal(submission.status)) {
          return json({ error: 'This envelope is no longer active' }, 410);
        }
        if (me.status === 'signed') return json({ error: 'Already signed' }, 409);
        if (!this.submitterTurn(me)) return json({ error: 'Earlier signers have not finished yet' }, 409);

        const body: any = await req.json();
        const values: Record<string, unknown> = body.values || {};
        const now = new Date().toISOString();
        const clientIp = req.headers.get('cf-connecting-ip') || '0.0.0.0';
        const userAgent = req.headers.get('user-agent') || '';

        const myFields = this.all<any>(
          `SELECT id, type, required FROM submission_fields WHERE submission_id = ? AND submitter_id = ?`,
          submission.id, me.id,
        );

        let signatureBytes: Uint8Array | null = null;
        for (const f of myFields) {
          const v = values[f.id];
          if (f.type === 'signature' || f.type === 'initials') {
            if (v == null) {
              if (f.required) return json({ error: 'A required signature is missing' }, 400);
              continue;
            }
            const sig = this.one<any>(`SELECT id, image_blob FROM signatures WHERE id = ? AND submitter_id = ?`, String(v), me.id);
            if (!sig) return json({ error: 'Unknown signature reference' }, 400);
            if (f.type === 'signature' && sig.image_blob) signatureBytes = new Uint8Array(sig.image_blob);
            this.sql.exec(`UPDATE submission_fields SET value = ? WHERE id = ?`, String(v), f.id);
          } else if (f.type === 'checkbox') {
            this.sql.exec(`UPDATE submission_fields SET value = ? WHERE id = ?`, v === true || v === 'true' ? 'true' : 'false', f.id);
          } else if (v != null) {
            this.sql.exec(`UPDATE submission_fields SET value = ? WHERE id = ?`, String(v).slice(0, 2000), f.id);
          } else if (f.required && f.type !== 'label') {
            return json({ error: 'A required field is missing' }, 400);
          }
        }

        this.sql.exec(
          `UPDATE submitters SET status = 'signed', signed_at = ?, ip_address = ?, user_agent = ?, signature_blob = ? WHERE id = ?`,
          now, clientIp, userAgent, signatureBytes, me.id,
        );
        this.audit(submission.id, 'signed', me.email, me.name, clientIp, { userAgent });

        const remaining = this.one<{ n: number }>(
          `SELECT COUNT(*) AS n FROM submitters WHERE submission_id = ? AND status != 'signed' AND is_cc = 0`, submission.id,
        );

        if ((remaining?.n ?? 0) === 0) {
          await this.finalize(submission.id, now);
        } else {
          await this.inviteCurrentTurn(submission.id);
        }
        return json({ ok: true, status: (remaining?.n ?? 0) === 0 ? 'completed' : 'signed' });
      }

      if (signMatch[2] === 'decline' && method === 'POST') {
        // The three guards `complete` carries five lines up. Without them the
        // same envelope refuses a signature and accepts a decline in the same
        // breath. 409 rather than complete's 410 is spec/0006 §S2c's stated
        // asymmetry, not an oversight.
        if (isTerminal(submission.status)) return json({ error: 'This envelope is no longer active' }, 409);
        if (me.status === 'signed') return json({ error: 'Already signed' }, 409);
        if (!this.submitterTurn(me)) return json({ error: 'Earlier signers have not finished yet' }, 409);

        const body: any = await req.json().catch(() => ({}));
        const now = new Date().toISOString();
        this.sql.exec(`UPDATE submitters SET status = 'declined', signed_at = ? WHERE id = ?`, now, me.id);
        this.sql.exec(`UPDATE submissions SET status = 'declined', updated_at = ? WHERE id = ?`, now, submission.id);
        this.audit(submission.id, 'declined', me.email, me.name, undefined, { reason: String(body.reason || '') });
        await this.mailOrLog(
          submission.created_by,
          `"${submission.title}" was declined`,
          `${me.name} (${me.email}) declined to sign "${submission.title}".${body.reason ? `\n\nReason: ${String(body.reason)}` : ''}\n\n— Pumasi Sign`,
        );
        return json({ ok: true });
      }
    }

    // ── files (owner or that envelope's signer) ───────────────────────────
    const fileMatch = path.match(/^\/api\/files\/(document-preview|signed-pdf|signature)\/([A-Za-z0-9_-]+)$/);
    if (fileMatch && method === 'GET') {
      const kind = fileMatch[1];
      const targetId = fileMatch[2];

      if (kind === 'signature') {
        const sig = this.one<any>(`SELECT submitter_id, image_blob FROM signatures WHERE id = ?`, targetId);
        if (!sig || !this.authorizedForSubmitter(req, sig.submitter_id)) return json({ error: 'Not found' }, 404);
        return new Response(sig.image_blob, { headers: { 'Content-Type': 'image/png', ...corsHeaders } });
      }

      if (!this.authorizedForSubmission(req, targetId)) return json({ error: 'Not found' }, 404);
      const row = this.one<any>(`SELECT title, original_pdf_blob, original_pdf_key, completed_pdf_blob, completed_pdf_key FROM submissions WHERE id = ?`, targetId);
      if (!row) return json({ error: 'Not found' }, 404);
      const pdf = kind === 'signed-pdf'
        ? await this.loadPdf(row.completed_pdf_key, row.completed_pdf_blob)
        : await this.loadPdf(row.original_pdf_key, row.original_pdf_blob);
      if (!pdf) return json({ error: 'Not available' }, 404);
      return new Response(pdf.buffer as ArrayBuffer, {
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': `${kind === 'signed-pdf' ? 'attachment' : 'inline'}; filename="${String(row.title).replace(/[^a-zA-Z0-9_-]/g, '_')}.pdf"`,
          ...corsHeaders,
        },
      });
    }

    return json({ error: 'Endpoint not found' }, 404);
  }

  /** All signed: stamp, certify, store, notify everyone (CCs included). */
  private async finalize(submissionId: string, now: string): Promise<void> {
    const sub = this.one<any>(
      `SELECT id, public_uid, title, created_by, original_pdf_blob, original_pdf_key FROM submissions WHERE id = ?`, submissionId,
    );
    if (!sub) return;
    const originalPdf = await this.loadPdf(sub.original_pdf_key, sub.original_pdf_blob);

    const allSubmitters: SignerInfo[] = this.all<any>(
      `SELECT id, name, email, role, signed_at, ip_address, user_agent, signature_blob FROM submitters WHERE submission_id = ? AND is_cc = 0`,
      submissionId,
    ).map((s: any) => ({
      id: s.id, name: s.name, email: s.email, role: s.role,
      signedAt: s.signed_at, ipAddress: s.ip_address, userAgent: s.user_agent,
      signatureImage: s.signature_blob ? new Uint8Array(s.signature_blob) : undefined,
    }));

    const typeMap: Record<string, PlacedField['type']> = {
      signature: 'signature', initials: 'initial', initial: 'initial',
      name: 'name', date: 'date', text: 'text', checkbox: 'checkbox',
      dropdown: 'text', radio: 'text', label: 'text',
    };
    const allFields: PlacedField[] = this.all<any>(
      `SELECT id, submitter_id, type, page, x, y, width, height, value, default_value FROM submission_fields WHERE submission_id = ?`,
      submissionId,
    ).map((f: any) => ({
      id: f.id, signerId: f.submitter_id,
      type: typeMap[f.type] ?? 'text',
      // The web contract is 0-based pages; stamping's PlacedField is 1-based.
      page: f.page + 1, x: f.x, y: f.y, width: f.width, height: f.height,
      value: f.type === 'label' ? (f.default_value ?? f.value ?? '') : (f.value ?? ''),
    }));

    if (originalPdf) {
      const stampRes = await stampAndCertifyPdf({
        originalPdfBytes: originalPdf,
        fields: allFields,
        signers: allSubmitters,
        envelopeUid: sub.public_uid,
        documentTitle: sub.title,
        completedAt: now,
      });
      const completedKey = await this.storePdf('completed', submissionId, stampRes.stampedPdfBytes);
      this.sql.exec(
        `UPDATE submissions SET status = 'completed', completed_at = ?, completed_pdf_blob = ?, completed_pdf_key = ?, updated_at = ? WHERE id = ?`,
        now, completedKey ? null : stampRes.stampedPdfBytes, completedKey, now, submissionId,
      );
      this.audit(submissionId, 'completed', 'system@pumasi.ai', 'Pumasi Sign Engine', undefined, {
        originalHash: stampRes.originalHash, completedHash: stampRes.completedHash,
      });
    } else {
      this.sql.exec(
        `UPDATE submissions SET status = 'completed', completed_at = ?, updated_at = ? WHERE id = ?`,
        now, now, submissionId,
      );
      this.audit(submissionId, 'completed', 'system@pumasi.ai', 'Pumasi Sign Engine');
    }

    await this.mailOrLog(
      sub.created_by,
      `"${sub.title}" is fully signed`,
      `Everyone has signed "${sub.title}".\n\nDownload the executed document from your dashboard:\n${this.baseUrl()}/envelopes/${sub.id}\n\n— Pumasi Sign`,
      this.mailHtml('Everyone has signed', [
        `"${sub.title}" is complete. The executed document with its signature certificate is ready.`,
      ], { cta: { label: 'Open the envelope', url: `${this.baseUrl()}/envelopes/${sub.id}` } }),
    );
    for (const s of this.all<any>(`SELECT name, email, token FROM submitters WHERE submission_id = ?`, submissionId)) {
      await this.mailOrLog(
        s.email,
        `"${sub.title}" is fully signed`,
        `Hello ${s.name},\n\nEveryone has signed "${sub.title}". You can retrieve the executed document any time:\n${this.baseUrl()}/sign/t/${s.token}\n\n— Pumasi Sign`,
        this.mailHtml('Everyone has signed', [
          `Hello ${s.name},`,
          `Everyone has signed "${sub.title}". You can retrieve the executed document any time.`,
        ], { cta: { label: 'Get the signed document', url: `${this.baseUrl()}/sign/t/${s.token}` } }),
      );
    }
  }
}
