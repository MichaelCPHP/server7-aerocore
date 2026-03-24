// Cloudflare Pages Function — Session Check
// If the middleware allowed the request through, the session is valid.

export async function onRequestGet(context) {
  const session = context.data.session || {};

  return new Response(
    JSON.stringify({ ok: true, user: session.user || 'admin' }),
    {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    },
  );
}
