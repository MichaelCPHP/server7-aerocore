#!/usr/bin/env python3
"""
Future Convergence Monitor — Projects forward to find years with multi-condition
convergences across clocks, signatures, astronomical events, and sacred numbers.

Specifically watches for:
- .666 unfired position convergences
- Shemitah + Jubilee boundary years
- Multi-clock closure years
- Astronomical conjunction/eclipse proximity
- Anchor date offsets landing in future

Usage:
  python3 future_convergence.py
  python3 future_convergence.py --start 2024 --end 2070
"""

import os
import csv
import json
import argparse
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))


def load_clocks():
    with open(BASE / "data" / "clocks.json") as f:
        return json.load(f)


def load_astro(name):
    p = BASE / "data" / f"astro_{name}.csv"
    if not p.exists():
        return []
    years = []
    with open(p) as f:
        for row in csv.DictReader(f):
            try:
                y = int(row.get("year_ad", row.get("year_start", 0)))
                years.append(y)
            except (ValueError, KeyError):
                pass
    return years


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=2024)
    parser.add_argument("--end", type=int, default=2070)
    args = parser.parse_args()

    print(f"  Future Convergence Monitor — scanning {args.start}-{args.end}...")

    clocks = load_clocks()
    conjunctions = set(load_astro("conjunctions"))
    eclipses = set(load_astro("eclipses"))
    blood_moons = set(load_astro("blood_moons"))

    # Anchor formulas
    anchors = [
        ("Balfour+120", 1917 + 120),
        ("Balfour+2Jub", 1917 + 100),
        ("Israel+80", 1948 + 80),
        ("Israel+Jub", 1948 + 50),
        ("SixDay+70", 1967 + 70),
        ("SixDay+Jub", 1967 + 50),
        ("Trump+Shem", 2017 + 7),
        ("Trump+2Shem", 2017 + 14),
        ("Trump+3Shem", 2017 + 21),
        ("Israel+100", 1948 + 100),
        ("Jerusalem+80", 1967 + 80),
    ]

    # Known shemitah anchor
    shemitah_anchor = 2022

    # Signature remainder targets
    sig_targets = {
        ".666 WARNING": 0.666,
        "CROSS (0.54)": 0.54,
        "COVENANT (0.00)": 0.00,
        "AUTHORITY (0.38)": 0.38,
    }

    results = []

    for year in range(args.start, args.end + 1):
        conditions = []
        score = 0

        # Check Shemitah
        is_shemitah = (year - shemitah_anchor) % 7 == 0
        if is_shemitah:
            conditions.append("SHEMITAH")
            score += 3

        # Check clock positions
        boundary_clocks = []
        for cname, clock in clocks.items():
            start = clock["start_year_ad"]
            cycle = clock["cycle_years"]
            elapsed = year - start
            if elapsed < 0:
                continue
            remainder = (elapsed % cycle) / cycle

            # Exact boundary
            if min(remainder, 1 - remainder) <= 0.02:
                boundary_clocks.append(cname)
                score += 5

            # Check closure
            total = clock.get("total_cycles")
            if isinstance(total, int):
                closure = start + total * cycle
                if year == closure:
                    conditions.append(f"{cname} CLOSES")
                    score += 10

            # Check .666 position
            if abs(remainder - 0.666) < 0.01:
                conditions.append(f"{cname} at .666")
                score += 4

        if boundary_clocks:
            conditions.append(f"JUBILEE({','.join(boundary_clocks)})")

        # Check slot (Shemitah position within 7-year cycle)
        slot = (year - shemitah_anchor) % 7
        if slot == 6:
            conditions.append("SLOT-6")
            score += 2

        # Check anchor hits
        anchor_hits = []
        for label, target in anchors:
            if target == year:
                anchor_hits.append(label)
                score += 5
            elif abs(target - year) <= 1:
                anchor_hits.append(f"~{label}")
                score += 2
        if anchor_hits:
            conditions.append(f"ANCHOR({','.join(anchor_hits)})")

        # Astronomical proximity
        astro_hits = []
        if year in conjunctions:
            astro_hits.append("conjunction")
            score += 2
        if year in eclipses:
            astro_hits.append("eclipse")
            score += 2
        if year in blood_moons:
            astro_hits.append("blood-moon")
            score += 3
        # Check ±1 year
        for y in [year - 1, year + 1]:
            if y in conjunctions:
                astro_hits.append("~conjunction")
                score += 1
            if y in blood_moons:
                astro_hits.append("~blood-moon")
                score += 1
        if astro_hits:
            conditions.append(f"ASTRO({','.join(astro_hits)})")

        # Triple .666 check (Shemitah + .666 + Slot 6)
        has_666 = any(".666" in c for c in conditions)
        if is_shemitah and has_666 and slot == 6:
            conditions.append("TRIPLE-666")
            score += 15

        if score > 0:
            results.append({
                "year": year,
                "convergence_score": score,
                "condition_count": len(conditions),
                "is_shemitah": "YES" if is_shemitah else "",
                "slot": slot,
                "boundary_clocks": len(boundary_clocks),
                "anchor_hits": len(anchor_hits),
                "conditions": " | ".join(conditions),
            })

    results.sort(key=lambda r: -r["convergence_score"])

    outfile = BASE / "output" / "future_convergence.csv"
    if results:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    print(f"        -> {outfile.name}: {len(results)} years with convergence signals")

    print()
    print("  FUTURE CONVERGENCE HOTSPOTS:")
    print(f"    {'Year':>6} {'Score':>6} {'#Cond':>6} {'Shem':>5} {'Conditions'}")
    print("    " + "-" * 80)
    for r in results[:20]:
        print(f"    {r['year']:>6} {r['convergence_score']:>6} {r['condition_count']:>6} "
              f"{'YES' if r['is_shemitah'] else '':>5} {r['conditions'][:60]}")


if __name__ == "__main__":
    main()
