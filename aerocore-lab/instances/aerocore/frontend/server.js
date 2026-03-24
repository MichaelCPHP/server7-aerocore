#!/usr/bin/env node
// Frontend Dev Server — serves static files, CRM API, proxies remaining /api/* to lab
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { DatabaseSync } = require('node:sqlite');

// ── Paths ──────────────────────────────────────────────────────────
const FRONTEND_DIR = __dirname;
const PUBLIC_DIR = path.join(FRONTEND_DIR, 'public');
const INSTANCE_DIR = path.resolve(FRONTEND_DIR, '..');
const OUTPUT_DIR = path.join(INSTANCE_DIR, 'output');
const DB_PATH = path.join(OUTPUT_DIR, 'crm.db');
const UPLOADS_DIR = path.join(OUTPUT_DIR, 'uploads');
const PORT = parseInt(process.env.PORT || 3280);

let LAB_PORT = 3210;
try {
  const labConfig = JSON.parse(fs.readFileSync(path.join(INSTANCE_DIR, 'lab.json'), 'utf8'));
  LAB_PORT = labConfig.port || 3210;
} catch (e) {}

// ── Config from .dev.vars ──────────────────────────────────────────
const config = {
  ADMIN_USER: 'admin',
  ADMIN_PASS_HASH: '',
  SESSION_SECRET: '',
  CONVERSIONS_API_KEY: '',
  NOTIFY_EMAIL: 'Info@AreoCore.com',
};
try {
  const devVars = fs.readFileSync(path.join(FRONTEND_DIR, '.dev.vars'), 'utf8');
  devVars.split('\n').forEach(line => {
    const eq = line.indexOf('=');
    if (eq > 0) config[line.slice(0, eq).trim()] = line.slice(eq + 1).trim();
  });
} catch (e) {}

// ── Ensure directories ─────────────────────────────────────────────
fs.mkdirSync(OUTPUT_DIR, { recursive: true });
fs.mkdirSync(UPLOADS_DIR, { recursive: true });

// ── Database ───────────────────────────────────────────────────────
let db;
function getDb() {
  if (!db) {
    db = new DatabaseSync(DB_PATH);
    db.exec('PRAGMA journal_mode=WAL');
    db.exec('PRAGMA foreign_keys=ON');
    // Ensure schema
    db.exec(fs.readFileSync(path.join(FRONTEND_DIR, 'schema.sql'), 'utf8'));
  }
  return db;
}

// ── MIME types ──────────────────────────────────────────────────────
const MIME = {
  '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.xml': 'application/xml', '.txt': 'text/plain', '.ico': 'image/x-icon',
  '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
  '.woff2': 'font/woff2', '.woff': 'font/woff', '.pdf': 'application/pdf',
  '.gif': 'image/gif',
};

// ── Helpers ────────────────────────────────────────────────────────

function serveFile(res, filePath) {
  const ext = path.extname(filePath);
  const mime = MIME[ext] || 'application/octet-stream';
  try {
    const content = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': mime + (['.html', '.css', '.js'].includes(ext) ? '; charset=utf-8' : '') });
    res.end(content);
  } catch (e) { res.writeHead(404); res.end('Not found'); }
}

function proxyToLab(req, res) {
  const opts = { hostname: '127.0.0.1', port: LAB_PORT, path: req.url, method: req.method, headers: { ...req.headers, host: `127.0.0.1:${LAB_PORT}` } };
  const proxy = http.request(opts, labRes => { res.writeHead(labRes.statusCode, labRes.headers); labRes.pipe(res); });
  proxy.on('error', () => { res.writeHead(502); res.end('Lab backend not available'); });
  req.pipe(proxy);
}

