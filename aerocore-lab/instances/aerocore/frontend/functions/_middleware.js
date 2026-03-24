// Cloudflare Pages Function — Auth Middleware
// Protects admin API routes with HMAC-SHA256 session verification.
// Public routes (/api/quote, /api/auth/login, /api/conversions) pass through.

const encoder = new TextEncoder();

// ── HMAC helpers ────────────────────────────────────────────────

async function getHmacKey(secret) {
  return crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign', 'verify'],
  );
}

async function signToken(payload, secret) {
  const key = await getHmacKey(secret);
  const payloadB64 = btoa(JSON.stringify(payload));
  const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(payloadB64));
  const sigB64 = btoa(String.fromCharCode(...new Uint8Array(sig)));
  return `${payloadB64}.${sigB64}`;
}

async function verifyToken(token, secret) {
  const parts = token.split('.');
  if (parts.length !== 2) return null;

  const [payloadB64, sigB64] = parts;
  const key = await getHmacKey(secret);

  // Decode signature from base64
  const sigStr = atob(sigB64);
  const sigBuf = new Uint8Array(sigStr.length);
  for (let i = 0; i < sigStr.length; i++) sigBuf[i] = sigStr.charCodeAt(i);

  const valid = await crypto.subtle.verify('HMAC', key, sigBuf, encoder.encode(payloadB64));
  if (!valid) return null;

  try {
    const payload = JSON.parse(atob(payloadB64));
    if (payload.exp && Date.now() > payload.exp) return null;
    return payload;
  } catch {
    return null;
  }
}

// ── Cookie parser ───────────────────────────────────────────────

function parseCookies(header) {
  const cookies = {};
  if (!header) return cookies;
  header.split(';').forEach((pair) => {
    const [name, ...rest] = pair.trim().split('=');
    if (name) cookies[name.trim()] = decodeURIComponent(rest.join('='));
  });
  return cookies;
}

// ── Routes that require authentication ──────────────────────────

const AUTH_PREFIXES = ['/api/submissions', '/api/attachments', '/api/auth/logout', '/api/auth/check'];

function requiresAuth(pathname) {
  return AUTH_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(prefix + '/'));
}

// ── Middleware entry point ───────────────────────────────────────

export async function onRequest(context) {
  const url = new URL(context.request.url);
  const { pathname } = url;

  // Public routes — pass through without auth
  if (!requiresAuth(pathname)) {
    return context.next();
  }

  // Protected route — validate session cookie
  const secret = context.env.SESSION_SECRET;
  if (!secret) {
    return new Response(JSON.stringify({ ok: false, error: 'Server misconfigured.' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const cookies = parseCookies(context.request.headers.get('Cookie'));
  const token = cookies.session;

  if (!token) {
    return new Response(JSON.stringify({ ok: false, error: 'Authentication required.' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const session = await verifyToken(token, secret);
  if (!session) {
    return new Response(JSON.stringify({ ok: false, error: 'Session expired or invalid.' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Attach session to context data for downstream handlers
  context.data.session = session;

  return context.next();
}
