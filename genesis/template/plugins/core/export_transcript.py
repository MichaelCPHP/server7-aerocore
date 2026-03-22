#!/usr/bin/env python3
"""Export a session transcript to the Jubilee Lab knowledge base.

Creates a markdown file in kb/transcripts/ and indexes it in output/transcripts.csv.

Usage:
    # Export from stdin (pipe or paste):
    python3 scripts/export_transcript.py --title "Session Title" --tags "tag1,tag2"

    # Export from a file:
    python3 scripts/export_transcript.py --title "Session Title" --file /path/to/transcript.md

    # With all metadata:
    python3 scripts/export_transcript.py \
        --title "7000-Year Plan Validation" \
        --tags "validation,millennium,sabbath,corrections" \
        --summary "Validated engine for 7000-year framework, corrected KB articles" \
        --topics "2037-convergence,7000-year-plan,transcript-system" \
        --file /path/to/content.md

    # List all transcripts:
    python3 scripts/export_transcript.py --list

    # Search transcripts:
    python3 scripts/export_transcript.py --search "2037"
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = Path(os.environ.get('LAB_INSTANCE', Path.cwd()))
KB_TRANSCRIPTS = ROOT_DIR / "kb" / "transcripts"
INDEX_FILE = ROOT_DIR / "output" / "transcripts.csv"

INDEX_FIELDS = [
    "id", "date", "time", "title", "slug", "tags", "summary",
    "topics", "word_count", "turn_count", "file_path"
]


def slugify(text):
    """Convert text to a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:80].rstrip('-')


def count_turns(content):
    """Estimate conversation turns from transcript content."""
    patterns = [
        r'^(?:User|Human|Michael|user|human)\s*[:\?]',
        r'^(?:Assistant|AI|Claude|Jubilee)\s*[:\?]',
        r'^---\s*$',
        r'^\*\*User\*\*',
        r'^\*\*Assistant\*\*',
        r'^> User:',
        r'^> Assistant:',
    ]
    turns = 0
    for line in content.split('\n'):
        for pattern in patterns:
            if re.match(pattern, line.strip()):
                turns += 1
                break
    return max(turns, 2)  # at minimum it's a back-and-forth


def next_id():
    """Get the next transcript ID from the index."""
    if not INDEX_FILE.exists():
        return 1
    with open(INDEX_FILE, newline='') as f:
        reader = csv.DictReader(f)
        ids = [int(row["id"]) for row in reader if row.get("id", "").isdigit()]
    return max(ids, default=0) + 1


def load_index():
    """Load existing transcript index."""
    if not INDEX_FILE.exists():
        return []
    with open(INDEX_FILE, newline='') as f:
        return list(csv.DictReader(f))


def save_index(rows):
    """Save transcript index."""
    INDEX_FILE.parent.mkdir(exist_ok=True)
    with open(INDEX_FILE, "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def export(title, content, tags="", summary="", topics="", project=""):
    """Export a transcript to KB and index it."""
    if project:
        target_dir = KB_TRANSCRIPTS / project
    else:
        target_dir = KB_TRANSCRIPTS
    target_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    tid = next_id()
    slug = slugify(title)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    filename = f"{date_str}-{slug}.md"
    filepath = target_dir / filename
    rel_path = f"kb/transcripts/{project + '/' if project else ''}{filename}"

    word_count = len(content.split())
    turn_count = count_turns(content)

    # Build the markdown file with frontmatter
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    topic_list = [t.strip() for t in topics.split(",") if t.strip()]

    md = f"""---
title: "{title}"
date: {date_str}
time: {time_str}
transcript_id: {tid}
tags: [{', '.join(tag_list)}]
topics: [{', '.join(topic_list)}]
summary: "{summary}"
word_count: {word_count}
turn_count: {turn_count}
---

# Session Transcript: {title}

**Date**: {date_str} {time_str}
**Transcript ID**: {tid}
**Words**: {word_count:,} | **Turns**: ~{turn_count}
**Tags**: {', '.join(tag_list) if tag_list else 'none'}
**Topics**: {', '.join(topic_list) if topic_list else 'none'}

{f"**Summary**: {summary}" if summary else ""}

---

{content}
"""

    filepath.write_text(md)

    # Update CSV index
    rows = load_index()
    rows.append({
        "id": tid,
        "date": date_str,
        "time": time_str,
        "title": title,
        "slug": slug,
        "tags": tags,
        "summary": summary,
        "topics": topics,
        "word_count": word_count,
        "turn_count": turn_count,
        "file_path": rel_path,
    })
    save_index(rows)

    print(f"Transcript exported successfully!")
    print(f"  ID:    {tid}")
    print(f"  File:  {rel_path}")
    print(f"  Words: {word_count:,}")
    print(f"  Turns: ~{turn_count}")
    print(f"  Index: output/transcripts.csv")
    return tid, rel_path


def list_transcripts():
    """List all transcripts."""
    rows = load_index()
    if not rows:
        print("No transcripts found.")
        return

    print(f"{'ID':>4}  {'Date':<12} {'Title':<45} {'Words':>7}  {'Tags'}")
    print("-" * 95)
    for r in rows:
        print(f"{r['id']:>4}  {r['date']:<12} {r['title'][:44]:<45} {r['word_count']:>7}  {r.get('tags', '')[:30]}")
    print(f"\nTotal: {len(rows)} transcripts")


def search_transcripts(query):
    """Search transcripts by keyword in title, tags, summary, topics."""
    rows = load_index()
    query_lower = query.lower()
    matches = []
    for r in rows:
        searchable = f"{r.get('title','')} {r.get('tags','')} {r.get('summary','')} {r.get('topics','')}".lower()
        if query_lower in searchable:
            matches.append(r)

    if not matches:
        print(f"No transcripts matching '{query}'.")
        return

    print(f"{'ID':>4}  {'Date':<12} {'Title':<45} {'Words':>7}  {'Tags'}")
    print("-" * 95)
    for r in matches:
        print(f"{r['id']:>4}  {r['date']:<12} {r['title'][:44]:<45} {r['word_count']:>7}  {r.get('tags', '')[:30]}")
    print(f"\nFound: {len(matches)} transcripts matching '{query}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export session transcript to Jubilee Lab KB")
    parser.add_argument("--title", type=str, help="Transcript title")
    parser.add_argument("--tags", type=str, default="", help="Comma-separated tags")
    parser.add_argument("--summary", type=str, default="", help="One-line summary")
    parser.add_argument("--topics", type=str, default="", help="Comma-separated topics discussed")
    parser.add_argument("--file", type=str, help="Read content from file instead of stdin")
    parser.add_argument("--project", type=str, default="", help="Project name (creates subdirectory under kb/transcripts/)")
    parser.add_argument("--list", action="store_true", help="List all transcripts")
    parser.add_argument("--search", type=str, help="Search transcripts by keyword")
    args = parser.parse_args()

    if args.list:
        list_transcripts()
    elif args.search:
        search_transcripts(args.search)
    elif args.title:
        if args.file:
            content = Path(args.file).read_text()
        else:
            print("Reading from stdin (paste content, then Ctrl+D to finish)...")
            content = sys.stdin.read()

        if not content.strip():
            print("Error: no content provided.")
            sys.exit(1)

        export(args.title, content, args.tags, args.summary, args.topics, args.project)
    else:
        parser.print_help()
