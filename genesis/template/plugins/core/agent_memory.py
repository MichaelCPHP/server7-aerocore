#!/usr/bin/env python3
"""Agent memory management — remember, recall, forget, identity operations.

Usage:
    python3 agent_memory.py remember <topic> <content> [--type context|feedback|project]
    python3 agent_memory.py recall [topic]
    python3 agent_memory.py forget <topic>
    python3 agent_memory.py identity
"""

import os
import sys
import re
import json

INSTANCE_DIR = os.environ.get('LAB_INSTANCE', os.getcwd())
AGENT_DIR = os.path.join(INSTANCE_DIR, 'agent')
MEMORY_DIR = os.path.join(AGENT_DIR, 'memory')
MEMORY_INDEX = os.path.join(AGENT_DIR, 'MEMORY.md')
IDENTITY_FILE = os.path.join(AGENT_DIR, 'IDENTITY.md')


def slugify(text):
    """Convert text to a safe filename slug."""
    s = text.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = s.strip('_')
    return s[:60] if s else 'untitled'


def read_frontmatter(filepath):
    """Read a markdown file and return (frontmatter_dict, body)."""
    try:
        content = open(filepath, 'r', encoding='utf-8').read()
    except FileNotFoundError:
        return None, None
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not m:
        return {}, content
    fm = {}
    for line in m.group(1).split('\n'):
        kv = line.split(':', 1)
        if len(kv) == 2:
            fm[kv[0].strip()] = kv[1].strip()
    return fm, m.group(2).strip()


def write_memory_file(slug, name, description, mem_type, content):
    """Write a memory file with frontmatter."""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    filepath = os.path.join(MEMORY_DIR, f'{mem_type}_{slug}.md')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f'---\nname: {name}\ndescription: {description}\ntype: {mem_type}\n---\n\n{content}\n')
    return filepath


def update_index(action, name, rel_path, description=''):
    """Add or remove an entry from MEMORY.md index."""
    # Read existing index
    sections = {'Context': [], 'Feedback': [], 'Project': [], 'Sessions': []}
    try:
        with open(MEMORY_INDEX, 'r', encoding='utf-8') as f:
            current_section = None
            for line in f:
                line_stripped = line.strip()
                if line_stripped.startswith('## '):
                    heading = line_stripped[3:].strip()
                    if heading in sections:
                        current_section = heading
                elif current_section and line_stripped.startswith('- ['):
                    sections[current_section].append(line_stripped)
    except FileNotFoundError:
        pass

    # Determine section from rel_path
    if '/session_' in rel_path or rel_path.startswith('memory/session_'):
        section = 'Sessions'
    elif '/context_' in rel_path or rel_path.startswith('memory/context_'):
        section = 'Context'
    elif '/feedback_' in rel_path or rel_path.startswith('memory/feedback_'):
        section = 'Feedback'
    else:
        section = 'Project'

    entry = f'- [{name}]({rel_path}) — {description}'

    if action == 'add':
        # Remove existing entry with same path (update case)
        for sec in sections:
            sections[sec] = [e for e in sections[sec] if f']({rel_path})' not in e]
        sections[section].append(entry)
    elif action == 'remove':
        for sec in sections:
            sections[sec] = [e for e in sections[sec] if f']({rel_path})' not in e]

    # Write updated index
    os.makedirs(AGENT_DIR, exist_ok=True)
    with open(MEMORY_INDEX, 'w', encoding='utf-8') as f:
        f.write('# Agent Memory Index\n')
        for sec_name in ['Context', 'Feedback', 'Project', 'Sessions']:
            f.write(f'\n## {sec_name}\n\n')
            entries = sections[sec_name]
            if entries:
                for e in entries:
                    f.write(f'{e}\n')
            else:
                f.write(f'_(No {sec_name.lower()} memories yet)_\n')


def cmd_remember(args):
    """Save a memory. Args: topic content [--type context|feedback|project]"""
    # Parse --type flag
    mem_type = 'context'
    filtered = []
    i = 0
    while i < len(args):
        if args[i] == '--type' and i + 1 < len(args):
            mem_type = args[i + 1]
            i += 2
        else:
            filtered.append(args[i])
            i += 1

    if len(filtered) < 2:
        print('Usage: /remember <topic> <content> [--type context|feedback|project]')
        sys.exit(1)

    topic = filtered[0]
    content = ' '.join(filtered[1:])
    slug = slugify(topic)
    description = content[:100] + ('...' if len(content) > 100 else '')

    filepath = write_memory_file(slug, topic, description, mem_type, content)
    rel_path = f'memory/{os.path.basename(filepath)}'
    update_index('add', topic, rel_path, description)

    print(f'Remembered: "{topic}" ({mem_type})')
    print(f'  File: {rel_path}')


