// Cloudflare Pages Function — Attachment Download
// GET /api/attachments/:id — stream file from KV with correct headers

export async function onRequestGet(context) {
  try {
    const id = context.params.id;

    // Look up attachment record in D1
    const attachment = await context.env.DB.prepare(
      'SELECT * FROM attachments WHERE id = ?'
    )
      .bind(id)
      .first();

    if (!attachment) {
      return new Response(JSON.stringify({ ok: false, error: 'Attachment not found.' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Fetch file data from KV
    const fileData = await context.env.UPLOADS.get(attachment.kv_key, { type: 'arrayBuffer' });

    if (!fileData) {
      return new Response(JSON.stringify({ ok: false, error: 'File data not found in storage.' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Determine safe filename for Content-Disposition
    const safeName = (attachment.original_name || attachment.filename || 'download')
      .replace(/[^\w.\-]/g, '_');

    return new Response(fileData, {
      status: 200,
      headers: {
        'Content-Type': attachment.content_type || 'application/octet-stream',
        'Content-Disposition': `attachment; filename="${safeName}"`,
        'Content-Length': String(attachment.size_bytes || fileData.byteLength),
        'Cache-Control': 'private, max-age=3600',
      },
    });
  } catch (err) {
    console.error('Attachment download error:', err);
    return new Response(JSON.stringify({ ok: false, error: 'Server error.' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
