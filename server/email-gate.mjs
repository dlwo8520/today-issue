const COOKIE = '__Host-today_issue';
const MAX_AGE = 30 * 24 * 60 * 60;
const encoder = new TextEncoder();
const escape = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const encode = bytes => btoa(String.fromCharCode(...bytes)).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '');
const decode = text => Uint8Array.from(atob(text.replaceAll('-', '+').replaceAll('_', '/')), c => c.charCodeAt(0));
const safePath = value => value?.startsWith('/') && !value.startsWith('//') && !/[\\\u0000-\u001f\u007f]/.test(value) ? value : '/';

async function key(secret) {
  return crypto.subtle.importKey('raw', encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
}

async function session(email, secret, now) {
  const payload = encode(encoder.encode(JSON.stringify({ email, exp: Math.floor(now / 1000) + MAX_AGE })));
  const signature = await crypto.subtle.sign('HMAC', await key(secret), encoder.encode(payload));
  return `${payload}.${encode(new Uint8Array(signature))}`;
}

async function validSession(request, email, secret, now) {
  try {
    const token = (request.headers.get('cookie') || '').split(';').map(s => s.trim()).find(s => s.startsWith(COOKIE + '='))?.slice(COOKIE.length + 1);
    if (!token || token.length > 2048) return false;
    const parts = token.split('.');
    if (parts.length !== 2 || !await crypto.subtle.verify('HMAC', await key(secret), decode(parts[1]), encoder.encode(parts[0]))) return false;
    const data = JSON.parse(new TextDecoder().decode(decode(parts[0])));
    return data.email === email && Number.isInteger(data.exp) && data.exp > Math.floor(now / 1000) && data.exp <= Math.floor(now / 1000) + MAX_AGE;
  } catch { return false; }
}

function entry(next, error = '') {
  return `<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>오늘의 잇슈 · 입장</title>
<style>*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f5f8f5;color:#213d30;font-family:system-ui,sans-serif;padding:24px}.card{width:100%;max-width:400px;background:white;border:1px solid #dce7df;border-radius:20px;padding:36px;box-shadow:0 16px 48px #183a2010}h1{font-size:27px;margin:0 0 12px}p{font-size:15px;line-height:1.6;color:#617266;margin:0 0 28px}label{display:block;font-size:14px;margin:0 0 9px}input,button{width:100%;font:inherit;border-radius:10px;padding:14px}input{border:1px solid #bdcfc2}button{margin-top:16px;background:#246c47;color:white;border:0;cursor:pointer;font-weight:650}input:focus,button:focus-visible{outline:3px solid #8ec6a5;outline-offset:2px}.error{color:#a33030;margin:14px 0 0;font-size:14px}</style>
<main class="card" data-personal-entry="email"><h1>오늘의 잇슈<span style="color:#358159">.</span></h1><p>이메일을 입력하고 오늘의 이야기를 만나보세요.</p>
<form method="post" action="/auth/enter"><label for="email">이메일</label><input id="email" name="email" type="email" autocomplete="email" required autofocus><input type="hidden" name="next" value="${escape(safePath(next))}"><button type="submit">들어가기</button>${error ? `<p class="error" role="alert">${escape(error)}</p>` : ''}</form></main></html>`;
}

function response(body, status = 200, headers = {}) {
  return new Response(body, { status, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'private, no-store', 'X-Robots-Tag': 'noindex, nofollow', ...headers } });
}

export async function handle(request, env, now = Date.now()) {
  const email = String(env.PERSONAL_EMAIL || '').trim().toLowerCase();
  const secret = env.PERSONAL_SESSION_SECRET;
  if (!email.includes('@') || typeof secret !== 'string' || secret.length < 32 || !env.ASSETS) return response('입장 설정을 준비 중입니다.', 503);
  const url = new URL(request.url);
  if (url.pathname === '/auth/enter') {
    if (request.method !== 'POST') return response('Method not allowed', 405, { Allow: 'POST' });
    if (request.headers.get('Origin') !== url.origin || !request.headers.get('content-type')?.startsWith('application/x-www-form-urlencoded')) return response('입력 요청을 확인해 주세요.', 403);
    // Read a bounded stream; Content-Length alone is not trustworthy.
    const reader = request.body?.getReader();
    if (!reader) return response('이메일을 확인해 주세요.', 400);
    const chunks = [];
    let size = 0;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 4096) { await reader.cancel(); return response('입력이 너무 깁니다.', 413); }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    const form = new URLSearchParams(new TextDecoder().decode(bytes));
    if (form.getAll('email').length !== 1 || form.get('email').trim().toLowerCase() !== email) return response(entry(form.get('next'), '이메일을 확인해 주세요.'), 403);
    const token = await session(email, secret, now);
    return response(null, 303, { Location: safePath(form.get('next')), 'Set-Cookie': `${COOKIE}=${token}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${MAX_AGE}` });
  }
  if (url.pathname === '/login') return response(entry(url.searchParams.get('next')));
  if (!await validSession(request, email, secret, now)) return response(null, 302, { Location: `/login?next=${encodeURIComponent(url.pathname + url.search)}` });
  if (!['GET', 'HEAD'].includes(request.method)) return response('Method not allowed', 405, { Allow: 'GET, HEAD' });
  const asset = await env.ASSETS.fetch(request);
  const headers = new Headers(asset.headers);
  headers.set('Cache-Control', 'private, no-store');
  headers.set('X-Robots-Tag', 'noindex, nofollow');
  return new Response(asset.body, { status: asset.status, statusText: asset.statusText, headers });
}

export default { fetch: (request, env) => handle(request, env) };
