// Cloudflare Pages Function — Quote Form Submission Handler
// Accepts multipart/form-data with file attachments.
// Stores submissions in D1, attachments in Workers KV.
//
// Environment bindings:
//   DB            — Cloudflare D1 database
//   UPLOADS       — Cloudflare Workers KV namespace
//   RESEND_API_KEY — Resend email API key
//   NOTIFY_EMAIL   — notification recipient

const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

// ── POST handler ────────────────────────────────────────────────

export async function onRequestPost(context) {
  try {
    const formData = await context.request.formData();

    // Parse fields
    const name = formData.get('name')?.trim() || '';
    const email = formData.get('email')?.trim() || '';
    const company = formData.get('company')?.trim() || '';
    const phone = formData.get('phone')?.trim() || '';
    const material = formData.get('material')?.trim() || '';
    const details = formData.get('details')?.trim() || '';
    const source = formData.get('source')?.trim() || '';
    const gotcha = formData.get('_gotcha') || '';

    // UTM / attribution
    const utm_source = formData.get('utm_source')?.trim() || null;
    const utm_medium = formData.get('utm_medium')?.trim() || null;
    const utm_campaign = formData.get('utm_campaign')?.trim() || null;
    const utm_term = formData.get('utm_term')?.trim() || null;
    const utm_content = formData.get('utm_content')?.trim() || null;
    const gclid = formData.get('gclid')?.trim() || null;

    // Honeypot — silent success for bots
    if (gotcha) {
      return jsonResponse({ ok: true });
    }

    // Validation
    if (!name || !email) {
      return jsonResponse({ ok: false, error: 'Name and email are required.' }, 400);
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return jsonResponse({ ok: false, error: 'Invalid email address.' }, 400);
    }

    const now = new Date().toISOString();

    // ── Insert submission into D1 ───────────────────────────────

    const insertResult = await context.env.DB.prepare(
      `INSERT INTO submissions
        (name, company, email, phone, material, details, source_page,
         utm_source, utm_medium, utm_campaign, utm_term, utm_content, gclid,
         status, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)`
    )
      .bind(
        name, company, email, phone, material, details, source,
        utm_source, utm_medium, utm_campaign, utm_term, utm_content, gclid,
        now, now,
      )
      .run();

    const submissionId = insertResult.meta.last_row_id;

    // ── Handle file attachments ─────────────────────────────────

    const files = formData.getAll('files');
    const attachmentErrors = [];

    for (const file of files) {
      // formData.getAll may return strings for empty fields — skip non-File entries
      if (!(file instanceof File) || file.size === 0) continue;

      if (file.size > MAX_FILE_SIZE) {
        attachmentErrors.push(`${file.name} exceeds 25 MB limit`);
        continue;
      }

      const kvKey = `submissions/${submissionId}/${crypto.randomUUID()}`;
      const arrayBuffer = await file.arrayBuffer();

      // Store in KV
      await context.env.UPLOADS.put(kvKey, arrayBuffer, {
        metadata: {
          originalName: file.name,
          contentType: file.type,
          submissionId,
        },
      });

      // Record in D1
      await context.env.DB.prepare(
        `INSERT INTO attachments
          (submission_id, filename, original_name, content_type, size_bytes, kv_key, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`
      )
        .bind(
          submissionId,
          kvKey.split('/').pop(), // UUID filename
          file.name,
          file.type || 'application/octet-stream',
          file.size,
          kvKey,
          now,
        )
        .run();
    }

    // ── Send email notification ─────────────────────────────────

    const apiKey = context.env.RESEND_API_KEY;
    const notifyEmail = context.env.NOTIFY_EMAIL || 'Info@AreoCore.com';

    if (apiKey) {
      const lines = [
        `Name: ${name}`,
        `Company: ${company || '\u2014'}`,
        `Email: ${email}`,
        `Phone: ${phone || '\u2014'}`,
        `Material: ${material || '\u2014'}`,
        `Details: ${details || '\u2014'}`,
        `Source Page: ${source || '\u2014'}`,
      ];

      if (utm_source || utm_medium || utm_campaign) {
        lines.push('', '--- Ad Attribution ---');
        if (utm_source) lines.push(`Source: ${utm_source}`);
        if (utm_medium) lines.push(`Medium: ${utm_medium}`);
        if (utm_campaign) lines.push(`Campaign: ${utm_campaign}`);
        if (utm_term) lines.push(`Term: ${utm_term}`);
        if (utm_content) lines.push(`Content: ${utm_content}`);
        if (gclid) lines.push(`GCLID: ${gclid}`);
      }

      const fileCount = files.filter((f) => f instanceof File && f.size > 0).length;
      if (fileCount > 0) {
        lines.push('', `Attachments: ${fileCount} file(s)`);
      }

      lines.push('', `Submitted: ${now}`);
      lines.push(`Submission ID: ${submissionId}`);

      try {
        const emailRes = await fetch('https://api.resend.com/emails', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${apiKey}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            from: 'AeroCore Quotes <quotes@areocore.com>',
            to: [notifyEmail],
            reply_to: email,
            subject: `Quote Request from ${name}${company ? ' (' + company + ')' : ''}`,
            text: lines.join('\n'),
          }),
        });

        if (!emailRes.ok) {
          console.error('Resend API error:', await emailRes.text());
        }
      } catch (emailErr) {
        console.error('Email send failed:', emailErr);
      }
    } else {
      console.log('QUOTE SUBMISSION (no email API configured):', { name, email, company, submissionId });
    }

    // ── Response ────────────────────────────────────────────────

    const response = { ok: true, id: submissionId };
    if (attachmentErrors.length > 0) {
      response.warnings = attachmentErrors;
    }

    return jsonResponse(response);
  } catch (err) {
    console.error('Quote form error:', err);
    return jsonResponse({ ok: false, error: 'Server error.' }, 500);
  }
}

// ── CORS preflight ──────────────────────────────────────────────

export async function onRequestOptions() {
  return new Response(null, { headers: CORS_HEADERS });
}
