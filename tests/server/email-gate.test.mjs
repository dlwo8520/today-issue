import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { handle } from '../../server/email-gate.mjs';

const origin = 'https://personal.pages.dev';
const now = Date.now();
const environment = () => ({ PERSONAL_EMAIL: 'owner@example.com', PERSONAL_SESSION_SECRET: 'synthetic-secret-longer-than-32-characters', ASSETS: { fetch: async () => new Response('private news') } });
const enter = (email, extra = {}) => new Request(origin + '/auth/enter', { method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/x-www-form-urlencoded', ...extra }, body: new URLSearchParams({ email, next: '/' }) });

test('anonymous home, JSON and assets redirect before serving any data', async () => {
  for (const path of ['/', '/data/latest.json', '/data/status.json', '/assets/app.js']) {
    const result = await handle(new Request(origin + path), environment(), now);
    assert.equal(result.status, 302);
    assert.match(result.headers.get('location'), /^\/login\?/);
    assert.equal(await result.text(), '');
  }
});

test('entry form contains no permitted email or news data', async () => {
  const result = await handle(new Request(origin + '/login?next=//evil.example'), environment(), now);
  const html = await result.text();
  assert.equal(result.status, 200);
  assert.match(html, /data-personal-entry="email"/);
  assert.doesNotMatch(html, /owner@example.com|private news/);
  assert.match(html, /name="next" value="\/"/);
});

test('the configured email enters directly and its signed cookie unlocks JSON', async () => {
  const env = environment();
  const entered = await handle(enter(' OWNER@example.com '), env, now);
  assert.equal(entered.status, 303);
  const cookie = entered.headers.get('set-cookie');
  assert.match(cookie, /Secure; HttpOnly; SameSite=Lax/);
  const result = await handle(new Request(origin + '/data/latest.json', { headers: { Cookie: cookie.split(';')[0] } }), env, now);
  assert.equal(await result.text(), 'private news');
  assert.equal(result.headers.get('cache-control'), 'private, no-store');
});

test('other emails and cross-origin posts cannot enter', async () => {
  assert.equal((await handle(enter('other@example.com'), environment(), now)).status, 403);
  assert.equal((await handle(enter('owner@example.com', { Origin: 'https://other.example' }), environment(), now)).status, 403);
});

test('forged, expired, and changed-owner cookies do not unlock assets', async () => {
  const env = environment();
  const entered = await handle(enter('owner@example.com'), env, now);
  const cookie = entered.headers.get('set-cookie').split(';')[0];
  const request = cookieValue => new Request(origin + '/data/latest.json', { headers: { Cookie: cookieValue } });
  assert.equal((await handle(request('__Host-today_issue=invalid'), env, now)).status, 302);
  assert.equal((await handle(request(cookie), env, now + 31 * 86400000)).status, 302);
  assert.equal((await handle(request(cookie), { ...env, PERSONAL_EMAIL: 'changed@example.com' }, now)).status, 302);
});

test('missing server bindings cannot fall through to static files', async () => {
  for (const env of [{}, { ...environment(), PERSONAL_SESSION_SECRET: '' }]) assert.equal((await handle(new Request(origin + '/data/latest.json'), env, now)).status, 503);
});

test('large chunked form bodies are rejected', async () => {
  const request = new Request(origin + '/auth/enter', { method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/x-www-form-urlencoded' }, body: 'email=' + 'a'.repeat(5000) });
  assert.equal((await handle(request, environment(), now)).status, 413);
});

test('the Worker execution context is not used as a session timestamp', async () => {
  const env = environment();
  const result = await worker.fetch(enter('owner@example.com'), env, { waitUntil() {} });
  const cookie = result.headers.get('set-cookie').split(';')[0];
  const page = await worker.fetch(new Request(origin + '/data/latest.json', { headers: { Cookie: cookie } }), env, { waitUntil() {} });
  assert.equal(await page.text(), 'private news');
});
