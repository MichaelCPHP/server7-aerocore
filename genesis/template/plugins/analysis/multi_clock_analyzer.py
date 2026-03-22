#!/usr/bin/env python3
"""
Multi-Clock Analyzer — Detects cross-clock conflicts and agreements.

For each event, compares its remainder position across all 10 clocks.
Flags events where clocks disagree (e.g., cosmic says WARNING but Israel
says JUBILEE). These conflicts reveal the most structurally interesting
events in the timeline.

Usage:
  python3 multi_clock_analyzer.py
"""

import os
import csv
import json
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

CLOCKS = [
    "cosmic", "israel", "church", "daniel", "moadim",
    "shemitah", "generation", "exile", "striving", "master",
]

# Signature bands — remainder ranges that map to named positions
BANDS = [
    ("JUBILEE",    0.00, 0.02),
    ("BEGINNING",  0.02, 0.08),
    ("EARLY",      0.08, 0.20),
    ("RISING",     0.20, 0.40),
    ("MIDPOINT",   0.40, 0.60),
    ("DECLINING",  0.60, 0.80),
    ("LATE",       0.80, 0.92),
    ("THRESHOLD",  0.92, 0.98),
    ("CLOSURE",    0.98, 1.00),
]


def classify_remainder(r):
    """Classify a remainder into a named band."""
    if r is None:
        return "INACTIVE"
    # Handle near-zero and near-one (wrapping)
    dist = min(r, 1 - r)
    if dist <= 0.02:
        return "JUBILEE"
    for name, lo, hi in BANDS:
        if lo <= r < hi:
            return name
    return "JUBILEE"  # r >= 0.98 wraps to boundary


def load_signatures():
    p = BASE / "data" / "signatures.json"
    if not p.exists():
        return []
    with open(p) as f:
        return json.load(f)


def main():
    print("  Multi-Clock Analyzer — cross-clock conflict detection...")

    db_path = BASE / "output" / "database.csv"
    if not db_path.exists():
        print("    ERROR: database.csv not found")
        return

    events = []
    with open(db_path) as f:
        events = list(csv.DictReader(f))

    results = []
    conflict_count = 0

    for row in events:
        name = row["name"]
        year_ad = int(row["year_ad"])

        bands = {}
        remainders = {}
        active_clocks = []

        for clock in CLOCKS:
            r_key = f"{clock}_remainder"
            val = row.get(r_key, "")
            if val and val != "0" or (val == "0" and int(row.get(f"{clock}_year_in_cycle", -1)) >= 0):
                try:
                    r = float(val)
                    band = classify_remainder(r)
                    bands[clock] = band
                    remainders[clock] = r
                    active_clocks.append(clock)
                except ValueError:
                    pass

        if len(active_clocks) < 2:
            continue

        # Detect conflicts: which unique bands are present?
        unique_bands = set(bands.values())
        unique_bands.discard("INACTIVE")

        # Find clocks at JUBILEE boundary
        jubilee_clocks = [c for c, b in bands.items() if b == "JUBILEE"]

        # Find clocks at THRESHOLD/CLOSURE
        threshold_clocks = [c for c, b in bands.items() if b in ("THRESHOLD", "CLOSURE")]

        # Conflict: at least one clock at JUBILEE and another far away
        has_conflict = len(unique_bands) > 1 and ("JUBILEE" in unique_bands or "THRESHOLD" in unique_bands)

        # Agreement: all active clocks in same band
        full_agreement = len(unique_bands) == 1

        # Calculate spread: distance between most extreme band positions
        if remainders:
            r_vals = list(remainders.values())
            # Use circular distance (0.98 and 0.02 are close)
            dists = [min(r, 1 - r) for r in r_vals]
            spread = max(dists) - min(dists) if dists else 0
        else:
            spread = 0

        # Band summary string
        band_summary = " | ".join(f"{c}={bands[c]}" for c in active_clocks)

        if has_conflict:
            conflict_count += 1

        results.append({
            "name": name,
            "year_ad": year_ad,
            "active_clocks": len(active_clocks),
            "unique_bands": len(unique_bands),
            "has_conflict": "YES" if has_conflict else "",
            "full_agreement": "YES" if full_agreement else "",
            "jubilee_clocks": len(jubilee_clocks),
            "jubilee_clock_names": " | ".join(jubilee_clocks) if jubilee_clocks else "",
            "threshold_clocks": len(threshold_clocks),
            "threshold_clock_names": " | ".join(threshold_clocks) if threshold_clocks else "",
            "spread": round(spread, 4),
            "band_summary": band_summary,
            "cosmic_band": bands.get("cosmic", ""),
            "israel_band": bands.get("israel", ""),
            "church_band": bands.get("church", ""),
            "daniel_band": bands.get("daniel", ""),
            "signature": row.get("signature", ""),
        })

    # Sort: conflicts first (by jubilee clock count desc), then by spread
    results.sort(key=lambda r: (
        -1 if r["has_conflict"] else 0,
        -r["jubilee_clocks"],
        -r["unique_bands"],
        -r["spread"],
    ))

    outfile = BASE / "output" / "multi_clock_analysis.csv"
    with open(outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"        -> {outfile.name}: {len(results)} events analyzed, {conflict_count} conflicts found")

    # Print conflicts
    conflicts = [r for r in results if r["has_conflict"]]
    if conflicts:
        print()
        print("  CROSS-CLOCK CONFLICTS (clocks disagree on position):")
        print(f"    {'Event':<40} {'Year':>6} {'Bands':>6} {'Jub':>4} {'Thr':>4} {'Summary'}")
        print("    " + "-" * 90)
        for r in conflicts[:25]:
            print(f"    {r['name'][:40]:<40} {r['year_ad']:>6} {r['unique_bands']:>6} "
                  f"{r['jubilee_clocks']:>4} {r['threshold_clocks']:>4} {r['band_summary'][:60]}")

    # Print full agreements
    agreements = [r for r in results if r["full_agreement"]]
    if agreements:
        print()
        print(f"  FULL AGREEMENT ({len(agreements)} events — all active clocks in same band):")
        for r in agreements[:10]:
            print(f"    {r['name'][:50]:<50} {r['year_ad']:>6} -> ALL {r['cosmic_band']}")


if __name__ == "__main__":
    main()
