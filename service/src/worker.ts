/**
 * Pumasi Sign Cloudflare Worker Entrypoint.
 */

import { PumasiSignService } from './durable.js';
import { convertOfficeToPdfViaGraph } from './convert/graph.js';
import { submitFeedbackToGitHub } from './feedback.js';

export { PumasiSignService };

/**
 * The one Durable Object this product has.
 *
 * `idFromName` is called with this constant on EVERY path — the request path
 * below and the scheduled sweep — because there is exactly one instance and
 * every user, session, envelope, submitter and audit row lives in its single
 * SQLite store. Two literals that agree today fork tomorrow
 * (pumasi/lessons/L-007), and here the fork would be a cron sweeping an empty
 * second store and reporting success having expired nothing. spec/0007 §S0.2.
 */
const SIGN_SERVICE_NAME = 'pumasi-sign-main';

/**
 * The sweep's path inside the Durable Object. Only `scheduled()` builds a
 * request for it, and it reaches the object through `stub.fetch()` — never
 * through this worker's own `fetch()`, which refuses the prefix outright.
 *
 * It is NOT under `/api/`: everything under `/api/` is forwarded to the
 * Durable Object, so a sweep route there would be reachable by anyone who
 * guessed it. Nothing here is protected by the path being obscure — this
 * repository is public by intent (CHARTER P2) and the name is written three
 * lines above the guard. The guard is the protection. spec/0007 §S2c.
 */
const INTERNAL_PREFIX = '/__internal/';

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

    // Before anything else, including the CORS pre-flight, so that nothing
    // about the internal surface is observable from the wire. A-415.
    if (path.startsWith(INTERNAL_PREFIX)) {
      return Response.json({ error: 'Not found' }, { status: 404 });
    }

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
      // The single global DO shard — the same one scheduled() sweeps.
      const id = env.SIGN_SERVICE.idFromName(SIGN_SERVICE_NAME);
      const stub = env.SIGN_SERVICE.get(id);
      return stub.fetch(req);
    }

    // 5. Serve Frontend Static Assets (Vue 3 SPA)
    if (env.ASSETS) {
      return env.ASSETS.fetch(req);
    }

    return new Response('Pumasi Sign Edge Service', { status: 200 });
  },

  /**
   * The expiry sweep — wrangler.jsonc's `triggers.crons`, hourly on the hour.
   *
   * Flips envelopes past their `expires_at` deadline to `expired`, so that the
   * deadline the Send wizard asks the sender for is a deadline the service
   * keeps. spec/0007.
   *
   * THE THROW IS LOAD-BEARING. A `scheduled` handler that swallows a failure
   * is a cron reporting success having expired nothing — pumasi/lessons/L-006
   * at infrastructure scale, the same failure
   * .github/scripts/assert-service-suite-ran.sh exists to stop one level down.
   * Throwing puts it in Cloudflare's cron invocation log, where someone can
   * see it.
   */
  async scheduled(_event: ScheduledController, env: Env, _ctx: ExecutionContext): Promise<void> {
    const stub = env.SIGN_SERVICE.get(env.SIGN_SERVICE.idFromName(SIGN_SERVICE_NAME));
    const res = await stub.fetch(
      new Request(`https://sign.internal${INTERNAL_PREFIX}expire`, { method: 'POST' }),
    );
    if (!res.ok) {
      throw new Error(`expiry sweep failed: ${res.status} ${await res.text()}`);
    }
  },
};
