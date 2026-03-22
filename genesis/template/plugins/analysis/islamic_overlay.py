#!/usr/bin/env python3
"""
Islamic Events in the Jubilee System — Overlay Islamic history onto the cosmic grid.

Filters events related to Islam and shows their Jubilee positions, remainders,
and which signatures fire. Compares Islamic vs biblical event signature profiles.

Usage:
  python3 scripts/islamic_overlay.py               # full analysis
  python3 scripts/islamic_overlay.py --compare      # include signature comparison
"""

import os
import csv, json, argparse
from pathlib import Path
from collections import defaultdict

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

# Keywords to identify Islamic-related events
ISLAMIC_KEYWORDS = [
    "muhammad", "hijra", "mecca", "islam", "muslim", "mosque",
    "dome of the rock", "jerusalem capture", "caliph", "omar",
    "tours", "crusade", "vienna", "ottoman", "siege",
    "taliban", "isis", "caliphate", "al-aqsa", "intifada",
    "october 7", "oct 7", "iranian", "iran",
    "arab spring", "abraham accords",
    "soviet-afghan", "jihadism",
]


def load_database():
    rows = []
    with open(BASE / "output" / "database.csv") as f:
        for row in csv.DictReader(f):
            row["cosmic_remainder"] = float(row["cosmic_remainder"])
            row["cosmic_jubilee"] = float(row["cosmic_jubilee"])
            row["year_ad"] = int(row["year_ad"])
            row["am_year"] = int(row["am_year"])
            rows.append(row)
    return rows


def load_signatures():
    with open(BASE / "data" / "signatures.json") as f:
        return json.load(f)


def is_islamic_event(event):
    """Check if an event is Islam-related by name, notes, or known keywords."""
    text = f"{event.get('name', '')} {event.get('notes', '')}".lower()
    return any(kw in text for kw in ISLAMIC_KEYWORDS)


def analyze_islamic(events, compare=False):
    signatures = load_signatures()

    islamic = [e for e in events if is_islamic_event(e)]
    biblical = [e for e in events if not is_islamic_event(e)]

    # Build output rows for Islamic events
    rows = []
    for ev in islamic:
        rows.append({
            "name": ev["name"],
            "date": ev["date"],
            "year_ad": ev["year_ad"],
            "am_year": ev["am_year"],
            "cosmic_jubilee": ev["cosmic_jubilee"],
            "cosmic_remainder": f"{ev['cosmic_remainder']:.4f}",
            "signature": ev.get("signature", ""),
            "slot": ev.get("slot", ""),
            "feast_season": ev.get("feast_season", ""),
            "notes": ev.get("notes", ""),
        })

    # Write CSV
    outfile = BASE / "output" / "islamic_overlay.csv"
    if rows:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    # Summary
    print(f"Islamic Overlay Analysis — {len(islamic)} Islamic events / {len(events)} total")
    print(f"Output: {outfile}")
    print()

    # List events
    print("Islamic events on the Jubilee grid:")
    print(f"  {'Date':>10}  {'J':>8}  {'R':>6}  {'Sig':>20}  Event")
    print("-" * 80)
    for r in rows:
        sig = r["signature"] if r["signature"] else "—"
        print(f"  {r['date']:>10}  J {r['cosmic_jubilee']:>6}  "
              f"{r['cosmic_remainder']:>6}  {sig:>20}  {r['name']}")

    # Signature distribution for Islamic events
    print("\nSignature distribution (Islamic events):")
    islamic_sigs = defaultdict(int)
    for ev in islamic:
        sig = ev.get("signature", "")
        if sig:
            islamic_sigs[sig] += 1
    for sig, count in sorted(islamic_sigs.items(), key=lambda x: -x[1]):
        print(f"  {sig:>20}: {count}")

    unfired = [ev for ev in islamic if not ev.get("signature", "")]
    print(f"  {'(no signature)':>20}: {len(unfired)}")

    if compare:
        # Compare signature profiles
        print("\n=== Signature Comparison: Islamic vs Biblical ===")
        biblical_sigs = defaultdict(int)
        for ev in biblical:
            sig = ev.get("signature", "")
            if sig:
                biblical_sigs[sig] += 1

        all_sigs = sorted(set(list(islamic_sigs.keys()) + list(biblical_sigs.keys())))
        print(f"\n  {'Signature':>20}  {'Islamic':>8}  {'Biblical':>8}  {'Dominant':>10}")
        print("  " + "-" * 55)
        for sig in all_sigs:
            ic = islamic_sigs.get(sig, 0)
            bc = biblical_sigs.get(sig, 0)
            dominant = "ISLAMIC" if ic > bc else ("BIBLICAL" if bc > ic else "TIED")
            print(f"  {sig:>20}  {ic:>8}  {bc:>8}  {dominant:>10}")

        # Islamic-unique signatures
        islamic_only = [s for s in islamic_sigs if s not in biblical_sigs]
        biblical_only = [s for s in biblical_sigs if s not in islamic_sigs]
        if islamic_only:
            print(f"\n  Signatures unique to Islamic events: {', '.join(islamic_only)}")
        if biblical_only:
            print(f"  Signatures unique to Biblical events: {', '.join(biblical_only)}")

    # Remainder clustering
    print("\nRemainder values for Islamic events:")
    remainders = sorted(set(float(r["cosmic_remainder"]) for r in rows))
    for rem in remainders:
        matching = [r["name"] for r in rows if float(r["cosmic_remainder"]) == rem]
        print(f"  R {rem:.4f}: {', '.join(matching)}")


def main():
    parser = argparse.ArgumentParser(description="Islamic events in the Jubilee system")
    parser.add_argument("--compare", "-c", action="store_true",
                        help="Include signature comparison with biblical events")
    args = parser.parse_args()

    events = load_database()
    print(f"Loaded {len(events)} events from database")
    analyze_islamic(events, compare=args.compare)


if __name__ == "__main__":
    main()
