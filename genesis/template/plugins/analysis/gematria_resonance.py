#!/usr/bin/env python3
"""
Gematria-Timeline Bridge — Systematically cross-references Hebrew word values
with event coordinates across all clock positions.

Tests whether gematria values of key Hebrew words correspond to:
- AM years of events (e.g., YHWH=26, year 26 AM?)
- Cosmic jubilee positions (e.g., Yovel=48, Jubilee 48?)
- Year-in-cycle positions (e.g., Moed=120, year 120 of a cycle?)
- Gap distances between events (e.g., gap of 358 years = Mashiach?)
- Clock remainders × cycle length matching gematria values

Usage:
  python3 gematria_resonance.py
"""

import os
import csv
import json
import math
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

CLOCKS = [
    "cosmic", "israel", "church", "daniel", "moadim",
    "shemitah", "generation", "exile", "striving", "master",
]

# Core gematria values to test
GEMATRIA = [
    {"word": "YHWH", "value": 26},
    {"word": "Elohim", "value": 86},
    {"word": "Yeshua", "value": 386},
    {"word": "Mashiach", "value": 358},
    {"word": "Yovel", "value": 48},
    {"word": "Shemitah", "value": 364},
    {"word": "Moed", "value": 120},
    {"word": "Ketz", "value": 1000},
    {"word": "Chokhmah", "value": 73},
    {"word": "Echad/Ahavah", "value": 13},
    {"word": "Emet", "value": 441},
    {"word": "Brit", "value": 612},
    {"word": "Yisrael", "value": 541},
    {"word": "Adam", "value": 45},
    {"word": "Or (Light)", "value": 207},
    {"word": "Gen1:1", "value": 2701},
    {"word": "Iesous", "value": 888},
    {"word": "777", "value": 777},
    {"word": "666", "value": 666},
]


def load_database():
    p = BASE / "output" / "database.csv"
    if not p.exists():
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def load_clocks():
    with open(BASE / "data" / "clocks.json") as f:
        return json.load(f)


def digital_root(n):
    n = abs(n)
    while n >= 10:
        n = sum(int(d) for d in str(n))
    return n


def main():
    print("  Gematria-Timeline Bridge — Hebrew values vs. event coordinates...")

    events = load_database()
    clock_config = load_clocks()
    if not events:
        print("    ERROR: database.csv not found")
        return

    # Build lookup structures
    am_years = {}  # AM year -> event(s)
    ad_years = {}  # AD year -> event(s)
    for row in events:
        y = int(row["year_ad"])
        am = int(row.get("am_year", 0))
        am_years.setdefault(am, []).append(row["name"])
        ad_years.setdefault(y, []).append(row["name"])

    # Build gap set
    gaps = set()
    sorted_events = sorted(events, key=lambda e: int(e["year_ad"]))
    for i in range(1, len(sorted_events)):
        gap = abs(int(sorted_events[i]["year_ad"]) - int(sorted_events[i - 1]["year_ad"]))
        gaps.add(gap)

    results = []

    for gem in GEMATRIA:
        word = gem["word"]
        val = gem["value"]

        hits = []

        # Test 1: AM year match
        if val in am_years:
            hits.append({"type": "AM_YEAR", "match": f"AM {val}", "events": " | ".join(am_years[val][:3])})

        # Test 2: AD year match (positive only)
        if val in ad_years:
            hits.append({"type": "AD_YEAR", "match": f"AD {val}", "events": " | ".join(ad_years[val][:3])})

        # Test 3: Jubilee position match
        for row in events:
            for clock in CLOCKS:
                jub_key = f"{clock}_jubilee"
                jub_val = row.get(jub_key, "")
                if jub_val:
                    try:
                        j = float(jub_val)
                        if abs(j - val) < 0.5:  # Within half a jubilee
                            hits.append({"type": f"JUBILEE_{clock.upper()}",
                                         "match": f"J{val} on {clock}",
                                         "events": row["name"]})
                    except ValueError:
                        pass

        # Test 4: Year-in-cycle match
        for row in events:
            for clock in CLOCKS:
                yic_key = f"{clock}_year_in_cycle"
                yic_val = row.get(yic_key, "")
                if yic_val:
                    try:
                        yic = int(float(yic_val))
                        if yic == val:
                            hits.append({"type": f"YEAR_IN_CYCLE_{clock.upper()}",
                                         "match": f"Year {val} of {clock} cycle",
                                         "events": row["name"]})
                    except ValueError:
                        pass

        # Test 5: Gap match
        if val in gaps:
            hits.append({"type": "GAP", "match": f"{val}-year gap exists", "events": ""})

        # Test 6: Multiple/factor of gematria in cycle lengths
        for cname, cdata in clock_config.items():
            cycle = cdata["cycle_years"]
            if val % cycle == 0:
                hits.append({"type": "FACTOR", "match": f"{val} = {val // cycle} × {cycle} ({cname})",
                             "events": ""})
            if cycle % val == 0 and val > 1:
                hits.append({"type": "DIVISOR", "match": f"{cycle} = {cycle // val} × {val} ({cname})",
                             "events": ""})

        # Test 7: Digital root resonance
        dr = digital_root(val)

        # Deduplicate hits by type+match
        seen = set()
        unique_hits = []
        for h in hits:
            key = f"{h['type']}:{h['match']}"
            if key not in seen:
                seen.add(key)
                unique_hits.append(h)
                if len(unique_hits) >= 20:  # Cap per word
                    break

        results.append({
            "word": word,
            "value": val,
            "digital_root": dr,
            "total_resonances": len(unique_hits),
            "resonance_types": " | ".join(sorted(set(h["type"] for h in unique_hits))),
            "top_resonances": " | ".join(f"{h['type']}:{h['match']}" for h in unique_hits[:8]),
            "event_matches": " | ".join(h["events"] for h in unique_hits if h["events"])[:200],
        })

    # Sort by total resonances
    results.sort(key=lambda r: -r["total_resonances"])

    outfile = BASE / "output" / "gematria_resonance.csv"
    if results:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    print(f"        -> {outfile.name}: {len(results)} gematria values tested")

    print()
    print("  GEMATRIA-TIMELINE RESONANCE:")
    print(f"    {'Word':<20} {'Value':>6} {'DR':>3} {'Hits':>5} {'Types'}")
    print("    " + "-" * 70)
    for r in results:
        print(f"    {r['word'][:20]:<20} {r['value']:>6} {r['digital_root']:>3} "
              f"{r['total_resonances']:>5} {r['resonance_types'][:40]}")


if __name__ == "__main__":
    main()
