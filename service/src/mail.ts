/**
 * Gmail API sender for Cloudflare Workers.
 *
 * pumasi.ai mail is Google Workspace-hosted; a service account with
 * domain-wide delegation sends as MAIL_IMPERSONATE via the Gmail REST API.
 * Workers cannot open SMTP connections, so this is the only viable transport.
 * The OAuth JWT is signed with WebCrypto — no SDK, stays wrangler-bundleable.
 */

const TOKEN_URL = 'https://oauth2.googleapis.com/token';
const SEND_URL = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send';
const SCOPE = 'https://www.googleapis.com/auth/gmail.send';

export interface MailEnv {
  GMAIL_SA_KEY?: string;
  MAIL_IMPERSONATE?: string;
  MAIL_FROM_NAME?: string;
}

const utf8 = (s: string): Uint8Array => new TextEncoder().encode(s);

function b64(bytes: Uint8Array): string {
  let s = '';
  for (const c of bytes) s += String.fromCharCode(c);
  return btoa(s);
}
const b64url = (bytes: Uint8Array): string =>
  b64(bytes).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

function pemToPkcs8(pem: string): ArrayBuffer {
  const body = pem.replace(/-----[A-Z ]+-----/g, '').replace(/\s+/g, '');
  const raw = atob(body);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes.buffer;
}

let cachedToken: { value: string; expiresAt: number; forUser: string } | undefined;

async function accessToken(saKeyJson: string, impersonate: string): Promise<string> {
  if (cachedToken && cachedToken.forUser === impersonate && cachedToken.expiresAt > Date.now() + 60_000) {
    return cachedToken.value;
  }
  const sa = JSON.parse(saKeyJson) as { client_email: string; private_key: string };
  const key = await crypto.subtle.importKey(
    'pkcs8',
    pemToPkcs8(sa.private_key),
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const now = Math.floor(Date.now() / 1000);
  const header = b64url(utf8(JSON.stringify({ alg: 'RS256', typ: 'JWT' })));
  const claims = b64url(utf8(JSON.stringify({
    iss: sa.client_email,
    sub: impersonate,
    scope: SCOPE,
    aud: TOKEN_URL,
    iat: now,
    exp: now + 3600,
  })));
  const payload = utf8(`${header}.${claims}`);
  const sig = new Uint8Array(
    await crypto.subtle.sign('RSASSA-PKCS1-v1_5', key, payload.buffer as ArrayBuffer),
  );
  const assertion = `${header}.${claims}.${b64url(sig)}`;

  const res = await fetch(TOKEN_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion,
    }),
  });
  if (!res.ok) throw new Error(`gmail token exchange failed: ${res.status} ${(await res.text()).slice(0, 200)}`);
  const tok = (await res.json()) as { access_token: string; expires_in: number };
  cachedToken = { value: tok.access_token, expiresAt: Date.now() + tok.expires_in * 1000, forUser: impersonate };
  return tok.access_token;
}

const encodeSubject = (s: string): string =>
  /^[\x20-\x7e]*$/.test(s) ? s : `=?utf-8?B?${b64(utf8(s))}?=`;

export function mailConfigured(env: MailEnv): boolean {
  return Boolean(env.GMAIL_SA_KEY && env.MAIL_IMPERSONATE);
}

/**
 * Send one email. Always carries a plain-text part; when `html` is given the
 * message goes out as multipart/alternative — mailbox providers score a
 * well-formed HTML+text pair better than bare plain text, which matters for
 * a young domain's inbox placement. Throws on failure — callers decide
 * whether that is fatal (login codes: yes) or logged (courtesy notices: no).
 */
export async function sendMail(
  env: MailEnv,
  msg: {
    to: string;
    subject: string;
    text: string;
    html?: string;
    attachments?: Array<{ filename: string; contentType: string; bytes: Uint8Array }>;
  },
): Promise<void> {
  if (!env.GMAIL_SA_KEY || !env.MAIL_IMPERSONATE) {
    throw new Error('mail is not configured (GMAIL_SA_KEY / MAIL_IMPERSONATE)');
  }
  const fromName = env.MAIL_FROM_NAME || 'Pumasi Sign';
  const headers = [
    `From: ${fromName} <${env.MAIL_IMPERSONATE}>`,
    `To: ${msg.to}`,
    `Reply-To: ${env.MAIL_IMPERSONATE}`,
    `Subject: ${encodeSubject(msg.subject)}`,
    'MIME-Version: 1.0',
  ];
  let raw: string;
  if (msg.attachments?.length) {
    const mixed = `=_pumasi_mixed_${crypto.randomUUID().replace(/-/g, '')}`;
    const alternative = `=_pumasi_alt_${crypto.randomUUID().replace(/-/g, '')}`;
    const body = msg.html
      ? [
          `Content-Type: multipart/alternative; boundary="${alternative}"`, '',
          `--${alternative}`, 'Content-Type: text/plain; charset=utf-8', '', msg.text,
          `--${alternative}`, 'Content-Type: text/html; charset=utf-8', '', msg.html,
          `--${alternative}--`,
        ]
      : ['Content-Type: text/plain; charset=utf-8', '', msg.text];
    const attachmentParts = msg.attachments.flatMap((attachment) => [
      `--${mixed}`,
      `Content-Type: ${attachment.contentType}; name="${attachment.filename.replace(/["\r\n]/g, '_')}"`,
      'Content-Transfer-Encoding: base64',
      `Content-Disposition: attachment; filename="${attachment.filename.replace(/["\r\n]/g, '_')}"`,
      '',
      b64(attachment.bytes).replace(/.{1,76}/g, '$&\r\n').trimEnd(),
    ]);
    raw = [
      ...headers, `Content-Type: multipart/mixed; boundary="${mixed}"`, '',
      `--${mixed}`, ...body, ...attachmentParts, `--${mixed}--`,
    ].join('\r\n');
  } else if (msg.html) {
    const boundary = `=_pumasi_${crypto.randomUUID().replace(/-/g, '')}`;
    raw = [
      ...headers,
      `Content-Type: multipart/alternative; boundary="${boundary}"`,
      '',
      `--${boundary}`,
      'Content-Type: text/plain; charset=utf-8',
      '',
      msg.text,
      `--${boundary}`,
      'Content-Type: text/html; charset=utf-8',
      '',
      msg.html,
      `--${boundary}--`,
    ].join('\r\n');
  } else {
    raw = [...headers, 'Content-Type: text/plain; charset=utf-8', '', msg.text].join('\r\n');
  }

  const token = await accessToken(env.GMAIL_SA_KEY, env.MAIL_IMPERSONATE);
  const res = await fetch(SEND_URL, {
    method: 'POST',
    headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
    body: JSON.stringify({ raw: b64url(utf8(raw)) }),
  });
  if (!res.ok) throw new Error(`gmail send failed: ${res.status} ${(await res.text()).slice(0, 200)}`);
}
