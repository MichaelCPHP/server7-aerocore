// Cloudflare Pages Function — Submissions List
// GET /api/submissions — paginated, filterable list of all quote submissions.
//
// Query params:
//   status   — filter by status (e.g. 'new', 'contacted', 'quoted', 'closed')
//   q        — search name, company, or email
//   from     — start date (ISO 8601 or YYYY-MM-DD)
//   to       — end date
//   page     — page number (default 1)
//   perPage  — results per page (default 50, max 200)

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Cookie',
};

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

export async function onRequestGet(context) {
  try {
    const url = new URL(context.request.url);
    const params = url.searchParams;

    const status = params.get('status') || null;
    const q = params.get('q')?.trim() || null;
    const from = params.get('from') || null;
    const to = params.get('to') || null;
    const page = Math.max(1, parseInt(params.get('page'), 10) || 1);
    const perPage = Math.min(200, Math.max(1, parseInt(params.get('perPage'), 10) || 50));
    const offset = (page - 1) * perPage;

    // ── Build WHERE clauses ───────────────────────────────────

    const conditions = [];
    const bindings = [];

    if (status) {
      conditions.push('s.status = ?');
      bindings.push(status);
    }

    if (q) {
      conditions.push('(s.name LIKE ? OR s.company LIKE ? OR s.email LIKE ?)');
      const pattern = `%${q}%`;
      bindings.push(pattern, pattern, pattern);
    }

    if (from) {
      conditions.push('s.created_at >= ?');
      bindings.push(from);
    }

    if (to) {
      // Include the full end date by appending time if not present
      const toValue = to.length === 10 ? `${to}T23:59:59.999Z` : to;
      conditions.push('s.created_at <= ?');
      bindings.push(toValue);
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

    // ── Count total matching rows ─────────────────────────────

    const countSql = `SELECT COUNT(*) AS total FROM submissions s ${whereClause}`;
    const countResult = await context.env.DB.prepare(countSql).bind(...bindings).first();
    const total = countResult?.total || 0;

    // ── Fetch page of submissions with attachment count ───────

    const dataSql = `
      SELECT
        s.*,
        COALESCE(a.attachment_count, 0) AS attachment_count
      FROM submissions s
      LEFT JOIN (
        SELECT submission_id, COUNT(*) AS attachment_count
        FROM attachments
        GROUP BY submission_id
      ) a ON a.submission_id = s.id
      ${whereClause}
      ORDER BY s.created_at DESC
      LIMIT ? OFFSET ?
    `;

    const dataResult = await context.env.DB.prepare(dataSql)
      .bind(...bindings, perPage, offset)
      .all();

    return jsonResponse({
      submissions: dataResult.results || [],
      total,
      page,
      perPage,
    });
  } catch (err) {
    console.error('Submissions list error:', err);
    return jsonResponse({ ok: false, error: 'Server error.' }, 500);
  }
}

// ── CORS preflight ──────────────────────────────────────────────

export async function onRequestOptions() {
  return new Response(null, { headers: CORS_HEADERS });
}
