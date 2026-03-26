#!/usr/bin/env python3
"""
Genesis IDE — Platform Manager
Manages lab platforms: list, create, start, stop, test, list instances, create instances.
"""

import sys
import os
import json
import re
import shutil
import subprocess
import html as html_mod
from pathlib import Path
from datetime import datetime

GENESIS_DIR = Path(os.environ.get('LAB_INSTANCE', Path(__file__).parent.parent))
PLATFORMS_FILE = GENESIS_DIR / 'platforms.json'
TEMPLATE_DIR = GENESIS_DIR / 'template'
T9_ROOT = Path(os.environ.get('SERVER_ROOT', GENESIS_DIR.parent))

def h(s):
    return html_mod.escape(str(s)) if s else ''

def resolve_platform_path(p):
    """Resolve a platform path — supports both absolute and relative (to server root) paths."""
    raw = Path(p)
    if raw.is_absolute():
        return raw
    return T9_ROOT / raw

def load_platforms():
    try:
        return json.loads(PLATFORMS_FILE.read_text())
    except:
        return []

def save_platforms(platforms):
    PLATFORMS_FILE.write_text(json.dumps(platforms, indent=2))

def slugify(text):
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    return s.strip('-')[:60]


# ─── LIST PLATFORMS ──────────────────────────────────────────────────────────

def cmd_list():
    platforms = load_platforms()
    if not platforms:
        print("<!--html-->")
        print('<div class="skill-header">No Platforms</div>')
        print('<div class="skill-subtext">No platforms registered. Use /create-platform to create one.</div>')
        return

    cards = ''
    for p in platforms:
        path = resolve_platform_path(p['path'])
        exists = path.exists()
        # Check if launcher is running
        port = None
        try:
            launcher_cfg = path / 'launcher.js'
            if launcher_cfg.exists():
                # Try to detect port from launcher or first instance
                for inst_dir in (path / 'instances').iterdir():
                    lab_json = inst_dir / 'lab.json'
                    if lab_json.exists():
                        cfg = json.loads(lab_json.read_text())
                        port = cfg.get('port')
                        break
        except:
            pass

        # Count instances
        inst_count = 0
        try:
            inst_count = len([d for d in (path / 'instances').iterdir() if (d / 'lab.json').exists()])
        except:
            pass

        status = 'available' if exists else 'missing'
        cards += f'''<div class="skill-card" onclick="labType('Tell me about the {h(p["name"])} platform at {h(p["path"])}')">
            <div style="display:flex;justify-content:space-between;align-items:start">
                <div class="sc-title">{h(p.get("icon","⚗"))} {h(p["name"])}</div>
                <span class="sc-badge {h(status)}">{h(status)}</span>
            </div>
            <div class="sc-meta">{h(p.get("description",""))}</div>
            <div class="sc-meta" style="margin-top:4px">{inst_count} instances · {h(p["path"])}</div>
            <div style="margin-top:6px">
                <span class="skill-btn" onclick="event.stopPropagation();labSend('/instances {h(p["id"])}')">Instances</span>
                <span class="skill-btn" onclick="event.stopPropagation();labSend('/start {h(p["id"])}')">Start</span>
                <span class="skill-btn" onclick="event.stopPropagation();labSend('/stop {h(p["id"])}')">Stop</span>
                <span class="skill-btn" onclick="event.stopPropagation();labSend('/versions {h(p["id"])}')">Versions</span>
            </div>
        </div>'''

    out = f'''<!--html-->
    <div class="skill-header">Platforms ({len(platforms)})</div>
    <div class="skill-subtext">Click a platform to explore it. Use /create-platform to add a new one.</div>
    <div class="skill-grid">{cards}</div>
    <div style="padding:8px">
        <span class="skill-btn primary" onclick="labType('Create a new platform for [describe purpose]')">+ New Platform</span>
    </div>'''
    print(out)


# ─── LIST INSTANCES ──────────────────────────────────────────────────────────

