#!/usr/bin/env python3
"""
Calendar Engine — 50-channel remainder grid.
10 clocks × 5 calendars = 50 independent measurement channels.

Each channel computes the Jubilee remainder for every event using a different
clock (cycle length + epoch) measured in a different calendar (day-length).

Usage:
  python3 calendar_engine.py
"""

import os
import csv
import json
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))
TROPICAL = 365.24219  # Reference: mean tropical year in days

CALENDARS = {
    "tropical":  365.24219,
    "prophetic": 360.000,
    "enochian":  364.000,
    "egyptian":  365.000,
    "lunar":     354.367,
}


def load_clocks():
    with open(BASE / "data" / "clocks.json") as f:
        return json.load(f)


def load_database():
    events = []
    with open(BASE / "output" / "database.csv") as f:
        for row in csv.DictReader(f):
            try:
                events.append({
                    "name": row["name"],
                    "year_ad": int(row["year_ad"]),
                })
            except (ValueError, KeyError):
                continue
    return events


def compute_remainder(year_ad, cycle_base, epoch, cal_days):
    """Compute remainder using a specific calendar's year-length."""
    ratio = cal_days / TROPICAL
    cycle_solar = cycle_base * ratio
    elapsed = year_ad - epoch
    if elapsed < 0 or cycle_solar <= 0:
        return None
    return (elapsed % cycle_solar) / cycle_solar


def main():
    print("  Calendar Engine — 50-channel grid...")

    clocks = load_clocks()
    events = load_database()

    # Build column list
    id_cols = ["name", "year_ad"]
    channel_cols = []
    for clock_name in clocks:
        for cal_name in CALENDARS:
            channel_cols.append(f"{clock_name}_{cal_name}_R")

    all_cols = id_cols + channel_cols

    rows = []
    for e in events:
        row = {"name": e["name"], "year_ad": e["year_ad"]}
        for clock_name, clock_def in clocks.items():
            cycle = clock_def["cycle_years"]
            epoch = clock_def["start_year_ad"]
            for cal_name, cal_days in CALENDARS.items():
                col = f"{clock_name}_{cal_name}_R"
                r = compute_remainder(e["year_ad"], cycle, epoch, cal_days)
                row[col] = round(r, 6) if r is not None else ""
        rows.append(row)

    outfile = BASE / "output" / "calendar_grid.csv"
    with open(outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_cols)
        writer.writeheader()
        writer.writerows(rows)

    print(f"        → {outfile.name}: {len(rows)} events × {len(channel_cols)} channels ({len(all_cols)} cols)")


if __name__ == "__main__":
    main()
