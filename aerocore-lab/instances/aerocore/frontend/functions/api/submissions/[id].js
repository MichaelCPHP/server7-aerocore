// Cloudflare Pages Function — Single Submission
// GET    /api/submissions/:id — full submission with attachments
// PATCH  /api/submissions/:id — update status and/or notes
// DELETE /api/submissions/:id — delete submission, attachments, and KV objects

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, PATCH, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Cookie',
};

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

// ── GET ─────────────────────────────────────────────────────────

export async function onRequestGet(context) {
  try {
    const id = context.params.id;

    const submission = await context.env.DB.prepare(
      'SELECT * FROM submissions WHERE id = ?'
    )
      .bind(id)
      .first();

    if (!submission) {
      return jsonResponse({ ok: false, error: 'Submission not found.' }, 404);
    }

    const attachments = await context.env.DB.prepare(
      'SELECT id, filename, original_name, content_type, size_bytes, created_at FROM attachments WHERE submission_id = ? ORDER BY created_at'
    )
      .bind(id)
      .all();

    return jsonResponse({
      ...submission,
      attachments: attachments.results || [],
    });
  } catch (err) {
    console.error('Submission GET error:', err);
    return jsonResponse({ ok: false, error: 'Server error.' }, 500);
  }
}

// ── PATCH ───────────────────────────────────────────────────────

export async function onRequestPatch(context) {
  try {
    const id = context.params.id;
    const body = await context.request.json();

    // Check submission exists
    const existing = await context.env.DB.prepare(
      'SELECT id FROM submissions WHERE id = ?'
    )
      .bind(id)
      .first();

    if (!existing) {
      return jsonResponse({ ok: false, error: 'Submission not found.' }, 404);
    }

    // Build dynamic UPDATE
    const fields = [];
    const values = [];

    if (body.status !== undefined) {
      fields.push('status = ?');
      values.push(body.status);
    }

    if (body.notes !== undefined) {
      fields.push('notes = ?');
      values.push(body.notes);
    }

    if (fields.length === 0) {
      return jsonResponse({ ok: false, error: 'No fields to update.' }, 400);
    }

    fields.push('updated_at = ?');
    values.push(new Date().toISOString());
    values.push(id);

    await context.env.DB.prepare(
      `UPDATE submissions SET ${fields.join(', ')} WHERE id = ?`
    )
      .bind(...values)
      .run();

    // Return updated submission
    const updated = await context.env.DB.prepare(
      'SELECT * FROM submissions WHERE id = ?'
    )
      .bind(id)
      .first();

    return jsonResponse({ ok: true, submission: updated });
  } catch (err) {
    console.error('Submission PATCH error:', err);
    return jsonResponse({ ok: false, error: 'Server error.' }, 500);
  }
}

// ── DELETE ───────────────────────────────────────────────────────

export async function onRequestDelete(context) {
  try {
    const id = context.params.id;

    // Check submission exists
    const existing = await context.env.DB.prepare(
      'SELECT id FROM submissions WHERE id = ?'
    )
      .bind(id)
      .first();

    if (!existing) {
      return jsonResponse({ ok: false, error: 'Submission not found.' }, 404);
    }

    // Fetch all attachments to delete from KV
    const attachments = await context.env.DB.prepare(
      'SELECT kv_key FROM attachments WHERE submission_id = ?'
    )
      .bind(id)
      .all();

    // Delete KV objects
    const kvKeys = (attachments.results || []).map((a) => a.kv_key);
    for (const key of kvKeys) {
      await context.env.UPLOADS.delete(key);
    }

    // Delete attachment rows
    await context.env.DB.prepare(
      'DELETE FROM attachments WHERE submission_id = ?'
    )
      .bind(id)
      .run();

    // Delete submission row
    await context.env.DB.prepare(
      'DELETE FROM submissions WHERE id = ?'
    )
      .bind(id)
      .run();

    return jsonResponse({ ok: true, deleted: id });
  } catch (err) {
    console.error('Submission DELETE error:', err);
    return jsonResponse({ ok: false, error: 'Server error.' }, 500);
  }
}

// ── CORS preflight ──────────────────────────────────────────────

export async function onRequestOptions() {
  return new Response(null, { headers: CORS_HEADERS });
}
