/**
 * Frozen acceptance cases A-500 – A-506 · spec/0009.
 *
 * The OAuth sign-in path of the Durable Object that answers sign.pumasi.ai —
 * `GET /api/auth/oauth/{google,microsoft}` and its `/callback`. Until this
 * file nothing in this repository executed either leg: `grep -rn oauth
 * service/src/test/` matched nothing, and the branch that decides whether a
 * provider's token becomes a session cookie had no assertion on it at all.
 *
 * THEY CHARACTERIZE. They record what the deployed tree does today, the same
 * way `auth-session.test.ts` A-302 records `establishSession`'s account rule.
 * A-502 in particular records that an `id_token` which OMITS `email_verified`
 * is admitted, because the guard tests `=== false`. That is a measurement and
 * it is deliberately not a repair: changing a guard on a live auth path is a
 * behaviour change, it belongs to whoever ranks it, and spec/0009 §S3 says so
 * at more length. RECORDED, NOT ENDORSED — if a later packet tightens the
 * guard, A-502 GOING RED IS THE CORRECT OUTCOME. Amend it with that change.
 *
 * THE TRAP THIS FILE IS BUILT AROUND, because it is the whole reason the
 * assertions look heavier than the branch they cover. FIVE distinct failures
 * on this route produce the byte-identical response `302 → /login`: no state
 * row, no `code` parameter, a non-`ok` token exchange, an `id_token` that does
 * not parse, and a claim set the guard rejects. A case that asserted only the
 * status and the Location would pass while exercising a completely different
 * branch from the one it claims — pumasi/lessons/L-006 at branch scale. So
 * every negative case here also asserts HOW FAR the request got: whether the
 * token endpoint was called, whether the state row was consumed, and that no
 * user and no session were written. A-500 is the guard that proves the stub
 * is reached at all.
 *
 * Read spec/0004 §S1c before trusting a green run: this is node:sqlite, not
 * workerd's SQLite, and a green count here is not evidence about production
 * (pumasi/DECISIONS.md Q-018, default part (c)).
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { newHarness, cookieValue, Harness } from './support/durable-harness.js';

/** Env that makes `oauthProvider('google')` return a configured provider. */
const GOOGLE = {
  GOOGLE_OAUTH_CLIENT_ID: 'client-id-google',
  GOOGLE_OAUTH_CLIENT_SECRET: 'client-secret-google',
};

/** Env that makes `oauthProvider('microsoft')` return a configured provider. */
const MICROSOFT = {
  MS_OAUTH_CLIENT_ID: 'client-id-ms',
  MS_OAUTH_CLIENT_SECRET: 'client-secret-ms',
};

