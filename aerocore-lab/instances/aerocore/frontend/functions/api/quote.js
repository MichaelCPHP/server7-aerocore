// Cloudflare Pages Function — Quote Form Submission Handler
// Receives form data via POST, sends email notification, returns JSON response
//
// Environment variables needed in Cloudflare Pages settings:
//   RESEND_API_KEY — API key from resend.com (free tier: 100 emails/day)
//   NOTIFY_EMAIL  — where to send notifications (default: Info@AreoCore.com)

export async function onRequestPost(context) {
  const headers = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
  };

  try {
    const body = await context.request.json();

    // Basic validation
    if (!body.name || !body.email) {
      return new Response(JSON.stringify({ ok: false, error: 'Name and email are required.' }), {
        status: 400,
        headers,
      });
    }

    // Simple email format check
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(body.email)) {
      return new Response(JSON.stringify({ ok: false, error: 'Invalid email address.' }), {
        status: 400,
        headers,
      });
    }

    // Honeypot check — if _gotcha field is filled, it's a bot
    if (body._gotcha) {
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers });
    }

    const notifyEmail = context.env.NOTIFY_EMAIL || 'Info@AreoCore.com';
    const apiKey = context.env.RESEND_API_KEY;

    // Build email body
    const lines = [
      `Name: ${body.name}`,
      `Company: ${body.company || '—'}`,
      `Email: ${body.email}`,
      `Phone: ${body.phone || '—'}`,
      `Material: ${body.material || '—'}`,
      `Details: ${body.details || '—'}`,
      `Source Page: ${body.source || '—'}`,
    ];

    if (body.utm && Object.keys(body.utm).length > 0) {
      lines.push('', '--- Ad Attribution ---');
      Object.entries(body.utm).forEach(([k, v]) => lines.push(`${k}: ${v}`));
    }

    lines.push('', `Submitted: ${new Date().toISOString()}`);

    const textBody = lines.join('\n');

    // Send via Resend if API key is configured
    if (apiKey) {
      const emailRes = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          from: 'AeroCore Quotes <quotes@areocore.com>',
          to: [notifyEmail],
          reply_to: body.email,
          subject: `Quote Request from ${body.name}${body.company ? ' (' + body.company + ')' : ''}`,
          text: textBody,
        }),
      });

      if (!emailRes.ok) {
        console.error('Resend API error:', await emailRes.text());
        return new Response(JSON.stringify({ ok: false, error: 'Failed to send notification.' }), {
          status: 500,
          headers,
        });
      }
    } else {
      // No email API configured — log to console (visible in Cloudflare dashboard logs)
      console.log('QUOTE SUBMISSION (no email API configured):', textBody);
    }

    return new Response(JSON.stringify({ ok: true }), { status: 200, headers });
  } catch (err) {
    console.error('Quote form error:', err);
    return new Response(JSON.stringify({ ok: false, error: 'Server error.' }), {
      status: 500,
      headers,
    });
  }
}

// Handle CORS preflight
export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    },
  });
}
