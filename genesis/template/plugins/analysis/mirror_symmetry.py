#!/usr/bin/env python3
"""
Mirror Symmetry Analyzer — Tests whether events mirror around a central point.
Default center: Jesus at J 80.000 (4 BC).

Usage:
  python3 scripts/mirror_symmetry.py
  python3 scripts/mirror_symmetry.py --center -4    # center on 4 BC
  python3 scripts/mirror_symmetry.py --tolerance 2   # ±2 year tolerance
"""

import os
import csv, json, argparse
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

def load_database():
    rows = []
    with open(BASE / "output" / "database.csv") as f:
        for row in csv.DictReader(f):
            row["year_ad"] = int(row["year_ad"])
            row["cosmic_jubilee"] = float(row["cosmic_jubilee"])
            row["cosmic_remainder"] = float(row["cosmic_remainder"])
            rows.append(row)
    return sorted(rows, key=lambda r: r["year_ad"])

def find_mirrors(events, center_year=-4, tolerance=3):
    """Find events that mirror each other around the center point."""
    before = [e for e in events if e["year_ad"] < center_year]
    after = [e for e in events if e["year_ad"] > center_year]

    mirrors = []
    for a in before:
        dist_a = center_year - a["year_ad"]
        for b in after:
            dist_b = b["year_ad"] - center_year
            if abs(dist_a - dist_b) <= tolerance:
                mirrors.append({
                    "before_event": a["name"],
                    "before_date": a["date"],
                    "before_distance": dist_a,
                    "center": center_year,
                    "after_event": b["name"],
                    "after_date": b["date"],
                    "after_distance": dist_b,
                    "difference": abs(dist_a - dist_b),
                    "same_remainder": "YES" if round(a["cosmic_remainder"], 2) == round(b["cosmic_remainder"], 2) else "",
                    "shared_signature": a.get("signature", "") if a.get("signature") == b.get("signature") and a.get("signature") else "",
                })

    # Sort by tightness of mirror
    mirrors.sort(key=lambda m: m["difference"])

    outfile = BASE / "output" / "mirror_symmetry.csv"
    if mirrors:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=mirrors[0].keys())
            writer.writeheader()
            writer.writerows(mirrors)

    print(f"Mirror symmetry around {center_year} (±{tolerance} years)")
    print(f"Found: {len(mirrors)} mirror pairs")
    print(f"Output: {outfile}")

    # Highlight exact mirrors
    exact = [m for m in mirrors if m["difference"] == 0]
    same_rem = [m for m in mirrors if m["same_remainder"]]
    shared_sig = [m for m in mirrors if m["shared_signature"]]

    if exact:
        print(f"\nExact mirrors ({len(exact)}):")
        for m in exact[:10]:
            print(f"  {m['before_event']} ({m['before_date']}) ←{m['before_distance']}yr→ CENTER ←{m['after_distance']}yr→ {m['after_event']} ({m['after_date']})")

    if same_rem:
        print(f"\nSame remainder ({len(same_rem)}):")
        for m in same_rem[:10]:
            print(f"  {m['before_event']} ↔ {m['after_event']} (both R {round(float(m.get('before_distance', 0)), 2)})")

def main():
    parser = argparse.ArgumentParser(description="Mirror symmetry analysis")
    parser.add_argument("--center", type=int, default=-4, help="Center year (default: -4 = 4 BC)")
    parser.add_argument("--tolerance", type=int, default=3, help="Year tolerance for matching")
    args = parser.parse_args()

    events = load_database()
    print(f"Loaded {len(events)} events")
    find_mirrors(events, center_year=args.center, tolerance=args.tolerance)

if __name__ == "__main__":
    main()
