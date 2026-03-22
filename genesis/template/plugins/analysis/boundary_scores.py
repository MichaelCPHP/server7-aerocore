#!/usr/bin/env python3
"""
Boundary Scores — Composite alignment scoring across all 50 channels.

For each event, counts how many of the 50 clock×calendar channels place it
at an exact Jubilee boundary. Events scoring high are hitting boundaries
across multiple independent measurement systems simultaneously.

Usage:
  python3 boundary_scores.py
"""

import os
import csv
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))


def main():
    print("  Boundary Scores — composite alignment...")

    # Load the calendar grid
    grid_path = BASE / "output" / "calendar_grid.csv"
    if not grid_path.exists():
        print("    ERROR: calendar_grid.csv not found — run calendar_engine first")
        return

    events = []
    with open(grid_path) as f:
        reader = csv.DictReader(f)
        channel_cols = [c for c in reader.fieldnames if c.endswith("_R")]
        for row in reader:
            events.append(row)

    total_channels = len(channel_cols)
    results = []

    for row in events:
        name = row["name"]
        year_ad = row["year_ad"]

        hits_002 = []
        hits_005 = []
        hits_010 = []
        min_dist = 1.0
        best_channel = ""
        weighted_sum = 0.0

        for col in channel_cols:
            val = row[col]
            if val == "" or val is None:
                continue
            r = float(val)
            dist = min(r, 1 - r)

            if dist < 0.02:
                hits_002.append(col.replace("_R", ""))
            if dist < 0.05:
                hits_005.append(col.replace("_R", ""))
            if dist < 0.10:
                hits_010.append(col.replace("_R", ""))
            if dist < min_dist:
                min_dist = dist
                best_channel = col.replace("_R", "")

            # Weighted score: sharper peaks score higher
            if dist > 0:
                weighted_sum += 1.0 / dist
            else:
                weighted_sum += 1000  # Perfect boundary

        results.append({
            "name": name,
            "year_ad": year_ad,
            "boundary_count_002": len(hits_002),
            "boundary_count_005": len(hits_005),
            "boundary_count_010": len(hits_010),
            "boundary_channels_002": " | ".join(hits_002) if hits_002 else "",
            "max_resonance_channel": best_channel,
            "min_boundary_dist": round(min_dist, 6),
            "composite_score": round(weighted_sum, 2),
            "total_channels": total_channels,
        })

    # Sort by composite score descending
    results.sort(key=lambda r: -r["composite_score"])

    outfile = BASE / "output" / "boundary_scores.csv"
    with open(outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"        → {outfile.name}: {len(results)} events scored across {total_channels} channels")

    # Print top 15
    print()
    print("  TOP 15 BY COMPOSITE SCORE:")
    print(f"    {'Event':<42} {'Year':>6} {'R<.02':>6} {'R<.05':>6} {'R<.10':>6} {'Score':>8}")
    print("    " + "─" * 75)
    for r in results[:15]:
        print(f"    {r['name'][:42]:<42} {r['year_ad']:>6} {r['boundary_count_002']:>6} "
              f"{r['boundary_count_005']:>6} {r['boundary_count_010']:>6} {r['composite_score']:>8.0f}")


if __name__ == "__main__":
    main()
