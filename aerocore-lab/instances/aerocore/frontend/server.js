#!/usr/bin/env node
// Frontend Dev Server — serves static files + proxies to lab API
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const FRONTEND_DIR = __dirname;
const PUBLIC_DIR = path.join(FRONTEND_DIR, 'public');
const PORT = parseInt(process.env.PORT || 3280);

let LAB_PORT = 3210;
try {
  const labConfig = JSON.parse(fs.readFileSync(path.join(FRONTEND_DIR, '..', 'lab.json'), 'utf8'));
  LAB_PORT = labConfig.port || 3210;
} catch (e) {}

let THEME = { name: 'default', primary: '#c8a55a', bg: '#0a0b10', text: '#e4e4ec' };
try {
  THEME = { ...THEME, ...JSON.parse(fs.readFileSync(path.join(FRONTEND_DIR, 'theme', 'theme.json'), 'utf8')) };
} catch (e) {}

const MIME = {
  '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.xml': 'application/xml', '.txt': 'text/plain', '.ico': 'image/x-icon',
  '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
  '.woff2': 'font/woff2', '.woff': 'font/woff',
};

function serveFile(res, filePath) {
  const ext = path.extname(filePath);
  const mime = MIME[ext] || 'application/octet-stream';
  try {
    const content = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': mime + (['.html','.css','.js'].includes(ext) ? '; charset=utf-8' : '') });
    res.end(content);
  } catch (e) { res.writeHead(404); res.end('Not found'); }
}

function proxyToLab(req, res) {
  const opts = { hostname: '127.0.0.1', port: LAB_PORT, path: req.url, method: req.method, headers: { ...req.headers, host: `127.0.0.1:${LAB_PORT}` } };
  const proxy = http.request(opts, labRes => { res.writeHead(labRes.statusCode, labRes.headers); labRes.pipe(res); });
  proxy.on('error', () => { res.writeHead(502); res.end('Lab backend not available'); });
  req.pipe(proxy);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  if (url.pathname.startsWith('/api/')) { proxyToLab(req, res); return; }

  // Resolve file path with clean URL support
  let filePath;
  const pathname = url.pathname.replace(/\/+$/, '') || '/';

  if (pathname === '/') {
    filePath = path.join(PUBLIC_DIR, 'index.html');
  } else {
    // Try exact file first
    filePath = path.join(PUBLIC_DIR, pathname);
    if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
      // Try pathname.html
      const htmlPath = path.join(PUBLIC_DIR, pathname + '.html');
      if (fs.existsSync(htmlPath) && fs.statSync(htmlPath).isFile()) {
        filePath = htmlPath;
      } else {
        // Try pathname/index.html (directory-based routing)
        const dirIndex = path.join(PUBLIC_DIR, pathname, 'index.html');
        if (fs.existsSync(dirIndex) && fs.statSync(dirIndex).isFile()) {
          filePath = dirIndex;
        } else {
          // 404 fallback
          filePath = path.join(PUBLIC_DIR, '404.html');
          if (!fs.existsSync(filePath)) filePath = path.join(PUBLIC_DIR, 'index.html');
        }
      }
    }
  }

  serveFile(res, filePath);
});

server.listen(PORT, () => {
  console.log(`  Frontend: http://localhost:${PORT}`);
  console.log(`  Backend:  http://localhost:${LAB_PORT}`);
});
