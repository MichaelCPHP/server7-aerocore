#!/usr/bin/env python3
"""
Server Manager — Create, list, and manage server environments.

Usage:
  python3 server_manager.py create --name DEV --type development --port 4000
  python3 server_manager.py create --name DEV --type development --port 4000 --platforms jubilee-lab,sapc-lab
  python3 server_manager.py list
"""

import os, sys, json, shutil, subprocess
from pathlib import Path
from datetime import datetime
import html as html_mod

# Paths
GENESIS_DIR = Path(os.environ.get('LAB_INSTANCE', Path(__file__).parent.parent))
SERVER_ROOT = Path(os.environ.get('SERVER_ROOT', GENESIS_DIR.parent))
DRIVE_ROOT = SERVER_ROOT.parent  # e.g., /Volumes/T9 Drive 1/
DEPLOYMENT_FILE = DRIVE_ROOT / 'deployment.json'

def h(s):
    return html_mod.escape(str(s)) if s else ''

def load_deployment():
    try:
        return json.loads(DEPLOYMENT_FILE.read_text())
    except:
        # Bootstrap: auto-register the source server if deployment.json doesn't exist
        deployment = {"version": "1.0", "driveRoot": str(DRIVE_ROOT), "servers": []}
        source_config = load_server_config(SERVER_ROOT)
        if source_config:
            deployment['servers'].append({
                "id": source_config.get('id', 'server1'),
                "name": source_config.get('name', SERVER_ROOT.name),
                "type": source_config.get('type', 'production'),
                "path": SERVER_ROOT.name,
                "portBase": source_config.get('portBase', 3000),
                "created": source_config.get('created', 'unknown')
            })
        return deployment

def save_deployment(data):
    DEPLOYMENT_FILE.write_text(json.dumps(data, indent=2))

def load_server_config(server_dir):
    try:
        return json.loads((server_dir / 'server.json').read_text())
    except:
        return {}

# --- Data exclusion patterns ---
# These paths (relative to an instance dir) are NEVER copied during duplication
EXCLUDE_FILES = {
    'data', 'kb/sessions/messages', 'output', 'logs',
    '__pycache__', '.DS_Store'
}

# These file extensions in session dirs should not be copied
SKIP_EXTENSIONS = {'.json'}  # session message files

def should_exclude(rel_path_str):
    """Check if a relative path should be excluded during duplication."""
    parts = rel_path_str.split(os.sep)
    for excl in EXCLUDE_FILES:
        excl_parts = excl.split('/')
        for i in range(len(parts) - len(excl_parts) + 1):
            if parts[i:i+len(excl_parts)] == excl_parts:
                return True
    return False