def cmd_instances(platform_id):
    if not platform_id:
        print("Usage: /instances <platform-id>")
        return

    platform_id = platform_id.strip()
    platforms = load_platforms()
    p = next((p for p in platforms if p['id'] == platform_id), None)
    if not p:
        print(f"Platform not found: {platform_id}")
        return

    path = resolve_platform_path(p['path'])
    instances_dir = path / 'instances'
    if not instances_dir.exists():
        print(f"No instances directory at {instances_dir}")
        return

    cards = ''
    for inst_dir in sorted(instances_dir.iterdir()):
        lab_json = inst_dir / 'lab.json'
        if not lab_json.exists():
            continue
        try:
            cfg = json.loads(lab_json.read_text())
        except:
            continue

        name = cfg.get('name', inst_dir.name)
        port = cfg.get('port', '?')
        has_frontend = (inst_dir / 'frontend' / 'server.js').exists()
        fe_port = port + 70 if isinstance(port, int) and has_frontend else None

        cards += f'''<div class="skill-card">
            <div class="sc-title">{h(cfg.get("icon","⚗"))} {h(name)}</div>
            <div class="sc-meta">Port: {port}{f" · Frontend: {fe_port}" if fe_port else ""} · Model: {h(cfg.get("model","opus"))}</div>
            <div style="margin-top:6px">
                <span class="skill-btn" onclick="labType('Open http://localhost:{port} in the Site tab')">Open Lab</span>
                {f'<span class="skill-btn" onclick="labType(\'Open http://localhost:{fe_port} in the Site tab\')">View Site</span>' if fe_port else ''}
            </div>
        </div>'''

    out = f'''<!--html-->
    <div class="skill-header">{h(p["name"])} — Instances</div>
    <div class="skill-subtext">{h(p["path"])}</div>
    <div class="skill-grid">{cards}</div>
    <div style="padding:8px">
        <span class="skill-btn primary" onclick="labType('Create a new instance in {h(platform_id)} for [describe purpose]')">+ New Instance</span>
        <span class="skill-btn" onclick="labSend('/platforms')">Back to Platforms</span>
    </div>'''
    print(out)


# ─── CREATE PLATFORM ─────────────────────────────────────────────────────────

def cmd_create(args):
    if not args:
        print("Usage: /create-platform <name> [description]")
        return

    parts = args.strip().split(None, 1)
    name = parts[0]
    description = parts[1] if len(parts) > 1 else ''
    slug = slugify(name)
    platform_dir = T9_ROOT / f'{slug}-lab'

    if platform_dir.exists():
        print(f"Directory already exists: {platform_dir}")
        return

    # Check template exists
    if not TEMPLATE_DIR.exists() or not (TEMPLATE_DIR / 'core' / 'server.js').exists():
        print("Template not found. Run setup first.")
        return

    # Create platform structure — NO local core/, plugins/, or skills/
    # All platforms use genesis/template/core/ and genesis/template/plugins/ (the global source of truth)
    platform_dir.mkdir(parents=True)
    (platform_dir / 'instances').mkdir()
    (platform_dir / 'docs').mkdir()
    (platform_dir / 'logs').mkdir()

    # Copy launcher.js (rewired to point to genesis template)
    shutil.copy2(TEMPLATE_DIR / 'launcher.js', platform_dir / 'launcher.js')

    # Copy instance-template for creating instances later
    if (TEMPLATE_DIR / 'instance-template').exists():
        shutil.copytree(TEMPLATE_DIR / 'instance-template', platform_dir / 'instance-template',
                        ignore=shutil.ignore_patterns('__pycache__'))

    # Replace placeholders in all text files
    now = datetime.now().strftime('%Y-%m-%d')
    replacements = {
        '{{PLATFORM_NAME}}': name,
        '{{PLATFORM_DESC}}': description or 'No description provided',
        '{{PLATFORM_SLUG}}': slug,
        '{{DATE}}': now,
    }
    for f in platform_dir.rglob('*'):
        if f.is_file() and f.suffix in ('.md', '.json', '.js', '.html', '.css', '.sh', '.txt'):
            try:
                content = f.read_text(errors='replace')
                changed = False
                for k, v in replacements.items():
                    if k in content:
                        content = content.replace(k, v)
                        changed = True
                if changed:
                    f.write_text(content)
            except:
                pass

    # Overwrite SYSTEM-DESIGN.md with full content
    (platform_dir / 'docs' / 'SYSTEM-DESIGN.md').write_text(f"""# {name} — System Design

**Platform**: {name}
**Created**: {now}
**Description**: {description or 'No description provided'}

## Architecture

This platform follows the Genesis Lab architecture:
- `launcher.js` — instance manager (boots instances from genesis/template/core/server.js)
- `instances/` — individual labs with their own data, KB, frontend
- Shared server, plugins, and skills live in genesis/template/ (global source of truth)
- Instance-local scripts go in instances/<name>/scripts/

## Instances

(Add instances as they are created)

## Data Flow

(Describe the data flow for this platform's domain)
""")

    # CLAUDE.md
    (platform_dir / 'CLAUDE.md').write_text(f"""# {name}

{description or 'A lab platform for research and analysis.'}

## Architecture
- Launcher at the platform root manages instances
- Each instance has its own lab (AI chat + file browser + skills) and optional frontend
- Shared plugins in plugins/ are available to all instances
- Instance-specific scripts go in instances/<name>/scripts/

## Development Rules
- Always run /snapshot before making data changes
- Use /rebuild after modifying source data
- Test changes before committing
""")

    # Initialize git
    subprocess.run(['git', 'init'], cwd=platform_dir, capture_output=True)
    subprocess.run(['git', 'add', '-A'], cwd=platform_dir, capture_output=True)
    subprocess.run(['git', 'commit', '-m', f'Initial platform: {name}'], cwd=platform_dir, capture_output=True)

    # Register in platforms.json
    platforms = load_platforms()
    platforms.append({
        'id': slug,
        'name': name,
        'description': description,
        'path': platform_dir.name,  # relative to server root
        'icon': '⚗',
        'color': '#4a8fe7',
        'instances': 0
    })
    save_platforms(platforms)

    out = f'''<!--html-->
    <div class="skill-header">Platform Created: {h(name)}</div>
    <div class="skill-subtext">{h(str(platform_dir))}</div>
    <div style="padding:8px">
        <span class="skill-btn primary" onclick="labSend('/create-instance {h(slug)} main')">Create First Instance</span>
        <span class="skill-btn" onclick="labSend('/platforms')">View Platforms</span>
    </div>'''
    print(out)