function jsonRes(res, data, status = 200, extraHeaders = {}) {
  const body = JSON.stringify(data);
  res.writeHead(status, { 'Content-Type': 'application/json', ...extraHeaders });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

function readJsonBody(req) {
  return readBody(req).then(buf => JSON.parse(buf.toString('utf8')));
}

function parseCookies(header) {
  const cookies = {};
  if (!header) return cookies;
  header.split(';').forEach(pair => {
    const [name, ...rest] = pair.trim().split('=');
    if (name) cookies[name.trim()] = decodeURIComponent(rest.join('='));
  });
  return cookies;
}

// ── Auth helpers ───────────────────────────────────────────────────

function sha256Hex(str) {
  return crypto.createHash('sha256').update(str).digest('hex');
}

function signSession(payload) {
  const payloadB64 = Buffer.from(JSON.stringify(payload)).toString('base64');
  const sig = crypto.createHmac('sha256', config.SESSION_SECRET).update(payloadB64).digest('base64');
  return `${payloadB64}.${sig}`;
}

function verifySession(token) {
  if (!token || !config.SESSION_SECRET) return null;
  const parts = token.split('.');
  if (parts.length !== 2) return null;
  const [payloadB64, sig] = parts;
  const expected = crypto.createHmac('sha256', config.SESSION_SECRET).update(payloadB64).digest('base64');
  if (!crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) return null;
  try {
    const payload = JSON.parse(Buffer.from(payloadB64, 'base64').toString('utf8'));
    if (payload.exp && Date.now() > payload.exp) return null;
    return payload;
  } catch { return null; }
}

function requireAuth(req) {
  const cookies = parseCookies(req.headers.cookie);
  return verifySession(cookies.session);
}

function sessionCookie(token, maxAge = 86400) {
  return `session=${encodeURIComponent(token)}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${maxAge}`;
}

// ── Multipart parser ───────────────────────────────────────────────

const MAX_FILE_SIZE = 25 * 1024 * 1024;

function parseMultipart(buf, contentType) {
  const m = contentType.match(/boundary=(?:"([^"]+)"|([^\s;]+))/i);
  if (!m) return { fields: {}, files: [] };
  const delimiter = '--' + (m[1] || m[2]);
  const fields = {};
  const files = [];

  // Find all delimiter positions
  const positions = [];
  let searchFrom = 0;
  while (true) {
    const idx = buf.indexOf(delimiter, searchFrom);
    if (idx === -1) break;
    positions.push(idx);
    searchFrom = idx + delimiter.length;
  }

  // Extract parts between consecutive delimiters
  for (let i = 0; i < positions.length - 1; i++) {
    let partStart = positions[i] + delimiter.length;
    let partEnd = positions[i + 1];
    // Trim \r\n after delimiter and before next delimiter
    if (buf[partStart] === 0x0d && buf[partStart + 1] === 0x0a) partStart += 2;
    if (partEnd >= 2 && buf[partEnd - 2] === 0x0d && buf[partEnd - 1] === 0x0a) partEnd -= 2;
    if (partEnd <= partStart) continue;

    const part = buf.subarray(partStart, partEnd);
    const sepIdx = part.indexOf('\r\n\r\n');
    if (sepIdx === -1) continue;

    const headers = part.subarray(0, sepIdx).toString('utf8');
    const body = part.subarray(sepIdx + 4);

    const nameMatch = headers.match(/name="([^"]+)"/i);
    if (!nameMatch) continue;
    const name = nameMatch[1];
    const filenameMatch = headers.match(/filename="([^"]*)"/i);

    if (filenameMatch && filenameMatch[1]) {
      const typeMatch = headers.match(/Content-Type:\s*(.+)/i);
      files.push({
        fieldName: name,
        filename: filenameMatch[1],
        contentType: typeMatch ? typeMatch[1].trim() : 'application/octet-stream',
        data: body,
        size: body.length,
      });
    } else {
      // Handle curl's multipart/mixed nesting (triggered by parens in values)
      const mixedMatch = headers.match(/Content-Type:\s*multipart\/mixed;\s*boundary=(?:"([^"]+)"|([^\s;]+))/i);
      if (mixedMatch) {
        const nested = parseMultipart(body, `multipart/mixed; boundary=${mixedMatch[1] || mixedMatch[2]}`);
        // Extract the first text value from the nested body
        const vals = Object.values(nested.fields);
        fields[name] = vals.length > 0 ? vals[0] : body.toString('utf8');
      } else {
        fields[name] = body.toString('utf8');
      }
    }
  }
  return { fields, files };
}

// ── CRM Route Handlers ────────────────────────────────────────────