def copy_server_structure(source_dir, target_dir, platforms=None):
    """
    Copy a server's structure without instance data.

    Copies:
    - genesis/ (template, scripts, skills, plugins, lab.json, start.command)
    - Platform dirs (launcher.js, CLAUDE.md, docs/, instance-template/)
    - Instance structure (lab.json, settings.json, CLAUDE.md, docs/, scripts/)

    Does NOT copy:
    - Instance data (data/*, kb/sessions/messages/*, output/*, logs/*)
    - Genesis IDE chat sessions (kb/sessions/messages/*)
    - __pycache__/, .DS_Store
    """
    source = Path(source_dir)
    target = Path(target_dir)

    # 1. Copy genesis/ (the template system)
    src_genesis = source / 'genesis'
    tgt_genesis = target / 'genesis'

    if src_genesis.exists():
        # Copy everything except session messages and logs
        for item in src_genesis.rglob('*'):
            rel = item.relative_to(src_genesis)
            rel_str = str(rel)

            # Skip git, pycache, DS_Store
            if '.git' in rel.parts or '__pycache__' in rel.parts or '.DS_Store' in rel.parts:
                continue
            # Skip session message files (large JSON blobs)
            if 'kb/sessions/messages' in rel_str and item.is_file():
                continue
            # Skip log files
            if 'logs' in rel.parts and item.suffix == '.log':
                continue

            tgt_path = tgt_genesis / rel
            if item.is_dir():
                tgt_path.mkdir(parents=True, exist_ok=True)
            else:
                tgt_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, tgt_path)

        # Create empty session files
        sessions_dir = tgt_genesis / 'kb' / 'sessions'
        sessions_dir.mkdir(parents=True, exist_ok=True)
        (sessions_dir / 'messages').mkdir(exist_ok=True)
        (sessions_dir / 'sessions.json').write_text('[]')
        (sessions_dir / 'projects.json').write_text('[]')

    # 2. Copy platform directories
    src_platforms = []
    try:
        platforms_json = json.loads((src_genesis / 'platforms.json').read_text())
        src_platforms = [p['path'] for p in platforms_json]
    except:
        pass

    # Filter to requested platforms
    if platforms:
        src_platforms = [p for p in src_platforms if p in platforms]

    for platform_path in src_platforms:
        src_platform = source / platform_path
        tgt_platform = target / platform_path

        if not src_platform.exists():
            continue

        tgt_platform.mkdir(parents=True, exist_ok=True)

        # Copy platform-level files
        for item in ['launcher.js', 'CLAUDE.md', 'start.command']:
            src_file = src_platform / item
            if src_file.exists():
                shutil.copy2(src_file, tgt_platform / item)

        # Copy docs/
        src_docs = src_platform / 'docs'
        if src_docs.exists():
            shutil.copytree(src_docs, tgt_platform / 'docs', dirs_exist_ok=True,
                          ignore=shutil.ignore_patterns('__pycache__', '.DS_Store'))

        # Copy instance-template/
        src_tmpl = src_platform / 'instance-template'
        if src_tmpl.exists():
            shutil.copytree(src_tmpl, tgt_platform / 'instance-template', dirs_exist_ok=True,
                          ignore=shutil.ignore_patterns('__pycache__', '.DS_Store'))

        # Copy instances (structure only, no data)
        src_instances = src_platform / 'instances'
        if src_instances.exists():
            for inst_dir in src_instances.iterdir():
                if not inst_dir.is_dir():
                    continue
                tgt_inst = tgt_platform / 'instances' / inst_dir.name
                tgt_inst.mkdir(parents=True, exist_ok=True)

                # Copy config files
                for cfg_file in ['lab.json', 'settings.json', 'CLAUDE.md']:
                    src_cfg = inst_dir / cfg_file
                    if src_cfg.exists():
                        shutil.copy2(src_cfg, tgt_inst / cfg_file)

                # Copy docs/ and scripts/ (structure, not data)
                for subdir in ['docs', 'scripts']:
                    src_sub = inst_dir / subdir
                    if src_sub.exists():
                        shutil.copytree(src_sub, tgt_inst / subdir, dirs_exist_ok=True,
                                      ignore=shutil.ignore_patterns('__pycache__', '.DS_Store'))

                # Create empty data directories
                for empty_dir in ['data', 'kb/sessions/messages', 'output', 'logs']:
                    (tgt_inst / empty_dir).mkdir(parents=True, exist_ok=True)

                # Create empty session files
                (tgt_inst / 'kb' / 'sessions' / 'sessions.json').write_text('[]')
                (tgt_inst / 'kb' / 'sessions' / 'projects.json').write_text('[]')

        # Copy logs dir (empty)
        (tgt_platform / 'logs').mkdir(exist_ok=True)

        # Init git for the platform
        subprocess.run(['git', 'init'], cwd=tgt_platform, capture_output=True)
        subprocess.run(['git', 'add', '-A'], cwd=tgt_platform, capture_output=True)
        subprocess.run(['git', 'commit', '-m', f'Initial server clone from {source.name}'],
                      cwd=tgt_platform, capture_output=True)

    # Init git for genesis
    subprocess.run(['git', 'init'], cwd=tgt_genesis, capture_output=True)
    subprocess.run(['git', 'add', '-A'], cwd=tgt_genesis, capture_output=True)
    subprocess.run(['git', 'commit', '-m', f'Initial server clone from {source.name}'],
                  cwd=tgt_genesis, capture_output=True)


