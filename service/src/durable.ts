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
 */

import { stampAndCertifyPdf, PlacedField, SignerInfo } from './core/stamping.js';
import { sendMail, mailConfigured, MailEnv } from './mail.js';

export interface Env extends MailEnv {
  SIGN_SERVICE: DurableObjectNamespace;
  BASE_URL?: string;
}

const SESSION_TTL_DAYS = 30;
const SIGNER_TTL_HOURS = 24;
const CODE_TTL_MIN = 15;
const RESEND_GUARD_SEC = 60;

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
      `ALTER TABLE submission_fields ADD COLUMN required INTEGER DEFAULT 1`,
      `ALTER TABLE submission_fields ADD COLUMN font_size REAL`,
      `ALTER TABLE submission_fields ADD COLUMN options_json TEXT`,
      `ALTER TABLE submission_fields ADD COLUMN default_value TEXT`,
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

  private async mailOrLog(to: string, subject: string, text: string): Promise<boolean> {
    try {
      await sendMail(this.env, { to, subject, text });
      return true;
    } catch (err) {
      console.warn(`[mail] send to ${to} failed: ${(err as Error).message}`);
      return false;
    }
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

  /** Field rows → the frontend's FieldDef shape. Role comes from the owning submitter. */
  private fieldDefs(submissionId: string): any[] {
    const roleById = new Map(
      this.all<{ id: string; role: string }>(`SELECT id, role FROM submitters WHERE submission_id = ?`, submissionId)
        .map((s) => [s.id, s.role || 'Signer']),
    );
    return this.all(
      `SELECT id, submitter_id, type, page, x, y, width, height, value, required, font_size, options_json, default_value
         FROM submission_fields WHERE submission_id = ?`, submissionId,
    ).map((f: any) => ({
      id: f.id,
      type: f.type,
      role: f.type === 'label' ? '' : (roleById.get(f.submitter_id) ?? ''),
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
      `SELECT COUNT(*) AS n FROM submitters WHERE submission_id = ? AND signing_order < ? AND status NOT IN ('signed')`,
      submitter.submission_id, submitter.signing_order,
    );
    return (blocking?.n ?? 0) === 0;
  }

  /** Email the pending signers whose turn it now is. */
  private async inviteCurrentTurn(submissionId: string): Promise<void> {
    const sub = this.one<any>(`SELECT id, title, created_by FROM submissions WHERE id = ?`, submissionId);
    if (!sub) return;
    const sender = this.one<UserRow>(`SELECT id, email, name, provider FROM users WHERE email = ?`, sub.created_by);
    const senderName = sender?.name || sub.created_by;
    const pending = this.all<any>(
      `SELECT id, name, email, token, signing_order FROM submitters
        WHERE submission_id = ? AND status = 'pending' ORDER BY signing_order ASC`, submissionId,
    );
    if (!pending.length) return;
    const firstOrder = pending[0].signing_order;
    for (const s of pending.filter((p) => p.signing_order === firstOrder)) {
      const link = `${this.baseUrl()}/sign/t/${s.token}`;
      const ok = await this.mailOrLog(
        s.email,
        `${senderName} sent you "${sub.title}" to sign`,
        `Hello ${s.name},\n\n${senderName} has requested your signature on "${sub.title}".\n\nReview and sign here:\n${link}\n\nYou will be asked for a verification code sent to this email address before the document opens.\n\n— Pumasi Sign`,
      );
      if (ok) this.audit(submissionId, 'invite_sent', s.email, s.name);
    }
  }

  // ── request dispatch ────────────────────────────────────────────────────

  async fetch(req: Request): Promise<Response> {
    const url = new URL(req.url);
    const path = url.pathname;
    const method = req.method;
    try {
      return await this.route(req, path, method);
    } catch (err) {
      console.warn(`[sign] ${method} ${path} failed: ${(err as Error).message}`);
      return json({ error: 'Internal error' }, 500);
    }
  }

  private async route(req: Request, path: string, method: string): Promise<Response> {
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

      let user = this.one<UserRow>(`SELECT id, email, name, provider FROM users WHERE email = ?`, email);
      const now = new Date().toISOString();
      if (!user) {
        const userId = `usr-${crypto.randomUUID().slice(0, 8)}`;
        const name = String(body.name || email.split('@')[0].replace(/[._]/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()));
        this.sql.exec(
          `INSERT INTO users (id, email, name, provider, created_at) VALUES (?, ?, ?, 'email', ?)`,
          userId, email, name, now,
        );
        this.sql.exec(
          `INSERT INTO org_branding (id, owner_id, company_name, primary_color, created_at, updated_at)
           VALUES (?, ?, ?, '#1A56DB', ?, ?)`,
          `org-${crypto.randomUUID().slice(0, 8)}`, userId, `${name}'s Workspace`, now, now,
        );
        user = { id: userId, email, name, provider: 'email' };
      }

      const token = newToken();
      this.sql.exec(
        `INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)`,
        token, user.id, new Date(Date.now() + SESSION_TTL_DAYS * 86400_000).toISOString(), now,
      );

      const branding = this.one(`SELECT company_name, logo_data_url, primary_color, welcome_message FROM org_branding WHERE owner_id = ?`, user.id);
      return json(
        {
          ok: true,
          user: { id: user.id, email: user.email, name: user.name, is_admin: true, can_send: true },
          branding: branding || { company_name: 'Pumasi Sign', primary_color: '#1A56DB' },
        },
        200,
        { 'Set-Cookie': setCookie('sign_session', token, SESSION_TTL_DAYS * 86400) },
      );
    }

    if (path === '/api/auth/me' && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      return json({ id: user.id, email: user.email, name: user.name, is_admin: true, can_send: true });
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

    // ── owner: templates ──────────────────────────────────────────────────
    if (path === '/api/templates' && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      return json(this.all(
        `SELECT id, name, page_count, is_shared, created_at FROM templates
          WHERE created_by = ? AND archived_at IS NULL ORDER BY created_at DESC`, user.email,
      ));
    }

    if (path === '/api/templates' && method === 'POST') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const body: any = await req.json();
      const id = `tpl-${crypto.randomUUID().slice(0, 8)}`;
      const pdfBytes = body.pdfBase64 ? dataUrlToBytes(`,${body.pdfBase64}`) : null;
      this.sql.exec(
        `INSERT INTO templates (id, name, created_by, pdf_blob, page_count, fields_json, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
        id, String(body.name || 'Untitled Template'), user.email, pdfBytes,
        Number(body.pageCount) || 1, JSON.stringify(body.fields || []), new Date().toISOString(),
      );
      return json({ id, name: body.name }, 201);
    }

    // ── owner: submissions ────────────────────────────────────────────────
    if (path === '/api/submissions' && method === 'GET') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const subs = this.all(
        `SELECT id, public_uid, title, message, created_by, status, completed_at, created_at, updated_at
           FROM submissions WHERE created_by = ? ORDER BY created_at DESC`, user.email,
      );
      for (const s of subs as any[]) {
        s.submitters = this.all(
          `SELECT id, name, email, role, signing_order, status, signed_at FROM submitters WHERE submission_id = ? ORDER BY signing_order ASC`,
          s.id,
        );
      }
      return json(subs);
    }

    if (path === '/api/submissions' && method === 'POST') {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const body: any = await req.json();
      const id = `sub-${crypto.randomUUID().slice(0, 10)}`;
      const publicUid = crypto.randomUUID().slice(0, 8);
      const now = new Date().toISOString();
      const pdfBytes = body.pdfBase64 ? dataUrlToBytes(`,${body.pdfBase64}`) : null;
      const status = body.sendImmediately ? 'pending' : 'draft';

      this.sql.exec(
        `INSERT INTO submissions (id, public_uid, title, message, created_by, status, original_pdf_blob, page_count, expires_at, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        id, publicUid, String(body.title || 'Untitled Agreement'), String(body.message || ''),
        user.email, status, pdfBytes, Number(body.pageCount) || 1, body.expiresAt ?? null, now, now,
      );

      const submitters: any[] = [];
      for (const [index, s] of (body.submitters || []).entries()) {
        const subId = `subtr-${crypto.randomUUID().slice(0, 8)}`;
        const token = newToken();
        this.sql.exec(
          `INSERT INTO submitters (id, submission_id, name, email, role, signing_order, token, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)`,
          subId, id, String(s.name || s.email), String(s.email).trim().toLowerCase(),
          s.role || 'Signer', Number(s.signingOrder) || index + 1, token, now,
        );
        submitters.push({ id: subId, name: s.name, email: s.email, role: s.role || 'Signer', token });
      }

      for (const f of body.fields || []) {
        this.sql.exec(
          `INSERT INTO submission_fields (id, submission_id, submitter_id, type, page, x, y, width, height, value, required, font_size, options_json, default_value)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
          `fld-${crypto.randomUUID().slice(0, 8)}`, id,
          f.submitterId || submitters[0]?.id || '', f.type, Number(f.page) || 0,
          Number(f.x) || 0, Number(f.y) || 0, Number(f.w ?? f.width) || 0, Number(f.h ?? f.height) || 0,
          f.value ?? '', f.required === false ? 0 : 1, f.font_size ?? null,
          f.options ? JSON.stringify(f.options) : null, f.default_value ?? null,
        );
      }

      this.audit(id, status === 'pending' ? 'sent' : 'created_draft', user.email, user.name);
      if (status === 'pending') await this.inviteCurrentTurn(id);

      return json({ id, publicUid, title: body.title, status, submitters, created_at: now }, 201);
    }

    // /api/submissions/:id[/pdf | /send | /remind | /cancel]
    if (path.startsWith('/api/submissions/')) {
      const user = this.sessionUser(req);
      if (!user) return json({ error: 'Not signed in' }, 401);
      const parts = path.split('/');
      const id = parts[3];
      const action = parts[4];
      const sub = this.one<any>(
        `SELECT id, public_uid, title, message, created_by, status, completed_at, expires_at, page_count, created_at FROM submissions
          WHERE (id = ? OR public_uid = ?) AND created_by = ?`, id, id, user.email,
      );
      if (!sub) return json({ error: 'Submission not found' }, 404);

      if (method === 'GET' && action === 'pdf') {
        const blobRow = this.one<any>(`SELECT original_pdf_blob, completed_pdf_blob FROM submissions WHERE id = ?`, sub.id);
        const pdfData = blobRow?.completed_pdf_blob || blobRow?.original_pdf_blob;
        if (!pdfData) return json({ error: 'PDF content not available' }, 404);
        return new Response(pdfData, {
          headers: {
            'Content-Type': 'application/pdf',
            'Content-Disposition': `inline; filename="${String(sub.title).replace(/[^a-zA-Z0-9_-]/g, '_')}.pdf"`,
            ...corsHeaders,
          },
        });
      }

      if (method === 'POST' && (action === 'send' || action === 'remind')) {
        if (sub.status === 'draft') {
          this.sql.exec(`UPDATE submissions SET status = 'pending', updated_at = ? WHERE id = ?`, new Date().toISOString(), sub.id);
          this.audit(sub.id, 'sent', user.email, user.name);
        } else {
          this.audit(sub.id, 'reminded', user.email, user.name);
        }
        await this.inviteCurrentTurn(sub.id);
        return json({ ok: true });
      }

      if (method === 'POST' && action === 'cancel') {
        this.sql.exec(`UPDATE submissions SET status = 'cancelled', updated_at = ? WHERE id = ?`, new Date().toISOString(), sub.id);
        this.audit(sub.id, 'cancelled', user.email, user.name);
        return json({ ok: true });
      }

      if (method === 'GET' && !action) {
        const submitters = this.all(
          `SELECT id, name, email, role, signing_order, token, status, signed_at FROM submitters WHERE submission_id = ? ORDER BY signing_order ASC`, sub.id,
        );
        const fields = this.fieldDefs(sub.id);
        const audit = this.all(
          `SELECT event_type, actor_email, actor_name, ip_address, created_at FROM audit_events WHERE submission_id = ? ORDER BY created_at ASC`, sub.id,
        );
        return json({ ...sub, submitters, fields, audit });
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
        `SELECT id, submission_id, name, email, role, status, signing_order FROM submitters WHERE id = ?`, submitterId,
      );
      if (!me) return json({ error: 'Unknown signer' }, 404);
      const submission = this.one<any>(
        `SELECT id, title, message, status, created_by, expires_at, page_count FROM submissions WHERE id = ?`, me.submission_id,
      );
      if (!submission) return json({ error: 'Unknown submission' }, 404);

      if (!signMatch[2] && method === 'GET') {
        const fields = this.fieldDefs(submission.id);
        const roleNames: Record<string, string> = {};
        for (const s of this.all<any>(`SELECT name, role FROM submitters WHERE submission_id = ?`, submission.id)) {
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
          my_fields: fields.filter((f: any) => {
            const row = this.one<{ submitter_id: string }>(`SELECT submitter_id FROM submission_fields WHERE id = ?`, f.id);
            return row?.submitter_id === me.id;
          }).map((f: any) => f.id),
          my_status: me.status,
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
        if (submission.status === 'cancelled' || submission.status === 'declined') {
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
          `SELECT COUNT(*) AS n FROM submitters WHERE submission_id = ? AND status != 'signed'`, submission.id,
        );

        if ((remaining?.n ?? 0) === 0) {
          await this.finalize(submission.id, now);
        } else {
          await this.inviteCurrentTurn(submission.id);
        }
        return json({ ok: true, status: (remaining?.n ?? 0) === 0 ? 'completed' : 'signed' });
      }

      if (signMatch[2] === 'decline' && method === 'POST') {
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
      const row = this.one<any>(`SELECT title, original_pdf_blob, completed_pdf_blob FROM submissions WHERE id = ?`, targetId);
      if (!row) return json({ error: 'Not found' }, 404);
      const pdf = kind === 'signed-pdf' ? row.completed_pdf_blob : row.original_pdf_blob;
      if (!pdf) return json({ error: 'Not available' }, 404);
      return new Response(pdf, {
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': `${kind === 'signed-pdf' ? 'attachment' : 'inline'}; filename="${String(row.title).replace(/[^a-zA-Z0-9_-]/g, '_')}.pdf"`,
          ...corsHeaders,
        },
      });
    }

    return json({ error: 'Endpoint not found' }, 404);
  }

  /** All signed: stamp, certify, store, notify everyone. */
  private async finalize(submissionId: string, now: string): Promise<void> {
    const sub = this.one<any>(
      `SELECT id, public_uid, title, created_by, original_pdf_blob FROM submissions WHERE id = ?`, submissionId,
    );
    if (!sub) return;

    const allSubmitters: SignerInfo[] = this.all<any>(
      `SELECT id, name, email, role, signed_at, ip_address, user_agent, signature_blob FROM submitters WHERE submission_id = ?`,
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

    if (sub.original_pdf_blob) {
      const stampRes = await stampAndCertifyPdf({
        originalPdfBytes: new Uint8Array(sub.original_pdf_blob),
        fields: allFields,
        signers: allSubmitters,
        envelopeUid: sub.public_uid,
        documentTitle: sub.title,
        completedAt: now,
      });
      this.sql.exec(
        `UPDATE submissions SET status = 'completed', completed_at = ?, completed_pdf_blob = ?, updated_at = ? WHERE id = ?`,
        now, stampRes.stampedPdfBytes, now, submissionId,
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
    );
    for (const s of this.all<any>(`SELECT name, email, token FROM submitters WHERE submission_id = ?`, submissionId)) {
      await this.mailOrLog(
        s.email,
        `"${sub.title}" is fully signed`,
        `Hello ${s.name},\n\nEveryone has signed "${sub.title}". You can retrieve the executed document any time:\n${this.baseUrl()}/sign/t/${s.token}\n\n— Pumasi Sign`,
      );
    }
  }
}
