#!/usr/bin/env python3
"""
Threshold Analysis — Twilight zone detection across all clocks.

Detects events at position 49/50 (R >= 0.96) on any clock — the THRESHOLD
zone where one era is ending and the next is about to begin. Flags multi-clock
threshold convergence and tracks cascade sequences (THRESHOLD -> JUBILEE).

Based on the "twilight zone" research sessions (Mar 15-16, 2026).

Usage:
  python3 threshold_analysis.py
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

THRESHOLD_LOW = 0.96   # Entry into threshold zone
THRESHOLD_HIGH = 1.00  # Closure


def load_database():
    p = BASE / "output" / "database.csv"
    if not p.exists():
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def main():
    print("  Threshold Analysis — twilight zone detection...")

    events = load_database()
    if not events:
        print("    ERROR: database.csv not found")
        return

    # Build year->event index for cascade detection
    year_index = {}
    for row in events:
        y = int(row["year_ad"])
        year_index.setdefault(y, []).append(row)

    threshold_events = []
    cascade_events = []

    for row in events:
        name = row["name"]
        year_ad = int(row["year_ad"])

        threshold_clocks = []
        near_jubilee_clocks = []
        all_positions = {}

        for clock in CLOCKS:
            r_key = f"{clock}_remainder"
            yic_key = f"{clock}_year_in_cycle"
            val = row.get(r_key, "")
            if not val:
                continue
            try:
                r = float(val)
            except ValueError:
                continue

            all_positions[clock] = r

            # Threshold zone: R >= 0.96 (position 48-50 of a 50-year cycle)
            if r >= THRESHOLD_LOW:
                cycle_yrs = None
                try:
                    yic = int(row.get(yic_key, 0))
                    # Estimate years to next jubilee
                    clocks_json = json.load(open(BASE / "data" / "clocks.json"))
                    if clock in clocks_json:
                        cycle_yrs = clocks_json[clock]["cycle_years"]
                except (ValueError, FileNotFoundError):
                    pass

                years_to_jubilee = None
                if cycle_yrs:
                    years_to_jubilee = cycle_yrs - int(row.get(yic_key, 0))

                threshold_clocks.append({
                    "clock": clock,
                    "remainder": r,
                    "year_in_cycle": row.get(yic_key, ""),
                    "years_to_jubilee": years_to_jubilee,
                })

            # Near-jubilee: R <= 0.04 (just crossed)
            if r <= 0.04:
                near_jubilee_clocks.append(clock)

        if not threshold_clocks:
            continue

        # Multi-clock threshold convergence
        multi = len(threshold_clocks) >= 2

        # Cascade detection: is there an event within 1-6 years that hits JUBILEE
        # on the same clock(s)?
        cascade_targets = []
        for tc in threshold_clocks:
            ytj = tc.get("years_to_jubilee")
            if ytj and 1 <= ytj <= 10:
                target_year = year_ad + ytj
                if target_year in year_index:
                    for future_event in year_index[target_year]:
                        r_key = f"{tc['clock']}_remainder"
                        future_r = future_event.get(r_key, "")
                        if future_r:
                            try:
                                if float(future_r) <= 0.04:
                                    cascade_targets.append({
                                        "clock": tc["clock"],
                                        "target_year": target_year,
                                        "target_event": future_event["name"],
                                        "gap_years": ytj,
                                    })
                            except ValueError:
                                pass

        threshold_events.append({
            "name": name,
            "year_ad": year_ad,
            "threshold_clock_count": len(threshold_clocks),
            "multi_clock_threshold": "YES" if multi else "",
            "threshold_clocks": " | ".join(
                f"{t['clock']}(R={t['remainder']:.4f}, yr={t['year_in_cycle']})"
                for t in threshold_clocks
            ),
            "years_to_jubilee": " | ".join(
                f"{t['clock']}:{t['years_to_jubilee']}yr"
                for t in threshold_clocks if t.get("years_to_jubilee")
            ),
            "cascade_count": len(cascade_targets),
            "cascade_targets": " | ".join(
                f"{c['clock']}->{c['target_event']}({c['target_year']}, +{c['gap_years']}yr)"
                for c in cascade_targets
            ) if cascade_targets else "",
            "near_jubilee_clocks": " | ".join(near_jubilee_clocks) if near_jubilee_clocks else "",
            "signature": row.get("signature", ""),
            "epoch": row.get("epoch", ""),
        })

        if cascade_targets:
            cascade_events.extend(cascade_targets)

    # Sort by threshold clock count (multi-clock first)
    threshold_events.sort(key=lambda r: (-r["threshold_clock_count"], r["year_ad"]))

    # Write threshold events
    outfile = BASE / "output" / "threshold_analysis.csv"
    if threshold_events:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=threshold_events[0].keys())
            writer.writeheader()
            writer.writerows(threshold_events)

    print(f"        -> {outfile.name}: {len(threshold_events)} threshold events found")
    multi_count = sum(1 for t in threshold_events if t["multi_clock_threshold"])
    print(f"        -> {multi_count} multi-clock threshold convergences")
    print(f"        -> {len(cascade_events)} cascade sequences (THRESHOLD -> JUBILEE)")

    # Print multi-clock thresholds
    multis = [t for t in threshold_events if t["multi_clock_threshold"]]
    if multis:
        print()
        print("  MULTI-CLOCK THRESHOLD CONVERGENCES:")
        print(f"    {'Event':<40} {'Year':>6} {'#Clk':>5} {'Clocks'}")
        print("    " + "-" * 80)
        for t in multis:
            print(f"    {t['name'][:40]:<40} {t['year_ad']:>6} {t['threshold_clock_count']:>5} "
                  f"{t['threshold_clocks'][:50]}")

    # Print cascade sequences
    if cascade_events:
        print()
        print("  CASCADE SEQUENCES (THRESHOLD -> JUBILEE):")
        for c in cascade_events[:15]:
            print(f"    {c['clock']}: -> {c['target_event']} ({c['target_year']}, +{c['gap_years']} years)")


if __name__ == "__main__":
    main()
