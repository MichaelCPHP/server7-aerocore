#!/usr/bin/env python3
"""
Jubilee Lab — Tag Relationship Analyzer
Discovers connections between events through shared tags.
Finds clusters, co-occurrences, and cross-dimensional patterns.
"""

import os
import csv, argparse, json
from pathlib import Path
from collections import defaultdict, Counter
from itertools import combinations

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))
DATA = BASE / "data"
OUT = BASE / "output"

def load_events():
    with open(DATA / "events.csv", newline="") as f:
        return list(csv.DictReader(f))

def parse_tags(tag_str):
    if not tag_str:
        return []
    return [t.strip() for t in tag_str.split() if t.startswith('#')]

def get_root(tag):
    return '#' + tag.lstrip('#').split('.')[0]

def main():
    parser = argparse.ArgumentParser(description='Analyze tag relationships')
    parser.add_argument('--cooccurrence', action='store_true', help='Find most common tag pairs')
    parser.add_argument('--clusters', action='store_true', help='Find event clusters by shared tags')
    parser.add_argument('--bridges', action='store_true', help='Find events that bridge different categories')
    parser.add_argument('--timeline', help='Show tag frequency over time for a specific root (e.g., #nation)')
    parser.add_argument('--compare', nargs=2, help='Compare two tags (e.g., #nation.israel #nation.islam)')
    parser.add_argument('--top', type=int, default=20, help='Number of results to show')
    args = parser.parse_args()

    events = load_events()

    if args.cooccurrence:
        # Find most common tag pairs across events
        pair_counts = Counter()
        for ev in events:
            tags = parse_tags(ev.get("tags", ""))
            # Only pair across different root categories
            for t1, t2 in combinations(tags, 2):
                if get_root(t1) != get_root(t2):
                    pair = tuple(sorted([t1, t2]))
                    pair_counts[pair] += 1

        rows = []
        print(f"\nTop {args.top} tag co-occurrences (cross-category):")
        for (t1, t2), count in pair_counts.most_common(args.top):
            print(f"  {count:3d}× {t1} + {t2}")
            rows.append({'tag_1': t1, 'tag_2': t2, 'count': count})

        with open(OUT / "tag_cooccurrence.csv", "w", newline="") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        print(f"\n  → tag_cooccurrence.csv: {len(pair_counts)} pairs")
        return

    if args.clusters:
        # Find groups of events sharing 3+ tags
        event_tags = [(ev["name"], set(parse_tags(ev.get("tags", "")))) for ev in events]
        clusters = []
        seen = set()

        for i, (name_a, tags_a) in enumerate(event_tags):
            for j, (name_b, tags_b) in enumerate(event_tags[i+1:], i+1):
                shared = tags_a & tags_b
                # Filter to cross-category shared tags
                roots = set(get_root(t) for t in shared)
                if len(roots) >= 3:
                    key = tuple(sorted([name_a, name_b]))
                    if key not in seen:
                        seen.add(key)
                        clusters.append({
                            'event_a': name_a,
                            'event_b': name_b,
                            'shared_tags': len(shared),
                            'shared_roots': len(roots),
                            'tags': ' '.join(sorted(shared))
                        })

        clusters.sort(key=lambda c: c['shared_tags'], reverse=True)

        print(f"\nTop {args.top} event clusters (3+ shared root categories):")
        for c in clusters[:args.top]:
            print(f"  {c['shared_tags']} tags, {c['shared_roots']} roots: {c['event_a']} ↔ {c['event_b']}")

        with open(OUT / "tag_clusters.csv", "w", newline="") as f:
            if clusters:
                writer = csv.DictWriter(f, fieldnames=clusters[0].keys())
                writer.writeheader()
                writer.writerows(clusters[:200])
        print(f"\n  → tag_clusters.csv: {len(clusters)} pairs")
        return

    if args.bridges:
        # Find events that connect otherwise separate categories
        # A "bridge" event has tags from 5+ different root categories
        bridges = []
        for ev in events:
            tags = parse_tags(ev.get("tags", ""))
            roots = set(get_root(t) for t in tags)
            if len(roots) >= 5:
                bridges.append({
                    'name': ev['name'],
                    'year_ad': ev['year_ad'],
                    'root_count': len(roots),
                    'tag_count': len(tags),
                    'roots': ' '.join(sorted(roots)),
                    'tags': ' '.join(sorted(tags))
                })

        bridges.sort(key=lambda b: b['root_count'], reverse=True)

        print(f"\nBridge events (5+ root categories):")
        for b in bridges[:args.top]:
            print(f"  {b['root_count']} roots, {b['tag_count']} tags: {b['name']} ({b['year_ad']})")
            print(f"    Roots: {b['roots']}")

        with open(OUT / "tag_bridges.csv", "w", newline="") as f:
            if bridges:
                writer = csv.DictWriter(f, fieldnames=bridges[0].keys())
                writer.writeheader()
                writer.writerows(bridges)
        print(f"\n  → tag_bridges.csv: {len(bridges)} bridge events")
        return

    if args.compare:
        t1 = args.compare[0] if args.compare[0].startswith('#') else '#' + args.compare[0]
        t2 = args.compare[1] if args.compare[1].startswith('#') else '#' + args.compare[1]

        e1 = [ev for ev in events if t1 in parse_tags(ev.get("tags", ""))]
        e2 = [ev for ev in events if t2 in parse_tags(ev.get("tags", ""))]
        names1 = set(e["name"] for e in e1)
        names2 = set(e["name"] for e in e2)
        both = names1 & names2
        only1 = names1 - names2
        only2 = names2 - names1

        print(f"\n{t1} vs {t2}")
        print(f"  {t1} only: {len(only1)} events")
        print(f"  {t2} only: {len(only2)} events")
        print(f"  Both: {len(both)} events")
        if both:
            print(f"\n  Shared events:")
            for n in sorted(both):
                print(f"    • {n}")
        return

    if args.timeline:
        root = args.timeline if args.timeline.startswith('#') else '#' + args.timeline
        # Count events with this root tag per century
        centuries = defaultdict(lambda: defaultdict(int))
        for ev in events:
            tags = parse_tags(ev.get("tags", ""))
            yr = int(ev["year_ad"])
            century = yr // 100 * 100
            for t in tags:
                if t.startswith(root + '.'):
                    centuries[century][t] += 1

        print(f"\n{root} tags over time:")
        for century in sorted(centuries.keys()):
            tags_str = ', '.join(f"{t.split('.')[-1]}:{c}" for t, c in sorted(centuries[century].items()))
            total = sum(centuries[century].values())
            bar = '█' * min(total, 40)
            yr_label = f"{abs(century)} BC" if century < 0 else f"{century} AD"
            print(f"  {yr_label:>10}: {bar} {total} [{tags_str}]")
        return

    # Default: run all analyses and output summary
    print("Tag Relationship Analysis")
    print("=" * 50)

    # Basic stats
    all_tags = []
    for ev in events:
        all_tags.extend(parse_tags(ev.get("tags", "")))

    tag_freq = Counter(all_tags)
    root_freq = Counter(get_root(t) for t in all_tags)

    print(f"\nTotal tag assignments: {len(all_tags)}")
    print(f"Unique tags: {len(tag_freq)}")
    print(f"Root categories: {len(root_freq)}")

    print(f"\nTop 15 most used tags:")
    for tag, count in tag_freq.most_common(15):
        print(f"  {count:3d}× {tag}")

    print(f"\nRoot category distribution:")
    for root, count in root_freq.most_common():
        print(f"  {count:3d}× {root}")

    print(f"\nRun with --cooccurrence, --clusters, --bridges, --compare, or --timeline for detailed analysis")

if __name__ == "__main__":
    main()