# ─── CREATE INSTANCE ─────────────────────────────────────────────────────────

def cmd_create_instance(args):
    if not args or len(args.strip().split()) < 2:
        print("Usage: /create-instance <platform-id> <name> [description]")
        return

    parts = args.strip().split(None, 2)
    platform_id = parts[0]
    inst_name = parts[1]
    inst_desc = parts[2] if len(parts) > 2 else ''

    platforms = load_platforms()
    p = next((p for p in platforms if p['id'] == platform_id), None)
    if not p:
        print(f"Platform not found: {platform_id}")
        return

    platform_dir = resolve_platform_path(p['path'])
    inst_slug = slugify(inst_name)
    inst_dir = platform_dir / 'instances' / inst_slug

    if inst_dir.exists():
        print(f"Instance already exists: {inst_dir}")
        return

    # Check for instance template
    inst_template = TEMPLATE_DIR / 'instance-template'
    fe_template = TEMPLATE_DIR / 'frontend-template'

    if inst_template.exists():
        shutil.copytree(inst_template, inst_dir, ignore=shutil.ignore_patterns('__pycache__'))
    else:
        for d in ['data', 'kb/sessions/messages', 'output', 'docs']:
            (inst_dir / d).mkdir(parents=True, exist_ok=True)

    # Copy frontend template
    if fe_template.exists() and not (inst_dir / 'frontend').exists():
        shutil.copytree(fe_template, inst_dir / 'frontend', ignore=shutil.ignore_patterns('__pycache__'))

    # Find next port
    used_ports = set()
    try:
        for d in (platform_dir / 'instances').iterdir():
            lj = d / 'lab.json'
            if lj.exists():
                cfg = json.loads(lj.read_text())
                used_ports.add(cfg.get('port', 0))
    except:
        pass
    port = 3210
    while port in used_ports:
        port += 1

    now = datetime.now().strftime('%Y-%m-%d')

    # Replace placeholders in copied template files
    replacements = {
        '{{INSTANCE_NAME}}': inst_name,
        '{{INSTANCE_DESC}}': inst_desc or 'No description provided',
        '{{PLATFORM_NAME}}': p['name'],
        '{{PORT}}': str(port),
        '{{FRONTEND_PORT}}': str(port + 70),
        '{{DATE}}': now,
    }
    for f in inst_dir.rglob('*'):
        if f.is_file() and f.suffix in ('.md', '.json', '.js', '.html', '.css', '.txt'):
            try:
                content = f.read_text(errors='replace')
                changed = False
                for k, v in replacements.items():
                    if k in content:
                        content = content.replace(k, v)
                        changed = True
                if changed:
                    f.write_text(content)
            except:
                pass

    # Write lab.json
    lab_config = {
        'name': inst_name,
        'description': inst_desc,
        'icon': '⚗',
        'color': '#4a8fe7',
        'port': port,
        'model': 'opus',
        'role': f'You are the {inst_name} AI assistant. You have full access to the project files, scripts, and knowledge base.',
        'plugins': ['core/*'],
        'apis': [],
        'dataDir': 'data',
        'scriptsDir': 'scripts',
        'kbDir': 'kb',
        'outputDir': 'output',
        'skills': []
    }
    (inst_dir / 'lab.json').write_text(json.dumps(lab_config, indent=2))

    # Write settings.json
    settings = {
        'enforcements': {'auto-snapshot': True, 'schema-validation': True, 'circuit-breaker': True},
        'skills': {},
        'frontend': {'pages': {'home': True}, 'theme': 'dark-blue'},
        'plugins': ['core/*']
    }
    (inst_dir / 'settings.json').write_text(json.dumps(settings, indent=2))

    # Write sessions files
    (inst_dir / 'kb' / 'sessions' / 'sessions.json').write_text('[]')
    (inst_dir / 'kb' / 'sessions' / 'projects.json').write_text('[]')

    # Write CLAUDE.md
    (inst_dir / 'CLAUDE.md').write_text(f'# {inst_name}\n\n{inst_desc}\n')

    # Write INSTANCE-DESIGN.md
    (inst_dir / 'docs' / 'INSTANCE-DESIGN.md').write_text(f"""# {inst_name} — Instance Design

**Instance**: {inst_name}
**Platform**: {p['name']}
**Port**: {port}
**Created**: {now}
**Description**: {inst_desc or 'No description provided'}

## Purpose

(Describe the purpose of this instance)

## Data Model

(Describe the data this instance works with)

## Skills

(List custom skills as they are added)
""")

    # Copy frontend template if available (skip if already exists from instance-template)
    if fe_template.exists() and not (inst_dir / 'frontend').exists():
        shutil.copytree(fe_template, inst_dir / 'frontend')
    elif not (inst_dir / 'frontend').exists():
        # Create minimal frontend
        fe_dir = inst_dir / 'frontend' / 'public'
        fe_dir.mkdir(parents=True, exist_ok=True)
        (inst_dir / 'frontend' / 'server.js').write_text(f"""#!/usr/bin/env node
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const PORT = parseInt(process.env.PORT || {port + 70});
let LAB_PORT = {port};
try {{ const c = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'lab.json'), 'utf8')); LAB_PORT = c.port || {port}; }} catch {{}}
const MIME = {{ '.html':'text/html','.css':'text/css','.js':'text/javascript','.json':'application/json' }};
const server = http.createServer((req, res) => {{
  const url = new URL(req.url, 'http://localhost:' + PORT);
  if (url.pathname.startsWith('/api/')) {{
    const opts = {{ hostname:'127.0.0.1', port:LAB_PORT, path:req.url, method:req.method, headers:{{ ...req.headers, host:'127.0.0.1:'+LAB_PORT }} }};
    const proxy = http.request(opts, lr => {{ res.writeHead(lr.statusCode, lr.headers); lr.pipe(res); }});
    proxy.on('error', () => {{ res.writeHead(502); res.end('Backend unavailable'); }});
    req.pipe(proxy);
    return;
  }}
  let fp = path.join(__dirname, 'public', url.pathname === '/' ? 'index.html' : url.pathname);
  if (fs.existsSync(fp) && fs.statSync(fp).isFile()) {{
    const ext = path.extname(fp);
    res.writeHead(200, {{ 'Content-Type': (MIME[ext]||'application/octet-stream') + (ext==='.html'||ext==='.css'||ext==='.js'?'; charset=utf-8':'') }});
    res.end(fs.readFileSync(fp));
  }} else {{
    fp = path.join(__dirname, 'public', 'index.html');
    if (fs.existsSync(fp)) {{ res.writeHead(200, {{ 'Content-Type':'text/html; charset=utf-8' }}); res.end(fs.readFileSync(fp)); }}
    else {{ res.writeHead(404); res.end('Not found'); }}
  }}
}});
server.listen(PORT, () => console.log('Frontend: http://localhost:' + PORT));
""")
        # Minimal index.html
        (fe_dir / 'index.html').write_text(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{inst_name}</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,sans-serif;background:#0a0b10;color:#e4e4ec;min-height:100vh;display:flex;align-items:center;justify-content:center}}
h1{{font-size:28px;font-weight:300;color:#c8a55a}}</style>
</head><body><h1>{inst_name}</h1></body></html>""")

    # Update instance count
    p['instances'] = p.get('instances', 0) + 1
    save_platforms(platforms)

    out = f'''<!--html-->
    <div class="skill-header">Instance Created: {h(inst_name)}</div>
    <div class="skill-subtext">Port: {port} · Frontend: {port + 70} · Path: {h(str(inst_dir))}</div>
    <div style="padding:8px">
        <span class="skill-btn" onclick="labSend('/instances {h(platform_id)}')">View Instances</span>
        <span class="skill-btn" onclick="labSend('/platforms')">Platforms</span>
    </div>'''
    print(out)


# ─── START PLATFORM ──────────────────────────────────────────────────────────

def cmd_start(platform_id):
    if not platform_id:
        print("Usage: /start <platform-id>")
        return

    platforms = load_platforms()
    p = next((p for p in platforms if p['id'] == platform_id.strip()), None)
    if not p:
        print(f"Platform not found: {platform_id}")
        return

    path = resolve_platform_path(p['path'])
    launcher = path / 'launcher.js'
    if not launcher.exists():
        print(f"No launcher.js found at {path}")
        return

    # Start launcher in background
    proc = subprocess.Popen(
        ['node', str(launcher)],
        cwd=str(path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )

    out = f'''<!--html-->
    <div class="skill-header">Platform Starting: {h(p["name"])}</div>
    <div class="skill-subtext">Launcher PID: {proc.pid} · Open the launcher to start instances</div>
    <div style="padding:8px">
        <span class="skill-btn" onclick="labSend('/instances {h(platform_id.strip())}')">View Instances</span>
    </div>'''
    print(out)


# ─── STOP PLATFORM ───────────────────────────────────────────────────────────

def cmd_stop(platform_id):
    if not platform_id:
        print("Usage: /stop <platform-id>")
        return

    platforms = load_platforms()
    p = next((p for p in platforms if p['id'] == platform_id.strip()), None)
    if not p:
        print(f"Platform not found: {platform_id}")
        return

    # Kill processes on known ports
    path = resolve_platform_path(p['path'])
    killed = 0
    try:
        for inst_dir in (path / 'instances').iterdir():
            lj = inst_dir / 'lab.json'
            if lj.exists():
                cfg = json.loads(lj.read_text())
                port = cfg.get('port')
                if port:
                    for pt in [port, port + 70]:
                        result = subprocess.run(['lsof', '-ti', f':{pt}'], capture_output=True, text=True)
                        for pid in result.stdout.strip().split('\n'):
                            if pid:
                                subprocess.run(['kill', '-9', pid], capture_output=True)
                                killed += 1
    except:
        pass

    print(f"<!--html-->")
    print(f'<div class="skill-header">Platform Stopped: {h(p["name"])}</div>')
    print(f'<div class="skill-subtext">Killed {killed} processes</div>')


# ─── TEST ────────────────────────────────────────────────────────────────────

def cmd_test(platform_id):
    if not platform_id:
        print("Usage: /test <platform-id>")
        return

    platforms = load_platforms()
    p = next((p for p in platforms if p['id'] == platform_id.strip()), None)
    if not p:
        print(f"Platform not found: {platform_id}")
        return

    path = resolve_platform_path(p['path'])
    errors = []
    checked = 0

    # Check JS
    for f in path.rglob('*.js'):
        if '.git' in f.parts or 'node_modules' in f.parts:
            continue
        checked += 1
        result = subprocess.run(['node', '--check', str(f)], capture_output=True, text=True)
        if result.returncode != 0:
            errors.append(f'JS: {f.relative_to(path)} — {result.stderr.strip()[:100]}')

    # Check Python
    for f in path.rglob('*.py'):
        if '.git' in f.parts or '__pycache__' in f.parts:
            continue
        checked += 1
        result = subprocess.run(['python3', '-m', 'py_compile', str(f)], capture_output=True, text=True)
        if result.returncode != 0:
            errors.append(f'PY: {f.relative_to(path)} — {result.stderr.strip()[:100]}')

    # Check JSON configs
    for f in path.rglob('lab.json'):
        if '.git' in f.parts:
            continue
        checked += 1
        try:
            json.loads(f.read_text())
        except Exception as e:
            errors.append(f'JSON: {f.relative_to(path)} — {str(e)[:100]}')

    if errors:
        err_html = ''.join(f'<div style="color:#e7554a;font-size:11px;padding:2px 0">{h(e)}</div>' for e in errors)
        print(f'<!--html--><div class="skill-header" style="color:#e7554a">Test Failed ({len(errors)} errors)</div><div style="padding:8px">{err_html}</div>')
    else:
        print(f'<!--html--><div class="skill-header" style="color:#3ac77e">All Tests Passed</div><div class="skill-subtext">{checked} files checked, 0 errors</div>')


# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    args = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else ''

    if command == 'list': cmd_list()
    elif command == 'create': cmd_create(args)
    elif command == 'instances': cmd_instances(args)
    elif command == 'create-instance': cmd_create_instance(args)
    elif command == 'start': cmd_start(args)
    elif command == 'stop': cmd_stop(args)
    elif command == 'test': cmd_test(args)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
