// Cloudflare Pages Function — Admin Logout
// Clears the session cookie.

export async function onRequestPost() {
  const cookie = [
    'session=',
    'Path=/',
    'HttpOnly',
    'Secure',
    'SameSite=Strict',
    'Max-Age=0',
  ].join('; ');

  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Set-Cookie': cookie,
    },
  });
}
