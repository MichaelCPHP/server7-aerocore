#!/usr/bin/env python3
"""
Remainder Scanner — Find clusters of events sharing the same Jubilee remainder.
Identifies structural patterns in the Jubilee grid.

Usage:
  python3 scripts/remainder_scan.py                  # full scan
  python3 scripts/remainder_scan.py --target 0.42    # scan for .42 cluster
  python3 scripts/remainder_scan.py --tolerance 0.02 # wider tolerance
"""

import os
import csv, sys, argparse, json
from pathlib import Path
from collections import defaultdict

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

def load_database():
    rows = []
    with open(BASE / "output" / "database.csv") as f:
        for row in csv.DictReader(f):
            row["cosmic_remainder"] = float(row["cosmic_remainder"])
            row["cosmic_jubilee"] = float(row["cosmic_jubilee"])
            row["year_ad"] = int(row["year_ad"])
            rows.append(row)
    return rows

def scan_remainders(events, target=None, tolerance=0.01):
    """Group events by remainder value within tolerance."""
    if target is not None:
        # Single target scan
        matches = [e for e in events if abs(e["cosmic_remainder"] - target) <= tolerance]
        print(f"\n=== Remainder {target:.4f} (±{tolerance}) — {len(matches)} events ===")
        for e in sorted(matches, key=lambda x: x["year_ad"]):
            print(f"  {e['date']:>12}  R {e['cosmic_remainder']:.4f}  {e['name']}")
        return matches

    # Full scan — group by rounded remainder
    clusters = defaultdict(list)
    for e in events:
        key = round(e["cosmic_remainder"], 2)
        clusters[key].append(e)

    # Write CSV sorted by cluster size
    rows = []
    for remainder in sorted(clusters.keys()):
        group = clusters[remainder]
        if len(group) >= 2:
            for e in sorted(group, key=lambda x: x["year_ad"]):
                rows.append({
                    "remainder": f"{remainder:.2f}",
                    "cluster_size": len(group),
                    "event": e["name"],
                    "date": e["date"],
                    "jubilee": e["cosmic_jubilee"],
                    "signature": e.get("signature", ""),
                    "notes": e.get("notes", ""),
                })

    outfile = BASE / "output" / "remainder_clusters.csv"
    if rows:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    print(f"Output: {outfile}")
    print(f"\nClusters (2+ events):")
    for remainder in sorted(clusters.keys()):
        group = clusters[remainder]
        if len(group) >= 2:
            sig = group[0].get("signature", "")
            sig_label = f" [{sig}]" if sig else ""
            print(f"  R {remainder:.2f}{sig_label}: {len(group)} events")

def main():
    parser = argparse.ArgumentParser(description="Scan for remainder clusters")
    parser.add_argument("--target", "-t", type=float, help="Target remainder value")
    parser.add_argument("--tolerance", type=float, default=0.01, help="Tolerance band")
    args = parser.parse_args()

    events = load_database()
    print(f"Loaded {len(events)} events from database")
    scan_remainders(events, target=args.target, tolerance=args.tolerance)

if __name__ == "__main__":
    main()
