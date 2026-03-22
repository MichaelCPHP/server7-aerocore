#!/usr/bin/env python3
"""Anchor Date Convergence Analysis.

Applies +70 (Psalms lifespan), +80 (Psalms 'by strength'), +100 (generation),
and +120 (Genesis maximum) to the four anchor dates and identifies convergences.

Usage:
    python3 scripts/anchor_dates.py                # full analysis
    python3 scripts/anchor_dates.py --target 2037  # check a specific year
"""

import argparse
import csv
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.environ.get("LAB_INSTANCE", os.path.dirname(SCRIPT_DIR))
OUTPUT_FILE = os.path.join(ROOT_DIR, "output", "anchor_dates.csv")

# The four anchor dates
ANCHORS = [
    {"year": 1900, "name": "Century opens", "event": "20th century begins"},
    {"year": 1917, "name": "Balfour Declaration", "event": "British support for Jewish homeland"},
    {"year": 1948, "name": "Israel reborn", "event": "Nation in a day (Isaiah 66:8)"},
    {"year": 1967, "name": "Jerusalem recaptured", "event": "Six-Day War — Jewish sovereignty restored"},
]

# Biblical time measures
MEASURES = [
    {"years": 70, "name": "Psalms 90:10 lifespan", "ref": "Psalm 90:10 — 'The days of our years are threescore years and ten'"},
    {"years": 80, "name": "Psalms 90:10 by strength", "ref": "Psalm 90:10 — 'and if by reason of strength they be fourscore years'"},
    {"years": 100, "name": "Generation (Law of First Mention)", "ref": "Genesis 15 — 400 years / 4 generations = 100"},
    {"years": 120, "name": "Genesis 6:3 maximum lifespan", "ref": "Genesis 6:3 — 'his days shall be an hundred and twenty years'"},
]

# Jubilee window (strict Masoretic)
JUBILEE_WINDOW = (1996, 2067)


def run(target_year=None):
    results = []
    convergences = {}  # year -> list of calculations

    for anchor in ANCHORS:
        for measure in MEASURES:
            end_year = anchor["year"] + measure["years"]
            in_window = JUBILEE_WINDOW[0] <= end_year <= JUBILEE_WINDOW[1]
            from_2026 = end_year - 2026

            row = {
                "anchor_year": anchor["year"],
                "anchor_name": anchor["name"],
                "measure_years": measure["years"],
                "measure_name": measure["name"],
                "end_year": end_year,
                "in_jubilee_window": "YES" if in_window else "no",
                "years_from_now": from_2026,
                "reference": measure["ref"],
            }
            results.append(row)

            # Track convergences
            if end_year not in convergences:
                convergences[end_year] = []
            convergences[end_year].append(f"{anchor['name']} + {measure['years']}")

    # Write CSV
    fieldnames = [
        "anchor_year", "anchor_name", "measure_years", "measure_name",
        "end_year", "in_jubilee_window", "years_from_now", "reference"
    ]
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(results, key=lambda r: (r["end_year"], r["anchor_year"])))

    # Print summary
    print(f"Anchor Date Convergence Analysis")
    print(f"{'=' * 60}")
    print(f"Anchors: {', '.join(str(a['year']) for a in ANCHORS)}")
    print(f"Measures: +{', +'.join(str(m['years']) for m in MEASURES)}")
    print(f"Jubilee window: {JUBILEE_WINDOW[0]}–{JUBILEE_WINDOW[1]}")
    print()

    # Show the full table
    print(f"{'Anchor':>6s}  {'Event':<25s}  {'+ yrs':>5s}  {'= End':>6s}  {'Jubilee?':>8s}  {'From now':>8s}")
    print("-" * 75)
    for r in sorted(results, key=lambda r: r["end_year"]):
        marker = " ★" if r["in_jubilee_window"] == "YES" else ""
        print(f"{r['anchor_year']:>6d}  {r['anchor_name']:<25s}  +{r['measure_years']:>4d}  = {r['end_year']:>4d}  {r['in_jubilee_window']:>8s}  {r['years_from_now']:>+7d}{marker}")

    # Show convergences (years hit by 2+ calculations)
    print(f"\n{'=' * 60}")
    print("CONVERGENCE POINTS (2+ independent calculations)")
    print(f"{'=' * 60}")
    for year in sorted(convergences.keys()):
        calcs = convergences[year]
        if len(calcs) >= 2:
            in_w = "★ IN WINDOW" if JUBILEE_WINDOW[0] <= year <= JUBILEE_WINDOW[1] else ""
            print(f"\n  {year} — {len(calcs)} convergences {in_w}")
            for c in calcs:
                print(f"    → {c}")

    # Target year check
    if target_year:
        print(f"\n{'=' * 60}")
        print(f"TARGET YEAR: {target_year}")
        print(f"{'=' * 60}")
        hits = [r for r in results if r["end_year"] == target_year]
        if hits:
            for h in hits:
                print(f"  {h['anchor_name']} + {h['measure_years']} ({h['measure_name']})")
        else:
            print(f"  No anchor+measure combination produces {target_year}")

    # The 2020 mirror pattern
    print(f"\n{'=' * 60}")
    print("2020 MIRROR PATTERN")
    print(f"{'=' * 60}")
    for anchor in ANCHORS[1:]:  # skip 1900
        end_120 = anchor["year"] + 120
        remaining = end_120 - 2020
        last_two = remaining % 100
        anchor_last_two = anchor["year"] % 100
        match = "✓ MIRROR" if last_two == anchor_last_two else ""
        print(f"  {anchor['year']} +120 = {end_120} → from 2020: {remaining} yrs remaining (last digits: {last_two}) {match}")

    print(f"\nOutput: {OUTPUT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Anchor Date Convergence Analysis")
    parser.add_argument("--target", type=int, help="Check a specific target year")
    args = parser.parse_args()
    run(target_year=args.target)
