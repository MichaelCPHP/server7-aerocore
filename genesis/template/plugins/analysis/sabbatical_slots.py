#!/usr/bin/env python3
"""
Sabbatical Slot Analysis — Map every event onto the 7-year Shemitah wheel.

Each AM year occupies a slot 0-6 in the sabbatical cycle:
  Slot 0 = Sabbath year (empires fall)
  Slot 6 = Eve of Sabbath (historically heaviest)

Usage:
  python3 scripts/sabbatical_slots.py              # full analysis
  python3 scripts/sabbatical_slots.py --slot 6     # show only slot-6 events
  python3 scripts/sabbatical_slots.py --slot 0     # show only Sabbath-year events
"""

import os
import csv, argparse
from pathlib import Path
from collections import defaultdict

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

SLOT_LABELS = {
    0: "Sabbath year (empire falls)",
    1: "Year 1 — new beginning",
    2: "Year 2",
    3: "Year 3 — mid-cycle",
    4: "Year 4",
    5: "Year 5",
    6: "Eve of Sabbath (heaviest)",
}


def load_events():
    events = []
    with open(BASE / "data" / "events.csv") as f:
        for row in csv.DictReader(f):
            events.append({"name": row["name"], "year_ad": int(row["year_ad"])})
    return sorted(events, key=lambda e: e["year_ad"])


def to_am(year_ad, creation_bc=4004):
    return creation_bc + year_ad


def analyze_slots(events, filter_slot=None):
    """Assign each event to its sabbatical slot and produce statistics."""
    slots = defaultdict(list)
    rows = []

    for ev in events:
        yr = ev["year_ad"]
        am = to_am(yr)
        slot = am % 7

        if filter_slot is not None and slot != filter_slot:
            continue

        date_str = f"{abs(yr)} BC" if yr <= 0 else f"{yr} AD"
        entry = {
            "name": ev["name"],
            "date": date_str,
            "year_ad": yr,
            "am_year": am,
            "slot": slot,
            "slot_label": SLOT_LABELS.get(slot, ""),
        }
        rows.append(entry)
        slots[slot].append(ev["name"])

    # Write per-event output
    outfile = BASE / "output" / "sabbatical_slots.csv"
    if rows:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    # Summary
    print(f"Sabbatical Slot Analysis — {len(rows)} events")
    print(f"Output: {outfile}")
    print()

    # Slot distribution table
    total = len(rows)
    print(f"{'Slot':>4}  {'Count':>5}  {'Pct':>5}  Label")
    print("-" * 60)
    for s in range(7):
        count = len(slots[s])
        pct = f"{count / total * 100:.1f}%" if total else "0%"
        marker = " <<<" if count == max(len(v) for v in slots.values()) else ""
        print(f"   {s}  {count:>5}  {pct:>5}  {SLOT_LABELS[s]}{marker}")

    # List events per slot
    print()
    for s in range(7):
        if slots[s]:
            print(f"Slot {s} — {SLOT_LABELS[s]}:")
            for name in slots[s]:
                print(f"  • {name}")
            print()


def main():
    parser = argparse.ArgumentParser(description="Sabbatical slot analysis (7-year wheel)")
    parser.add_argument("--slot", "-s", type=int, choices=range(7),
                        help="Filter to a specific slot (0-6)")
    args = parser.parse_args()

    events = load_events()
    print(f"Loaded {len(events)} events")
    analyze_slots(events, filter_slot=args.slot)


if __name__ == "__main__":
    main()
