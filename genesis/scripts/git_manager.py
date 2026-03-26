#!/usr/bin/env python3
"""
Genesis IDE — Git Manager
Version control for platforms: versions, snapshot, and general git commands.
"""

import sys
import os
import json
import subprocess
import html as html_mod
from pathlib import Path

GENESIS_DIR = Path(os.environ.get('LAB_INSTANCE', Path(__file__).parent.parent))
PLATFORMS_FILE = GENESIS_DIR / 'platforms.json'

def h(s):
    return html_mod.escape(str(s)) if s else ''

def load_platforms():
    try:
        return json.loads(PLATFORMS_FILE.read_text())
    except:
        return []

def get_platform_path(platform_id):
    platforms = load_platforms()
    p = next((p for p in platforms if p['id'] == platform_id.strip()), None)
    if not p:
        return None, f"Platform not found: {platform_id}"
    path = Path(p['path'])
    if not path.exists():
        return None, f"Platform directory missing: {path}"
    return path, None


# ─── VERSIONS ────────────────────────────────────────────────────────────────

def cmd_versions(platform_id):
    if not platform_id:
        print("Usage: /versions <platform-id>")
        return

    path, err = get_platform_path(platform_id)
    if err:
        print(err)
        return

    # Get tags
    tags_result = subprocess.run(
        ['git', 'tag', '-l', '--sort=-creatordate', '--format=%(refname:short) %(creatordate:short) %(subject)'],
        cwd=path, capture_output=True, text=True
    )
    tags = tags_result.stdout.strip().split('\n')[:10] if tags_result.stdout.strip() else []

    # Get recent commits
    log_result = subprocess.run(
        ['git', 'log', '--oneline', '-15'],
        cwd=path, capture_output=True, text=True
    )
    commits = log_result.stdout.strip().split('\n') if log_result.stdout.strip() else []

    tags_html = ''
    if tags:
        tags_html = '<div style="margin-bottom:12px"><div style="font-size:10px;font-weight:600;color:var(--text-muted,#888);margin-bottom:4px">TAGS</div>'
        for t in tags:
            parts = t.split(None, 2)
            tag_name = parts[0] if parts else t
            tags_html += f'<div style="padding:2px 0;font-size:11px"><code style="color:var(--gold,#c8a55a)">{h(tag_name)}</code> <span style="color:var(--text-muted,#888)">{h(" ".join(parts[1:]))}</span>'
            tags_html += f' <span class="skill-btn" style="font-size:9px;padding:1px 6px" onclick="labType(\'Restore {h(platform_id)} to tag {h(tag_name)}\')">restore</span></div>'
        tags_html += '</div>'

    commits_html = ''
    if commits:
        commits_html = '<div><div style="font-size:10px;font-weight:600;color:var(--text-muted,#888);margin-bottom:4px">RECENT COMMITS</div>'
        for c in commits:
            parts = c.split(None, 1)
            sha = parts[0] if parts else ''
            msg = parts[1] if len(parts) > 1 else ''
            commits_html += f'<div style="padding:2px 0;font-size:11px"><code style="color:var(--text-muted,#888)">{h(sha)}</code> {h(msg)}</div>'
        commits_html += '</div>'

    out = f'''<!--html-->
    <div class="skill-header">Version History: {h(platform_id)}</div>
    <div style="padding:8px">{tags_html}{commits_html}</div>
    <div style="padding:8px">
        <span class="skill-btn" onclick="labSend('/snapshot {h(platform_id)} checkpoint')">New Snapshot</span>
        <span class="skill-btn" onclick="labSend('/platforms')">Platforms</span>
    </div>'''
    print(out)


# ─── SNAPSHOT ────────────────────────────────────────────────────────────────

def cmd_snapshot(args):
    if not args or len(args.strip().split(None, 1)) < 2:
        print("Usage: /snapshot <platform-id> <description>")
        return

    parts = args.strip().split(None, 1)
    platform_id = parts[0]
    description = parts[1]

    path, err = get_platform_path(platform_id)
    if err:
        print(err)
        return

    # Stage and commit
    subprocess.run(['git', 'add', '-A'], cwd=path, capture_output=True)
    result = subprocess.run(
        ['git', 'commit', '-m', description],
        cwd=path, capture_output=True, text=True
    )

    if result.returncode == 0:
        # Get the short sha
        sha = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=path, capture_output=True, text=True).stdout.strip()
        out = f'''<!--html-->
        <div class="skill-header" style="color:#3ac77e">Snapshot Saved</div>
        <div class="skill-subtext"><code>{h(sha)}</code> {h(description)}</div>
        <div style="padding:8px">
            <span class="skill-btn" onclick="labSend('/versions {h(platform_id)}')">View History</span>
        </div>'''
        print(out)
    elif 'nothing to commit' in result.stdout + result.stderr:
        print("<!--html--><div class=\"skill-header\">No Changes</div><div class=\"skill-subtext\">Working tree is clean, nothing to commit.</div>")
    else:
        print(f"Git error: {result.stderr.strip()}")


# ─── GIT (general) ───────────────────────────────────────────────────────────

def cmd_git(args):
    if not args:
        print("Usage: /git <platform-id> <command> [args]")
        print("Examples: /git jubilee-lab status, /git jubilee-lab log -5, /git jubilee-lab diff")
        return

    parts = args.strip().split(None, 1)
    platform_id = parts[0]
    git_args = parts[1] if len(parts) > 1 else 'status'

    path, err = get_platform_path(platform_id)
    if err:
        print(err)
        return

    # Safety: block destructive commands
    dangerous = ['push --force', 'reset --hard', 'clean -f', 'branch -D']
    for d in dangerous:
        if d in git_args:
            print(f"Blocked: '{d}' is destructive. Use git manually if you're sure.")
            return

    result = subprocess.run(
        ['git'] + git_args.split(),
        cwd=path, capture_output=True, text=True
    )

    output = (result.stdout + result.stderr).strip()
    if output:
        print(output)
    else:
        print("(no output)")


# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    args = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else ''

    if command == 'versions': cmd_versions(args)
    elif command == 'snapshot': cmd_snapshot(args)
    else: cmd_git(command + (' ' + args if args else ''))