// POST /api/auth/login
async function handleLogin(req, res) {
  try {
    const { username, password } = await readJsonBody(req);
    if (!username || !password) return jsonRes(res, { ok: false, error: 'Username and password required.' }, 400);
    if (!config.ADMIN_PASS_HASH || !config.SESSION_SECRET) return jsonRes(res, { ok: false, error: 'Server misconfigured.' }, 500);

    const inputHash = sha256Hex(password);
    if (username !== config.ADMIN_USER || inputHash !== config.ADMIN_PASS_HASH.toLowerCase()) {
      return jsonRes(res, { ok: false, error: 'Invalid credentials' }, 401);
    }

    const exp = Date.now() + 86400 * 1000;
    const token = signSession({ user: username, exp });
    jsonRes(res, { ok: true }, 200, { 'Set-Cookie': sessionCookie(token) });
  } catch (err) {
    console.error('Login error:', err);
    jsonRes(res, { ok: false, error: 'Server error.' }, 500);
  }
}

// POST /api/auth/logout
function handleLogout(req, res) {
  jsonRes(res, { ok: true }, 200, { 'Set-Cookie': sessionCookie('', 0) });
}

// GET /api/auth/check
function handleAuthCheck(req, res) {
  const session = requireAuth(req);
  if (!session) return jsonRes(res, { ok: false, error: 'Authentication required.' }, 401);
  jsonRes(res, { ok: true, user: session.user || 'admin' });
}

// POST /api/quote
async function handleQuote(req, res) {
  try {
    const buf = await readBody(req);
    const contentType = req.headers['content-type'] || '';
    if (!contentType.includes('multipart/form-data')) return jsonRes(res, { ok: false, error: 'Invalid content type.' }, 400);

    const { fields, files } = parseMultipart(buf, contentType);

    const fg = (key) => (fields[key] || '').trim();
    const name = fg('name');
    const email = fg('email');
    const company = fg('company');
    const phone = fg('phone');
    const material = fg('material');
    const details = fg('details');
    const source = fg('source');
    const gotcha = fg('_gotcha');

    const utm_source = fg('utm_source') || null;
    const utm_medium = fg('utm_medium') || null;
    const utm_campaign = fg('utm_campaign') || null;
    const utm_term = fg('utm_term') || null;
    const utm_content = fg('utm_content') || null;
    const gclid = fg('gclid') || null;

    // Honeypot
    if (gotcha) return jsonRes(res, { ok: true });

    // Validate
    if (!name || !email) return jsonRes(res, { ok: false, error: 'Name and email are required.' }, 400);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return jsonRes(res, { ok: false, error: 'Invalid email address.' }, 400);

    const now = new Date().toISOString();
    const d = getDb();

    const insertStmt = d.prepare(
      `INSERT INTO submissions
        (name, company, email, phone, material, details, source_page,
         utm_source, utm_medium, utm_campaign, utm_term, utm_content, gclid,
         status, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)`
    );
    const result = insertStmt.run(
      name, company, email, phone, material, details, source,
      utm_source, utm_medium, utm_campaign, utm_term, utm_content, gclid,
      now, now
    );
    const submissionId = Number(result.lastInsertRowid);

    // Handle file attachments — save to disk
    const attachStmt = d.prepare(
      `INSERT INTO attachments
        (submission_id, filename, original_name, content_type, size_bytes, kv_key, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`
    );
    const warnings = [];
    for (const file of files) {
      if (file.fieldName !== 'files') continue;
      if (file.size > MAX_FILE_SIZE) { warnings.push(`${file.filename} exceeds 25 MB limit`); continue; }

      const uuid = crypto.randomUUID();
      const ext = path.extname(file.filename) || '';
      const diskName = uuid + ext;
      const subDir = path.join(UPLOADS_DIR, String(submissionId));
      fs.mkdirSync(subDir, { recursive: true });
      fs.writeFileSync(path.join(subDir, diskName), file.data);

      const kvKey = `submissions/${submissionId}/${uuid}`;
      attachStmt.run(submissionId, diskName, file.filename, file.contentType, file.size, kvKey, now);
    }

    console.log(`[CRM] New quote submission #${submissionId} from ${name} <${email}>`);

    const response = { ok: true, id: submissionId };
    if (warnings.length > 0) response.warnings = warnings;
    jsonRes(res, response);
  } catch (err) {
    console.error('Quote form error:', err);
    jsonRes(res, { ok: false, error: 'Server error.' }, 500);
  }
}

