#!/usr/bin/env node
// Lab Platform — Core Server
// Zero npm dependencies — Node.js built-in modules only
// Reads lab.json from the instance directory to configure itself.

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { createInterface } = require('node:readline');
const { randomUUID } = require('node:crypto');
const { writeFile, unlink } = require('node:fs/promises');

// ---------------------------------------------------------------------------
// Config — loaded from instance's lab.json
// ---------------------------------------------------------------------------

const INSTANCE_DIR = process.env.LAB_INSTANCE || process.cwd();
const CORE_DIR = __dirname;
const PLATFORM_DIR = path.resolve(CORE_DIR, '..');

// Load lab.json
const LAB_CONFIG_PATH = path.join(INSTANCE_DIR, 'lab.json');
let LAB = { name: 'Lab', port: 3210, model: 'opus', role: '', plugins: [], color: '#c8a55a', icon: '⚗' };
try { LAB = { ...LAB, ...JSON.parse(fs.readFileSync(LAB_CONFIG_PATH, 'utf8')) }; }
catch (e) { console.log(`No lab.json found at ${LAB_CONFIG_PATH}, using defaults`); }

const PORT = parseInt(process.env.LAB_PORT || LAB.port || 3210);
const WORK_DIR = LAB.cwd ? path.resolve(INSTANCE_DIR, LAB.cwd) : INSTANCE_DIR;
const ROOT = INSTANCE_DIR;
const FILE_ROOT = WORK_DIR; // File browser root — defaults to instance dir, can be workspace root via lab.json cwd
const IS_GENESIS = process.env.LAB_IS_GENESIS === '1';
const SERVER_ROOT = process.env.SERVER_ROOT || path.resolve(INSTANCE_DIR, '..', '..');
const GENESIS_DIR = process.env.GENESIS_DIR || path.resolve(CORE_DIR, '..', '..'); // parent of template/core/

// Load server identity (server.json at server root)
let SERVER_CONFIG = {};
try { SERVER_CONFIG = JSON.parse(fs.readFileSync(path.join(SERVER_ROOT, 'server.json'), 'utf8')); } catch (e) {}
const GLOBAL_PLUGINS_DIR = process.env.GLOBAL_PLUGINS_DIR || path.join(GENESIS_DIR, 'template', 'plugins');
const GLOBAL_SKILLS_DIR = process.env.GLOBAL_SKILLS_DIR || path.join(GENESIS_DIR, 'template', 'skills');
const DATA_DIR = path.join(ROOT, LAB.dataDir || 'data');
const OUTPUT_DIR = path.join(ROOT, LAB.outputDir || 'output');
const SESSIONS_DIR = path.join(ROOT, LAB.kbDir || 'kb', 'sessions');
const SESSIONS_FILE = path.join(SESSIONS_DIR, 'sessions.json');
const MESSAGES_DIR = path.join(SESSIONS_DIR, 'messages');
const PROJECTS_DIR = path.join(ROOT, 'projects');
const CLAUDE_BIN = process.env.CLAUDE_BIN || (() => {
  const { execSync } = require('node:child_process');
  try { return execSync('which claude', { encoding: 'utf8' }).trim(); }
  catch { return 'claude'; } // fallback to PATH
})();

// --- Joint sessions (inter-agent communication) ---
const JOINT_DB_PY = path.join(CORE_DIR, 'joint_db.py');
const DRIVE_ROOT = path.resolve(SERVER_ROOT, '..');
const PLATFORM_ID = path.basename(path.resolve(ROOT, '..', '..'));
const INSTANCE_NAME = path.basename(ROOT);
const AGENT_ID = `${INSTANCE_NAME}.${SERVER_CONFIG.id || 'local'}.${PLATFORM_ID}.${PORT}`;
let AGENT_DISPLAY = LAB.name || INSTANCE_NAME;
try { const _id = fs.readFileSync(path.join(ROOT, 'agent', 'IDENTITY.md'), 'utf8'); const _nm = _id.match(/\*\*Name\*\*:\s*(.+)/); if (_nm) AGENT_DISPLAY = _nm[1].trim(); } catch {}

function jointCmd(command, args = []) {
  const { execSync } = require('node:child_process');
  const escaped = args.map(a => `'${String(a).replace(/'/g, "'\\''")}'`).join(' ');
  try {
    const result = execSync(`python3 "${JOINT_DB_PY}" ${command} ${escaped}`, {
      encoding: 'utf8', timeout: 10000,
      env: { ...process.env, DRIVE_ROOT }
    });
    return JSON.parse(result);
  } catch (e) {
    return { error: e.message };
  }
}

// Resolve plugin directories — expand "core/*", "analysis/*" etc.
// Looks in GLOBAL_PLUGINS_DIR first, then PLATFORM_DIR/plugins as fallback
function resolvePlugins() {
  const scripts = [];
  const pluginsDir = fs.existsSync(GLOBAL_PLUGINS_DIR) ? GLOBAL_PLUGINS_DIR : path.join(PLATFORM_DIR, 'plugins');
  for (const pattern of (LAB.plugins || [])) {
    if (pattern.endsWith('/*')) {
      const category = pattern.slice(0, -2);
      const dir = path.join(pluginsDir, category);
      try {
        for (const f of fs.readdirSync(dir)) {
          if (f.endsWith('.py') || f.endsWith('.sh')) scripts.push({ name: f, path: path.join(dir, f), category });
        }
      } catch (e) {}
    }
  }
  // Also include instance-local scripts
  const localScripts = path.join(ROOT, 'scripts');
  try {
    for (const f of fs.readdirSync(localScripts)) {
      if (f.endsWith('.py') || f.endsWith('.sh')) scripts.push({ name: f, path: path.join(localScripts, f), category: 'local' });
    }
  } catch (e) {}
  return scripts;
}

// Resolve a script path — check instance/scripts first, then global plugins, then platform plugins
function resolveScript(name) {
  const pluginsDir = fs.existsSync(GLOBAL_PLUGINS_DIR) ? GLOBAL_PLUGINS_DIR : path.join(PLATFORM_DIR, 'plugins');
  const locations = [
    path.join(ROOT, 'scripts', name),
    path.join(pluginsDir, 'core', name),
    path.join(pluginsDir, 'analysis', name),
  ];
  for (const p of locations) { if (fs.existsSync(p)) return p; }
  return null; // not found anywhere
}

console.log(`\n  ${LAB.icon || '⚗'}  ${LAB.name}`);
console.log(`  Instance: ${INSTANCE_DIR}`);
console.log(`  Port: ${PORT}\n`);

try { fs.mkdirSync(MESSAGES_DIR, { recursive: true }); } catch (e) { console.error('Failed to create sessions dir:', e.message); }
try { fs.mkdirSync(OUTPUT_DIR, { recursive: true }); } catch (e) {}
try { fs.mkdirSync(DATA_DIR, { recursive: true }); } catch (e) {}
try { fs.mkdirSync(PROJECTS_DIR, { recursive: true }); } catch (e) {}
try { fs.mkdirSync(path.join(ROOT, 'tasks'), { recursive: true }); } catch (e) {}
try { fs.mkdirSync(path.join(ROOT, 'plans'), { recursive: true }); } catch (e) {}

// ---------------------------------------------------------------------------
// Data helpers
// ---------------------------------------------------------------------------

function loadJSON(p) {
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch (e) { log(`loadJSON(${p}): ${e.message}`); return null; }
}

function parseCSVLine(line) {
  const r = []; let c = '', q = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') { if (q && line[i + 1] === '"') { c += '"'; i++; } else q = !q; }
    else if (ch === ',' && !q) { r.push(c.trim()); c = ''; }
    else c += ch;
  }
  r.push(c.trim());
  return r;
}

function loadCSV(filepath) {
  try {
    const lines = fs.readFileSync(filepath, 'utf8').trim().split('\n');
    if (lines.length < 2) return [];
    const headers = parseCSVLine(lines[0]);
    return lines.slice(1).map(l => {
      const vals = parseCSVLine(l);
      const obj = {};
      headers.forEach((h, i) => obj[h] = vals[i] || '');
      return obj;
    });
  } catch (e) { log(`loadCSV(${filepath}): ${e.message}`); return []; }
}

function getEvents() { return loadCSV(path.join(DATA_DIR, 'events.csv')); }
function getClocks() { return loadJSON(path.join(DATA_DIR, 'clocks.json')) || {}; }
function getSignatures() { return loadJSON(path.join(DATA_DIR, 'signatures.json')) || []; }
function getDatabase() { return loadCSV(path.join(OUTPUT_DIR, 'database.csv')); }

// ---------------------------------------------------------------------------
// File browser — rooted at FILE_ROOT (instance dir, or workspace root via lab.json cwd)
// ---------------------------------------------------------------------------

const SKIP_DIRS = new Set(['.git', 'node_modules', 'chat', '__pycache__', '.venv', ...(LAB.skipDirs || [])]);
const SKIP_EXT = new Set(['.psd', '.psb', '.tar.gz', '.zip', '.command', ...(LAB.skipExt || [])]);
const MAX_WALK_DEPTH = LAB.maxWalkDepth || 5;
const activeProcs = new Map(); // sessionId -> child process (for abort)

function walkDir(dir, depth) {
  if (depth === undefined) depth = 0;
  if (depth > MAX_WALK_DEPTH) return [];
  const results = [];
  try {
    const entries = fs.readdirSync(path.join(FILE_ROOT, dir), { withFileTypes: true });
    for (const e of entries) {
      if (e.name.startsWith('.') && e.name !== '.gitattributes') continue;
      const rel = dir ? `${dir}/${e.name}` : e.name;
      if (e.isDirectory()) {
        if (SKIP_DIRS.has(e.name)) continue;
        results.push({ name: e.name, path: rel, isDir: true });
        results.push(...walkDir(rel, depth + 1));
      } else {
        const ext = path.extname(e.name).toLowerCase();
        if (SKIP_EXT.has(ext)) continue;
        try {
          const stat = fs.statSync(path.join(FILE_ROOT, rel));
          results.push({ name: e.name, path: rel, size: stat.size });
        } catch (e) {}
      }
    }
  } catch (e) { log(`walkDir(${dir}): ${e.message}`); }
  return results;
}

function listBrowseableFiles() {
  return walkDir('', 0);
}

function getFileContent(filePath) {
  if (filePath.includes('..')) return null;
  const fullPath = path.join(FILE_ROOT, filePath);
  if (!fs.existsSync(fullPath)) return null;

  const ext = path.extname(filePath).toLowerCase();
  const name = path.basename(filePath);
  if (ext === '.csv') {
    const rows = loadCSV(fullPath);
    const headers = rows.length > 0 ? Object.keys(rows[0]) : [];
    return { type: 'csv', name, path: filePath, headers, rows };
  } else if (ext === '.xlsx') {
    try {
      const xlsxReader = path.join(__dirname, 'xlsx_reader.py');
      const result = require('node:child_process').execSync(`python3 "${xlsxReader}" "${fullPath}"`, { encoding: 'utf8', maxBuffer: 20 * 1024 * 1024, timeout: 15000 });
      const parsed = JSON.parse(result);
      return { type: 'xlsx', name, path: filePath, sheets: parsed.sheets };
    } catch (e) { log('xlsx parse error: ' + e.message); return null; }
  } else if (['.md', '.txt', '.py', '.sh', '.js', '.json', '.yml', '.yaml', '.cfg', '.ini', '.env', '.gitattributes', '.html', '.htm', '.css', '.xml', '.sql', '.ts', '.jsx', '.tsx', '.toml', ''].includes(ext) || name.startsWith('.')) {
    const type = ext === '.csv' ? 'csv' : ext === '.json' ? 'json' : ext === '.md' ? 'md' : 'text';
    return { type, name, path: filePath, content: fs.readFileSync(fullPath, 'utf8') };
  }
  return null;
}

