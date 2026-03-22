#!/usr/bin/env python3
"""
Frequency Acceleration Analysis — Measure how event density increases over time.

Counts events per century from Creation to present, calculates acceleration,
and identifies the compression pattern.

Usage:
  python3 scripts/frequency.py                    # full analysis
  python3 scripts/frequency.py --bucket 50        # 50-year buckets
  python3 scripts/frequency.py --bucket 500       # 500-year buckets
"""

import os
import csv, argparse
from pathlib import Path
from collections import defaultdict

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))


def load_events():
    events = []
    with open(BASE / "data" / "events.csv") as f:
        for row in csv.DictReader(f):
            events.append({"name": row["name"], "year_ad": int(row["year_ad"])})
    return sorted(events, key=lambda e: e["year_ad"])


def to_am(year_ad, creation_bc=4004):
    return creation_bc + year_ad


def analyze_frequency(events, bucket_size=100):
    """Count events per bucket and calculate acceleration."""
    # Determine range
    min_yr = min(e["year_ad"] for e in events)
    max_yr = max(e["year_ad"] for e in events)

    # Build buckets using AM years for a clean start
    buckets = defaultdict(list)
    for ev in events:
        am = to_am(ev["year_ad"])
        bucket_start = (am // bucket_size) * bucket_size
        buckets[bucket_start].append(ev["name"])

    # Build output rows
    rows = []
    all_bucket_starts = sorted(buckets.keys())

    # Include empty buckets
    if all_bucket_starts:
        full_range = range(all_bucket_starts[0], all_bucket_starts[-1] + bucket_size, bucket_size)
    else:
        full_range = []

    prev_count = 0
    for am_start in full_range:
        am_end = am_start + bucket_size - 1
        ad_start = am_start - 4004
        ad_end = am_end - 4004
        names = buckets.get(am_start, [])
        count = len(names)

        # Acceleration: change from previous bucket
        accel = count - prev_count

        date_start = f"{abs(ad_start)} BC" if ad_start <= 0 else f"{ad_start} AD"
        date_end = f"{abs(ad_end)} BC" if ad_end <= 0 else f"{ad_end} AD"

        rows.append({
            "am_start": am_start,
            "am_end": am_end,
            "date_range": f"{date_start} → {date_end}",
            "event_count": count,
            "events_per_year": round(count / bucket_size, 4),
            "acceleration": accel,
            "events": " | ".join(names) if names else "",
        })
        prev_count = count

    # Write CSV
    outfile = BASE / "output" / "frequency.csv"
    if rows:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    # Summary
    total_events = len(events)
    total_span = max_yr - min_yr
    print(f"Frequency Analysis — {total_events} events across {total_span} years")
    print(f"Bucket size: {bucket_size} years")
    print(f"Output: {outfile}")

    # Compression analysis
    print(f"\n{'AM Range':>15}  {'Date Range':>25}  {'Count':>5}  {'Rate':>8}  {'Accel':>6}")
    print("-" * 70)
    for r in rows:
        if r["event_count"] > 0:
            bar = "█" * r["event_count"]
            print(f"  AM {r['am_start']:>4}-{r['am_end']:>4}  {r['date_range']:>25}  "
                  f"{r['event_count']:>5}  {r['events_per_year']:>8.4f}  "
                  f"{r['acceleration']:>+5d}  {bar}")

    # Identify eras
    print("\nCompression pattern:")
    first_half = [r for r in rows if r["am_start"] < 3000]
    second_half = [r for r in rows if r["am_start"] >= 3000]
    first_count = sum(r["event_count"] for r in first_half)
    second_count = sum(r["event_count"] for r in second_half)
    print(f"  AM 0-2999 (Creation→David):    {first_count} events")
    print(f"  AM 3000-6030 (David→present):  {second_count} events")
    if first_count > 0:
        print(f"  Ratio: {second_count / first_count:.1f}× more events in second half")

    # Most dense bucket
    densest = max(rows, key=lambda r: r["event_count"])
    print(f"\n  Densest bucket: AM {densest['am_start']}-{densest['am_end']} "
          f"({densest['date_range']}) — {densest['event_count']} events")


def main():
    parser = argparse.ArgumentParser(description="Frequency acceleration analysis")
    parser.add_argument("--bucket", "-b", type=int, default=100,
                        help="Bucket size in years (default: 100)")
    args = parser.parse_args()

    events = load_events()
    print(f"Loaded {len(events)} events")
    analyze_frequency(events, bucket_size=args.bucket)


if __name__ == "__main__":
    main()
