#!/usr/bin/env node
// Lab Platform — Launcher
// Grid UI for managing lab instances. Start, stop, open, create.

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { randomUUID } = require('node:crypto');

const PLATFORM_DIR = __dirname;
const INSTANCES_DIR = path.join(PLATFORM_DIR, 'instances');
const SERVER_ROOT = process.env.SERVER_ROOT || path.resolve(PLATFORM_DIR, '..');
const GENESIS_DIR = process.env.GENESIS_DIR || path.join(SERVER_ROOT, 'genesis');
const CORE_SERVER = path.join(GENESIS_DIR, 'template', 'core', 'server.js');
const GLOBAL_PLUGINS_DIR = path.join(GENESIS_DIR, 'template', 'plugins');
const GLOBAL_SKILLS_DIR = path.join(GENESIS_DIR, 'template', 'skills');

// Read server.json for port base (defaults to 3000 for backward compatibility)
let SERVER_CONFIG = {};
try { SERVER_CONFIG = JSON.parse(fs.readFileSync(path.join(SERVER_ROOT, 'server.json'), 'utf8')); } catch (e) {}
const PORT_BASE = SERVER_CONFIG.portBase || 3000;
const PORT = parseInt(process.env.LAUNCHER_PORT || (PORT_BASE + 200), 10);

// Ensure instances directory exists
try { fs.mkdirSync(INSTANCES_DIR, { recursive: true }); } catch (e) {}

// Track running instances
const running = {}; // id -> { proc, port }

function getInstances() {
  const instances = [];
  try {
    for (const name of fs.readdirSync(INSTANCES_DIR)) {
      const dir = path.join(INSTANCES_DIR, name);
      const configPath = path.join(dir, 'lab.json');
      if (!fs.statSync(dir).isDirectory()) continue;
      if (!fs.existsSync(configPath)) continue;
      try {
        const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
        const hasFrontend = fs.existsSync(path.join(dir, 'frontend', 'server.js'));
        instances.push({
          id: name,
          name: config.name || name,
          description: config.description || '',
          icon: config.icon || '\u2697',
          color: config.color || '#888',
          port: config.port || 3210,
          frontendPort: (config.port || 3210) + 70,
          model: config.model || 'opus',
          running: !!running[name],
          hasFrontend,
        });
      } catch (e) {}
    }
  } catch (e) {}
  return instances;
}