function buildViewerContext(vc) {
  if (!vc) return '';
  // Database viewer context
  if (vc.database) {
    const ss = vc.database;
    const lines = ['[DATABASE VIEWER CONTEXT]'];
    if (ss.databases && ss.databases.length) {
      lines.push(`Databases: ${ss.databases.map(d => `${d.name} (${d.tableCount} tables${d.readonly ? ', read-only' : ''})`).join(', ')}`);
    }
    if (ss.activeDb) lines.push(`Active database: ${ss.activeDb}`);
    if (ss.tables && ss.tables.length) lines.push(`Tables in active db: ${ss.tables.join(', ')}`);
    if (ss.activeTable) lines.push(`Active table: ${ss.activeTable}`);
    if (ss.headers) lines.push(`Columns: ${ss.headers.join(', ')}`);
    if (ss.totalRows != null) lines.push(`Total rows: ${ss.totalRows}`);
    if (ss.selectedCell) {
      const c = ss.selectedCell;
      lines.push(`Selected cell: row ${c.row}, column "${c.col}" = "${c.value}"`);
    }
    lines.push(`Note: jubilee.db is rebuilt from pipeline CSVs via /rebuild. spreadsheet.db is user-managed.`);
    lines.push(`SQL queries: Use the Query panel or /query skill for ad-hoc SELECT queries.`);
    lines.push(`When the user asks about viewing data, suggest the Database tab over browsing CSV files.`);
    lines.push(`Output CSVs in output/ are pipeline artifacts rebuilt by /rebuild. The Database tab shows the same data with SQL query support.`);
    lines.push('[END DATABASE VIEWER CONTEXT]');
    return lines.join('\n');
  }
  // Task context (task selected from task pane)
  if (vc.task) {
    const t = vc.task;
    const statusLabel = t.status === 'completed' ? 'COMPLETED' : t.status === 'in_progress' ? 'IN PROGRESS' : 'PENDING';
    const lines = ['[SELECTED TASK CONTEXT]'];
    lines.push(`Task: ${t.content}`);
    lines.push(`Status: ${statusLabel}`);
    lines.push(`The user selected this task from the task pane. They want to discuss, work on, or get status for this specific task.`);
    lines.push('[END TASK CONTEXT]');
    return lines.join('\n');
  }
  // System browse context (file or folder selected from system file browser)
  if (vc.systemBrowse) {
    const sb = vc.systemBrowse;
    const lines = ['[SYSTEM BROWSE CONTEXT]'];
    lines.push(`Selected ${sb.isDir ? 'folder' : 'file'}: ${sb.path}`);
    if (sb.isDir && sb.children && sb.children.length) {
      lines.push(`Folder contents (${sb.children.length} items):`);
      for (const c of sb.children.slice(0, 30)) {
        lines.push(`  ${c.isDir ? '📁' : '📄'} ${c.name}${c.size != null ? ` (${c.size} bytes)` : ''}`);
      }
      if (sb.children.length > 30) lines.push(`  ... and ${sb.children.length - 30} more items`);
    }
    lines.push('[END SYSTEM BROWSE CONTEXT]');
    return lines.join('\n');
  }
  // Session reference context (session injected from sidebar right-click)
  if (vc.sessionRef) {
    const sr = vc.sessionRef;
    const lines = ['[SESSION REFERENCE CONTEXT]'];
    lines.push(`The user is referencing another session:`);
    lines.push(`  Session ID: ${sr.id}`);
    lines.push(`  Title: ${sr.title}`);
    lines.push(`  Model: ${sr.model || 'unknown'}`);
    if (sr.projectName) lines.push(`  Project: ${sr.projectName} (${sr.projectId})`);
    // Try to load recent messages from that session for context
    try {
      const refMsgs = getMessages(sr.id);
      if (refMsgs && refMsgs.length) {
        const recent = refMsgs.slice(-5);
        lines.push(`  Recent messages (last ${recent.length}):`);
        for (const m of recent) {
          const preview = typeof m.content === 'string' ? m.content.slice(0, 150) : '';
          lines.push(`    [${m.role}] ${preview}${preview.length >= 150 ? '...' : ''}`);
        }
      }
    } catch (e) { /* ignore */ }
    lines.push('The user may want to discuss, reference, or continue work from that session.');
    lines.push('[END SESSION REFERENCE CONTEXT]');
    return lines.join('\n');
  }
  // Folder context (folder selected in project file tree)
  if (vc.folder) {
    const lines = ['[VIEWER CONTEXT]'];
    lines.push(`Selected folder: ${vc.folder.path}`);
    if (vc.folder.children && vc.folder.children.length) {
      lines.push(`Folder contents (${vc.folder.children.length} items):`);
      for (const c of vc.folder.children.slice(0, 30)) {
        lines.push(`  ${c.isDir ? '📁' : '📄'} ${c.name}${c.size != null ? ` (${c.size} bytes)` : ''}`);
      }
      if (vc.folder.children.length > 30) lines.push(`  ... and ${vc.folder.children.length - 30} more items`);
    }
    lines.push('[END VIEWER CONTEXT]');
    return lines.join('\n');
  }
  // File viewer context
  if (!vc.file) return '';
  const lines = ['[VIEWER CONTEXT]'];
  lines.push(`Currently viewing: ${vc.file}`);
  if (vc.totalRows) lines.push(`File has ${vc.totalRows} rows, ${(vc.headers || []).length} columns`);
  if (vc.headers) lines.push(`Columns: ${vc.headers.join(', ')}`);
  if (vc.selectedRow) {
    const r = vc.selectedRow;
    const summary = Object.entries(r.data || {}).slice(0, 8).map(([k, v]) => `${k}=${v}`).join(', ');
    lines.push(`Selected row #${r.index}: ${summary}`);
  }
  if (vc.selectedCell) {
    const c = vc.selectedCell;
    lines.push(`Selected cell: row ${c.row}, column "${c.col}" = "${c.value}"`);
  }
  if (vc.selectedCol) {
    lines.push(`Selected column: "${vc.selectedCol.name}"`);
  }
  if (vc.sortBy) lines.push(`Sorted by: ${vc.sortBy} (${vc.sortDir || 'asc'})`);
  if (vc.file && vc.file.startsWith('output/') && vc.file.endsWith('.csv')) {
    lines.push(`Tip: This is a pipeline output CSV. The Database tab shows the same data with SQL query support, sorting, and export.`);
  }
  lines.push('[END VIEWER CONTEXT]');
  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Session persistence
// ---------------------------------------------------------------------------

function readSessions() {
  try { return JSON.parse(fs.readFileSync(SESSIONS_FILE, 'utf8')); } catch (e) { if (e.code !== 'ENOENT') log(`readSessions: ${e.message}`); return []; }
}
function writeSessions(s) { fs.writeFileSync(SESSIONS_FILE, JSON.stringify(s, null, 2)); }
function listSessions() { return readSessions(); }
function getSession(id) { return readSessions().find(s => s.id === id); }

function createSession(model = 'opus', projectId = null, opts = {}) {
  const sessions = readSessions();
  const now = new Date().toISOString();
  const session = {
    id: randomUUID(), claudeSessionId: null,
    title: opts.title || 'New Analysis', model,
    createdAt: now, lastMessageAt: now,
    messageCount: 0, totalCost: 0,
    agentName: AGENT_DISPLAY,
  };
  if (projectId) session.projectId = projectId;
  if (opts.isMain) session.isMain = true;
  sessions.push(session);
  writeSessions(sessions);
  log(`Session created: ${session.id} (${model}${session.isMain ? ', MAIN' : ''}${projectId ? ', project=' + projectId : ''})`);
  return session;
}

function getMainSession() {
  const sessions = readSessions();
  return sessions.find(s => s.isMain);
}

function getOrCreateMainSession() {
  let main = getMainSession();
  if (!main) {
    const agentName = loadAgentIdentity().name || AGENT_DISPLAY;
    main = createSession('opus', null, { isMain: true, title: `${agentName} — Main` });
    log(`Main session auto-created: ${main.id.slice(0,8)}`);
  }
  return main;
}

function updateSession(id, updates) {
  const sessions = readSessions();
  const idx = sessions.findIndex(s => s.id === id);
  if (idx === -1) return null;
  Object.assign(sessions[idx], updates);
  writeSessions(sessions);
  return sessions[idx];
}

function deleteSession(id) {
  const sessions = readSessions();
  const filtered = sessions.filter(s => s.id !== id);
  if (filtered.length === sessions.length) return false;
  writeSessions(filtered);
  try { fs.unlinkSync(path.join(MESSAGES_DIR, `${id}.json`)); } catch (e) { if (e.code !== 'ENOENT') log(`Delete messages file: ${e.message}`); }
  log(`Session deleted: ${id}`);
  return true;
}

// ---------------------------------------------------------------------------
// Projects persistence
// ---------------------------------------------------------------------------

const PROJECTS_FILE = path.join(PROJECTS_DIR, 'projects.json');

function readProjects() {
  try { return JSON.parse(fs.readFileSync(PROJECTS_FILE, 'utf8')); }
  catch (e) { if (e.code !== 'ENOENT') log(`readProjects: ${e.message}`); return []; }
}
function writeProjects(p) { fs.writeFileSync(PROJECTS_FILE, JSON.stringify(p, null, 2)); }

function getProject(projectId) {
  if (!projectId) return null;
  return readProjects().find(pr => pr.id === projectId) || null;
}

function getProjectName(projectId) {
  const p = getProject(projectId);
  return p ? p.name : '';
}

function createProject(name, description = '') {
  const projects = readProjects();
  const id = randomUUID();
  const projectDir = path.join(PROJECTS_DIR, id);
  const jobsDir = path.join(projectDir, 'jobs');
  fs.mkdirSync(jobsDir, { recursive: true });

  const project = {
    id,
    name: name || 'Untitled Project',
    description,
    createdAt: new Date().toISOString(),
  };

  // Write project.md
  const mdContent = `# ${project.name}\n\n${description || 'No description yet.'}\n\nCreated: ${project.createdAt}\n`;
  fs.writeFileSync(path.join(projectDir, 'project.md'), mdContent);

  // Create project SQLite database with default tables
  const dbPath = path.join(projectDir, 'project.db');
  try {
    const DATABASE_MANAGER_PY = path.join(__dirname, 'database_manager.py');
    require('node:child_process').execSync(
      `python3 "${DATABASE_MANAGER_PY}" "${dbPath}" create-db`,
      { encoding: 'utf8', timeout: 10000 }
    );
    // Create a default 'notes' table for project-level notes
    require('node:child_process').execSync(
      `python3 "${DATABASE_MANAGER_PY}" "${dbPath}" create notes title content status created_at`,
      { encoding: 'utf8', timeout: 10000 }
    );
    log(`Project database created: ${dbPath}`);
  } catch (e) {
    log(`Warning: Failed to create project database: ${e.message}`);
  }

  projects.push(project);
  writeProjects(projects);
  log(`Project created: ${project.name} (${id.slice(0,8)})`);
  return project;
}

function updateProject(projectId, updates) {
  const projects = readProjects();
  const idx = projects.findIndex(p => p.id === projectId);
  if (idx === -1) return null;
  Object.assign(projects[idx], updates);
  writeProjects(projects);
  return projects[idx];
}

function deleteProject(projectId) {
  const projects = readProjects();
  const filtered = projects.filter(p => p.id !== projectId);
  if (filtered.length === projects.length) return false;
  writeProjects(filtered);
  // Unlink sessions from this project
  const sessions = readSessions();
  for (const s of sessions) {
    if (s.projectId === projectId) delete s.projectId;
  }
  writeSessions(sessions);
  log(`Project deleted: ${projectId}`);
  return true;
}

// ---------------------------------------------------------------------------
// Jobs persistence — scoped to projects
// ---------------------------------------------------------------------------

function getJobsFile(projectId) {
  return path.join(PROJECTS_DIR, projectId, 'jobs.json');
}

function readJobs(projectId) {
  try { return JSON.parse(fs.readFileSync(getJobsFile(projectId), 'utf8')); }
  catch (e) { if (e.code !== 'ENOENT') log(`readJobs: ${e.message}`); return []; }
}
function writeJobs(projectId, jobs) {
  const dir = path.join(PROJECTS_DIR, projectId);
  fs.mkdirSync(path.join(dir, 'jobs'), { recursive: true });
  fs.writeFileSync(getJobsFile(projectId), JSON.stringify(jobs, null, 2));
}

function getJob(projectId, jobId) {
  return readJobs(projectId).find(j => j.id === jobId) || null;
}

function createJob(projectId, sessionId, title = 'New Job') {
  const jobs = readJobs(projectId);
  const id = randomUUID();
  const jobDir = path.join(PROJECTS_DIR, projectId, 'jobs');
  fs.mkdirSync(jobDir, { recursive: true });

  const job = {
    id,
    projectId,
    sessionId,
    title,
    status: 'active',     // active | completed | paused
    createdAt: new Date().toISOString(),
    completedAt: null,
    collaborators: [],     // [{ agentId, name, port, role, invitedAt }]
  };

  jobs.push(job);
  writeJobs(projectId, jobs);
  log(`Job created: ${title} (${id.slice(0,8)}) in project ${projectId.slice(0,8)}`);
  return job;
}

function updateJob(projectId, jobId, updates) {
  const jobs = readJobs(projectId);
  const idx = jobs.findIndex(j => j.id === jobId);
  if (idx === -1) return null;
  Object.assign(jobs[idx], updates);
  if (updates.status === 'completed' && !jobs[idx].completedAt) {
    jobs[idx].completedAt = new Date().toISOString();
  }
  writeJobs(projectId, jobs);
  return jobs[idx];
}

function getJobPlanPath(projectId, jobId) {
  return path.join(PROJECTS_DIR, projectId, 'jobs', `${jobId}-plan.md`);
}

function getJobTasksPath(projectId, jobId) {
  return path.join(PROJECTS_DIR, projectId, 'jobs', `${jobId}-tasks.json`);
}

function getJobPlan(projectId, jobId) {
  try { return fs.readFileSync(getJobPlanPath(projectId, jobId), 'utf8'); }
  catch (e) { return null; }
}

function getJobTasks(projectId, jobId) {
  try { return JSON.parse(fs.readFileSync(getJobTasksPath(projectId, jobId), 'utf8')); }
  catch (e) { return []; }
}

function getSessionJobs(projectId, sessionId) {
  return readJobs(projectId).filter(j => j.sessionId === sessionId);
}

function getActiveJob(projectId, sessionId) {
  return readJobs(projectId).find(j => j.sessionId === sessionId && j.status === 'active') || null;
}

// ---------------------------------------------------------------------------
// Settings — enforcements, preferences (persisted per instance)
// ---------------------------------------------------------------------------

const SETTINGS_FILE = path.join(ROOT, 'settings.json');

const DEFAULT_SETTINGS = {
  enforcements: {
    'auto-snapshot': true,
    'schema-validation': true,
    'circuit-breaker': true,
    'duplicate-detection': true,
    'audit-trail': true,
    'task-discipline': true,
    'plan-discipline': true,
    'deploy-guard': true,
    'job-discipline': true,
  },
  circuitBreakerMax: 5,
};

function loadSettings() {
  try {
    const saved = JSON.parse(fs.readFileSync(SETTINGS_FILE, 'utf8'));
    return {
      ...DEFAULT_SETTINGS,
      ...saved,
      enforcements: { ...DEFAULT_SETTINGS.enforcements, ...(saved.enforcements || {}) },
    };
  } catch { return { ...DEFAULT_SETTINGS }; }
}

function saveSettings(settings) {
  fs.writeFileSync(SETTINGS_FILE, JSON.stringify(settings, null, 2));
  return settings;
}

// ---------------------------------------------------------------------------
// Enforcement engine — runs before data operations
// ---------------------------------------------------------------------------

function enforcePreWrite(filePath, content) {
  const settings = loadSettings();
  const errors = [];

  // Auto-snapshot before data file modification
  if (settings.enforcements['auto-snapshot']) {
    if (filePath.startsWith('data/') && fs.existsSync(path.join(ROOT, filePath))) {
      const snapshotDir = path.join(ROOT, '.snapshots');
      try {
        fs.mkdirSync(snapshotDir, { recursive: true });
        const ts = new Date().toISOString().replace(/[:.]/g, '-');
        const dest = path.join(snapshotDir, `${path.basename(filePath)}.${ts}`);
        fs.copyFileSync(path.join(ROOT, filePath), dest);
        log(`Auto-snapshot: ${filePath} → .snapshots/${path.basename(dest)}`);
      } catch (e) { log(`Snapshot failed: ${e.message}`); }
    }
  }

  // Schema validation for events.csv
  if (settings.enforcements['schema-validation'] && filePath === 'data/events.csv' && content) {
    const lines = content.trim().split('\n');
    if (lines.length > 1) {
      const headers = lines[0].split(',').map(h => h.trim());
      const required = ['name', 'year_ad'];
      for (const r of required) {
        if (!headers.includes(r)) errors.push(`Missing required column: ${r}`);
      }
    }
  }

  // Duplicate detection
  if (settings.enforcements['duplicate-detection'] && filePath === 'data/events.csv' && content) {
    const lines = content.trim().split('\n');
    if (lines.length > 1) {
      const headers = lines[0].split(',');
      const nameIdx = headers.indexOf('name');
      if (nameIdx >= 0) {
        const names = new Set();
        for (let i = 1; i < lines.length; i++) {
          const cols = lines[i].split(',');
          const name = cols[nameIdx]?.trim();
          if (name && names.has(name)) errors.push(`Duplicate event: ${name} (row ${i + 1})`);
          names.add(name);
        }
      }
    }
  }

  return errors;
}

// Circuit breaker state
const circuitState = {}; // command -> { count, lastFail }

function checkCircuitBreaker(command) {
  const settings = loadSettings();
  if (!settings.enforcements['circuit-breaker']) return null;
  const key = command.split(/\s+/).slice(0, 2).join(' ');
  const state = circuitState[key] || { count: 0, lastFail: 0 };
  if (state.count >= (settings.circuitBreakerMax || 5)) {
    if (Date.now() - state.lastFail < 120000) {
      return `Circuit breaker: "${key}" failed ${state.count} times. Wait 2 minutes or investigate the error.`;
    }
    state.count = 0; // Reset after cooldown
  }
  return null;
}

function recordCircuitFailure(command) {
  const key = command.split(/\s+/).slice(0, 2).join(' ');
  if (!circuitState[key]) circuitState[key] = { count: 0, lastFail: 0 };
  circuitState[key].count++;
  circuitState[key].lastFail = Date.now();
}

function recordCircuitSuccess(command) {
  const key = command.split(/\s+/).slice(0, 2).join(' ');
  if (circuitState[key]) circuitState[key].count = 0;
}

// Audit trail
function auditLog(action, details) {
  const settings = loadSettings();
  if (!settings.enforcements['audit-trail']) return;
  const auditDir = path.join(ROOT, '.audit');
  try {
    fs.mkdirSync(auditDir, { recursive: true });
    const entry = JSON.stringify({ timestamp: new Date().toISOString(), action, ...details }) + '\n';
    fs.appendFileSync(path.join(auditDir, 'operations.jsonl'), entry);
  } catch (e) {}
}

// ---------------------------------------------------------------------------
// Skills — slash commands for the lab chat
// ---------------------------------------------------------------------------

function getSkills() {
  const pluginsDir = fs.existsSync(GLOBAL_PLUGINS_DIR) ? GLOBAL_PLUGINS_DIR : path.join(PLATFORM_DIR, 'plugins');
  const pipelinePath = path.join(pluginsDir, 'core', 'pipeline.py');
  const buildDbPath = path.join(pluginsDir, 'core', 'build_db.py');
  const snapshotPath = path.join(pluginsDir, 'core', 'data-snapshot.sh');

  const builtins = [
    {
      command: 'rebuild',
      name: 'Rebuild All',
      category: 'core',
      description: 'Run the full pipeline — engine + all analysis scripts + rebuild SQLite database',
      usage: '/rebuild [--force]',
      run: (args) => ['python3', pipelinePath, ...(args.includes('--force') ? ['--force'] : [])],
    },
    {
      command: 'status',
      name: 'Pipeline Status',
      category: 'core',
      description: 'Show which pipeline steps are current vs stale',
      usage: '/status',
      run: () => ['python3', pipelinePath, '--status'],
    },
    {
      command: 'build-db',
      name: 'Build Database',
      category: 'core',
      description: 'Rebuild SQLite database from all CSV files and KB markdown',
      usage: '/build-db',
      run: () => ['python3', buildDbPath],
    },
    {
      command: 'db-stats',
      name: 'Database Stats',
      category: 'core',
      description: 'Show all tables with row counts and column counts',
      usage: '/db-stats',
      run: () => ['python3', buildDbPath, '--stats'],
    },
    {
      command: 'query',
      name: 'SQL Query',
      category: 'core',
      description: 'Run a read-only SQL query against the database',
      usage: '/query SELECT name, year_ad FROM events WHERE signature = "CROSS"',
      run: (args) => ['python3', buildDbPath, '--query', args],
    },
    {
      command: 'snapshot',
      name: 'Data Snapshot',
      category: 'core',
      description: 'Git snapshot of data and output directories',
      usage: '/snapshot "description of changes"',
      run: (args) => ['bash', snapshotPath, args || 'manual snapshot'],
    },
    {
      command: 'analyze',
      name: 'Run Analysis',
      category: 'core',
      description: 'Run a specific analysis script by name (e.g., convergence, remainder_scan)',
      usage: '/analyze convergence [--target 0.42]',
      run: (args) => {
        const parts = args.trim().split(/\s+/);
        const scriptName = parts[0];
        const scriptArgs = parts.slice(1);
        const scriptPath = path.join(pluginsDir, 'analysis', scriptName + '.py');
        return ['python3', scriptPath, ...scriptArgs];
      },
    },
    {
      command: 'log',
      name: 'Research Log',
      category: 'core',
      description: 'Add an entry to the research activity log (type: discovery/import/analysis/milestone/note)',
      usage: '/log discovery "Title" "Description"',
      run: (args) => {
        // Parse: /log type "title" "description"
        const m = args.match(/^(\w+)\s+"([^"]+)"\s+"([^"]+)"/) || args.match(/^(\w+)\s+(.+)/);
        if (!m) return ['echo', 'Usage: /log type "title" "description"'];
        const type = m[1];
        const title = m[2];
        const desc = m[3] || '';
        const logPath = path.join(ROOT, 'kb', 'research-log.json');
        let entries = [];
        try { entries = JSON.parse(fs.readFileSync(logPath, 'utf8')); } catch {}
        entries.push({ id: entries.length + 1, date: new Date().toISOString(), type, title, description: desc, details: '' });
        fs.writeFileSync(logPath, JSON.stringify(entries, null, 2));
        return ['echo', `Logged: [${type}] ${title}`];
      },
    },
    {
      command: 'uploads',
      name: 'List Uploads',
      category: 'core',
      description: 'Show files in data/uploads/ ready for processing',
      usage: '/uploads',
      run: () => ['ls', '-la', path.join(ROOT, 'data', 'uploads')],
    },
    {
      command: 'help',
      name: 'Help',
      category: 'core',
      description: 'Show all available skills',
      usage: '/help',
      run: () => ['echo', getSkills().map(s => `/${s.command} — ${s.description}`).join('\n')],
    },
    // --- Joint session skills ---
    {
      command: 'joint-create',
      name: 'Create Channel',
      category: 'joint',
      description: 'Create a joint session channel for multi-agent collaboration',
      usage: '/joint-create #channel-name "Topic description"',
      run: (args) => {
        const m = args.match(/^#?(\S+)\s*(?:"([^"]*)")?/);
        if (!m) return ['echo', 'Usage: /joint-create #name "topic"'];
        const result = jointCmd('create-channel', [m[1], m[2] || '', AGENT_ID]);
        if (result.error) return ['echo', `Error: ${result.error}`];
        jointCmd('join', [result.name, AGENT_ID, AGENT_DISPLAY, SERVER_CONFIG.id || 'local', INSTANCE_NAME, String(PORT), LAB.icon || '', LAB.color || '', 'agent']);
        return ['echo', `Created #${result.name} — ${result.id}`];
      },
    },
    {
      command: 'joint-join',
      name: 'Join Channel',
      category: 'joint',
      description: 'Join a joint session channel',
      usage: '/joint-join #channel-name',
      run: (args) => {
        const name = args.trim().replace(/^#/, '');
        if (!name) return ['echo', 'Usage: /joint-join #name'];
        const result = jointCmd('join', [name, AGENT_ID, AGENT_DISPLAY, SERVER_CONFIG.id || 'local', INSTANCE_NAME, String(PORT), LAB.icon || '', LAB.color || '', 'agent']);
        if (result.error) return ['echo', `Error: ${result.error}`];
        return ['echo', `Joined #${result.channel}`];
      },
    },
    {
      command: 'joint-leave',
      name: 'Leave Channel',
      category: 'joint',
      description: 'Leave a joint session channel',
      usage: '/joint-leave #channel-name',
      run: (args) => {
        const name = args.trim().replace(/^#/, '');
        if (!name) return ['echo', 'Usage: /joint-leave #name'];
        const result = jointCmd('leave', [name, AGENT_ID]);
        return ['echo', result.error ? `Error: ${result.error}` : `Left #${result.channel}`];
      },
    },
    {
      command: 'joint-post',
      name: 'Post to Channel',
      category: 'joint',
      description: 'Post a message to a joint session channel',
      usage: '/joint-post #channel-name Your message here',
      run: (args) => {
        const m = args.match(/^#?(\S+)\s+(.+)/s);
        if (!m) return ['echo', 'Usage: /joint-post #name message'];
        const result = jointCmd('post', [m[1], AGENT_ID, AGENT_DISPLAY, 'agent', m[2]]);
        return ['echo', result.error ? `Error: ${result.error}` : `Posted to #${m[1]} (seq ${result.seq})`];
      },
    },
    {
      command: 'joint-read',
      name: 'Read Channel',
      category: 'joint',
      description: 'Read recent messages from a joint session channel',
      usage: '/joint-read #channel-name [count]',
      run: (args) => {
        const m = args.match(/^#?(\S+)\s*(\d+)?/);
        if (!m) return ['echo', 'Usage: /joint-read #name [count]'];
        const limit = m[2] || '20';
        const msgs = jointCmd('messages', [m[1], '0', limit]);
        if (msgs.error) return ['echo', `Error: ${msgs.error}`];
        if (!Array.isArray(msgs) || msgs.length === 0) return ['echo', `#${m[1]}: No messages yet.`];
        const lines = msgs.map(msg => {
          const time = msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : '';
          return `[${time}] ${msg.display_name}: ${msg.content}`;
        });
        return ['echo', `#${m[1]} — ${msgs.length} messages:\n${lines.join('\n')}`];
      },
    },
    {
      command: 'joint-channels',
      name: 'List Channels',
      category: 'joint',
      description: 'List all joint session channels',
      usage: '/joint-channels',
      run: () => {
        const channels = jointCmd('list-channels');
        if (!Array.isArray(channels) || channels.length === 0) return ['echo', 'No channels. Create one with /joint-create #name'];
        const lines = channels.map(ch => `#${ch.name} — ${ch.member_count} members, ${ch.last_seq || 0} msgs — "${ch.topic}"`);
        return ['echo', `Channels:\n${lines.join('\n')}`];
      },
    },
    {
      command: 'joint-members',
      name: 'Channel Members',
      category: 'joint',
      description: 'List members of a joint session channel',
      usage: '/joint-members #channel-name',
      run: (args) => {
        const name = args.trim().replace(/^#/, '');
        if (!name) return ['echo', 'Usage: /joint-members #name'];
        const members = jointCmd('members', [name]);
        if (members.error) return ['echo', `Error: ${members.error}`];
        if (!Array.isArray(members) || members.length === 0) return ['echo', `#${name}: No members.`];
        const lines = members.map(m => `${m.icon || '•'} ${m.display_name} (${m.server_id}/${m.instance}) — ${m.role}`);
        return ['echo', `#${name} members:\n${lines.join('\n')}`];
      },
    },
    {
      command: 'joint-ask',
      name: 'Ask Agent in Channel',
      category: 'joint',
      description: 'Ask a remote agent to respond in a joint session channel',
      usage: '/joint-ask #channel-name agent-port "Your question"',
      run: (args) => {
        const m = args.match(/^#?(\S+)\s+(\d+)\s+(.+)/s);
        if (!m) return ['echo', 'Usage: /joint-ask #channel port "question"'];
        const [, channelName, port, question] = m;
        // Post the question to the channel first
        jointCmd('post', [channelName, AGENT_ID, AGENT_DISPLAY, 'agent', question]);
        // Invoke the remote agent
        const http = require('node:http');
        const postData = JSON.stringify({ prompt: question });
        const req = http.request({ hostname: 'localhost', port: parseInt(port), path: `/api/joint/channels/${encodeURIComponent(channelName)}/invoke`, method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(postData) } }, (resp) => { /* fire and forget */ });
        req.on('error', () => {});
        req.write(postData);
        req.end();
        return ['echo', `Invoked agent on port ${port} in #${channelName}`];
      },
    },
    // --- Agent memory skills ---
    {
      command: 'remember',
      name: 'Remember',
      category: 'agent',
      description: 'Save a memory for cross-session recall',
      usage: '/remember <topic> <content> [--type context|feedback|project]',
      run: (args) => {
        if (!args.trim()) return ['echo', 'Usage: /remember <topic> <content> [--type context|feedback|project]'];
        const memScript = path.join(pluginsDir, 'core', 'agent_memory.py');
        // Split into topic (first word or quoted string) and content (rest)
        const m = args.match(/^"([^"]+)"\s+(.+)/s) || args.match(/^(\S+)\s+(.+)/s);
        if (!m) return ['echo', 'Usage: /remember <topic> <content>'];
        return ['python3', memScript, 'remember', m[1], m[2]];
      },
    },
    {
      command: 'recall',
      name: 'Recall',
      category: 'agent',
      description: 'List or search agent memories',
      usage: '/recall [topic]',
      run: (args) => {
        const memScript = path.join(pluginsDir, 'core', 'agent_memory.py');
        return args.trim() ? ['python3', memScript, 'recall', args.trim()] : ['python3', memScript, 'recall'];
      },
    },
    {
      command: 'forget',
      name: 'Forget',
      category: 'agent',
      description: 'Remove a memory by topic',
      usage: '/forget <topic>',
      run: (args) => {
        if (!args.trim()) return ['echo', 'Usage: /forget <topic>'];
        const memScript = path.join(pluginsDir, 'core', 'agent_memory.py');
        return ['python3', memScript, 'forget', args.trim()];
      },
    },
    {
      command: 'identity',
      name: 'Agent Identity',
      category: 'agent',
      description: 'Show agent identity, memory count, and channel memberships',
      usage: '/identity',
      run: () => {
        const memScript = path.join(pluginsDir, 'core', 'agent_memory.py');
        return ['python3', memScript, 'identity'];
      },
    },
  ];

  // --- Catalog-based skills ---
  // Load from GLOBAL_SKILLS_DIR/catalog.json, filtered by lab.json "skills" config
  let catalogSkills = [];
  const catalogPath = path.join(GLOBAL_SKILLS_DIR, 'catalog.json');
  try {
    const catalog = JSON.parse(fs.readFileSync(catalogPath, 'utf8'));
    const enabledPatterns = LAB.skills || [];
    // Check if a skill matches the instance's enabled patterns
    const isEnabled = (skill) => {
      if (enabledPatterns.length === 0) return true; // no skills config = all catalog skills enabled by default
      for (const pattern of enabledPatterns) {
        if (pattern === '*') return true;
        if (pattern.endsWith('/*')) {
          const cat = pattern.slice(0, -2);
          if (skill.category === cat) return true;
        } else if (pattern === skill.command) return true;
      }
      return false;
    };
    // Build run() functions for catalog script skills (non-builtIn)
    catalogSkills = catalog.skills
      .filter(s => !s.builtIn && isEnabled(s))
      .filter(s => {
        // Gate: skip catalog skills whose script can't be resolved (e.g., draft_manager.py only in some instances)
        if (s.script && !resolveScript(s.script)) return false;
        return true;
      })
      .map(s => ({
        command: s.command,
        name: s.name,
        category: s.category,
        description: s.description,
        usage: s.usage,
        run: (userArgs) => {
          const scriptPath = resolveScript(s.script);
          const ext = path.extname(s.script).toLowerCase();
          const cmd = ext === '.sh' ? 'bash' : 'python3';
          return [cmd, scriptPath, ...(s.args || []), userArgs].filter(Boolean);
        },
      }));
  } catch (e) { /* no catalog or parse error — fall back to lab.json skills */ }

  // --- Legacy: instance-specific skills from lab.json (backward compat) ---
  const instanceSkills = (LAB.skills || [])
    .filter(s => typeof s === 'object' && s.command) // only skill objects, not glob strings
    .map(s => ({
      command: s.command,
      name: s.name,
      description: s.description,
      usage: s.usage,
      run: (userArgs) => {
        const scriptPath = resolveScript(s.script);
        return ['python3', scriptPath, ...(s.args || []), userArgs].filter(Boolean);
      },
    }));

  // Auto-generate skills from analysis scripts
  const scriptSkills = generateScriptSkills();

  // Merge: builtins + scripts + catalog + instance (dedupe by command, later wins)
  const seen = new Map();
  for (const s of [...builtins, ...scriptSkills, ...catalogSkills, ...instanceSkills]) seen.set(s.command, s);
  const allSkills = [...seen.values()];

  // Filter based on settings.json skills config (false = disabled)
  const settings = loadSettings();
  const skillConfig = settings.skills || {};
  return allSkills.filter(s => skillConfig[s.command] !== false);
}

// ---------------------------------------------------------------------------
// Scripts manifest
// ---------------------------------------------------------------------------

function loadScriptsManifest() {
  // Try loading manifest.json from instance scripts dir first
  const manifestPath = path.join(ROOT, 'scripts', 'manifest.json');
  if (fs.existsSync(manifestPath)) {
    try { return JSON.parse(fs.readFileSync(manifestPath, 'utf8')); }
    catch (e) { log(`loadScriptsManifest: ${e.message}`); }
  }
  // Try from global or platform plugins/analysis
  const pluginsDir = fs.existsSync(GLOBAL_PLUGINS_DIR) ? GLOBAL_PLUGINS_DIR : path.join(PLATFORM_DIR, 'plugins');
  const pluginManifest = path.join(pluginsDir, 'analysis', 'manifest.json');
  if (fs.existsSync(pluginManifest)) {
    try { return JSON.parse(fs.readFileSync(pluginManifest, 'utf8')); }
    catch (e) { log(`loadScriptsManifest(plugins): ${e.message}`); }
  }
  // Fallback: scan scripts directory and extract docstrings
  const scripts = [];
  const scriptsDir = path.join(ROOT, 'scripts');
  try {
    for (const f of fs.readdirSync(scriptsDir)) {
      if (!f.endsWith('.py') || f === '__init__.py') continue;
      const content = fs.readFileSync(path.join(scriptsDir, f), 'utf8');
      const docMatch = content.match(/^"""([\s\S]*?)"""/m) || content.match(/^'''([\s\S]*?)'''/m);
      const firstLine = docMatch ? docMatch[1].trim().split('\n')[0] : f.replace('.py', '');
      scripts.push({
        name: f.replace('.py', '').replace(/_/g, ' '),
        file: `scripts/${f}`,
        description: firstLine,
        input: 'output/database.csv',
        output: 'stdout',
      });
    }
  } catch (e) { log(`loadScriptsManifest scan: ${e.message}`); }
  return scripts;
}

// ---------------------------------------------------------------------------
// Generate skills from analysis scripts (auto-register each script as a skill)
// ---------------------------------------------------------------------------

function generateScriptSkills() {
  const manifest = loadScriptsManifest();
  const pluginsDir = fs.existsSync(GLOBAL_PLUGINS_DIR) ? GLOBAL_PLUGINS_DIR : path.join(PLATFORM_DIR, 'plugins');
  return manifest.map(s => {
    const fileName = path.basename(s.file, '.py');
    const command = fileName.replace(/_/g, '-');
    return {
      command,
      name: s.name,
      category: 'analysis',
      description: s.description,
      usage: `/${command} [args]`,
      input: s.input || '',
      output: s.output || '',
      chains_with: s.chains_with || [],
      isScript: true,
      run: (args) => {
        const scriptPath = path.join(pluginsDir, 'analysis', fileName + '.py');
        if (!fs.existsSync(scriptPath)) {
          // Fall back to instance scripts dir
          const localPath = path.join(ROOT, 'scripts', fileName + '.py');
          return ['python3', localPath, ...(args ? args.trim().split(/\s+/) : [])];
        }
        return ['python3', scriptPath, ...(args ? args.trim().split(/\s+/) : [])];
      },
    };
  });
}

// ---------------------------------------------------------------------------
// Metadata generation (heuristic — no API call needed)
// ---------------------------------------------------------------------------

function generateMetadata(session, messages) {
  const userMsgs = messages.filter(m => m.role === 'user').map(m => m.content);
  const assistMsgs = messages.filter(m => m.role === 'assistant').map(m => m.content);
  const allText = [...userMsgs, ...assistMsgs].join(' ');

  // Title: session title or first user message
  const title = (session.title && session.title !== 'New Analysis')
    ? session.title
    : (userMsgs[0] || 'Untitled').slice(0, 50);

  // Tags: extract from signature names, keywords, and patterns
  const sigs = getSignatures();
  const tagSet = new Set();
  const upper = allText.toUpperCase();
  for (const sig of sigs) {
    if (upper.includes(sig.name.toUpperCase())) tagSet.add(sig.name.toLowerCase());
  }
  // Common topic keywords
  const keywords = ['jubilee', 'sabbatical', 'remainder', 'convergence', 'feast', 'millennium', 'prophecy', 'daniel', 'exodus', 'creation', 'cross', 'resurrection', 'judgment', 'covenant', 'restoration', 'exile', 'gematria', 'islamic'];
  for (const kw of keywords) {
    if (upper.includes(kw.toUpperCase())) tagSet.add(kw);
  }
  // Year mentions
  const years = allText.match(/\b(20[2-4]\d)\b/g);
  if (years) for (const y of [...new Set(years)]) tagSet.add(y);

  // Summary: first assistant response, truncated
  const summary = assistMsgs[0]
    ? assistMsgs[0].replace(/\n/g, ' ').slice(0, 200).trim() + (assistMsgs[0].length > 200 ? '...' : '')
    : '';

  // Topics: unique user question themes
  const topics = userMsgs.slice(0, 5).map(m => {
    const words = m.split(/\s+/).slice(0, 6).join(' ');
    return words.length > 40 ? words.slice(0, 37) + '...' : words;
  }).join(', ');

  return {
    title,
    tags: [...tagSet].slice(0, 10).join(', '),
    summary,
    topics,
  };
}

// ---------------------------------------------------------------------------
// Message persistence
// ---------------------------------------------------------------------------

function getMessages(sessionId) {
  try { return JSON.parse(fs.readFileSync(path.join(MESSAGES_DIR, `${sessionId}.json`), 'utf8')); }
  catch { return []; }
}

function appendMessage(sessionId, msg) {
  const msgs = getMessages(sessionId);
  msgs.push(msg);
  fs.writeFileSync(path.join(MESSAGES_DIR, `${sessionId}.json`), JSON.stringify(msgs));
  // Broadcast to live session listeners
  sessionBroadcast(sessionId, { type: 'message', message: msg });
}

// ---------------------------------------------------------------------------
// Agent Inbox — cross-session message queue (file-based)
// ---------------------------------------------------------------------------
const INBOX_FILE = path.join(ROOT, 'agent', 'inbox.json');

function readInbox() {
  try { return JSON.parse(fs.readFileSync(INBOX_FILE, 'utf8')); }
  catch { return []; }
}

function writeInbox(messages) {
  try { fs.mkdirSync(path.dirname(INBOX_FILE), { recursive: true }); } catch {}
  fs.writeFileSync(INBOX_FILE, JSON.stringify(messages, null, 2));
}

function addToInbox(entry) {
  const inbox = readInbox();
  entry.id = randomUUID();
  entry.receivedAt = new Date().toISOString();
  entry.delivered = false;
  inbox.push(entry);
  writeInbox(inbox);
  return entry;
}

function getUndeliveredInbox() {
  return readInbox().filter(m => !m.delivered);
}

function markInboxDelivered(ids) {
  const inbox = readInbox();
  let changed = false;
  for (const msg of inbox) {
    if (ids.includes(msg.id)) { msg.delivered = true; msg.deliveredAt = new Date().toISOString(); changed = true; }
  }
  if (changed) writeInbox(inbox);
  return changed;
}

function clearInbox(onlyDelivered = false) {
  if (onlyDelivered) {
    const inbox = readInbox().filter(m => !m.delivered);
    writeInbox(inbox);
  } else {
    writeInbox([]);
  }
}

// ---------------------------------------------------------------------------
// Live session SSE — allows external clients to monitor sessions in real-time
// ---------------------------------------------------------------------------
const sessionListeners = new Map(); // sessionId → Set<res>

function sessionBroadcast(sessionId, data) {
  const listeners = sessionListeners.get(sessionId);
  if (!listeners || !listeners.size) return;
  const payload = `data: ${JSON.stringify(data)}\n\n`;
  for (const res of listeners) {
    try { res.write(payload); } catch (e) { listeners.delete(res); }
  }
}

function addSessionListener(sessionId, res) {
  if (!sessionListeners.has(sessionId)) sessionListeners.set(sessionId, new Set());
  sessionListeners.get(sessionId).add(res);
}

function removeSessionListener(sessionId, res) {
  const listeners = sessionListeners.get(sessionId);
  if (listeners) { listeners.delete(res); if (!listeners.size) sessionListeners.delete(sessionId); }
}

// ---------------------------------------------------------------------------
// Agent identity loading
// ---------------------------------------------------------------------------

let _agentIdentityCache = null;
let _agentMemoryCache = null;
let _agentCacheTime = 0;
const AGENT_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

function loadAgentIdentity() {
  const now = Date.now();
  if (_agentIdentityCache && (now - _agentCacheTime) < AGENT_CACHE_TTL) {
    return _agentIdentityCache;
  }

  const agentDir = path.join(ROOT, 'agent');
  const result = { name: null, role: null, icon: null, color: null, agentId: null, soul: '', rules: '' };

  // Load IDENTITY.md
  try {
    const content = fs.readFileSync(path.join(agentDir, 'IDENTITY.md'), 'utf8');
    const nameMatch = content.match(/\*\*Name\*\*:\s*(.+)/);
    const roleMatch = content.match(/\*\*Role\*\*:\s*(.+)/);
    const iconMatch = content.match(/\*\*Icon\*\*:\s*(.+)/);
    const colorMatch = content.match(/\*\*Color\*\*:\s*(.+)/);
    const idMatch = content.match(/Agent ID\s*\|\s*([^|]+)/);
    if (nameMatch) result.name = nameMatch[1].trim();
    if (roleMatch) result.role = roleMatch[1].trim();
    if (iconMatch) result.icon = iconMatch[1].trim();
    if (colorMatch) result.color = colorMatch[1].trim();
    if (idMatch) result.agentId = idMatch[1].trim();
  } catch (e) { /* no IDENTITY.md — graceful fallback */ }

  // Load SOUL.md
  try {
    result.soul = fs.readFileSync(path.join(agentDir, 'SOUL.md'), 'utf8');
  } catch (e) { /* no SOUL.md */ }

  // Load RULES.md
  try {
    result.rules = fs.readFileSync(path.join(agentDir, 'RULES.md'), 'utf8');
  } catch (e) { /* no RULES.md */ }

  _agentIdentityCache = result;
  _agentCacheTime = now;
  return result;
}

function loadAgentMemory() {
  const now = Date.now();
  if (_agentMemoryCache && (now - _agentCacheTime) < AGENT_CACHE_TTL) {
    return _agentMemoryCache;
  }

  const agentDir = path.join(ROOT, 'agent');
  let result = { count: 0, formatted: '', recentSessions: '' };

  try {
    const index = fs.readFileSync(path.join(agentDir, 'MEMORY.md'), 'utf8');
    const linkPattern = /\[([^\]]+)\]\(([^)]+\.md)\)/g;
    const memories = [];
    const sessions = [];
    let totalLength = 0;
    const MAX_MEMORY_CHARS = 6000; // ~2000 tokens
    let match;

    while ((match = linkPattern.exec(index)) !== null) {
      const [, name, relPath] = match;
      try {
        let raw = fs.readFileSync(path.join(agentDir, relPath), 'utf8');
        // Check if session type (from frontmatter or filename)
        const isSession = relPath.includes('session_') || /type:\s*session/.test(raw);
        let content = raw.replace(/^---[\s\S]*?---\s*/, '').trim();
        if (totalLength + content.length > MAX_MEMORY_CHARS) break;
        if (isSession) {
          sessions.push({ name, content });
        } else {
          memories.push({ name, content });
        }
        totalLength += content.length;
      } catch (e) { /* skip unreadable memory file */ }
    }

    if (memories.length > 0) {
      const parts = memories.map(m => `### ${m.name}\n${m.content}`);
      result.formatted = parts.join('\n\n');
      result.count = memories.length;
    }
    // Return last 3 session summaries for "Recent Sessions" section
    if (sessions.length > 0) {
      const recent = sessions.slice(-3);
      result.recentSessions = recent.map(s => `- **${s.name}**: ${s.content.split('\n').filter(l => l.startsWith('- ')).slice(0, 3).join('; ').slice(0, 200) || s.content.slice(0, 200)}`).join('\n');
      result.count += sessions.length;
    }
  } catch (e) { /* no MEMORY.md — graceful fallback */ }

  _agentMemoryCache = result;
  _agentCacheTime = now;
  return result;
}

// ---------------------------------------------------------------------------
// Cross-context awareness — recent channel activity for sidebar sessions
// ---------------------------------------------------------------------------

let _channelActivityCache = null;
let _channelActivityCacheTime = 0;
const CHANNEL_ACTIVITY_CACHE_TTL = 30000; // 30 seconds

function loadRecentChannelActivity() {
  const now = Date.now();
  if (_channelActivityCache && (now - _channelActivityCacheTime) < CHANNEL_ACTIVITY_CACHE_TTL) {
    return _channelActivityCache;
  }

  let result = '';
  try {
    const channels = jointCmd('list-channels');
    if (!Array.isArray(channels) || channels.length === 0) return '';

    const lines = [];
    let totalChars = 0;
    const MAX_CHARS = 1500;

    for (const ch of channels) {
      // Check if this agent is a member
      const members = jointCmd('members', [ch.name]);
      if (!Array.isArray(members) || !members.some(m => m.agent_id === AGENT_ID)) continue;

      // Load last 5 messages (use since_seq to get the tail, not the head)
      const sinceSeq = Math.max(0, (ch.last_seq || 0) - 5);
      const msgs = jointCmd('messages', [ch.name, String(sinceSeq), '5']);
      if (!Array.isArray(msgs) || msgs.length === 0) continue;

      const channelLines = [`#${ch.name}:`];
      for (const msg of msgs.slice(-5)) {
        const line = `  [${msg.display_name}] ${(msg.content || '').slice(0, 200)}`;
        channelLines.push(line);
      }
      const block = channelLines.join('\n');
      if (totalChars + block.length > MAX_CHARS) break;
      lines.push(block);
      totalChars += block.length;
    }

    result = lines.join('\n\n');
  } catch (e) { /* joint sessions unavailable */ }

  _channelActivityCache = result;
  _channelActivityCacheTime = now;
  return result;
}

// ---------------------------------------------------------------------------
// Session continuity — auto-save session summaries to agent memory
// ---------------------------------------------------------------------------

function saveSessionSummary(sessionId) {
  try {
    const agentDir = path.join(ROOT, 'agent');
    if (!fs.existsSync(agentDir)) return; // no agent identity = no session saving
    const memoryDir = path.join(agentDir, 'memory');
    fs.mkdirSync(memoryDir, { recursive: true });

    const session = getSession(sessionId);
    if (!session) return;

    const messages = getMessages(sessionId);
    const userMsgs = messages
      .filter(m => m.role === 'user')
      .slice(-5)
      .map(m => (m.content || '').slice(0, 150));
    if (userMsgs.length === 0) return; // nothing to summarize

    const now = new Date();
    const dateStr = now.toISOString().slice(0, 10);
    const timeStr = now.toISOString().slice(11, 19).replace(/:/g, '');
    const title = session.title || 'Untitled Session';
    const slug = `session_${dateStr}_${timeStr}`;
    const description = `Session: ${title} (${dateStr})`;

    const content = `Session: ${title}\nDate: ${dateStr}\nModel: ${session.model || 'opus'}\nMessages: ${messages.filter(m => m.role === 'user').length} user, ${messages.filter(m => m.role === 'assistant').length} assistant\n\nTopics discussed:\n${userMsgs.map(m => `- ${m}`).join('\n')}`;

    // Write memory file
    fs.writeFileSync(path.join(memoryDir, `${slug}.md`),
      `---\nname: ${title}\ndescription: ${description}\ntype: session\n---\n\n${content}\n`);

    // Prune old session files (keep max 10)
    const sessionFiles = fs.readdirSync(memoryDir)
      .filter(f => f.startsWith('session_') && f.endsWith('.md'))
      .sort();
    while (sessionFiles.length > 10) {
      const oldest = sessionFiles.shift();
      try { fs.unlinkSync(path.join(memoryDir, oldest)); } catch {}
    }

    // Rebuild index and invalidate cache
    rebuildMemoryIndex();
    _agentMemoryCache = null;

    log(`Session summary saved: ${slug}`);
  } catch (e) {
    log(`Session summary save error: ${e.message}`);
  }
}

function rebuildMemoryIndex() {
  const agentDir = path.join(ROOT, 'agent');
  const memoryDir = path.join(agentDir, 'memory');
  if (!fs.existsSync(memoryDir)) return;

  const sections = { Context: [], Feedback: [], Project: [], Sessions: [] };
  const files = fs.readdirSync(memoryDir).filter(f => f.endsWith('.md')).sort();

  for (const f of files) {
    try {
      const raw = fs.readFileSync(path.join(memoryDir, f), 'utf8');
      const fmMatch = raw.match(/^---\s*\n([\s\S]*?)\n---/);
      let name = f, description = '', type = 'context';
      if (fmMatch) {
        const nameM = fmMatch[1].match(/name:\s*(.+)/);
        const descM = fmMatch[1].match(/description:\s*(.+)/);
        const typeM = fmMatch[1].match(/type:\s*(.+)/);
        if (nameM) name = nameM[1].trim();
        if (descM) description = descM[1].trim();
        if (typeM) type = typeM[1].trim();
      }
      const entry = `- [${name}](memory/${f}) — ${description}`;
      if (type === 'session') sections.Sessions.push(entry);
      else if (type === 'feedback') sections.Feedback.push(entry);
      else if (type === 'project') sections.Project.push(entry);
      else sections.Context.push(entry);
    } catch {}
  }

  let md = '# Agent Memory Index\n';
  for (const [sec, entries] of Object.entries(sections)) {
    md += `\n## ${sec}\n\n`;
    md += entries.length ? entries.join('\n') + '\n' : `_(No ${sec.toLowerCase()} memories yet)_\n`;
  }
  fs.writeFileSync(path.join(agentDir, 'MEMORY.md'), md);
}

// ---------------------------------------------------------------------------
// Memory pruning — keeps total memory within bounds
// ---------------------------------------------------------------------------

function pruneAgentMemory() {
  try {
    const agentDir = path.join(ROOT, 'agent');
    const memoryDir = path.join(agentDir, 'memory');
    if (!fs.existsSync(memoryDir)) return;

    const MAX_TOTAL_CHARS = 12000; // ~4000 tokens
    const files = fs.readdirSync(memoryDir).filter(f => f.endsWith('.md')).sort();

    // Calculate total size
    let totalSize = 0;
    const fileInfo = [];
    for (const f of files) {
      try {
        const content = fs.readFileSync(path.join(memoryDir, f), 'utf8');
        fileInfo.push({ name: f, size: content.length, isSession: f.startsWith('session_') });
        totalSize += content.length;
      } catch {}
    }

    if (totalSize <= MAX_TOTAL_CHARS) return;

    // Prune oldest session files first, then oldest project files
    // Never prune context_* or feedback_* (they're high-value)
    const pruneOrder = fileInfo
      .filter(f => f.isSession)
      .concat(fileInfo.filter(f => !f.isSession && f.name.startsWith('project_')));

    let pruned = 0;
    for (const f of pruneOrder) {
      if (totalSize <= MAX_TOTAL_CHARS) break;
      try {
        fs.unlinkSync(path.join(memoryDir, f.name));
        totalSize -= f.size;
        pruned++;
        log(`Memory pruned: ${f.name} (${f.size} chars)`);
      } catch {}
    }

    if (pruned > 0) rebuildMemoryIndex();
  } catch (e) {
    log(`Memory pruning error: ${e.message}`);
  }
}

// Run memory pruning at startup
pruneAgentMemory();

// ---------------------------------------------------------------------------
// System prompt
// ---------------------------------------------------------------------------

function buildSystemPrompt(sessionId) {
  // =====================================================================
  // SELF-DESCRIBING SYSTEM PROMPT
  // Dynamically discovers all capabilities at runtime.
  // Adding a new skill, script, doc, or table automatically appears here.
  // =====================================================================

  const lines = [];

  // --- 1. Identity (from agent files, fallback to lab.json) ---
  const agent = loadAgentIdentity();
  if (agent.name) {
    lines.push(`You are ${agent.name}, the ${agent.role || LAB.name + ' AI assistant'}. Agent ID: ${agent.agentId || AGENT_ID}`);
    if (agent.soul) {
      lines.push('', agent.soul);
    }
  } else {
    lines.push(LAB.role || `You are the ${LAB.name} AI assistant. You have full access to the project files, scripts, and knowledge base.`);
  }

  // --- 1b. Agent rules ---
  if (agent.rules) {
    lines.push('', agent.rules);
  }

  // --- 1c. Agent memory ---
  const agentMemory = loadAgentMemory();
  if (agentMemory.count > 0) {
    lines.push('', '## Your Memory', '', `You have ${agentMemory.count} memories:`, '', agentMemory.formatted);
  }

  // --- 1d. Recent sessions ---
  if (agentMemory.recentSessions) {
    lines.push('', '## Recent Sessions', '', 'Here is what was discussed in recent sessions:', '', agentMemory.recentSessions);
  }

  // --- 1e. Recent channel activity (cross-context awareness, cached) ---
  const channelActivity = loadRecentChannelActivity();
  if (channelActivity) {
    lines.push('', '## Recent Channel Activity', '', 'Recent messages from joint channels you are a member of. You can reference these if the user asks about channel conversations.', '', channelActivity);
  }

  // --- 2. Data summary (dynamic) ---
  const events = getEvents();
  const clocks = getClocks();
  const sigs = getSignatures();
  if (events.length) lines.push('', `Database: ${events.length} events.`);
  if (Object.keys(clocks).length) {
    lines.push('', 'Clocks:');
    for (const [key, clock] of Object.entries(clocks)) lines.push(`  - ${key}: ${clock.description}`);
  }
  if (sigs.length) {
    lines.push('', 'Named Signatures:');
    for (const sig of sigs) lines.push(`  - R=${sig.remainder} ${sig.name}: ${sig.description}`);
  }

  // --- 3. Skills (dynamic from getSkills(), grouped by category) ---
  const skills = getSkills();
  if (skills.length) {
    const grouped = {};
    for (const s of skills) (grouped[s.category || 'other'] = grouped[s.category || 'other'] || []).push(s);
    lines.push('', 'Available Skills:');
    for (const [cat, catSkills] of Object.entries(grouped)) {
      lines.push(`  [${cat}]`);
      for (const s of catSkills) {
        const chain = s.chains_with && s.chains_with.length ? ` → chains with: ${s.chains_with.join(', ')}` : '';
        lines.push(`    ${s.usage}: ${s.description}${chain}`);
      }
    }
  }

  // --- 4. Workflows (dynamic from workflows.json) ---
  const workflowsPath = path.join(GENESIS_DIR, 'template', 'workflows.json');
  try {
    const wf = JSON.parse(fs.readFileSync(workflowsPath, 'utf8'));
    if (wf.workflows && wf.workflows.length) {
      lines.push('', 'Workflow Recipes (use these patterns to chain skills):');
      for (const w of wf.workflows) {
        lines.push(`  ${w.name}: ${w.steps.join(' → ')}`);
        lines.push(`    When: ${w.trigger}`);
        lines.push(`    ${w.description}`);
      }
    }
    if (wf.categories) {
      lines.push('', 'Skill Categories — when to use each:');
      for (const [cat, info] of Object.entries(wf.categories)) {
        lines.push(`  ${cat}: ${info.description}`);
        lines.push(`    Use when: ${info.when}`);
      }
    }
  } catch (e) { /* no workflows.json */ }

  // --- 5. Scripts (dynamic from manifest) ---
  const scripts = loadScriptsManifest();
  if (scripts.length) {
    lines.push('', 'Analysis Scripts (each is also a slash command):');
    for (const s of scripts) {
      const chains = s.chains_with ? ` → chains with: ${s.chains_with.join(', ')}` : '';
      lines.push(`  - ${s.name || s.file}: ${s.description}${chains}`);
    }
  }

  // --- 6. Database schema (dynamic from SQLite) ---
  const dbPath = path.join(ROOT, 'output', 'jubilee.db');
  if (fs.existsSync(dbPath)) {
    try {
      const { DatabaseSync } = require('node:sqlite');
      const db = new DatabaseSync(dbPath, { open: true, readOnly: true });
      const tables = db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_config' AND name NOT LIKE '%_data' AND name NOT LIKE '%_docsize' AND name NOT LIKE '%_idx' AND name NOT LIKE '%_content' ORDER BY name").all();
      lines.push('', 'SQLite Database — query with /query or python3 scripts/build_db.py --query "SQL"');
      for (const { name } of tables) {
        const cols = db.prepare(`PRAGMA table_info("${name}")`).all();
        const count = db.prepare(`SELECT COUNT(*) as c FROM "${name}"`).get();
        lines.push(`  - ${name} (${count.c} rows): ${cols.map(c => c.name).join(', ')}`);
      }
      lines.push('FTS: events_fts (name, tags, notes, signature), kb_fts (path, title, tags, content)');
      db.close();
    } catch (e) { log(`Schema load error: ${e.message}`); }
  }

  // --- 7. Plugins (dynamic from resolvePlugins()) ---
  const plugins = resolvePlugins();
  if (plugins.length) {
    const categories = {};
    for (const p of plugins) (categories[p.category] = categories[p.category] || []).push(p.name);
    lines.push('', 'Plugins:');
    for (const [cat, names] of Object.entries(categories)) lines.push(`  - ${cat}: ${names.join(', ')}`);
  }

  // --- 8. Documentation (dynamic scan of docs/) ---
  const docsDir = path.join(ROOT, 'docs');
  try {
    const docFiles = fs.readdirSync(docsDir).filter(f => f.endsWith('.md'));
    if (docFiles.length) {
      lines.push('', 'Documentation (in docs/):');
      for (const f of docFiles) lines.push(`  - ${f}`);
    }
  } catch (e) {}

  // --- 9. Enforcements (dynamic from settings) ---
  const settings = loadSettings();
  const activeEnforcements = Object.entries(settings.enforcements || {}).filter(([, v]) => v);
  if (activeEnforcements.length) {
    lines.push('', 'Active Enforcements:');
    for (const [name] of activeEnforcements) lines.push(`  - ${name}`);
  }

  // --- 9b. Task Discipline enforcement (structural prompt injection) ---
  if (settings.enforcements['task-discipline']) {
    const planActive = settings.enforcements['plan-discipline'];
    lines.push(
      '',
      '## TASK DISCIPLINE ENFORCEMENT — ACTIVE',
      '',
      'You are operating under TASK DISCIPLINE mode. This is a MANDATORY structural requirement.',
      '',
      '### Rules:',
    );
    if (planActive) {
      lines.push(
        '1. Plan Discipline is also active — the plan is written FIRST, then tasks are derived from it.',
        '2. Each micro-step in the plan (1.1, 1.2, 2.1, etc.) becomes ONE task.',
        '3. Task content MUST reference phase and step: e.g. "Phase 1.2: Add validation to inputs"',
        '4. Task activeForm MUST mirror: e.g. "Adding validation to inputs (Phase 1.2)"',
        '5. Complete ALL Phase N tasks before creating/starting Phase N+1 tasks.',
      );
    } else {
      lines.push(
        '1. BEFORE doing ANY work (reading files, running commands, writing code, analyzing data),',
        '   you MUST first call the TodoWrite tool to create a task list for the request.',
        '5. You MUST NOT call any tool other than TodoWrite until you have at least one task defined.',
        '   This applies to ALL requests — even simple ones. A one-line task like "Check node version" is fine.',
      );
    }
    lines.push(
      '',
      '### Execution Rules:',
      '- Each task MUST be marked as in_progress BEFORE you begin working on it.',
      '- Only ONE task may be in_progress at any time.',
      '- A task MUST be marked as completed IMMEDIATELY after you finish it, before starting the next.',
      '- When ALL tasks are completed, update the task list to reflect full completion before your final response.',
      '',
      '### Task Format:',
      '- content: imperative form ("Fix the auth bug", "Read the config file")',
      '- activeForm: present continuous ("Fixing the auth bug", "Reading the config file")',
      '- status: pending | in_progress | completed',
      '- Break non-trivial requests into 3+ specific, verifiable tasks.',
      '- For trivial/simple requests, create a SINGLE task.',
      '',
      '### Violation Protocol:',
      'If you find yourself doing work without an active task, STOP immediately.',
      'Call TodoWrite to create/update your task list, mark the relevant task in_progress, then continue.',
      'This is not optional — task discipline is a structural guardrail enforced by the platform.',
    );
  }

  // --- 9c. Plan Discipline enforcement (structural prompt injection) ---
  if (settings.enforcements['plan-discipline']) {
    const planPath = path.join(ROOT, 'plans', (sessionId || 'unknown') + '-plan.md');
    lines.push(
      '',
      '## PLAN DISCIPLINE ENFORCEMENT — ACTIVE',
      '',
      'You are operating under PLAN DISCIPLINE mode. This is a MANDATORY structural requirement.',
      'You MUST plan before you build. Plans drive tasks. Tasks drive execution.',
      '',
      '### Workflow (strict order):',
      '1. RECEIVE the user\'s request — read and understand it fully.',
      '2. WRITE THE PLAN — use the Write tool to save your plan to: ' + planPath,
      '3. CREATE TASKS from the plan — call TodoWrite with tasks derived from Phase micro-steps.',
      '4. EXECUTE — work through tasks one at a time, marking each in_progress then completed.',
      '5. DEVIATE SAFELY — if you need to change approach, UPDATE the plan file first, then update tasks.',
      '',
      '### Plan Format (MANDATORY structure):',
      '',
      '```markdown',
      '# Plan: [Brief title]',
      '',
      '## Objective',
      '[What you are accomplishing and why — 1-3 sentences]',
      '',
      '## Phase 1: [Phase Name]',
      '[Brief description of this phase]',
      '',
      '### Steps:',
      '1.1. [Specific micro-step — actionable, verifiable]',
      '1.2. [Next micro-step]',
      '1.3. [Next micro-step]',
      '',
      '### Files:',
      '- path/to/file.js — what changes and why',
      '',
      '## Phase 2: [Phase Name]',
      '[Brief description]',
      '',
      '### Steps:',
      '2.1. [Micro-step]',
      '2.2. [Micro-step]',
      '',
      '### Files:',
      '- path/to/file.js — what changes',
      '',
      '## Phase 3: [Phase Name] (if needed)',
      '...',
      '',
      '## Risks & Considerations',
      '- [What could go wrong, edge cases, dependencies]',
      '```',
      '',
      '### Task Creation Rules:',
      '- Each Phase becomes a GROUP of tasks.',
      '- Each micro-step (1.1, 1.2, 2.1, etc.) becomes ONE task in TodoWrite.',
      '- Task content MUST reference the phase and step: e.g. "Phase 1.2: Add validation to form inputs"',
      '- Task activeForm mirrors it: e.g. "Adding validation to form inputs (Phase 1.2)"',
      '- Complete ALL tasks in Phase 1 before starting Phase 2 tasks.',
      '- For trivial requests (single-step work), use a single Phase with 1-2 steps.',
      '',
      '### Execution Rules:',
      '- Work through phases IN ORDER. Do not skip ahead.',
      '- Mark each task in_progress BEFORE starting the work.',
      '- Mark each task completed IMMEDIATELY after finishing.',
      '- Only ONE task may be in_progress at a time.',
      '- When a phase is complete, move to the next phase.',
      '- When ALL phases are done, update the plan file to mark completion at the top.',
      '',
      '### Violation Protocol:',
      'If you begin implementation work (editing files, running commands, writing code)',
      'WITHOUT first having written the plan file and created tasks, STOP immediately.',
      'Write the plan, create tasks, then continue. This is non-negotiable.',
    );
  }

  // --- 9d. Job Discipline enforcement (structural prompt injection) ---
  if (settings.enforcements['job-discipline']) {
    const session = getSession(sessionId);
    const projectId = session ? session.projectId : null;
    const project = projectId ? getProject(projectId) : null;
    const activeJob = (projectId && sessionId) ? getActiveJob(projectId, sessionId) : null;
    const completedJobs = (projectId && sessionId) ? getSessionJobs(projectId, sessionId).filter(j => j.status === 'completed') : [];

    if (project) {
      lines.push(
        '',
        '## JOB DISCIPLINE ENFORCEMENT — ACTIVE',
        '',
        'You are operating under JOB DISCIPLINE mode. This is a MANDATORY structural requirement.',
        'The strict pipeline is: **Job → Plan → Tasks → Execute**. No shortcuts allowed.',
        'PreToolUse hooks will BLOCK tool calls that violate the pipeline.',
        '',
        '### Current Context:',
        `- **Project:** ${project.name} (${projectId})`,
        `- **Session:** ${sessionId}`,
        `- **Active Job:** ${activeJob ? activeJob.title + ' (' + activeJob.id + ')' : 'NONE'}`,
        `- **Completed Jobs:** ${completedJobs.length}`,
      );

      if (activeJob) {
        const jobPlanPath = getJobPlanPath(projectId, activeJob.id);
        const hasPlan = fs.existsSync(jobPlanPath);
        const hasTodos = Array.isArray(session ? session.todos : null) && session.todos.length > 0;
        const allDone = hasTodos && session.todos.every(t => t.status === 'completed');

        lines.push(
          '',
          '### Pipeline Status:',
          `  1. Job: ✅ "${activeJob.title}"`,
          `  2. Plan: ${hasPlan ? '✅ Written' : '❌ NOT WRITTEN — do this FIRST'}`,
          `  3. Tasks: ${hasTodos ? (allDone ? '✅ All completed' : '✅ Created') : '❌ NOT CREATED' + (hasPlan ? ' — do this NEXT' : '')}`,
          `  4. Execute: ${(hasPlan && hasTodos) ? '✅ Ready to work' : '🚫 BLOCKED until plan + tasks exist'}`,
        );

        lines.push(
          '',
          '### Job File Paths (MANDATORY — use these, NOT session-level paths):',
          `- **Plan file:** ${jobPlanPath}`,
          '',
          '### Strict Rules:',
          '1. **FIRST TOOL CALL after creating a job MUST be Write** to save your plan to the exact path above.',
          '   This is NOT optional. The plan pane in the UI reads this file. If you skip it, the user sees "No plan yet."',
          '   Do NOT use plans/{sessionId}-plan.md — that is the old path.',
          '2. Plan must have Phases with numbered micro-steps (1.1, 1.2, 2.1, etc.)',
          '3. **SECOND step: call TodoWrite** to create tasks derived from each micro-step in the plan.',
          '4. Only AFTER the plan file is written AND tasks exist may you begin implementation.',
          '   If you call any tool (Bash, Edit, Grep, etc.) before writing the plan file, you are violating discipline.',
          '5. Follow tasks in order: mark in_progress → do work → mark completed.',
          '6. When ALL tasks are complete, close the job by running:',
          `   curl -s http://localhost:${PORT}/api/projects/${projectId}/jobs/${activeJob.id} -X PATCH -H "Content-Type: application/json" -d \'{"status":"completed"}\'`,
          '',
          '### Mid-Job Updates:',
          '- You CAN update the plan file and tasks mid-job if requirements change.',
          '- Add new tasks via TodoWrite if you discover additional work.',
          '- Update the plan file with new phases if scope changes.',
        );

        // If all tasks are done, prompt the agent to close the job
        if (allDone) {
          lines.push(
            '',
            '### ⚠️ ALL TASKS COMPLETE — Close this job now.',
            `Run: curl -s http://localhost:${PORT}/api/projects/${projectId}/jobs/${activeJob.id} -X PATCH -H "Content-Type: application/json" -d \'{"status":"completed"}\'`,
            'After closing, if the user gives you more work, create a NEW job for it.',
          );
        }
      } else {
        lines.push(
          '',
          '### Pipeline Status:',
          '  1. Job: ❌ NO ACTIVE JOB',
          '  2. Plan: 🚫 BLOCKED',
          '  3. Tasks: 🚫 BLOCKED',
          '  4. Execute: 🚫 BLOCKED',
          '',
          '### CRITICAL — You MUST create a job before doing any work.',
          `Create a job by running this Bash command:`,
          `  curl -s http://localhost:${PORT}/api/sessions/${sessionId}/jobs -X POST -H "Content-Type: application/json" -d \'{"title":"YOUR JOB TITLE HERE"}\'`,
          '',
          'Replace YOUR JOB TITLE HERE with a short descriptive title for the work.',
          'The title should describe what the user is asking you to do.',
          'After creating the job, proceed to write the plan, create tasks, then execute.',
        );

        if (completedJobs.length) {
          lines.push(
            '',
            '### Previous Jobs in This Session:',
            ...completedJobs.map(j => `- ✅ ${j.title} (completed ${j.completedAt ? new Date(j.completedAt).toLocaleTimeString() : ''})`),
            '',
            'The user is giving you new instructions. Create a NEW job for this new work.',
          );
        }
      }
    } else if (!projectId) {
      lines.push(
        '',
        '## JOB DISCIPLINE — SESSION NOT IN PROJECT',
        '',
        'This session is not assigned to a project. Job discipline requires a project.',
        'Ask the user which project this session belongs to, or create a new project.',
      );
    }
  }

  // --- 10. Instructions (skip if agent rules are loaded — they cover these) ---
  if (!agent.rules) {
    lines.push(
      '', 'Instructions:',
      '- Present findings as data, not doctrine. Quantify statistical significance.',
      '- You can run python3 scripts, query the database, read/write files.',
      '- Use /rebuild to run the full pipeline after data changes.',
      '- Before modifying data files, use /snapshot to create a backup.',
      '- Chain analyses for multi-step research.',
    );
  }

  // --- 11. Global template awareness ---
  lines.push(
    '', 'Global Template Architecture:',
    `- This lab runs from a shared server template at ${GENESIS_DIR}/template/core/server.js`,
    `- Global skills catalog: ${GLOBAL_SKILLS_DIR}/catalog.json`,
    `- Global plugins: ${GLOBAL_PLUGINS_DIR}/ (core/ and analysis/ subdirectories)`,
    '- Instance-local scripts live in this instance\'s scripts/ directory.',
    '- When you create a new script or skill, create it locally in this instance\'s scripts/ directory first.',
    '- Do NOT write directly to the global template directories — only Genesis IDE can promote scripts to global.',
    '- If the user asks you to make a skill or script available to all labs, tell them to use Genesis IDE to promote it.',
    '- If the user asks you to modify the server or core lab behavior, tell them to use Genesis IDE — edits go to template/core/server.js, then get promoted.',
  );

  // --- 12. Joint session awareness ---
  try {
    const channels = jointCmd('list-channels');
    if (Array.isArray(channels) && channels.length > 0) {
      // Check which channels this agent is a member of
      const myChannels = [];
      for (const ch of channels) {
        const members = jointCmd('members', [ch.name]);
        if (Array.isArray(members) && members.some(m => m.agent_id === AGENT_ID)) {
          myChannels.push(ch);
        }
      }
      if (myChannels.length > 0) {
        const agentName = agent.name || AGENT_DISPLAY;
        lines.push('', `You are ${agentName} (${agent.agentId || AGENT_ID}).`);
        lines.push('Joint Sessions — you are a member of these shared channels:');
        for (const ch of myChannels) {
          lines.push(`  - #${ch.name}: ${ch.topic || 'No topic'} (${ch.member_count} members, ${ch.last_seq || 0} messages)`);
        }
        lines.push('Use /joint-read #channel to read messages, /joint-post #channel <msg> to post.');
        lines.push('Use /joint-ask #channel <port> "question" to invoke a remote agent in a channel.');
        // Agent addressing rules
        lines.push('', '@Mention Addressing Rules:');
        lines.push(`- Messages starting with @${agentName} are directed AT YOU — you MUST respond.`);
        lines.push('- Messages starting with @OtherAgentName are NOT for you — stay SILENT, do not respond.');
        lines.push('- Messages with no @mention are broadcast to all — respond if the topic is relevant to your domain.');
        lines.push(`- When reading joint messages, look for @${agentName} (case-insensitive) to find messages addressed to you.`);
        lines.push(`- Partial matches also count: @${agentName.slice(0, 3)} addresses you.`);
        // Channel task coordination
        lines.push('', '## Channel Task Coordination');
        lines.push('When you receive a [CHANNEL TASK from #channel-name] message:');
        lines.push('- This is a task assigned to you via a joint channel by another agent or Michael.');
        lines.push('- You are now working in your MAIN SESSION with full tool access (files, scripts, database, etc.).');
        lines.push('- Do the actual work here — run analysis, read files, write code, whatever the task requires.');
        lines.push('- Your final text response will be automatically posted back to the channel.');
        lines.push('- Keep your channel response concise — summarize results, not process.');
        lines.push('- Start your response with @mentions of everyone involved.');
        lines.push('- You do NOT need to be told to work in your main session — this is your natural behavior.');
      }
    }
  } catch (e) { /* joint sessions unavailable */ }

  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Context enrichment
// ---------------------------------------------------------------------------

function buildDataContext(message) {
  const db = getDatabase();
  const sigs = getSignatures();
  const lines = ['[JUBILEE LAB DATA CONTEXT]'];

  // Remainder values mentioned
  const remMatch = message.match(/\.(\d{2})\b/);
  if (remMatch) {
    const rem = parseFloat(`0.${remMatch[1]}`);
    const matching = db.filter(e => {
      const r = parseFloat(e.remainder);
      return !isNaN(r) && Math.abs(r - rem) < 0.02;
    });
    if (matching.length > 0) {
      lines.push(`\nEvents at remainder ~${rem.toFixed(2)} (${matching.length} found):`);
      for (const e of matching.slice(0, 20)) {
        lines.push(`  - ${e.name} (${e.year_ad}) — J${e.jubilee}, R${e.remainder}, Sig: ${e.signature || 'none'}`);
      }
    }
  }

  // Signature names mentioned
  const upperMsg = message.toUpperCase();
  for (const sig of sigs) {
    if (upperMsg.includes(sig.name.toUpperCase())) {
      const matching = db.filter(e => e.signature === sig.name);
      if (matching.length > 0) {
        lines.push(`\nEvents with "${sig.name}" signature (${matching.length} found):`);
        for (const e of matching.slice(0, 15)) {
          lines.push(`  - ${e.name} (${e.year_ad}) — J${e.jubilee}, R${e.remainder}`);
        }
      }
    }
  }

  // Specific event names mentioned
  const events = getEvents();
  for (const e of events) {
    if (e.name && upperMsg.includes(e.name.toUpperCase())) {
      const dbEntry = db.find(d => d.name === e.name);
      if (dbEntry) {
        lines.push(`\nEvent detail — ${dbEntry.name}:`);
        lines.push(`  Year: ${dbEntry.year_ad} | AM: ${dbEntry.am_year} | Jubilee: ${dbEntry.jubilee}`);
        lines.push(`  Remainder: ${dbEntry.remainder} | Signature: ${dbEntry.signature || 'none'}`);
        if (dbEntry.israel_jubilee) lines.push(`  Israel: J${dbEntry.israel_jubilee} R${dbEntry.israel_remainder}`);
        if (dbEntry.church_jubilee) lines.push(`  Church: J${dbEntry.church_jubilee} R${dbEntry.church_remainder}`);
        if (dbEntry.notes || e.notes) lines.push(`  Notes: ${dbEntry.notes || e.notes}`);
        break;
      }
    }
  }

  // Year mentioned (check convergence)
  const yearMatch = message.match(/\b(20[2-4]\d)\b/);
  if (yearMatch) {
    const year = parseInt(yearMatch[1]);
    const dbEntry = db.find(d => parseInt(d.year_ad) === year);
    if (dbEntry) {
      lines.push(`\nYear ${year} in database: ${dbEntry.name} — J${dbEntry.jubilee}, R${dbEntry.remainder}`);
    }
  }

  // Summary stats
  const sigCounts = {};
  for (const e of db) { if (e.signature) sigCounts[e.signature] = (sigCounts[e.signature] || 0) + 1; }
  const topSigs = Object.entries(sigCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);
  lines.push(`\nDatabase: ${db.length} events, ${Object.keys(sigCounts).length} active signatures`);
  if (topSigs.length) lines.push('Top: ' + topSigs.map(([s, c]) => `${s}(${c})`).join(', '));
  lines.push('[END DATA CONTEXT]');

  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Claude CLI process
// ---------------------------------------------------------------------------

function sendToClaudeStream(sessionId, message, onEvent) {
  return new Promise(async (resolve, reject) => {
    const session = getSession(sessionId);
    if (!session) { reject(new Error('Session not found')); return; }

    const systemPrompt = buildSystemPrompt(sessionId);
    const escaped = systemPrompt.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    const ts = Date.now();
    const scriptPath = `/tmp/jubilee-lab-claude-${ts}.sh`;
    const resumeFlag = session.claudeSessionId ? `--resume "${session.claudeSessionId}"` : '';
    const model = session.model || 'opus';

    // Only append system prompt on first message (no claudeSessionId yet).
    // On resumed sessions, Claude already has it — re-sending bloats context/cost.
    const systemFlag = session.claudeSessionId ? '' : `--append-system-prompt "${escaped}"`;

    const script = `#!/bin/bash
unset CLAUDECODE CLAUDE_CODE
export LAB_PORT="${PORT}"
export GENESIS_DIR="${GENESIS_DIR}"
export LAB_INSTANCE="${INSTANCE_DIR}"
cd "${WORK_DIR}"
"${CLAUDE_BIN}" -p --output-format stream-json --verbose --include-partial-messages --permission-mode bypassPermissions --model ${model} ${resumeFlag} ${systemFlag}
`;
    try { await writeFile(scriptPath, script, { mode: 0o755 }); }
    catch (e) { reject(e); return; }

    log(`Spawning Claude (${model}) for session ${sessionId.slice(0, 8)}...`);
    const startTime = Date.now();
    const proc = spawn('/bin/bash', [scriptPath], { stdio: ['pipe', 'pipe', 'pipe'] });
    activeProcs.set(sessionId, proc);

    proc.stdin.write(message);
    proc.stdin.end();

    const rl = createInterface({ input: proc.stdout });
    let stderr = '';
    // Track content blocks by index for stream_event deltas
    let blockTypes = {};  // index -> 'thinking' | 'text' | 'tool_use'
    let blockMeta = {};   // index -> { id, name, input } for tool_use
    let toolJsonBuf = {}; // index -> partial JSON string for tool input
    let thinkingBuf = {}; // index -> accumulated thinking text
    let seenToolIds = new Set();
    let assistantSaved = false; // prevent duplicate saves from assistant + result events
    let contextOverflowHandled = false; // suppress close error if overflow already sent via result event

    proc.stderr.on('data', chunk => { stderr += chunk.toString(); });

    rl.on('line', line => {
      if (!line.trim()) return;
      try {
        const event = JSON.parse(line);

        // --- system/init: capture session ID ---
        if (event.type === 'system' && event.subtype === 'init' && event.session_id) {
          log(`Claude session: ${event.session_id}`);
          updateSession(sessionId, { claudeSessionId: event.session_id });
          onEvent(event);
        }

        // --- stream_event: real-time incremental tokens ---
        else if (event.type === 'stream_event') {
          const se = event.event || {};

          if (se.type === 'content_block_start') {
            const cb = se.content_block || {};
            blockTypes[se.index] = cb.type;
            if (cb.type === 'tool_use') {
              blockMeta[se.index] = { id: cb.id, name: cb.name };
              toolJsonBuf[se.index] = '';
              // Emit tool_start immediately
              const detail = { type: 'tool_start', tool: cb.name, id: cb.id };
              onEvent({ type: 'assistant', content: [detail] });
            }
          }

          else if (se.type === 'content_block_delta') {
            const delta = se.delta || {};
            if (delta.type === 'thinking_delta') {
              thinkingBuf[se.index] = (thinkingBuf[se.index] || '') + (delta.thinking || '');
              onEvent({ type: 'assistant', content: [{ type: 'thinking', thinking: delta.thinking }] });
            } else if (delta.type === 'text_delta') {
              onEvent({ type: 'assistant', content: [{ type: 'text', text: delta.text }] });
            } else if (delta.type === 'input_json_delta') {
              toolJsonBuf[se.index] = (toolJsonBuf[se.index] || '') + (delta.partial_json || '');
            }
          }

          else if (se.type === 'content_block_stop') {
            const bt = blockTypes[se.index];
            if (bt === 'thinking' && thinkingBuf[se.index]) {
              appendMessage(sessionId, {
                role: 'thinking', content: thinkingBuf[se.index],
                timestamp: new Date().toISOString(),
              });
            }
            if (bt === 'tool_use' && blockMeta[se.index]) {
              // Parse complete tool input and emit descriptive label
              const meta = blockMeta[se.index];
              let input = {};
              try { input = JSON.parse(toolJsonBuf[se.index] || '{}'); } catch (e) {}
              let description = `Using ${meta.name}...`;
              if (meta.name === 'Bash' && input.command) description = `$ ${input.command}`;
              else if (meta.name === 'Read' && input.file_path) description = `Reading ${input.file_path}`;
              else if (meta.name === 'Write' && input.file_path) {
                description = `Writing ${input.file_path}`;
                // Detect plan file writes and emit plan_update event
                const plansDir = path.join(ROOT, 'plans');
                if (input.file_path.startsWith(plansDir) && input.file_path.endsWith('-plan.md')) {
                  onEvent({ type: 'assistant', content: [{ type: 'plan_update', path: input.file_path, content: input.content || '' }] });
                }
                // Also detect job plan writes: projects/{id}/jobs/{id}-plan.md
                if (input.file_path.includes('/jobs/') && input.file_path.endsWith('-plan.md')) {
                  onEvent({ type: 'assistant', content: [{ type: 'plan_update', path: input.file_path, content: input.content || '' }] });
                }
                // Emit file_changed event for real-time viewer refresh
                onEvent({ type: 'assistant', content: [{ type: 'file_changed', path: input.file_path }] });
              }
              else if (meta.name === 'Edit' && input.file_path) {
                description = `Editing ${input.file_path}`;
                // Detect plan file edits
                const plansDir2 = path.join(ROOT, 'plans');
                if (input.file_path.startsWith(plansDir2) && input.file_path.endsWith('-plan.md')) {
                  try {
                    const updated = fs.readFileSync(input.file_path, 'utf8');
                    onEvent({ type: 'assistant', content: [{ type: 'plan_update', path: input.file_path, content: updated }] });
                  } catch {}
                }
                // Also detect job plan edits: projects/{id}/jobs/{id}-plan.md
                if (input.file_path.includes('/jobs/') && input.file_path.endsWith('-plan.md')) {
                  try {
                    const updated = fs.readFileSync(input.file_path, 'utf8');
                    onEvent({ type: 'assistant', content: [{ type: 'plan_update', path: input.file_path, content: updated }] });
                  } catch {}
                }
                // Emit file_changed event for real-time viewer refresh
                onEvent({ type: 'assistant', content: [{ type: 'file_changed', path: input.file_path }] });
              }
              else if (meta.name === 'Grep' && input.pattern) description = `Searching for "${input.pattern}"${input.path ? ' in ' + input.path : ''}`;
              else if (meta.name === 'Glob' && input.pattern) description = `Finding files: ${input.pattern}`;
              else if (meta.name === 'Agent' && input.description) description = `Agent: ${input.description}${input.prompt ? ' — ' + input.prompt.slice(0, 200) : ''}`;
              else if (meta.name === 'TodoWrite') {
                description = `Updating task list`;
                // Extract todo items for display + persist to session
                if (input.todos && Array.isArray(input.todos)) {
                  const items = input.todos.map(t => {
                    const icon = t.status === 'completed' ? '\u2705' : t.status === 'in_progress' ? '\u23f3' : '\u2b1c';
                    return `${icon} ${t.content || t.activeForm || ''}`;
                  }).join('\n');
                  description = `Updating task list:\n${items}`;
                  // Save todos to session for the task pane
                  updateSession(sessionId, { todos: input.todos });
                  // Save todos to a file for file browser navigation
                  try {
                    const tasksDir = path.join(ROOT, 'tasks');
                    if (!fs.existsSync(tasksDir)) fs.mkdirSync(tasksDir, { recursive: true });
                    fs.writeFileSync(path.join(tasksDir, sessionId + '-tasks.json'), JSON.stringify(input.todos, null, 2));
                  } catch (e) { log('Save task file error: ' + e.message); }
                  // Also persist to job tasks.json if session has an active job
                  try {
                    const _sess = getSession(sessionId);
                    if (_sess && _sess.projectId) {
                      const _activeJob = getActiveJob(_sess.projectId, _sess.id);
                      if (_activeJob) {
                        const jobTasksFile = getJobTasksPath(_sess.projectId, _activeJob.id);
                        fs.writeFileSync(jobTasksFile, JSON.stringify(input.todos, null, 2));
                      }
                    }
                  } catch (e) { log('Save job tasks error: ' + e.message); }
                  // Emit todos event so the frontend task pane updates live
                  onEvent({ type: 'assistant', content: [{ type: 'todos_update', todos: input.todos }] });
                  // Auto-update plan status when all tasks are completed
                  const allDone = input.todos.length > 0 && input.todos.every(t => t.status === 'completed');
                  if (allDone) {
                    // Check session-level plan first, then job-level plan
                    const planFiles = [path.join(ROOT, 'plans', sessionId + '-plan.md')];
                    try {
                      const _sess2 = getSession(sessionId);
                      if (_sess2 && _sess2.projectId) {
                        const _aj = getActiveJob(_sess2.projectId, _sess2.id);
                        if (_aj) planFiles.unshift(getJobPlanPath(_sess2.projectId, _aj.id));
                      }
                    } catch {}
                    for (const planFile of planFiles) {
                      try {
                        if (fs.existsSync(planFile)) {
                          let planContent = fs.readFileSync(planFile, 'utf8');
                          planContent = planContent.replace(/\*\*Status\*?\*?:?\*?\*?\s*(IN PROGRESS|In Progress|in progress)/i, '**Status:** COMPLETE');
                          planContent = planContent.replace(/^(- \[ \])/gm, '- [x]');
                          fs.writeFileSync(planFile, planContent);
                          onEvent({ type: 'assistant', content: [{ type: 'plan_update', path: planFile, content: planContent }] });
                          break; // only update the first found plan
                        }
                      } catch (e) { log('Plan auto-complete error: ' + e.message); }
                    }
                  }
                }
              }
              else if (input.file_path) description = `${meta.name}: ${input.file_path}`;
              // Update the tool_start with full description
              onEvent({ type: 'assistant', content: [{ type: 'tool_description', tool: meta.name, id: meta.id, description }] });
              appendMessage(sessionId, {
                role: 'system', content: description,
                timestamp: new Date().toISOString(), tool: meta.name, toolId: meta.id,
              });
            }
          }
        }

        // --- user: tool results ---
        else if (event.type === 'user') {
          const content = event.message?.content || [];
          for (const block of content) {
            if (block.type === 'tool_result') {
              let raw;
              if (typeof block.content === 'string') {
                raw = block.content;
              } else if (Array.isArray(block.content)) {
                // Extract text from content blocks (e.g. Agent tool returns [{type:"text",text:"..."}])
                raw = block.content.map(b => b.text || b.content || '').join('');
              } else {
                raw = JSON.stringify(block.content);
              }
              const output = raw.slice(0, 4000);
              appendMessage(sessionId, {
                role: 'system', content: output,
                timestamp: new Date().toISOString(), tool: 'output', toolId: block.tool_use_id,
              });
              onEvent({ type: 'assistant', content: [{ type: 'tool_result', tool_use_id: block.tool_use_id, content: output }] });
            }
          }
        }

        // --- result: final ---
        else if (event.type === 'result') {
          // Detect context overflow from result event (Claude CLI returns is_error + "Prompt is too long")
          if (event.is_error && /prompt.*(too long|too large)/i.test(event.result || '')) {
            log(`Context overflow detected: ${(event.result || '').slice(0, 100)}`);
            event._contextOverflow = true;
            contextOverflowHandled = true;
          }
          updateSession(sessionId, {
            lastMessageAt: new Date().toISOString(),
            totalCost: (session.totalCost || 0) + (event.total_cost_usd || 0),
          });
          onEvent(event);
        }

        // Complete assistant message — save for channel invocations, skip for chat (result event saves with metadata)
        else if (event.type === 'assistant') {
          const content = event.message?.content || [];
          const types = content.map(b => b.type).join(',');
          const isError = event.error || event.message?.error;
          log(`Assistant event: ${content.length} blocks [${types}]${isError ? ' (error: ' + isError + ')' : ''}`);
          // Skip saving error responses (e.g. "Prompt is too long")
          if (isError) {
            log(`Skipping save for error assistant event: ${isError}`);
          } else {
            const textParts = content
              .filter(b => b.type === 'text')
              .map(b => b.text)
              .join('');
            if (textParts && !assistantSaved) {
              assistantSaved = true; // mark so result event can skip duplicate save
              appendMessage(sessionId, {
                role: 'assistant', content: textParts,
                timestamp: new Date().toISOString(),
              });
            }
          }
        }

      } catch (e) { log(`Stream JSON parse error: ${e.message}`); }
    });

    proc.on('error', async err => {
      await unlink(scriptPath).catch(() => {});
      reject(err);
    });

    // Wait for readline to finish processing all buffered lines before handling close
    let rlClosed = false;
    rl.on('close', () => { rlClosed = true; });

    proc.on('close', async code => {
      activeProcs.delete(sessionId);
      // Wait for readline to drain any buffered lines (up to 500ms)
      if (!rlClosed) await new Promise(r => { rl.on('close', r); setTimeout(r, 500); });
      const dur = ((Date.now() - startTime) / 1000).toFixed(1);
      await unlink(scriptPath).catch(() => {});
      if (code !== 0) {
        log(`Claude exited ${code} (${dur}s): ${stderr.slice(0, 200)}`);
        // If context overflow was already handled via result event, resolve cleanly
        if (contextOverflowHandled) {
          log(`Context overflow already handled via result event, resolving`);
          resolve();
          return;
        }
        // Detect context window overflow from stderr (fallback)
        const isContextOverflow = /prompt.*(too long|too large)|context.*exceed|token.*limit|max.*context/i.test(stderr);
        if (isContextOverflow) {
          reject(new Error('CONTEXT_OVERFLOW: The conversation has exceeded the context window. Use /compact to summarize and reset the context.'));
        } else {
          reject(new Error(`Claude exited ${code}: ${stderr.slice(0, 500)}`));
        }
        return;
      }
      log(`Claude completed (${dur}s)`);
      // Auto-save session summary to agent memory
      try { saveSessionSummary(sessionId); } catch (e) { log(`Session summary error: ${e.message}`); }
      resolve();
    });
  });
}

// ---------------------------------------------------------------------------
// Invoke agent in joint channel — one-shot Claude CLI call
// ---------------------------------------------------------------------------

// Rate limiter state for agent responses in channels
const channelRateLimits = new Map(); // channelId -> { count, resetAt }
const channelAgentExchanges = new Map(); // channelId -> { lastAgentId, consecutiveCount }
let activeInvocation = false; // concurrency guard — one invoke at a time

function invokeAgentInChannel(channelId, prompt, senderName) {
  if (activeInvocation) {
    log('Invoke: skipped — another invocation already in progress');
    return;
  }
  activeInvocation = true;
  const agent = loadAgentIdentity();
  const agentName = agent.name || AGENT_DISPLAY;

  // Load channel info and recent messages
  const channelInfo = jointCmd('channel-info', [channelId]);
  const recentMsgs = jointCmd('messages', [channelId, '0', '20']);
  const channelName = channelInfo?.name || channelId;
  const channelContext = Array.isArray(recentMsgs)
    ? recentMsgs.map(m => `[${m.display_name}] ${m.content}`).join('\n')
    : '(no messages)';

  // Route through main session for full multi-turn capability
  const mainSession = getOrCreateMainSession();
  const taskMessage = [
    `[CHANNEL TASK from #${channelName}]`,
    `${senderName || 'Someone'} mentioned you in #${channelName}:`,
    '',
    `> ${prompt}`,
    '',
    `Recent channel context:`,
    channelContext,
    '',
    `Respond to this. When done, your response will be posted to #${channelName}.`,
  ].join('\n');

  log(`Invoke: routing #${channelName} task to main session ${mainSession.id.slice(0,8)}...`);

  // Append the channel task as a user message in the main session
  appendMessage(mainSession.id, {
    role: 'user', content: taskMessage,
    timestamp: new Date().toISOString(),
  });
  updateSession(mainSession.id, { messageCount: (mainSession.messageCount || 0) + 1, lastMessageAt: new Date().toISOString() });

  // Send to Claude via main session (full tool access, multi-turn)
  sendToClaudeStream(mainSession.id, taskMessage, (event) => {
    // Broadcast to any live session listeners (so browser can see work happening)
    if (event.type === 'stream_event' || event.type === 'assistant') {
      // Already handled by sendToClaudeStream's sessionBroadcast
    }
  }).then(() => {
    // Extract the last assistant message from the main session
    const msgs = getMessages(mainSession.id);
    const lastAssistant = [...msgs].reverse().find(m => m.role === 'assistant');
    if (lastAssistant && lastAssistant.content) {
      const responseText = lastAssistant.content.slice(0, 8000); // Cap channel responses
      log(`Invoke: ${agentName} responding in #${channelName} via main session (${responseText.length} chars)`);
      jointCmd('post', [channelId, AGENT_ID, AGENT_DISPLAY, 'agent', responseText]);
    } else {
      log(`Invoke: no assistant response in main session for #${channelName}`);
      jointCmd('post', [channelId, 'system', 'System', 'system', `${agentName} had no response.`]);
    }
    activeInvocation = false;
  }).catch(err => {
    log(`Invoke error (main session): ${err.message}`);
    jointCmd('post', [channelId, 'system', 'System', 'system', `Error invoking ${agentName}: ${err.message}`]);
    activeInvocation = false;
  });
}

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Persistent logging — writes to ROOT/logs/server.log
// ---------------------------------------------------------------------------
const LOG_DIR = path.join(ROOT, 'logs');
const LOG_FILE = path.join(LOG_DIR, 'server.log');
const MAX_LOG_SIZE = 5 * 1024 * 1024; // 5MB rotation

try { fs.mkdirSync(LOG_DIR, { recursive: true }); } catch {}

function log(msg, level) {
  level = level || 'INFO';
  const now = new Date();
  const ts = now.toLocaleTimeString();
  const iso = now.toISOString();
  console.log(`  [${ts}] ${msg}`);
  try {
    try { const s = fs.statSync(LOG_FILE); if (s.size > MAX_LOG_SIZE) { fs.renameSync(LOG_FILE, LOG_FILE + '.' + iso.slice(0, 10)); } } catch {}
    fs.appendFileSync(LOG_FILE, `[${iso}] [${level}] ${msg}\n`);
  } catch {}
}

function resolvePlatformPath(p) { return path.isAbsolute(p) ? p : path.join(SERVER_ROOT, p); }

// Kill all child platform instances (used by restart and shutdown)
function killAllChildren() {
  let totalKilled = 0;
  try {
    const platforms = JSON.parse(fs.readFileSync(path.join(INSTANCE_DIR, 'platforms.json'), 'utf8'));
    const { execSync } = require('node:child_process');
    for (const plat of platforms) {
      const instDir = path.join(resolvePlatformPath(plat.path), 'instances');
      try {
        for (const name of fs.readdirSync(instDir)) {
          const ljPath = path.join(instDir, name, 'lab.json');
          if (!fs.existsSync(ljPath)) continue;
          const cfg = JSON.parse(fs.readFileSync(ljPath, 'utf8'));
          if (cfg.port) {
            for (const pt of [cfg.port, cfg.port + 70]) {
              try {
                const pids = execSync(`lsof -ti:${pt}`, { encoding: 'utf8' }).trim().split('\n');
                for (const pid of pids) {
                  if (pid && parseInt(pid) !== process.pid) {
                    try { process.kill(parseInt(pid), 'SIGKILL'); totalKilled++; } catch {}
                  }
                }
              } catch {}
            }
          }
        }
      } catch {}
    }
  } catch (e) { log(`killAllChildren error: ${e.message}`, 'ERROR'); }
  return totalKilled;
}

function platformLog(platformPath, msg, level) {
  if (!IS_GENESIS) return; // only genesis writes platform logs
  level = level || 'INFO';
  const iso = new Date().toISOString();
  const logDir = path.join(platformPath, 'logs');
  const logFile = path.join(logDir, 'platform.log');
  try {
    fs.mkdirSync(logDir, { recursive: true });
    try { const s = fs.statSync(logFile); if (s.size > MAX_LOG_SIZE) { fs.renameSync(logFile, logFile + '.' + iso.slice(0, 10)); } } catch {}
    fs.appendFileSync(logFile, `[${iso}] [${level}] ${msg}\n`);
  } catch {}
}

function parseBody(req) {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => { try { resolve(JSON.parse(body)); } catch { resolve({}); } });
    req.on('error', () => resolve({}));
  });
}

function json(res, data, status = 200) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
  });
  res.end(JSON.stringify(data));
}

