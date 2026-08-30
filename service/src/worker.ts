/**
 * Pumasi Sign Cloudflare Worker Entrypoint.
 */

import { PumasiSignService } from './durable.js';
import { convertOfficeToPdfViaGraph } from './convert/graph.js';
import { submitFeedbackToGitHub } from './feedback.js';

export { PumasiSignService };

export interface Env {
  SIGN_SERVICE: DurableObjectNamespace;
  ASSETS?: Fetcher;
  DOCUMENTS?: any; // R2 Bucket binding
  BASE_URL?: string;
  GITHUB_FEEDBACK_TOKEN?: string;
  GITHUB_FEEDBACK_REPO?: string;
  GMAIL_SA_KEY?: string;
  MAIL_IMPERSONATE?: string;
  MAIL_FROM_NAME?: string;
  MS_GRAPH_TENANT_ID?: string;
  MS_GRAPH_CLIENT_ID?: string;
  MS_GRAPH_CLIENT_SECRET?: string;
  MS_GRAPH_DRIVE_ID?: string;
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    const path = url.pathname;

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

    // 2. Feedback Submission -> GitHub Issues
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
          payload.userEmail = formData.get('userEmail') || '';
          const contextRaw = formData.get('context');
          if (contextRaw && typeof contextRaw === 'string') {
            try { payload.context = JSON.parse(contextRaw); } catch {}
          }
          const errorsRaw = formData.get('errors');
          if (errorsRaw && typeof errorsRaw === 'string') {
            try { payload.errors = JSON.parse(errorsRaw); } catch {}
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

    // 3. Office 365 Cloud Document Conversion
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

    // 4. Forward all API signing, templates, and submissions to Durable Object
    if (path.startsWith('/api/')) {
      if (!env.SIGN_SERVICE) {
        return Response.json({ error: 'Durable Object binding SIGN_SERVICE not available' }, { status: 500 });
      }
      // Single global DO shard or multi-tenant by domain/org
      const id = env.SIGN_SERVICE.idFromName('pumasi-sign-main');
      const stub = env.SIGN_SERVICE.get(id);
      return stub.fetch(req);
    }

    // 5. Serve Frontend Static Assets (Vue 3 SPA)
    if (env.ASSETS) {
      return env.ASSETS.fetch(req);
    }

    return new Response('Pumasi Sign Edge Service', { status: 200 });
  },
};
