/**
 * Pumasi Sign Durable Object — SQLite State & Signing Logic.
 */

import { stampAndCertifyPdf, PlacedField, SignerInfo } from './core/stamping.js';

export interface Env {
  SIGN_SERVICE: DurableObjectNamespace;
  BASE_URL?: string;
  GITHUB_FEEDBACK_TOKEN?: string;
  GITHUB_FEEDBACK_REPO?: string;
}

export class PumasiSignService implements DurableObject {
  private sql: SqlStorage;

  constructor(private state: DurableObjectState, private env: Env) {
    this.sql = state.storage.sql;
    this.initSchema();
  }

  private initSchema() {
    this.sql.exec(`
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
  }

  async fetch(req: Request): Promise<Response> {
    const url = new URL(req.url);
    const path = url.pathname;
    const method = req.method;

    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    if (method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    // ── Templates API ────────────────────────────────────────────────────────
    if (path === '/api/templates' && method === 'GET') {
      const cursor = this.sql.exec(`SELECT id, name, created_by, page_count, fields_json, is_shared, created_at FROM templates WHERE archived_at IS NULL ORDER BY created_at DESC`);
      const items = Array.from(cursor).map((r: any) => ({
        ...r,
        fields: JSON.parse(r.fields_json || '[]'),
      }));
      return Response.json(items, { headers: corsHeaders });
    }

    if (path === '/api/templates' && method === 'POST') {
      const body: any = await req.json();
      const id = `tpl-${crypto.randomUUID().slice(0, 10)}`;
      const now = new Date().toISOString();
      const pdfBytes = body.pdfBase64 ? Uint8Array.from(atob(body.pdfBase64), c => c.charCodeAt(0)) : null;

      this.sql.exec(
        `INSERT INTO templates (id, name, created_by, pdf_blob, page_count, fields_json, is_adhoc, is_shared, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        id,
        body.name || 'Untitled Template',
        body.createdBy || 'admin@pumasi.ai',
        pdfBytes,
        body.pageCount || 1,
        JSON.stringify(body.fields || []),
        body.isAdhoc ? 1 : 0,
        body.isShared ? 1 : 0,
        now
      );

      return Response.json({ id, name: body.name, created_at: now }, { status: 201, headers: corsHeaders });
    }

    // ── Submissions API (Envelopes) ─────────────────────────────────────────
    if (path === '/api/submissions' && method === 'GET') {
      const cursor = this.sql.exec(`SELECT id, public_uid, title, message, created_by, status, completed_at, created_at, updated_at FROM submissions ORDER BY created_at DESC`);
      const submissions = Array.from(cursor);
      return Response.json(submissions, { headers: corsHeaders });
    }

    if (path === '/api/submissions' && method === 'POST') {
      const body: any = await req.json();
      const id = `sub-${crypto.randomUUID().slice(0, 10)}`;
      const publicUid = crypto.randomUUID().slice(0, 8);
      const now = new Date().toISOString();
      const pdfBytes = body.pdfBase64 ? Uint8Array.from(atob(body.pdfBase64), c => c.charCodeAt(0)) : null;

      const status = body.sendImmediately ? 'pending' : 'draft';

      this.sql.exec(
        `INSERT INTO submissions (id, public_uid, title, message, created_by, status, original_pdf_blob, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        id,
        publicUid,
        body.title || 'Untitled Agreement',
        body.message || '',
        body.createdBy || 'admin@pumasi.ai',
        status,
        pdfBytes,
        now,
        now
      );

      // Add Submitters (Signers)
      const submitters: any[] = [];
      for (const [index, s] of (body.submitters || []).entries()) {
        const subId = `subtr-${crypto.randomUUID().slice(0, 8)}`;
        const token = crypto.randomUUID().replace(/-/g, '') + crypto.randomUUID().slice(0, 8);
        this.sql.exec(
          `INSERT INTO submitters (id, submission_id, name, email, role, signing_order, token, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)`,
          subId,
          id,
          s.name,
          s.email,
          s.role || 'Signer',
          s.signingOrder || index + 1,
          token,
          now
        );
        submitters.push({ id: subId, name: s.name, email: s.email, role: s.role, token });
      }

      // Add Fields
      for (const f of body.fields || []) {
        const fieldId = `fld-${crypto.randomUUID().slice(0, 8)}`;
        this.sql.exec(
          `INSERT INTO submission_fields (id, submission_id, submitter_id, type, page, x, y, width, height, value)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
          fieldId,
          id,
          f.submitterId || submitters[0]?.id,
          f.type,
          f.page,
          f.x,
          f.y,
          f.width,
          f.height,
          f.value || ''
        );
      }

      // Record Audit Event
      this.sql.exec(
        `INSERT INTO audit_events (id, submission_id, event_type, actor_email, actor_name, created_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
        `evt-${crypto.randomUUID().slice(0, 8)}`,
        id,
        status === 'pending' ? 'sent' : 'created_draft',
        body.createdBy || 'admin@pumasi.ai',
        'Pumasi Sign',
        now
      );

      return Response.json({
        id,
        publicUid,
        title: body.title,
        status,
        submitters,
        created_at: now,
      }, { status: 201, headers: corsHeaders });
    }

    if (path.startsWith('/api/submissions/') && method === 'GET') {
      const parts = path.split('/');
      const id = parts[3];

      if (parts[4] === 'pdf') {
        const sub = Array.from(this.sql.exec(`SELECT original_pdf_blob, completed_pdf_blob, title, status FROM submissions WHERE id = ? OR public_uid = ?`, id, id))[0] as any;
        if (!sub) return new Response('Not Found', { status: 404 });
        const pdfData = sub.completed_pdf_blob || sub.original_pdf_blob;
        if (!pdfData) return new Response('PDF content not available', { status: 404 });
        return new Response(pdfData, {
          headers: {
            'Content-Type': 'application/pdf',
            'Content-Disposition': `inline; filename="${sub.title.replace(/[^a-zA-Z0-9_-]/g, '_')}.pdf"`,
            ...corsHeaders,
          },
        });
      }

      const sub = Array.from(this.sql.exec(`SELECT id, public_uid, title, message, created_by, status, completed_at, created_at FROM submissions WHERE id = ? OR public_uid = ?`, id, id))[0] as any;
      if (!sub) return Response.json({ error: 'Submission not found' }, { status: 404, headers: corsHeaders });

      const submitters = Array.from(this.sql.exec(`SELECT id, name, email, role, signing_order, token, status, signed_at FROM submitters WHERE submission_id = ? ORDER BY signing_order ASC`, sub.id));
      const fields = Array.from(this.sql.exec(`SELECT id, submitter_id, type, page, x, y, width, height, value FROM submission_fields WHERE submission_id = ?`, sub.id));
      const audit = Array.from(this.sql.exec(`SELECT event_type, actor_email, actor_name, ip_address, created_at FROM audit_events WHERE submission_id = ? ORDER BY created_at ASC`, sub.id));

      return Response.json({ ...sub, submitters, fields, audit }, { headers: corsHeaders });
    }

    // ── Public Signing Flow (/api/signing/:token) ───────────────────────────
    if (path.startsWith('/api/signing/') && method === 'GET') {
      const token = path.replace('/api/signing/', '');
      const submitter = Array.from(this.sql.exec(`SELECT id, submission_id, name, email, role, status FROM submitters WHERE token = ?`, token))[0] as any;
      if (!submitter) {
        return Response.json({ error: 'Invalid or expired signing link' }, { status: 404, headers: corsHeaders });
      }

      const sub = Array.from(this.sql.exec(`SELECT id, public_uid, title, message, status, original_pdf_blob, completed_pdf_blob FROM submissions WHERE id = ?`, submitter.submission_id))[0] as any;
      if (!sub || sub.status === 'cancelled') {
        return Response.json({ error: 'This agreement is no longer active' }, { status: 410, headers: corsHeaders });
      }

      const fields = Array.from(this.sql.exec(`SELECT id, submitter_id, type, page, x, y, width, height, value FROM submission_fields WHERE submission_id = ?`, sub.id));

      return Response.json({
        submitter: {
          id: submitter.id,
          name: submitter.name,
          email: submitter.email,
          role: submitter.role,
          status: submitter.status,
        },
        document: {
          id: sub.id,
          publicUid: sub.public_uid,
          title: sub.title,
          message: sub.message,
          status: sub.status,
        },
        fields,
      }, { headers: corsHeaders });
    }

    if (path.startsWith('/api/signing/') && method === 'POST') {
      const token = path.replace('/api/signing/', '');
      const submitter = Array.from(this.sql.exec(`SELECT id, submission_id, name, email, role, status FROM submitters WHERE token = ?`, token))[0] as any;
      if (!submitter) {
        return Response.json({ error: 'Invalid signing token' }, { status: 404, headers: corsHeaders });
      }

      const body: any = await req.json();
      const now = new Date().toISOString();
      const clientIp = req.headers.get('cf-connecting-ip') || req.headers.get('x-forwarded-for') || '127.0.0.1';
      const userAgent = req.headers.get('user-agent') || 'Browser';

      // 1. Update Submitter status and signature
      let sigBytes: Uint8Array | null = null;
      if (body.signatureBase64 && body.signatureBase64.includes(',')) {
        const raw = atob(body.signatureBase64.split(',')[1]);
        sigBytes = new Uint8Array(raw.length);
        for (let i = 0; i < raw.length; i++) sigBytes[i] = raw.charCodeAt(i);
      }

      this.sql.exec(
        `UPDATE submitters SET status = 'signed', signed_at = ?, ip_address = ?, user_agent = ?, signature_blob = ? WHERE id = ?`,
        now,
        clientIp,
        userAgent,
        sigBytes,
        submitter.id
      );

      // 2. Update Field Values
      for (const [fieldId, val] of Object.entries(body.fieldValues || {})) {
        this.sql.exec(
          `UPDATE submission_fields SET value = ? WHERE id = ? AND submission_id = ?`,
          String(val),
          fieldId,
          submitter.submission_id
        );
      }

      // 3. Record Audit Event
      this.sql.exec(
        `INSERT INTO audit_events (id, submission_id, event_type, actor_email, actor_name, ip_address, details_json, created_at)
         VALUES (?, ?, 'signed', ?, ?, ?, ?, ?)`,
        `evt-${crypto.randomUUID().slice(0, 8)}`,
        submitter.submission_id,
        submitter.email,
        submitter.name,
        clientIp,
        JSON.stringify({ userAgent }),
        now
      );

      // 4. Check if all submitters have signed
      const remaining = Array.from(this.sql.exec(
        `SELECT COUNT(*) as count FROM submitters WHERE submission_id = ? AND status != 'signed'`,
        submitter.submission_id
      ))[0] as any;

      if (remaining.count === 0) {
        // All signed! Execute Pure Core Stamping & Certification
        const sub = Array.from(this.sql.exec(
          `SELECT id, public_uid, title, original_pdf_blob FROM submissions WHERE id = ?`,
          submitter.submission_id
        ))[0] as any;

        const allSubmitters = Array.from(this.sql.exec(
          `SELECT id, name, email, role, signed_at, ip_address, user_agent, signature_blob FROM submitters WHERE submission_id = ?`,
          submitter.submission_id
        )).map((s: any) => ({
          id: s.id,
          name: s.name,
          email: s.email,
          role: s.role,
          signedAt: s.signed_at,
          ipAddress: s.ip_address,
          userAgent: s.user_agent,
          signatureImage: s.signature_blob ? new Uint8Array(s.signature_blob) : undefined,
        }));

        const allFields = Array.from(this.sql.exec(
          `SELECT id, submitter_id, type, page, x, y, width, height, value FROM submission_fields WHERE submission_id = ?`,
          submitter.submission_id
        )).map((f: any) => ({
          id: f.id,
          signerId: f.submitter_id,
          type: f.type as any,
          page: f.page,
          x: f.x,
          y: f.y,
          width: f.width,
          height: f.height,
          value: f.value,
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
            now,
            stampRes.stampedPdfBytes,
            now,
            sub.id
          );

          this.sql.exec(
            `INSERT INTO audit_events (id, submission_id, event_type, actor_email, actor_name, details_json, created_at)
             VALUES (?, ?, 'completed', 'system@pumasi.ai', 'Pumasi Sign Engine', ?, ?)`,
            `evt-${crypto.randomUUID().slice(0, 8)}`,
            sub.id,
            JSON.stringify({ originalHash: stampRes.originalHash, completedHash: stampRes.completedHash }),
            now
          );
        }
      }

      return Response.json({ ok: true, status: remaining.count === 0 ? 'completed' : 'signed' }, { headers: corsHeaders });
    }

    return Response.json({ error: 'Endpoint not found' }, { status: 404, headers: corsHeaders });
  }
}
