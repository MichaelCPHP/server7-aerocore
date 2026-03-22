#!/usr/bin/env python3
"""
Epoch Boundary Precision — Measures how precisely epoch transitions align
with Jubilee boundaries and detects "tail" periods.

Based on the 4-epoch structure (Conscience, Law, Spirit, Completion),
each transitioning at J40, J80, J120, J160. Measures:
- Exact alignment vs. drift from ideal boundary
- Tail duration (gap between last major event and epoch close)
- Transition grammar (what signature patterns surround boundaries)
- Symmetry between epoch durations

Usage:
  python3 epoch_precision.py
"""

import os
import csv
import json
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))


def load_database():
    p = BASE / "output" / "database.csv"
    if not p.exists():
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def load_epochs():
    p = BASE / "data" / "epoch_structure.csv"
    if not p.exists():
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def main():
    print("  Epoch Boundary Precision — transition alignment analysis...")

    events = load_database()
    epochs = load_epochs()
    if not events or not epochs:
        print("    ERROR: database.csv or epoch_structure.csv not found")
        return

    # Build year index
    year_events = {}
    for row in events:
        y = int(row["year_ad"])
        year_events.setdefault(y, []).append(row)

    # Ideal boundary Jubilees
    boundaries = {
        "J0": {"jubilee": 0, "am": 0, "ad": -4004, "label": "Creation"},
        "J40": {"jubilee": 40, "am": 2000, "ad": -2004, "label": "Epoch 1→2 (Conscience→Law)"},
        "J80": {"jubilee": 80, "am": 4000, "ad": -4, "label": "Epoch 2→3 (Law→Spirit)"},
        "J120": {"jubilee": 120, "am": 6000, "ad": 1996, "label": "Epoch 3→4 (Spirit→Completion)"},
        "J160": {"jubilee": 160, "am": 8000, "ad": 3996, "label": "Epoch 4 close (Plan complete)"},
    }

    results = []

    for bname, bdata in boundaries.items():
        target_ad = bdata["ad"]
        target_am = bdata["am"]

        # Find nearest events to boundary
        nearest = []
        for row in events:
            y = int(row["year_ad"])
            gap = abs(y - target_ad)
            if gap <= 50:  # Within 50 years of boundary
                nearest.append({
                    "name": row["name"],
                    "year_ad": y,
                    "gap": y - target_ad,
                    "signature": row.get("signature", ""),
                    "cosmic_remainder": float(row.get("cosmic_remainder", 0)),
                })

        nearest.sort(key=lambda n: abs(n["gap"]))

        # Closest event
        closest = nearest[0] if nearest else None
        closest_gap = closest["gap"] if closest else None
        closest_name = closest["name"] if closest else ""

        # Events within 10 years of boundary (tight window)
        tight = [n for n in nearest if abs(n["gap"]) <= 10]

        # Tail analysis: last major event before boundary
        before_events = [n for n in nearest if n["gap"] < 0]
        after_events = [n for n in nearest if n["gap"] > 0]
        last_before = before_events[-1] if before_events else None
        first_after = after_events[0] if after_events else None

        tail_duration = abs(last_before["gap"]) if last_before else None

        # Signature at boundary
        boundary_signatures = [n["signature"] for n in tight if n["signature"]]

        results.append({
            "boundary": bname,
            "label": bdata["label"],
            "target_ad": target_ad,
            "target_am": target_am,
            "closest_event": closest_name,
            "closest_gap_years": closest_gap,
            "events_within_10yr": len(tight),
            "events_within_50yr": len(nearest),
            "tight_window_events": " | ".join(f"{n['name']}({n['gap']:+d})" for n in tight),
            "tail_duration": tail_duration if tail_duration else "",
            "last_event_before": last_before["name"] if last_before else "",
            "first_event_after": first_after["name"] if first_after else "",
            "boundary_signatures": " | ".join(boundary_signatures) if boundary_signatures else "",
        })

    # Epoch duration symmetry
    epoch_results = []
    for ep in epochs:
        dur = int(ep.get("duration_years", 0))
        am_start = int(ep.get("am_start", 0))
        am_end = int(ep.get("am_end", 0))
        ad_start = int(ep.get("ad_start", 0))
        ad_end = int(ep.get("ad_end", 0))

        # Count events in this epoch
        epoch_events = [e for e in events if ad_start <= int(e["year_ad"]) <= ad_end]

        # Signatures in this epoch
        sig_counts = {}
        for e in epoch_events:
            sig = e.get("signature", "")
            if sig:
                sig_counts[sig] = sig_counts.get(sig, 0) + 1
        top_sigs = sorted(sig_counts.items(), key=lambda x: -x[1])[:5]

        epoch_results.append({
            "epoch": ep.get("epoch_name", ""),
            "epoch_id": ep.get("epoch_id", ""),
            "am_range": f"{am_start}-{am_end}",
            "ad_range": f"{ad_start} to {ad_end}",
            "duration": dur,
            "event_count": len(epoch_events),
            "density_per_100yr": round(len(epoch_events) / (dur / 100), 2) if dur > 0 else 0,
            "top_signatures": " | ".join(f"{s}:{c}" for s, c in top_sigs),
            "deviation_from_2000": dur - 2000,
        })

    # Write boundary results
    outfile = BASE / "output" / "epoch_precision.csv"
    if results:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    # Write epoch summary
    epoch_file = BASE / "output" / "epoch_summary.csv"
    if epoch_results:
        with open(epoch_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=epoch_results[0].keys())
            writer.writeheader()
            writer.writerows(epoch_results)

    print(f"        -> {outfile.name}: {len(results)} boundaries analyzed")
    print(f"        -> {epoch_file.name}: {len(epoch_results)} epochs profiled")

    print()
    print("  EPOCH BOUNDARY ALIGNMENT:")
    print(f"    {'Boundary':<8} {'Target':>8} {'Closest Event':<35} {'Gap':>5} {'Tight':>6}")
    print("    " + "-" * 70)
    for r in results:
        print(f"    {r['boundary']:<8} {r['target_ad']:>8} {r['closest_event'][:35]:<35} "
              f"{r['closest_gap_years'] if r['closest_gap_years'] is not None else 'N/A':>5} {r['events_within_10yr']:>6}")

    print()
    print("  EPOCH DURATION SYMMETRY:")
    for ep in epoch_results:
        dev = ep['deviation_from_2000']
        sym = "EXACT" if dev == 0 else f"{dev:+d}yr"
        print(f"    {ep['epoch'][:30]:<30} {ep['duration']:>5}yr  {sym:<8}  "
              f"{ep['event_count']:>3} events  {ep['density_per_100yr']:>5.1f}/100yr")


if __name__ == "__main__":
    main()
