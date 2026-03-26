#!/usr/bin/env python3
"""
Deploy Manager — Push template code between servers (WordPress-style updates).

Only deploys shared template code. NEVER touches instance data, sessions, or logs.

Usage:
  python3 deploy_manager.py deploy --source SERVER2-DEV --target SERVER1-MASTER
  python3 deploy_manager.py deploy --source SERVER2-DEV --target SERVER1-MASTER --restart
  python3 deploy_manager.py deploy-all --source SERVER2-DEV [--restart]
  python3 deploy_manager.py restart --server SERVER5-JUBILEE
  python3 deploy_manager.py status
  python3 deploy_manager.py diff --source SERVER2-DEV --target SERVER1-MASTER
"""

import os, sys, json, shutil, subprocess, filecmp
from pathlib import Path
from datetime import datetime
import html as html_mod

# Paths
GENESIS_DIR = Path(os.environ.get('LAB_INSTANCE', Path(__file__).parent.parent))
SERVER_ROOT = Path(os.environ.get('SERVER_ROOT', GENESIS_DIR.parent))
DRIVE_ROOT = SERVER_ROOT.parent
DEPLOYMENT_FILE = DRIVE_ROOT / 'deployment.json'

def h(s):
    return html_mod.escape(str(s)) if s else ''

def load_deployment():
    try:
        return json.loads(DEPLOYMENT_FILE.read_text())
    except:
        return {"version": "1.0", "driveRoot": str(DRIVE_ROOT), "servers": []}

def resolve_server(name):
    """Resolve a server name to its directory path."""
    deployment = load_deployment()
    for s in deployment['servers']:
        if s['name'] == name or s['id'] == name or s['path'] == name:
            return DRIVE_ROOT / s['path'], s
    # Try direct path
    direct = DRIVE_ROOT / name
    if direct.exists() and (direct / 'server.json').exists():
        config = json.loads((direct / 'server.json').read_text())
        return direct, config
    return None, None

# --- Deploy scope ---
# These paths (relative to server root) are the ONLY things that get deployed.
# Everything else stays local to the server.

DEPLOY_PATHS_GENESIS = [
    'genesis/template/core/server.js',
    'genesis/template/core/index.html',
    'genesis/template/core/theme.js',
    'genesis/template/core/database_manager.py',
    'genesis/template/core/joint_db.py',
    'genesis/template/core/xlsx_reader.py',
    'genesis/template/core/hook-job-discipline.sh',
    'genesis/template/core/vendor',
    'genesis/template/plugins',
    'genesis/template/skills/catalog.json',
    'genesis/template/workflows.json',
    'genesis/template/launcher.js',
    'genesis/scripts/platform_manager.py',
    'genesis/scripts/server_manager.py',
    'genesis/scripts/deploy_manager.py',
    'genesis/scripts/git_manager.py',
]

DEPLOY_PATHS_PLATFORM = [
    # Relative to platform root (e.g., jubilee-lab/)
    'launcher.js',
    'CLAUDE.md',
    'docs',
    'instance-template',
]

# NEVER deploy these (safety check)
# NOTE: agent_memory.py IS deployed (via genesis/template/plugins).
# But agent/ identity dirs are per-server — never overwrite them.
NEVER_DEPLOY = {
    'data', 'kb/sessions/messages', 'output', 'logs',
    'agent',                          # agent identity files are per-server
    '.git', '__pycache__', '.DS_Store', 'node_modules'
}

def is_safe_path(rel_path_str):
    """Ensure a path doesn't contain any NEVER_DEPLOY segments."""
    parts = rel_path_str.split(os.sep)
    for excl in NEVER_DEPLOY:
        excl_parts = excl.split('/')
        for i in range(len(parts) - len(excl_parts) + 1):
            if parts[i:i+len(excl_parts)] == excl_parts:
                return False
    return True


