#!/usr/bin/env python3
"""
Signature Lifecycle — Dormancy, activation, and reactivation tracking.

For each named signature, maps its complete firing history across the timeline.
Detects dormancy periods, reactivation events, clustering patterns, and
era-specific affinities. Inspired by the JARED pattern discovery (R=0.20:
fired 3 times in 6000 years, then twice in a row).

Usage:
  python3 signature_lifecycle.py
"""

import os
import csv
import json
import math
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))


def load_database():
    p = BASE / "output" / "database.csv"
    if not p.exists():
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def load_signatures():
    p = BASE / "data" / "signatures.json"
    if not p.exists():
        return []
    with open(p) as f:
        return json.load(f)


def main():
    print("  Signature Lifecycle — dormancy and reactivation tracking...")

    events = load_database()
    if not events:
        print("    ERROR: database.csv not found")
        return

    # Group events by signature
    sig_events = {}
    for row in events:
        sig = row.get("signature", "").strip()
        if not sig:
            continue
        sig_events.setdefault(sig, []).append(row)

    # Sort each group by year
    for sig in sig_events:
        sig_events[sig].sort(key=lambda r: int(r["year_ad"]))

    # Timeline span
    all_years = [int(r["year_ad"]) for r in events]
    timeline_start = min(all_years)
    timeline_end = max(all_years)
    timeline_span = timeline_end - timeline_start

    results = []

    for sig_name, firings in sig_events.items():
        years = [int(r["year_ad"]) for r in firings]
        count = len(years)

        # Gap analysis
        gaps = []
        for i in range(1, len(years)):
            gaps.append(years[i] - years[i - 1])

        max_gap = max(gaps) if gaps else 0
        min_gap = min(gaps) if gaps else 0
        avg_gap = sum(gaps) / len(gaps) if gaps else 0
        median_gap = sorted(gaps)[len(gaps) // 2] if gaps else 0

        # Dormancy detection: longest gap vs average
        dormancy_ratio = max_gap / avg_gap if avg_gap > 0 else 0

        # Clustering: are firings bunched together?
        # Coefficient of variation of gaps (high = irregular, low = regular)
        if gaps and avg_gap > 0:
            std_gap = math.sqrt(sum((g - avg_gap) ** 2 for g in gaps) / len(gaps))
            gap_cv = std_gap / avg_gap
        else:
            gap_cv = 0

        # Era distribution
        epoch_counts = {}
        for r in firings:
            epoch = r.get("epoch", "unknown")
            epoch_counts[epoch] = epoch_counts.get(epoch, 0) + 1
        dominant_epoch = max(epoch_counts, key=epoch_counts.get) if epoch_counts else ""

        # Density: firings per 1000 years
        density = (count / timeline_span) * 1000 if timeline_span > 0 else 0

        # Reactivation detection: fired recently after long dormancy
        recent_reactivation = ""
        if count >= 3 and gaps:
            last_gap = gaps[-1]
            prior_avg = sum(gaps[:-1]) / len(gaps[:-1]) if len(gaps) > 1 else max_gap
            if prior_avg > 0 and last_gap < prior_avg * 0.5:
                recent_reactivation = f"Gap shrunk {prior_avg:.0f}yr -> {last_gap}yr"

        # Back-to-back detection (consecutive events within 20 years)
        back_to_back = []
        for i in range(1, len(years)):
            if years[i] - years[i - 1] <= 20:
                back_to_back.append(f"{years[i-1]}-{years[i]}")

        # First and last firing
        first_year = years[0]
        last_year = years[-1]
        active_span = last_year - first_year

        results.append({
            "signature": sig_name,
            "total_firings": count,
            "first_year": first_year,
            "last_year": last_year,
            "active_span": active_span,
            "density_per_1000yr": round(density, 2),
            "avg_gap": round(avg_gap, 1),
            "median_gap": median_gap,
            "min_gap": min_gap,
            "max_gap": max_gap,
            "dormancy_ratio": round(dormancy_ratio, 2),
            "gap_regularity_cv": round(gap_cv, 3),
            "dominant_epoch": dominant_epoch,
            "epoch_distribution": " | ".join(f"{e}:{c}" for e, c in sorted(epoch_counts.items())),
            "recent_reactivation": recent_reactivation,
            "back_to_back": " | ".join(back_to_back) if back_to_back else "",
            "firing_years": " | ".join(str(y) for y in years),
        })

    # Sort by dormancy ratio (most interesting lifecycle patterns first)
    results.sort(key=lambda r: -r["dormancy_ratio"])

    outfile = BASE / "output" / "signature_lifecycle.csv"
    if results:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    print(f"        -> {outfile.name}: {len(results)} signatures profiled")

    # Print most interesting lifecycles
    print()
    print("  SIGNATURE LIFECYCLE SUMMARY:")
    print(f"    {'Signature':<25} {'#':>4} {'Span':>6} {'AvgGap':>7} {'MaxGap':>7} {'Dorm':>6} {'Reactivation'}")
    print("    " + "-" * 85)
    for r in results[:20]:
        react = r['recent_reactivation'][:30] if r['recent_reactivation'] else ""
        print(f"    {r['signature'][:25]:<25} {r['total_firings']:>4} {r['active_span']:>6} "
              f"{r['avg_gap']:>7.0f} {r['max_gap']:>7} {r['dormancy_ratio']:>6.1f} {react}")

    # Flag reactivations
    reactivations = [r for r in results if r["recent_reactivation"]]
    if reactivations:
        print()
        print(f"  REACTIVATION ALERTS ({len(reactivations)} signatures):")
        for r in reactivations:
            print(f"    {r['signature']}: {r['recent_reactivation']}")

    # Flag back-to-back
    b2b = [r for r in results if r["back_to_back"]]
    if b2b:
        print()
        print(f"  BACK-TO-BACK CLUSTERS ({len(b2b)} signatures):")
        for r in b2b:
            print(f"    {r['signature']}: {r['back_to_back']}")


if __name__ == "__main__":
    main()
