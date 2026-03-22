#!/usr/bin/env python3
"""
Daniel's 490-Year Forward Projection — Apply 490-year multiples from key anchors.

Daniel's "70 weeks" (490 years) is a master cycle. This script projects 490-year
multiples forward from anchor dates and checks what events land on those years.

Key checks:
  7 × 490 from -1406 (Canaan entry) = 2024
  3 × 490 from -1446 (Exodus) = 24 AD (near Jesus' ministry start)
  1 × 490 from -457 (decree) = 33 AD (near Crucifixion)

Usage:
  python3 scripts/daniel_490.py                   # full analysis
  python3 scripts/daniel_490.py --max-mult 10     # up to 10× multiples
"""

import os
import csv, json, argparse
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

# Anchor dates for the 490-year projection
DEFAULT_ANCHORS = [
    {"name": "Exodus", "year_ad": -1446, "description": "Israel leaves Egypt"},
    {"name": "Canaan entry", "year_ad": -1406, "description": "Israel enters Promised Land; Israel clock starts"},
    {"name": "Artaxerxes decree", "year_ad": -457, "description": "Daniel 9:25 — decree to restore Jerusalem"},
    {"name": "Crucifixion", "year_ad": 30, "description": "The Cross — center of history"},
    {"name": "Temple destroyed (Rome)", "year_ad": 70, "description": "9th of Av — Second Temple destroyed"},
    {"name": "David captures Jerusalem", "year_ad": -1004, "description": "AM 3000 — J 60 exact"},
]


def load_events():
    events = {}
    with open(BASE / "data" / "events.csv") as f:
        for row in csv.DictReader(f):
            yr = int(row["year_ad"])
            events[yr] = row["name"]
    return events


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


def project_490(anchors, max_mult=10):
    event_map = load_events()
    clocks = load_clocks()
    signatures = load_signatures()

    rows = []

    for anchor in anchors:
        for mult in range(1, max_mult + 1):
            target_year = anchor["year_ad"] + (490 * mult)
            am = to_am(target_year)
            cosmic = calculate_clock(target_year, clocks["cosmic"])

            # Check for nearby events (within 3 years)
            event_hit = ""
            for offset in range(0, 4):
                for sign in [0, 1, -1]:
                    check = target_year + (offset * sign) if sign != 0 else target_year
                    if check in event_map:
                        if offset == 0:
                            event_hit = event_map[check]
                        else:
                            event_hit = f"({event_map[check]} [{sign * offset:+d}yr])"
                        break
                if event_hit:
                    break

            date_str = f"{abs(target_year)} BC" if target_year <= 0 else f"{target_year} AD"
            anchor_date = f"{abs(anchor['year_ad'])} BC" if anchor["year_ad"] <= 0 else f"{anchor['year_ad']} AD"

            sig = detect_signature(cosmic["remainder"], signatures) if cosmic["active"] else ""

            rows.append({
                "anchor": anchor["name"],
                "anchor_date": anchor_date,
                "multiple": f"{mult}×490",
                "years_forward": 490 * mult,
                "target_year": target_year,
                "target_date": date_str,
                "am_year": am,
                "cosmic_jubilee": cosmic["jubilee"] if cosmic["active"] else "",
                "cosmic_remainder": cosmic["remainder"] if cosmic["active"] else "",
                "signature": sig,
                "event_hit": event_hit,
            })

    # Write CSV
    outfile = BASE / "output" / "daniel_490.csv"
    if rows:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    # Summary
    print(f"Daniel 490-Year Projection — {len(rows)} calculations")
    print(f"Output: {outfile}")
    print()

    # Highlight hits
    hits = [r for r in rows if r["event_hit"]]
    print(f"Event hits: {len(hits)}")
    print()
    for anchor in anchors:
        anchor_rows = [r for r in rows if r["anchor"] == anchor["name"]]
        print(f"From {anchor['name']} ({anchor['description']}):")
        for r in anchor_rows:
            hit = f"  → {r['event_hit']}" if r["event_hit"] else ""
            sig = f" [{r['signature']}]" if r["signature"] else ""
            print(f"  {r['multiple']:>6} = {r['target_date']:>8}  "
                  f"AM {r['am_year']}  J {r['cosmic_jubilee']}{sig}{hit}")
        print()

    # Call out key checks
    print("=== Key Checks ===")
    print(f"  7×490 from Canaan entry (-1406): {-1406 + 7*490} AD  (Israel clock J70 = 2024)")
    print(f"  3×490 from Exodus (-1446):       {-1446 + 3*490} AD  (near Jesus ministry)")
    print(f"  1×490 from decree (-457):        {-457 + 1*490} AD   (near Crucifixion)")
    print(f"  5×490 from David (-1004):        {-1004 + 5*490} AD  (Reformation era)")


def main():
    parser = argparse.ArgumentParser(description="Daniel's 490-year forward projection")
    parser.add_argument("--max-mult", "-m", type=int, default=10,
                        help="Maximum multiple of 490 to project (default: 10)")
    args = parser.parse_args()

    project_490(DEFAULT_ANCHORS, max_mult=args.max_mult)


if __name__ == "__main__":
    main()
