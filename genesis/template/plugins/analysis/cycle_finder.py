#!/usr/bin/env python3
"""
Cycle Finder — Detect repeating patterns in event sequences.
Scans for intervals that are multiples of sacred numbers.

Usage:
  python3 scripts/cycle_finder.py                    # scan all events
  python3 scripts/cycle_finder.py --number 50        # scan for 50-year cycles only
  python3 scripts/cycle_finder.py --min-events 3     # clusters with 3+ events
"""

import os
import csv, sys, argparse
from pathlib import Path
from collections import defaultdict

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

SACRED_NUMBERS = {
    7: "Shemitah (sabbatical)",
    12: "Tribes/Apostles",
    40: "Testing/generation",
    49: "Jubilee cycle (7×7)",
    50: "Jubilee",
    70: "Lifespan/exile",
    120: "Striving (Gen 6:3)",
    400: "Sojourn",
    430: "Egypt sojourn",
    490: "70 weeks (70×7)",
}

def load_events():
    events = []
    with open(BASE / "data" / "events.csv") as f:
        for row in csv.DictReader(f):
            events.append({"name": row["name"], "year": int(row["year_ad"])})
    return sorted(events, key=lambda e: e["year"])

def find_cycles(events, target_number=None, min_events=2):
    """Find all pairs/clusters separated by multiples of sacred numbers."""
    results = defaultdict(list)

    numbers = {target_number: SACRED_NUMBERS.get(target_number, f"{target_number}-year cycle")} if target_number else SACRED_NUMBERS

    for i, a in enumerate(events):
        for j, b in enumerate(events):
            if j <= i:
                continue
            gap = b["year"] - a["year"]
            if gap <= 0:
                continue
            for num, label in numbers.items():
                if gap % num == 0:
                    mult = gap // num
                    if mult <= 30:  # reasonable range
                        key = f"{num}-year ({label})"
                        results[key].append({
                            "from": a["name"],
                            "from_year": a["year"],
                            "to": b["name"],
                            "to_year": b["year"],
                            "gap": gap,
                            "multiple": mult,
                        })

    # Write CSV
    outfile = BASE / "output" / "cycles.csv"
    rows = []
    for cycle_type, pairs in sorted(results.items()):
        for p in pairs:
            rows.append({
                "cycle_type": cycle_type,
                "from_event": p["from"],
                "from_year": p["from_year"],
                "to_event": p["to"],
                "to_year": p["to_year"],
                "gap_years": p["gap"],
                "multiple": f"{p['multiple']}×",
            })

    if rows:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    print(f"Cycles found: {len(rows)} pairs across {len(results)} cycle types")
    print(f"Output: {outfile}")

    # Summary
    print("\nSummary:")
    for cycle_type in sorted(results.keys()):
        print(f"  {cycle_type}: {len(results[cycle_type])} pairs")

def main():
    parser = argparse.ArgumentParser(description="Find sacred number cycles in events")
    parser.add_argument("--number", "-n", type=int, help="Specific cycle number to search")
    parser.add_argument("--min-events", "-m", type=int, default=2, help="Min events in cluster")
    args = parser.parse_args()

    events = load_events()
    print(f"Loaded {len(events)} events")
    find_cycles(events, target_number=args.number, min_events=args.min_events)

if __name__ == "__main__":
    main()