// GET /api/submissions
function handleSubmissionsList(req, res) {
  const session = requireAuth(req);
  if (!session) return jsonRes(res, { ok: false, error: 'Authentication required.' }, 401);

  try {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const params = url.searchParams;

    const status = params.get('status') || null;
    const q = params.get('q') || params.get('search') || null;
    const from = params.get('from') || null;
    const to = params.get('to') || null;
    const page = Math.max(1, parseInt(params.get('page'), 10) || 1);
    const perPage = Math.min(200, Math.max(1, parseInt(params.get('perPage'), 10) || 50));
    const offset = (page - 1) * perPage;

    const conditions = [];
    const bindings = [];

    if (status) { conditions.push('s.status = ?'); bindings.push(status); }
    if (q) {
      conditions.push('(s.name LIKE ? OR s.company LIKE ? OR s.email LIKE ?)');
      const p = `%${q}%`;
      bindings.push(p, p, p);
    }
    if (from) { conditions.push('s.created_at >= ?'); bindings.push(from); }
    if (to) {
      const toVal = to.length === 10 ? `${to}T23:59:59.999Z` : to;
      conditions.push('s.created_at <= ?');
      bindings.push(toVal);
    }

    const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
    const d = getDb();

    const countRow = d.prepare(`SELECT COUNT(*) AS total FROM submissions s ${where}`).get(...bindings);
    const total = countRow ? countRow.total : 0;

    const rows = d.prepare(`
      SELECT s.*,
        COALESCE(a.attachment_count, 0) AS attachment_count
      FROM submissions s
      LEFT JOIN (
        SELECT submission_id, COUNT(*) AS attachment_count
        FROM attachments GROUP BY submission_id
      ) a ON a.submission_id = s.id
      ${where}
      ORDER BY s.created_at DESC
      LIMIT ? OFFSET ?
    `).all(...bindings, perPage, offset);

    jsonRes(res, { submissions: rows, total, page, perPage });
  } catch (err) {
    console.error('Submissions list error:', err);
    jsonRes(res, { ok: false, error: 'Server error.' }, 500);
  }
}

// GET /api/submissions/:id
function handleSubmissionGet(req, res, id) {
  const session = requireAuth(req);
  if (!session) return jsonRes(res, { ok: false, error: 'Authentication required.' }, 401);

  try {
    const d = getDb();
    const submission = d.prepare('SELECT * FROM submissions WHERE id = ?').get(id);
    if (!submission) return jsonRes(res, { ok: false, error: 'Submission not found.' }, 404);

    const attachments = d.prepare(
      'SELECT id, filename, original_name, content_type, size_bytes, created_at FROM attachments WHERE submission_id = ? ORDER BY created_at'
    ).all(id);

    jsonRes(res, { ...submission, attachments });
  } catch (err) {
    console.error('Submission GET error:', err);
    jsonRes(res, { ok: false, error: 'Server error.' }, 500);
  }
}

// PATCH /api/submissions/:id
async function handleSubmissionPatch(req, res, id) {
  const session = requireAuth(req);
  if (!session) return jsonRes(res, { ok: false, error: 'Authentication required.' }, 401);

  try {
    const body = await readJsonBody(req);
    const d = getDb();

    const existing = d.prepare('SELECT id FROM submissions WHERE id = ?').get(id);
    if (!existing) return jsonRes(res, { ok: false, error: 'Submission not found.' }, 404);

    const fields = [];
    const values = [];
    if (body.status !== undefined) { fields.push('status = ?'); values.push(body.status); }
    if (body.notes !== undefined) { fields.push('notes = ?'); values.push(body.notes); }
    if (fields.length === 0) return jsonRes(res, { ok: false, error: 'No fields to update.' }, 400);

    fields.push('updated_at = ?');
    values.push(new Date().toISOString());
    values.push(id);

    d.prepare(`UPDATE submissions SET ${fields.join(', ')} WHERE id = ?`).run(...values);
    const updated = d.prepare('SELECT * FROM submissions WHERE id = ?').get(id);
    jsonRes(res, { ok: true, submission: updated });
  } catch (err) {
    console.error('Submission PATCH error:', err);
    jsonRes(res, { ok: false, error: 'Server error.' }, 500);
  }
}

