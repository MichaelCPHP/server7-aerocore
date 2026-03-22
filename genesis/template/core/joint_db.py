#!/usr/bin/env python3
"""Joint session database operations for inter-agent communication.

Manages shared channels (like IRC/Slack) where multiple AI agents and users
can collaborate in real-time across servers and instances.

Database: /Volumes/T9 Drive 1/.joint-sessions/joint.db (WAL mode)

Usage:
    python3 joint_db.py init
    python3 joint_db.py create-channel <name> <topic> <created_by>
    python3 joint_db.py list-channels
    python3 joint_db.py join <channel_name> <agent_id> <display_name> <server_id> <instance> <port> [icon] [color] [role]
    python3 joint_db.py leave <channel_name> <agent_id>
    python3 joint_db.py members <channel_name>
    python3 joint_db.py post <channel_name> <agent_id> <display_name> <role> <content> [metadata_json]
    python3 joint_db.py messages <channel_name> [since_seq] [limit]
    python3 joint_db.py discover-agents
    python3 joint_db.py channel-info <channel_name>
"""

import sqlite3
import json
import sys
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Resolve database path — shared across all servers on the drive
DRIVE_ROOT = os.environ.get('DRIVE_ROOT', '/Volumes/T9 Drive 1')
DB_DIR = os.path.join(DRIVE_ROOT, '.joint-sessions')
DB_PATH = os.environ.get('JOINT_DB', os.path.join(DB_DIR, 'joint.db'))

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    topic       TEXT DEFAULT '',
    created_by  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    archived    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS members (
    channel_id  TEXT NOT NULL REFERENCES channels(id),
    agent_id    TEXT NOT NULL,
    display_name TEXT NOT NULL,
    server_id   TEXT NOT NULL,
    instance    TEXT NOT NULL,
    port        INTEGER NOT NULL,
    icon        TEXT DEFAULT '',
    color       TEXT DEFAULT '',
    role        TEXT DEFAULT 'agent',
    joined_at   TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen   TEXT,
    PRIMARY KEY (channel_id, agent_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id  TEXT NOT NULL REFERENCES channels(id),
    agent_id    TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'agent',
    content     TEXT NOT NULL,
    metadata    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    seq         INTEGER
);

CREATE INDEX IF NOT EXISTS idx_messages_channel_seq ON messages(channel_id, seq);
CREATE INDEX IF NOT EXISTS idx_messages_channel_time ON messages(channel_id, created_at);
"""


def get_db():
    """Open database connection with WAL mode and busy timeout."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("PRAGMA foreign_keys=ON")
    db.row_factory = sqlite3.Row
    return db


def init_db():
    """Create tables if they don't exist."""
    db = get_db()
    db.executescript(SCHEMA)
    db.close()
    return {"ok": True, "db": DB_PATH}


def resolve_channel(db, name_or_id):
    """Find channel by name or ID. Names can be passed with or without #."""
    clean = name_or_id.lstrip('#')
    row = db.execute(
        "SELECT * FROM channels WHERE name = ? OR name = ? OR id = ?",
        (name_or_id, clean, name_or_id)
    ).fetchone()
    return dict(row) if row else None


def create_channel(name, topic, created_by):
    """Create a new channel."""
    clean = name.lstrip('#')
    channel_id = str(uuid.uuid4())[:8]
    db = get_db()
    try:
        db.execute(
            "INSERT INTO channels (id, name, topic, created_by) VALUES (?, ?, ?, ?)",
            (channel_id, clean, topic, created_by)
        )
        db.commit()
        ch = dict(db.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone())
        return ch
    except sqlite3.IntegrityError:
        return {"error": f"Channel '{clean}' already exists"}
    finally:
        db.close()


def list_channels():
    """List all non-archived channels with member counts."""
    db = get_db()
    rows = db.execute("""
        SELECT c.*, COUNT(m.agent_id) as member_count,
               (SELECT MAX(seq) FROM messages WHERE channel_id = c.id) as last_seq
        FROM channels c
        LEFT JOIN members m ON c.id = m.channel_id
        WHERE c.archived = 0
        GROUP BY c.id
        ORDER BY c.created_at DESC
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]


def channel_info(name_or_id):
    """Get channel info with members."""
    db = get_db()
    ch = resolve_channel(db, name_or_id)
    if not ch:
        db.close()
        return {"error": f"Channel '{name_or_id}' not found"}
    members = db.execute(
        "SELECT * FROM members WHERE channel_id = ?", (ch['id'],)
    ).fetchall()
    ch['members'] = [dict(m) for m in members]
    msg_count = db.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE channel_id = ?", (ch['id'],)
    ).fetchone()
    ch['message_count'] = msg_count['cnt']
    db.close()
    return ch


def join_channel(channel_name, agent_id, display_name, server_id, instance, port,
                 icon='', color='', role='agent'):
    """Join an agent to a channel."""
    db = get_db()
    ch = resolve_channel(db, channel_name)
    if not ch:
        db.close()
        return {"error": f"Channel '{channel_name}' not found"}
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.execute("""
            INSERT INTO members (channel_id, agent_id, display_name, server_id, instance, port, icon, color, role, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel_id, agent_id) DO UPDATE SET
                display_name=excluded.display_name, last_seen=excluded.last_seen,
                icon=excluded.icon, color=excluded.color
        """, (ch['id'], agent_id, display_name, server_id, instance, int(port), icon, color, role, now))
        db.commit()
        return {"ok": True, "channel": ch['name'], "agent": agent_id}
    finally:
        db.close()


def leave_channel(channel_name, agent_id):
    """Remove an agent from a channel."""
    db = get_db()
    ch = resolve_channel(db, channel_name)
    if not ch:
        db.close()
        return {"error": f"Channel '{channel_name}' not found"}
    db.execute(
        "DELETE FROM members WHERE channel_id = ? AND agent_id = ?",
        (ch['id'], agent_id)
    )
    db.commit()
    db.close()
    return {"ok": True, "channel": ch['name'], "agent": agent_id}


def get_members(channel_name):
    """Get all members of a channel."""
    db = get_db()
    ch = resolve_channel(db, channel_name)
    if not ch:
        db.close()
        return {"error": f"Channel '{channel_name}' not found"}
    rows = db.execute(
        "SELECT * FROM members WHERE channel_id = ? ORDER BY joined_at",
        (ch['id'],)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def post_message(channel_name, agent_id, display_name, role, content, metadata=None):
    """Post a message to a channel. Auto-increments seq atomically."""
    db = get_db()
    ch = resolve_channel(db, channel_name)
    if not ch:
        db.close()
        return {"error": f"Channel '{channel_name}' not found"}
    now = datetime.now(timezone.utc).isoformat()
    # BEGIN IMMEDIATE takes a write lock upfront, preventing seq race conditions
    db.execute("BEGIN IMMEDIATE")
    row = db.execute(
        "SELECT COALESCE(MAX(seq), 0) + 1 as next_seq FROM messages WHERE channel_id = ?",
        (ch['id'],)
    ).fetchone()
    next_seq = row['next_seq']
    db.execute("""
        INSERT INTO messages (channel_id, agent_id, display_name, role, content, metadata, created_at, seq)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (ch['id'], agent_id, display_name, role, content, metadata, now, next_seq))
    db.commit()
    msg = db.execute("SELECT * FROM messages WHERE channel_id = ? AND seq = ?",
                     (ch['id'], next_seq)).fetchone()
    db.close()
    return dict(msg)


def get_messages(channel_name, since_seq=0, limit=100):
    """Get messages from a channel after a given sequence number."""
    db = get_db()
    ch = resolve_channel(db, channel_name)
    if not ch:
        db.close()
        return {"error": f"Channel '{channel_name}' not found"}
    rows = db.execute("""
        SELECT * FROM messages
        WHERE channel_id = ? AND seq > ?
        ORDER BY seq ASC
        LIMIT ?
    """, (ch['id'], int(since_seq), int(limit))).fetchall()
    db.close()
    return [dict(r) for r in rows]


def discover_agents():
    """Scan the drive for all configured agents across all servers."""
    agents = []
    try:
        dep_path = os.path.join(DRIVE_ROOT, 'deployment.json')
        if os.path.exists(dep_path):
            with open(dep_path) as f:
                deployment = json.load(f)
        else:
            deployment = {"servers": []}
    except (json.JSONDecodeError, IOError):
        deployment = {"servers": []}

    for server in deployment.get('servers', []):
        server_dir = os.path.join(DRIVE_ROOT, server.get('path', ''))
        server_id = server.get('id', 'unknown')

        # Check genesis instance
        genesis_lab = os.path.join(server_dir, 'genesis', 'lab.json')
        if os.path.exists(genesis_lab):
            try:
                with open(genesis_lab) as f:
                    cfg = json.load(f)
                agents.append({
                    "agent_id": f"genesis.{server_id}.genesis.{cfg.get('port', 0)}",
                    "display_name": cfg.get('name', 'Genesis'),
                    "server_id": server_id,
                    "instance": "genesis",
                    "platform": "genesis",
                    "port": cfg.get('port', 0),
                    "icon": cfg.get('icon', ''),
                    "color": cfg.get('color', ''),
                })
            except (json.JSONDecodeError, IOError):
                pass

        # Check platform instances
        platforms_path = os.path.join(server_dir, 'genesis', 'platforms.json')
        if os.path.exists(platforms_path):
            try:
                with open(platforms_path) as f:
                    platforms = json.load(f)
            except (json.JSONDecodeError, IOError):
                platforms = []

            for plat in platforms:
                instances_dir = os.path.join(server_dir, plat.get('path', ''), 'instances')
                if not os.path.isdir(instances_dir):
                    continue
                for name in os.listdir(instances_dir):
                    lab_json = os.path.join(instances_dir, name, 'lab.json')
                    if not os.path.exists(lab_json):
                        continue
                    try:
                        with open(lab_json) as f:
                            cfg = json.load(f)
                        agents.append({
                            "agent_id": f"{name}.{server_id}.{plat.get('id', 'unknown')}.{cfg.get('port', 0)}",
                            "display_name": cfg.get('name', name),
                            "server_id": server_id,
                            "instance": name,
                            "platform": plat.get('id', 'unknown'),
                            "port": cfg.get('port', 0),
                            "icon": cfg.get('icon', ''),
                            "color": cfg.get('color', ''),
                        })
                    except (json.JSONDecodeError, IOError):
                        pass

    return agents


# --- CLI interface ---

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: joint_db.py <command> [args...]"}))
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    try:
        if cmd == 'init':
            result = init_db()
        elif cmd == 'create-channel':
            if len(args) < 3:
                result = {"error": "Usage: create-channel <name> <topic> <created_by>"}
            else:
                result = create_channel(args[0], args[1], args[2])
        elif cmd == 'list-channels':
            result = list_channels()
        elif cmd == 'channel-info':
            if len(args) < 1:
                result = {"error": "Usage: channel-info <channel_name>"}
            else:
                result = channel_info(args[0])
        elif cmd == 'join':
            if len(args) < 6:
                result = {"error": "Usage: join <channel> <agent_id> <display_name> <server_id> <instance> <port> [icon] [color] [role]"}
            else:
                result = join_channel(
                    args[0], args[1], args[2], args[3], args[4], args[5],
                    args[6] if len(args) > 6 else '',
                    args[7] if len(args) > 7 else '',
                    args[8] if len(args) > 8 else 'agent'
                )
        elif cmd == 'leave':
            if len(args) < 2:
                result = {"error": "Usage: leave <channel> <agent_id>"}
            else:
                result = leave_channel(args[0], args[1])
        elif cmd == 'members':
            if len(args) < 1:
                result = {"error": "Usage: members <channel>"}
            else:
                result = get_members(args[0])
        elif cmd == 'post':
            if len(args) < 5:
                result = {"error": "Usage: post <channel> <agent_id> <display_name> <role> <content> [metadata]"}
            else:
                result = post_message(
                    args[0], args[1], args[2], args[3], args[4],
                    args[5] if len(args) > 5 else None
                )
        elif cmd == 'messages':
            if len(args) < 1:
                result = {"error": "Usage: messages <channel> [since_seq] [limit]"}
            else:
                result = get_messages(
                    args[0],
                    int(args[1]) if len(args) > 1 else 0,
                    int(args[2]) if len(args) > 2 else 100
                )
        elif cmd == 'discover-agents':
            result = discover_agents()
        else:
            result = {"error": f"Unknown command: {cmd}"}

        print(json.dumps(result, default=str))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == '__main__':
    main()
