#!/usr/bin/env python3
"""
Remainder Complement Pairs — Find events whose cosmic remainders sum to ~1.0.

Two events with complementary remainders (e.g., R=0.32 + R=0.68 = 1.00) sit
at mirror positions on the Jubilee wheel. These are structural echoes.

Usage:
  python3 scripts/complement_pairs.py                    # default tolerance 0.02
  python3 scripts/complement_pairs.py --tolerance 0.01   # tighter match
  python3 scripts/complement_pairs.py --tolerance 0.05   # wider match
"""

import os
import csv, json, argparse
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))


def load_database():
    rows = []
    with open(BASE / "output" / "database.csv") as f:
        for row in csv.DictReader(f):
            row["cosmic_remainder"] = float(row["cosmic_remainder"])
            row["cosmic_jubilee"] = float(row["cosmic_jubilee"])
            row["year_ad"] = int(row["year_ad"])
            rows.append(row)
    return rows


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


def find_complement_pairs(events, tolerance=0.02):
    """Find all pairs where R_a + R_b ≈ 1.0000."""
    signatures = load_signatures()
    pairs = []

    for i, a in enumerate(events):
        for j, b in enumerate(events):
            if j <= i:
                continue
            ra = a["cosmic_remainder"]
            rb = b["cosmic_remainder"]
            remainder_sum = ra + rb
            delta = abs(remainder_sum - 1.0)

            if delta <= tolerance:
                sig_a = detect_signature(ra, signatures)
                sig_b = detect_signature(rb, signatures)
                pairs.append({
                    "event_a": a["name"],
                    "date_a": a["date"],
                    "remainder_a": f"{ra:.4f}",
                    "signature_a": sig_a,
                    "event_b": b["name"],
                    "date_b": b["date"],
                    "remainder_b": f"{rb:.4f}",
                    "signature_b": sig_b,
                    "sum": f"{remainder_sum:.4f}",
                    "delta_from_1": f"{delta:.4f}",
                })

    # Sort by tightest match
    pairs.sort(key=lambda p: float(p["delta_from_1"]))

    # Write CSV
    outfile = BASE / "output" / "complement_pairs.csv"
    if pairs:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=pairs[0].keys())
            writer.writeheader()
            writer.writerows(pairs)

    # Summary
    print(f"Complement Pair Analysis (tolerance ±{tolerance})")
    print(f"Found {len(pairs)} mirror pairs")
    print(f"Output: {outfile}")
    print()

    # Show top pairs
    print("Top complement pairs (closest to R_a + R_b = 1.0000):")
    for p in pairs[:20]:
        print(f"  {p['remainder_a']} + {p['remainder_b']} = {p['sum']}  "
              f"Δ{p['delta_from_1']}  "
              f"{p['event_a']} ↔ {p['event_b']}")

    # Signature complement analysis
    if pairs:
        print("\nSignature mirror pairs:")
        seen = set()
        for p in pairs:
            if p["signature_a"] and p["signature_b"]:
                key = tuple(sorted([p["signature_a"], p["signature_b"]]))
                if key not in seen:
                    seen.add(key)
                    print(f"  {p['signature_a']} ↔ {p['signature_b']}")


def main():
    parser = argparse.ArgumentParser(description="Find remainder complement pairs (R_a + R_b ≈ 1.0)")
    parser.add_argument("--tolerance", "-t", type=float, default=0.02,
                        help="Tolerance for sum ≈ 1.0 (default: 0.02)")
    args = parser.parse_args()

    events = load_database()
    print(f"Loaded {len(events)} events from database")
    find_complement_pairs(events, tolerance=args.tolerance)


if __name__ == "__main__":
    main()