def sync_path(src_base, tgt_base, rel_path, dry_run=False):
    """
    Sync a single file or directory from source to target.
    Returns list of (action, rel_path) tuples.
    """
    changes = []
    src = src_base / rel_path
    tgt = tgt_base / rel_path

    if not src.exists():
        return changes

    if src.is_file():
        if not is_safe_path(rel_path):
            return changes
        if not tgt.exists():
            changes.append(('add', rel_path))
            if not dry_run:
                tgt.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, tgt)
        elif not filecmp.cmp(src, tgt, shallow=False):
            changes.append(('update', rel_path))
            if not dry_run:
                shutil.copy2(src, tgt)
    elif src.is_dir():
        # Recursively sync directory
        for item in src.rglob('*'):
            if item.is_file():
                item_rel = str(item.relative_to(src_base))
                if not is_safe_path(item_rel):
                    continue
                tgt_item = tgt_base / item_rel
                if not tgt_item.exists():
                    changes.append(('add', item_rel))
                    if not dry_run:
                        tgt_item.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, tgt_item)
                elif not filecmp.cmp(item, tgt_item, shallow=False):
                    changes.append(('update', item_rel))
                    if not dry_run:
                        shutil.copy2(item, tgt_item)

        # Check for files in target that don't exist in source (deletions)
        if tgt.exists():
            for item in tgt.rglob('*'):
                if item.is_file():
                    item_rel = str(item.relative_to(tgt_base))
                    if not is_safe_path(item_rel):
                        continue
                    src_item = src_base / item_rel
                    if not src_item.exists():
                        changes.append(('delete', item_rel))
                        if not dry_run:
                            item.unlink()

    return changes


def deploy(source_dir, target_dir, dry_run=False):
    """
    Deploy template code from source server to target server.
    Returns list of all changes made.
    """
    all_changes = []

    # 1. Deploy genesis-level paths
    for rel_path in DEPLOY_PATHS_GENESIS:
        changes = sync_path(source_dir, target_dir, rel_path, dry_run)
        all_changes.extend(changes)

    # 2. Deploy platform-level paths
    # Merge platforms from BOTH source and target to handle all platform dirs
    seen_paths = set()
    platforms = []
    for pf in [source_dir / 'genesis' / 'platforms.json', target_dir / 'genesis' / 'platforms.json']:
        try:
            for p in json.loads(pf.read_text()):
                pp = p.get('path', '')
                if pp and pp not in seen_paths:
                    seen_paths.add(pp)
                    platforms.append(p)
        except:
            pass

    for platform in platforms:
        platform_path = platform.get('path', '')
        if not platform_path:
            continue
        for rel_path in DEPLOY_PATHS_PLATFORM:
            full_rel = f'{platform_path}/{rel_path}'
            changes = sync_path(source_dir, target_dir, full_rel, dry_run)
            all_changes.extend(changes)

    return all_changes


