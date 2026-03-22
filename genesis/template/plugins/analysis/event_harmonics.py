#!/usr/bin/env python3
"""
Event Harmonics — Astronomical phase overlay for every event.

Computes where each event sits in key planetary orbital cycles:
- 2-Pluto (495.88yr) — Daniel 490 resonance
- 3-Neptune (494.37yr) — Daniel 490 resonance
- 34-Saturn (1001.54yr) — Cosmic Day resonance
- Venus pentagram (7.993yr)
- Jupiter-Saturn conjunction (19.859yr)
- Saros eclipse (18.03yr)
- Metonic (19yr) — Hebrew calendar

Usage:
  python3 event_harmonics.py
"""

import os
import csv
import json
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

# Astronomical cycles (period in solar years)
ASTRO_CYCLES = {
    "pluto_2x":      495.88,
    "neptune_3x":    494.37,
    "saturn_34x":   1001.538,
    "venus_penta":     7.993,
    "conjunction":    19.859,
    "saros":          18.030,
    "metonic":        19.000,
}

# Phase names for composite signature
PHASE_NAMES = {
    (0.00, 0.05): "BEGIN",
    (0.05, 0.20): "EARLY",
    (0.20, 0.40): "RISING",
    (0.40, 0.60): "MID",
    (0.60, 0.80): "LATE",
    (0.80, 0.95): "CLOSING",
    (0.95, 1.00): "END",
}

CREATION_EPOCH = -4004


def phase_label(phase):
    for (lo, hi), name in PHASE_NAMES.items():
        if lo <= phase < hi:
            return name
    return "END"


def load_database():
    events = []
    with open(BASE / "output" / "database.csv") as f:
        for row in csv.DictReader(f):
            try:
                events.append({
                    "name": row["name"],
                    "year_ad": int(row["year_ad"]),
                    "signature": row.get("signature", ""),
                })
            except (ValueError, KeyError):
                continue
    return events


def main():
    print("  Event Harmonics — astronomical phase overlay...")

    events = load_database()
    results = []

    for e in events:
        year = e["year_ad"]
        elapsed = year - CREATION_EPOCH

        row = {
            "name": e["name"],
            "year_ad": year,
            "signature": e["signature"],
        }

        phase_labels = []
        boundary_hits = 0

        for cycle_name, period in ASTRO_CYCLES.items():
            phase = (elapsed % period) / period
            dist = min(phase, 1 - phase)
            row[f"{cycle_name}_phase"] = round(phase, 6)
            row[f"{cycle_name}_dist"] = round(dist, 6)

            label = phase_label(phase)
            phase_labels.append(f"{cycle_name}:{label}")

            if dist < 0.05:
                boundary_hits += 1

        row["astro_boundary_count"] = boundary_hits
        row["astro_signature"] = " | ".join(phase_labels)

        results.append(row)

    # Sort by boundary count
    results.sort(key=lambda r: (-r["astro_boundary_count"], r["year_ad"]))

    outfile = BASE / "output" / "event_harmonics.csv"
    with open(outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"        → {outfile.name}: {len(results)} events × {len(ASTRO_CYCLES)} cycles")

    # Print top events by astro boundary alignment
    print()
    print("  TOP 15 BY ASTRONOMICAL BOUNDARY ALIGNMENT:")
    print(f"    {'Event':<42} {'Year':>6} {'Hits':>5} {'Signature'}")
    print("    " + "─" * 70)
    for r in results[:15]:
        print(f"    {r['name'][:42]:<42} {r['year_ad']:>6} {r['astro_boundary_count']:>5} {r['signature']}")


if __name__ == "__main__":
    main()