def rewrite_ports(server_dir, new_port_base):
    """Rewrite all port numbers in a server to use the new port base."""
    old_base = 3000  # default original base
    offset = new_port_base - old_base

    if offset == 0:
        return

    # Rewrite genesis/lab.json
    genesis_lab = server_dir / 'genesis' / 'lab.json'
    if genesis_lab.exists():
        config = json.loads(genesis_lab.read_text())
        if 'port' in config:
            config['port'] = new_port_base + 199
        genesis_lab.write_text(json.dumps(config, indent=2))

    # Rewrite all instance lab.json files
    for lab_json in server_dir.rglob('instances/*/lab.json'):
        try:
            config = json.loads(lab_json.read_text())
            if 'port' in config:
                config['port'] = config['port'] + offset
            lab_json.write_text(json.dumps(config, indent=2))
        except:
            pass

    # Rewrite instance-template lab.json files
    for tmpl_json in server_dir.rglob('instance-template/lab.json'):
        try:
            config = json.loads(tmpl_json.read_text())
            if 'port' in config:
                config['port'] = config['port'] + offset
            tmpl_json.write_text(json.dumps(config, indent=2))
        except:
            pass


def cmd_create(args):
    """Create a new server environment by duplicating the source server."""
    import argparse, shlex

    # Skill system may pass all user args as a single string — split it
    if len(args) == 1 and ' ' in args[0] and not args[0].startswith('--'):
        args = shlex.split(args[0])

    parser = argparse.ArgumentParser()
    # Support both positional and flag-based: /create-server DEV development 4000
    #   OR: /create-server --name DEV --type development --port 4000
    parser.add_argument('positional', nargs='*', default=[], help='name [type] [port]')
    parser.add_argument('--name', default=None, help='Server name (e.g., DEV, STAGING)')
    parser.add_argument('--type', default=None, help='Server type (production/development/staging)')
    parser.add_argument('--port', type=int, default=None, help='Port base (e.g., 4000)')
    parser.add_argument('--platforms', default=None, help='Comma-separated platform list (default: all)')
    parsed = parser.parse_args(args)

    # Merge positional args into named args
    pos = parsed.positional
    name = parsed.name or (pos[0] if len(pos) > 0 else None)
    stype = parsed.type or (pos[1] if len(pos) > 1 else 'development')
    port = parsed.port or (int(pos[2]) if len(pos) > 2 else None)

    if not name or not port:
        print('<!--html--><div class="skill-error">Usage: /create-server &lt;name&gt; &lt;type&gt; &lt;port-base&gt;<br>Example: /create-server DEV development 4000</div>')
        return

    parsed.name = name
    parsed.type = stype
    parsed.port = port

    name_upper = parsed.name.upper()

    # Determine server number by scanning existing SERVER* directories + deployment registry
    deployment = load_deployment()
    existing_nums = set()
    for s in deployment['servers']:
        # Extract number from SERVER{N}-... pattern
        sname = s.get('name', '')
        if sname.startswith('SERVER'):
            try:
                num_str = sname.split('-')[0].replace('SERVER', '')
                existing_nums.add(int(num_str))
            except ValueError:
                pass
    # Also scan drive for SERVER* directories not in registry
    for d in DRIVE_ROOT.iterdir():
        if d.is_dir() and d.name.startswith('SERVER'):
            try:
                num_str = d.name.split('-')[0].replace('SERVER', '')
                existing_nums.add(int(num_str))
            except ValueError:
                pass
    server_num = max(existing_nums, default=0) + 1
    server_folder = f'SERVER{server_num}-{name_upper}'
    target_dir = DRIVE_ROOT / server_folder

    if target_dir.exists():
        print(f'<!--html--><div class="skill-error">Server directory already exists: {h(server_folder)}</div>')
        return

    platforms = parsed.platforms.split(',') if parsed.platforms else None

    print(f'<!--html--><div class="skill-header">Creating Server: {h(server_folder)}</div>')
    print(f'<div class="skill-subtext">Type: {h(parsed.type)} | Port base: {parsed.port} | Source: {h(SERVER_ROOT.name)}</div>')

    # 1. Copy structure
    print(f'<div class="skill-step">Copying server structure...</div>')
    copy_server_structure(SERVER_ROOT, target_dir, platforms)

    # 2. Create server.json
    server_config = {
        "id": f"server{server_num}",
        "name": server_folder,
        "type": parsed.type,
        "portBase": parsed.port,
        "created": datetime.now().strftime('%Y-%m-%d'),
        "description": f"{parsed.type.title()} server — {name_upper}"
    }
    (target_dir / 'server.json').write_text(json.dumps(server_config, indent=2))

    # 3. Rewrite ports
    print(f'<div class="skill-step">Rewriting ports (base: {parsed.port})...</div>')
    rewrite_ports(target_dir, parsed.port)

    # 4. Register in deployment.json
    deployment['servers'].append({
        "id": f"server{server_num}",
        "name": server_folder,
        "type": parsed.type,
        "path": server_folder,
        "portBase": parsed.port,
        "created": server_config['created']
    })
    save_deployment(deployment)

    # Summary
    genesis_port = parsed.port + 199
    launcher_port = parsed.port + 200

    print(f'''
<div class="skill-card">
  <div class="sc-label">Server Created</div>
  <div class="sc-value">{h(server_folder)}</div>
  <div class="sc-meta">
    <div>Type: {h(parsed.type)}</div>
    <div>Genesis IDE: http://localhost:{genesis_port}</div>
    <div>Platform launcher: http://localhost:{launcher_port}</div>
    <div>Location: {h(str(target_dir))}</div>
  </div>
</div>
<div class="skill-subtext">
  Start with: <code>cd "{h(str(target_dir / 'genesis'))}" && bash start.command</code>
</div>
''')