function startInstance(id) {
  if (running[id]) return { port: running[id].port, already: true };
  const dir = path.join(INSTANCES_DIR, id);
  const configPath = path.join(dir, 'lab.json');
  if (!fs.existsSync(configPath)) return null;
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  const port = config.port || 3210;

  const proc = spawn('node', [CORE_SERVER], {
    cwd: dir,
    env: { ...process.env, LAB_INSTANCE: dir, LAB_PORT: String(port), SERVER_ROOT, GENESIS_DIR, GLOBAL_PLUGINS_DIR, GLOBAL_SKILLS_DIR },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  proc.stdout.on('data', d => process.stdout.write(`[${id}] ${d}`));
  proc.stderr.on('data', d => process.stderr.write(`[${id}] ${d}`));
  proc.on('close', () => { delete running[id]; });
  running[id] = { proc, port, frontendProc: null, frontendPort: null };

  // Start frontend if it exists
  const frontendServer = path.join(dir, 'frontend', 'server.js');
  const frontendPort = port + 70;
  if (fs.existsSync(frontendServer)) {
    const fProc = spawn('node', [frontendServer], {
      cwd: dir,
      env: { ...process.env, PORT: String(frontendPort) },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    fProc.stdout.on('data', d => process.stdout.write(`[${id}-fe] ${d}`));
    fProc.stderr.on('data', d => process.stderr.write(`[${id}-fe] ${d}`));
    running[id].frontendProc = fProc;
    running[id].frontendPort = frontendPort;
    console.log(`  Frontend: http://localhost:${frontendPort}`);
  }

  console.log(`  Started ${config.name || id} on port ${port}`);
  return { port, frontendPort: running[id].frontendPort, already: false };
}

function stopInstance(id) {
  if (!running[id]) return false;
  running[id].proc.kill();
  if (running[id].frontendProc) running[id].frontendProc.kill();
  delete running[id];
  return true;
}

function createInstance(name, description, icon, color) {
  const id = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const dir = path.join(INSTANCES_DIR, id);
  if (fs.existsSync(dir)) return { error: 'Instance already exists' };

  // Find next available port (offset from server port base)
  const usedPorts = getInstances().map(i => i.port);
  let port = PORT_BASE + 211;
  while (usedPorts.includes(port)) port++;

  fs.mkdirSync(path.join(dir, 'data'), { recursive: true });
  fs.mkdirSync(path.join(dir, 'kb', 'sessions', 'messages'), { recursive: true });
  fs.mkdirSync(path.join(dir, 'kb', 'transcripts'), { recursive: true });
  fs.mkdirSync(path.join(dir, 'output'), { recursive: true });
  fs.mkdirSync(path.join(dir, 'scripts'), { recursive: true });
  fs.mkdirSync(path.join(dir, 'docs'), { recursive: true });

  const config = {
    name: name,
    description: description || '',
    icon: icon || '\u2697',
    color: color || '#4a8fe7',
    port: port,
    model: 'opus',
    role: `You are the ${name} AI assistant. You have full access to the project files, scripts, and knowledge base.`,
    plugins: ['core/*'],
    apis: [],
    dataDir: 'data',
    scriptsDir: 'scripts',
    kbDir: 'kb',
    outputDir: 'output',
  };

  fs.writeFileSync(path.join(dir, 'lab.json'), JSON.stringify(config, null, 2));
  fs.writeFileSync(path.join(dir, 'kb', 'sessions', 'sessions.json'), '[]');
  fs.writeFileSync(path.join(dir, 'kb', 'sessions', 'projects.json'), '[]');

  console.log(`  Created instance: ${name} (${id}) on port ${port}`);
  return { id, port };
}

function parseBody(req) {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => { try { resolve(JSON.parse(body)); } catch (e) { resolve({}); } });
  });
}

// SVG favicon — simple beaker
const FAVICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><text y="28" font-size="28">⚗</text></svg>`;

const LAUNCHER_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lab Platform</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><text y='28' font-size='28'>⚗</text></svg>">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0a0b10;--bg2:#12131a;--bg3:#181924;--border:#1e2030;--text:#e4e4ec;--text2:#9a9ab0;--radius:12px}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:60px 20px}
h1{font-size:28px;font-weight:300;margin-bottom:8px}
.subtitle{color:var(--text2);font-size:14px;margin-bottom:40px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px;width:100%;max-width:960px}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);padding:24px;transition:all 0.2s;position:relative;overflow:hidden}
.card:hover{border-color:var(--accent,#888);transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,0.3)}
.card-icon{font-size:36px;margin-bottom:12px}
.card-name{font-size:18px;font-weight:600;margin-bottom:6px}
.card-desc{font-size:13px;color:var(--text2);line-height:1.5;margin-bottom:16px;min-height:40px}
.card-meta{font-size:10px;color:var(--text2);margin-bottom:12px;display:flex;gap:12px}
.card-status{font-size:11px;display:flex;align-items:center;gap:6px;margin-bottom:14px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.dot.running{background:#3ac77e;box-shadow:0 0 6px #3ac77e}
.dot.stopped{background:#555}
.card-actions{display:flex;gap:8px}
.btn{padding:7px 16px;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--text);font-size:12px;cursor:pointer;transition:all 0.15s}
.btn:hover{background:rgba(255,255,255,0.05)}
.btn:disabled{opacity:0.4;cursor:not-allowed}
.btn.primary{background:var(--accent,#888);border-color:var(--accent,#888);color:#000;font-weight:600}
.btn.primary:hover{opacity:0.9}
.btn.danger{border-color:#e7554a;color:#e7554a}
.btn.danger:hover{background:rgba(231,85,74,0.1)}
.new-card{border-style:dashed;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:200px;color:var(--text2);cursor:pointer}
.new-card:hover{color:var(--text);border-color:var(--text2)}
.new-icon{font-size:32px;margin-bottom:8px}
/* Modal */
.modal-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:100;align-items:center;justify-content:center}
.modal-overlay.show{display:flex}
.modal{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);padding:28px;width:400px;max-width:90vw}
.modal h2{font-size:18px;font-weight:600;margin-bottom:20px}
.modal label{display:block;font-size:12px;color:var(--text2);margin-bottom:4px;margin-top:12px}
.modal input,.modal textarea{width:100%;padding:8px 10px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:13px;font-family:inherit}
.modal textarea{height:60px;resize:vertical}
.modal-actions{margin-top:20px;display:flex;gap:8px;justify-content:flex-end}
.icon-picker{display:flex;gap:8px;margin-top:6px;flex-wrap:wrap}
.icon-opt{font-size:24px;cursor:pointer;padding:4px 8px;border-radius:6px;border:2px solid transparent}
.icon-opt:hover,.icon-opt.selected{border-color:var(--text2);background:var(--bg3)}
</style>
</head>
<body>
<h1>Lab Platform</h1>
<p class="subtitle">Select a lab to open</p>
<div class="grid" id="grid"></div>
<div class="modal-overlay" id="create-modal">
  <div class="modal">
    <h2>Create New Lab</h2>
    <label>Name</label>
    <input id="new-name" placeholder="e.g. Forex Lab">
    <label>Description</label>
    <textarea id="new-desc" placeholder="What is this lab for?"></textarea>
    <label>Icon</label>
    <div class="icon-picker" id="icon-picker"></div>
    <div class="modal-actions">
      <button class="btn" onclick="closeCreateModal()">Cancel</button>
      <button class="btn primary" style="--accent:#4a8fe7" onclick="doCreate()">Create</button>
    </div>
  </div>
</div>

<script>
const ICONS = ['\u2697','\u2726','\u2734','\u26A1','\u2699','\u2615','\u2693','\u2702','\u2764','\u2B50','\uD83D\uDCC8','\uD83D\uDD2C','\uD83E\uDDEA','\uD83C\uDF0D','\uD83D\uDCDA','\uD83D\uDE80'];
const COLORS = ['#c8a55a','#4a8fe7','#3ac77e','#e7554a','#9a7be8','#2db8a0','#e88a3e','#e74a8f'];
let selectedIcon = ICONS[0];

function renderIconPicker() {
  document.getElementById('icon-picker').innerHTML = ICONS.map(i =>
    '<span class="icon-opt' + (i===selectedIcon?' selected':'') + '" onclick="pickIcon(this,\\'' + i + '\\')">' + i + '</span>'
  ).join('');
}

function pickIcon(el, icon) {
  selectedIcon = icon;
  document.querySelectorAll('.icon-opt').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
}

async function load() {
  const res = await fetch('/api/instances');
  const { data } = await res.json();
  const grid = document.getElementById('grid');
  let html = '';
  for (const lab of data) {
    const dot = lab.running ? '<span class="dot running"></span> Running on :' + lab.port : '<span class="dot stopped"></span> Stopped';
    html += '<div class="card" style="--accent:' + lab.color + '">'
      + '<div class="card-icon">' + lab.icon + '</div>'
      + '<div class="card-name">' + lab.name + '</div>'
      + '<div class="card-desc">' + lab.description + '</div>'
      + '<div class="card-meta"><span>Port ' + lab.port + '</span><span>Model: ' + lab.model + '</span></div>'
      + '<div class="card-status">' + dot + '</div>'
      + '<div class="card-actions">';
    if (lab.running) {
      html += '<button class="btn primary" onclick="openLab(\\'' + lab.id + '\\',' + lab.port + ')">Open Lab</button>';
      if (lab.hasFrontend) html += '<button class="btn" style="border-color:var(--accent);color:var(--accent)" onclick="openFrontend(\\'' + lab.id + '\\',' + lab.frontendPort + ')">View Site</button>';
      html += '<button class="btn danger" onclick="toggleLab(\\'' + lab.id + '\\',false)">Stop</button>';
    } else {
      html += '<button class="btn primary" onclick="toggleLab(\\'' + lab.id + '\\',true)">Start</button>';
    }
    html += '</div></div>';
  }
  html += '<div class="card new-card" onclick="showCreateModal()"><div class="new-icon">+</div><div>New Lab</div></div>';
  grid.innerHTML = html;
}

async function toggleLab(id, start) {
  if (start) {
    const btn = event.target; btn.disabled = true; btn.textContent = 'Starting...';
    const res = await fetch('/api/instances/' + id + '/start', { method: 'POST' });
    const { port } = await res.json();
    if (port) {
      // Wait for server to be ready
      for (let i = 0; i < 15; i++) {
        try { const r = await fetch('http://localhost:' + port + '/api/lab'); if (r.ok) break; } catch(e) {}
        await new Promise(r => setTimeout(r, 500));
      }
      window.open('http://localhost:' + port, '_blank');
    }
    load();
  } else {
    await fetch('/api/instances/' + id + '/stop', { method: 'POST' });
    load();
  }
}

function openLab(id, port) {
  window.open('http://localhost:' + port, '_blank');
}

function openFrontend(id, port) {
  window.open('http://localhost:' + port, '_blank');
}

function showCreateModal() {
  document.getElementById('new-name').value = '';
  document.getElementById('new-desc').value = '';
  selectedIcon = ICONS[0];
  renderIconPicker();
  document.getElementById('create-modal').classList.add('show');
  document.getElementById('new-name').focus();
}

function closeCreateModal() {
  document.getElementById('create-modal').classList.remove('show');
}

async function doCreate() {
  const name = document.getElementById('new-name').value.trim();
  if (!name) { document.getElementById('new-name').focus(); return; }
  const desc = document.getElementById('new-desc').value.trim();
  const colors = ['#c8a55a','#4a8fe7','#3ac77e','#e7554a','#9a7be8','#2db8a0','#e88a3e','#e74a8f'];
  const color = colors[Math.floor(Math.random() * colors.length)];
  const res = await fetch('/api/instances', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description: desc, icon: selectedIcon, color })
  });
  const result = await res.json();
  if (result.error) { alert(result.error); return; }
  closeCreateModal();
  load();
}

load();
setInterval(load, 5000);
</script>
</body>
</html>`;

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const p = url.pathname;
  const m = req.method;

  // Favicon
  if (p === '/favicon.ico') {
    res.writeHead(200, { 'Content-Type': 'image/svg+xml' });
    res.end(FAVICON);
    return;
  }

  if (p === '/' && m === 'GET') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(LAUNCHER_HTML);
    return;
  }

  if (p === '/api/instances' && m === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ data: getInstances() }));
    return;
  }

  if (p === '/api/instances' && m === 'POST') {
    const body = await parseBody(req);
    if (!body.name) { res.writeHead(400, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ error: 'Name required' })); return; }
    const result = createInstance(body.name, body.description, body.icon, body.color);
    res.writeHead(result.error ? 400 : 200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(result));
    return;
  }

  const startMatch = p.match(/^\/api\/instances\/([^/]+)\/start$/);
  if (startMatch && m === 'POST') {
    const result = startInstance(startMatch[1]);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(result || { error: 'Instance not found' }));
    return;
  }

  const stopMatch = p.match(/^\/api\/instances\/([^/]+)\/stop$/);
  if (stopMatch && m === 'POST') {
    stopInstance(stopMatch[1]);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true }));
    return;
  }

  res.writeHead(404);
  res.end('Not found');
});

server.listen(PORT, () => {
  console.log(`\n  \u2697  Lab Platform`);
  console.log(`  http://localhost:${PORT}`);
  console.log(`  Instances: ${getInstances().length}\n`);
});
