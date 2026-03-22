#!/usr/bin/env python3
"""
Patriarch Lifecycle Analyzer — Maps biographical timings against Jubilee
positions for key biblical figures.

For each patriarch/leader, maps birth → key events → death and tests
whether major life transitions occur at Jubilee boundaries across
multiple clocks. Calculates alignment scores vs random baseline.

Usage:
  python3 patriarch_lifecycle.py
"""

import os
import csv
import json
from pathlib import Path
from collections import defaultdict

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

CLOCKS = [
    "cosmic", "israel", "church", "daniel", "moadim",
    "shemitah", "generation", "exile", "striving", "master",
]

# Key figures to track (name patterns to match in events)
FIGURES = [
    "Adam", "Seth", "Enoch", "Noah", "Abraham", "Isaac", "Jacob", "Joseph",
    "Moses", "Joshua", "Samuel", "David", "Solomon", "Elijah", "Elisha",
    "Isaiah", "Jeremiah", "Daniel", "Ezra", "Nehemiah",
    "Jesus", "Paul", "John",
]


def load_database():
    p = BASE / "output" / "database.csv"
    if not p.exists():
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def match_figure(event_name, figure):
    """Check if an event name relates to a figure."""
    name_lower = event_name.lower()
    fig_lower = figure.lower()

    # Direct match
    if fig_lower in name_lower:
        return True

    # Special cases
    aliases = {
        "jesus": ["christ", "crucifixion", "resurrection", "baptism", "transfiguration",
                   "sermon on the mount", "last supper", "ascension", "temptation"],
        "moses": ["exodus", "burning bush", "red sea", "sinai", "tabernacle built"],
        "abraham": ["abram"],
        "jacob": ["israel wrestles"],
        "paul": ["saul converted", "damascus road", "shipwreck"],
        "john": ["john the baptist", "john exiled", "revelation written"],
    }
    for alias in aliases.get(fig_lower, []):
        if alias in name_lower:
            return True

    return False


def boundary_distance(row, clock):
    """Get how close this event is to a boundary on the given clock."""
    r_key = f"{clock}_remainder"
    val = row.get(r_key, "")
    if not val:
        return None
    try:
        r = float(val)
        return min(r, 1 - r)
    except ValueError:
        return None


def main():
    print("  Patriarch Lifecycle Analyzer — biographical timing vs. Jubilee...")

    events = load_database()
    if not events:
        print("    ERROR: database.csv not found")
        return

    results = []

    for figure in FIGURES:
        # Find all events related to this figure
        related = []
        for row in events:
            if match_figure(row["name"], figure):
                related.append(row)

        if not related:
            continue

        # Sort by year
        related.sort(key=lambda r: int(r["year_ad"]))

        # Calculate alignment for each event
        event_details = []
        total_boundary_hits = 0
        total_checks = 0

        for row in related:
            year_ad = int(row["year_ad"])
            hits = []
            near_hits = []

            for clock in CLOCKS:
                dist = boundary_distance(row, clock)
                if dist is not None:
                    total_checks += 1
                    if dist <= 0.02:
                        hits.append(clock)
                        total_boundary_hits += 1
                    elif dist <= 0.05:
                        near_hits.append(clock)

            event_details.append({
                "event": row["name"],
                "year": year_ad,
                "boundary_hits": len(hits),
                "near_hits": len(near_hits),
                "hit_clocks": " | ".join(hits),
                "signature": row.get("signature", ""),
            })

        # Lifespan span
        first_year = int(related[0]["year_ad"])
        last_year = int(related[-1]["year_ad"])
        span = last_year - first_year

        # Alignment score: boundary hits / total checks
        alignment_score = total_boundary_hits / total_checks if total_checks > 0 else 0

        # Expected random alignment (2% threshold on both ends = 4% chance per check)
        expected_random = total_checks * 0.04
        observed_vs_expected = total_boundary_hits / expected_random if expected_random > 0 else 0

        results.append({
            "figure": figure,
            "event_count": len(related),
            "first_year": first_year,
            "last_year": last_year,
            "span_years": span,
            "total_boundary_hits": total_boundary_hits,
            "total_checks": total_checks,
            "alignment_score": round(alignment_score, 4),
            "vs_random": round(observed_vs_expected, 2),
            "events": " | ".join(f"{d['event']}({d['year']},B={d['boundary_hits']})" for d in event_details),
            "best_aligned_event": max(event_details, key=lambda d: d["boundary_hits"])["event"] if event_details else "",
        })

    # Sort by alignment score (most aligned first)
    results.sort(key=lambda r: -r["alignment_score"])

    outfile = BASE / "output" / "patriarch_lifecycle.csv"
    if results:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    print(f"        -> {outfile.name}: {len(results)} figures profiled")

    print()
    print("  PATRIARCH ALIGNMENT SCORES:")
    print(f"    {'Figure':<15} {'Events':>7} {'Span':>6} {'Hits':>5} {'Checks':>7} {'Align':>7} {'vs Rand':>8}")
    print("    " + "-" * 65)
    for r in results:
        print(f"    {r['figure'][:15]:<15} {r['event_count']:>7} {r['span_years']:>6} "
              f"{r['total_boundary_hits']:>5} {r['total_checks']:>7} "
              f"{r['alignment_score']:>7.3f} {r['vs_random']:>7.1f}x")

    # Summary
    if results:
        avg_vs_random = sum(r["vs_random"] for r in results) / len(results)
        print(f"\n    Average vs. random: {avg_vs_random:.1f}x")
        above = sum(1 for r in results if r["vs_random"] > 1.5)
        print(f"    Figures >1.5x random: {above}/{len(results)}")


if __name__ == "__main__":
    main()
