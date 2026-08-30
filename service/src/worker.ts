/**
 * Pumasi Sign Cloudflare Worker Entrypoint.
 */

import { stampAndCertifyPdf, PlacedField, SignerInfo } from './core/stamping.js';
import { convertOfficeToPdfViaGraph } from './convert/graph.js';
import { R2SignStorage } from './storage/r2.js';
import { submitFeedbackToGitHub } from './feedback.js';

export interface Env {
  DOCUMENTS: any; // R2 Bucket binding
  BASE_URL?: string;
  GITHUB_FEEDBACK_TOKEN?: string;
  GITHUB_FEEDBACK_REPO?: string;
  MS_GRAPH_TENANT_ID?: string;
  MS_GRAPH_CLIENT_ID?: string;
  MS_GRAPH_CLIENT_SECRET?: string;
  MS_GRAPH_DRIVE_ID?: string;
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    const path = url.pathname;
    const storage = new R2SignStorage(env.DOCUMENTS);

    // CORS Headers for API calls
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    if (req.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    // 1. Health Check
    if (path === '/api/health' || path === '/healthz') {
      return Response.json(
        { status: 'ok', service: 'pumasi-sign', time: new Date().toISOString() },
        { headers: corsHeaders }
      );
    }

    // 2. Feedback Submission
    if (path === '/api/feedback' && req.method === 'POST') {
      try {
        let payload: any = {};
        const contentType = req.headers.get('content-type') || '';
        
        if (contentType.includes('application/json')) {
          payload = await req.json();
        } else if (contentType.includes('multipart/form-data') || contentType.includes('application/x-www-form-urlencoded')) {
          const formData = await req.formData();
          payload.message = formData.get('message') || '';
          payload.type = formData.get('type') || 'feedback';
          payload.screenshotBase64 = formData.get('screenshot') || '';
          const contextRaw = formData.get('context');
          if (contextRaw && typeof contextRaw === 'string') {
            try { payload.context = JSON.parse(contextRaw); } catch {}
          }
        }

        const result = await submitFeedbackToGitHub(payload, {
          GITHUB_FEEDBACK_TOKEN: env.GITHUB_FEEDBACK_TOKEN,
          GITHUB_FEEDBACK_REPO: env.GITHUB_FEEDBACK_REPO || 'pumasi-ai/pumasi-sign',
        });

        return Response.json(result, { status: result.ok ? 200 : 500, headers: corsHeaders });
      } catch (err: any) {
        return Response.json({ ok: false, error: err.message }, { status: 500, headers: corsHeaders });
      }
    }

    // 3. Document Stamping & Completion API
    if (path === '/api/stamping/complete' && req.method === 'POST') {
      try {
        const body: any = await req.json();
        const { documentKey, fields, signers, envelopeUid, documentTitle } = body;

        let pdfBytes: Uint8Array;
        if (documentKey) {
          const doc = await storage.getDocument(documentKey);
          if (!doc) {
            return Response.json({ error: 'Original document not found' }, { status: 404, headers: corsHeaders });
          }
          pdfBytes = doc.data;
        } else if (body.pdfBase64) {
          const raw = atob(body.pdfBase64);
          pdfBytes = new Uint8Array(raw.length);
          for (let i = 0; i < raw.length; i++) pdfBytes[i] = raw.charCodeAt(i);
        } else {
          return Response.json({ error: 'Missing documentKey or pdfBase64' }, { status: 400, headers: corsHeaders });
        }

        const result = await stampAndCertifyPdf({
          originalPdfBytes: pdfBytes,
          fields: fields as PlacedField[],
          signers: signers as SignerInfo[],
          envelopeUid: envelopeUid || `env-${crypto.randomUUID().slice(0, 8)}`,
          documentTitle: documentTitle || 'Signed Agreement',
          completedAt: new Date().toISOString(),
        });

        const completedKey = `completed/${envelopeUid || crypto.randomUUID()}.pdf`;
        if (env.DOCUMENTS) {
          await storage.putDocument(completedKey, result.stampedPdfBytes, 'application/pdf');
        }

        return Response.json({
          ok: true,
          completedKey,
          originalHash: result.originalHash,
          completedHash: result.completedHash,
          pageCount: result.pageCount,
        }, { headers: corsHeaders });
      } catch (err: any) {
        return Response.json({ error: err.message }, { status: 500, headers: corsHeaders });
      }
    }

    // 4. Native Office 365 Cloud Document Conversion
    if (path === '/api/convert' && req.method === 'POST') {
      if (!env.MS_GRAPH_TENANT_ID || !env.MS_GRAPH_CLIENT_ID || !env.MS_GRAPH_CLIENT_SECRET || !env.MS_GRAPH_DRIVE_ID) {
        return Response.json({ error: 'Office 365 conversion is not configured' }, { status: 501, headers: corsHeaders });
      }

      try {
        const formData = await req.formData();
        const file = formData.get('file') as File | null;
        if (!file) {
          return Response.json({ error: 'No file uploaded' }, { status: 400, headers: corsHeaders });
        }

        const ext = file.name.split('.').pop() || '';
        const arrayBuffer = await file.arrayBuffer();
        const fileBytes = new Uint8Array(arrayBuffer);

        const pdfBytes = await convertOfficeToPdfViaGraph(fileBytes, ext, {
          tenantId: env.MS_GRAPH_TENANT_ID,
          clientId: env.MS_GRAPH_CLIENT_ID,
          clientSecret: env.MS_GRAPH_CLIENT_SECRET,
          driveId: env.MS_GRAPH_DRIVE_ID,
        });

        if (!pdfBytes) {
          return Response.json({ error: 'Conversion failed or format unsupported' }, { status: 422, headers: corsHeaders });
        }

        return new Response(pdfBytes.buffer as BodyInit, {
          headers: {
            'Content-Type': 'application/pdf',
            'Content-Disposition': `attachment; filename="${file.name.replace(/\.[^/.]+$/, '')}.pdf"`,
            ...corsHeaders,
          },
        });
      } catch (err: any) {
        return Response.json({ error: err.message }, { status: 500, headers: corsHeaders });
      }
    }

    // 5. Document Serving from R2
    if (path.startsWith('/api/documents/') && req.method === 'GET') {
      const key = path.replace('/api/documents/', '');
      const doc = await storage.getDocument(key);
      if (!doc) {
        return new Response('Not Found', { status: 404 });
      }
      return new Response(doc.data.buffer as BodyInit, {
        headers: {
          'Content-Type': doc.contentType,
          'Cache-Control': 'public, max-age=3600',
          ...corsHeaders,
        },
      });
    }

    // Fallback: 404 for unmatched API routes
    if (path.startsWith('/api/')) {
      return Response.json({ error: 'Route not found' }, { status: 404, headers: corsHeaders });
    }

    return new Response('Pumasi Sign Edge Service', { status: 200 });
  },
};
