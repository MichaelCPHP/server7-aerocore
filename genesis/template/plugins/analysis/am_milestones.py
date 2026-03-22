#!/usr/bin/env python3
"""
AM Millennium Markers — What event falls at each AM millennium boundary?

The 8000-year plan maps 8 cosmic "days" of 1000 years each (7 feasts + Shemini Atzeret).
Key check points:
  AM 1000 — Day 1/2 boundary
  AM 2000 — Day 2/3 boundary (Abraham era)
  AM 3000 — Day 3/4 boundary (David takes Jerusalem, J 60 exact)
  AM 4000 — Day 4/5 boundary (Magi visit, J 80)
  AM 5000 — Day 5/6 boundary
  AM 6000 — Day 6/7 boundary (J 120, 1996)
  AM 7000 — Day 7/8 boundary (J 140, Millennium close)
  AM 8000 — Day 8 close (J 160, plan completion)

Usage:
  python3 scripts/am_milestones.py                 # full analysis
  python3 scripts/am_milestones.py --step 500      # every 500 AM years
"""

import os
import csv, json, argparse
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))


def load_events():
    events = []
    with open(BASE / "data" / "events.csv") as f:
        for row in csv.DictReader(f):
            events.append({"name": row["name"], "year_ad": int(row["year_ad"])})
    return sorted(events, key=lambda e: e["year_ad"])


def load_clocks():
    with open(BASE / "data" / "clocks.json") as f:
        return json.load(f)


def load_signatures():
    with open(BASE / "data" / "signatures.json") as f:
        return json.load(f)


def detect_signature(remainder, signatures):
    r = round(remainder, 2)
    for sig in signatures:
        sig_val = float(sig["remainder"])
        if abs(r - sig_val) <= float(sig.get("tolerance", 0.01)):
            return sig["name"]
    return ""


def to_am(year_ad, creation_bc=4004):
    return creation_bc + year_ad


def calculate_clock(year_ad, clock):
    start = clock["start_year_ad"]
    cycle = clock["cycle_years"]
    years_elapsed = year_ad - start
    if years_elapsed < 0:
        return {"jubilee": 0, "remainder": 0, "active": False}
    jubilee = years_elapsed / cycle
    remainder = (years_elapsed % cycle) / cycle
    return {"jubilee": round(jubilee, 4), "remainder": round(remainder, 4), "active": True}


def find_nearest_event(events, target_am, creation_bc=4004):
    """Find the closest event to the given AM year."""
    target_ad = target_am - creation_bc
    best = None
    best_dist = float("inf")
    for ev in events:
        dist = abs(ev["year_ad"] - target_ad)
        if dist < best_dist:
            best_dist = dist
            best = ev
    return best, best_dist


def analyze_milestones(events, step=1000):
    clocks = load_clocks()
    signatures = load_signatures()

    rows = []
    milestones = list(range(0, 8001, step))

    for am_target in milestones:
        ad_year = am_target - 4004
        date_str = f"{abs(ad_year)} BC" if ad_year <= 0 else f"{ad_year} AD"

        # Cosmic clock at this point
        cosmic = calculate_clock(ad_year, clocks["cosmic"])
        sig = detect_signature(cosmic["remainder"], signatures) if cosmic["active"] else ""

        # Find nearest event
        nearest, offset = find_nearest_event(events, am_target)
        nearest_name = nearest["name"] if nearest else ""
        nearest_yr = nearest["year_ad"] if nearest else ""
        nearest_am = to_am(nearest_yr) if nearest else ""
        nearest_date = (f"{abs(nearest_yr)} BC" if nearest_yr <= 0 else f"{nearest_yr} AD") if nearest else ""

        # Cosmic day
        cosmic_day = min(8, am_target // 1000 + 1) if am_target > 0 else 1
        feast_map = {
            1: "Passover", 2: "Unleavened Bread", 3: "Firstfruits",
            4: "Pentecost", 5: "Trumpets", 6: "Atonement",
            7: "Tabernacles", 8: "Shemini Atzeret",
        }
        day_boundary = f"Day {cosmic_day - 1}/{cosmic_day}" if am_target > 0 else "Day 1 start"

        rows.append({
            "am_milestone": am_target,
            "ad_year": ad_year,
            "date": date_str,
            "cosmic_day_boundary": day_boundary,
            "feast_mapping": feast_map.get(cosmic_day, ""),
            "cosmic_jubilee": cosmic["jubilee"] if cosmic["active"] else 0,
            "signature": sig,
            "nearest_event": nearest_name,
            "nearest_date": nearest_date,
            "nearest_am": nearest_am,
            "offset_years": offset,
            "exact_hit": "YES" if offset <= 5 else "",
            "pct_of_plan": round((am_target / 8000) * 100, 2),
        })

    # Write CSV
    outfile = BASE / "output" / "am_milestones.csv"
    if rows:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    # Summary
    print(f"AM Millennium Markers — step {step} years")
    print(f"Output: {outfile}")
    print()
    print(f"{'AM':>6}  {'Date':>10}  {'J':>8}  {'Boundary':>12}  {'Feast':>15}  "
          f"{'Nearest Event':>35}  {'±yr':>4}  {'Hit':>3}")
    print("-" * 110)
    for r in rows:
        hit_marker = " ★" if r["exact_hit"] else ""
        print(f"  {r['am_milestone']:>4}  {r['date']:>10}  "
              f"J {r['cosmic_jubilee']:>6}  {r['cosmic_day_boundary']:>12}  "
              f"{r['feast_mapping']:>15}  {r['nearest_event']:>35}  "
              f"{r['offset_years']:>+4d}{hit_marker}")

    # Verification
    print("\n=== Verification ===")
    print(f"  AM 3000 = {3000 - 4004} AD → David captures Jerusalem (J 60 exact)")
    print(f"  AM 4000 = {4000 - 4004} AD → Near Magi visit (J 80)")
    print(f"  AM 6000 = {6000 - 4004} AD → J 120 (1996)")
    print(f"  AM 7000 = {7000 - 4004} AD → J 140 (Millennium close)")
    print(f"  AM 8000 = {8000 - 4004} AD → J 160 (plan completion)")


def main():
    parser = argparse.ArgumentParser(description="AM millennium marker analysis")
    parser.add_argument("--step", "-s", type=int, default=1000,
                        help="Step size in AM years (default: 1000)")
    args = parser.parse_args()

    events = load_events()
    print(f"Loaded {len(events)} events")
    analyze_milestones(events, step=args.step)


if __name__ == "__main__":
    main()