def cmd_recall(args):
    """List or search memories. Args: [topic]"""
    if not os.path.exists(MEMORY_DIR):
        print('No memories yet.')
        return

    files = sorted(f for f in os.listdir(MEMORY_DIR) if f.endswith('.md'))
    if not files:
        print('No memories yet.')
        return

    search = ' '.join(args).lower() if args else None

    found = 0
    for fname in files:
        fpath = os.path.join(MEMORY_DIR, fname)
        fm, body = read_frontmatter(fpath)
        if fm is None:
            continue
        name = fm.get('name', fname)
        mem_type = fm.get('type', '?')

        if search:
            haystack = f'{name} {body}'.lower()
            if search not in haystack:
                continue

        found += 1
        print(f'[{mem_type}] {name}')
        if body:
            # Show first 3 lines of body
            preview = '\n'.join(body.split('\n')[:3])
            print(f'  {preview}')
        print()

    if search and found == 0:
        print(f'No memories matching "{" ".join(args)}".')
    elif not search:
        print(f'{found} memories total.')


def cmd_forget(args):
    """Remove a memory. Args: topic"""
    if not args:
        print('Usage: /forget <topic>')
        sys.exit(1)

    topic = ' '.join(args)
    slug = slugify(topic)

    # Find matching file(s)
    removed = False
    if os.path.exists(MEMORY_DIR):
        for fname in os.listdir(MEMORY_DIR):
            if slug in fname and fname.endswith('.md'):
                fpath = os.path.join(MEMORY_DIR, fname)
                rel_path = f'memory/{fname}'
                os.remove(fpath)
                update_index('remove', topic, rel_path)
                print(f'Forgot: "{topic}" (removed {fname})')
                removed = True
                break

    if not removed:
        print(f'No memory found matching "{topic}".')
        # List available memories for reference
        if os.path.exists(MEMORY_DIR):
            files = [f for f in os.listdir(MEMORY_DIR) if f.endswith('.md')]
            if files:
                print('Available memories:')
                for f in sorted(files):
                    fm, _ = read_frontmatter(os.path.join(MEMORY_DIR, f))
                    name = fm.get('name', f) if fm else f
                    print(f'  - {name} ({f})')


def cmd_identity(args):
    """Show agent identity summary."""
    # Read IDENTITY.md
    if not os.path.exists(IDENTITY_FILE):
        print('No agent identity configured.')
        return

    content = open(IDENTITY_FILE, 'r', encoding='utf-8').read()

    # Parse fields
    fields = {}
    for pattern in [r'\*\*Name\*\*:\s*(.+)', r'\*\*Role\*\*:\s*(.+)', r'\*\*Icon\*\*:\s*(.+)',
                     r'\*\*Color\*\*:\s*(.+)']:
        m = re.search(pattern, content)
        if m:
            key = pattern.split(r'\*\*')[1]
            fields[key] = m.group(1).strip()

    id_match = re.search(r'Agent ID\s*\|\s*([^|]+)', content)
    if id_match:
        fields['Agent ID'] = id_match.group(1).strip()

    # Print identity
    name = fields.get('Name', 'Unknown')
    role = fields.get('Role', 'Unknown')
    icon = fields.get('Icon', '')
    color = fields.get('Color', '')
    agent_id = fields.get('Agent ID', 'unknown')

    print(f'{icon} {name}')
    print(f'  Role: {role}')
    print(f'  Agent ID: {agent_id}')
    print(f'  Color: {color}')

    # Memory count
    mem_count = 0
    if os.path.exists(MEMORY_DIR):
        mem_count = len([f for f in os.listdir(MEMORY_DIR) if f.endswith('.md')])
    print(f'  Memories: {mem_count}')

    # Channel memberships (from joint_db if available)
    try:
        import subprocess
        core_dir = os.path.dirname(os.path.abspath(__file__))
        joint_db = os.path.join(core_dir, 'joint_db.py')
        drive_root = os.environ.get('DRIVE_ROOT', os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(INSTANCE_DIR)))))
        result = subprocess.run(['python3', joint_db, 'list-channels'],
                                capture_output=True, text=True, timeout=5,
                                env={**os.environ, 'DRIVE_ROOT': drive_root})
        if result.returncode == 0:
            channels = json.loads(result.stdout)
            if channels:
                print(f'  Channels: {len(channels)}')
                for ch in channels:
                    print(f'    - #{ch["name"]}')
    except Exception:
        pass


COMMANDS = {
    'remember': cmd_remember,
    'recall': cmd_recall,
    'forget': cmd_forget,
    'identity': cmd_identity,
}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f'Usage: {sys.argv[0]} <{"|".join(COMMANDS.keys())}> [args...]')
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])
