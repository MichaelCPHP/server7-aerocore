// Cloudflare Pages Function — Conversions API
// GET /api/conversions — returns submission data for ad conversion tracking.
// Authenticated via X-API-Key header (checked against CONVERSIONS_API_KEY).
//
// Query params:
//   from      — start date (ISO 8601 or YYYY-MM-DD)
//   to        — end date
//   has_gclid — if 'true', only return submissions with a gclid value
//   format    — 'gads' for Google Ads offline conversion import format

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, X-API-Key',
};

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

export async function onRequestGet(context) {
  // ── API key authentication ──────────────────────────────────

  const apiKey = context.request.headers.get('X-API-Key');
  const expectedKey = context.env.CONVERSIONS_API_KEY;

  if (!expectedKey) {
    return jsonResponse({ ok: false, error: 'Conversions API not configured.' }, 500);
  }

  if (!apiKey || apiKey !== expectedKey) {
    return jsonResponse({ ok: false, error: 'Invalid or missing API key.' }, 401);
  }

  try {
    const url = new URL(context.request.url);
    const params = url.searchParams;

    const from = params.get('from') || null;
    const to = params.get('to') || null;
    const hasGclid = params.get('has_gclid') === 'true';
    const format = params.get('format') || null;

    // ── Build query ─────────────────────────────────────────

    const conditions = [];
    const bindings = [];

    if (from) {
      conditions.push('created_at >= ?');
      bindings.push(from);
    }

    if (to) {
      const toValue = to.length === 10 ? `${to}T23:59:59.999Z` : to;
      conditions.push('created_at <= ?');
      bindings.push(toValue);
    }

    if (hasGclid) {
      conditions.push("gclid IS NOT NULL AND gclid != ''");
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

    const sql = `
      SELECT id, name, company, email, material, gclid,
             utm_source, utm_medium, utm_campaign, utm_term,
             status, created_at
      FROM submissions
      ${whereClause}
      ORDER BY created_at DESC
    `;

    const result = await context.env.DB.prepare(sql).bind(...bindings).all();
    const submissions = result.results || [];

    // ── Google Ads offline conversion format ─────────────────

    if (format === 'gads') {
      const conversions = submissions
        .filter((s) => s.gclid)
        .map((s) => ({
          'Google Click ID': s.gclid,
          'Conversion Name': 'Quote Request',
          'Conversion Time': formatGadsDate(s.created_at),
          'Conversion Value': '',
          'Conversion Currency': 'USD',
        }));

      return jsonResponse({
        ok: true,
        format: 'gads',
        conversions,
        total: conversions.length,
      });
    }

    // ── Default format ──────────────────────────────────────

    return jsonResponse({
      ok: true,
      submissions,
      total: submissions.length,
    });
  } catch (err) {
    console.error('Conversions API error:', err);
    return jsonResponse({ ok: false, error: 'Server error.' }, 500);
  }
}

// Format date for Google Ads: "yyyy-MM-dd HH:mm:ss z"
function formatGadsDate(isoString) {
  try {
    const d = new Date(isoString);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())} +0000`;
  } catch {
    return isoString;
  }
}

// ── CORS preflight ──────────────────────────────────────────────

export async function onRequestOptions() {
  return new Response(null, { headers: CORS_HEADERS });
}