// HTTP client helper for agent-to-agent communication
function fetchJson(url, opts = {}) {
  return new Promise((resolve, reject) => {
    const { method = 'GET', body } = opts;
    const parsed = new URL(url);
    const reqOpts = {
      hostname: parsed.hostname,
      port: parsed.port,
      path: parsed.pathname + parsed.search,
      method,
      headers: { 'Content-Type': 'application/json' },
      timeout: 10000,
    };
    const req = http.request(reqOpts, (resp) => {
      let data = '';
      resp.on('data', c => data += c);
      resp.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch { resolve({ raw: data }); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Request timed out')); });
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

function serveFile(res, filepath, contentType) {
  try {
    const content = fs.readFileSync(filepath);
    res.writeHead(200, { 'Content-Type': contentType, 'Access-Control-Allow-Origin': '*' });
    res.end(content);
  } catch {
    res.writeHead(404);
    res.end('Not Found');
  }
}

// ---------------------------------------------------------------------------
// HTTP Server
// ---------------------------------------------------------------------------

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, DELETE, PATCH, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    });
    res.end();
    return;
  }

  const url = new URL(req.url, `http://localhost:${PORT}`);
  const p = url.pathname;
  const m = req.method;

  // --- Static ---
  if (IS_GENESIS && p === '/' && m === 'GET') {
    serveFile(res, path.join(INSTANCE_DIR, 'console.html'), 'text/html; charset=utf-8');
    return;
  }
  if (p === '/ide' && m === 'GET') {
    serveFile(res, path.join(__dirname, 'index.html'), 'text/html; charset=utf-8');
    return;
  }
  if (!IS_GENESIS && p === '/' && m === 'GET') {
    serveFile(res, path.join(__dirname, 'index.html'), 'text/html; charset=utf-8');
    return;
  }

  // --- Template core static files (theme.js, etc.) ---
  if (p.startsWith('/template/core/') && m === 'GET') {
    const safeName = path.basename(p).replace(/\.\./g, '');
    const filePath = path.join(__dirname, safeName);
    const ext = path.extname(filePath).toLowerCase();
    const mimeTypes = { '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json' };
    const ct = mimeTypes[ext] || 'application/octet-stream';
    serveFile(res, filePath, ct);
    return;
  }

  // --- Vendor static files (local JS/CSS libraries) ---
  if (p.startsWith('/vendor/') && m === 'GET') {
    const safePath = p.replace(/\.\./g, '').slice(1); // remove leading /
    const filePath = path.join(__dirname, safePath);
    const ext = path.extname(filePath).toLowerCase();
    const mimeTypes = { '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf' };
    const ct = mimeTypes[ext] || 'application/octet-stream';
    serveFile(res, filePath, ct);
    return;
  }

  // --- Servers API (genesis console only) ---
  if (IS_GENESIS && p === '/api/servers' && m === 'GET') {
    try {
      const deployFile = path.join(SERVER_ROOT, '..', 'deployment.json');
      let deployment = { servers: [] };
      try { deployment = JSON.parse(fs.readFileSync(deployFile, 'utf8')); } catch {}
      // If empty, bootstrap with current server
      if (!deployment.servers.length && SERVER_CONFIG.id) {
        deployment.servers.push({ id: SERVER_CONFIG.id, name: SERVER_CONFIG.name || path.basename(SERVER_ROOT), type: SERVER_CONFIG.type || 'production', path: path.basename(SERVER_ROOT), portBase: SERVER_CONFIG.portBase || 3000, created: SERVER_CONFIG.created || '' });
      }
      // Check each server's status with a quick HTTP probe
      const http = require('node:http');
      const results = await Promise.all(deployment.servers.map(s => new Promise(resolve => {
        const genesisPort = (s.portBase || 3000) + 199;
        const serverDir = path.join(SERVER_ROOT, '..', s.path);
        const exists = fs.existsSync(serverDir);
        if (!exists) { resolve({ ...s, genesisPort, status: 'missing' }); return; }
        const req = http.get(`http://localhost:${genesisPort}/api/lab`, { timeout: 1500 }, res => {
          let body = '';
          res.on('data', d => body += d);
          res.on('end', () => {
            try { const d = JSON.parse(body); resolve({ ...s, genesisPort, status: 'running', labName: d.data?.name }); }
            catch { resolve({ ...s, genesisPort, status: 'running' }); }
          });
        });
        req.on('error', () => resolve({ ...s, genesisPort, status: 'stopped' }));
        req.on('timeout', () => { req.destroy(); resolve({ ...s, genesisPort, status: 'stopped' }); });
      })));
      json(res, { data: results });
    } catch (e) { json(res, { data: [] }); }
    return;
  }

  // --- Server Start/Stop API (genesis console only) ---
  const serverStartMatch = IS_GENESIS && m === 'POST' && p.match(/^\/api\/servers\/([^/]+)\/(start|stop)$/);
  if (serverStartMatch) {
    const serverId = serverStartMatch[1];
    const action = serverStartMatch[2];
    try {
      const deployFile = path.join(SERVER_ROOT, '..', 'deployment.json');
      const deployment = JSON.parse(fs.readFileSync(deployFile, 'utf8'));
      const server = deployment.servers.find(s => s.id === serverId);
      if (!server) { json(res, { error: 'Server not found' }, 404); return; }
      const genesisPort = (server.portBase || 3000) + 199;
      const serverDir = path.join(SERVER_ROOT, '..', server.path);
      const genesisDir = path.join(serverDir, 'genesis');

      if (action === 'stop') {
        const { execSync } = require('node:child_process');
        let killed = 0;
        try {
          const pids = execSync(`lsof -ti:${genesisPort}`, { encoding: 'utf8' }).trim().split('\n');
          for (const pid of pids) { if (pid) { try { process.kill(parseInt(pid), 'SIGTERM'); killed++; } catch {} } }
        } catch {}
        json(res, { ok: true, action: 'stop', killed });
      } else {
        // Check if already running
        const http = require('node:http');
        const alreadyRunning = await new Promise(resolve => {
          const req = http.get(`http://localhost:${genesisPort}/api/lab`, { timeout: 1500 }, () => resolve(true));
          req.on('error', () => resolve(false));
          req.on('timeout', () => { req.destroy(); resolve(false); });
        });
        if (alreadyRunning) { json(res, { ok: true, action: 'start', already: true }); return; }
        // Start the server
        const coreServer = path.join(genesisDir, 'template', 'core', 'server.js');
        if (!fs.existsSync(coreServer)) { json(res, { error: 'Server core not found' }, 404); return; }
        const proc = spawn('node', [coreServer], {
          cwd: genesisDir,
          env: { ...process.env, SERVER_ROOT: serverDir, LAB_IS_GENESIS: '1', LAB_INSTANCE: genesisDir, LAB_PORT: String(genesisPort), GENESIS_DIR: genesisDir, GLOBAL_PLUGINS_DIR: path.join(genesisDir, 'template', 'plugins'), GLOBAL_SKILLS_DIR: path.join(genesisDir, 'template', 'skills') },
          stdio: 'ignore', detached: true
        });
        proc.unref();
        json(res, { ok: true, action: 'start', pid: proc.pid, port: genesisPort });
      }
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  // --- Platforms API (genesis console only) ---
  if (IS_GENESIS && p === '/api/platforms' && m === 'GET') {
    try {
      const platforms = JSON.parse(fs.readFileSync(path.join(INSTANCE_DIR, 'platforms.json'), 'utf8'));
      const result = platforms.map(pl => {
        const pPath = resolvePlatformPath(pl.path);
        let instances = [];
        try {
          const instDir = path.join(pPath, 'instances');
          for (const name of fs.readdirSync(instDir)) {
            const ljPath = path.join(instDir, name, 'lab.json');
            if (fs.existsSync(ljPath)) {
              const cfg = JSON.parse(fs.readFileSync(ljPath, 'utf8'));
              let running = false;
              try { const { execSync } = require('node:child_process'); const pids = execSync(`lsof -ti:${cfg.port}`, { encoding: 'utf8', timeout: 2000 }).trim(); running = pids.length > 0; } catch {}
              instances.push({ id: name, name: cfg.name, port: cfg.port, icon: cfg.icon, color: cfg.color, model: cfg.model, running, hasFrontend: fs.existsSync(path.join(instDir, name, 'frontend', 'server.js')) });
            }
          }
        } catch (e) {}
        return { ...pl, instances };
      });
      json(res, { data: result });
    } catch (e) { json(res, { data: [] }); }
    return;
  }

  if (IS_GENESIS && p === '/api/platforms/create' && m === 'POST') {
    const body = await parseBody(req);
    const { name, description, icon, color } = body;
    if (!name || !name.trim()) { json(res, { error: 'Name is required' }, 400); return; }
    try {
      const scriptPath = path.join(INSTANCE_DIR, 'scripts', 'platform_manager.py');
      const args = description ? `${name} ${description}` : name;
      require('node:child_process').execSync(`python3 "${scriptPath}" create ${args}`, { encoding: 'utf8', cwd: INSTANCE_DIR, env: { ...process.env, LAB_INSTANCE: INSTANCE_DIR } });
      if (icon || color) {
        try {
          const platforms = JSON.parse(fs.readFileSync(path.join(INSTANCE_DIR, 'platforms.json'), 'utf8'));
          const slug = name.toLowerCase().replace(/[^\w\s-]/g, '').replace(/[\s_]+/g, '-').slice(0, 60);
          const plat = platforms.find(pl => pl.id === slug);
          if (plat) { if (icon) plat.icon = icon; if (color) plat.color = color; fs.writeFileSync(path.join(INSTANCE_DIR, 'platforms.json'), JSON.stringify(platforms, null, 2)); }
        } catch {}
      }
      log(`Platform created: ${name}`);
      json(res, { data: { status: 'created', name } });
    } catch (e) { log(`Platform creation failed: ${e.message}`, 'ERROR'); json(res, { error: e.stderr || e.message }, 500); }
    return;
  }

  if (IS_GENESIS) {
    const instCreateMatch = p.match(/^\/api\/platforms\/([^/]+)\/instances\/create$/);
    if (instCreateMatch && m === 'POST') {
      const platformId = instCreateMatch[1];
      const body = await parseBody(req);
      const { name, description } = body;
      if (!name || !name.trim()) { json(res, { error: 'Instance name is required' }, 400); return; }
      try {
        const scriptPath = path.join(INSTANCE_DIR, 'scripts', 'platform_manager.py');
        const args = description ? `${platformId} ${name} ${description}` : `${platformId} ${name}`;
        require('node:child_process').execSync(`python3 "${scriptPath}" create-instance ${args}`, { encoding: 'utf8', cwd: INSTANCE_DIR, env: { ...process.env, LAB_INSTANCE: INSTANCE_DIR } });
        log(`Instance created: ${name} in ${platformId}`);
        json(res, { data: { status: 'created', name, platformId } });
      } catch (e) { log(`Instance creation failed: ${e.message}`, 'ERROR'); json(res, { error: e.stderr || e.message }, 500); }
      return;
    }
  }

  if (IS_GENESIS && p === '/api/restart' && m === 'POST') {
    log('Server restart requested — stopping all children first');
    const killed = killAllChildren();
    log(`Restart: stopped ${killed} child process(es) before respawn`);
    json(res, { data: { status: 'restarting', killed } });
    setTimeout(() => {
      const proc = spawn('node', [__filename], { cwd: INSTANCE_DIR, env: { ...process.env, LAB_INSTANCE: INSTANCE_DIR, LAB_PORT: String(PORT), LAB_IS_GENESIS: '1' }, stdio: 'ignore', detached: true });
      proc.unref();
      process.exit(0);
    }, 500);
    return;
  }

  if (IS_GENESIS && p === '/api/shutdown' && m === 'POST') {
    log('Server shutdown requested — stopping all platforms first');
    const killed = killAllChildren();
    log(`Shutdown: stopped ${killed} child process(es)`);
    json(res, { data: { status: 'shutting_down', killed } });
    setTimeout(() => { process.exit(0); }, 500);
    return;
  }

  if (IS_GENESIS) {
    const platformStartMatch = p.match(/^\/api\/platforms\/([^/]+)\/start$/);
    if (platformStartMatch && m === 'POST') {
      const platformId = platformStartMatch[1];
      try {
        const platforms = JSON.parse(fs.readFileSync(path.join(INSTANCE_DIR, 'platforms.json'), 'utf8'));
        const plat = platforms.find(pl => pl.id === platformId);
        if (!plat) { json(res, { error: 'Platform not found' }, 404); return; }
        log(`Starting platform: ${plat.name} (${platformId})`);
        const platPath = resolvePlatformPath(plat.path);
        platformLog(platPath, `Platform start requested`);
        const instDir = path.join(platPath, 'instances');
        const coreServer = __filename; // use THIS server — the single source of truth
        const started = [];
        for (const name of fs.readdirSync(instDir)) {
          const instPath = path.join(instDir, name);
          const ljPath = path.join(instPath, 'lab.json');
          if (!fs.existsSync(ljPath)) continue;
          try {
            const cfg = JSON.parse(fs.readFileSync(ljPath, 'utf8'));
            let alreadyRunning = false;
            try { const { execSync } = require('node:child_process'); execSync(`lsof -ti:${cfg.port}`, { encoding: 'utf8' }); alreadyRunning = true; } catch {}
            if (alreadyRunning) { started.push({ id: name, port: cfg.port, skipped: true }); continue; }
            const proc = spawn('node', [coreServer], { cwd: instPath, env: { ...process.env, LAB_INSTANCE: instPath, LAB_PORT: String(cfg.port), LAB_IS_GENESIS: '0', GLOBAL_PLUGINS_DIR, GLOBAL_SKILLS_DIR, GENESIS_DIR }, stdio: 'ignore', detached: true });
            proc.unref();
            const fePath = path.join(instPath, 'frontend', 'server.js');
            if (fs.existsSync(fePath)) { const feProc = spawn('node', [fePath], { cwd: instPath, env: { ...process.env, PORT: String(cfg.port + 70) }, stdio: 'ignore', detached: true }); feProc.unref(); }
            platformLog(platPath, `Instance ${name} started on port ${cfg.port}`);
            started.push({ id: name, port: cfg.port });
          } catch (e) { log(`Failed to start instance ${name}: ${e.message}`, 'ERROR'); }
        }
        log(`Platform ${plat.name}: ${started.length} instance(s) started`);
        platformLog(platPath, `Platform start complete — ${started.length} instance(s)`);
        json(res, { data: { status: 'started', instances: started } });
      } catch (e) { log(`Platform start error: ${e.message}`, 'ERROR'); json(res, { error: e.message }, 500); }
      return;
    }
  }

  if (IS_GENESIS) {
    const platformStopMatch = p.match(/^\/api\/platforms\/([^/]+)\/stop$/);
    if (platformStopMatch && m === 'POST') {
      const platformId = platformStopMatch[1];
      try {
        const platforms = JSON.parse(fs.readFileSync(path.join(INSTANCE_DIR, 'platforms.json'), 'utf8'));
        const plat = platforms.find(pl => pl.id === platformId);
        if (!plat) { json(res, { error: 'Platform not found' }, 404); return; }
        log(`Stopping platform: ${plat.name} (${platformId})`);
        const platPath = resolvePlatformPath(plat.path);
        platformLog(platPath, `Platform stop requested`);
        const instDir = path.join(platPath, 'instances');
        let killed = 0;
        try {
          for (const name of fs.readdirSync(instDir)) {
            const ljPath = path.join(instDir, name, 'lab.json');
            if (!fs.existsSync(ljPath)) continue;
            const cfg = JSON.parse(fs.readFileSync(ljPath, 'utf8'));
            if (cfg.port) {
              for (const pt of [cfg.port, cfg.port + 70]) {
                try { const { execSync } = require('node:child_process'); const pids = execSync(`lsof -ti:${pt}`, { encoding: 'utf8' }).trim().split('\n'); for (const pid of pids) { if (pid) { try { process.kill(parseInt(pid), 'SIGKILL'); killed++; } catch {} } } } catch {}
              }
            }
          }
        } catch {}
        const launcherPort = (SERVER_CONFIG.portBase || 3000) + 200;
        try { const { execSync } = require('node:child_process'); const pids = execSync(`lsof -ti:${launcherPort}`, { encoding: 'utf8' }).trim().split('\n'); for (const pid of pids) { if (pid) { try { process.kill(parseInt(pid), 'SIGKILL'); killed++; } catch {} } } } catch {}
        log(`Platform ${plat.name}: stopped (${killed} process(es) killed)`);
        platformLog(platPath, `Platform stop complete — ${killed} process(es) killed`);
        json(res, { data: { status: 'stopped', killed } });
      } catch (e) { log(`Platform stop error: ${e.message}`, 'ERROR'); json(res, { error: e.message }, 500); }
      return;
    }
  }

  if (IS_GENESIS) {
    const instStartMatch = p.match(/^\/api\/platforms\/([^/]+)\/instances\/([^/]+)\/start$/);
    if (instStartMatch && m === 'POST') {
      const [, platformId, instId] = instStartMatch;
      try {
        const platforms = JSON.parse(fs.readFileSync(path.join(INSTANCE_DIR, 'platforms.json'), 'utf8'));
        const plat = platforms.find(pl => pl.id === platformId);
        if (!plat) { json(res, { error: 'Platform not found' }, 404); return; }
        const instPath = path.join(resolvePlatformPath(plat.path), 'instances', instId);
        const ljPath = path.join(instPath, 'lab.json');
        if (!fs.existsSync(ljPath)) { json(res, { error: 'Instance not found' }, 404); return; }
        const cfg = JSON.parse(fs.readFileSync(ljPath, 'utf8'));
        log(`Starting instance: ${instId} (port ${cfg.port}) in ${plat.name}`);
        const proc = spawn('node', [__filename], { cwd: instPath, env: { ...process.env, LAB_INSTANCE: instPath, LAB_PORT: String(cfg.port), LAB_IS_GENESIS: '0', GLOBAL_PLUGINS_DIR, GLOBAL_SKILLS_DIR, GENESIS_DIR }, stdio: 'ignore', detached: true });
        proc.unref();
        const fePath = path.join(instPath, 'frontend', 'server.js');
        if (fs.existsSync(fePath)) { const feProc = spawn('node', [fePath], { cwd: instPath, env: { ...process.env, PORT: String(cfg.port + 70) }, stdio: 'ignore', detached: true }); feProc.unref(); }
        log(`Instance ${instId} started on port ${cfg.port}`);
        json(res, { data: { status: 'started', port: cfg.port } });
      } catch (e) { log(`Instance start error: ${e.message}`, 'ERROR'); json(res, { error: e.message }, 500); }
      return;
    }
  }

  if (IS_GENESIS) {
    const instStopMatch = p.match(/^\/api\/platforms\/([^/]+)\/instances\/([^/]+)\/stop$/);
    if (instStopMatch && m === 'POST') {
      const [, platformId, instId] = instStopMatch;
      try {
        const platforms = JSON.parse(fs.readFileSync(path.join(INSTANCE_DIR, 'platforms.json'), 'utf8'));
        const plat = platforms.find(pl => pl.id === platformId);
        if (!plat) { json(res, { error: 'Platform not found' }, 404); return; }
        const ljPath = path.join(resolvePlatformPath(plat.path), 'instances', instId, 'lab.json');
        if (!fs.existsSync(ljPath)) { json(res, { error: 'Instance not found' }, 404); return; }
        const cfg = JSON.parse(fs.readFileSync(ljPath, 'utf8'));
        log(`Stopping instance: ${instId} (port ${cfg.port}) in ${plat.name}`);
        let killed = 0;
        const { execSync } = require('node:child_process');
        for (const pt of [cfg.port, cfg.port + 70]) {
          try { const pids = execSync(`lsof -ti:${pt}`, { encoding: 'utf8' }).trim().split('\n'); for (const pid of pids) { if (pid) { try { process.kill(parseInt(pid), 'SIGKILL'); killed++; } catch {} } } } catch {}
        }
        log(`Instance ${instId} stopped (${killed} process(es) killed)`);
        json(res, { data: { status: 'stopped', killed } });
      } catch (e) { log(`Instance stop error: ${e.message}`, 'ERROR'); json(res, { error: e.message }, 500); }
      return;
    }
  }

  // --- Lab config ---
  // --- AI status check (cached 60s) ---
  if (p === '/api/ai/status' && m === 'GET') {
    if (!global._aiStatusCache || Date.now() - global._aiStatusCache.ts > 60000) {
      let available = false;
      try {
        const { execSync } = require('node:child_process');
        execSync(`"${CLAUDE_BIN}" --version`, { timeout: 5000, encoding: 'utf8', stdio: 'pipe' });
        available = true;
      } catch {}
      global._aiStatusCache = { available, ts: Date.now() };
    }
    json(res, { data: { available: global._aiStatusCache.available, model: LAB.model || 'opus' } });
    return;
  }

  if (p === '/api/lab' && m === 'GET') {
    const ai = loadAgentIdentity();
    json(res, { data: { name: LAB.name, description: LAB.description, icon: LAB.icon, color: LAB.color, model: LAB.model, root: FILE_ROOT, server: SERVER_CONFIG.name || null, serverType: SERVER_CONFIG.type || null, serverRole: SERVER_CONFIG.role || SERVER_CONFIG.type || null, serverDisplayName: SERVER_CONFIG.displayName || SERVER_CONFIG.name || null, serverIcon: SERVER_CONFIG.icon || null, serverColor: SERVER_CONFIG.color || null, serverDescription: SERVER_CONFIG.description || null, isGenesis: IS_GENESIS, agentName: ai.name || null, agentIcon: ai.icon || null, agentColor: ai.color || null, examplePrompts: LAB.examplePrompts || null, plugins: resolvePlugins().map(p => ({ name: p.name, category: p.category })) } });
    return;
  }

  // --- Sessions ---
  if (p === '/api/sessions' && m === 'GET') {
    const sorted = listSessions().sort((a, b) => new Date(b.lastMessageAt) - new Date(a.lastMessageAt));
    json(res, { data: sorted });
    return;
  }

  if (p === '/api/sessions' && m === 'POST') {
    const body = await parseBody(req);
    json(res, { data: createSession(body.model || 'opus', body.projectId || null) });
    return;
  }

  const sessMatch = p.match(/^\/api\/sessions\/([^/]+)$/);
  if (sessMatch && m === 'DELETE') {
    json(res, { data: { success: deleteSession(sessMatch[1]) } });
    return;
  }

  if (sessMatch && m === 'PATCH') {
    const body = await parseBody(req);
    const updated = updateSession(sessMatch[1], body);
    json(res, { data: updated }, updated ? 200 : 404);
    return;
  }

  // --- Live session monitoring (SSE) ---
  const liveMatch = p.match(/^\/api\/sessions\/([^/]+)\/live$/);
  if (liveMatch && m === 'GET') {
    const sessionId = liveMatch[1];
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
      'Access-Control-Allow-Origin': '*',
    });
    res.write(`data: ${JSON.stringify({ type: 'connected', sessionId })}\n\n`);
    addSessionListener(sessionId, res);
    req.on('close', () => removeSessionListener(sessionId, res));
    return; // Keep connection open
  }

  // --- Messages ---
  const msgMatch = p.match(/^\/api\/sessions\/([^/]+)\/messages$/);
  if (msgMatch && m === 'GET') {
    json(res, { data: getMessages(msgMatch[1]) });
    return;
  }
  if (msgMatch && m === 'POST') {
    // Client-side message sync — used when stream is interrupted (server restart, etc.)
    const sessionId = msgMatch[1];
    const body = await parseBody(req);
    if (body.messages && Array.isArray(body.messages)) {
      fs.writeFileSync(path.join(MESSAGES_DIR, `${sessionId}.json`), JSON.stringify(body.messages));
      log(`Messages synced for session ${sessionId.slice(0, 8)} (${body.messages.length} msgs)`);
      json(res, { data: { synced: body.messages.length } });
    } else {
      json(res, { error: 'Missing messages array' }, 400);
    }
    return;
  }

  // --- Todos (task pane) ---
  const todosMatch = p.match(/^\/api\/sessions\/([^/]+)\/todos$/);
  if (todosMatch && m === 'GET') {
    const session = getSession(todosMatch[1]);
    json(res, { data: session ? (session.todos || []) : [] });
    return;
  }

  // --- Plan for session ---
  const planMatch = p.match(/^\/api\/sessions\/([^/]+)\/plan$/);
  if (planMatch && m === 'GET') {
    const sid = planMatch[1];
    // Check session-level plan first
    const planFile = path.join(ROOT, 'plans', sid + '-plan.md');
    try {
      if (fs.existsSync(planFile)) {
        const content = fs.readFileSync(planFile, 'utf8');
        json(res, { data: { content, path: planFile } });
        return;
      }
      // Check job-level plan (active job for this session)
      const sess = getSession(sid);
      if (sess && sess.projectId) {
        const aj = getActiveJob(sess.projectId, sid);
        if (aj) {
          const jobPlanFile = getJobPlanPath(sess.projectId, aj.id);
          if (fs.existsSync(jobPlanFile)) {
            const content = fs.readFileSync(jobPlanFile, 'utf8');
            json(res, { data: { content, path: jobPlanFile, jobId: aj.id, jobTitle: aj.title } });
            return;
          }
        }
        // Check most recent completed job's plan
        const allJobs = getSessionJobs(sess.projectId, sid);
        for (let i = allJobs.length - 1; i >= 0; i--) {
          const jobPlanFile = getJobPlanPath(sess.projectId, allJobs[i].id);
          if (fs.existsSync(jobPlanFile)) {
            const content = fs.readFileSync(jobPlanFile, 'utf8');
            json(res, { data: { content, path: jobPlanFile, jobId: allJobs[i].id, jobTitle: allJobs[i].title } });
            return;
          }
          // Also check plans/ dir for files starting with job ID prefix (agents sometimes write here)
          const plansDir = path.join(ROOT, 'plans');
          if (fs.existsSync(plansDir)) {
            const prefix = allJobs[i].id.slice(0, 8);
            const match = fs.readdirSync(plansDir).find(f => f.startsWith(prefix) && f.endsWith('.md'));
            if (match) {
              const matchPath = path.join(plansDir, match);
              const content = fs.readFileSync(matchPath, 'utf8');
              json(res, { data: { content, path: matchPath, jobId: allJobs[i].id, jobTitle: allJobs[i].title } });
              return;
            }
          }
        }
      }
      // Final fallback: most recently modified .md in plans/
      const plansDir = path.join(ROOT, 'plans');
      if (fs.existsSync(plansDir)) {
        const planFiles = fs.readdirSync(plansDir).filter(f => f.endsWith('-plan.md') || f.endsWith('.md')).map(f => ({ name: f, mtime: fs.statSync(path.join(plansDir, f)).mtimeMs })).sort((a, b) => b.mtime - a.mtime);
        if (planFiles.length) {
          const latest = path.join(plansDir, planFiles[0].name);
          const content = fs.readFileSync(latest, 'utf8');
          json(res, { data: { content, path: latest } });
          return;
        }
      }
      json(res, { data: null });
    } catch { json(res, { data: null }); }
    return;
  }

  // --- Task file path for session ---
  const taskFileMatch = p.match(/^\/api\/sessions\/([^/]+)\/task-file$/);
  if (taskFileMatch && m === 'GET') {
    const sid = taskFileMatch[1];
    const taskFile = path.join(ROOT, 'tasks', sid + '-tasks.json');
    json(res, { data: { path: taskFile, exists: fs.existsSync(taskFile) } });
    return;
  }

  // --- Settings ---
  if (p === '/api/settings' && m === 'GET') {
    json(res, { data: loadSettings() });
    return;
  }
  if (p === '/api/settings' && m === 'PATCH') {
    const body = await parseBody(req);
    const current = loadSettings();
    if (body.enforcements) current.enforcements = { ...current.enforcements, ...body.enforcements };
    if (body.skills) current.skills = body.skills;
    if (body.circuitBreakerMax != null) current.circuitBreakerMax = body.circuitBreakerMax;
    json(res, { data: saveSettings(current) });
    return;
  }

  // --- Skills ---
  if (p === '/api/skills' && m === 'GET') {
    json(res, { data: getSkills() });
    return;
  }

  const skillMatch = p.match(/^\/api\/sessions\/([^/]+)\/skill$/);
  if (skillMatch && m === 'POST') {
    const sessionId = skillMatch[1];
    const body = await parseBody(req);
    const skillName = body.skill;
    const skillArgs = body.args || '';

    const session = getSession(sessionId);
    if (!session) { json(res, { error: 'Session not found' }, 404); return; }

    const skill = getSkills().find(s => s.command === skillName);
    if (!skill) { json(res, { error: `Unknown skill: ${skillName}. Type /help to see available skills.` }, 400); return; }

    // SSE response
    res.writeHead(200, {
      'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache',
      'Connection': 'keep-alive', 'X-Accel-Buffering': 'no',
    });
    const sse = (data) => res.write(`data: ${JSON.stringify(data)}\n\n`);

    appendMessage(sessionId, { role: 'user', content: `/${skillName}${skillArgs ? ' ' + skillArgs : ''}`, timestamp: new Date().toISOString() });

    sse({ type: 'tool_start', tool: 'Skill', id: skillName });
    sse({ type: 'tool_desc', tool: 'Skill', id: skillName, description: `Running skill: ${skill.name}` });

    // --- Built-in communication skills (no external process needed) ---
    if (skillName === 'send' || skillName === 'inbox' || skillName === 'agents') {
      try {
        let result = '';
        if (skillName === 'send') {
          // Parse: /send <target> <message>  — target can be a name or port
          const parts = (skillArgs || '').match(/^(\S+)\s+(.+)$/s);
          if (!parts) { throw new Error('Usage: /send <agent-name-or-port> <message>'); }
          const target = parts[1];
          const msg = parts[2];
          // Resolve target to port — try as number first, then look up by name in joint agents
          let targetPort = parseInt(target);
          if (isNaN(targetPort)) {
            const agents = jointCmd ? JSON.parse(jointCmd('agents', []).stdout || '[]') : [];
            const found = (Array.isArray(agents) ? agents : []).find(a => a.name && a.name.toLowerCase().includes(target.toLowerCase()));
            if (found) { targetPort = found.port; }
            else { throw new Error(`Agent "${target}" not found. Use /agents to see available agents.`); }
          }
          const sendRes = await fetchJson(`http://localhost:${PORT}/api/agent/send`, {
            method: 'POST', body: { targetPort, message: msg, fromSessionId: sessionId, triggerAgent: true },
          });
          if (sendRes.error) throw new Error(sendRes.error);
          result = `<!--html--><div style="color:#3ac77e;font-size:12px">✓ Message sent to agent on port ${targetPort}</div><div style="font-size:11px;color:#888;margin-top:4px">Session: ${sendRes.data?.targetSession?.slice(0,8) || '?'} · Triggered: ${sendRes.data?.response?.data?.triggered || false}</div>`;
        } else if (skillName === 'inbox') {
          const all = (skillArgs || '').includes('--all');
          const inbox = readInbox();
          const msgs = all ? inbox : inbox.filter(m => !m.delivered);
          if (!msgs.length) { result = '<!--html--><div style="font-size:11px;color:var(--text-muted);padding:8px">No ' + (all ? '' : 'undelivered ') + 'messages</div>'; }
          else {
            result = '<!--html-->' + msgs.map(m => {
              const from = m.sender?.name || 'Unknown';
              const time = m.receivedAt ? new Date(m.receivedAt).toLocaleTimeString() : '';
              const dim = m.delivered ? 'opacity:0.6;' : '';
              return `<div style="${dim}margin-bottom:8px;padding:6px;border-left:2px solid ${m.isReply ? '#3ac77e' : '#4a8fe7'}"><strong>${from}</strong> <span style="font-size:10px;color:#888">${time}${m.delivered ? ' · delivered' : ''}</span><div style="font-size:12px;margin-top:2px">${(m.message || '').slice(0, 300)}</div></div>`;
            }).join('');
          }
        } else if (skillName === 'agents') {
          const agents = await fetchJson(`http://localhost:${PORT}/api/joint/agents`).catch(() => ({ data: [] }));
          const list = agents?.data || [];
          if (!list.length) { result = '<!--html--><div style="font-size:11px;color:var(--text-muted)">No agents discovered</div>'; }
          else {
            result = '<!--html--><table style="font-size:11px;width:100%"><tr style="color:#888"><td>Name</td><td>Port</td><td>Server</td><td>Status</td></tr>' +
              list.map(a => `<tr><td>${a.icon || ''} ${a.name || a.id}</td><td>${a.port}</td><td>${a.server || '?'}</td><td style="color:${a.running !== false ? '#3ac77e' : '#888'}">${a.running !== false ? 'online' : 'offline'}</td></tr>`).join('') + '</table>';
          }
        }
        sse({ type: 'tool_output', id: skillName, output: result });
        appendMessage(sessionId, { role: 'system', content: result, timestamp: new Date().toISOString(), tool: 'Skill', toolId: skillName });
        sse({ type: 'text', content: '' });
        sse({ type: 'done', result, duration: 0, cost: 0 });
      } catch (err) {
        sse({ type: 'error', message: err.message });
        appendMessage(sessionId, { role: 'system', content: `Skill failed: ${err.message}`, timestamp: new Date().toISOString() });
      }
      sse({ type: 'close' });
      res.end();
      return;
    }

    try {
      const cmd = skill.run(skillArgs, INSTANCE_DIR);
      const startTime = Date.now();
      const result = await new Promise((resolve, reject) => {
        const proc = spawn(cmd[0], cmd.slice(1), { cwd: String(WORK_DIR), env: { ...process.env, LAB_INSTANCE: String(INSTANCE_DIR) } });
        let stdout = '', stderr = '';
        proc.stdout.on('data', d => { stdout += d; });
        proc.stderr.on('data', d => { stderr += d; });
        proc.on('close', code => {
          if (code === 0) resolve(stdout);
          else reject(new Error(stderr || `Exit code ${code}`));
        });
      });
      const duration = Date.now() - startTime;
      sse({ type: 'tool_output', id: skillName, output: result.slice(0, 8000) });
      appendMessage(sessionId, { role: 'system', content: result.trim(), timestamp: new Date().toISOString(), tool: 'Skill', toolId: skillName });
      sse({ type: 'text', content: skill.summary ? skill.summary(result) : '' });
      sse({ type: 'done', result: result.trim(), duration, cost: 0 });
      appendMessage(sessionId, { role: 'assistant', content: `Skill \`${skill.name}\` completed.`, timestamp: new Date().toISOString(), duration });

      // Auto-log significant skills to research log
      if (['rebuild', 'analyze'].includes(skillName) || skill.isScript) {
        const logPath = path.join(ROOT, 'kb', 'research-log.json');
        try {
          let entries = []; try { entries = JSON.parse(fs.readFileSync(logPath, 'utf8')); } catch {}
          entries.push({ id: entries.length + 1, date: new Date().toISOString(), type: 'analysis', title: `${skill.name} executed`, description: `Ran /${skillName} ${skillArgs || ''}`.trim(), details: result.slice(0, 500) });
          fs.writeFileSync(logPath, JSON.stringify(entries, null, 2));
        } catch (e) { log(`Auto-log failed: ${e.message}`); }
      }
    } catch (err) {
      sse({ type: 'error', message: err.message });
      appendMessage(sessionId, { role: 'system', content: `Skill failed: ${err.message}`, timestamp: new Date().toISOString() });
    }
    sse({ type: 'close' });
    res.end();
    return;
  }

  // --- Abort streaming ---
  const abortMatch = p.match(/^\/api\/sessions\/([^/]+)\/abort$/);
  if (abortMatch && m === 'POST') {
    const sessionId = abortMatch[1];
    const proc = activeProcs.get(sessionId);
    if (proc) {
      log(`Aborting Claude for session ${sessionId.slice(0, 8)}`);
      // Kill the bash process and its child (claude)
      try { require('node:child_process').execSync(`pkill -KILL -P ${proc.pid}`, { timeout: 3000 }); } catch {}
      try { proc.kill('SIGKILL'); } catch {}
      activeProcs.delete(sessionId);
      json(res, { data: { status: 'aborted' } });
    } else {
      json(res, { data: { status: 'not_running' } });
    }
    return;
  }

  // --- Compact session ---
  const compactMatch = p.match(/^\/api\/sessions\/([^/]+)\/compact$/);
  if (compactMatch && m === 'POST') {
    const sessionId = compactMatch[1];
    const session = getSession(sessionId);
    if (!session) { json(res, { error: 'Session not found' }, 404); return; }
    const messages = getMessages(sessionId);
    // Only summarize non-compacted messages (new content since last compact)
    const activeMsgs = messages.filter(m => !m.compacted && !m.compactMarker);
    const allUserMsgs = activeMsgs.filter(m => m.role === 'user').map(m => m.content);
    const allAssistantMsgs = activeMsgs.filter(m => m.role === 'assistant').map(m => typeof m.content === 'string' ? m.content.slice(0, 800) : '');
    // Include key tool outputs (bash results, agent results) for richer context
    const toolOutputs = activeMsgs
      .filter(m => m.tool === 'output' && m.content && m.content.length < 500)
      .slice(-5)
      .map(m => m.content.slice(0, 200));
    // Build comprehensive compact summary
    const summaryParts = [
      `[SESSION COMPACTED]`,
      `Session: ${session.title} (${session.id.slice(0,8)})`,
      `Date: ${new Date().toISOString().slice(0, 10)}`,
      `Messages before compaction: ${activeMsgs.length} (${allUserMsgs.length} user, ${allAssistantMsgs.length} assistant)`,
      `\nUser messages (full text):\n${allUserMsgs.map(m => `- ${m}`).join('\n').slice(0, 6000)}`,
      `\n---\nAssistant context (last ${Math.min(5, allAssistantMsgs.length)} responses):\n${allAssistantMsgs.slice(-5).join('\n---\n').slice(0, 4000)}`,
    ];
    if (toolOutputs.length) {
      summaryParts.push(`\n---\nKey tool outputs:\n${toolOutputs.join('\n')}`);
    }
    // Include prior compact summaries so context chains across multiple compacts
    const priorCompacts = messages.filter(m => m.compacted && m.role === 'system' && (m.content || '').startsWith('[SESSION COMPACTED]'));
    if (priorCompacts.length) {
      summaryParts.push(`\n---\nPrior session context (${priorCompacts.length} earlier compact(s)):\n${priorCompacts.map(m => m.content).join('\n===\n').slice(0, 3000)}`);
    }
    const summary = summaryParts.join('\n');

    // Reset claudeSessionId to force a fresh Claude session
    updateSession(sessionId, { claudeSessionId: null });
    // Mark all existing messages as compacted (preserved for display, not sent to Claude)
    const compactedMessages = messages.map(m => m.compacted ? m : { ...m, compacted: true });
    // Prepend compaction markers
    compactedMessages.unshift(
      { role: 'system', content: summary, timestamp: new Date().toISOString(), compacted: true },
      { role: 'system', content: `Session compacted at ${new Date().toISOString()}. ${messages.length} messages summarized. Context window reset.`, timestamp: new Date().toISOString(), compactMarker: true },
    );
    fs.writeFileSync(path.join(MESSAGES_DIR, `${sessionId}.json`), JSON.stringify(compactedMessages));
    log(`Session compacted: ${sessionId.slice(0,8)} (${messages.length} messages preserved with compacted flag)`);

    // Also save compact summary to agent persistent memory (survives across sessions)
    try {
      const agentDir = path.join(ROOT, 'agent');
      if (fs.existsSync(agentDir)) {
        const memoryDir = path.join(agentDir, 'memory');
        fs.mkdirSync(memoryDir, { recursive: true });
        const now = new Date();
        const slug = `session_${now.toISOString().slice(0, 10)}_${now.toISOString().slice(11, 19).replace(/:/g, '')}`;
        const memContent = `---\nname: ${session.title || 'Compacted Session'}\ndescription: Compact summary of session ${sessionId.slice(0,8)} (${now.toISOString().slice(0,10)})\ntype: session\n---\n\n${summary}\n`;
        fs.writeFileSync(path.join(memoryDir, `${slug}.md`), memContent);
        // Prune old session files (keep max 10)
        const sessionFiles = fs.readdirSync(memoryDir).filter(f => f.startsWith('session_') && f.endsWith('.md')).sort();
        while (sessionFiles.length > 10) {
          const oldest = sessionFiles.shift();
          try { fs.unlinkSync(path.join(memoryDir, oldest)); } catch {}
        }
        rebuildMemoryIndex();
        _agentMemoryCache = null;
        log(`Compact summary saved to agent memory: ${slug}`);
      }
    } catch (e) { log(`Compact memory save error: ${e.message}`); }

    json(res, { data: { ok: true, summary: true, previousMessageCount: messages.length } });
    return;
  }

  // --- Smart Compact (export KB article + compact + recovery instructions) ---
  const smartCompactMatch = p.match(/^\/api\/sessions\/([^/]+)\/smart-compact$/);
  if (smartCompactMatch && m === 'POST') {
    const sessionId = smartCompactMatch[1];
    const session = getSession(sessionId);
    if (!session) { json(res, { error: 'Session not found' }, 404); return; }
    const body = await parseBody(req);
    const kbFolder = (body.kbFolder || 'analysis').replace(/[^a-zA-Z0-9_-]/g, '-');

    try {
      // Step 1: Export session as KB article
      const messages = getMessages(sessionId);
      if (!messages.length) { json(res, { error: 'No messages to export' }, 400); return; }
      const title = session.title || 'Untitled Session';
      const now = new Date();
      const dateStr = now.toISOString().split('T')[0];
      const timeStr = now.toTimeString().split(' ')[0];

      // Build markdown
      const mdLines = [`# ${title}\n`, `**Session ID**: \`${sessionId}\``, `**Date**: ${dateStr} ${timeStr}`, `**Model**: ${session.model || 'opus'}`, `**Messages**: ${messages.length}`, `**Cost**: $${(session.totalCost || 0).toFixed(2)}`, '', '---', ''];
      for (const msg of messages) {
        const time = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : '';
        if (msg.role === 'user') mdLines.push(`## User (${time})\n\n${msg.content}\n\n---\n`);
        else if (msg.role === 'assistant') mdLines.push(`## Assistant (${time})\n\n${msg.content}\n\n---\n`);
        else if (msg.role === 'thinking') mdLines.push(`> **Reasoning**: ${msg.content.slice(0, 500)}${msg.content.length > 500 ? '...' : ''}\n`);
        else if (msg.tool === 'output') mdLines.push(`\`\`\`\n${msg.content.slice(0, 2000)}\n\`\`\`\n`);
        else if (msg.tool) mdLines.push(`> **${msg.tool}**: ${msg.content}\n`);
      }
      const mdContent = mdLines.join('\n');

      // Generate metadata and save KB article
      const meta = generateMetadata(session, messages);
      const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50);
      let filename = `${dateStr}-${slug}.md`;
      const kbDir = path.join(ROOT, 'kb', kbFolder);
      fs.mkdirSync(kbDir, { recursive: true });
      let version = 1;
      const baseName = `${dateStr}-${slug}`;
      if (fs.existsSync(path.join(kbDir, filename))) {
        version = 2;
        while (fs.existsSync(path.join(kbDir, `${baseName}-v${version}.md`))) version++;
        filename = `${baseName}-v${version}.md`;
      }
      const article = `---\ntitle: "${meta.title || title}"\ndate: ${dateStr}\nsession_id: ${sessionId}\ntags: [${meta.tags || ''}]\nsummary: "${(meta.summary || '').replace(/"/g, '\\"')}"\nexport_version: ${version}\n---\n\n${mdContent}`;
      const kbArticlePath = path.join(ROOT, 'kb', kbFolder, filename);
      fs.writeFileSync(kbArticlePath, article);
      auditLog('smart_compact_export', { sessionId, filename, version, folder: kbFolder });
      log(`Smart compact: KB article exported to kb/${kbFolder}/${filename}`);

      // Step 2: Compact the session (reuse existing compact logic)
      const activeMsgs = messages.filter(m => !m.compacted && !m.compactMarker);
      const allUserMsgs = activeMsgs.filter(m => m.role === 'user').map(m => m.content);
      const allAssistantMsgs = activeMsgs.filter(m => m.role === 'assistant').map(m => typeof m.content === 'string' ? m.content.slice(0, 800) : '');
      const toolOutputs = activeMsgs
        .filter(m => m.tool === 'output' && m.content && m.content.length < 500)
        .slice(-5)
        .map(m => m.content.slice(0, 200));
      const summaryParts = [
        `[SESSION COMPACTED]`,
        `Session: ${title} (${sessionId.slice(0,8)})`,
        `Date: ${dateStr}`,
        `Messages before compaction: ${activeMsgs.length} (${allUserMsgs.length} user, ${allAssistantMsgs.length} assistant)`,
        `KB Article: ${kbArticlePath}`,
        `\nUser messages (full text):\n${allUserMsgs.map(m => `- ${m}`).join('\n').slice(0, 6000)}`,
        `\n---\nAssistant context (last ${Math.min(5, allAssistantMsgs.length)} responses):\n${allAssistantMsgs.slice(-5).join('\n---\n').slice(0, 4000)}`,
      ];
      if (toolOutputs.length) {
        summaryParts.push(`\n---\nKey tool outputs:\n${toolOutputs.join('\n')}`);
      }
      const priorCompacts = messages.filter(m => m.compacted && m.role === 'system' && (m.content || '').startsWith('[SESSION COMPACTED]'));
      if (priorCompacts.length) {
        summaryParts.push(`\n---\nPrior session context (${priorCompacts.length} earlier compact(s)):\n${priorCompacts.map(m => m.content).join('\n===\n').slice(0, 3000)}`);
      }
      const summary = summaryParts.join('\n');

      updateSession(sessionId, { claudeSessionId: null });
      const compactedMessages = messages.map(m => m.compacted ? m : { ...m, compacted: true });
      compactedMessages.unshift(
        { role: 'system', content: summary, timestamp: now.toISOString(), compacted: true },
        { role: 'system', content: `Session compacted at ${now.toISOString()}. ${messages.length} messages summarized. KB article saved to kb/${kbFolder}/${filename}`, timestamp: now.toISOString(), compactMarker: true },
      );
      fs.writeFileSync(path.join(MESSAGES_DIR, `${sessionId}.json`), JSON.stringify(compactedMessages));
      log(`Smart compact: session compacted (${messages.length} messages preserved)`);

      // Save to agent memory
      try {
        const agentDir = path.join(ROOT, 'agent');
        if (fs.existsSync(agentDir)) {
          const memoryDir = path.join(agentDir, 'memory');
          fs.mkdirSync(memoryDir, { recursive: true });
          const memSlug = `session_${now.toISOString().slice(0, 10)}_${now.toISOString().slice(11, 19).replace(/:/g, '')}`;
          const memContent = `---\nname: ${title}\ndescription: Compact summary of session ${sessionId.slice(0,8)} (${dateStr}). KB article: ${kbArticlePath}\ntype: session\n---\n\n${summary}\n`;
          fs.writeFileSync(path.join(memoryDir, `${memSlug}.md`), memContent);
          const sessionFiles = fs.readdirSync(memoryDir).filter(f => f.startsWith('session_') && f.endsWith('.md')).sort();
          while (sessionFiles.length > 10) {
            const oldest = sessionFiles.shift();
            try { fs.unlinkSync(path.join(memoryDir, oldest)); } catch {}
          }
          rebuildMemoryIndex();
          _agentMemoryCache = null;
        }
      } catch (e) { log(`Smart compact memory save error: ${e.message}`); }

      json(res, { data: { ok: true, kbArticlePath, kbFolder, filename, version, previousMessageCount: messages.length } });
    } catch (err) {
      log(`Smart compact error: ${err.message}`);
      json(res, { error: `Smart compact failed: ${err.message}` }, 500);
    }
    return;
  }

  // --- Deploy Guard hook endpoint (blocks manual cp/rsync to server template dirs) ---
  if (p === '/api/hooks/deploy-guard' && m === 'POST') {
    const settings = loadSettings();
    if (!settings.enforcements['deploy-guard']) {
      json(res, {}); return;
    }
    const body = await parseBody(req);
    const toolName = body.tool_name || '';
    const toolInput = body.tool_input || {};

    // --- Guard 1: Block Edit/Write to deployed (non-template) server files ---
    if (toolName === 'Edit' || toolName === 'Write') {
      const filePath = toolInput.file_path || '';
      // Block edits to server.js, index.html, theme.js in non-template locations across any SERVER
      const deployedFilePat = /SERVER\d+-[A-Z-]+\/genesis\/((?!template)[^/]+|instances\/)/i;
      const coreFilePat = /\/(server\.js|index\.html|theme\.js)$/;
      if (deployedFilePat.test(filePath) && coreFilePat.test(filePath)) {
        json(res, {
          hookSpecificOutput: {
            hookEventName: 'PreToolUse',
            permissionDecision: 'deny',
            permissionDecisionReason: `DEPLOY GUARD: Do NOT edit deployed instance code (${filePath.split('/').slice(-2).join('/')}). Edit genesis/template/core/ instead.`,
          },
        });
        return;
      }
    }

    // For remaining guards, only check Bash commands
    if (toolName !== 'Bash') { json(res, {}); return; }

    const cmd = toolInput.command || '';

    // --- Guard 2: Block manual cp/rsync/mv to server template directories ---
    const serverTemplatePat = /\b(cp|rsync|mv)\b.*\/Volumes\/T9[^"']*SERVER[^"']*\/(genesis\/template|\.claude\/rules)/i;
    if (serverTemplatePat.test(cmd)) {
      // Allow if it's within the SAME server (not cross-server)
      const serverMentions = (cmd.match(/SERVER\d+-[A-Z-]+/gi) || []);
      const uniqueServers = [...new Set(serverMentions.map(s => s.toUpperCase()))];
      if (uniqueServers.length > 1) {
        json(res, {
          hookSpecificOutput: {
            hookEventName: 'PreToolUse',
            permissionDecision: 'deny',
            permissionDecisionReason: `DEPLOY GUARD: Do NOT manually copy between servers. Use: python3 scripts/deploy_manager.py deploy --source SERVER2-DEV --target TARGET_SERVER --dry-run`,
          },
        });
        return;
      }
    }

    // --- Guard 3: Require --dry-run before real deploy ---
    const deployPat = /deploy_manager\.py\s+deploy\b/;
    if (deployPat.test(cmd) && !/dry.?run/.test(cmd)) {
      json(res, {
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          additionalContext: `DEPLOY SAFETY: Always run --dry-run first to preview changes before deploying.\n\npython3 scripts/deploy_manager.py deploy --source X --target Y --dry-run\n\nReview the diff, then run without --dry-run to apply.`,
        }
      });
      return; // warn but allow — response already sent
    }

    // --- Guard 4: Warn on mass kill ---
    const massKillPat = /\bfor\b.*\b(3199|4199|5199|6199|7199|8199|9199|10199)\b.*\b(kill|xargs\s+kill)\b|\bfor\b.*\b(kill|xargs\s+kill)\b.*\b(3199|4199|5199|6199|7199|8199|9199|10199)\b/i;
    if (massKillPat.test(cmd)) {
      json(res, {
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          additionalContext: `WARNING: Mass kill detected — this will stop multiple server processes. Make sure you have a restart plan ready for ALL 12 processes (8 genesis + 4 lab instances).`,
        }
      });
      return; // warn but allow — response already sent
    }

    // --- Guard 5: Block lab instances without LAB_IS_GENESIS=0 ---
    const labStartPat = /LAB_INSTANCE=.*instances\//i;
    if (labStartPat.test(cmd) && !cmd.includes('LAB_IS_GENESIS=0')) {
      json(res, {
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          additionalContext: `DEPLOY GUARD BLOCK: Starting a lab instance without LAB_IS_GENESIS=0. Lab instances MUST have LAB_IS_GENESIS=0 explicitly set, otherwise it leaks from the parent shell and the root "/" route will fail. Add LAB_IS_GENESIS=0 to your command.`,
        }
      });
      return;
    }

    json(res, {}); // allow
    return;
  }

  // --- Restart completeness hook (ensures all processes are restarted after deploy) ---
  if (p === '/api/hooks/restart-check' && m === 'POST') {
    const settings = loadSettings();
    if (!settings.enforcements['deploy-guard']) {
      json(res, {}); return;
    }
    const body = await parseBody(req);
    const toolName = body.tool_name || '';
    const toolInput = body.tool_input || {};

    // After a deploy command, check that a restart follows
    if (toolName === 'Bash') {
      const cmd = toolInput.command || '';
      // If running deploy_manager.py deploy (not dry-run), remind about restart
      if (/deploy_manager\.py\s+deploy\b/.test(cmd) && !/dry.?run/.test(cmd)) {
        json(res, {
          hookSpecificOutput: {
            hookEventName: 'PreToolUse',
            additionalContext: `RESTART REMINDER: After this deploy completes, you MUST restart ALL 12 server processes:\n- 8 genesis consoles: ports 3199, 4199, 5199, 6199, 7199, 8199, 9199, 10199 (LAB_IS_GENESIS=1)\n- 4 lab instances: ports 5212 (SAPC), 6212 (SAPC-DEV), 9210 (AeroCore), 9211 (AeroCore-Ads) (LAB_IS_GENESIS=0)\nThen verify EVERY port returns HTTP 200 for /, /ide, and /template/core/theme.js`,
          }
        });
        // Still allow the command — this is a reminder, not a block
      }
    }

    json(res, {}); return;
  }

  // --- Job discipline hook endpoint (HTTP hook for Claude Code) ---
  // Enforces strict pipeline: 1. Create Job → 2. Write Plan → 3. Create Tasks → 4. Execute
  if (p === '/api/hooks/job-discipline' && m === 'POST') {
    const settings = loadSettings();
    if (!settings.enforcements['job-discipline']) {
      json(res, {}); return;
    }
    const body = await parseBody(req);
    const toolName = body.tool_name || '';
    const toolInput = body.tool_input || {};
    const sessionId = body.session_id || '';

    log(`[JOB-HOOK] tool=${toolName} session=${sessionId ? sessionId.slice(0,8) : 'NONE'} input_keys=${Object.keys(toolInput).join(',') || 'NONE'}`);

    // Always allow these meta-tools
    if (['ToolSearch', 'AskUserQuestion'].includes(toolName)) {
      json(res, {}); return;
    }

    // Find the session
    let session = null;
    const allSessions = readSessions();
    for (const s of allSessions) {
      if (s.claudeSessionId === sessionId || s.id === sessionId) {
        session = s;
        break;
      }
    }

    // If session doesn't belong to a project, skip enforcement
    if (!session || !session.projectId) {
      log(`[JOB-HOOK] SKIP: session=${session ? 'found' : 'NOT FOUND'} projectId=${session?.projectId || 'NONE'}`);
      json(res, {}); return;
    }

    const projectId = session.projectId;
    const activeJob = getActiveJob(projectId, session.id);
    const jobPlanPathCheck = activeJob ? getJobPlanPath(projectId, activeJob.id) : 'N/A';
    const hasPlanCheck = activeJob ? fs.existsSync(jobPlanPathCheck) : false;
    const hasTodosCheck = Array.isArray(session.todos) && session.todos.length > 0;
    log(`[JOB-HOOK] EVAL: job=${activeJob ? activeJob.id.slice(0,8) : 'NONE'} plan=${hasPlanCheck} todos=${hasTodosCheck} tool=${toolName}`);

    // --- STAGE 1: No job exists → agent must create one via Bash curl ---
    if (!activeJob) {
      // Allow TodoWrite so agent can set up tracking
      if (toolName === 'TodoWrite') { json(res, {}); return; }
      // Allow Bash ONLY if it's a curl to create a job
      if (toolName === 'Bash' && toolInput.command) {
        const cmd = toolInput.command;
        if (cmd.includes('/api/sessions/') && cmd.includes('/jobs') && cmd.includes('POST')) {
          log(`[JOB-HOOK] ALLOW: Stage 1 — job creation curl`);
          json(res, {}); return;
        }
        // Also allow curl to close/update jobs
        if (cmd.includes('/api/projects/') && cmd.includes('/jobs/') && cmd.includes('PATCH')) {
          json(res, {}); return;
        }
      }
      // Allow Read/Grep/Glob for research
      if (['Read', 'Grep', 'Glob'].includes(toolName)) { json(res, {}); return; }

      log(`[JOB-HOOK] DENY: Stage 1 — no job, tool=${toolName}`);
      json(res, {
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'deny',
          permissionDecisionReason: `JOB DISCIPLINE — No active job. Create one first using: curl -s http://localhost:${PORT}/api/sessions/${session.id}/jobs -X POST -H "Content-Type: application/json" -d '{"title":"DESCRIPTIVE TITLE"}'`,
        },
        systemMessage: `BLOCKED: No active job exists for this session. You MUST create a job first by running: curl -s http://localhost:${PORT}/api/sessions/${session.id}/jobs -X POST -H "Content-Type: application/json" -d '{"title":"TITLE"}'`,
      });
      return;
    }

    // Job exists — check pipeline stages
    const jobPlanPath = getJobPlanPath(projectId, activeJob.id);
    const hasPlan = fs.existsSync(jobPlanPath);
    const hasTodos = Array.isArray(session.todos) && session.todos.length > 0;

    // Always allow Bash curl for job management (close/update jobs)
    if (toolName === 'Bash' && toolInput.command) {
      const cmd = toolInput.command;
      if ((cmd.includes('/api/projects/') || cmd.includes('/api/sessions/')) && cmd.includes('/jobs') && (cmd.includes('PATCH') || cmd.includes('POST'))) {
        json(res, {}); return;
      }
    }

    // --- STAGE 2: Job exists but no plan → write plan first ---
    if (!hasPlan) {
      // Allow TodoWrite always
      if (toolName === 'TodoWrite') { json(res, {}); return; }
      // Allow Write/Edit ONLY if targeting the job plan file
      if ((toolName === 'Write' || toolName === 'Edit') && toolInput.file_path) {
        if (toolInput.file_path === jobPlanPath || (toolInput.file_path.includes('/jobs/') && toolInput.file_path.endsWith('-plan.md'))) {
          json(res, {}); return;
        }
      }
      // Allow Read/Grep/Glob for research before writing plan
      if (['Read', 'Grep', 'Glob'].includes(toolName)) { json(res, {}); return; }

      log(`[JOB-HOOK] DENY: Stage 2 — no plan, tool=${toolName}`);
      json(res, {
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'deny',
          permissionDecisionReason: `JOB DISCIPLINE — No plan. Write plan to: ${jobPlanPath}`,
        },
        systemMessage: `BLOCKED: Job "${activeJob.title}" has no plan. Write your plan to: ${jobPlanPath} — include phases with micro-steps (1.1, 1.2, etc.)`,
      });
      return;
    }

    // --- STAGE 3: Job + Plan exist but no tasks → create tasks first ---
    if (!hasTodos) {
      // Allow TodoWrite (this is what we WANT them to do)
      if (toolName === 'TodoWrite') { json(res, {}); return; }
      // Allow editing the plan
      if ((toolName === 'Write' || toolName === 'Edit') && toolInput.file_path === jobPlanPath) {
        json(res, {}); return;
      }
      // Allow Read for context
      if (['Read', 'Grep', 'Glob'].includes(toolName)) { json(res, {}); return; }

      log(`[JOB-HOOK] DENY: Stage 3 — no tasks, tool=${toolName}`);
      json(res, {
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'deny',
          permissionDecisionReason: `JOB DISCIPLINE — Plan exists but no tasks. Use TodoWrite to create tasks from your plan.`,
        },
        systemMessage: `BLOCKED: Job "${activeJob.title}" has a plan but no tasks. Call TodoWrite to create tasks from each micro-step before working.`,
      });
      return;
    }

    // --- STAGE 4: Job + Plan + Tasks all exist → allow everything ---
    json(res, {}); return;
  }

  // --- Task discipline hook endpoint (HTTP hook for Claude Code) ---
  if (p === '/api/hooks/task-discipline' && m === 'POST') {
    const settings = loadSettings();
    if (!settings.enforcements['task-discipline']) {
      json(res, {}); // no enforcement, pass through
      return;
    }
    const body = await parseBody(req);
    const toolName = body.tool_name || '';
    const toolInput = body.tool_input || {};
    const sessionId = body.session_id || '';

    // If tool is TodoWrite or ToolSearch, always allow
    if (toolName === 'TodoWrite' || toolName === 'ToolSearch') {
      json(res, {}); return;
    }

    // Allow Bash curls to job management APIs — must be checked FIRST before any deny
    if (toolName === 'Bash' && toolInput.command) {
      const cmd = toolInput.command;
      if ((cmd.includes('/api/sessions/') || cmd.includes('/api/projects/')) && cmd.includes('/jobs') && (cmd.includes('POST') || cmd.includes('PATCH'))) {
        json(res, {}); return;
      }
    }

    // If job-discipline is also active AND session is in a project, defer to job-discipline
    if (settings.enforcements['job-discipline']) {
      let sessionInProject = false;
      const allSessionsJD = readSessions();
      for (const s of allSessionsJD) {
        if (s.claudeSessionId === sessionId || s.id === sessionId) {
          sessionInProject = !!s.projectId;
          break;
        }
      }
      if (sessionInProject) {
        json(res, {}); return; // job-discipline handles full pipeline
      }
    }

    // Check if this session has any todos defined
    let hasTodos = false;
    const allSessions = readSessions();
    for (const s of allSessions) {
      if (s.claudeSessionId === sessionId || s.id === sessionId) {
        hasTodos = Array.isArray(s.todos) && s.todos.length > 0;
        break;
      }
    }

    if (!hasTodos) {
      json(res, {
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'deny',
          permissionDecisionReason: `TASK DISCIPLINE: You called ${toolName} without tasks. Call TodoWrite first.`,
        },
        systemMessage: `BLOCKED: You must call TodoWrite to define tasks before using ${toolName}. Create at least one task now.`,
      });
      return;
    }

    json(res, {}); // has todos, allow
    return;
  }

  // --- Inbox check hook — surfaces undelivered messages between tool calls ---
  if (p === '/api/hooks/check-inbox' && m === 'POST') {
    const undelivered = getUndeliveredInbox();
    if (!undelivered.length) { json(res, {}); return; }

    // Build a system message with all pending inbox messages
    const urgentMsgs = undelivered.filter(m => m.priority === 'urgent');
    const normalMsgs = undelivered.filter(m => m.priority !== 'urgent');

    const lines = ['[INBOX — You have incoming messages from other agents]', ''];
    if (urgentMsgs.length) {
      lines.push('🔴 URGENT:');
      for (const msg of urgentMsgs) {
        const from = msg.sender?.name || 'Unknown';
        lines.push(`  From ${from}: ${msg.message}`);
      }
      lines.push('');
    }
    if (normalMsgs.length) {
      lines.push('Messages:');
      for (const msg of normalMsgs) {
        const from = msg.sender?.name || 'Unknown';
        lines.push(`  From ${from}: ${msg.message}`);
      }
      lines.push('');
    }
    lines.push('Respond to urgent messages immediately. Normal messages can wait until your current task is done.');
    lines.push(`To reply, use: curl -s http://localhost:${PORT}/api/agent/send -X POST -H "Content-Type: application/json" -d '{"targetPort":SENDER_PORT,"message":"YOUR REPLY"}'`);

    // Mark as delivered
    markInboxDelivered(undelivered.map(m => m.id));

    // Don't block — just inject context
    json(res, {
      systemMessage: lines.join('\n'),
    });
    return;
  }

  // --- Chat (SSE) ---
  const chatMatch = p.match(/^\/api\/sessions\/([^/]+)\/chat$/);
  if (chatMatch && m === 'POST') {
    const sessionId = chatMatch[1];
    const body = await parseBody(req);
    const message = body.message;
    const viewerContext = body.viewerContext || null;

    if (!message) { json(res, { error: 'Missing message' }, 400); return; }
    const session = getSession(sessionId);
    if (!session) { json(res, { error: 'Session not found' }, 404); return; }

    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
      'Access-Control-Allow-Origin': '*',
    });

    const sse = (data) => res.write(`data: ${JSON.stringify(data)}\n\n`);

    // SSE keepalive — prevent browser timeout during long AI thinking
    const keepalive = setInterval(() => {
      try { res.write(`: keepalive\n\n`); } catch {}
    }, 5000);

    const startTime = Date.now();
    const isFirst = session.messageCount === 0;

    appendMessage(sessionId, { role: 'user', content: message, timestamp: new Date().toISOString() });

    const vcBlock = buildViewerContext(viewerContext);
    const context = buildDataContext(message);
    // If this is the first message after a compact, include compact summaries so Claude has prior context
    let compactContext = '';
    if (!session.claudeSessionId) {
      const allMsgs = getMessages(sessionId);
      // Collect the MOST RECENT compact summary (which already chains prior compacts within it)
      const compactSummaries = allMsgs.filter(m => m.compacted && m.role === 'system' && (m.content || '').startsWith('[SESSION COMPACTED]'));
      if (compactSummaries.length) {
        // Use the most recent one — it already contains prior compact summaries chained inside it
        const latest = compactSummaries[0];
        // Check if summary includes a KB Article path for enhanced recovery
        const kbMatch = (latest.content || '').match(/KB Article:\s*(.+)/);
        const kbRecovery = kbMatch ? `\n\n[KB RECOVERY]\nThe full conversation was exported to: ${kbMatch[1].trim()}\nRead this file from the bottom up (last 200 lines first) to recover your complete working memory. Resume work seamlessly as if the compaction never happened.\n[END KB RECOVERY]` : '';
        compactContext = `[PRIOR SESSION CONTEXT]\nThis session was compacted. The user may reference things from earlier in the conversation. Here is a comprehensive summary of everything discussed:\n\n${latest.content}${kbRecovery}\n[END PRIOR CONTEXT]\n\n`;
      }
    }
    const enriched = `${compactContext}${vcBlock ? vcBlock + '\n\n' : ''}${context}\n\n---\n\nUser question: ${message}`;

    try {
      await sendToClaudeStream(sessionId, enriched, event => {
        try {
          if (event.type === 'system' && event.subtype === 'init') {
            const ev = { type: 'init', sessionId: event.session_id, model: event.model };
            sse(ev); sessionBroadcast(sessionId, { type: 'stream', event: ev });
          } else if (event.type === 'assistant' && event.content) {
            for (const block of event.content) {
              if (block.type === 'thinking') {
                const ev = { type: 'thinking', content: block.thinking };
                sse(ev); sessionBroadcast(sessionId, { type: 'stream', event: ev });
              } else if (block.type === 'text') {
                const ev = { type: 'text', content: block.text };
                sse(ev); sessionBroadcast(sessionId, { type: 'stream', event: ev });
              } else if (block.type === 'tool_start') {
                const ev = { type: 'tool_start', tool: block.tool, id: block.id };
                sse(ev); sessionBroadcast(sessionId, { type: 'stream', event: ev });
              } else if (block.type === 'tool_description') {
                const ev = { type: 'tool_desc', tool: block.tool, id: block.id, description: block.description };
                sse(ev); sessionBroadcast(sessionId, { type: 'stream', event: ev });
              } else if (block.type === 'tool_result') {
                const ev = { type: 'tool_output', id: block.tool_use_id, output: block.content };
                sse(ev); sessionBroadcast(sessionId, { type: 'stream', event: ev });
              } else if (block.type === 'todos_update') {
                const ev = { type: 'todos', todos: block.todos };
                sse(ev); sessionBroadcast(sessionId, { type: 'stream', event: ev });
              } else if (block.type === 'plan_update') {
                const ev = { type: 'plan', content: block.content, path: block.path };
                sse(ev); sessionBroadcast(sessionId, { type: 'stream', event: ev });
              } else if (block.type === 'file_changed') {
                const ev = { type: 'file_changed', path: block.path };
                sse(ev); sessionBroadcast(sessionId, { type: 'stream', event: ev });
              }
            }
          } else if (event.type === 'result') {
            const duration = Date.now() - startTime;
            const usage = event.usage || {};
            // Handle context overflow — send error event instead of done
            if (event._contextOverflow) {
              sse({ type: 'error', message: 'CONTEXT_OVERFLOW: The conversation has exceeded the context window. Use /compact to summarize and reset the context.' });
              sessionBroadcast(sessionId, { type: 'stream', event: { type: 'error', message: 'CONTEXT_OVERFLOW' } });
            } else {
            const doneEv = {
              type: 'done', result: event.result, sessionId: event.session_id,
              duration, cost: event.total_cost_usd, num_turns: event.num_turns,
              usage: { input: usage.input_tokens, output: usage.output_tokens, cached: usage.cache_read_input_tokens },
            };
            sse(doneEv);
            sessionBroadcast(sessionId, { type: 'stream', event: doneEv });
            // Update the already-saved assistant message with duration/cost metadata
            // (assistant event in sendToClaudeStream already saved the text)
            if (event.result) {
              const msgs = getMessages(sessionId);
              // Find last assistant message without duration (saved by assistant event, needs metadata)
              const lastIdx = msgs.length - 1;
              const last = lastIdx >= 0 ? msgs[lastIdx] : null;
              if (last && last.role === 'assistant' && last.duration == null) {
                // Update with result text + metadata (result text is authoritative)
                last.content = event.result;
                last.duration = duration;
                last.cost = event.total_cost_usd;
                fs.writeFileSync(path.join(MESSAGES_DIR, `${sessionId}.json`), JSON.stringify(msgs));
              } else if (!last || last.role !== 'assistant') {
                // Fallback: no prior assistant save, create new
                appendMessage(sessionId, {
                  role: 'assistant', content: event.result,
                  timestamp: new Date().toISOString(), duration, cost: event.total_cost_usd,
                });
              }
              // else: last assistant already has duration (somehow saved twice) — skip
            }
            } // end else (non-overflow result)
          }
        } catch (e) { log(`SSE event error: ${e.message}`); }
      });

      const updates = { messageCount: session.messageCount + 1, lastMessageAt: new Date().toISOString() };
      if (isFirst) updates.title = message;
      updateSession(sessionId, updates);
    } catch (err) {
      log(`Chat error: ${err.message}`);
      sse({ type: 'error', message: err.message });
    }

    clearInterval(keepalive);
    sse({ type: 'close' });
    res.end();
    return;
  }

  // --- File browser ---
  if (p === '/api/files/fingerprint' && m === 'GET') {
    // Lightweight check — returns a hash so the client only refreshes when files change
    let hash = 0;
    const walk = (d) => { try { for (const e of fs.readdirSync(d, { withFileTypes: true })) { if (e.name.startsWith('.') || SKIP_DIRS.has(e.name)) continue; const fp = path.join(d, e.name); if (e.isDirectory()) walk(fp); else { const s = fs.statSync(fp); hash = ((hash << 5) - hash + s.mtimeMs) | 0; } } } catch (e) {} };
    walk(ROOT);
    json(res, { data: hash });
    return;
  }

  if (p === '/api/files' && m === 'GET') {
    json(res, { data: listBrowseableFiles() });
    return;
  }

  // File upload — saves to data/uploads/
  if (p === '/api/upload' && m === 'POST') {
    // Optional ?dir= param to upload into a specific directory
    const targetDir = url.searchParams.get('dir');
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => {
      try {
        const body = Buffer.concat(chunks);
        const boundary = req.headers['content-type']?.split('boundary=')[1];
        if (!boundary) { json(res, { error: 'Missing multipart boundary' }, 400); return; }
        const parts = body.toString('binary').split('--' + boundary).filter(p => p.includes('filename='));
        if (!parts.length) { json(res, { error: 'No file in upload' }, 400); return; }
        const results = [];
        for (const part of parts) {
          const filenameMatch = part.match(/filename="([^"]+)"/);
          if (!filenameMatch) continue;
          const filename = filenameMatch[1].replace(/[^a-zA-Z0-9._\-]/g, '_');
          const headerEnd = part.indexOf('\r\n\r\n');
          const fileData = part.slice(headerEnd + 4).replace(/\r\n$/, '');
          // Determine destination directory
          let relDir = 'data/uploads';
          if (targetDir && !targetDir.includes('..')) relDir = targetDir;
          const destDir = path.join(ROOT, relDir);
          fs.mkdirSync(destDir, { recursive: true });
          const dest = path.join(destDir, filename);
          fs.writeFileSync(dest, fileData, 'binary');
          const relPath = `${relDir}/${filename}`;
          auditLog('file_upload', { filename, size: fileData.length, dest: relPath });
          log(`File uploaded: ${relPath} (${fileData.length} bytes)`);
          results.push({ filename, path: relPath, size: fileData.length });
        }
        json(res, { data: results.length === 1 ? results[0] : results });
      } catch (e) {
        log(`Upload error: ${e.message}`);
        json(res, { error: e.message }, 500);
      }
    });
    return;
  }

  if (p === '/api/file' && m === 'GET') {
    const filePath = url.searchParams.get('path');
    if (!filePath) { json(res, { error: 'Missing path' }, 400); return; }
    const content = getFileContent(filePath);
    if (!content) { json(res, { error: 'File not found' }, 404); return; }
    json(res, { data: content });
    return;
  }

  // ─── File system operations ───────────────────────────────────────────

  // --- Database API (SQLite-backed, multi-database) ---
  const DEFAULT_USER_DB = path.join(FILE_ROOT, 'output', 'spreadsheet.db');
  const DATABASE_MANAGER_PY = path.join(__dirname, 'database_manager.py');
  const OUTPUT_DIR_SS = path.join(FILE_ROOT, 'output');

  // Resolve database path from ?db= parameter (defaults to user database)
  function resolveDbPath(urlObj) {
    const dbParam = urlObj.searchParams.get('db');
    if (!dbParam) return DEFAULT_USER_DB;
    // Support project database paths: projects/{projectId}/project.db
    if (dbParam.startsWith('projects/') && dbParam.endsWith('/project.db')) {
      const projId = dbParam.split('/')[1];
      if (projId && /^[0-9a-f-]+$/i.test(projId)) {
        const projDbPath = path.join(PROJECTS_DIR, projId, 'project.db');
        if (fs.existsSync(projDbPath)) return projDbPath;
      }
    }
    // Security: only allow .db files in the output directory, no path traversal
    const sanitized = path.basename(dbParam);
    if (!sanitized.endsWith('.db')) return DEFAULT_USER_DB;
    const fullPath = path.join(OUTPUT_DIR_SS, sanitized);
    return fs.existsSync(fullPath) ? fullPath : DEFAULT_USER_DB;
  }

  // Check if a database is read-only (only jubilee.db is read-only — it's pipeline-generated)
  function isReadOnlyDb(dbPath) {
    return path.basename(dbPath) === 'jubilee.db';
  }

  // Discover all SQLite databases in output/
  if (p === '/api/database/databases' && m === 'GET') {
    try {
      const databases = [];
      // 1. Scan output/ for .db files (existing behavior)
      const files = fs.readdirSync(OUTPUT_DIR_SS).filter(f => f.endsWith('.db') && !f.endsWith('-shm') && !f.endsWith('-wal'));
      for (const file of files) {
        const dbPath = path.join(OUTPUT_DIR_SS, file);
        try {
          const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" list`, { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024, timeout: 10000 });
          const tables = JSON.parse(result);
          databases.push({
            name: file,
            path: `output/${file}`,
            readonly: file === 'jubilee.db',
            tables: tables,
            tableCount: tables.length,
            size: fs.statSync(dbPath).size,
          });
        } catch (e) { /* skip unreadable db files */ }
      }
      // 2. Scan projects/ for project databases
      try {
        const projects = readProjects();
        for (const proj of projects) {
          const projDbPath = path.join(PROJECTS_DIR, proj.id, 'project.db');
          if (fs.existsSync(projDbPath)) {
            try {
              const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${projDbPath}" list`, { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024, timeout: 10000 });
              const tables = JSON.parse(result);
              databases.push({
                name: `${proj.name}`,
                path: `projects/${proj.id}/project.db`,
                readonly: false,
                tables: tables,
                tableCount: tables.length,
                size: fs.statSync(projDbPath).size,
                projectId: proj.id,
                isProjectDb: true,
              });
            } catch (e) { /* skip unreadable project db */ }
          }
        }
      } catch (e) { /* no projects dir */ }
      // Sort: largest database (most tables) first, then by size descending
      databases.sort((a, b) => {
        if (b.tableCount !== a.tableCount) return b.tableCount - a.tableCount;
        return b.size - a.size;
      });
      json(res, { data: databases });
    } catch (e) { json(res, { data: [] }); }
    return;
  }

  if (p === '/api/database/tables' && m === 'GET') {
    const dbPath = resolveDbPath(url);
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" list`, { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024, timeout: 10000 });
      json(res, { data: JSON.parse(result), db: path.basename(dbPath), readonly: isReadOnlyDb(dbPath) });
    } catch (e) { json(res, { data: [] }); }
    return;
  }

  const tableGetMatch = p.match(/^\/api\/database\/table\/(.+)$/) ;
  if (tableGetMatch && m === 'GET') {
    const dbPath = resolveDbPath(url);
    const table = decodeURIComponent(tableGetMatch[1]);
    const limit = url.searchParams.get('limit') || 500;
    const offset = url.searchParams.get('offset') || 0;
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" get "${table}" ${limit} ${offset}`, { encoding: 'utf8', maxBuffer: 20 * 1024 * 1024, timeout: 15000 });
      const data = JSON.parse(result);
      data.db = path.basename(dbPath);
      data.readonly = isReadOnlyDb(dbPath);
      json(res, { data });
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  if (p === '/api/database/cell' && m === 'POST') {
    const body = await parseBody(req);
    const dbPath = body.db ? path.join(OUTPUT_DIR_SS, path.basename(body.db)) : DEFAULT_USER_DB;
    if (isReadOnlyDb(dbPath)) { json(res, { error: 'Database is read-only' }, 403); return; }
    const { table, rowid, column, value } = body;
    if (!table || !rowid || !column) { json(res, { error: 'Missing table, rowid, or column' }, 400); return; }
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" update "${table}" ${rowid} "${column}" "${(value || '').replace(/"/g, '\\"')}"`, { encoding: 'utf8', timeout: 5000 });
      json(res, JSON.parse(result));
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  if (p === '/api/database/table' && m === 'POST') {
    const body = await parseBody(req);
    const { name, columns, db } = body;
    if (!name) { json(res, { error: 'Missing table name' }, 400); return; }
    const dbPath = db ? path.join(OUTPUT_DIR_SS, path.basename(db)) : DEFAULT_USER_DB;
    if (isReadOnlyDb(dbPath)) { json(res, { error: 'Database is read-only' }, 403); return; }
    const cols = (columns || ['Column_A', 'Column_B', 'Column_C']).map(c => `"${c}"`).join(' ');
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" create "${name}" ${cols}`, { encoding: 'utf8', timeout: 5000 });
      json(res, JSON.parse(result));
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  if (tableGetMatch && m === 'DELETE') {
    const table = decodeURIComponent(tableGetMatch[1]);
    const dbPath = resolveDbPath(url);
    if (isReadOnlyDb(dbPath)) { json(res, { error: 'Database is read-only' }, 403); return; }
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" drop "${table}"`, { encoding: 'utf8', timeout: 5000 });
      json(res, JSON.parse(result));
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  if (p === '/api/database/import' && m === 'POST') {
    const body = await parseBody(req);
    const xlsxPath = body.path;
    if (!xlsxPath) { json(res, { error: 'Missing xlsx path' }, 400); return; }
    const fullXlsx = path.join(FILE_ROOT, xlsxPath);
    if (!fs.existsSync(fullXlsx)) { json(res, { error: 'File not found' }, 404); return; }
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${DEFAULT_USER_DB}" import "${fullXlsx}"`, { encoding: 'utf8', maxBuffer: 20 * 1024 * 1024, timeout: 30000 });
      json(res, JSON.parse(result));
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  if (p === '/api/database/row' && m === 'POST') {
    const body = await parseBody(req);
    const dbPath = body.db ? path.join(OUTPUT_DIR_SS, path.basename(body.db)) : DEFAULT_USER_DB;
    if (isReadOnlyDb(dbPath)) { json(res, { error: 'Database is read-only' }, 403); return; }
    if (!body.table) { json(res, { error: 'Missing table' }, 400); return; }
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" add-row "${body.table}"`, { encoding: 'utf8', timeout: 5000 });
      json(res, JSON.parse(result));
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  if (p === '/api/database/row' && m === 'DELETE') {
    const body = await parseBody(req);
    const dbPath = body.db ? path.join(OUTPUT_DIR_SS, path.basename(body.db)) : DEFAULT_USER_DB;
    if (isReadOnlyDb(dbPath)) { json(res, { error: 'Database is read-only' }, 403); return; }
    if (!body.table || !body.rowid) { json(res, { error: 'Missing table or rowid' }, 400); return; }
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" delete-row "${body.table}" ${body.rowid}`, { encoding: 'utf8', timeout: 5000 });
      json(res, JSON.parse(result));
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  if (p === '/api/database/column' && m === 'POST') {
    const body = await parseBody(req);
    if (!body.table || !body.column) { json(res, { error: 'Missing table or column' }, 400); return; }
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${DEFAULT_USER_DB}" add-col "${body.table}" "${body.column}"`, { encoding: 'utf8', timeout: 5000 });
      json(res, JSON.parse(result));
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  // Insert a row with data
  if (p === '/api/database/insert' && m === 'POST') {
    const body = await parseBody(req);
    const { table, data, db } = body;
    if (!table || !data) { json(res, { error: 'Missing table or data' }, 400); return; }
    const dbPath = db ? path.join(OUTPUT_DIR_SS, path.basename(db)) : DEFAULT_USER_DB;
    if (isReadOnlyDb(dbPath)) { json(res, { error: 'Database is read-only' }, 403); return; }
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" insert "${table}"`, { input: JSON.stringify(data), encoding: 'utf8', timeout: 5000 });
      json(res, JSON.parse(result));
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  // Update a row by primary key id
  if (p === '/api/database/update-row' && m === 'POST') {
    const body = await parseBody(req);
    const { table, id: rowId, data, db } = body;
    if (!table || !rowId || !data) { json(res, { error: 'Missing table, id, or data' }, 400); return; }
    const dbPath = db ? path.join(OUTPUT_DIR_SS, path.basename(db)) : DEFAULT_USER_DB;
    if (isReadOnlyDb(dbPath)) { json(res, { error: 'Database is read-only' }, 403); return; }
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" update-row "${table}" "${rowId}"`, { input: JSON.stringify(data), encoding: 'utf8', timeout: 5000 });
      json(res, JSON.parse(result));
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  // Delete a row by primary key id
  if (p === '/api/database/delete-by-id' && m === 'POST') {
    const body = await parseBody(req);
    const { table, id: rowId, db } = body;
    if (!table || !rowId) { json(res, { error: 'Missing table or id' }, 400); return; }
    const dbPath = db ? path.join(OUTPUT_DIR_SS, path.basename(db)) : DEFAULT_USER_DB;
    if (isReadOnlyDb(dbPath)) { json(res, { error: 'Database is read-only' }, 403); return; }
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" delete-by-id "${table}" "${rowId}"`, { encoding: 'utf8', timeout: 5000 });
      json(res, JSON.parse(result));
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  // Create a new empty database
  if (p === '/api/database/create' && m === 'POST') {
    const body = await parseBody(req);
    const { name } = body;
    if (!name) { json(res, { error: 'Missing database name' }, 400); return; }
    const sanitized = path.basename(name).replace(/[^a-zA-Z0-9_-]/g, '');
    const dbName = sanitized.endsWith('.db') ? sanitized : sanitized + '.db';
    if (dbName === 'jubilee.db') { json(res, { error: 'Cannot overwrite jubilee.db' }, 403); return; }
    if (!fs.existsSync(OUTPUT_DIR_SS)) fs.mkdirSync(OUTPUT_DIR_SS, { recursive: true });
    const dbPath = path.join(OUTPUT_DIR_SS, dbName);
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" create-db`, { encoding: 'utf8', timeout: 5000 });
      json(res, JSON.parse(result));
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  if (p === '/api/database/query' && m === 'POST') {
    const body = await parseBody(req);
    const { sql, db } = body;
    if (!sql) { json(res, { error: 'Missing sql' }, 400); return; }
    // Security: only allow SELECT statements
    const firstWord = sql.trim().split(/\s+/)[0].toUpperCase();
    if (firstWord !== 'SELECT') { json(res, { error: `Only SELECT queries are allowed (got ${firstWord})` }, 403); return; }
    const dbPath = db ? path.join(OUTPUT_DIR_SS, path.basename(db)) : DEFAULT_USER_DB;
    if (!fs.existsSync(dbPath)) { json(res, { error: 'Database not found' }, 404); return; }
    try {
      // Pipe SQL via stdin to avoid shell injection
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" query`, { input: sql, encoding: 'utf8', maxBuffer: 20 * 1024 * 1024, timeout: 15000 });
      json(res, JSON.parse(result));
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  const dbExportMatch = p.match(/^\/api\/database\/export\/(.+)$/);
  if (dbExportMatch && m === 'GET') {
    const table = decodeURIComponent(dbExportMatch[1]);
    const dbPath = resolveDbPath(url);
    try {
      const result = require('node:child_process').execSync(`python3 "${DATABASE_MANAGER_PY}" "${dbPath}" export "${table}"`, { encoding: 'utf8', maxBuffer: 20 * 1024 * 1024, timeout: 15000 });
      res.writeHead(200, {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': `attachment; filename="${table}.csv"`,
      });
      res.end(result);
    } catch (e) { json(res, { error: e.message }, 500); }
    return;
  }

  // ─── File system operations ───────────────────────────────────────────
  if (p === '/api/fs/create-file' && m === 'POST') {
    const body = await parseBody(req);
    const filePath = body.path;
    if (!filePath || filePath.includes('..')) { json(res, { error: 'Invalid path' }, 400); return; }
    const fullPath = path.join(ROOT, filePath);
    if (fs.existsSync(fullPath)) { json(res, { error: 'File already exists' }, 409); return; }
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, body.content || '');
    auditLog('fs_create_file', { path: filePath });
    log(`File created: ${filePath}`);
    json(res, { data: { path: filePath } });
    return;
  }

  if (p === '/api/fs/create-folder' && m === 'POST') {
    const body = await parseBody(req);
    const folderPath = body.path;
    if (!folderPath || folderPath.includes('..')) { json(res, { error: 'Invalid path' }, 400); return; }
    const fullPath = path.join(ROOT, folderPath);
    if (fs.existsSync(fullPath)) { json(res, { error: 'Folder already exists' }, 409); return; }
    fs.mkdirSync(fullPath, { recursive: true });
    auditLog('fs_create_folder', { path: folderPath });
    log(`Folder created: ${folderPath}`);
    json(res, { data: { path: folderPath } });
    return;
  }

  if (p === '/api/fs/rename' && m === 'POST') {
    const body = await parseBody(req);
    const { oldPath, newName } = body;
    if (!oldPath || !newName || oldPath.includes('..') || newName.includes('/') || newName.includes('..')) {
      json(res, { error: 'Invalid path or name' }, 400); return;
    }
    const fullOld = path.join(ROOT, oldPath);
    if (!fs.existsSync(fullOld)) { json(res, { error: 'Source not found' }, 404); return; }
    const dir = path.dirname(fullOld);
    const fullNew = path.join(dir, newName);
    if (fs.existsSync(fullNew)) { json(res, { error: 'Target already exists' }, 409); return; }
    fs.renameSync(fullOld, fullNew);
    const newPath = path.join(path.dirname(oldPath), newName);
    auditLog('fs_rename', { from: oldPath, to: newPath });
    log(`Renamed: ${oldPath} -> ${newPath}`);
    json(res, { data: { oldPath, newPath } });
    return;
  }

  if (p === '/api/fs/delete' && m === 'POST') {
    const body = await parseBody(req);
    const filePath = body.path;
    if (!filePath || filePath.includes('..')) { json(res, { error: 'Invalid path' }, 400); return; }
    const fullPath = path.join(ROOT, filePath);
    if (!fs.existsSync(fullPath)) { json(res, { error: 'Not found' }, 404); return; }
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) fs.rmSync(fullPath, { recursive: true });
    else fs.unlinkSync(fullPath);
    auditLog('fs_delete', { path: filePath, isDir: stat.isDirectory() });
    log(`Deleted: ${filePath}`);
    json(res, { data: { path: filePath } });
    return;
  }

  if (p === '/api/fs/copy' && m === 'POST') {
    const body = await parseBody(req);
    const { src } = body;
    let dest = body.dest;
    if (!src || !dest || src.includes('..') || dest.includes('..')) {
      json(res, { error: 'Invalid path' }, 400); return;
    }
    const fullSrc = path.join(ROOT, src);
    if (!fs.existsSync(fullSrc)) { json(res, { error: 'Source not found' }, 404); return; }
    // Auto-rename if destination exists
    let fullDest = path.join(ROOT, dest);
    if (fs.existsSync(fullDest)) {
      const dir = path.dirname(dest);
      const base = path.basename(dest);
      const ext = path.extname(base);
      const stem = ext ? base.slice(0, -ext.length) : base;
      for (let i = 2; i < 100; i++) {
        const candidate = `${stem}-copy${i > 2 ? '-' + i : ''}${ext}`;
        dest = dir && dir !== '.' ? `${dir}/${candidate}` : candidate;
        fullDest = path.join(ROOT, dest);
        if (!fs.existsSync(fullDest)) break;
      }
    }
    fs.mkdirSync(path.dirname(fullDest), { recursive: true });
    const stat = fs.statSync(fullSrc);
    if (stat.isDirectory()) fs.cpSync(fullSrc, fullDest, { recursive: true });
    else fs.copyFileSync(fullSrc, fullDest);
    auditLog('fs_copy', { src, dest });
    log(`Copied: ${src} -> ${dest}`);
    json(res, { data: { src, dest } });
    return;
  }

  if (p === '/api/fs/move' && m === 'POST') {
    const body = await parseBody(req);
    const { src } = body;
    let dest = body.dest;
    if (!src || !dest || src.includes('..') || dest.includes('..')) {
      json(res, { error: 'Invalid path' }, 400); return;
    }
    const fullSrc = path.join(ROOT, src);
    if (!fs.existsSync(fullSrc)) { json(res, { error: 'Source not found' }, 404); return; }
    // Auto-rename if destination exists
    let fullDest = path.join(ROOT, dest);
    if (fs.existsSync(fullDest)) {
      const dir = path.dirname(dest);
      const base = path.basename(dest);
      const ext = path.extname(base);
      const stem = ext ? base.slice(0, -ext.length) : base;
      for (let i = 2; i < 100; i++) {
        const candidate = `${stem}-${i}${ext}`;
        dest = dir && dir !== '.' ? `${dir}/${candidate}` : candidate;
        fullDest = path.join(ROOT, dest);
        if (!fs.existsSync(fullDest)) break;
      }
    }
    fs.mkdirSync(path.dirname(fullDest), { recursive: true });
    fs.renameSync(fullSrc, fullDest);
    auditLog('fs_move', { src, dest });
    log(`Moved: ${src} -> ${dest}`);
    json(res, { data: { src, dest } });
    return;
  }

  if (p === '/api/fs/save' && m === 'POST') {
    const body = await parseBody(req);
    const filePath = body.path;
    if (!filePath || filePath.includes('..')) { json(res, { error: 'Invalid path' }, 400); return; }
    const fullPath = path.join(ROOT, filePath);
    if (!fs.existsSync(fullPath)) { json(res, { error: 'File not found' }, 404); return; }
    fs.writeFileSync(fullPath, body.content || '');
    auditLog('fs_save', { path: filePath, size: (body.content || '').length });
    log(`File saved: ${filePath} (${(body.content || '').length} bytes)`);
    json(res, { data: { path: filePath, size: (body.content || '').length } });
    return;
  }

  if (p === '/api/fs/info' && m === 'GET') {
    const filePath = url.searchParams.get('path');
    if (!filePath || filePath.includes('..')) { json(res, { error: 'Invalid path' }, 400); return; }
    const fullPath = path.join(ROOT, filePath);
    if (!fs.existsSync(fullPath)) { json(res, { error: 'Not found' }, 404); return; }
    const stat = fs.statSync(fullPath);
    json(res, {
      data: {
        path: filePath, name: path.basename(filePath),
        isDir: stat.isDirectory(), size: stat.size,
        mode: '0' + (stat.mode & 0o777).toString(8),
        modified: stat.mtime.toISOString(), created: stat.birthtime.toISOString(),
      },
    });
    return;
  }

  if (p === '/api/fs/chmod' && m === 'POST') {
    const body = await parseBody(req);
    const filePath = body.path;
    const mode = parseInt(body.mode, 8);
    if (!filePath || filePath.includes('..') || isNaN(mode)) {
      json(res, { error: 'Invalid path or mode' }, 400); return;
    }
    const fullPath = path.join(ROOT, filePath);
    if (!fs.existsSync(fullPath)) { json(res, { error: 'Not found' }, 404); return; }
    fs.chmodSync(fullPath, mode);
    auditLog('fs_chmod', { path: filePath, mode: body.mode });
    log(`Chmod: ${filePath} -> ${body.mode}`);
    json(res, { data: { path: filePath, mode: body.mode } });
    return;
  }

  if (p === '/api/fs/download' && m === 'GET') {
    const filePath = url.searchParams.get('path');
    if (!filePath || filePath.includes('..')) { res.writeHead(400); res.end('Invalid path'); return; }
    const fullPath = path.join(ROOT, filePath);
    if (!fs.existsSync(fullPath)) { res.writeHead(404); res.end('Not found'); return; }
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) { res.writeHead(400); res.end('Cannot download a directory'); return; }
    const filename = path.basename(filePath);
    res.writeHead(200, {
      'Content-Type': 'application/octet-stream',
      'Content-Disposition': `attachment; filename="${filename}"`,
      'Content-Length': stat.size,
    });
    fs.createReadStream(fullPath).pipe(res);
    return;
  }

  // --- System file browser (browse from filesystem root) ---
  if (p === '/api/system-browse' && m === 'GET') {
    const dirPath = url.searchParams.get('path') || '/';
    // Resolve to absolute — prevent relative tricks
    const absDir = path.resolve(dirPath);
    if (!fs.existsSync(absDir)) { json(res, { error: 'Directory not found' }, 404); return; }
    const stat = fs.statSync(absDir);
    if (!stat.isDirectory()) { json(res, { error: 'Not a directory' }, 400); return; }
    try {
      const entries = fs.readdirSync(absDir, { withFileTypes: true });
      const items = [];
      for (const e of entries) {
        if (e.name.startsWith('.') && absDir === '/') continue; // hide dotfiles at root
        try {
          const fullPath = path.join(absDir, e.name);
          const s = fs.statSync(fullPath);
          items.push({
            name: e.name,
            path: fullPath,
            isDir: s.isDirectory(),
            size: s.isDirectory() ? null : s.size,
            modified: s.mtime.toISOString(),
          });
        } catch {}
      }
      // Sort: dirs first, then alpha
      items.sort((a, b) => {
        if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
      json(res, { data: { path: absDir, parent: absDir === '/' ? null : path.dirname(absDir), items } });
    } catch (e) {
      json(res, { error: `Cannot read directory: ${e.message}` }, 403);
    }
    return;
  }

  // --- Read a system file by absolute path (for system browser viewer) ---
  if (p === '/api/system-file' && m === 'GET') {
    const filePath = url.searchParams.get('path');
    if (!filePath) { json(res, { error: 'Missing path' }, 400); return; }
    const absPath = path.resolve(filePath);
    if (!fs.existsSync(absPath)) { json(res, { error: 'File not found' }, 404); return; }
    const stat = fs.statSync(absPath);
    if (stat.isDirectory()) { json(res, { error: 'Path is a directory' }, 400); return; }
    // Size limit: 5MB
    if (stat.size > 5 * 1024 * 1024) { json(res, { error: 'File too large (>5MB)' }, 400); return; }
    const ext = path.extname(absPath).toLowerCase();
    const name = path.basename(absPath);
    try {
      if (ext === '.csv') {
        const rows = loadCSV(absPath);
        const headers = rows.length > 0 ? Object.keys(rows[0]) : [];
        json(res, { data: { type: 'csv', name, path: absPath, headers, rows, isSystemFile: true } });
      } else if (ext === '.xlsx') {
        const xlsxReader = path.join(__dirname, 'xlsx_reader.py');
        const result = require('node:child_process').execSync(`python3 "${xlsxReader}" "${absPath}"`, { encoding: 'utf8', maxBuffer: 20 * 1024 * 1024, timeout: 15000 });
        const parsed = JSON.parse(result);
        json(res, { data: { type: 'xlsx', name, path: absPath, sheets: parsed.sheets, isSystemFile: true } });
      } else if (['.md', '.txt', '.py', '.sh', '.js', '.json', '.yml', '.yaml', '.cfg', '.ini', '.env', '.html', '.css', '.ts', '.tsx', '.jsx', '.go', '.rs', '.rb', '.php', '.sql', '.xml', '.toml', '.log', ''].includes(ext) || name.startsWith('.')) {
        const type = ext === '.json' ? 'json' : ext === '.md' ? 'md' : 'text';
        const content = fs.readFileSync(absPath, 'utf8');
        json(res, { data: { type, name, path: absPath, content, isSystemFile: true } });
      } else {
        json(res, { error: `Unsupported file type: ${ext || '(none)'}` }, 400);
      }
    } catch (e) {
      json(res, { error: `Cannot read file: ${e.message}` }, 500);
    }
    return;
  }

  // --- SQL query endpoint ---
  if (p === '/api/sql' && m === 'POST') {
    const body = await parseBody(req);
    const query = (body.query || '').trim();
    if (!query) { json(res, { error: 'Missing query' }, 400); return; }
    // Read-only: block writes
    const upper = query.toUpperCase();
    if (/^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH)\b/.test(upper)) {
      json(res, { error: 'Read-only: write operations not allowed' }, 403);
      return;
    }
    const dbPath = path.join(ROOT, 'output', 'jubilee.db');
    if (!fs.existsSync(dbPath)) {
      json(res, { error: 'Database not built. Run: python3 scripts/build_db.py' }, 404);
      return;
    }
    try {
      const { DatabaseSync } = require('node:sqlite');
      const db = new DatabaseSync(dbPath, { open: true, readOnly: true });
      const start = performance.now();
      const stmt = db.prepare(query);
      const rows = stmt.all();
      const elapsed = performance.now() - start;
      const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
      db.close();
      log(`SQL (${elapsed.toFixed(1)}ms, ${rows.length} rows): ${query.slice(0, 100)}`);
      json(res, { data: { columns, rows, rowCount: rows.length, elapsed_ms: Math.round(elapsed * 10) / 10 } });
    } catch (err) {
      log(`SQL error: ${err.message}`);
      json(res, { error: err.message }, 400);
    }
    return;
  }

  if (p === '/api/sql/schema' && m === 'GET') {
    const dbPath = path.join(ROOT, 'output', 'jubilee.db');
    if (!fs.existsSync(dbPath)) {
      json(res, { error: 'Database not built' }, 404);
      return;
    }
    try {
      const { DatabaseSync } = require('node:sqlite');
      const db = new DatabaseSync(dbPath, { open: true, readOnly: true });
      const tables = db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_config' AND name NOT LIKE '%_data' AND name NOT LIKE '%_docsize' AND name NOT LIKE '%_idx' AND name NOT LIKE '%_content' ORDER BY name").all();
      const schema = {};
      for (const { name } of tables) {
        const cols = db.prepare(`PRAGMA table_info("${name}")`).all();
        const count = db.prepare(`SELECT COUNT(*) as c FROM "${name}"`).get();
        schema[name] = { columns: cols.map(c => ({ name: c.name, type: c.type })), rowCount: count.c };
      }
      db.close();
      json(res, { data: schema });
    } catch (err) {
      json(res, { error: err.message }, 500);
    }
    return;
  }

  // --- KB folder management ---
  if (p === '/api/kb/folders' && m === 'GET') {
    const kbRoot = path.join(ROOT, 'kb');
    try {
      if (!fs.existsSync(kbRoot)) fs.mkdirSync(kbRoot, { recursive: true });
      const entries = fs.readdirSync(kbRoot, { withFileTypes: true });
      const folders = entries.filter(e => e.isDirectory() && e.name !== 'sessions').map(e => e.name).sort();
      json(res, { data: folders });
    } catch (e) { json(res, { data: [] }); }
    return;
  }

  if (p === '/api/kb/folders' && m === 'POST') {
    const body = await parseBody(req);
    const { name } = body;
    if (!name) { json(res, { error: 'Missing folder name' }, 400); return; }
    const sanitized = name.replace(/[^a-zA-Z0-9_-]/g, '-').toLowerCase();
    if (!sanitized) { json(res, { error: 'Invalid folder name' }, 400); return; }
    const folderPath = path.join(ROOT, 'kb', sanitized);
    fs.mkdirSync(folderPath, { recursive: true });
    json(res, { data: { name: sanitized, path: `kb/${sanitized}` } });
    return;
  }

  // --- Export session (markdown, JSON, or KB article) ---
  const exportMatch = p.match(/^\/api\/sessions\/([^/]+)\/export$/);
  if (exportMatch && m === 'POST') {
    const sessionId = exportMatch[1];
    const session = getSession(sessionId);
    if (!session) { json(res, { error: 'Session not found' }, 404); return; }
    const messages = getMessages(sessionId);
    if (!messages.length) { json(res, { error: 'No messages to export' }, 400); return; }

    const body = await parseBody(req);
    const format = body.format || 'markdown'; // markdown, json, kb-article
    const title = session.title || 'Untitled Session';
    const now = new Date();
    const dateStr = now.toISOString().split('T')[0];
    const timeStr = now.toTimeString().split(' ')[0];

    if (format === 'json') {
      // Raw JSON export
      const exported = { sessionId, title, model: session.model, createdAt: session.createdAt, exportedAt: now.toISOString(), messageCount: messages.length, messages };
      json(res, { data: { content: JSON.stringify(exported, null, 2), filename: `${dateStr}-session-${sessionId.slice(0,8)}.json`, format: 'json' } });
      return;
    }

    // Build markdown from messages
    const mdLines = [`# ${title}\n`, `**Session ID**: \`${sessionId}\``, `**Date**: ${dateStr} ${timeStr}`, `**Model**: ${session.model || 'opus'}`, `**Messages**: ${messages.length}`, `**Cost**: $${(session.totalCost || 0).toFixed(2)}`, '', '---', ''];
    for (const msg of messages) {
      const time = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : '';
      if (msg.role === 'user') mdLines.push(`## User (${time})\n\n${msg.content}\n\n---\n`);
      else if (msg.role === 'assistant') mdLines.push(`## Assistant (${time})\n\n${msg.content}\n\n---\n`);
      else if (msg.role === 'thinking') mdLines.push(`> **Reasoning**: ${msg.content.slice(0, 500)}${msg.content.length > 500 ? '...' : ''}\n`);
      else if (msg.tool === 'output') mdLines.push(`\`\`\`\n${msg.content.slice(0, 2000)}\n\`\`\`\n`);
      else if (msg.tool) mdLines.push(`> **${msg.tool}**: ${msg.content}\n`);
    }
    const mdContent = mdLines.join('\n');

    if (format === 'kb-article') {
      // Save as KB article with AI-generated metadata
      const meta = generateMetadata(session, messages);
      const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50);
      let filename = `${dateStr}-${slug}.md`;
      const kbFolder = (body.kbFolder || 'analysis').replace(/[^a-zA-Z0-9_-]/g, '-');
      const kbDir = path.join(ROOT, 'kb', kbFolder);
      fs.mkdirSync(kbDir, { recursive: true });
      // If file already exists, append version number to create a new one
      let version = 1;
      let updated = false;
      const baseName = `${dateStr}-${slug}`;
      if (fs.existsSync(path.join(kbDir, filename))) {
        // Find next available version
        version = 2;
        while (fs.existsSync(path.join(kbDir, `${baseName}-v${version}.md`))) version++;
        filename = `${baseName}-v${version}.md`;
        updated = true;
      }
      const article = `---\ntitle: "${meta.title || title}"\ndate: ${dateStr}\nsession_id: ${sessionId}\ntags: [${meta.tags || ''}]\nsummary: "${(meta.summary || '').replace(/"/g, '\\"')}"\nexport_version: ${version}\n---\n\n${mdContent}`;
      fs.writeFileSync(path.join(kbDir, filename), article);
      auditLog('export_kb_article', { sessionId, filename, version, folder: kbFolder });
      log(`KB article exported: kb/${kbFolder}/${filename}${updated ? ` (version ${version})` : ''}`);
      json(res, { data: { content: article, filename, path: `kb/${kbFolder}/${filename}`, format: 'kb-article', version, updated, folder: kbFolder } });
      return;
    }

    // Default: markdown download
    const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50);
    const filename = `${dateStr}-${slug}.md`;
    auditLog('export_markdown', { sessionId, filename });
    json(res, { data: { content: mdContent, filename, format: 'markdown' } });
    return;
  }

  // --- Data summary ---
  if (p === '/api/data/summary' && m === 'GET') {
    const events = getEvents();
    const clocks = getClocks();
    const sigs = getSignatures();
    const db = getDatabase();
    const sigCounts = {};
    for (const e of db) { if (e.signature) sigCounts[e.signature] = (sigCounts[e.signature] || 0) + 1; }
    json(res, {
      data: {
        eventCount: events.length,
        dbCount: db.length,
        clocks: Object.entries(clocks).map(([k, v]) => ({ name: k, ...v })),
        signatures: sigs.map(s => ({ ...s, count: sigCounts[s.name] || 0 })),
      },
    });
    return;
  }

  // --- Scripts manifest ---
  if (p === '/api/scripts' && m === 'GET') {
    const manifest = loadScriptsManifest();
    json(res, { data: manifest });
    return;
  }

  // --- Projects ---
  if (p === '/api/projects' && m === 'GET') {
    const projects = readProjects();
    const sessions = readSessions();
    for (const proj of projects) {
      proj.sessionCount = sessions.filter(s => s.projectId === proj.id).length;
      proj.jobCount = readJobs(proj.id).length;
    }
    // Also include unassigned session count
    const unassigned = sessions.filter(s => !s.projectId).length;
    json(res, { data: projects, unassignedSessions: unassigned });
    return;
  }

  if (p === '/api/projects' && m === 'POST') {
    const body = await parseBody(req);
    const project = createProject(body.name, body.description);
    json(res, { data: project });
    return;
  }

  // GET /api/projects/{id}
  const projectDetailMatch = p.match(/^\/api\/projects\/([^/]+)$/);
  if (projectDetailMatch && m === 'GET') {
    const proj = getProject(projectDetailMatch[1]);
    if (!proj) { json(res, { error: 'Project not found' }, 404); return; }
    const sessions = readSessions().filter(s => s.projectId === proj.id);
    const jobs = readJobs(proj.id);
    const mdPath = path.join(PROJECTS_DIR, proj.id, 'project.md');
    let md = '';
    try { md = fs.readFileSync(mdPath, 'utf8'); } catch (e) {}
    json(res, { data: { ...proj, sessions, jobs, md } });
    return;
  }

  // PUT /api/projects/{id}
  if (projectDetailMatch && m === 'PUT') {
    const body = await parseBody(req);
    const proj = updateProject(projectDetailMatch[1], body);
    if (!proj) { json(res, { error: 'Project not found' }, 404); return; }
    // Update project.md if description changed
    if (body.description !== undefined || body.name !== undefined) {
      const mdPath = path.join(PROJECTS_DIR, proj.id, 'project.md');
      const mdContent = `# ${proj.name}\n\n${proj.description || 'No description yet.'}\n\nCreated: ${proj.createdAt}\n`;
      try { fs.writeFileSync(mdPath, mdContent); } catch (e) {}
    }
    json(res, { data: proj });
    return;
  }

  // DELETE /api/projects/{id}
  if (projectDetailMatch && m === 'DELETE') {
    const ok = deleteProject(projectDetailMatch[1]);
    json(res, { data: { deleted: ok } });
    return;
  }

  // GET /api/projects/{id}/sessions
  const projectSessionsMatch = p.match(/^\/api\/projects\/([^/]+)\/sessions$/);
  if (projectSessionsMatch && m === 'GET') {
    const sessions = readSessions().filter(s => s.projectId === projectSessionsMatch[1]);
    json(res, { data: sessions });
    return;
  }

  // GET /api/projects/{id}/md — read project.md
  const projectMdMatch = p.match(/^\/api\/projects\/([^/]+)\/md$/);
  if (projectMdMatch && m === 'GET') {
    const mdPath = path.join(PROJECTS_DIR, projectMdMatch[1], 'project.md');
    try {
      const content = fs.readFileSync(mdPath, 'utf8');
      json(res, { data: { content, path: mdPath } });
    } catch (e) {
      json(res, { data: null });
    }
    return;
  }

  // PUT /api/projects/{id}/md — update project.md
  if (projectMdMatch && m === 'PUT') {
    const body = await parseBody(req);
    const mdPath = path.join(PROJECTS_DIR, projectMdMatch[1], 'project.md');
    try {
      fs.mkdirSync(path.dirname(mdPath), { recursive: true });
      fs.writeFileSync(mdPath, body.content || '');
      json(res, { data: { saved: true, path: mdPath } });
    } catch (e) {
      json(res, { error: e.message }, 500);
    }
    return;
  }

  // --- Jobs ---

  // GET /api/projects/{projectId}/jobs
  const projectJobsMatch = p.match(/^\/api\/projects\/([^/]+)\/jobs$/);
  if (projectJobsMatch && m === 'GET') {
    const jobs = readJobs(projectJobsMatch[1]);
    json(res, { data: jobs });
    return;
  }

  // POST /api/projects/{projectId}/jobs
  if (projectJobsMatch && m === 'POST') {
    const body = await parseBody(req);
    const job = createJob(projectJobsMatch[1], body.sessionId, body.title);
    // Broadcast job_update to all listeners on this session
    if (body.sessionId) {
      sessionBroadcast(body.sessionId, { type: 'stream', event: { type: 'job_update', job } });
    }
    json(res, { data: job });
    return;
  }

  // GET /api/projects/{projectId}/jobs/{jobId}
  const jobDetailMatch = p.match(/^\/api\/projects\/([^/]+)\/jobs\/([^/]+)$/);
  if (jobDetailMatch && m === 'GET') {
    const [, projectId, jobId] = jobDetailMatch;
    const job = getJob(projectId, jobId);
    if (!job) { json(res, { error: 'Job not found' }, 404); return; }
    job.plan = getJobPlan(projectId, jobId);
    job.tasks = getJobTasks(projectId, jobId);
    json(res, { data: job });
    return;
  }

  // PUT/PATCH /api/projects/{projectId}/jobs/{jobId}
  if (jobDetailMatch && (m === 'PUT' || m === 'PATCH')) {
    const [, projectId, jobId] = jobDetailMatch;
    const body = await parseBody(req);
    const job = updateJob(projectId, jobId, body);
    if (!job) { json(res, { error: 'Job not found' }, 404); return; }
    // Broadcast job_update to all listeners on this job's session
    if (job.sessionId) {
      sessionBroadcast(job.sessionId, { type: 'stream', event: { type: 'job_update', job } });
    }
    json(res, { data: job });
    return;
  }

  // GET /api/projects/{projectId}/jobs/{jobId}/plan
  const jobPlanMatch = p.match(/^\/api\/projects\/([^/]+)\/jobs\/([^/]+)\/plan$/);
  if (jobPlanMatch && m === 'GET') {
    const [, projectId, jobId] = jobPlanMatch;
    const content = getJobPlan(projectId, jobId);
    const planPath = getJobPlanPath(projectId, jobId);
    json(res, { data: content ? { content, path: planPath } : null });
    return;
  }

  // GET /api/projects/{projectId}/jobs/{jobId}/tasks
  const jobTasksMatch = p.match(/^\/api\/projects\/([^/]+)\/jobs\/([^/]+)\/tasks$/);
  if (jobTasksMatch && m === 'GET') {
    const [, projectId, jobId] = jobTasksMatch;
    const tasks = getJobTasks(projectId, jobId);
    const tasksPath = getJobTasksPath(projectId, jobId);
    json(res, { data: { tasks, path: tasksPath } });
    return;
  }

  // GET /api/sessions/{sessionId}/jobs — convenience: get jobs for a session
  const sessionJobsMatch = p.match(/^\/api\/sessions\/([^/]+)\/jobs$/);
  if (sessionJobsMatch && m === 'GET') {
    const session = getSession(sessionJobsMatch[1]);
    if (!session || !session.projectId) { json(res, { data: [] }); return; }
    const jobs = getSessionJobs(session.projectId, session.id);
    json(res, { data: jobs });
    return;
  }

  // POST /api/sessions/{sessionId}/jobs — convenience: create job in session's project
  if (sessionJobsMatch && m === 'POST') {
    const sessionId = sessionJobsMatch[1];
    const session = getSession(sessionId);
    if (!session || !session.projectId) { json(res, { error: 'Session must belong to a project to create jobs' }, 400); return; }
    const body = await parseBody(req);
    const job = createJob(session.projectId, session.id, body.title);
    // Broadcast job_update so all connected clients refresh the jobs list
    sessionBroadcast(sessionId, { type: 'stream', event: { type: 'job_update', job } });
    json(res, { data: job });
    return;
  }

  // PATCH /api/sessions/{sessionId}/jobs/{jobId} — convenience: update job via session path
  const sessionJobDetailMatch = p.match(/^\/api\/sessions\/([^/]+)\/jobs\/([^/]+)$/);
  if (sessionJobDetailMatch && (m === 'PATCH' || m === 'PUT')) {
    const sessionId = sessionJobDetailMatch[1];
    const session = getSession(sessionId);
    if (!session || !session.projectId) { json(res, { error: 'Session not found or no project' }, 404); return; }
    const body = await parseBody(req);
    const job = updateJob(session.projectId, sessionJobDetailMatch[2], body);
    if (!job) { json(res, { error: 'Job not found' }, 404); return; }
    // Broadcast job_update so all connected clients refresh the jobs list
    sessionBroadcast(sessionId, { type: 'stream', event: { type: 'job_update', job } });
    json(res, { data: job });
    return;
  }

  // GET /api/sessions/{sessionId}/active-job — get the active job for context injection
  const activeJobMatch = p.match(/^\/api\/sessions\/([^/]+)\/active-job$/);
  if (activeJobMatch && m === 'GET') {
    const session = getSession(activeJobMatch[1]);
    if (!session || !session.projectId) { json(res, { data: null }); return; }
    const job = getActiveJob(session.projectId, session.id);
    if (!job) { json(res, { data: null }); return; }
    job.plan = getJobPlan(session.projectId, job.id);
    job.tasks = getJobTasks(session.projectId, job.id);
    json(res, { data: job });
    return;
  }

  // --- Collaborative Jobs ---

  // POST /api/jobs/{jobId}/invite — invite a remote agent to collaborate on a job
  const jobInviteMatch = p.match(/^\/api\/jobs\/([^/]+)\/invite$/);
  if (jobInviteMatch && m === 'POST') {
    const jobId = jobInviteMatch[1];
    const body = await parseBody(req);
    if (!body.targetPort) { json(res, { error: 'targetPort required' }, 400); return; }

    // Find the job across all projects
    let foundJob = null, foundProjectId = null;
    try {
      const projectsFile = path.join(PROJECTS_DIR, 'projects.json');
      const projects = JSON.parse(fs.readFileSync(projectsFile, 'utf8'));
      for (const proj of projects) {
        const job = getJob(proj.id, jobId);
        if (job) { foundJob = job; foundProjectId = proj.id; break; }
      }
    } catch {}

    if (!foundJob) { json(res, { error: 'Job not found' }, 404); return; }

    const ai = loadAgentIdentity();
    const collaborator = {
      agentId: body.agentId || null,
      name: body.agentName || null,
      port: body.targetPort,
      role: body.role || 'collaborator',
      invitedAt: new Date().toISOString(),
    };

    // Add to collaborators if not already there
    if (!foundJob.collaborators) foundJob.collaborators = [];
    if (!foundJob.collaborators.find(c => c.port === body.targetPort)) {
      foundJob.collaborators.push(collaborator);
      updateJob(foundProjectId, jobId, { collaborators: foundJob.collaborators });
    }

    // Send invite message to the target agent
    const jobPlan = getJobPlan(foundProjectId, jobId) || '(no plan yet)';
    const jobTasks = getJobTasks(foundProjectId, jobId);
    const tasksSummary = jobTasks.length ? jobTasks.map(t => `- [${t.status}] ${t.content}`).join('\n') : '(no tasks yet)';

    const inviteMessage = [
      `[JOB COLLABORATION INVITE]`,
      `From: ${ai.name || AGENT_DISPLAY}`,
      `Job: ${foundJob.title}`,
      `Job ID: ${foundJob.id}`,
      `Project: ${foundProjectId}`,
      '',
      `Plan:`,
      jobPlan,
      '',
      `Tasks:`,
      tasksSummary,
      '',
      body.message || 'You have been invited to collaborate on this job.',
      '',
      `To update task status, call: curl -s http://localhost:${PORT}/api/jobs/${jobId}/task-update -X POST -H "Content-Type: application/json" -d '{"taskIndex":N,"status":"completed","agentPort":${body.targetPort}}'`,
    ].join('\n');

    // Send invite via direct inject to their main session
    try {
      const sessRes = await fetchJson(`http://localhost:${body.targetPort}/api/sessions`);
      const sessions = sessRes?.data || [];
      const main = sessions.find(s => s.isMain);
      const targetSession = main?.id || sessions[0]?.id;
      if (targetSession) {
        await fetchJson(`http://localhost:${body.targetPort}/api/sessions/${targetSession}/inject`, {
          method: 'POST',
          body: {
            message: inviteMessage,
            sender: {
              name: ai.name || AGENT_DISPLAY,
              agentId: ai.agentId || AGENT_ID,
              server: SERVER_CONFIG.name || 'unknown',
              lab: LAB.name || 'unknown',
              port: PORT,
            },
            priority: 'normal',
            triggerAgent: body.triggerAgent !== false,
          },
        });
      }
    } catch (err) {
      log(`Job invite delivery failed for port ${body.targetPort}: ${err.message}`);
    }

    json(res, { data: { invited: true, job: foundJob } });
    return;
  }

  // POST /api/jobs/{jobId}/task-update — remote agent updates a task status
  const jobTaskUpdateMatch = p.match(/^\/api\/jobs\/([^/]+)\/task-update$/);
  if (jobTaskUpdateMatch && m === 'POST') {
    const jobId = jobTaskUpdateMatch[1];
    const body = await parseBody(req);

    // Find job across all projects
    let foundProjectId = null;
    try {
      const projectsFile = path.join(PROJECTS_DIR, 'projects.json');
      const projects = JSON.parse(fs.readFileSync(projectsFile, 'utf8'));
      for (const proj of projects) {
        if (getJob(proj.id, jobId)) { foundProjectId = proj.id; break; }
      }
    } catch {}

    if (!foundProjectId) { json(res, { error: 'Job not found' }, 404); return; }

    const tasksPath = getJobTasksPath(foundProjectId, jobId);
    const tasks = getJobTasks(foundProjectId, jobId);
    const idx = body.taskIndex ?? body.index;
    if (idx == null || idx < 0 || idx >= tasks.length) { json(res, { error: 'Invalid task index' }, 400); return; }

    if (body.status) tasks[idx].status = body.status;
    if (body.activeForm) tasks[idx].activeForm = body.activeForm;
    if (body.agentPort) tasks[idx].assignee = body.agentPort;
    tasks[idx].lastUpdatedBy = body.agentPort || 'unknown';
    tasks[idx].lastUpdatedAt = new Date().toISOString();

    fs.writeFileSync(tasksPath, JSON.stringify(tasks, null, 2));

    // Broadcast the update to any session watching this job
    const job = getJob(foundProjectId, jobId);
    if (job?.sessionId) {
      sessionBroadcast(job.sessionId, { type: 'stream', event: { type: 'job_update', job } });
    }

    json(res, { data: { updated: true, task: tasks[idx] } });
    return;
  }

  // --- Cross-Session Message Inject ---
  // POST /api/sessions/{id}/inject — receive a message from another agent/session
  const injectMatch = p.match(/^\/api\/sessions\/([^/]+)\/inject$/);
  if (injectMatch && m === 'POST') {
    const targetSessionId = injectMatch[1];
    const body = await parseBody(req);
    const session = getSession(targetSessionId);
    if (!session) { json(res, { error: 'Session not found' }, 404); return; }
    if (!body.message) { json(res, { error: 'message is required' }, 400); return; }

    const sender = body.sender || {};
    const priority = body.priority || 'normal';
    const triggerAgent = body.triggerAgent === true;
    const isReply = body.isReply === true;

    // Build the injected message with full sender context
    const senderLabel = sender.name ? `${sender.name} (${sender.server || '?'}:${sender.port || '?'})` : 'Unknown Agent';
    const injectPrefix = isReply ? '[CROSS-SESSION REPLY]' : (priority === 'urgent' ? '[URGENT CROSS-SESSION MESSAGE]' : '[CROSS-SESSION MESSAGE]');
    const fullMessage = [
      `${injectPrefix}`,
      `From: ${senderLabel}`,
      sender.sessionId ? `Session: ${sender.sessionId}` : '',
      sender.lab ? `Lab: ${sender.lab}` : '',
      '',
      body.message,
    ].filter(Boolean).join('\n');

    // Always add to inbox
    const inboxEntry = addToInbox({
      targetSessionId,
      message: body.message,
      fullMessage,
      sender,
      priority,
      triggerAgent,
      isReply,
    });

    // Broadcast inbox_message SSE event to session listeners
    sessionBroadcast(targetSessionId, { type: 'inbox_message', entry: inboxEntry });

    // Always append cross-session messages to the session for display (so user sees them in chat)
    appendMessage(targetSessionId, {
      role: 'user', content: fullMessage,
      timestamp: new Date().toISOString(),
      injected: true, senderAgent: sender.name || null,
      isReply,
    });
    updateSession(targetSessionId, {
      messageCount: (session.messageCount || 0) + 1,
      lastMessageAt: new Date().toISOString(),
    });
    // Broadcast as a new message so UI updates in real-time (must include all fields for proper rendering)
    sessionBroadcast(targetSessionId, { type: 'message', message: { role: 'user', content: fullMessage, timestamp: new Date().toISOString(), injected: true, senderAgent: sender.name || null, isReply: isReply || false } });

    // Mark as delivered since it's now in the session (user will see it)
    if (!triggerAgent) markInboxDelivered([inboxEntry.id]);

    // If triggerAgent is true AND no active Claude proc for this session, trigger Claude
    if (triggerAgent && !activeProcs.has(targetSessionId)) {

      // Fire and forget — don't block the response
      // Capture assistant text from stream events (not from disk — avoids race conditions)
      let _capturedText = '';
      const _injectStreamCb = (ev) => {
        if (ev.type === 'assistant' && Array.isArray(ev.content)) {
          for (const block of ev.content) {
            if (block.type === 'text' && block.text) _capturedText += block.text;
          }
        }
      };
      sendToClaudeStream(targetSessionId, fullMessage, _injectStreamCb).then(() => {
        markInboxDelivered([inboxEntry.id]);
        log(`Inject: Claude processed message in session ${targetSessionId.slice(0, 8)} from ${senderLabel}`);

        // Auto-reply: send Claude's response back to the sender (unless this IS a reply — prevent loops)
        if (!isReply && sender.port) {
          // Use captured stream text; fall back to last saved assistant message
          let responseText = _capturedText.trim();
          if (!responseText) {
            const msgs = getMessages(targetSessionId);
            const lastAssistant = [...msgs].reverse().find(m => m.role === 'assistant');
            if (lastAssistant && lastAssistant.content) responseText = lastAssistant.content;
          }
          if (responseText) {
            const ai = loadAgentIdentity();
            responseText = responseText.slice(0, 8000);
            log(`Inject: auto-replying to ${sender.name || sender.port} with ${responseText.length} chars`);

            // Find sender's session to inject into
            fetchJson(`http://localhost:${sender.port}/api/sessions`).then(sessRes => {
              const sessions = sessRes?.data || [];
              const senderSession = (sender.sessionId && sessions.find(s => s.id === sender.sessionId))
                || sessions.find(s => s.isMain)
                || sessions[0];
              if (senderSession) {
                fetchJson(`http://localhost:${sender.port}/api/sessions/${senderSession.id}/inject`, {
                  method: 'POST',
                  body: {
                    message: responseText,
                    sender: {
                      name: ai.name || AGENT_DISPLAY,
                      agentId: ai.agentId || AGENT_ID,
                      server: SERVER_CONFIG.name || 'unknown',
                      lab: LAB.name || 'unknown',
                      port: PORT,
                      sessionId: targetSessionId,
                    },
                    priority: 'normal',
                    triggerAgent: false,
                    isReply: true,
                  },
                }).then(() => {
                  log(`Inject: auto-reply delivered to ${sender.name || sender.port}`);
                }).catch(err => {
                  log(`Inject: auto-reply delivery failed: ${err.message}`);
                });
              }
            }).catch(err => {
              log(`Inject: could not discover sender sessions: ${err.message}`);
            });
          }
        }
      }).catch(err => {
        log(`Inject: Claude error for session ${targetSessionId.slice(0, 8)}: ${err.message}`);
      });

      json(res, { data: { injected: true, triggered: true, inboxId: inboxEntry.id } });
    } else {
      json(res, { data: { injected: true, triggered: false, inboxId: inboxEntry.id, reason: triggerAgent ? 'session busy' : 'trigger not requested' } });
    }
    return;
  }

  // --- Agent Inbox API ---

  // GET /api/agent/inbox — list inbox messages
  if (p === '/api/agent/inbox' && m === 'GET') {
    const all = url.searchParams.get('all') === '1';
    json(res, { data: all ? readInbox() : getUndeliveredInbox() });
    return;
  }

  // POST /api/agent/inbox/clear — clear delivered or all messages
  if (p === '/api/agent/inbox/clear' && m === 'POST') {
    const body = await parseBody(req);
    clearInbox(body.onlyDelivered !== false);
    json(res, { data: { cleared: true } });
    return;
  }

  // POST /api/agent/inbox/deliver — mark specific messages as delivered
  if (p === '/api/agent/inbox/deliver' && m === 'POST') {
    const body = await parseBody(req);
    if (!body.ids || !Array.isArray(body.ids)) { json(res, { error: 'ids array required' }, 400); return; }
    markInboxDelivered(body.ids);
    json(res, { data: { delivered: true } });
    return;
  }

  // POST /api/agent/send — send a message to a remote agent via their inject endpoint
  if (p === '/api/agent/send' && m === 'POST') {
    const body = await parseBody(req);
    if (!body.targetPort) { json(res, { error: 'targetPort required' }, 400); return; }
    if (!body.message) { json(res, { error: 'message required' }, 400); return; }

    const ai = loadAgentIdentity();
    const sender = {
      name: ai.name || AGENT_DISPLAY,
      agentId: ai.agentId || AGENT_ID,
      server: SERVER_CONFIG.name || SERVER_CONFIG.id || 'unknown',
      lab: LAB.name || PLATFORM_ID || 'unknown',
      port: PORT,
      sessionId: body.fromSessionId || null,
    };

    // First discover the target agent's session to inject into
    const targetPort = body.targetPort;
    const targetSessionId = body.targetSessionId || null;
    const priority = body.priority || 'normal';
    const triggerAgent = body.triggerAgent !== false; // default true

    try {
      // If no target session specified, get their main session
      let sessionId = targetSessionId;
      if (!sessionId) {
        const sessRes = await fetchJson(`http://localhost:${targetPort}/api/sessions`);
        const sessions = sessRes?.data || [];
        const main = sessions.find(s => s.isMain);
        sessionId = main?.id || sessions[0]?.id;
        if (!sessionId) { json(res, { error: 'No sessions found on target agent' }, 404); return; }
      }

      // Send the inject request
      const injectRes = await fetchJson(`http://localhost:${targetPort}/api/sessions/${sessionId}/inject`, {
        method: 'POST',
        body: { message: body.message, sender, priority, triggerAgent },
      });

      json(res, { data: { sent: true, targetPort, targetSession: sessionId, response: injectRes } });
    } catch (err) {
      json(res, { error: `Failed to send to agent on port ${targetPort}: ${err.message}` }, 502);
    }
    return;
  }

  // --- Calculate year ---
  if (p === '/api/calculate' && m === 'GET') {
    const year = parseInt(url.searchParams.get('year'));
    if (isNaN(year)) { json(res, { error: 'Missing year' }, 400); return; }
    const clocks = getClocks();
    const sigs = getSignatures();
    const positions = {};
    for (const [name, clock] of Object.entries(clocks)) {
      const elapsed = year - clock.start_year_ad;
      if (elapsed < 0) { positions[name] = null; continue; }
      const cycle = clock.cycle_years;
      const jubilee = elapsed / cycle;
      const remainder = (elapsed % cycle) / cycle;
      positions[name] = { jubilee: Math.round(jubilee * 10000) / 10000, remainder: Math.round(remainder * 10000) / 10000, cycle: Math.floor(jubilee), yearInCycle: elapsed % cycle };
    }
    let signature = null;
    const cosmicR = positions.cosmic?.remainder;
    if (cosmicR != null) {
      for (const s of sigs) {
        if (Math.abs(cosmicR - parseFloat(s.remainder)) <= (s.tolerance || 0.01)) { signature = s.name; break; }
      }
    }
    const am = year + 4004;
    json(res, { data: { year, am, cosmicDay: Math.min(8, Math.floor(am / 1000) + 1), pctPlan: Math.round((am / 8000) * 10000) / 100, signature, positions } });
    return;
  }

  // --- Research log ---
  if (p === '/api/research-log' && m === 'GET') {
    const logPath = path.join(ROOT, 'kb', 'research-log.json');
    try { json(res, { data: JSON.parse(fs.readFileSync(logPath, 'utf8')) }); }
    catch { json(res, { data: [] }); }
    return;
  }
  if (p === '/api/research-log' && m === 'POST') {
    const body = await parseBody(req);
    const logPath = path.join(ROOT, 'kb', 'research-log.json');
    let entries = [];
    try { entries = JSON.parse(fs.readFileSync(logPath, 'utf8')); } catch {}
    const entry = { id: entries.length + 1, date: new Date().toISOString(), type: body.type || 'note', title: body.title || '', description: body.description || '', details: body.details || '' };
    entries.push(entry);
    fs.writeFileSync(logPath, JSON.stringify(entries, null, 2));
    json(res, { data: entry });
    return;
  }

  // --- Joint Sessions API (inter-agent communication) ---

  // Identity
  if (p === '/api/joint/whoami' && m === 'GET') {
    const ai = loadAgentIdentity();
    json(res, { data: { agentId: ai.agentId || AGENT_ID, agentName: ai.name || null, displayName: ai.name || AGENT_DISPLAY, serverId: SERVER_CONFIG.id, instance: INSTANCE_NAME, platform: PLATFORM_ID, port: PORT, icon: ai.icon || LAB.icon || '', color: ai.color || LAB.color || '' } });
    return;
  }

  // Discover agents
  if (p === '/api/joint/agents' && m === 'GET') {
    const agents = jointCmd('discover-agents');
    // Probe each agent to check if running
    const http = require('node:http');
    const probed = [];
    const probePromises = (Array.isArray(agents) ? agents : []).map(agent => {
      return new Promise(resolve => {
        const req = http.get(`http://localhost:${agent.port}/api/lab`, { timeout: 1500 }, (resp) => {
          let data = '';
          resp.on('data', c => data += c);
          resp.on('end', () => { agent.status = 'running'; resolve(); });
        });
        req.on('error', () => { agent.status = 'stopped'; resolve(); });
        req.on('timeout', () => { req.destroy(); agent.status = 'stopped'; resolve(); });
      });
    });
    await Promise.all(probePromises);
    json(res, { data: agents });
    return;
  }

  // List channels
  if (p === '/api/joint/channels' && m === 'GET') {
    json(res, { data: jointCmd('list-channels') });
    return;
  }

  // Create channel
  if (p === '/api/joint/channels' && m === 'POST') {
    const body = await parseBody(req);
    const result = jointCmd('create-channel', [body.name || '#unnamed', body.topic || '', AGENT_ID]);
    if (result.error) { json(res, result, 400); return; }
    // Auto-join creator
    jointCmd('join', [result.name, AGENT_ID, AGENT_DISPLAY, SERVER_CONFIG.id || 'local', INSTANCE_NAME, PORT, LAB.icon || '', LAB.color || '', 'agent']);
    json(res, { data: result });
    return;
  }

  // Channel routes: /api/joint/channels/:id/*
  const jointChannelMatch = p.match(/^\/api\/joint\/channels\/([^/]+)(?:\/(.*))?$/);
  if (jointChannelMatch) {
    const channelId = decodeURIComponent(jointChannelMatch[1]);
    const sub = jointChannelMatch[2] || '';

    // Channel info
    if (!sub && m === 'GET') {
      json(res, { data: jointCmd('channel-info', [channelId]) });
      return;
    }

    // Join channel
    if (sub === 'join' && m === 'POST') {
      const result = jointCmd('join', [channelId, AGENT_ID, AGENT_DISPLAY, SERVER_CONFIG.id || 'local', INSTANCE_NAME, PORT, LAB.icon || '', LAB.color || '', 'agent']);
      json(res, { data: result });
      return;
    }

    // Leave channel
    if (sub === 'leave' && m === 'POST') {
      const result = jointCmd('leave', [channelId, AGENT_ID]);
      json(res, { data: result });
      return;
    }

    // Members
    if (sub === 'members' && m === 'GET') {
      json(res, { data: jointCmd('members', [channelId]) });
      return;
    }

    // Post message
    if (sub === 'messages' && m === 'POST') {
      const body = await parseBody(req);
      const displayName = body.displayName || AGENT_DISPLAY;
      const agentId = body.agentId || AGENT_ID;
      const role = body.role || 'agent';
      const content = body.content || '';
      const result = jointCmd('post', [channelId, agentId, displayName, role, content, body.metadata ? JSON.stringify(body.metadata) : '']);
      if (result.error) { json(res, result, 400); return; }
      json(res, { data: result });

      // --- @mention auto-trigger ---
      // Check if message mentions this server's agent (and is not from this agent)
      const agentName = loadAgentIdentity().name || AGENT_DISPLAY;
      const mentionPatterns = [
        new RegExp(`@${agentName}\\b`, 'i'),
        new RegExp(`@${agentName.slice(0, 3)}\\b`, 'i'),
      ];
      const isSelfMessage = agentId === AGENT_ID;
      const isMentioned = mentionPatterns.some(p => p.test(content));

      if (isMentioned && !isSelfMessage) {
        // Rate limit check
        const now = Date.now();
        const limit = channelRateLimits.get(channelId);
        if (limit && now < limit.resetAt && limit.count >= 3) {
          const waitSec = Math.ceil((limit.resetAt - now) / 1000);
          log(`Rate limit hit for #${channelId} — ${waitSec}s remaining`);
          jointCmd('post', [channelId, 'system', 'System', 'system', `Rate limit reached — pausing ${agentName} responses for ${waitSec}s.`]);
        } else {
          // Agent-to-agent loop prevention
          const exchanges = channelAgentExchanges.get(channelId) || { lastAgentId: null, consecutiveCount: 0 };
          const isAgentSender = role === 'agent';
          if (isAgentSender && exchanges.lastAgentId && exchanges.lastAgentId !== agentId) {
            // This is an agent responding to another agent
            exchanges.consecutiveCount++;
          } else if (!isAgentSender) {
            // Human message — reset counter
            exchanges.consecutiveCount = 0;
          }
          exchanges.lastAgentId = agentId;
          channelAgentExchanges.set(channelId, exchanges);

          if (isAgentSender && exchanges.consecutiveCount > 2) {
            log(`Loop prevention: agents exchanged ${exchanges.consecutiveCount} messages in #${channelId}`);
            jointCmd('post', [channelId, 'system', 'System', 'system', `Conversation paused — agents have exchanged ${exchanges.consecutiveCount} messages. @Michael to continue.`]);
          } else {
            // Update rate limiter
            if (!limit || now >= limit.resetAt) {
              channelRateLimits.set(channelId, { count: 1, resetAt: now + 60000 });
            } else {
              limit.count++;
            }
            log(`@mention detected for ${agentName} in #${channelId} from ${displayName}`);
            try { invokeAgentInChannel(channelId, content, displayName); }
            catch (e) { log(`Auto-invoke error: ${e.message}`); }
          }
        }
      }

      // --- Cross-server @mention forwarding ---
      // If message mentions a REMOTE agent in this channel, forward invoke to their server
      // Note: no isSelfMessage guard here — local agent can mention remote agents
      {
        const members = jointCmd('members', [channelId]);
        if (Array.isArray(members)) {
          const http = require('node:http');
          for (const member of members) {
            // Skip local agent and the sender
            if (String(member.port) === String(PORT)) continue;
            if (member.agent_id === agentId) continue;
            const memberName = member.display_name || '';
            const firstName = memberName.split(/\s+/)[0] || memberName;
            const remoteMentionPatterns = [
              new RegExp(`@${memberName}\\b`, 'i'),
              firstName !== memberName ? new RegExp(`@${firstName}\\b`, 'i') : null,
              memberName.length >= 3 ? new RegExp(`@${memberName.slice(0, 3)}\\b`, 'i') : null,
            ].filter(Boolean);
            if (remoteMentionPatterns.some(p => p.test(content))) {
              log(`Cross-server @mention: forwarding invoke for ${memberName} to port ${member.port}`);
              const postData = JSON.stringify({ prompt: content, senderName: displayName });
              const invokeReq = http.request({
                hostname: 'localhost', port: parseInt(member.port),
                path: `/api/joint/channels/${encodeURIComponent(channelId)}/invoke`,
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(postData) }
              }, () => { /* fire and forget */ });
              invokeReq.on('error', (e) => log(`Cross-server invoke error (port ${member.port}): ${e.message}`));
              invokeReq.write(postData);
              invokeReq.end();
            }
          }
        }
      }
      return;
    }

    // Get messages (with polling support via since_seq)
    if (sub === 'messages' && m === 'GET') {
      const sinceSeq = url.searchParams.get('since_seq') || '0';
      const limit = url.searchParams.get('limit') || '100';
      json(res, { data: jointCmd('messages', [channelId, sinceSeq, limit]) });
      return;
    }

    // SSE stream — real-time message updates
    if (sub === 'stream' && m === 'GET') {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
      });
      res.write(':ok\n\n');
      let lastSeq = parseInt(url.searchParams.get('since_seq') || '0');
      const interval = setInterval(() => {
        try {
          const msgs = jointCmd('messages', [channelId, String(lastSeq), '50']);
          if (Array.isArray(msgs)) {
            for (const msg of msgs) {
              res.write(`data: ${JSON.stringify(msg)}\n\n`);
              if (msg.seq > lastSeq) lastSeq = msg.seq;
            }
          }
        } catch (e) { /* ignore polling errors */ }
      }, 1500);
      req.on('close', () => clearInterval(interval));
      return;
    }

    // Invoke — ask this instance's agent to respond in the channel
    if (sub === 'invoke' && m === 'POST') {
      const body = await parseBody(req);
      const prompt = body.prompt || 'Please respond to the conversation in this joint channel.';
      // Post system message and respond immediately (don't block)
      jointCmd('post', [channelId, 'system', 'System', 'system', `Invoking ${AGENT_DISPLAY}...`]);
      json(res, { data: { ok: true, message: `Invocation sent to ${AGENT_DISPLAY}` } });
      // Spawn Claude asynchronously — response will appear in channel when ready
      try { invokeAgentInChannel(channelId, prompt, body.senderName || null); }
      catch (e) { log(`Invoke error: ${e.message}`); }
      return;
    }
  }

  // 404
  res.writeHead(404, { 'Content-Type': 'text/plain' });
  res.end('Not Found');
});

server.listen(PORT, () => {
  const events = getEvents();
  console.log('');
  console.log('  ===================================');
  console.log(`  ${LAB.icon || '✦'}  ${LAB.name || 'Lab'} Server`);
  console.log('  ===================================');
  console.log(`  URL:     http://localhost:${PORT}`);
  console.log(`  Project: ${ROOT}`);
  console.log(`  Events:  ${events.length}`);
  console.log(`  Claude:  ${CLAUDE_BIN}`);
  console.log(`  Agent:   ${AGENT_ID}`);
  console.log(`  Log:     ${LOG_FILE}`);
  console.log('  ===================================');
  console.log('');
  // Initialize joint sessions database
  jointCmd('init');
  // Ensure main session exists
  const mainSession = getOrCreateMainSession();
  console.log(`  Main:    ${mainSession.id.slice(0,8)} (${mainSession.title})`);
  log(`Server started — ${LAB.name || 'Lab'} on port ${PORT} — agent: ${AGENT_ID}`);
});