def git_snapshot(server_dir, message):
    """Create a git commit in the server's genesis repo to track the deployment."""
    genesis_dir = server_dir / 'genesis'
    if not (genesis_dir / '.git').exists():
        return False
    try:
        subprocess.run(['git', 'add', '-A'], cwd=genesis_dir, capture_output=True, timeout=30)
        result = subprocess.run(
            ['git', 'commit', '-m', message],
            cwd=genesis_dir, capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except:
        return False


def cmd_deploy(args):
    """Deploy template code from source to target server."""
    import argparse, shlex

    # Skill system may pass all user args as a single string — split it
    if len(args) == 1 and ' ' in args[0]:
        args = shlex.split(args[0])

    parser = argparse.ArgumentParser()
    # Support: /deploy SERVER2-DEV SERVER1-MASTER  OR  /deploy --source X --target Y
    parser.add_argument('positional', nargs='*', default=[])
    parser.add_argument('--source', default=None, help='Source server name')
    parser.add_argument('--target', default=None, help='Target server name')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without applying')
    parser.add_argument('--restart', action='store_true', help='Restart target server after deploy')
    parsed = parser.parse_args(args)

    pos = parsed.positional
    source = parsed.source or (pos[0] if len(pos) > 0 else None)
    target = parsed.target or (pos[1] if len(pos) > 1 else None)

    if not source or not target:
        print('<!--html--><div class="skill-error">Usage: /deploy &lt;source-server&gt; &lt;target-server&gt; [--dry-run] [--restart]<br>Example: /deploy SERVER2-DEV SERVER1-MASTER --restart</div>')
        return

    parsed.source = source
    parsed.target = target

    source_dir, source_config = resolve_server(parsed.source)
    target_dir, target_config = resolve_server(parsed.target)

    if not source_dir or not source_dir.exists():
        print(f'<!--html--><div class="skill-error">Source server not found: {h(parsed.source)}</div>')
        return
    if not target_dir or not target_dir.exists():
        print(f'<!--html--><div class="skill-error">Target server not found: {h(parsed.target)}</div>')
        return

    source_name = source_config.get('name', parsed.source) if isinstance(source_config, dict) else parsed.source
    target_name = target_config.get('name', parsed.target) if isinstance(target_config, dict) else parsed.target

    mode = 'DRY RUN' if parsed.dry_run else 'DEPLOYING'
    print(f'<!--html--><div class="skill-header">{mode}: {h(source_name)} → {h(target_name)}</div>')

    # Snapshot target before deploy (so we can rollback)
    if not parsed.dry_run:
        git_snapshot(target_dir, f'pre-deploy snapshot (from {source_name})')

    # Deploy
    changes = deploy(source_dir, target_dir, dry_run=parsed.dry_run)

    if not changes:
        print(f'<div class="skill-subtext">No changes to deploy — servers are in sync.</div>')
        return

    # Snapshot target after deploy
    if not parsed.dry_run:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        git_snapshot(target_dir, f'deploy from {source_name} at {timestamp}')

    # Group changes by action
    adds = [c for c in changes if c[0] == 'add']
    updates = [c for c in changes if c[0] == 'update']
    deletes = [c for c in changes if c[0] == 'delete']

    print(f'<div class="skill-subtext">{len(changes)} changes: {len(adds)} added, {len(updates)} updated, {len(deletes)} deleted</div>')

    # Show changes grouped
    if adds:
        print(f'<div class="skill-step" style="color:#3ac77e">Added ({len(adds)}):</div>')
        print('<div style="font-size:11px;color:#888;padding-left:12px">')
        for _, path in adds[:20]:
            print(f'+ {h(path)}<br>')
        if len(adds) > 20:
            print(f'... and {len(adds) - 20} more')
        print('</div>')

    if updates:
        print(f'<div class="skill-step" style="color:#4a8fe7">Updated ({len(updates)}):</div>')
        print('<div style="font-size:11px;color:#888;padding-left:12px">')
        for _, path in updates[:20]:
            print(f'~ {h(path)}<br>')
        if len(updates) > 20:
            print(f'... and {len(updates) - 20} more')
        print('</div>')

    if deletes:
        print(f'<div class="skill-step" style="color:#e7554a">Deleted ({len(deletes)}):</div>')
        print('<div style="font-size:11px;color:#888;padding-left:12px">')
        for _, path in deletes[:20]:
            print(f'- {h(path)}<br>')
        if len(deletes) > 20:
            print(f'... and {len(deletes) - 20} more')
        print('</div>')

    if parsed.dry_run:
        print(f'<div class="skill-subtext">This was a dry run. Run without --dry-run to apply changes.</div>')
    else:
        print(f'<div class="skill-subtext">Deploy complete. Target server git snapshot created for rollback.</div>')

        # Auto-restart if requested
        if parsed.restart and changes:
            print(f'<div class="skill-step" style="color:#4a8fe7">Restarting {h(target_name)}...</div>')
            killed, started_genesis, started_instances, started_frontends = restart_server(target_dir, target_config)
            port_base = target_config.get('portBase', 3000) if isinstance(target_config, dict) else 3000
            if started_genesis:
                print(f'<div class="skill-step" style="color:#3ac77e">&#x2714; Genesis IDE on :{port_base + 199}</div>')
            for inst in started_instances:
                print(f'<div class="skill-step" style="color:#3ac77e">&#x2714; Instance {h(inst["id"])} on :{inst["port"]}</div>')
            for fe in started_frontends:
                print(f'<div class="skill-step" style="color:#3ac77e">&#x2714; Frontend {h(fe["id"])} on :{fe["port"]}</div>')


def cmd_diff(args):
    """Show differences between two servers (template code only)."""
    import shlex

    # Skill system may pass all user args as a single string — split it
    if len(args) == 1 and ' ' in args[0]:
        args = shlex.split(args[0])

    # Support: /server-diff SERVER2-DEV SERVER1-MASTER  OR --source/--target
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('positional', nargs='*', default=[])
    parser.add_argument('--source', default=None)
    parser.add_argument('--target', default=None)
    parsed = parser.parse_args(args)

    pos = parsed.positional
    source = parsed.source or (pos[0] if len(pos) > 0 else None)
    target = parsed.target or (pos[1] if len(pos) > 1 else None)

    if not source or not target:
        print('<!--html--><div class="skill-error">Usage: /server-diff &lt;source&gt; &lt;target&gt;</div>')
        return

    cmd_deploy(['--source', source, '--target', target, '--dry-run'])


def cmd_status(args=None):
    """Check status of all servers (running/stopped, port, type)."""
    import argparse, shlex
    args = args or []

    # Skill system may pass all user args as a single string — split it
    if len(args) == 1 and ' ' in args[0]:
        args = shlex.split(args[0])

    parser = argparse.ArgumentParser()
    parser.add_argument('positional', nargs='*', default=[])
    parser.add_argument('--server', default=None, help='Check specific server')
    parsed = parser.parse_args(args)

    # Support: /server-status SERVER1-MASTER  OR  /server-status --server X
    pos = parsed.positional
    if not parsed.server and len(pos) > 0:
        parsed.server = pos[0]

    deployment = load_deployment()
    servers = deployment.get('servers', [])

    if not servers:
        print('<!--html--><div class="skill-subtext">No servers registered in deployment.json</div>')
        return

    if parsed.server:
        servers = [s for s in servers if s['name'] == parsed.server or s['id'] == parsed.server]

    print(f'<!--html--><div class="skill-header">Server Status</div>')

    for s in servers:
        server_dir = DRIVE_ROOT / s['path']
        port_base = s.get('portBase', 3000)
        genesis_port = port_base + 199
        launcher_port = port_base + 200

        # Check directory exists
        if not server_dir.exists():
            status = 'missing'
            status_color = '#e7554a'
            status_icon = '&#x2716;'
        else:
            # Check if Genesis IDE is running
            genesis_running = False
            try:
                import urllib.request
                resp = urllib.request.urlopen(f'http://localhost:{genesis_port}/api/lab', timeout=2)
                genesis_running = resp.getcode() == 200
            except:
                pass

            # Check if launcher is running
            launcher_running = False
            try:
                import urllib.request
                resp = urllib.request.urlopen(f'http://localhost:{launcher_port}/api/status', timeout=2)
                launcher_running = resp.getcode() == 200
            except:
                pass

            if genesis_running:
                status = 'running'
                status_color = '#3ac77e'
                status_icon = '&#x2714;'
            else:
                status = 'stopped'
                status_color = '#e88a3e'
                status_icon = '&#x25CB;'

        type_badge = s.get('type', 'unknown')
        type_color = '#3ac77e' if type_badge == 'production' else '#4a8fe7' if type_badge == 'development' else '#e88a3e'

        # Get git info
        git_info = ''
        genesis_git = server_dir / 'genesis' / '.git'
        if genesis_git.exists():
            try:
                result = subprocess.run(
                    ['git', 'log', '--oneline', '-1'],
                    cwd=server_dir / 'genesis', capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    git_info = result.stdout.strip()
            except:
                pass

        # Count instances across platforms
        instance_count = 0
        try:
            platforms = json.loads((server_dir / 'genesis' / 'platforms.json').read_text())
            for p in platforms:
                inst_dir = server_dir / p['path'] / 'instances'
                if inst_dir.exists():
                    instance_count += sum(1 for d in inst_dir.iterdir() if d.is_dir())
        except:
            pass

        print(f'''<div class="skill-card">
  <div style="display:flex;align-items:center;gap:8px">
    <span style="color:{status_color}">{status_icon}</span>
    <span class="sc-label">{h(s["name"])}</span>
    <span style="padding:1px 6px;border-radius:3px;font-size:9px;font-weight:600;background:{type_color}22;color:{type_color}">{h(type_badge)}</span>
    <span style="padding:1px 6px;border-radius:3px;font-size:9px;font-weight:600;background:{status_color}22;color:{status_color}">{status}</span>
  </div>
  <div class="sc-meta">
    <div>Genesis IDE: :{genesis_port} | Launcher: :{launcher_port} | Instances: {instance_count}</div>
    <div>Latest commit: {h(git_info) if git_info else 'n/a'}</div>
    <div>Path: {h(str(server_dir))}</div>
  </div>
</div>''')


# ─── RESTART ────────────────────────────────────────────────────────────────

def restart_server(server_dir, server_config):
    """
    Restart all Genesis processes for a server.
    Returns (killed_count, started_genesis, started_instances).
    """
    import time
    server_path = str(server_dir)
    port_base = server_config.get('portBase', 3000)
    genesis_port = port_base + 199

    # 1. Discover running instances before killing anything
    running_instances = []
    platforms_file = server_dir / 'genesis' / 'platforms.json'
    try:
        platforms = json.loads(platforms_file.read_text())
    except:
        platforms = []

    for p in platforms:
        inst_dir = server_dir / p['path'] / 'instances'
        if not inst_dir.exists():
            continue
        for d in inst_dir.iterdir():
            lj = d / 'lab.json'
            if not lj.exists():
                continue
            try:
                cfg = json.loads(lj.read_text())
                port = cfg.get('port')
                if not port:
                    continue
                result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
                if result.stdout.strip():
                    # Detect actual frontend port by finding the frontend process
                    fe_port = None
                    fe_server = d / 'frontend' / 'server.js'
                    if fe_server.exists():
                        try:
                            fe_result = subprocess.run(
                                ['pgrep', '-f', f'node.*{server_dir.name}.*{d.name}/frontend/server.js'],
                                capture_output=True, text=True
                            )
                            for fe_pid in fe_result.stdout.strip().split('\n'):
                                fe_pid = fe_pid.strip()
                                if not fe_pid:
                                    continue
                                lsof_res = subprocess.run(
                                    ['lsof', '-a', '-p', fe_pid, '-iTCP', '-sTCP:LISTEN', '-P', '-Fn'],
                                    capture_output=True, text=True
                                )
                                for line in lsof_res.stdout.split('\n'):
                                    if line.startswith('n') and ':' in line:
                                        detected = int(line.split(':')[-1])
                                        if detected > 0:
                                            fe_port = detected
                                            break
                                if fe_port:
                                    break
                        except:
                            pass
                        if not fe_port:
                            fe_port = port + 70  # fallback
                    running_instances.append({
                        'id': d.name, 'port': port, 'dir': str(d),
                        'platform_path': p['path'],
                        'frontend_port': fe_port,
                    })
            except:
                pass

    # 2. Kill ALL node processes whose command contains this server's path
    killed = 0
    try:
        result = subprocess.run(
            ['pgrep', '-f', f'node.*{server_dir.name}'],
            capture_output=True, text=True
        )
        for pid in result.stdout.strip().split('\n'):
            pid = pid.strip()
            if not pid:
                continue
            # Verify it's actually for this server (double check)
            ps_result = subprocess.run(['ps', '-p', pid, '-o', 'args='], capture_output=True, text=True)
            if server_dir.name in ps_result.stdout:
                subprocess.run(['kill', pid], capture_output=True)
                killed += 1
    except:
        pass

    time.sleep(1.5)

    # 3. Force kill any stragglers
    try:
        result = subprocess.run(
            ['pgrep', '-f', f'node.*{server_dir.name}'],
            capture_output=True, text=True
        )
        for pid in result.stdout.strip().split('\n'):
            pid = pid.strip()
            if pid:
                subprocess.run(['kill', '-9', pid], capture_output=True)
    except:
        pass
    time.sleep(0.5)

    # 4. Start Genesis IDE
    started_genesis = False
    genesis_core = server_dir / 'genesis' / 'template' / 'core' / 'server.js'
    if genesis_core.exists():
        env = {**os.environ,
            'LAB_IS_GENESIS': '1',
            'LAB_PORT': str(genesis_port),
            'SERVER_ROOT': str(server_dir),
            'LAB_INSTANCE': str(server_dir / 'genesis'),
            'GENESIS_DIR': str(server_dir / 'genesis'),
            'GLOBAL_PLUGINS_DIR': str(server_dir / 'genesis' / 'template' / 'plugins'),
            'GLOBAL_SKILLS_DIR': str(server_dir / 'genesis' / 'template' / 'skills'),
        }
        subprocess.Popen(
            ['node', str(genesis_core)],
            cwd=str(server_dir / 'genesis'),
            env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        started_genesis = True

    # 5. Restart previously-running instances (or discover all if none were running)
    if not running_instances:
        # No instances were running — discover ALL instances from platforms.json
        for p in platforms:
            inst_dir = server_dir / p['path'] / 'instances'
            if not inst_dir.exists():
                continue
            for d in inst_dir.iterdir():
                if not d.is_dir() or 'backup' in d.name:
                    continue
                lj = d / 'lab.json'
                if not lj.exists():
                    continue
                try:
                    cfg = json.loads(lj.read_text())
                    port = cfg.get('port')
                    if not port:
                        continue
                    fe_port = (port + 70) if (d / 'frontend' / 'server.js').exists() else None
                    running_instances.append({
                        'id': d.name, 'port': port, 'dir': str(d),
                        'platform_path': p['path'],
                        'frontend_port': fe_port,
                    })
                except:
                    pass

    # Deduplicate by port — only start the first (non-backup) instance per port
    seen_ports = set()
    deduped = []
    # Sort so non-backup instances come first
    for inst in sorted(running_instances, key=lambda i: ('backup' in i['id'], i['id'])):
        if inst['port'] not in seen_ports:
            seen_ports.add(inst['port'])
            deduped.append(inst)

    started_instances = []
    for inst in deduped:
        inst_dir_path = Path(inst['dir'])
        # Build clean env — strip LAB_IS_GENESIS so lab instances don't think they're Genesis IDE
        clean_env = {k: v for k, v in os.environ.items() if k != 'LAB_IS_GENESIS'}
        env = {**clean_env,
            'LAB_INSTANCE': inst['dir'],
            'LAB_PORT': str(inst['port']),
            'GENESIS_DIR': str(server_dir / 'genesis'),
            'GLOBAL_PLUGINS_DIR': str(server_dir / 'genesis' / 'template' / 'plugins'),
            'GLOBAL_SKILLS_DIR': str(server_dir / 'genesis' / 'template' / 'skills'),
        }
        subprocess.Popen(
            ['node', str(genesis_core)],
            cwd=inst['dir'],
            env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        started_instances.append(inst)

    # 6. Start frontends (give backends a moment to start first)
    time.sleep(1)
    started_frontends = []
    for inst in deduped:
        inst_dir_path = Path(inst['dir'])
        fe_server = inst_dir_path / 'frontend' / 'server.js'
        if fe_server.exists():
            fe_port = inst.get('frontend_port') or (inst['port'] + 70)
            fe_env = {**os.environ, 'PORT': str(fe_port)}
            subprocess.Popen(
                ['node', str(fe_server)],
                cwd=inst['dir'],
                env=fe_env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            started_frontends.append({'id': inst['id'], 'port': fe_port})

    return killed, started_genesis, started_instances, started_frontends


def cmd_restart(args):
    """Restart all processes for a server."""
    import argparse, shlex
    if len(args) == 1 and ' ' in args[0]:
        args = shlex.split(args[0])

    parser = argparse.ArgumentParser()
    parser.add_argument('positional', nargs='*', default=[])
    parser.add_argument('--server', default=None)
    parsed = parser.parse_args(args)

    server_name = parsed.server or (parsed.positional[0] if parsed.positional else None)
    if not server_name:
        print('<!--html--><div class="skill-error">Usage: /restart &lt;server-name&gt;</div>')
        return

    server_dir, server_config = resolve_server(server_name)
    if not server_dir:
        print(f'<!--html--><div class="skill-error">Server not found: {h(server_name)}</div>')
        return

    name = server_config.get('name', server_name) if isinstance(server_config, dict) else server_name
    port_base = server_config.get('portBase', 3000) if isinstance(server_config, dict) else 3000

    print(f'<!--html--><div class="skill-header">Restarting: {h(name)}</div>')

    killed, started_genesis, started_instances, started_frontends = restart_server(server_dir, server_config)

    print(f'<div class="skill-subtext">Killed {killed} old processes</div>')
    if started_genesis:
        print(f'<div class="skill-step" style="color:#3ac77e">&#x2714; Genesis IDE started on :{port_base + 199}</div>')
    for inst in started_instances:
        print(f'<div class="skill-step" style="color:#3ac77e">&#x2714; Instance {h(inst["id"])} started on :{inst["port"]}</div>')
    for fe in started_frontends:
        print(f'<div class="skill-step" style="color:#3ac77e">&#x2714; Frontend {h(fe["id"])} started on :{fe["port"]}</div>')

    # Verify after a short wait
    import time
    time.sleep(2)
    try:
        import urllib.request
        resp = urllib.request.urlopen(f'http://localhost:{port_base + 199}/api/lab', timeout=3)
        if resp.getcode() == 200:
            print(f'<div class="skill-step" style="color:#3ac77e">&#x2714; Verified: Genesis IDE responding on :{port_base + 199}</div>')
        else:
            print(f'<div class="skill-step" style="color:#e88a3e">&#x26A0; Genesis IDE returned {resp.getcode()}</div>')
    except Exception as e:
        print(f'<div class="skill-step" style="color:#e88a3e">&#x26A0; Genesis IDE not yet responding (may need a moment)</div>')

    for inst in started_instances:
        try:
            resp = urllib.request.urlopen(f'http://localhost:{inst["port"]}/api/lab', timeout=3)
            if resp.getcode() == 200:
                print(f'<div class="skill-step" style="color:#3ac77e">&#x2714; Verified: {h(inst["id"])} responding on :{inst["port"]}</div>')
        except:
            print(f'<div class="skill-step" style="color:#e88a3e">&#x26A0; {h(inst["id"])} not yet responding on :{inst["port"]}</div>')


# ─── DEPLOY ALL ─────────────────────────────────────────────────────────────

def cmd_deploy_all(args):
    """Deploy from source to ALL other servers, with optional restart."""
    import argparse, shlex
    if len(args) == 1 and ' ' in args[0]:
        args = shlex.split(args[0])

    parser = argparse.ArgumentParser()
    parser.add_argument('positional', nargs='*', default=[])
    parser.add_argument('--source', default=None)
    parser.add_argument('--restart', action='store_true', help='Restart target servers after deploy')
    parser.add_argument('--skip', nargs='*', default=[], help='Server names to skip')
    parsed = parser.parse_args(args)

    source = parsed.source or (parsed.positional[0] if parsed.positional else None)
    if not source:
        print('<!--html--><div class="skill-error">Usage: deploy-all --source &lt;server&gt; [--restart] [--skip SERVER1 SERVER2]</div>')
        return

    source_dir, source_config = resolve_server(source)
    if not source_dir:
        print(f'<!--html--><div class="skill-error">Source server not found: {h(source)}</div>')
        return

    source_name = source_config.get('name', source) if isinstance(source_config, dict) else source
    deployment = load_deployment()
    targets = [s for s in deployment.get('servers', [])
               if s['name'] != source_name and s['name'] not in parsed.skip]

    if not targets:
        print(f'<!--html--><div class="skill-subtext">No target servers to deploy to.</div>')
        return

    print(f'<!--html--><div class="skill-header">Deploy All: {h(source_name)} → {len(targets)} servers</div>')

    total_changes = 0
    restarted = []

    for s in targets:
        target_dir, target_config = resolve_server(s['name'])
        if not target_dir or not target_dir.exists():
            print(f'<div class="skill-step" style="color:#e88a3e">&#x26A0; {h(s["name"])}: directory not found, skipping</div>')
            continue

        # Snapshot before
        git_snapshot(target_dir, f'pre-deploy snapshot (from {source_name})')

        changes = deploy(source_dir, target_dir, dry_run=False)

        # Snapshot after
        if changes:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            git_snapshot(target_dir, f'deploy from {source_name} at {timestamp}')

        adds = len([c for c in changes if c[0] == 'add'])
        updates = len([c for c in changes if c[0] == 'update'])
        deletes = len([c for c in changes if c[0] == 'delete'])
        total_changes += len(changes)

        if changes:
            print(f'<div class="skill-step" style="color:#4a8fe7">&#x2714; {h(s["name"])}: {len(changes)} changes ({adds} added, {updates} updated, {deletes} deleted)</div>')
        else:
            print(f'<div class="skill-step" style="color:#888">&#x2022; {h(s["name"])}: already in sync</div>')

        # Restart if requested
        if parsed.restart and changes:
            port_base = s.get('portBase', 3000)
            genesis_port = port_base + 199
            # Check if server is running before restarting
            is_running = False
            try:
                import urllib.request
                resp = urllib.request.urlopen(f'http://localhost:{genesis_port}/api/lab', timeout=2)
                is_running = resp.getcode() == 200
            except:
                pass

            if is_running:
                killed, started_genesis, started_instances, started_frontends = restart_server(target_dir, target_config or s)
                restarted.append(s['name'])
                inst_names = ', '.join(i['id'] for i in started_instances) if started_instances else 'none'
                fe_names = ', '.join(f'{f["id"]}:{f["port"]}' for f in started_frontends) if started_frontends else ''
                extra = f', frontends: {fe_names}' if fe_names else ''
                print(f'<div class="skill-step" style="color:#3ac77e">  ↳ Restarted (killed {killed}, instances: {inst_names}{extra})</div>')
            else:
                print(f'<div class="skill-step" style="color:#888">  ↳ Not running, skip restart</div>')

    print(f'<div class="skill-subtext">{total_changes} total changes across {len(targets)} servers')
    if restarted:
        print(f' · Restarted: {", ".join(restarted)}')
    print('</div>')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 deploy_manager.py <command> [args]")
        print("Commands: deploy, deploy-all, restart, diff, status")
        sys.exit(1)

    command = sys.argv[1]
    remaining = sys.argv[2:]

    if command == 'deploy':
        cmd_deploy(remaining)
    elif command == 'deploy-all':
        cmd_deploy_all(remaining)
    elif command == 'restart':
        cmd_restart(remaining)
    elif command == 'diff':
        cmd_diff(remaining)
    elif command == 'status':
        cmd_status(remaining)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
