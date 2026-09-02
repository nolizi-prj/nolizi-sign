import assert from 'node:assert/strict';
import test from 'node:test';
import { submitFeedbackToGitHub } from '../feedback.js';

test('A-970 · feedback uploads as many as five ordered images and links all of them', async () => {
  const originalFetch = globalThis.fetch;
  const requests: { url: string; init?: RequestInit }[] = [];
  globalThis.fetch = async (input, init) => {
    requests.push({ url: String(input), init });
    if (init?.method === 'PUT') return Response.json({ content: { sha: 'ok' } });
    return Response.json({ html_url: 'https://github.example/issues/21', number: 21 });
  };

  try {
    const result = await submitFeedbackToGitHub({
      message: 'Multiple screenshots',
      attachmentsBase64: ['data:image/png;base64,QQ==', 'data:image/webp;base64,Qg=='],
    }, { GITHUB_FEEDBACK_TOKEN: 'test-token', GITHUB_FEEDBACK_REPO: 'pumasi-ai/pumasi-sign' });

    assert.equal(result.ok, true);
    assert.equal(requests.length, 3);
    assert.match(requests[0].url, /shot-1-.*\.png$/);
    assert.match(requests[1].url, /shot-2-.*\.webp$/);
    const issueBody = JSON.parse(String(requests[2].init?.body)).body as string;
    assert.match(issueBody, /Attached Images \(2\)/);
    assert.match(issueBody, /Feedback image 1/);
    assert.match(issueBody, /Feedback image 2/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('A-971 · feedback rejects more than five images without calling GitHub', async () => {
  const originalFetch = globalThis.fetch;
  let called = false;
  globalThis.fetch = async () => { called = true; return new Response(); };
  try {
    const result = await submitFeedbackToGitHub({
      message: 'Too many',
      attachmentsBase64: Array.from({ length: 6 }, () => 'data:image/png;base64,QQ=='),
    }, { GITHUB_FEEDBACK_TOKEN: 'test-token' });
    assert.equal(result.ok, false);
    assert.match(result.message ?? '', /up to 5/);
    assert.equal(called, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
