#!/usr/bin/env python3
"""
Convergence Index — Unified multi-dimensional score per event.

Combines: boundary score + anchor proximity + complement match count +
multi-clock alignment + astronomical proximity into a single composite
convergence index. Events with high CI are hitting on multiple independent
measurement systems simultaneously.

Usage:
  python3 convergence_index.py
"""

import os
import csv
import json
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

# Anchor dates and their prophetic offsets
ANCHOR_OFFSETS = [
    (1900, [70, 80, 100, 120, 130, 140]),
    (1917, [50, 70, 80, 100, 120]),
    (1948, [40, 50, 70, 80]),
    (1967, [50, 70, 80]),
    (2017, [7, 14, 21]),
]

CLOCKS = [
    "cosmic", "israel", "church", "daniel", "moadim",
    "shemitah", "generation", "exile", "striving", "master",
]


def load_csv(name):
    p = BASE / "output" / name
    if not p.exists():
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def load_database():
    return load_csv("database.csv")


def build_boundary_lookup():
    """Map event name -> boundary score from boundary_scores.csv."""
    lookup = {}
    for row in load_csv("boundary_scores.csv"):
        lookup[row["name"]] = {
            "boundary_002": int(row.get("boundary_count_002", 0)),
            "boundary_005": int(row.get("boundary_count_005", 0)),
            "composite_score": float(row.get("composite_score", 0)),
        }
    return lookup


def build_complement_lookup():
    """Map event name -> complement pair count."""
    counts = {}
    for row in load_csv("complement_pairs.csv"):
        for key in ["event_a", "event_b"]:
            name = row.get(key, "")
            if name:
                counts[name] = counts.get(name, 0) + 1
    return counts


def count_clock_alignments(row, threshold=0.02):
    """Count how many clocks place this event near a boundary."""
    hits = []
    for clock in CLOCKS:
        r_key = f"{clock}_remainder"
        if r_key in row and row[r_key]:
            try:
                r = float(row[r_key])
                dist = min(r, 1 - r)
                if dist <= threshold:
                    hits.append(clock)
            except ValueError:
                pass
    return hits


def anchor_proximity_score(year_ad):
    """Count how many anchor+offset formulas target this year (exact or +/-2)."""
    exact = 0
    near = 0
    details = []
    for anchor, offsets in ANCHOR_OFFSETS:
        for offset in offsets:
            target = anchor + offset
            gap = abs(year_ad - target)
            if gap == 0:
                exact += 1
                details.append(f"{anchor}+{offset}")
            elif gap <= 2:
                near += 1
    return exact, near, details


def astro_proximity_score(row):
    """Score based on proximity to astronomical events."""
    score = 0
    for gap_col in ["conjunction_gap", "eclipse_gap", "blood_moon_gap"]:
        val = row.get(gap_col, "")
        if val:
            try:
                gap = abs(int(float(val)))
                if gap == 0:
                    score += 3
                elif gap <= 2:
                    score += 2
                elif gap <= 5:
                    score += 1
            except ValueError:
                pass
    return score


def shemitah_check(year_ad, anchor=2022):
    """Is this year a Shemitah year?"""
    return (year_ad - anchor) % 7 == 0


def main():
    print("  Convergence Index — unified multi-dimensional scoring...")

    events = load_database()
    if not events:
        print("    ERROR: database.csv not found")
        return

    boundary_lookup = build_boundary_lookup()
    complement_lookup = build_complement_lookup()

    results = []

    for row in events:
        name = row["name"]
        year_ad = int(row["year_ad"])

        # Dimension 1: Boundary score (from 50-channel grid)
        bd = boundary_lookup.get(name, {})
        boundary_002 = bd.get("boundary_002", 0)
        boundary_005 = bd.get("boundary_005", 0)
        boundary_composite = bd.get("composite_score", 0)

        # Dimension 2: Multi-clock alignment (how many clocks agree)
        clock_hits = count_clock_alignments(row)
        clock_alignment = len(clock_hits)

        # Dimension 3: Anchor proximity
        anchor_exact, anchor_near, anchor_details = anchor_proximity_score(year_ad)

        # Dimension 4: Complement pairs (how connected is this event)
        complement_count = complement_lookup.get(name, 0)

        # Dimension 5: Astronomical proximity
        astro_score = astro_proximity_score(row)

        # Dimension 6: Shemitah
        is_shemitah = shemitah_check(year_ad)

        # Dimension 7: Signature strength
        signature = row.get("signature", "")
        has_signature = 1 if signature else 0

        # ── Composite Convergence Index ──
        # Weighted sum — each dimension normalized to roughly 0-10 scale
        ci = (
            min(boundary_002, 10) * 3.0          # boundary hits (max 30)
            + clock_alignment * 4.0               # clock agreement (max 40)
            + anchor_exact * 8.0                  # exact anchor hit (max 40)
            + anchor_near * 3.0                   # near anchor hit (max 15)
            + min(complement_count, 5) * 2.0      # complement connectivity (max 10)
            + astro_score * 2.0                   # astronomical proximity (max 18)
            + (3.0 if is_shemitah else 0)         # shemitah bonus
            + has_signature * 2.0                 # signature bonus
        )

        results.append({
            "name": name,
            "year_ad": year_ad,
            "convergence_index": round(ci, 1),
            "boundary_hits_002": boundary_002,
            "boundary_hits_005": boundary_005,
            "clock_alignment_count": clock_alignment,
            "aligned_clocks": " | ".join(clock_hits) if clock_hits else "",
            "anchor_exact": anchor_exact,
            "anchor_near": anchor_near,
            "anchor_details": " | ".join(anchor_details) if anchor_details else "",
            "complement_pairs": complement_count,
            "astro_proximity": astro_score,
            "is_shemitah": "YES" if is_shemitah else "",
            "signature": signature,
        })

    results.sort(key=lambda r: -r["convergence_index"])

    outfile = BASE / "output" / "convergence_index.csv"
    with open(outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"        -> {outfile.name}: {len(results)} events scored")
    print()
    print("  TOP 20 BY CONVERGENCE INDEX:")
    print(f"    {'Event':<40} {'Year':>6} {'CI':>7} {'Bnd':>4} {'Clk':>4} {'Anc':>4} {'Cmp':>4} {'Ast':>4}")
    print("    " + "-" * 75)
    for r in results[:20]:
        print(f"    {r['name'][:40]:<40} {r['year_ad']:>6} {r['convergence_index']:>7.1f} "
              f"{r['boundary_hits_002']:>4} {r['clock_alignment_count']:>4} "
              f"{r['anchor_exact']:>4} {r['complement_pairs']:>4} {r['astro_proximity']:>4}")


if __name__ == "__main__":
    main()