// DELETE /api/submissions/:id
function handleSubmissionDelete(req, res, id) {
  const session = requireAuth(req);
  if (!session) return jsonRes(res, { ok: false, error: 'Authentication required.' }, 401);

  try {
    const d = getDb();
    const existing = d.prepare('SELECT id FROM submissions WHERE id = ?').get(id);
    if (!existing) return jsonRes(res, { ok: false, error: 'Submission not found.' }, 404);

    // Delete files from disk
    const uploadsSubDir = path.join(UPLOADS_DIR, String(id));
    if (fs.existsSync(uploadsSubDir)) {
      fs.rmSync(uploadsSubDir, { recursive: true, force: true });
    }

    d.prepare('DELETE FROM attachments WHERE submission_id = ?').run(id);
    d.prepare('DELETE FROM submissions WHERE id = ?').run(id);
    jsonRes(res, { ok: true, deleted: id });
  } catch (err) {
    console.error('Submission DELETE error:', err);
    jsonRes(res, { ok: false, error: 'Server error.' }, 500);
  }
}

// GET /api/attachments/:id
function handleAttachment(req, res, id) {
  const session = requireAuth(req);
  if (!session) return jsonRes(res, { ok: false, error: 'Authentication required.' }, 401);

  try {
    const d = getDb();
    const att = d.prepare('SELECT * FROM attachments WHERE id = ?').get(id);
    if (!att) return jsonRes(res, { ok: false, error: 'Attachment not found.' }, 404);

    // Find file on disk
    const subId = att.submission_id;
    const diskPath = path.join(UPLOADS_DIR, String(subId), att.filename);
    if (!fs.existsSync(diskPath)) return jsonRes(res, { ok: false, error: 'File not found on disk.' }, 404);

    const safeName = (att.original_name || att.filename || 'download').replace(/[^\w.\-]/g, '_');
    const fileData = fs.readFileSync(diskPath);
    res.writeHead(200, {
      'Content-Type': att.content_type || 'application/octet-stream',
      'Content-Disposition': `inline; filename="${safeName}"`,
      'Content-Length': String(fileData.length),
      'Cache-Control': 'private, max-age=3600',
    });
    res.end(fileData);
  } catch (err) {
    console.error('Attachment download error:', err);
    jsonRes(res, { ok: false, error: 'Server error.' }, 500);
  }
}

// GET /api/conversions
function handleConversions(req, res) {
  const apiKey = req.headers['x-api-key'];
  if (!config.CONVERSIONS_API_KEY) return jsonRes(res, { ok: false, error: 'Conversions API not configured.' }, 500);
  if (!apiKey || apiKey !== config.CONVERSIONS_API_KEY) return jsonRes(res, { ok: false, error: 'Invalid or missing API key.' }, 401);

  try {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const params = url.searchParams;
    const from = params.get('from') || null;
    const to = params.get('to') || null;
    const hasGclid = params.get('has_gclid') === 'true';
    const format = params.get('format') || null;

    const conditions = [];
    const bindings = [];
    if (from) { conditions.push('created_at >= ?'); bindings.push(from); }
    if (to) {
      const toVal = to.length === 10 ? `${to}T23:59:59.999Z` : to;
      conditions.push('created_at <= ?');
      bindings.push(toVal);
    }
    if (hasGclid) conditions.push("gclid IS NOT NULL AND gclid != ''");

    const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
    const d = getDb();
    const submissions = d.prepare(`
      SELECT id, name, company, email, material, gclid,
             utm_source, utm_medium, utm_campaign, utm_term,
             status, created_at
      FROM submissions ${where} ORDER BY created_at DESC
    `).all(...bindings);

    if (format === 'gads') {
      const conversions = submissions.filter(s => s.gclid).map(s => ({
        'Google Click ID': s.gclid,
        'Conversion Name': 'Quote Request',
        'Conversion Time': s.created_at,
        'Conversion Value': '',
        'Conversion Currency': 'USD',
      }));
      return jsonRes(res, { ok: true, format: 'gads', conversions, total: conversions.length });
    }

    jsonRes(res, { ok: true, submissions, total: submissions.length });
  } catch (err) {
    console.error('Conversions API error:', err);
    jsonRes(res, { ok: false, error: 'Server error.' }, 500);
  }
}

