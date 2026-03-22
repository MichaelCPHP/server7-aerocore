#!/usr/bin/env python3
"""
Convergence Analyzer — Tests whether multiple independent calculations
point to the same year/window.

Usage:
  python3 scripts/convergence.py                # default scan 2024-2040
  python3 scripts/convergence.py --start 2020 --end 2050
"""

import os
import csv, json, argparse
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

def load_clocks():
    with open(BASE / "data" / "clocks.json") as f:
        return json.load(f)

def analyze_convergence(start=2024, end=2040):
    clocks = load_clocks()

    # Fixed convergence formulas
    formulas = [
        ("Balfour + 120", 1917 + 120, "Genesis 6:3 lifespan from Balfour Declaration"),
        ("Jerusalem + 70", 1967 + 70, "Psalm 90:10 lifespan from Six-Day War"),
        ("Israel reborn + 80", 1948 + 80, "Psalm 90:10 'by reason of strength' from 1948"),
        ("Balfour + 2 Jubilees", 1917 + 100, "2 Jubilees from Balfour"),
        ("Six-Day War + 1 Jubilee", 1967 + 50, "1 Jubilee from Six-Day War"),
        ("Trump + Shemitah", 2017 + 7, "1 Shemitah from Jerusalem declaration"),
    ]

    # Clock closure years
    for name, clock in clocks.items():
        total = clock.get("total_cycles")
        if isinstance(total, int):
            closure = clock["start_year_ad"] + (total * clock["cycle_years"])
            formulas.append((f"{name} clock closes", closure, f"{name}: {total} cycles × {clock['cycle_years']} years from {clock['start_year_ad']}"))

    # Shemitah years (every 7 from a known anchor)
    shemitah_years = set()
    for y in range(start, end + 1):
        if (y - 2022) % 7 == 0:  # 2022 is a known shemitah anchor
            shemitah_years.add(y)

    # Score each year
    rows = []
    for year in range(start, end + 1):
        hits = []
        for label, target, desc in formulas:
            if target == year:
                hits.append(f"{label}: {desc}")

        is_shemitah = year in shemitah_years

        rows.append({
            "year": year,
            "convergence_count": len(hits),
            "is_shemitah": "YES" if is_shemitah else "",
            "formulas": " | ".join(hits) if hits else "",
        })

    # Sort by convergence count descending
    rows.sort(key=lambda r: -r["convergence_count"])

    outfile = BASE / "output" / "convergence.csv"
    with open(outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Convergence analysis: {start}-{end}")
    print(f"Output: {outfile}")
    print(f"\nTop convergence years:")
    for r in rows[:10]:
        shemitah = " [SHEMITAH]" if r["is_shemitah"] else ""
        if r["convergence_count"] > 0:
            print(f"  {r['year']}: {r['convergence_count']} convergences{shemitah}")
            for formula in r["formulas"].split(" | "):
                print(f"      → {formula}")

def main():
    parser = argparse.ArgumentParser(description="Analyze year convergences")
    parser.add_argument("--start", type=int, default=2024)
    parser.add_argument("--end", type=int, default=2040)
    args = parser.parse_args()
    analyze_convergence(args.start, args.end)

if __name__ == "__main__":
    main()
