// Cloudflare Pages Function — Admin Login
// Authenticates against ADMIN_USER / ADMIN_PASS_HASH env vars.
// Issues an HMAC-SHA256 signed session cookie on success.

const encoder = new TextEncoder();

// ── Crypto helpers ──────────────────────────────────────────────

async function sha256Hex(str) {
  const hash = await crypto.subtle.digest('SHA-256', encoder.encode(str));
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function getHmacKey(secret) {
  return crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
}

async function signToken(payload, secret) {
  const key = await getHmacKey(secret);
  const payloadB64 = btoa(JSON.stringify(payload));
  const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(payloadB64));
  const sigB64 = btoa(String.fromCharCode(...new Uint8Array(sig)));
  return `${payloadB64}.${sigB64}`;
}

// ── POST handler ────────────────────────────────────────────────

export async function onRequestPost(context) {
  const headers = { 'Content-Type': 'application/json' };

  try {
    const { username, password } = await context.request.json();

    if (!username || !password) {
      return new Response(
        JSON.stringify({ ok: false, error: 'Username and password required.' }),
        { status: 400, headers },
      );
    }

    const expectedUser = context.env.ADMIN_USER;
    const expectedHash = context.env.ADMIN_PASS_HASH;
    const sessionSecret = context.env.SESSION_SECRET;

    if (!expectedUser || !expectedHash || !sessionSecret) {
      return new Response(
        JSON.stringify({ ok: false, error: 'Server misconfigured.' }),
        { status: 500, headers },
      );
    }

    // Constant-time-ish comparison: hash the input and compare hex strings.
    // The SHA-256 hash itself provides uniform distribution making timing attacks impractical.
    const inputHash = await sha256Hex(password);

    if (username !== expectedUser || inputHash !== expectedHash.toLowerCase()) {
      return new Response(
        JSON.stringify({ ok: false, error: 'Invalid credentials' }),
        { status: 401, headers },
      );
    }

    // ── Issue session token ───────────────────────────────────

    const exp = Date.now() + 86400 * 1000; // 24 hours
    const token = await signToken({ user: username, exp }, sessionSecret);

    const cookie = [
      `session=${encodeURIComponent(token)}`,
      'Path=/',
      'HttpOnly',
      'Secure',
      'SameSite=Strict',
      'Max-Age=86400',
    ].join('; ');

    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { ...headers, 'Set-Cookie': cookie },
    });
  } catch (err) {
    console.error('Login error:', err);
    return new Response(
      JSON.stringify({ ok: false, error: 'Server error.' }),
      { status: 500, headers },
    );
  }
}