// ── Router ─────────────────────────────────────────────────────────

const CRM_ROUTES = new Set([
  '/api/quote', '/api/auth/login', '/api/auth/logout', '/api/auth/check',
  '/api/submissions', '/api/conversions',
]);

function isCrmRoute(pathname) {
  if (CRM_ROUTES.has(pathname)) return true;
  if (pathname.startsWith('/api/submissions/')) return true;
  if (pathname.startsWith('/api/attachments/')) return true;
  return false;
}

async function handleCrmRoute(req, res, pathname, method) {
  // Auth routes
  if (pathname === '/api/auth/login' && method === 'POST') return handleLogin(req, res);
  if (pathname === '/api/auth/logout' && method === 'POST') return handleLogout(req, res);
  if (pathname === '/api/auth/check' && method === 'GET') return handleAuthCheck(req, res);

  // Quote form
  if (pathname === '/api/quote' && method === 'POST') return handleQuote(req, res);

  // Submissions list
  if (pathname === '/api/submissions' && method === 'GET') return handleSubmissionsList(req, res);

  // Single submission
  const subMatch = pathname.match(/^\/api\/submissions\/(\d+)$/);
  if (subMatch) {
    const id = parseInt(subMatch[1], 10);
    if (method === 'GET') return handleSubmissionGet(req, res, id);
    if (method === 'PATCH') return handleSubmissionPatch(req, res, id);
    if (method === 'DELETE') return handleSubmissionDelete(req, res, id);
  }

  // Attachments
  const attMatch = pathname.match(/^\/api\/attachments\/(\d+)$/);
  if (attMatch) {
    const id = parseInt(attMatch[1], 10);
    if (method === 'GET') return handleAttachment(req, res, id);
  }

  // Conversions
  if (pathname === '/api/conversions' && method === 'GET') return handleConversions(req, res);

  // Method not allowed
  jsonRes(res, { error: 'Method not allowed' }, 405);
}

// ── Static file serving ────────────────────────────────────────────

function resolveStaticFile(pathname) {
  if (pathname === '/') return path.join(PUBLIC_DIR, 'index.html');

  let filePath = path.join(PUBLIC_DIR, pathname);
  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) return filePath;

  const htmlPath = path.join(PUBLIC_DIR, pathname + '.html');
  if (fs.existsSync(htmlPath) && fs.statSync(htmlPath).isFile()) return htmlPath;

  const dirIndex = path.join(PUBLIC_DIR, pathname, 'index.html');
  if (fs.existsSync(dirIndex) && fs.statSync(dirIndex).isFile()) return dirIndex;

  const notFound = path.join(PUBLIC_DIR, '404.html');
  return fs.existsSync(notFound) ? notFound : path.join(PUBLIC_DIR, 'index.html');
}

// ── HTTP Server ────────────────────────────────────────────────────

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const pathname = url.pathname.replace(/\/+$/, '') || '/';
  const method = req.method.toUpperCase();

  // CRM API routes — handle locally
  if (pathname.startsWith('/api/') && isCrmRoute(pathname)) {
    try {
      await handleCrmRoute(req, res, pathname, method);
    } catch (err) {
      console.error('CRM route error:', err);
      if (!res.headersSent) jsonRes(res, { error: 'Internal server error' }, 500);
    }
    return;
  }

  // Other /api/* routes — proxy to lab server
  if (pathname.startsWith('/api/')) {
    proxyToLab(req, res);
    return;
  }

  // Static files
  serveFile(res, resolveStaticFile(pathname));
});

server.listen(PORT, () => {
  console.log(`  Frontend: http://localhost:${PORT}`);
  console.log(`  Backend:  http://localhost:${LAB_PORT}`);
  console.log(`  CRM DB:   ${DB_PATH}`);
  console.log(`  Uploads:  ${UPLOADS_DIR}`);
});