/** base64url, unpadded — the encoding a real id_token segment arrives in. */
function b64url(value: string): string {
  return btoa(value).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** A three-segment JWT whose payload is `claims` and whose signature is junk. */
function idToken(claims: Record<string, unknown>): string {
  return `${b64url('{"alg":"RS256"}')}.${b64url(JSON.stringify(claims))}.not-a-signature`;
}

interface TokenCall {
  url: string;
  method: string;
  body: Record<string, string>;
}

interface Stub {
  calls: TokenCall[];
  restore(): void;
}

/**
 * Replace the global `fetch` the callback uses to reach the provider's token
 * endpoint. Returns the calls it saw, so a case can prove the request got
 * past the state check rather than inferring it from a 302 that five
 * different branches produce.
 *
 * `reply` returns the Response for the exchange. Anything the worker fetches
 * that is not the token endpoint is a bug in the test, not in the worker, and
 * throws rather than being silently answered.
 */
function stubTokenEndpoint(reply: () => Response | Promise<Response>): Stub {
  const real = globalThis.fetch;
  const calls: TokenCall[] = [];
  let userInfo: Record<string, unknown> = {};
  globalThis.fetch = (async (input: any, init: any = {}) => {
    const url = String(typeof input === 'string' ? input : input.url);
    if (/\/userinfo$/.test(url)) {
      assert.equal(new Headers(init.headers).get('authorization'), 'Bearer at');
      return Response.json(userInfo);
    }
    if (!/\/token$/.test(url)) {
      throw new Error(`the worker fetched an unexpected URL: ${url}`);
    }
    calls.push({
      url,
      method: String(init.method ?? 'GET'),
      body: Object.fromEntries(new URLSearchParams(String(init.body ?? ''))),
    });
    const response = await reply();
    try {
      const token = await response.clone().json() as { id_token?: string };
      const segment = token.id_token?.split('.')[1] || '';
      userInfo = JSON.parse(atob(segment.replace(/-/g, '+').replace(/_/g, '/')));
    } catch { userInfo = {}; }
    return response;
  }) as typeof fetch;
  return { calls, restore: () => { globalThis.fetch = real; } };
}

/** A token-endpoint reply carrying `id_token`, the shape the worker reads. */
const tokenOk = (id_token: string, extra: Record<string, unknown> = {}) => () =>
  Response.json({ token_type: 'Bearer', access_token: 'at', id_token, ...extra });

/**
 * Drive the authorize leg and hand back the `state` the worker minted. This
 * is how a case gets a live `auth_codes` row without seeding one by hand —
 * the row's shape is the worker's own, not the test's guess at it.
 */
async function authorize(h: Harness, provider: string, next?: string): Promise<string> {
  const path = `/api/auth/oauth/${provider}${next === undefined ? '' : `?next=${encodeURIComponent(next)}`}`;
  const res = await h.fetch(path);
  assert.equal(res.status, 302, 'the authorize leg did not redirect to the provider');
  const location = new URL(res.headers.get('location')!);
  const state = location.searchParams.get('state');
  assert.ok(state, 'the authorize leg minted no state');
  return state;
}

const count = (h: Harness, table: string): number =>
  (h.db.prepare(`SELECT count(*) AS n FROM ${table}`).get() as { n: number }).n;

/**
 * What the callback wrote, or did not. Every negative case in this file pins
 * all four, because spec/0009 §S2 claims they do and a spec review twice
 * found a case exempting itself from that claim
 * (reviews/20260831-232258-spec-qwen.md, and the round after it).
 */
function after(h: Harness, state: string) {
  return {
    users: count(h, 'users'),
    sessions: count(h, 'sessions'),
    branding: count(h, 'org_branding'),
    stateRow: h.db.prepare(`SELECT id FROM auth_codes WHERE email = ?`).get(`oauth:${state}`),
  };
}

// ── A-500 · the reader guard: both legs are real, and the stub is reached ───
//
// Every other case in this file asserts something about the callback. If the
// authorize leg did not store state, or the callback's state lookup never
// matched, all of them would take the `!row` early return and answer
// `302 → /login` — and four of the five negative cases would still be green
// while measuring nothing. This case exists to make that impossible, and it
// pins the authorize leg's own open-redirect guard while it is here.

test('A-500 the authorize leg mints state the callback consumes, and the token endpoint is really called', async () => {
  const h = newHarness(GOOGLE);

  const res = await h.fetch('/api/auth/oauth/google?next=%2Fenvelopes');
  assert.equal(res.status, 302);
  const location = new URL(res.headers.get('location')!);
  assert.equal(location.origin + location.pathname, 'https://accounts.google.com/o/oauth2/v2/auth');
  assert.equal(location.searchParams.get('client_id'), 'client-id-google');
  assert.equal(
    location.searchParams.get('redirect_uri'),
    'https://sign.example.test/api/auth/oauth/google/callback',
  );
  assert.equal(location.searchParams.get('response_type'), 'code');
  assert.equal(location.searchParams.get('scope'), 'openid email profile');
  assert.equal(location.searchParams.get('prompt'), 'select_account');
  const state = location.searchParams.get('state')!;
  assert.ok(state, 'no state parameter');

  // The state is a row in auth_codes under a namespaced pseudo-address, and
  // it carries the `next` the caller asked for.
  const row = h.db.prepare(`SELECT email, code FROM auth_codes`).get() as
    { email: string; code: string } | undefined;
  assert.ok(row, 'the authorize leg stored no state row');
  assert.equal(row.email, `oauth:${state}`);
  assert.deepEqual(JSON.parse(row.code), { next: '/envelopes' });

  // And the callback reaches the provider's token endpoint with the code and
  // the client credentials — measured on the stub, not inferred from a 302.
  const stub = stubTokenEndpoint(tokenOk(idToken({ email: 'a@pumasi.ai', email_verified: true })));
  try {
    const cb = await h.fetch(`/api/auth/oauth/google/callback?state=${state}&code=auth-code-xyz`);
    assert.equal(cb.status, 302);
    assert.equal(stub.calls.length, 1, 'the callback did not call the token endpoint');
    assert.equal(stub.calls[0].url, 'https://oauth2.googleapis.com/token');
    assert.equal(stub.calls[0].method, 'POST');
    assert.deepEqual(stub.calls[0].body, {
      code: 'auth-code-xyz',
      client_id: 'client-id-google',
      client_secret: 'client-secret-google',
      redirect_uri: 'https://sign.example.test/api/auth/oauth/google/callback',
      grant_type: 'authorization_code',
    });
    // The state is single-use: consumed by the callback that spent it.
    assert.equal(count(h, 'auth_codes'), 0, 'the state row survived the callback that used it');
  } finally {
    stub.restore();
  }

  // The authorize leg's own open-redirect guard, pinned here because this is
  // the case that reads that leg. An off-site `next` becomes `/`.
  for (const [asked, stored] of [
    ['https://evil.example/steal', '/'],
    ['//evil.example/steal', '/'],
    ['/envelopes/abc', '/envelopes/abc'],
  ] as const) {
    const g = newHarness(GOOGLE);
    const s = await authorize(g, 'google', asked);
    const r = g.db.prepare(`SELECT code FROM auth_codes WHERE email = ?`).get(`oauth:${s}`) as
      { code: string };
    assert.equal(JSON.parse(r.code).next, stored, `next=${asked} was stored as something else`);
  }
});

// ── A-501 · the accepted case ───────────────────────────────────────────────

test('A-501 an id_token with email_verified true establishes a session and returns to the stored next', async () => {
  const h = newHarness(GOOGLE);
  const state = await authorize(h, 'google', '/envelopes/e-1');

  const stub = stubTokenEndpoint(tokenOk(idToken({
    email: 'Verified.User@Pumasi.AI',
    email_verified: true,
    name: 'Verified User',
  })));
  let res: Response;
  try {
    res = await h.fetch(`/api/auth/oauth/google/callback?state=${state}&code=c`);
  } finally {
    stub.restore();
  }

  assert.equal(res.status, 302);
  assert.equal(res.headers.get('location'), '/envelopes/e-1', 'the stored next was not honoured');

  const token = cookieValue(res, 'sign_session');
  assert.ok(token, 'no sign_session cookie was set');

  const user = h.db.prepare(`SELECT id, email, name, provider FROM users`).get() as
    { id: string; email: string; name: string; provider: string };
  // Lower-cased before the account lookup, the same as the email path (A-304).
  assert.equal(user.email, 'verified.user@pumasi.ai');
  assert.equal(user.name, 'Verified User');
  // The provider string reaching establishSession is the URL segment.
  assert.equal(user.provider, 'google');

  const session = h.db.prepare(`SELECT user_id FROM sessions WHERE token = ?`).get(token) as
    { user_id: string } | undefined;
  assert.ok(session, 'the cookie names a token with no row in sessions');
  assert.equal(session.user_id, user.id);

  // A workspace was created with the account, as establishSession does.
  assert.equal(count(h, 'org_branding'), 1);

  // And the session the cookie carries is one /api/auth/me accepts.
  const me = await h.fetch('/api/auth/me', { cookie: `sign_session=${token}` });
  assert.equal(me.status, 200);
  assert.equal((await me.json() as { email: string }).email, 'verified.user@pumasi.ai');
});

// ── A-502 · the finding: an OMITTED email_verified is admitted ──────────────
//
// RECORDED, NOT ENDORSED. roadmap/BACKLOG.md item 2's named first slice, and
// job 0050's proposal 5. The guard at durable.ts:848 reads
//
//     claims.email_verified === false
//
// so `undefined` — a payload with no such claim — is not `false` and passes.
// This case does not argue that the branch is exploitable; it measures that
// the branch admits, which is what the packet asked for and is all the
// evidence supports. spec/0009 §S3 states the mitigation in the code's own
// comment and does not wave it away. If a packet later requires the claim,
// this case must go red and be amended with that change, NOT worked around.

test('A-502 an identity that omits email_verified is refused', async () => {
  const h = newHarness(GOOGLE);
  const state = await authorize(h, 'google');

  // No `email_verified` key at all. Everything else is a well-formed payload.
  const claims = { email: 'no-claim@example.com', name: 'No Claim' };
  assert.ok(!('email_verified' in claims), 'the fixture must not carry the claim');

  const stub = stubTokenEndpoint(tokenOk(idToken(claims)));
  let res: Response;
  try {
    res = await h.fetch(`/api/auth/oauth/google/callback?state=${state}&code=c`);
    assert.equal(stub.calls.length, 1, 'the token endpoint was not reached — wrong branch');
  } finally {
    stub.restore();
  }

  assert.equal(res.status, 302);
  assert.equal(res.headers.get('location'), '/login');
  const token = cookieValue(res, 'sign_session');
  assert.equal(token, undefined);

  const state502 = after(h, state);
  assert.equal(state502.users, 0);
  assert.equal(state502.sessions, 0);
  assert.equal(state502.stateRow, undefined, 'the state row was not consumed');

  assert.equal(state502.branding, 0);
});

// ── A-503 · the claim present and false IS refused ──────────────────────────

test('A-503 email_verified false is refused: no cookie, no account, no session — and the exchange did happen', async () => {
  const h = newHarness(GOOGLE);
  const state = await authorize(h, 'google', '/envelopes');

  const stub = stubTokenEndpoint(tokenOk(idToken({
    email: 'unverified@example.com',
    email_verified: false,
    name: 'Unverified',
  })));
  let res: Response;
  try {
    res = await h.fetch(`/api/auth/oauth/google/callback?state=${state}&code=c`);
    // Without this the case would be green on a request that never left the
    // state check, and would measure nothing about the guard.
    assert.equal(stub.calls.length, 1, 'the token endpoint was not reached — wrong branch');
  } finally {
    stub.restore();
  }

  assert.equal(res.status, 302);
  assert.equal(res.headers.get('location'), '/login', 'a refused sign-in did not go to /login');
  assert.equal(cookieValue(res, 'sign_session'), undefined, 'a refused sign-in set a session cookie');

  const wrote = after(h, state);
  assert.equal(wrote.users, 0, 'a refused sign-in created an account');
  assert.equal(wrote.sessions, 0, 'a refused sign-in created a session');
  assert.equal(wrote.branding, 0, 'a refused sign-in created a workspace');
  // Refused or not, the state was spent before the exchange. A replay of the
  // same state cannot re-enter the exchange.
  assert.equal(wrote.stateRow, undefined, 'the state row survived a refused callback');

  const replay = await h.fetch(`/api/auth/oauth/google/callback?state=${state}&code=c`);
  assert.equal(replay.status, 302);
  assert.equal(replay.headers.get('location'), '/login');
  assert.equal(count(h, 'users'), 0);
});

// ── A-504 · a non-ok token exchange ─────────────────────────────────────────

test('A-504 a non-ok token response is refused, and the refusal is not read as a claim set', async () => {
  const h = newHarness(GOOGLE);
  const state = await authorize(h, 'google');

  // A body that WOULD pass the claim guard if the status were ignored: the
  // point of this case is that `tokenRes.ok` is checked before the payload is
  // touched. `error_description` carries an address so a reader that fell
  // through to JSON.parse would not simply crash.
  const stub = stubTokenEndpoint(() => Response.json(
    { error: 'invalid_grant', id_token: idToken({ email: 'sneak@example.com', email_verified: true }) },
    { status: 400 },
  ));
  let res: Response;
  try {
    res = await h.fetch(`/api/auth/oauth/google/callback?state=${state}&code=c`);
    assert.equal(stub.calls.length, 1, 'the token endpoint was not reached — wrong branch');
  } finally {
    stub.restore();
  }

  assert.equal(res.status, 302);
  assert.equal(res.headers.get('location'), '/login');
  assert.equal(cookieValue(res, 'sign_session'), undefined);

  const wrote = after(h, state);
  assert.equal(wrote.users, 0, 'a failed exchange created an account');
  assert.equal(wrote.sessions, 0);
  assert.equal(wrote.branding, 0, 'a failed exchange created a workspace');
  assert.equal(wrote.stateRow, undefined, 'the state row survived a failed exchange');
});

// ── A-505 · an id_token whose payload segment does not parse ────────────────

test('A-505 an unparseable, absent or claimless id_token is refused — the empty claim set does not sign anyone in', async () => {
  // Four shapes that all reach `JSON.parse(atob(...))` or its absence, each
  // driven on its own harness so one cannot mask another. `claims` starts as
  // `{}` and the catch leaves it `{}`, so what refuses these is the `!email`
  // half of the guard rather than the try/catch — which is the thing worth
  // pinning, because a future edit that gave `claims` a default email would
  // pass every other case in this file.
  const shapes: Array<[string, unknown]> = [
    ['payload segment is not base64 of JSON', `${b64url('{"alg":"RS256"}')}.@@@not-base64@@@.sig`],
    ['payload segment is base64 of something that is not JSON', `${b64url('{"alg":"RS256"}')}.${b64url('this is not json')}.sig`],
    ['the token has no second segment', 'single-segment'],
    ['there is no id_token at all', undefined],
  ];

  for (const [why, id_token] of shapes) {
    const h = newHarness(GOOGLE);
    const state = await authorize(h, 'google');

    const stub = stubTokenEndpoint(() => Response.json(
      id_token === undefined ? { token_type: 'Bearer' } : { token_type: 'Bearer', id_token },
    ));
    let res: Response;
    try {
      res = await h.fetch(`/api/auth/oauth/google/callback?state=${state}&code=c`);
      assert.equal(stub.calls.length, 1, `${why}: the token endpoint was not reached`);
    } finally {
      stub.restore();
    }

    assert.equal(res.status, 302, why);
    assert.equal(res.headers.get('location'), '/login', why);
    assert.equal(cookieValue(res, 'sign_session'), undefined, `${why}: a session cookie was set`);
    const wrote = after(h, state);
    assert.equal(wrote.users, 0, `${why}: an account was created`);
    assert.equal(wrote.sessions, 0, `${why}: a session was created`);
    assert.equal(wrote.branding, 0, `${why}: a workspace was created`);
    // The state was spent before the exchange, so it cannot be replayed into
    // a second attempt at parsing a token. Asserted here and not only in
    // A-503 because spec/0009 §S2 claims EVERY negative case pins how far the
    // request got, and a spec review found this case exempting itself from
    // that claim (reviews/20260831-232258-spec-qwen.md).
    assert.equal(wrote.stateRow, undefined, `${why}: the state row survived`);
  }

  // An address with no `@` is refused by the same guard, and it is asserted
  // here rather than left to the `!email` clause alone: `includes('@')` is
  // the whole of what this route checks an address against, and A-502 already
  // shows the third clause admits by omission.
  const h = newHarness(GOOGLE);
  const state = await authorize(h, 'google');
  const stub = stubTokenEndpoint(tokenOk(idToken({ email: 'not-an-address', email_verified: true })));
  try {
    const res = await h.fetch(`/api/auth/oauth/google/callback?state=${state}&code=c`);
    assert.equal(stub.calls.length, 1, 'no @: the token endpoint was not reached');
    assert.equal(res.headers.get('location'), '/login');
    assert.equal(cookieValue(res, 'sign_session'), undefined);
    const wrote = after(h, state);
    assert.equal(wrote.users, 0, 'no @: an account was created');
    assert.equal(wrote.sessions, 0, 'no @: a session was created');
    assert.equal(wrote.branding, 0, 'no @: a workspace was created');
    assert.equal(wrote.stateRow, undefined, 'no @: the state row survived');
  } finally {
    stub.restore();
  }
});

// ── A-506 · Microsoft's fallback claim, and the two refusals before any of it ─

test('A-506 preferred_username signs a Microsoft user in, the display name falls back to the local part, and an unconfigured provider is 503', async () => {
  const h = newHarness(MICROSOFT);
  const state = await authorize(h, 'microsoft');

  // Microsoft's id_token often carries no `email`; `preferred_username` is
  // the fallback the worker reads, and no `name` claim means the display name
  // is derived from the local part.
  const stub = stubTokenEndpoint(tokenOk(idToken({
    preferred_username: 'First.Last@pumasi.ai',
  })));
  let res: Response;
  try {
    res = await h.fetch(`/api/auth/oauth/microsoft/callback?state=${state}&code=c`);
    assert.equal(stub.calls[0].url, 'https://login.microsoftonline.com/common/oauth2/v2.0/token');
  } finally {
    stub.restore();
  }

  assert.equal(res.status, 302);
  assert.ok(cookieValue(res, 'sign_session'), 'preferred_username did not sign the user in');
  const user = h.db.prepare(`SELECT email, name, provider FROM users`).get() as
    { email: string; name: string; provider: string };
  assert.equal(user.email, 'first.last@pumasi.ai');
  // Derived from the local part, verbatim and NOT title-cased — the email
  // path's `First Last` prettifying is not on this route. Recorded because
  // the two paths differing is the kind of thing a reader assumes away.
  assert.equal(user.name, 'first.last');
  assert.equal(user.provider, 'microsoft');

  // Both legs answer 503 when the deployment has no credentials for the
  // provider, and they answer it BEFORE minting state or calling anything.
  const bare = newHarness();
  for (const path of [
    '/api/auth/oauth/google',
    '/api/auth/oauth/google/callback?state=x&code=y',
    '/api/auth/oauth/microsoft',
    '/api/auth/oauth/microsoft/callback?state=x&code=y',
  ]) {
    const r = await bare.fetch(path);
    assert.equal(r.status, 503, `${path} did not report the provider unconfigured`);
    assert.match((await r.json() as { error: string }).error, /sign-in is not configured/);
  }
  assert.equal(count(bare, 'auth_codes'), 0, 'an unconfigured provider still minted state');

  // A provider this worker does not serve is not an OAuth route at all.
  const unknown = await h.fetch('/api/auth/oauth/okta');
  assert.equal(unknown.status, 404);

  // And a callback with no state row, or no code, is refused without ever
  // reaching the token endpoint — the branch every negative case above had to
  // be shown to have got past.
  // One account and one session exist on `h` from the sign-in above; these two
  // refusals must add neither. Pinned against the counts as they stand rather
  // than against zero, so the case still measures on a non-empty store.
  const before = { users: count(h, 'users'), sessions: count(h, 'sessions'), branding: count(h, 'org_branding') };
  const noStub = stubTokenEndpoint(() => { throw new Error('the token endpoint must not be called'); });
  try {
    const noState = await h.fetch('/api/auth/oauth/microsoft/callback?state=never-minted&code=c');
    assert.equal(noState.status, 302);
    assert.equal(noState.headers.get('location'), '/login');
    assert.equal(cookieValue(noState, 'sign_session'), undefined, 'an unknown state set a session cookie');

    const s2 = await authorize(h, 'microsoft');
    const noCode = await h.fetch(`/api/auth/oauth/microsoft/callback?state=${s2}`);
    assert.equal(noCode.status, 302);
    assert.equal(noCode.headers.get('location'), '/login');
    assert.equal(cookieValue(noCode, 'sign_session'), undefined, 'a code-less callback set a session cookie');
    // A code-less callback does NOT consume the state row: it returns before
    // the DELETE. Recorded, not endorsed.
    assert.ok(
      h.db.prepare(`SELECT id FROM auth_codes WHERE email = ?`).get(`oauth:${s2}`),
      'a code-less callback consumed the state row',
    );
    assert.equal(noStub.calls.length, 0, 'a refused callback reached the token endpoint');
    assert.deepEqual(
      { users: count(h, 'users'), sessions: count(h, 'sessions'), branding: count(h, 'org_branding') },
      before,
      'a callback refused before the exchange still wrote to the store',
    );
  } finally {
    noStub.restore();
  }
});