def cmd_list(args=None):
    """List all servers in the deployment."""
    deployment = load_deployment()
    servers = deployment.get('servers', [])

    if not servers:
        # Auto-register current server if deployment.json is empty
        current_config = load_server_config(SERVER_ROOT)
        if current_config:
            servers = [{
                "id": current_config.get('id', 'server1'),
                "name": current_config.get('name', SERVER_ROOT.name),
                "type": current_config.get('type', 'unknown'),
                "path": SERVER_ROOT.name,
                "portBase": current_config.get('portBase', 3000),
                "created": current_config.get('created', 'unknown')
            }]

    print(f'<!--html--><div class="skill-header">Servers ({len(servers)})</div>')

    for s in servers:
        server_dir = DRIVE_ROOT / s['path']
        exists = server_dir.exists()
        genesis_port = s.get('portBase', 3000) + 199

        # Check if running (try to connect)
        status = 'offline'
        status_color = '#555'
        if exists:
            status = 'stopped'
            status_color = '#e88a3e'
            try:
                import urllib.request
                urllib.request.urlopen(f'http://localhost:{genesis_port}/api/lab', timeout=1)
                status = 'running'
                status_color = '#3ac77e'
            except:
                pass
        else:
            status = 'missing'
            status_color = '#e7554a'

        type_badge = s.get('type', 'unknown')
        type_color = '#3ac77e' if type_badge == 'production' else '#4a8fe7' if type_badge == 'development' else '#e88a3e'

        print(f'''<div class="skill-card" onclick="labType('Tell me about server {h(s["name"])}')">
  <div style="display:flex;align-items:center;gap:8px">
    <span style="width:8px;height:8px;border-radius:50%;background:{status_color};display:inline-block"></span>
    <span class="sc-label">{h(s["name"])}</span>
    <span style="padding:1px 6px;border-radius:3px;font-size:9px;font-weight:600;background:{type_color}22;color:{type_color}">{h(type_badge)}</span>
  </div>
  <div class="sc-meta">
    <div>Port base: {s.get("portBase", "?")} | Genesis: :{genesis_port} | Status: {status}</div>
    <div>Created: {s.get("created", "?")}</div>
  </div>
</div>''')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 server_manager.py <command> [args]")
        print("Commands: create, list")
        sys.exit(1)

    command = sys.argv[1]
    remaining = sys.argv[2:]

    if command == 'create':
        cmd_create(remaining)
    elif command == 'list':
        cmd_list(remaining)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
