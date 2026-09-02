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

import { PDFDocument, StandardFonts, rgb } from 'pdf-lib';
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

/** Public, non-enumerable identifier printed on executed documents. */
const newEnvelopeUid = (): string => crypto.randomUUID().toUpperCase();
const MAX_DOCUMENT_PAGES = 500;
const CONSENT_VERSION = 'pumasi-esign-consent-v1';
const CONSENT_TEXT = 'I agree to use electronic records and signatures for this envelope and intend my electronic signature to be legally binding like a handwritten signature.';

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

const attachmentExtension = (contentType: string): string =>
  contentType === 'application/pdf' ? 'pdf' : contentType === 'image/png' ? 'png' : 'jpg';

/**
 * Turn an untrusted multipart filename into a safe evidence/display name.
 * The extension is derived from bytes already inspected by the caller, never
 * from the browser-supplied MIME type. A conflicting extension is refused
 * instead of silently making `invoice.pdf.exe` look harmless in one screen
 * and executable in another downstream system.
 */
const safeAttachmentFilename = (rawName: string, contentType: string): { filename?: string; error?: string } => {
  const expected = attachmentExtension(contentType);
  const normalized = String(rawName || '')
    .normalize('NFKC')
    .replace(/[\u0000-\u001f\u007f]/g, '')
    .replace(/[\\/:*?"<>|]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^\.+/, '');
  if (!normalized) return { filename: `attachment.${expected}` };
  const dot = normalized.lastIndexOf('.');
  if (dot >= 0) {
    const supplied = normalized.slice(dot + 1).toLowerCase();
    const allowed = contentType === 'image/jpeg' ? new Set(['jpg', 'jpeg']) : new Set([expected]);
    if (!allowed.has(supplied)) {
      return { error: `The attachment filename must end in .${expected}${contentType === 'image/jpeg' ? ' or .jpeg' : ''} to match its contents` };
    }
  }
  const stem = (dot >= 0 ? normalized.slice(0, dot) : normalized).trim().replace(/[. ]+$/g, '') || 'attachment';
  return { filename: `${stem.slice(0, 240)}.${expected}` };
};

/** Internal submitter status → the frontend's SubmitterStatus. */
const outSubmitterStatus = (s: string): string => (s === 'signed' ? 'completed' : s);

/**
 * The four statuses an envelope never leaves: it has been executed, refused,
 * voided, or its deadline passed — and every later write is destroying a
 * record rather than making one. `draft` and `pending` are the only statuses a
 * transition may move. spec/0006 §S2; `expired` added by spec/0007 §S0.4.
 *
 * `expired` belongs here for the same reason as the other three and it is not
 * a fifth kind of thing: no further transition improves the record. A sender
 * whose envelope lapsed is not stuck — `POST /{id}/copy` (:1269) makes a fresh
 * draft and clears its deadline (:1278).
 */
const isTerminal = (status: unknown): boolean =>
  status === 'completed' || status === 'declined' || status === 'cancelled' || status === 'expired';

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

      CREATE TABLE IF NOT EXISTS archive_recipients (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        email TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(owner_id, email)
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

      CREATE TABLE IF NOT EXISTS template_shares (
        id TEXT PRIMARY KEY,
        template_id TEXT NOT NULL,
        recipient_email TEXT NOT NULL,
        shared_by TEXT NOT NULL,
        permission TEXT NOT NULL DEFAULT 'use',
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        accepted_at TEXT,
        revoked_at TEXT,
        UNIQUE(template_id, recipient_email)
      );

      CREATE INDEX IF NOT EXISTS idx_template_shares_recipient
        ON template_shares(recipient_email, status);

      CREATE TABLE IF NOT EXISTS team_members (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'member',
        status TEXT NOT NULL DEFAULT 'pending',
        invited_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        accepted_at TEXT,
        revoked_at TEXT,
        UNIQUE(owner_id, email)
      );

      CREATE INDEX IF NOT EXISTS idx_team_members_email ON team_members(email, status);

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

      CREATE TABLE IF NOT EXISTS attachments (
        id TEXT PRIMARY KEY,
        submitter_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        content_type TEXT NOT NULL,
        size INTEGER NOT NULL,
        data_blob BLOB,
        data_key TEXT,
        created_at TEXT
      );

      CREATE TABLE IF NOT EXISTS submission_documents (
        id TEXT PRIMARY KEY,
        submission_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        position INTEGER NOT NULL,
        page_count INTEGER NOT NULL,
        page_start INTEGER NOT NULL,
        pdf_blob BLOB,
        pdf_key TEXT,
        created_at TEXT
      );

      CREATE TABLE IF NOT EXISTS rate_limit_events (
        id TEXT PRIMARY KEY,
        bucket_key TEXT NOT NULL,
        occurred_at INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_rate_limit_bucket_time ON rate_limit_events(bucket_key, occurred_at);

      CREATE TABLE IF NOT EXISTS signer_consents (
        id TEXT PRIMARY KEY,
        submission_id TEXT NOT NULL,
        submitter_id TEXT NOT NULL UNIQUE,
        disclosure_version TEXT NOT NULL,
        disclosure_text TEXT NOT NULL,
        accepted_at TEXT NOT NULL,
        ip_address TEXT,
        user_agent TEXT,
        reviewed_document_hash TEXT NOT NULL,
        document_manifest_json TEXT NOT NULL
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
      `ALTER TABLE submissions ADD COLUMN certificate_pdf_blob BLOB`,
      `ALTER TABLE submissions ADD COLUMN certificate_pdf_key TEXT`,
      `ALTER TABLE submissions ADD COLUMN original_hash TEXT`,
      `ALTER TABLE submissions ADD COLUMN completed_hash TEXT`,
      `ALTER TABLE submissions ADD COLUMN certificate_hash TEXT`,
      `ALTER TABLE submission_documents ADD COLUMN sha256 TEXT`,
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

  private async sha256(bytes: Uint8Array): Promise<string> {
    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer));
    return Array.from(digest, (byte) => byte.toString(16).padStart(2, '0')).join('');
  }

  private async graphConfig(): Promise<{ tenantId: string; clientId: string; clientSecret: string; driveId: string } | null> {
    const { MS_GRAPH_TENANT_ID, MS_GRAPH_CLIENT_ID, MS_GRAPH_CLIENT_SECRET, MS_GRAPH_DRIVE_ID } = this.env;
    if (!MS_GRAPH_TENANT_ID || !MS_GRAPH_CLIENT_ID || !MS_GRAPH_CLIENT_SECRET || !MS_GRAPH_DRIVE_ID) return null;
    return { tenantId: MS_GRAPH_TENANT_ID, clientId: MS_GRAPH_CLIENT_ID, clientSecret: MS_GRAPH_CLIENT_SECRET, driveId: MS_GRAPH_DRIVE_ID };
  }

  /** Normalize one supported upload into the stable PDF used by templates. */
  private async uploadAsPdf(file: File): Promise<{ bytes?: Uint8Array; pageCount?: number; error?: string }> {
    if (file.size > this.maxPdfBytes()) {
      return { error: `The source file exceeds the ${Math.round(this.maxPdfBytes() / 1_000_000)}MB limit.` };
    }
    const input = new Uint8Array(await file.arrayBuffer());
    const lower = file.name.toLowerCase();
    const ext = lower.split('.').pop() || '';
    let bytes: Uint8Array;
    if (lower.endsWith('.pdf')) {
      bytes = input;
    } else if (/\.(png|jpe?g)$/.test(lower)) {
      const doc = await PDFDocument.create();
      const img = lower.endsWith('.png') ? await doc.embedPng(input) : await doc.embedJpg(input);
      const page = doc.addPage([612, 792]);
      const scale = Math.min(552 / img.width, 712 / img.height, 1);
      page.drawImage(img, {
        x: (612 - img.width * scale) / 2,
        y: (792 - img.height * scale) / 2,
        width: img.width * scale,
        height: img.height * scale,
      });
      bytes = await doc.save();
    } else if (ext === 'txt' || ext === 'csv') {
      // Text is rendered locally so this useful baseline does not depend on
      // Microsoft Graph. Standard PDF fonts are WinAnsi; unsupported Unicode
      // code points are made explicit rather than crashing conversion.
      let text = new TextDecoder('utf-8', { fatal: false }).decode(input)
        .replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n').replace(/\t/g, '    ');
      text = text.replace(/[^\x20-\x7E\n]/g, '?');
      const doc = await PDFDocument.create();
      const font = await doc.embedFont(StandardFonts.Courier);
      const fontSize = 9;
      const lineHeight = 12;
      const maxColumns = ext === 'csv' ? 105 : 95;
      const lines: string[] = [];
      for (const sourceLine of text.split('\n')) {
        if (!sourceLine.length) { lines.push(''); continue; }
        for (let offset = 0; offset < sourceLine.length; offset += maxColumns) {
          lines.push(sourceLine.slice(offset, offset + maxColumns));
        }
      }
      const linesPerPage = 58;
      for (let offset = 0; offset < Math.max(lines.length, 1); offset += linesPerPage) {
        const page = doc.addPage([612, 792]);
        lines.slice(offset, offset + linesPerPage).forEach((line, index) => {
          page.drawText(line, { x: 36, y: 756 - index * lineHeight, size: fontSize, font, color: rgb(0, 0, 0) });
        });
      }
      bytes = await doc.save();
    } else if (SUPPORTED_OFFICE_FORMATS.has(ext)) {
      const cfg = await this.graphConfig();
      if (!cfg) return { error: 'Office conversion is not configured. Convert the file to PDF first.' };
      const converted = await convertOfficeToPdfViaGraph(input, ext, cfg);
      if (!converted) return { error: 'The Office document could not be converted. Convert it to PDF first.' };
      bytes = converted;
    } else {
      return { error: 'This document format is not supported.' };
    }
    if (bytes.length > this.maxPdfBytes()) return { error: `The document exceeds the ${Math.round(this.maxPdfBytes() / 1_000_000)}MB limit.` };
    const parsed = await PDFDocument.load(bytes).catch(() => null);
    if (!parsed || parsed.getPageCount() === 0) return { error: 'The uploaded document is not a readable PDF.' };
    if (parsed.getPageCount() > MAX_DOCUMENT_PAGES) return { error: `The document exceeds the ${MAX_DOCUMENT_PAGES}-page limit.` };
    return { bytes, pageCount: parsed.getPageCount() };
  }

  /** Normalize files independently, then build the ordered rendition fields reference. */
  private async prepareDocuments(files: File[]): Promise<{
    documents?: { id: string; filename: string; position: number; pageCount: number; pageStart: number; bytes: Uint8Array }[];
    merged?: Uint8Array;
    error?: string;
  }> {
    const sourceBytes = files.reduce((sum, file) => sum + file.size, 0);
    if (sourceBytes > this.maxPdfBytes()) return { error: `The source files exceed the ${Math.round(this.maxPdfBytes() / 1_000_000)}MB combined limit.` };
    const documents: { id: string; filename: string; position: number; pageCount: number; pageStart: number; bytes: Uint8Array }[] = [];
    const merged = await PDFDocument.create();
    let pageStart = 0;
    for (const [position, file] of files.entries()) {
      const normalized = await this.uploadAsPdf(file);
      if (!normalized.bytes || !normalized.pageCount) return { error: `"${file.name}": ${normalized.error || 'could not be prepared.'}` };
      const source = await PDFDocument.load(normalized.bytes);
      const pages = await merged.copyPages(source, source.getPageIndices());
      for (const page of pages) merged.addPage(page);
      documents.push({
        id: `doc-${crypto.randomUUID().slice(0, 10)}`,
        filename: file.name.slice(0, 255),
        position,
        pageCount: normalized.pageCount,
        pageStart,
        bytes: normalized.bytes,
      });
      pageStart += normalized.pageCount;
      if (pageStart > MAX_DOCUMENT_PAGES) return { error: `The combined documents exceed the ${MAX_DOCUMENT_PAGES}-page limit.` };
    }
    const bytes = await merged.save();
    if (bytes.length > this.maxPdfBytes()) return { error: `The combined documents exceed the ${Math.round(this.maxPdfBytes() / 1_000_000)}MB limit.` };
    return { documents, merged: bytes };
  }

  private async persistSubmissionDocuments(submissionId: string, documents: NonNullable<Awaited<ReturnType<PumasiSignService['prepareDocuments']>>['documents']>, now: string) {
    for (const document of documents) {
      const key = await this.storePdf(`submission-documents/${submissionId}`, document.id, document.bytes);
      this.sql.exec(
        `INSERT INTO submission_documents (id, submission_id, filename, position, page_count, page_start, pdf_blob, pdf_key, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        document.id, submissionId, document.filename, document.position, document.pageCount, document.pageStart,
        key ? null : document.bytes, key, now,
      );
      this.sql.exec(`UPDATE submission_documents SET sha256 = ? WHERE id = ?`, await this.sha256(document.bytes), document.id);
    }
  }

  private async mailOrLog(
    to: string,
    subject: string,
    text: string,
    html?: string,
    attachments?: Array<{ filename: string; contentType: string; bytes: Uint8Array }>,
  ): Promise<boolean> {
    try {
      await sendMail(this.env, { to, subject, text, html, attachments });
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

  private async sendTeamInvitation(email: string, inviter: UserRow, workspaceName: string): Promise<void> {
    const url = `${this.env.BASE_URL || 'https://sign.pumasi.ai'}/login?next=${encodeURIComponent('/dashboard')}`;
    await this.mailOrLog(
      email,
      `${inviter.name} invited you to Pumasi Sign`,
      `${inviter.name} (${inviter.email}) invited you to join ${workspaceName} in Pumasi Sign. Team membership does not give access to anyone else's envelopes or templates.\n\nAccept invitation: ${url}`,
      this.mailHtml(`${inviter.name} invited you to join their team`, [
        `Join ${workspaceName} to create and send your own agreements. Membership does not expose anyone else's envelopes or templates.`,
        `Sign in with ${email} to accept this invitation.`,
      ], { cta: { label: 'Accept invitation', url } }),
    );
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

  /** Persistent sliding-window limiter shared by every request hitting this DO. */
  private async rateLimited(scope: string, identifiers: string[], limit: number, windowSeconds: number): Promise<number | null> {
    const now = Date.now();
    const cutoff = now - windowSeconds * 1000;
    this.sql.exec(`DELETE FROM rate_limit_events WHERE occurred_at < ?`, now - 86_400_000);
    const buckets: string[] = [];
    for (const identifier of identifiers.filter(Boolean)) {
      const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`${scope}:${identifier}`)));
      buckets.push(`${scope}:${Array.from(digest, (byte) => byte.toString(16).padStart(2, '0')).join('')}`);
    }
    let retryAfter = 0;
    for (const bucket of buckets) {
      const rows = this.all<{ occurred_at: number }>(
        `SELECT occurred_at FROM rate_limit_events WHERE bucket_key = ? AND occurred_at >= ? ORDER BY occurred_at ASC`, bucket, cutoff,
      );
      if (rows.length >= limit) retryAfter = Math.max(retryAfter, Math.ceil((rows[0].occurred_at + windowSeconds * 1000 - now) / 1000));
    }
    if (retryAfter > 0) return retryAfter;
    for (const bucket of buckets) {
      this.sql.exec(
        `INSERT INTO rate_limit_events (id, bucket_key, occurred_at) VALUES (?, ?, ?)`,
        `rate-${crypto.randomUUID().slice(0, 10)}`, bucket, now,
      );
    }
    return null;
  }

  private clientIp(req: Request): string {
    return req.headers.get('cf-connecting-ip') || req.headers.get('x-forwarded-for')?.split(',')[0].trim() || 'unknown';
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

  private templateOut(viewer: UserRow, t: any): any {
    const fields = t.fields_json ? JSON.parse(t.fields_json) : [];
    const roles = t.roles_json
      ? JSON.parse(t.roles_json)
      : [...new Set(fields.map((f: any) => f.role).filter((r: string) => r))];
    const creator = this.one<UserRow>(`SELECT id, email, name, provider FROM users WHERE email = ?`, t.created_by) ?? viewer;
    return {
      id: t.id,
      name: t.name,
      page_count: t.page_count || 1,
      fields,
      roles,
      created_at: t.created_at,
      shared: t.created_by === viewer.email
        ? Boolean(this.one(`SELECT 1 FROM template_shares WHERE template_id = ? AND status != 'revoked' LIMIT 1`, t.id))
        : true,
      access: t.created_by === viewer.email ? 'owner' : 'use',
      owner: { id: creator.id, name: creator.name, email: creator.email, is_external: false },
      archived_at: t.archived_at || null,
    };
  }

  private canUseTemplate(t: any, user: UserRow): boolean {
    if (t.created_by === user.email) return true;
    return Boolean(this.one(
      `SELECT 1 FROM template_shares WHERE template_id = ? AND recipient_email = ? AND status != 'revoked'`,
      t.id, user.email.toLowerCase(),
    ));
  }

  private workspaceFor(user: UserRow): { ownerId: string; role: 'owner' | 'admin' | 'member' } {
    const membership = this.one<{ owner_id: string; role: 'admin' | 'member' }>(
      `SELECT owner_id, role FROM team_members WHERE email = ? AND status = 'accepted' ORDER BY accepted_at DESC LIMIT 1`,
      user.email.toLowerCase(),
    );
    return membership ? { ownerId: membership.owner_id, role: membership.role } : { ownerId: user.id, role: 'owner' };
  }

  private accountUserOut(user: UserRow): any {
    const workspace = this.workspaceFor(user);
    return {
      id: user.id, email: user.email, name: user.name,
      is_admin: workspace.role === 'owner' || workspace.role === 'admin',
      is_external: false, can_send: true, role: workspace.role, provider: user.provider,
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
      has_certificate: Boolean(sub.certificate_pdf_key || sub.certificate_pdf_blob),
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

  /**
   * Flip every envelope past its deadline to `expired`. Returns how many.
   *
   * The SPA asks the sender for the deadline, refuses one in the past, shows
   * it back, and tells them in words what it means. This is the only thing in
   * the product that makes any of that true. spec/0007 §S2d.
   *
   * Four decisions live in the statement below:
   *
   * - `status = 'pending'` ONLY. A draft was never sent to anybody; expiring
   *   one takes a document away from a sender still writing it, and
   *   EnvelopeDetailView.vue:777 tells that sender to set a new date, advice
   *   that stays true only if drafts do not expire.
   * - `LIKE '____-__-__T%'`. `expires_at` is TEXT and the comparison is
   *   lexicographic, which is exact for the ISO-8601 UTC strings the wizard
   *   sends (SendView.vue:79). The multipart create path (:1032) stores
   *   whatever a client sent without validating it, so the shape is pinned
   *   here: a malformed value is left alone rather than expired on an
   *   accidental string comparison.
   * - No LIMIT. A bounded sweep leaves rows unexpired with nothing saying so.
   *   This is one shard holding the whole product; if that ever stops being
   *   true the fix is a bound AND a signal, not a bound.
   * - SELECT then UPDATE, not `UPDATE ... RETURNING`. The rows are needed for
   *   the audit writes anyway, and this assumes nothing about which SQLite
   *   version workerd's Durable Object storage exposes.
   */
  private sweepExpired(): number {
    const now = new Date().toISOString();
    const due = this.all<{ id: string; expires_at: string }>(
      `SELECT id, expires_at FROM submissions
        WHERE status = 'pending'
          AND expires_at IS NOT NULL
          AND expires_at LIKE '____-__-__T%'
          AND expires_at < ?`,
      now,
    );
    for (const row of due) {
      // The UPDATE re-carries the SELECT's own predicate rather than trusting
      // the row it just read. Recommended at spec review by glm
      // (reviews/20260831-203202-spec-glm.md §2), which looked for a reachable
      // interleaving on workerd and could not construct one — input gates make
      // this sequence atomic on the single object. It is one clause, it costs
      // nothing, and it means a future caller of sweepExpired() outside a
      // storage-gated context cannot make this write a lie.
      this.sql.exec(
        `UPDATE submissions SET status = 'expired', updated_at = ?
          WHERE id = ? AND status = 'pending'`,
        now, row.id,
      );
      // The system did this, not the sender: attributing it to a person would
      // be a false record. Same actor finalize() uses for `completed`.
      this.audit(row.id, 'expired', 'system@pumasi.ai', 'Pumasi Sign Engine', undefined, {
        expires_at: row.expires_at,
      });
    }
    return due.length;
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
    // A share is bound to the verified login email. Merely possessing or
    // forwarding the notification link never grants a different account access.
    this.sql.exec(
      `UPDATE template_shares SET status = 'accepted', accepted_at = COALESCE(accepted_at, ?)
        WHERE recipient_email = ? AND status = 'pending'`,
      now, email.toLowerCase(),
    );
    this.sql.exec(
      `UPDATE team_members SET status = 'accepted', accepted_at = COALESCE(accepted_at, ?)
        WHERE id = (SELECT id FROM team_members WHERE email = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1)`,
      now, email.toLowerCase(),
    );
    const token = newToken();
    this.sql.exec(
      `INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)`,
      token, user.id, new Date(Date.now() + SESSION_TTL_DAYS * 86400_000).toISOString(), now,
    );
    return { user, cookie: setCookie('sign_session', token, SESSION_TTL_DAYS * 86400) };
  }

  private oauthProvider(name: string): { authUrl: string; tokenUrl: string; userInfoUrl: string; clientId?: string; clientSecret?: string } | null {
    if (name === 'google') {
      return {
        authUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
        tokenUrl: 'https://oauth2.googleapis.com/token',
        userInfoUrl: 'https://openidconnect.googleapis.com/v1/userinfo',
        clientId: this.env.GOOGLE_OAUTH_CLIENT_ID,
        clientSecret: this.env.GOOGLE_OAUTH_CLIENT_SECRET,
      };
    }
    if (name === 'microsoft') {
      return {
        authUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
        tokenUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
        userInfoUrl: 'https://graph.microsoft.com/oidc/userinfo',
        clientId: this.env.MS_OAUTH_CLIENT_ID,
        clientSecret: this.env.MS_OAUTH_CLIENT_SECRET,
      };
    }
    return null;
  }

  private async route(req: Request, url: URL, path: string, method: string): Promise<Response> {
    // Storage-backed readiness. The edge Worker is the only caller because it
    // rejects every /__internal/* URL before forwarding public requests.
    if (path === '/__internal/ready' && method === 'GET') {
      const row = this.one<{ ok: number }>('SELECT 1 AS ok');
      return json({ ready: row?.ok === 1 });
    }

    // ── the hourly expiry sweep ───────────────────────────────────────────
    //
    // Reached only from worker.ts's `scheduled()` export, through
    // `stub.fetch()`. worker.ts refuses this prefix on its own `fetch()`, so
    // it is not on the public surface — deliberately NOT under /api/, every
    // path of which is forwarded here. spec/0007 §S2c.
    if (path === '/__internal/expire' && method === 'POST') {
      return json({ expired: this.sweepExpired() });
    }

    if (path === '/__internal/rate-limit' && method === 'POST') {
      const body: any = await req.json().catch(() => ({}));
      const owner = this.sessionUser(req);
      const policies: Record<string, { limit: number; window: number }> = {
        // Pilot users often submit several observations in one review session.
        // Keep the conservative anonymous/IP ceiling, but do not lock an
        // authenticated reviewer out after five useful reports.
        feedback: { limit: owner ? 30 : 5, window: 3600 },
        'standalone-convert': { limit: 20, window: 600 },
      };
      const policy = policies[String(body.scope || '')];
      if (!policy) return json({ error: 'Unknown rate-limit policy' }, 400);
      const identity = owner ? `owner:${owner.id}` : `ip:${this.clientIp(req)}`;
      const retryAfter = await this.rateLimited(String(body.scope), [identity], policy.limit, policy.window);
      return json({ allowed: retryAfter == null, retry_after: retryAfter });
    }

    // Conversion and document writes are CPU/storage-heavy. Authenticated
    // principals get independent buckets; anonymous calls fall back to IP.
    if (method === 'POST' && (
      path === '/api/submissions/adhoc/merged-document' ||
      path === '/api/submissions/adhoc' ||
      path === '/api/templates' ||
      /\/replace-document$/.test(path) ||
      /^\/api\/sign\/[A-Za-z0-9_-]+\/(signature|attachment)$/.test(path)
    )) {
      const owner = this.sessionUser(req);
      const signer = this.signerSubmitterId(req);
      const identity = owner ? `owner:${owner.id}` : signer ? `signer:${signer}` : `ip:${this.clientIp(req)}`;
      const retry = await this.rateLimited('document-write', [identity], 30, 600);
      if (retry != null) return json({ error: 'Too many document requests. Try again shortly.' }, 429, { 'Retry-After': String(retry) });
    }

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
      const tok = (await tokenRes.json()) as { access_token?: string };
      // Never trust a merely decoded JWT payload. Ask the provider for the
      // identity bound to the access token returned by this code exchange;
      // TLS plus the bearer-token check provides the verification boundary.
      if (!tok.access_token) return new Response(null, { status: 302, headers: { Location: '/login' } });
      const userInfoRes = await fetch(provider.userInfoUrl, {
        headers: { Authorization: `Bearer ${tok.access_token}` },
      });
      if (!userInfoRes.ok) return new Response(null, { status: 302, headers: { Location: '/login' } });
      const claims: any = await userInfoRes.json().catch(() => ({}));
      const email = String(claims.email || claims.preferred_username || '').trim().toLowerCase();
      // Google's UserInfo contract supplies email_verified and it must be
      // affirmative. Microsoft Entra's UserInfo endpoint generally omits that
      // Google-specific claim; the identity is authenticated by the bearer
      // token/code exchange itself. Requiring the absent claim made every real
      // Microsoft login silently return to /login.
      const unverifiedGoogleEmail = oauthMatch[1] === 'google' && claims.email_verified !== true;
      if (!email || !email.includes('@') || unverifiedGoogleEmail) {
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
      const retry = await this.rateLimited('login-code-request', [`ip:${this.clientIp(req)}`, `email:${email}`], 10, 3600);
      if (retry != null) return json({ error: 'Too many verification-code requests. Try again later.' }, 429, { 'Retry-After': String(retry) });
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
      const retry = await this.rateLimited('login-code-verify', [`ip:${this.clientIp(req)}`, `email:${email}`], 6, 900);
      if (retry != null) return json({ error: 'Too many verification attempts. Try again later.' }, 429, { 'Retry-After': String(retry) });
      if (!this.consumeCode(email, code)) {
        return json({ error: 'Invalid or expired verification code' }, 401);
      }

      const displayName = String(body.name || email.split('@')[0].replace(/[._]/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()));
      const { user, cookie } = this.establishSession(email, displayName, 'email');
      const branding = this.one(`SELECT company_name, logo_data_url, primary_color, welcome_message FROM org_branding WHERE owner_id = ?`, this.workspaceFor(user).ownerId);
      return json(
        {
          ok: true,
          user: this.accountUserOut(user),
          branding: branding || { company_name: 'Pumasi Sign', primary_color: '#1A56DB' },
        },
        200,
        { 'Set-Cookie': cookie },
      );
    }

    if (path === '/api/auth/me' && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      return json(this.accountUserOut(user));
    }

    if (path === '/api/profile' && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      return json(this.accountUserOut(user));
    }

    if (path === '/api/profile' && method === 'PUT') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const body: any = await req.json();
      const name = String(body.name || '').trim().replace(/\s+/g, ' ');
      if (name.length < 2 || name.length > 120) return json({ error: 'Name must be between 2 and 120 characters' }, 400);
      this.sql.exec(`UPDATE users SET name = ? WHERE id = ?`, name, user.id);
      return json(this.accountUserOut({ ...user, name }));
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
      const branding = this.one(`SELECT company_name, logo_data_url, primary_color, welcome_message FROM org_branding WHERE owner_id = ?`, this.workspaceFor(user).ownerId);
      return json(branding || { company_name: 'Pumasi Sign', primary_color: '#1A56DB', welcome_message: null, logo_data_url: null });
    }

    if (path === '/api/branding' && method === 'PUT') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const workspace = this.workspaceFor(user);
      if (workspace.role === 'member') return json({ error: 'Only workspace admins can change branding' }, 403);
      const body: any = await req.json();
      const now = new Date().toISOString();
      const existing = this.one<{ id: string }>(`SELECT id FROM org_branding WHERE owner_id = ?`, workspace.ownerId);
      if (existing) {
        this.sql.exec(
          `UPDATE org_branding SET company_name = ?, logo_data_url = ?, primary_color = ?, welcome_message = ?, updated_at = ? WHERE owner_id = ?`,
          String(body.company_name || 'Pumasi Sign').slice(0, 120),
          body.logo_data_url ?? null,
          String(body.primary_color || '#1A56DB').slice(0, 20),
          body.welcome_message != null ? String(body.welcome_message).slice(0, 500) : null,
          now, workspace.ownerId,
        );
      } else {
        this.sql.exec(
          `INSERT INTO org_branding (id, owner_id, company_name, logo_data_url, primary_color, welcome_message, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
          `org-${crypto.randomUUID().slice(0, 8)}`, workspace.ownerId,
          String(body.company_name || 'Pumasi Sign').slice(0, 120),
          body.logo_data_url ?? null,
          String(body.primary_color || '#1A56DB').slice(0, 20),
          body.welcome_message != null ? String(body.welcome_message).slice(0, 500) : null,
          now, now,
        );
      }
      const branding = this.one(`SELECT company_name, logo_data_url, primary_color, welcome_message FROM org_branding WHERE owner_id = ?`, workspace.ownerId);
      return json(branding);
    }

    // ── owner: automatic completed-envelope archive recipients ───────────
    if (path === '/api/admin/archive-recipients' && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      return json(this.all<{ email: string }>(
        `SELECT email FROM archive_recipients WHERE owner_id = ? ORDER BY email`, user.id,
      ).map((row) => row.email));
    }

    if (path === '/api/admin/archive-recipients' && method === 'PUT') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const body: any = await req.json();
      if (!Array.isArray(body.emails)) return json({ error: 'emails must be an array' }, 400);
      const emails: string[] = [...new Set<string>(
        body.emails.map((value: unknown) => String(value).trim().toLowerCase()).filter(Boolean),
      )];
      if (emails.length > 10) return json({ error: 'Up to 10 archive recipients are allowed' }, 400);
      if (emails.some((email) => !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))) {
        return json({ error: 'Every archive recipient must be a valid email address' }, 400);
      }
      if (emails.includes(user.email.toLowerCase())) {
        return json({ error: 'The envelope owner already receives completed-envelope notifications' }, 400);
      }
      this.sql.exec(`DELETE FROM archive_recipients WHERE owner_id = ?`, user.id);
      const now = new Date().toISOString();
      for (const email of emails) {
        this.sql.exec(
          `INSERT INTO archive_recipients (id, owner_id, email, created_at) VALUES (?, ?, ?, ?)`,
          `arc-${crypto.randomUUID().slice(0, 8)}`, user.id, email, now,
        );
      }
      return json(emails);
    }

    // Team membership grants account capabilities only. Resource visibility
    // remains owner/participant/explicit-share scoped in the routes below.
    if (path === '/api/team/members' && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const workspace = this.workspaceFor(user);
      if (workspace.role === 'member') return json({ error: 'Only workspace admins can manage the team' }, 403);
      const owner = this.one<UserRow>(`SELECT id, email, name, provider FROM users WHERE id = ?`, workspace.ownerId);
      const members = this.all<any>(
        `SELECT tm.id, tm.email, tm.role, tm.status, tm.created_at, tm.accepted_at,
                COALESCE(u.name, tm.email) AS name
           FROM team_members tm LEFT JOIN users u ON u.email = tm.email
          WHERE tm.owner_id = ? AND tm.status != 'revoked' ORDER BY tm.created_at`, workspace.ownerId,
      );
      return json([
        { id: `owner-${workspace.ownerId}`, email: owner?.email || user.email, name: owner?.name || user.name, role: 'owner', status: 'accepted', created_at: null },
        ...members,
      ]);
    }

    if (path === '/api/team/members' && method === 'POST') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const workspace = this.workspaceFor(user);
      if (workspace.role === 'member') return json({ error: 'Only workspace admins can invite people' }, 403);
      const body: any = await req.json();
      const email = String(body.email || '').trim().toLowerCase();
      const role = body.role === 'admin' ? 'admin' : 'member';
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return json({ error: 'A valid email is required' }, 400);
      const owner = this.one<UserRow>(`SELECT id, email, name, provider FROM users WHERE id = ?`, workspace.ownerId);
      if (email === owner?.email.toLowerCase()) return json({ error: 'The workspace owner is already on the team' }, 400);
      const elsewhere = this.one<{ owner_id: string }>(
        `SELECT owner_id FROM team_members WHERE email = ? AND status = 'accepted' AND owner_id != ? LIMIT 1`, email, workspace.ownerId,
      );
      if (elsewhere) return json({ error: 'This person already belongs to another workspace' }, 409);
      const now = new Date().toISOString();
      const id = `tmb-${crypto.randomUUID().slice(0, 12)}`;
      this.sql.exec(
        `INSERT INTO team_members (id, owner_id, email, role, status, invited_by, created_at, revoked_at)
         VALUES (?, ?, ?, ?, 'pending', ?, ?, NULL)
         ON CONFLICT(owner_id, email) DO UPDATE SET role = excluded.role,
           status = CASE WHEN team_members.status = 'accepted' THEN 'accepted' ELSE 'pending' END,
           invited_by = excluded.invited_by, created_at = excluded.created_at,
           accepted_at = CASE WHEN team_members.status = 'accepted' THEN team_members.accepted_at ELSE NULL END,
           revoked_at = NULL`,
        id, workspace.ownerId, email, role, user.email, now,
      );
      await this.sendTeamInvitation(email, user, owner?.name || 'your team');
      const row = this.one<any>(
        `SELECT tm.id, tm.email, tm.role, tm.status, tm.created_at, tm.accepted_at, COALESCE(u.name, tm.email) AS name
           FROM team_members tm LEFT JOIN users u ON u.email = tm.email WHERE tm.owner_id = ? AND tm.email = ?`,
        workspace.ownerId, email,
      );
      return json(row, 201);
    }

    const teamMemberMatch = path.match(/^\/api\/team\/members\/([A-Za-z0-9_-]+)(?:\/(resend))?$/);
    if (teamMemberMatch) {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const workspace = this.workspaceFor(user);
      if (workspace.role === 'member') return json({ error: 'Only workspace admins can manage the team' }, 403);
      const member = this.one<any>(
        `SELECT * FROM team_members WHERE id = ? AND owner_id = ? AND status != 'revoked'`, teamMemberMatch[1], workspace.ownerId,
      );
      if (!member) return json({ error: 'Team member not found' }, 404);
      if (teamMemberMatch[2] === 'resend' && method === 'POST') {
        if (member.status !== 'pending') return json({ error: 'Only pending invitations can be resent' }, 409);
        const owner = this.one<UserRow>(`SELECT id, email, name, provider FROM users WHERE id = ?`, workspace.ownerId);
        await this.sendTeamInvitation(member.email, user, owner?.name || 'your team');
        return json({ ok: true });
      }
      if (!teamMemberMatch[2] && method === 'PUT') {
        const body: any = await req.json();
        if (body.role !== 'admin' && body.role !== 'member') {
          return json({ error: 'Role must be admin or user' }, 400);
        }
        if (member.email.toLowerCase() === user.email.toLowerCase() && body.role !== member.role) {
          return json({ error: 'Ask the workspace owner or another admin to change your role' }, 409);
        }
        this.sql.exec(`UPDATE team_members SET role = ? WHERE id = ?`, body.role, member.id);
        return json({
          id: member.id, email: member.email, role: body.role, status: member.status,
          name: this.one<UserRow>(`SELECT id, email, name, provider FROM users WHERE email = ?`, member.email)?.name || member.email,
          created_at: member.created_at, accepted_at: member.accepted_at,
        });
      }
      if (!teamMemberMatch[2] && method === 'DELETE') {
        this.sql.exec(`UPDATE team_members SET status = 'revoked', revoked_at = ? WHERE id = ?`, new Date().toISOString(), member.id);
        return json({ ok: true });
      }
      return json({ error: 'Endpoint not found' }, 404);
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
      const archived = url.searchParams.get('archived') === 'true';
      const rows = this.all<any>(
        `SELECT * FROM templates
          WHERE (created_by = ? OR id IN (
            SELECT template_id FROM template_shares WHERE recipient_email = ? AND status != 'revoked'
          )) AND archived_at IS ${archived ? 'NOT NULL' : 'NULL'} AND is_adhoc = 0
          ${archived ? 'AND created_by = ?' : ''} ORDER BY created_at DESC`,
        ...(archived ? [user.email, user.email.toLowerCase(), user.email] : [user.email, user.email.toLowerCase()]),
      );
      return json(rows.map((t) => this.templateOut(user, t)));
    }

    if (path === '/api/templates' && method === 'POST') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const contentType = req.headers.get('content-type') || '';
      let name: string;
      let pdfBytes: Uint8Array | null;
      let pageCount: number;
      let fields: any[] = [];
      let roles: string[] = [];
      if (contentType.includes('multipart/form-data')) {
        const form = await req.formData();
        const file = form.get('file');
        name = String(form.get('name') || '').trim();
        if (!name || !(file instanceof File)) return json({ error: 'Name and document are required' }, 400);
        const normalized = await this.uploadAsPdf(file);
        if (!normalized.bytes) return json({ error: normalized.error || 'The document could not be processed' }, 422);
        pdfBytes = normalized.bytes;
        pageCount = normalized.pageCount!;
      } else {
        const body: any = await req.json();
        name = String(body.name || '').trim() || 'Untitled Template';
        pdfBytes = body.pdfBase64 ? dataUrlToBytes(`,${body.pdfBase64}`) : null;
        pageCount = Number(body.pageCount ?? body.page_count) || 1;
        fields = Array.isArray(body.fields) ? body.fields : [];
        roles = Array.isArray(body.roles) ? body.roles : [];
      }
      const id = `tpl-${crypto.randomUUID().slice(0, 8)}`;
      const pdfKey = pdfBytes ? await this.storePdf('templates', id, pdfBytes) : null;
      this.sql.exec(
        `INSERT INTO templates (id, name, created_by, pdf_blob, pdf_key, page_count, fields_json, roles_json, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        id, name.slice(0, 255), user.email, pdfKey ? null : pdfBytes, pdfKey,
        pageCount, JSON.stringify(fields), JSON.stringify(roles), new Date().toISOString(),
      );
      const t = this.one<any>(`SELECT * FROM templates WHERE id = ?`, id);
      return json(this.templateOut(user, t), 201);
    }

    const tplMatch = path.match(/^\/api\/templates\/([A-Za-z0-9_-]+)(?:\/(fields|sharing|copy|archive|unarchive))?$/);
    if (tplMatch) {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const t = this.one<any>(`SELECT * FROM templates WHERE id = ?`, tplMatch[1]);
      if (!t) return json({ error: 'Template not found' }, 404);
      const visible = this.canUseTemplate(t, user);
      const owned = t.created_by === user.email;
      const action = tplMatch[2];
      if (!visible) return json({ error: 'Template not found' }, 404);
      if (!action && method === 'GET') {
        if (t.archived_at) return json({ error: 'Template not found' }, 404);
        return json(this.templateOut(user, t));
      }
      if (action === 'fields' && method === 'PUT') {
        if (!owned) return json({ error: 'Forbidden' }, 403);
        const body: any = await req.json();
        if (!Array.isArray(body.fields)) return json({ error: 'fields must be an array' }, 400);
        if (body.fields.some((f: any) => !Number.isInteger(f.page) || f.page < 0 || f.page >= (t.page_count || 1))) {
          return json({ error: 'page out of range' }, 422);
        }
        const roles = Array.isArray(body.roles)
          ? body.roles.map(String)
          : [...new Set(body.fields.filter((f: any) => f.type !== 'label').map((f: any) => String(f.role || '')).filter(Boolean))];
        this.sql.exec(`UPDATE templates SET fields_json = ?, roles_json = ? WHERE id = ?`, JSON.stringify(body.fields), JSON.stringify(roles), t.id);
        return json(this.templateOut(user, this.one<any>(`SELECT * FROM templates WHERE id = ?`, t.id)));
      }
      if (action === 'sharing' && method === 'PUT') {
        if (!owned) return json({ error: 'Forbidden' }, 403);
        const body: any = await req.json();
        if (!Array.isArray(body.emails)) return json({ error: 'emails must be an array' }, 400);
        const emails = [...new Set<string>(body.emails.map((v: unknown) => String(v).trim().toLowerCase()).filter(Boolean))];
        if (emails.length > 50) return json({ error: 'A template can be shared with up to 50 people' }, 400);
        if (emails.some((email) => !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))) {
          return json({ error: 'Every recipient must be a valid email address' }, 400);
        }
        if (emails.includes(user.email.toLowerCase())) return json({ error: 'You already own this template' }, 400);

        const existing = new Set(this.all<{ recipient_email: string }>(
          `SELECT recipient_email FROM template_shares WHERE template_id = ? AND status != 'revoked'`, t.id,
        ).map((row) => row.recipient_email));
        const now = new Date().toISOString();
        for (const email of emails) {
          this.sql.exec(
            `INSERT INTO template_shares (id, template_id, recipient_email, shared_by, permission, status, created_at, revoked_at)
             VALUES (?, ?, ?, ?, 'use', 'pending', ?, NULL)
             ON CONFLICT(template_id, recipient_email) DO UPDATE SET status = 'pending', revoked_at = NULL, shared_by = excluded.shared_by`,
            `tsh-${crypto.randomUUID().slice(0, 12)}`, t.id, email, user.email, now,
          );
          if (!existing.has(email)) {
            const url = `${this.env.BASE_URL || 'https://sign.pumasi.ai'}/templates`;
            await this.mailOrLog(
              email,
              `${user.name} shared a template with you`,
              `${user.name} (${user.email}) shared “${t.name}” with you. You can use it to create an envelope, but cannot edit or delete the original.\n\nOpen templates: ${url}`,
              this.mailHtml(`${user.name} shared a template with you`, [
                `You can use “${t.name}” to create an envelope. You cannot edit or delete the original template.`,
                `Sign in with ${email} to access it.`,
              ], { cta: { label: 'Open shared template', url } }),
            );
          }
        }
        for (const email of existing) {
          if (!emails.includes(email)) {
            this.sql.exec(
              `UPDATE template_shares SET status = 'revoked', revoked_at = ? WHERE template_id = ? AND recipient_email = ?`,
              now, t.id, email,
            );
          }
        }
        return json({
          template: this.templateOut(user, this.one<any>(`SELECT * FROM templates WHERE id = ?`, t.id)),
          shares: this.all(`SELECT recipient_email AS email, permission, status, created_at FROM template_shares WHERE template_id = ? AND status != 'revoked' ORDER BY created_at`, t.id),
        });
      }
      if (action === 'sharing' && method === 'GET') {
        if (!owned) return json({ error: 'Forbidden' }, 403);
        return json(this.all(
          `SELECT recipient_email AS email, permission, status, created_at FROM template_shares WHERE template_id = ? AND status != 'revoked' ORDER BY created_at`, t.id,
        ));
      }
      if (action === 'archive' && method === 'POST') {
        if (!owned) return json({ error: 'Forbidden' }, 403);
        this.sql.exec(`UPDATE templates SET archived_at = ? WHERE id = ?`, new Date().toISOString(), t.id);
        return json({ status: 'ok' });
      }
      if (action === 'unarchive' && method === 'POST') {
        if (!owned) return json({ error: 'Forbidden' }, 403);
        this.sql.exec(`UPDATE templates SET archived_at = NULL WHERE id = ?`, t.id);
        return json({ status: 'ok' });
      }
      if (action === 'copy' && method === 'POST') {
        if (t.archived_at) return json({ error: 'Template is archived' }, 409);
        const bytes = await this.loadPdf(t.pdf_key, t.pdf_blob);
        if (!bytes) return json({ error: 'Template document is unavailable' }, 409);
        const id = `tpl-${crypto.randomUUID().slice(0, 8)}`;
        const key = await this.storePdf('templates', id, bytes);
        this.sql.exec(
          `INSERT INTO templates (id, name, created_by, pdf_blob, pdf_key, page_count, fields_json, roles_json, is_adhoc, is_shared, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)`,
          id, `Copy of ${t.name}`.slice(0, 255), user.email, key ? null : bytes, key,
          t.page_count, t.fields_json || '[]', t.roles_json || '[]', new Date().toISOString(),
        );
        return json(this.templateOut(user, this.one<any>(`SELECT * FROM templates WHERE id = ?`, id)), 201);
      }
      return json({ error: 'Endpoint not found' }, 404);
    }

    if (path.match(/^\/api\/files\/template-pdf\/[A-Za-z0-9_-]+$/) && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const id = path.split('/').pop()!;
      const t = this.one<any>(`SELECT * FROM templates WHERE id = ? AND archived_at IS NULL`, id);
      if (t && !this.canUseTemplate(t, user)) return json({ error: 'Not found' }, 404);
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

      const prepared = await this.prepareDocuments(files);
      if (!prepared.merged) return json({ error: prepared.error }, prepared.error?.includes('limit') ? 413 : 422);
      return new Response(prepared.merged.buffer as ArrayBuffer, {
        headers: { 'Content-Type': 'application/pdf', ...corsHeaders },
      });
    }

    // ── owner: create one-off envelope from an uploaded PDF ───────────────
    if (path === '/api/submissions/adhoc' && method === 'POST') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const form = await req.formData();
      const sourceFiles = form.getAll('documents').filter((f): f is File => f instanceof File);
      const legacyFile = form.get('file');
      const files = sourceFiles.length ? sourceFiles : legacyFile instanceof File ? [legacyFile] : [];
      if (!files.length) return json({ error: 'At least one document file is required' }, 400);
      const prepared = await this.prepareDocuments(files);
      if (!prepared.merged || !prepared.documents) return json({ error: prepared.error }, prepared.error?.includes('limit') ? 413 : 422);
      const pdfBytes = prepared.merged;

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
      const pageCount = prepared.documents.reduce((sum, document) => sum + document.pageCount, 0);

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
        id, newEnvelopeUid(), title, message, user.email,
        isDraft ? 'draft' : 'pending', pdfKey ? null : pdfBytes, pdfKey, pageCount, tplId,
        remindersEnabled ? 1 : 0, reminderInterval, expiresAt, now, now,
      );
      await this.persistSubmissionDocuments(id, prepared.documents, now);
      this.sql.exec(`UPDATE submissions SET original_hash = ? WHERE id = ?`, await this.sha256(pdfBytes), id);

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
        `SELECT id, name, created_by, pdf_blob, pdf_key, page_count, fields_json FROM templates
          WHERE id = ? AND archived_at IS NULL`, String(body.template_id || ''),
      );
      if (!tpl || !this.canUseTemplate(tpl, user)) return json({ error: 'Template not found' }, 404);
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
        id, newEnvelopeUid(),
        String(body.title || tpl.name).slice(0, 200), body.message ?? null, user.email,
        isDraft ? 'draft' : 'pending', pdfKey ? null : tplPdf, pdfKey, tpl.page_count || 1, tpl.id,
        body.reminders_enabled === false ? 0 : 1, Number(body.reminder_interval_days) || 3,
        body.expires_at ?? null, now, now,
      );
      if (tplPdf) this.sql.exec(`UPDATE submissions SET original_hash = ? WHERE id = ?`, await this.sha256(tplPdf), id);

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

      if (method === 'GET' && action === 'documents') {
        const documents = this.all<any>(
          `SELECT id, filename, position, page_count, page_start FROM submission_documents
            WHERE submission_id = ? ORDER BY position ASC`, sub.id,
        );
        return json(documents.length ? documents.map((document) => ({
          id: document.id,
          filename: document.filename,
          order: document.position,
          page_count: document.page_count,
          page_start: document.page_start,
          download_url: `/api/files/submission-document/${document.id}`,
        })) : [{
          id: sub.id, filename: `${sub.title}.pdf`, order: 0,
          page_count: sub.page_count || 1, page_start: 0,
          download_url: `/api/files/document-preview/${sub.id}`,
        }]);
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

        // The "correct expiration & reminders" dialog (EnvelopeDetailView.vue
        // :428) has always sent these three and this route has always thrown
        // them away, closing on "Envelope settings updated." having updated
        // nothing. Harmless while the deadline meant nothing; a trap the
        // moment spec/0007 makes it binding, because a sender extending a
        // deadline before it passes is told it worked and the envelope
        // expires on the old date anyway. spec/0007 §S1d, §S3d.
        const settings: string[] = [];
        const has = (k: string) => Object.prototype.hasOwnProperty.call(body, k);
        if (has('expires_at')) settings.push('expiration date');
        if (has('reminders_enabled')) settings.push('reminders');
        if (has('reminder_interval_days')) settings.push('reminder interval');

        // FIRST statement of the branch, before the title/message write and
        // before any other read of the body -- so a refused correction writes
        // nothing and audits nothing, which is the idiom job 0058 established
        // for every other guard in this file. Moved here from below on kimi's
        // code review (reviews/20260831-203845-code-kimi.md), which found that
        // a body carrying BOTH a title and a settings field got a 409 with the
        // title write already persisted. spec/0007 §S3d.
        //
        // A body with no settings field is unaffected: title and message keep
        // the behaviour they had, on every status, which this spec does not
        // touch.
        if (settings.length > 0 && isTerminal(sub.status)) {
          return json({ error: 'This envelope is already closed' }, 409);
        }

        // `title` has always been KEPT when the body omits it -- `?? sub.title`
        // below -- and `message` had no counterpart, so a body that never
        // mentioned it wrote NULL. The settings dialog above omits it on every
        // save, so every use of that pencil deleted the sender's covering note
        // to the signers, silently, and closed on "Envelope settings updated."
        // The note is returned to every recipient on the token view (:1593).
        // roadmap/BACKLOG.md item 1; spec/0008 §S1.
        //
        // `!== undefined` rather than `??`, deliberately: the two cases this
        // has to tell apart are ABSENT (keep) and PRESENT-AND-NULL (clear).
        // The correct-details dialog (EnvelopeDetailView.vue:380) sends
        // `message: null` on purpose when the sender empties the box, and the
        // send form at :1175 writes `body.message ?? null` on create. `??`
        // here would collapse the two and make a message unremovable, which is
        // the same class of bug pointing the other way. spec/0008 §S2.
        const title = String(body.title ?? sub.title).slice(0, 200);
        const message = body.message !== undefined
          ? (body.message != null ? String(body.message).slice(0, 2000) : null)
          : (sub.message ?? null);
        this.sql.exec(
          `UPDATE submissions SET title = ?, message = ?, updated_at = ? WHERE id = ?`,
          title, message, now, sub.id,
        );

        if (settings.length > 0) {
          // Only while it is still live. The pencil that sends these is drawn
          // for `pending` and `draft` only (EnvelopeDetailView.vue:64), and
          // reviving a finished envelope by extending its deadline is not a
          // capability this spec adds — `copy` is the route out.
          if (has('expires_at')) {
            this.sql.exec(
              `UPDATE submissions SET expires_at = ? WHERE id = ?`,
              body.expires_at ? String(body.expires_at) : null, sub.id,
            );
          }
          if (has('reminders_enabled')) {
            this.sql.exec(
              `UPDATE submissions SET reminders_enabled = ? WHERE id = ?`,
              body.reminders_enabled === false ? 0 : 1, sub.id,
            );
          }
          if (has('reminder_interval_days')) {
            this.sql.exec(
              `UPDATE submissions SET reminder_interval_days = ? WHERE id = ?`,
              Number(body.reminder_interval_days) || 3, sub.id,
            );
          }
        }

        // EnvelopeDetailView.vue:608 has rendered `detail.changed` all along
        // and had never been sent one until 2471a29, which sent it the three
        // settings and nothing else -- so a correction to the WORDS of the
        // agreement named nothing, while a correction to a reminder interval
        // named itself. spec/0008 §S3 answers that question `yes` rather than
        // leaving it open: title and message join the same list.
        //
        // Compared against the stored row, not against presence in the body,
        // because both dialogs re-send fields the sender did not touch --
        // EnvelopeDetailView.vue:380 always sends both -- and a history line
        // claiming a change that did not happen is its own defect. `sub` is
        // the pre-PATCH snapshot read at :1219, so the writes above do not
        // move it.
        //
        // The 409 guard stays keyed on `settings`, NOT on this list: title and
        // message keep the behaviour they had on every status, which is what
        // spec/0007 §S3d promised and what this spec does not touch.
        const changed = [...settings];
        if (title !== sub.title) changed.push('title');
        if (message !== (sub.message ?? null)) changed.push('message');

        this.audit(sub.id, 'corrected', user.email, user.name, undefined,
          changed.length > 0 ? { changed } : undefined);
        return json(this.submissionOut(user, this.one<any>(`SELECT * FROM submissions WHERE id = ?`, sub.id)));
      }

      if (method === 'DELETE' && !action) {
        if (sub.status !== 'draft') return json({ error: 'Only drafts can be deleted' }, 409);
        for (const key of [sub.original_pdf_key, sub.completed_pdf_key, sub.certificate_pdf_key]) {
          if (key) await this.docs()?.deleteDocument(String(key)).catch(() => {});
        }
        for (const attachment of this.all<{ data_key: string | null }>(
          `SELECT a.data_key FROM attachments a JOIN submitters s ON s.id = a.submitter_id WHERE s.submission_id = ?`, sub.id,
        )) {
          if (attachment.data_key) await this.docs()?.deleteDocument(attachment.data_key).catch(() => {});
        }
        for (const document of this.all<{ pdf_key: string | null }>(
          `SELECT pdf_key FROM submission_documents WHERE submission_id = ?`, sub.id,
        )) {
          if (document.pdf_key) await this.docs()?.deleteDocument(document.pdf_key).catch(() => {});
        }
        if (sub.template_id) {
          const t = this.one<any>(`SELECT pdf_key FROM templates WHERE id = ? AND is_adhoc = 1`, sub.template_id);
          if (t?.pdf_key) await this.docs()?.deleteDocument(String(t.pdf_key)).catch(() => {});
        }
        this.sql.exec(`DELETE FROM submission_fields WHERE submission_id = ?`, sub.id);
        this.sql.exec(`DELETE FROM attachments WHERE submitter_id IN (SELECT id FROM submitters WHERE submission_id = ?)`, sub.id);
        this.sql.exec(`DELETE FROM submission_documents WHERE submission_id = ?`, sub.id);
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
          newId, newEnvelopeUid(), newKey ? null : srcPdf, newKey, now, now, sub.id,
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
        for (const document of this.all<any>(
          `SELECT * FROM submission_documents WHERE submission_id = ? ORDER BY position ASC`, sub.id,
        )) {
          const bytes = await this.loadPdf(document.pdf_key, document.pdf_blob);
          if (!bytes) continue;
          const documentId = `doc-${crypto.randomUUID().slice(0, 10)}`;
          const key = await this.storePdf(`submission-documents/${newId}`, documentId, bytes);
          this.sql.exec(
            `INSERT INTO submission_documents (id, submission_id, filename, position, page_count, page_start, pdf_blob, pdf_key, created_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            documentId, newId, document.filename, document.position, document.page_count, document.page_start,
            key ? null : bytes, key, now,
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

      if (method === 'POST' && action === 'retry-completion') {
        if (sub.status === 'completed') return json(this.submissionOut(user, sub));
        if (isTerminal(sub.status)) return json({ error: 'This envelope is already closed' }, 409);
        const signers = this.one<{ total: number; unfinished: number }>(
          `SELECT COUNT(*) AS total,
                  SUM(CASE WHEN status != 'signed' THEN 1 ELSE 0 END) AS unfinished
             FROM submitters WHERE submission_id = ? AND is_cc = 0`,
          sub.id,
        );
        if ((signers?.total ?? 0) === 0 || (signers?.unfinished ?? 0) !== 0) {
          return json({ error: 'Completion can only be retried after every signer has finished' }, 409);
        }
        const completed = await this.finalize(sub.id, new Date().toISOString());
        if (!completed) {
          return json({ error: 'The final document could not be produced. Your signatures are saved; try again shortly.' }, 503);
        }
        return json(this.submissionOut(user, this.one<any>(`SELECT * FROM submissions WHERE id = ?`, sub.id)));
      }

      if (method === 'POST' && action === 'save-as-template') {
        const bytes = await this.loadPdf(sub.original_pdf_key, sub.original_pdf_blob);
        if (!bytes) return json({ error: 'The envelope document is unavailable' }, 409);
        const signerRows = this.all<any>(
          `SELECT id, role FROM submitters WHERE submission_id = ? AND is_cc = 0 ORDER BY signing_order ASC, created_at ASC`,
          sub.id,
        );
        const roleBySubmitter = new Map<string, string>();
        const roles = signerRows.map((s, i) => {
          const role = `Signer ${i + 1}`;
          roleBySubmitter.set(s.id, role);
          return role;
        });
        const fields = this.fieldDefs(sub.id).map((field: any) => {
          if (field.type === 'label') return field;
          const row = this.one<{ submitter_id: string }>(`SELECT submitter_id FROM submission_fields WHERE id = ?`, field.id);
          return { ...field, role: row ? (roleBySubmitter.get(row.submitter_id) || field.role) : field.role };
        });
        const id = `tpl-${crypto.randomUUID().slice(0, 8)}`;
        const key = await this.storePdf('templates', id, bytes);
        this.sql.exec(
          `INSERT INTO templates (id, name, created_by, pdf_blob, pdf_key, page_count, fields_json, roles_json, is_adhoc, is_shared, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)`,
          id, String(sub.title).slice(0, 255), user.email, key ? null : bytes, key,
          sub.page_count || 1, JSON.stringify(fields), JSON.stringify(roles), new Date().toISOString(),
        );
        return json(this.templateOut(user, this.one<any>(`SELECT * FROM templates WHERE id = ?`, id)), 201);
      }

      if (method === 'POST' && action === 'replace-document') {
        if (sub.status !== 'draft' && sub.status !== 'pending') {
          return json({ error: 'Only draft or awaiting-signature envelopes can be corrected' }, 409);
        }
        const alreadySigned = this.one<{ n: number }>(
          `SELECT COUNT(*) AS n FROM submitters WHERE submission_id = ? AND status = 'signed'`, sub.id,
        );
        if ((alreadySigned?.n ?? 0) > 0) {
          return json({ error: 'The documents cannot be replaced after a signer has finished' }, 409);
        }
        const form = await req.formData();
        const multi = form.getAll('documents').filter((file): file is File => file instanceof File);
        const legacy = form.get('file');
        const files = multi.length ? multi : legacy instanceof File ? [legacy] : [];
        if (!files.length) return json({ error: 'At least one replacement document is required' }, 400);
        const prepared = await this.prepareDocuments(files);
        if (!prepared.merged || !prepared.documents) {
          return json({ error: prepared.error }, prepared.error?.includes('limit') ? 413 : 422);
        }
        const pageCount = prepared.documents.reduce((total, document) => total + document.pageCount, 0);
        const outOfRange = this.one<{ n: number }>(
          `SELECT COUNT(*) AS n FROM submission_fields WHERE submission_id = ? AND page >= ?`, sub.id, pageCount,
        );
        if ((outOfRange?.n ?? 0) > 0) {
          return json({ error: 'The replacement has fewer pages than the existing field placement. Move or remove those fields first.' }, 422);
        }

        // Write new R2 objects before switching the database references. A
        // storage failure therefore leaves the existing agreement untouched.
        const revision = crypto.randomUUID().slice(0, 8);
        const originalKey = await this.storePdf('originals', `${sub.id}-${revision}`, prepared.merged);
        const storedDocuments: Array<(typeof prepared.documents)[number] & { key: string | null }> = [];
        for (const document of prepared.documents) {
          const key = await this.storePdf(`submission-documents/${sub.id}`, document.id, document.bytes);
          storedDocuments.push({ ...document, key });
        }
        let templateKey: string | null = null;
        const adhocTemplate = sub.template_id
          ? this.one<any>(`SELECT id, pdf_key FROM templates WHERE id = ? AND is_adhoc = 1`, sub.template_id)
          : null;
        if (adhocTemplate) templateKey = await this.storePdf('templates', `${adhocTemplate.id}-${revision}`, prepared.merged);

        const oldDocuments = this.all<{ pdf_key: string | null }>(
          `SELECT pdf_key FROM submission_documents WHERE submission_id = ?`, sub.id,
        );
        this.sql.exec(`DELETE FROM submission_documents WHERE submission_id = ?`, sub.id);
        for (const document of storedDocuments) {
          this.sql.exec(
            `INSERT INTO submission_documents (id, submission_id, filename, position, page_count, page_start, pdf_blob, pdf_key, created_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            document.id, sub.id, document.filename, document.position, document.pageCount, document.pageStart,
            document.key ? null : document.bytes, document.key, now,
          );
          this.sql.exec(`UPDATE submission_documents SET sha256 = ? WHERE id = ?`, await this.sha256(document.bytes), document.id);
        }
        this.sql.exec(
          `UPDATE submissions SET original_pdf_blob = ?, original_pdf_key = ?, completed_pdf_blob = NULL,
             completed_pdf_key = NULL, completed_at = NULL, page_count = ?, updated_at = ? WHERE id = ?`,
          originalKey ? null : prepared.merged, originalKey, pageCount, now, sub.id,
        );
        this.sql.exec(`UPDATE submissions SET original_hash = ? WHERE id = ?`, await this.sha256(prepared.merged), sub.id);
        if (adhocTemplate) {
          this.sql.exec(
            `UPDATE templates SET pdf_blob = ?, pdf_key = ?, page_count = ? WHERE id = ?`,
            templateKey ? null : prepared.merged, templateKey, pageCount, adhocTemplate.id,
          );
        }
        this.audit(sub.id, 'document_replaced', user.email, user.name, undefined, {
          documents: prepared.documents.map((document) => document.filename), page_count: pageCount,
        });

        for (const key of [sub.original_pdf_key, sub.completed_pdf_key, adhocTemplate?.pdf_key, ...oldDocuments.map((d) => d.pdf_key)]) {
          if (key) await this.docs()?.deleteDocument(String(key)).catch(() => {});
        }
        return json(this.submissionOut(user, this.one<any>(`SELECT * FROM submissions WHERE id = ?`, sub.id)));
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

      // `expired` sits AHEAD of `already_signed` on purpose: an expired
      // envelope never completed, so there is no executed document, and
      // ExternalSignView.vue's RETRIEVABLE branch exists to hand one back.
      // spec/0007 §S3b.
      const tokenStatus =
        submission.status === 'cancelled' ? 'cancelled'
        : sub.status === 'declined' || submission.status === 'declined' ? 'declined'
        : submission.status === 'completed' ? 'completed'
        : submission.status === 'expired' ? 'expired'
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
        // `expired` joins the two refusals: without it the worker emails a
        // verification code for a dead envelope, and spec/0007 §S0.3 says
        // this change sends no mail.
        if (tokenStatus === 'cancelled' || tokenStatus === 'declined' || tokenStatus === 'expired') {
          return json({ error: 'This envelope is no longer active.' }, 410);
        }
        const retry = await this.rateLimited(
          'signer-code-request', [`ip:${this.clientIp(req)}`, `submitter:${sub.id}`], 10, 3600,
        );
        if (retry != null) return json({ error: 'Too many verification-code requests. Try again later.' }, 429, { 'Retry-After': String(retry) });
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
        const retry = await this.rateLimited(
          'signer-code-verify', [`ip:${this.clientIp(req)}`, `submitter:${sub.id}`], 6, 900,
        );
        if (retry != null) return json({ error: 'Too many verification attempts. Try again later.' }, 429, { 'Retry-After': String(retry) });
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
    const signMatch = path.match(/^\/api\/sign\/([A-Za-z0-9_-]+)(?:\/(signature|attachment|complete|decline))?$/);
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
          disclosure: { version: CONSENT_VERSION, text: CONSENT_TEXT },
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

      if (signMatch[2] === 'attachment' && method === 'POST') {
        if (isTerminal(submission.status) || me.status === 'signed') {
          return json({ error: 'This envelope is no longer open for attachments' }, 409);
        }
        const ownsField = this.one<{ n: number }>(
          `SELECT COUNT(*) AS n FROM submission_fields WHERE submission_id = ? AND submitter_id = ? AND type = 'attachment'`,
          submission.id, me.id,
        );
        if ((ownsField?.n ?? 0) === 0) return json({ error: 'No attachment field is assigned to this signer' }, 409);
        const form = await req.formData();
        const file = form.get('file');
        if (!(file instanceof File)) return json({ error: 'A file is required' }, 400);
        const bytes = new Uint8Array(await file.arrayBuffer());
        const limit = this.docs() ? 10 * 1024 * 1024 : 1_000_000;
        if (bytes.length === 0) return json({ error: 'The attachment is empty' }, 422);
        if (bytes.length > limit) return json({ error: `Attachment exceeds the ${Math.round(limit / 1_000_000)} MB limit` }, 413);
        const contentType = bytes[0] === 0x25 && bytes[1] === 0x50 && bytes[2] === 0x44 && bytes[3] === 0x46
          ? 'application/pdf'
          : bytes.slice(0, 8).every((v, i) => v === [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a][i])
            ? 'image/png'
            : bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff
              ? 'image/jpeg' : null;
        if (!contentType) return json({ error: 'Attachment must be a PDF, PNG, or JPEG file' }, 422);
        const safeName = safeAttachmentFilename(file.name, contentType);
        if (!safeName.filename) return json({ error: safeName.error }, 422);
        const id = `att-${crypto.randomUUID().slice(0, 10)}`;
        const key = this.docs() ? `attachments/${me.id}/${id}` : null;
        if (key) await this.docs()!.putDocument(key, bytes, contentType);
        const filename = safeName.filename;
        this.sql.exec(
          `INSERT INTO attachments (id, submitter_id, filename, content_type, size, data_blob, data_key, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
          id, me.id, filename, contentType, bytes.length, key ? null : bytes, key, new Date().toISOString(),
        );
        return json({ attachment_id: id, filename }, 201);
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
        if (body.consent_accepted !== true || body.consent_version !== CONSENT_VERSION) {
          return json({ error: 'You must accept the current electronic records and signature disclosure before finishing' }, 422);
        }
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
            if (sig.image_blob && (signatureBytes == null || f.type === 'signature')) {
              signatureBytes = new Uint8Array(sig.image_blob);
            }
            this.sql.exec(`UPDATE submission_fields SET value = ? WHERE id = ?`, String(v), f.id);
          } else if (f.type === 'checkbox') {
            this.sql.exec(`UPDATE submission_fields SET value = ? WHERE id = ?`, v === true || v === 'true' ? 'true' : 'false', f.id);
          } else if (f.type === 'attachment' && v != null) {
            const attachment = this.one<any>(`SELECT id, filename FROM attachments WHERE id = ? AND submitter_id = ?`, String(v), me.id);
            if (!attachment) return json({ error: `field ${f.id}: attachment not found or not yours` }, 422);
            this.sql.exec(`UPDATE submission_fields SET value = ? WHERE id = ?`, String(v), f.id);
          } else if (v != null) {
            this.sql.exec(`UPDATE submission_fields SET value = ? WHERE id = ?`, String(v).slice(0, 2000), f.id);
          } else if (f.required && f.type !== 'label') {
            return json({ error: 'A required field is missing' }, 400);
          }
        }

        const evidenceSource = this.one<any>(
          `SELECT original_hash, original_pdf_key, original_pdf_blob FROM submissions WHERE id = ?`, submission.id,
        );
        const reviewedPdf = evidenceSource?.original_hash
          ? null
          : await this.loadPdf(evidenceSource?.original_pdf_key, evidenceSource?.original_pdf_blob);
        const reviewedHash = evidenceSource?.original_hash || (reviewedPdf ? await this.sha256(reviewedPdf) : null);
        if (!reviewedHash) return json({ error: 'The document evidence is unavailable' }, 409);
        const documentManifest: any[] = [];
        for (const document of this.all<any>(
          `SELECT filename, position, page_count, pdf_blob, pdf_key, sha256 FROM submission_documents WHERE submission_id = ? ORDER BY position ASC`, submission.id,
        )) {
          let hash = document.sha256;
          if (!hash) {
            const bytes = await this.loadPdf(document.pdf_key, document.pdf_blob);
            if (!bytes) return json({ error: `Document evidence is unavailable for ${document.filename}` }, 409);
            hash = await this.sha256(bytes);
          }
          documentManifest.push({ filename: document.filename, order: document.position, page_count: document.page_count, sha256: hash });
        }
        if (documentManifest.length === 0) {
          documentManifest.push({ filename: `${submission.title}.pdf`, order: 0, page_count: submission.page_count || 1, sha256: reviewedHash });
        }
        this.sql.exec(
          `INSERT INTO signer_consents (id, submission_id, submitter_id, disclosure_version, disclosure_text, accepted_at,
             ip_address, user_agent, reviewed_document_hash, document_manifest_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
          `consent-${crypto.randomUUID().slice(0, 10)}`, submission.id, me.id, CONSENT_VERSION, CONSENT_TEXT, now,
          clientIp, userAgent, reviewedHash, JSON.stringify(documentManifest),
        );

        this.sql.exec(
          `UPDATE submitters SET status = 'signed', signed_at = ?, ip_address = ?, user_agent = ?, signature_blob = ? WHERE id = ?`,
          now, clientIp, userAgent, signatureBytes, me.id,
        );
        this.audit(submission.id, 'signed', me.email, me.name, clientIp, { userAgent });

        const remaining = this.one<{ n: number }>(
          `SELECT COUNT(*) AS n FROM submitters WHERE submission_id = ? AND status != 'signed' AND is_cc = 0`, submission.id,
        );

        if ((remaining?.n ?? 0) === 0) {
          const completed = await this.finalize(submission.id, now);
          if (!completed) {
            return json({ error: 'Your signature was saved, but the final document could not be produced. Please try again shortly.' }, 503);
          }
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
    const fileMatch = path.match(/^\/api\/files\/(document-preview|signed-pdf|certificate|signature|attachment|submission-document)\/([A-Za-z0-9_-]+)$/);
    if (fileMatch && method === 'GET') {
      const kind = fileMatch[1];
      const targetId = fileMatch[2];

      if (kind === 'submission-document') {
        const document = this.one<any>(`SELECT * FROM submission_documents WHERE id = ?`, targetId);
        if (!document || !this.authorizedForSubmission(req, document.submission_id)) return json({ error: 'Not found' }, 404);
        const bytes = await this.loadPdf(document.pdf_key, document.pdf_blob);
        if (!bytes) return json({ error: 'Not available' }, 404);
        return new Response(bytes.buffer as ArrayBuffer, {
          headers: {
            'Content-Type': 'application/pdf',
            'Content-Disposition': `attachment; filename="${String(document.filename).replace(/["\r\n]/g, '_').replace(/\.[^.]+$/, '')}.pdf"`,
            ...corsHeaders,
          },
        });
      }

      if (kind === 'attachment') {
        const attachment = this.one<any>(
          `SELECT a.*, s.submission_id FROM attachments a JOIN submitters s ON s.id = a.submitter_id WHERE a.id = ?`, targetId,
        );
        if (!attachment || !this.authorizedForSubmission(req, attachment.submission_id)) return json({ error: 'Not found' }, 404);
        const stored = attachment.data_key ? await this.docs()?.getDocument(attachment.data_key) : null;
        const bytes = stored?.data ?? (attachment.data_blob ? new Uint8Array(attachment.data_blob) : null);
        if (!bytes) return json({ error: 'Not available' }, 404);
        return new Response(bytes.buffer as ArrayBuffer, {
          headers: {
            'Content-Type': attachment.content_type,
            'Content-Disposition': `attachment; filename="${String(attachment.filename).replace(/["\r\n]/g, '_')}"`,
            ...corsHeaders,
          },
        });
      }

      if (kind === 'signature') {
        const sig = this.one<any>(`SELECT submitter_id, image_blob FROM signatures WHERE id = ?`, targetId);
        if (!sig || !this.authorizedForSubmitter(req, sig.submitter_id)) return json({ error: 'Not found' }, 404);
        return new Response(sig.image_blob, { headers: { 'Content-Type': 'image/png', ...corsHeaders } });
      }

      if (!this.authorizedForSubmission(req, targetId)) return json({ error: 'Not found' }, 404);
      const row = this.one<any>(`SELECT title, original_pdf_blob, original_pdf_key, completed_pdf_blob, completed_pdf_key, certificate_pdf_blob, certificate_pdf_key FROM submissions WHERE id = ?`, targetId);
      if (!row) return json({ error: 'Not found' }, 404);
      const pdf = kind === 'certificate'
        ? await this.loadPdf(row.certificate_pdf_key, row.certificate_pdf_blob)
        : kind === 'signed-pdf'
        ? await this.loadPdf(row.completed_pdf_key, row.completed_pdf_blob)
        : await this.loadPdf(row.original_pdf_key, row.original_pdf_blob);
      if (!pdf) return json({ error: 'Not available' }, 404);
      return new Response(pdf.buffer as ArrayBuffer, {
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': `${kind === 'document-preview' ? 'inline' : 'attachment'}; filename="${String(row.title).replace(/[^a-zA-Z0-9_-]/g, '_')}${kind === 'certificate' ? '_certificate' : ''}.pdf"`,
          ...corsHeaders,
        },
      });
    }

    return json({ error: 'Endpoint not found' }, 404);
  }

  /** All signed: stamp, certify, store, notify everyone (CCs included). */
  private async finalize(submissionId: string, now: string): Promise<boolean> {
    const sub = this.one<any>(
      `SELECT id, public_uid, title, created_by, original_pdf_blob, original_pdf_key FROM submissions WHERE id = ?`, submissionId,
    );
    if (!sub) return false;
    const originalPdf = await this.loadPdf(sub.original_pdf_key, sub.original_pdf_blob);

    if (!originalPdf) {
      this.audit(submissionId, 'completion_failed', 'system@pumasi.ai', 'Pumasi Sign Engine', undefined, {
        reason: 'original_document_unavailable',
      });
      return false;
    }

    const allSubmitters: SignerInfo[] = this.all<any>(
      `SELECT s.id, s.name, s.email, s.role, s.signed_at, s.ip_address, s.user_agent, s.signature_blob,
              c.disclosure_version, c.accepted_at, c.reviewed_document_hash
         FROM submitters s LEFT JOIN signer_consents c ON c.submitter_id = s.id
        WHERE s.submission_id = ? AND s.is_cc = 0`,
      submissionId,
    ).map((s: any) => ({
      id: s.id, name: s.name, email: s.email, role: s.role,
      signedAt: s.signed_at, ipAddress: s.ip_address, userAgent: s.user_agent,
      signatureImage: s.signature_blob ? new Uint8Array(s.signature_blob) : undefined,
      consentVersion: s.disclosure_version, consentAcceptedAt: s.accepted_at,
      reviewedDocumentHash: s.reviewed_document_hash,
    }));

    const typeMap: Record<string, PlacedField['type']> = {
      signature: 'signature', initials: 'initial', initial: 'initial',
      name: 'name', date: 'date', text: 'text', checkbox: 'checkbox',
      dropdown: 'text', radio: 'text', label: 'text',
    };
    const allFields: PlacedField[] = this.all<any>(
      `SELECT id, submitter_id, type, page, x, y, width, height, value, default_value FROM submission_fields WHERE submission_id = ?`,
      submissionId,
    ).map((f: any) => {
      const selectedMark = (f.type === 'signature' || f.type === 'initials') && f.value
        ? this.one<{ image_blob: ArrayBuffer }>(
            `SELECT image_blob FROM signatures WHERE id = ? AND submitter_id = ?`, f.value, f.submitter_id,
          )
        : null;
      return {
        id: f.id, signerId: f.submitter_id,
        type: typeMap[f.type] ?? 'text',
        // The web contract is 0-based pages; stamping's PlacedField is 1-based.
        page: f.page + 1, x: f.x, y: f.y, width: f.width, height: f.height,
        value: f.type === 'attachment'
          ? (this.one<{ filename: string }>(`SELECT filename FROM attachments WHERE id = ?`, f.value)?.filename ?? '')
          : f.type === 'label' ? (f.default_value ?? f.value ?? '') : (f.value ?? ''),
        signatureImage: selectedMark?.image_blob ? new Uint8Array(selectedMark.image_blob) : undefined,
      };
    });

    const attachments: { filename: string; contentType: string; bytes: Uint8Array }[] = [];
    for (const row of this.all<any>(
      `SELECT DISTINCT a.* FROM attachments a
       JOIN submission_fields f ON f.value = a.id
       WHERE f.submission_id = ? AND f.type = 'attachment'`, submissionId,
    )) {
      const stored = row.data_key ? await this.docs()?.getDocument(row.data_key) : null;
      const bytes = stored?.data ?? (row.data_blob ? new Uint8Array(row.data_blob) : null);
      if (!bytes) {
        this.audit(submissionId, 'completion_failed', 'system@pumasi.ai', 'Pumasi Sign Engine', undefined, {
          reason: 'attachment_unavailable', attachmentId: row.id,
        });
        return false;
      }
      attachments.push({ filename: row.filename, contentType: row.content_type, bytes });
    }

    const stampRes = await stampAndCertifyPdf({
      originalPdfBytes: originalPdf,
      fields: allFields,
      signers: allSubmitters,
      envelopeUid: sub.public_uid,
      documentTitle: sub.title,
      completedAt: now,
      attachments,
    });
    const completedKey = await this.storePdf('completed', submissionId, stampRes.stampedPdfBytes);
    const certificateKey = await this.storePdf('certificates', submissionId, stampRes.certificatePdfBytes);
    const certificateHash = await this.sha256(stampRes.certificatePdfBytes);
    this.sql.exec(
      `UPDATE submissions SET status = 'completed', completed_at = ?, completed_pdf_blob = ?, completed_pdf_key = ?,
         certificate_pdf_blob = ?, certificate_pdf_key = ?, original_hash = ?, completed_hash = ?, certificate_hash = ?, updated_at = ? WHERE id = ?`,
      now, completedKey ? null : stampRes.stampedPdfBytes, completedKey,
      certificateKey ? null : stampRes.certificatePdfBytes, certificateKey,
      stampRes.originalHash, stampRes.completedHash, certificateHash, now, submissionId,
    );
    this.audit(submissionId, 'completed', 'system@pumasi.ai', 'Pumasi Sign Engine', undefined, {
      originalHash: stampRes.originalHash, completedHash: stampRes.completedHash, certificateHash,
    });

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
    const owner = this.one<{ id: string }>(`SELECT id FROM users WHERE email = ?`, sub.created_by);
    if (owner) {
      const alreadyNotified = new Set([
        sub.created_by.toLowerCase(),
        ...this.all<{ email: string }>(`SELECT email FROM submitters WHERE submission_id = ?`, submissionId)
          .map((row) => row.email.toLowerCase()),
      ]);
      for (const archive of this.all<{ email: string }>(
        `SELECT email FROM archive_recipients WHERE owner_id = ? ORDER BY email`, owner.id,
      )) {
        if (alreadyNotified.has(archive.email.toLowerCase())) continue;
        const delivered = await this.mailOrLog(
          archive.email,
          `Archive copy: "${sub.title}" is fully signed`,
          `The completed envelope "${sub.title}" is attached for your organization's records.\n\nThis automatic archive copy was configured by the workspace administrator.\n\n— Pumasi Sign`,
          this.mailHtml('Completed envelope archive copy', [
            `The completed envelope "${sub.title}" is attached for your organization's records.`,
            'This automatic archive copy was configured by the workspace administrator.',
          ]),
          [
            { filename: `${sub.title}-completed.pdf`, contentType: 'application/pdf', bytes: stampRes.stampedPdfBytes },
            { filename: `${sub.title}-certificate.pdf`, contentType: 'application/pdf', bytes: stampRes.certificatePdfBytes },
          ],
        );
        this.audit(submissionId, delivered ? 'archive_copy_sent' : 'archive_copy_failed', archive.email, 'Archive recipient');
      }
    }
    return true;
  }
}
