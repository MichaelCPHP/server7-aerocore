#!/usr/bin/env python3
"""
Jubilee Lab — Hierarchical Tag Index Builder
Reads events.csv (tags column), builds a full tag taxonomy index,
and outputs tag_index.csv with parent-child relationships + event counts.
"""

import os
import csv, json, argparse, sys
from pathlib import Path
from collections import defaultdict

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))
DATA = BASE / "data"
OUT = BASE / "output"

def load_events():
    with open(DATA / "events.csv", newline="") as f:
        return list(csv.DictReader(f))

def parse_tags(tag_str):
    """Parse a tag string like '#epoch.2 #cat.war #nation.israel' into list of tags"""
    if not tag_str:
        return []
    return [t.strip() for t in tag_str.split() if t.startswith('#')]

def build_index(events):
    """Build hierarchical tag index from all events"""
    tag_events = defaultdict(list)  # tag -> [event names]
    tag_tree = {}  # full tag -> {parent, children, depth}

    for ev in events:
        tags = parse_tags(ev.get("tags", ""))
        for tag in tags:
            tag_events[tag].append(ev["name"])

            # Build tree nodes for this tag and all ancestors
            parts = tag.lstrip('#').split('.')
            for depth in range(len(parts)):
                node = '#' + '.'.join(parts[:depth+1])
                if node not in tag_tree:
                    parent = '#' + '.'.join(parts[:depth]) if depth > 0 else ''
                    tag_tree[node] = {
                        'tag': node,
                        'parent': parent,
                        'depth': depth,
                        'label': parts[depth],
                        'full_path': node
                    }

    return tag_events, tag_tree

def write_index(tag_events, tag_tree):
    """Write tag_index.csv"""
    rows = []
    for tag in sorted(tag_tree.keys()):
        node = tag_tree[tag]
        events = tag_events.get(tag, [])
        children = [t for t, n in tag_tree.items() if n['parent'] == tag]

        rows.append({
            'tag': tag,
            'parent': node['parent'],
            'depth': node['depth'],
            'label': node['label'],
            'event_count': len(events),
            'child_count': len(children),
            'children': ' | '.join(sorted(children)),
            'events': ' | '.join(events[:20]) + (f' (+{len(events)-20} more)' if len(events) > 20 else ''),
        })

    outfile = OUT / "tag_index.csv"
    if rows:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    return rows

def write_tag_matrix(events):
    """Write tag_matrix.csv — events × top-level tag categories (for filtering)"""
    # Get all root tags
    all_tags = set()
    for ev in events:
        for tag in parse_tags(ev.get("tags", "")):
            root = '#' + tag.lstrip('#').split('.')[0]
            all_tags.add(root)

    roots = sorted(all_tags)
    rows = []
    for ev in events:
        tags = parse_tags(ev.get("tags", ""))
        tag_roots = {'#' + t.lstrip('#').split('.')[0] for t in tags}
        row = {'name': ev['name'], 'year_ad': ev['year_ad'], 'tags': ev.get('tags', '')}
        for root in roots:
            row[root] = 1 if root in tag_roots else 0
        rows.append(row)

    outfile = OUT / "tag_matrix.csv"
    if rows:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

def print_tree(tag_tree, tag_events, root='', indent=0):
    """Print tag tree to stdout"""
    children = sorted([t for t, n in tag_tree.items() if n['parent'] == root])
    for child in children:
        count = len(tag_events.get(child, []))
        node = tag_tree[child]
        prefix = '  ' * indent + ('├─ ' if indent > 0 else '')
        print(f"{prefix}{node['label']} ({count} events) [{child}]")
        print_tree(tag_tree, tag_events, root=child, indent=indent+1)

def main():
    parser = argparse.ArgumentParser(description='Build hierarchical tag index')
    parser.add_argument('--tag', help='Show events for a specific tag (e.g., #cat.war)')
    parser.add_argument('--tree', action='store_true', help='Print tag tree to stdout')
    parser.add_argument('--search', help='Find tags matching a keyword')
    parser.add_argument('--intersect', nargs=2, help='Find events with BOTH tags')
    args = parser.parse_args()

    events = load_events()
    tag_events, tag_tree = build_index(events)

    if args.tag:
        tag = args.tag if args.tag.startswith('#') else '#' + args.tag
        matches = tag_events.get(tag, [])
        # Also check children
        child_tags = [t for t in tag_tree if t.startswith(tag + '.')]
        for ct in child_tags:
            matches.extend(tag_events.get(ct, []))
        matches = sorted(set(matches))
        print(f"\n{tag}: {len(matches)} events")
        for m in matches:
            print(f"  • {m}")
        return

    if args.search:
        q = args.search.lower()
        matches = [t for t in sorted(tag_tree.keys()) if q in t.lower()]
        print(f"\nTags matching '{args.search}':")
        for t in matches:
            count = len(tag_events.get(t, []))
            print(f"  {t} ({count} events)")
        return

    if args.intersect:
        t1 = args.intersect[0] if args.intersect[0].startswith('#') else '#' + args.intersect[0]
        t2 = args.intersect[1] if args.intersect[1].startswith('#') else '#' + args.intersect[1]
        e1 = set(tag_events.get(t1, []))
        e2 = set(tag_events.get(t2, []))
        both = sorted(e1 & e2)
        print(f"\n{t1} ∩ {t2}: {len(both)} events")
        for m in both:
            print(f"  • {m}")
        return

    # Default: build full index
    rows = write_index(tag_events, tag_tree)
    write_tag_matrix(events)

    print(f"\nTag Index Built:")
    print(f"  Unique tags: {len(tag_tree)}")
    print(f"  Root categories: {len([t for t,n in tag_tree.items() if n['depth']==0])}")
    print(f"  tag_index.csv: {len(rows)} rows")
    print(f"  tag_matrix.csv: {len(events)} events × root categories")

    if args.tree:
        print(f"\n{'─'*60}")
        print_tree(tag_tree, tag_events)
    else:
        # Print summary
        roots = sorted([t for t, n in tag_tree.items() if n['depth'] == 0])
        print(f"\nRoot categories:")
        for r in roots:
            children = [t for t, n in tag_tree.items() if n['parent'] == r]
            total = sum(len(tag_events.get(c, [])) for c in [r] + [t for t in tag_tree if t.startswith(r + '.')])
            print(f"  {r}: {len(children)} children, ~{total} event-tags")

if __name__ == "__main__":
    main()
