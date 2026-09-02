import { test } from 'node:test';
import assert from 'node:assert/strict';
import { newHarness, cookieValue, Harness } from './support/durable-harness.js';
import { makePdf } from './support/pdf-probe.js';

let seq = 0;
function seedCode(h: Harness, email: string): void {
  const now = new Date();
  h.db.prepare(`INSERT INTO auth_codes (id, email, code, expires_at, created_at) VALUES (?, ?, '123456', ?, ?)`).run(
    `team-code-${++seq}`, email, new Date(now.getTime() + 600_000).toISOString(), now.toISOString(),
  );
}

async function signIn(h: Harness, email: string, name: string): Promise<{ cookie: string; user: any; branding: any }> {
  seedCode(h, email);
  const response = await h.fetch('/api/auth/login/verify', {
    method: 'POST', body: JSON.stringify({ email, name, code: '123456' }),
  });
  assert.equal(response.status, 200);
  const body = await response.json() as any;
  return { cookie: `sign_session=${cookieValue(response, 'sign_session')}`, user: body.user, branding: body.branding };
}

async function template(h: Harness, cookie: string): Promise<any> {
  const form = new FormData();
  form.set('name', 'Owner private template');
  form.set('file', new File([new Uint8Array(await makePdf(['PRIVATE']))], 'private.pdf', { type: 'application/pdf' }));
  const response = await h.fetch('/api/templates', { method: 'POST', cookie, body: form });
  assert.equal(response.status, 201);
  return response.json();
}

test('A-704 · team invitation accepts on verified sign-in without sharing resources', async () => {
  const h = newHarness();
  const owner = await signIn(h, 'owner@pumasi.ai', 'Owner');
  assert.equal((await h.fetch('/api/branding', {
    method: 'PUT', cookie: owner.cookie,
    body: JSON.stringify({ company_name: 'Owner Company', primary_color: '#C026D3', logo_data_url: 'data:image/png;base64,logo' }),
  })).status, 200);
  const privateTemplate = await template(h, owner.cookie);
  const invite = await h.fetch('/api/team/members', {
    method: 'POST', cookie: owner.cookie,
    body: JSON.stringify({ email: 'member@pumasi.ai', role: 'member' }),
  });
  assert.equal(invite.status, 201);
  assert.equal((await invite.json() as any).status, 'pending');

  const member = await signIn(h, 'member@pumasi.ai', 'Member');
  assert.equal(member.user.is_admin, false);
  assert.equal(member.user.can_send, true);
  const team = await (await h.fetch('/api/team/members', { cookie: owner.cookie })).json() as any[];
  assert.equal(team.find((row) => row.email === 'member@pumasi.ai')?.status, 'accepted');

  assert.deepEqual(await (await h.fetch('/api/templates', { cookie: member.cookie })).json(), []);
  assert.equal((await h.fetch(`/api/templates/${privateTemplate.id}`, { cookie: member.cookie })).status, 404);
  assert.equal((await h.fetch(`/api/files/template-pdf/${privateTemplate.id}`, { cookie: member.cookie })).status, 404);
  assert.equal((await h.fetch('/api/team/members', { cookie: member.cookie })).status, 403);
  const memberBranding = await (await h.fetch('/api/branding', { cookie: member.cookie })).json() as any;
  assert.equal(memberBranding.company_name, 'Owner Company');
  assert.equal(memberBranding.primary_color, '#C026D3');
  assert.equal(member.branding.company_name, 'Owner Company');
  assert.equal((await h.fetch('/api/branding', {
    method: 'PUT', cookie: member.cookie, body: JSON.stringify({ company_name: 'Hijack' }),
  })).status, 403);

  const profile = await h.fetch('/api/profile', { method: 'PUT', cookie: member.cookie, body: JSON.stringify({ name: 'Updated Member', email: 'attacker@example.test' }) });
  assert.equal(profile.status, 200);
  const updatedProfile = await profile.json() as any;
  assert.equal(updatedProfile.name, 'Updated Member');
  assert.equal(updatedProfile.email, 'member@pumasi.ai');
  assert.equal((await h.fetch('/api/profile', { method: 'PUT', cookie: member.cookie, body: JSON.stringify({ name: 'x' }) })).status, 400);
});

test('A-705 · admins can manage membership, pending invites resend, and revocation restores no resource access', async () => {
  const h = newHarness();
  const owner = await signIn(h, 'owner2@pumasi.ai', 'Owner Two');
  const adminInvite = await h.fetch('/api/team/members', {
    method: 'POST', cookie: owner.cookie,
    body: JSON.stringify({ email: 'admin@pumasi.ai', role: 'admin' }),
  });
  const pending = await adminInvite.json() as any;
  assert.equal((await h.fetch(`/api/team/members/${pending.id}/resend`, { method: 'POST', cookie: owner.cookie })).status, 200);
  const admin = await signIn(h, 'admin@pumasi.ai', 'Admin');
  assert.equal(admin.user.is_admin, true);

  assert.equal((await h.fetch(`/api/team/members/${pending.id}`, {
    method: 'PUT', cookie: owner.cookie, body: JSON.stringify({ role: 'member' }),
  })).status, 200);
  const demotedMe = await h.fetch('/api/auth/me', { cookie: admin.cookie });
  assert.equal((await demotedMe.json() as any).is_admin, false);
  assert.equal((await h.fetch('/api/team/members', { cookie: admin.cookie })).status, 403);
  assert.equal((await h.fetch(`/api/team/members/${pending.id}`, {
    method: 'PUT', cookie: admin.cookie, body: JSON.stringify({ role: 'admin' }),
  })).status, 403);
  assert.equal((await h.fetch(`/api/team/members/${pending.id}`, {
    method: 'PUT', cookie: owner.cookie, body: JSON.stringify({ role: 'admin' }),
  })).status, 200);
  assert.equal((await h.fetch(`/api/team/members/${pending.id}`, {
    method: 'PUT', cookie: admin.cookie, body: JSON.stringify({ role: 'member' }),
  })).status, 409);

  const memberInvite = await h.fetch('/api/team/members', {
    method: 'POST', cookie: admin.cookie,
    body: JSON.stringify({ email: 'second@pumasi.ai', role: 'member' }),
  });
  assert.equal(memberInvite.status, 201);
  const second = await memberInvite.json() as any;
  assert.equal((await h.fetch(`/api/team/members/${second.id}`, { method: 'DELETE', cookie: admin.cookie })).status, 200);
  const rows = await (await h.fetch('/api/team/members', { cookie: owner.cookie })).json() as any[];
  assert.equal(rows.some((row) => row.email === 'second@pumasi.ai'), false);
});
