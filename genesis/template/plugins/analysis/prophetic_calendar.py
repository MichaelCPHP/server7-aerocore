#!/usr/bin/env python3
"""
Prophetic Calendar Analysis — Tests the 360-day prophetic year hypothesis
and clock scale relationships across the Jubilee system.

Key insight: The 360-day "prophetic year" is the geometric mean of the lunar
(354.37 day) and solar (365.25 day) years. This creates measurable conversion
factors between calendar systems that may be encoded in the 49/50 Jubilee duality.

Daniel's day-counts: 1260, 1290, 1335, 2300, 2520
Revelation: 42 months + 42 months = 7 prophetic years

Usage:
  python3 prophetic_calendar.py
"""

import os
import csv
import json
import math
from pathlib import Path
from collections import defaultdict

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

# ── Constants ───────────────────────────────────────────────────────────

SOLAR_YEAR = 365.25          # days
LUNAR_YEAR = 354.37          # days (12 synodic months)
PROPHETIC_YEAR = 360.0       # days
SYNODIC_MONTH = 29.53059     # days (lunar month)

PROPHETIC_SOLAR_RATIO = PROPHETIC_YEAR / SOLAR_YEAR  # 0.98563...

DANIEL_DAYS = {
    "1260_days": 1260,   # Dan 12:7, Rev 11:3, 12:6 — half tribulation
    "1290_days": 1290,   # Dan 12:11 — abomination + 30 days
    "1335_days": 1335,   # Dan 12:12 — blessed who waits
    "2300_evenings_mornings": 2300,  # Dan 8:14 — sanctuary cleansed
    "2520_days": 2520,   # 7 × 360 — full tribulation (42+42 months)
}

ANCHOR_EVENTS = [
    # (name, year_ad, description)
    ("Crucifixion", 30, "Death of Jesus"),
    ("Fall of Jerusalem", -586, "Babylonian destruction of Temple"),
    ("Artaxerxes decree", -457, "Daniel clock start"),
    ("Cyrus decree", -538, "End of Babylonian exile"),
    ("Nehemiah rebuilds", -444, "Walls of Jerusalem restored"),
    ("Maccabean cleansing", -165, "Temple rededicated (Hanukkah)"),
    ("Temple destroyed 70 AD", 70, "Roman destruction"),
    ("Israel reborn", 1948, "Modern state established"),
    ("Six-Day War", 1967, "Jerusalem reunified"),
    ("Balfour Declaration", 1917, "British mandate for Jewish homeland"),
]


def load_database():
    events = []
    db_path = BASE / "output" / "database.csv"
    if not db_path.exists():
        return events
    with open(db_path) as f:
        for row in csv.DictReader(f):
            try:
                year = int(row["year_ad"])
            except (ValueError, KeyError):
                continue
            events.append({
                "name": row.get("name", ""),
                "year_ad": year,
                "am_year": int(row.get("am_year", 0) or 0),
                "signature": row.get("signature", ""),
                "cosmic_remainder": float(row.get("cosmic_remainder", 0) or 0),
            })
    return events


def load_clocks():
    with open(BASE / "data" / "clocks.json") as f:
        return json.load(f)


# ── Analysis 1: Prophetic Year as Geometric Mean ────────────────────────

def analyze_prophetic_year():
    """Prove that 360 ≈ geometric mean of lunar and solar years."""
    geo_mean = math.sqrt(LUNAR_YEAR * SOLAR_YEAR)
    arith_mean = (LUNAR_YEAR + SOLAR_YEAR) / 2
    harm_mean = 2 / (1/LUNAR_YEAR + 1/SOLAR_YEAR)

    return {
        "solar_year_days": SOLAR_YEAR,
        "lunar_year_days": LUNAR_YEAR,
        "prophetic_year_days": PROPHETIC_YEAR,
        "geometric_mean": round(geo_mean, 4),
        "geo_mean_error_days": round(abs(geo_mean - 360), 4),
        "arithmetic_mean": round(arith_mean, 4),
        "arith_mean_error_days": round(abs(arith_mean - 360), 4),
        "harmonic_mean": round(harm_mean, 4),
        "harm_mean_error_days": round(abs(harm_mean - 360), 4),
        "prophetic_solar_ratio": round(PROPHETIC_SOLAR_RATIO, 6),
    }


# ── Analysis 2: The 49/50 Duality ──────────────────────────────────────

def analyze_jubilee_duality():
    """Test whether 50 prophetic years ≈ 49 solar years."""
    rows = []
    test_values = [
        ("3.5 prophetic years (half-tribulation)", 3.5),
        ("7 prophetic years (full tribulation)", 7),
        ("49 prophetic years (Sabbatical)", 49),
        ("50 prophetic years (Jubilee)", 50),
        ("70 prophetic years (Lifespan/Exile)", 70),
        ("490 prophetic years (Daniel)", 490),
        ("1000 prophetic years (Cosmic Day)", 1000),
    ]

    for label, prophetic_years in test_values:
        solar_equiv = prophetic_years * PROPHETIC_SOLAR_RATIO
        nearest_int = round(solar_equiv)
        drift_days = abs(solar_equiv - nearest_int) * SOLAR_YEAR

        rows.append({
            "label": label,
            "prophetic_years": prophetic_years,
            "solar_equivalent": round(solar_equiv, 4),
            "nearest_integer_yr": nearest_int,
            "drift_solar_days": round(drift_days, 2),
            "drift_synodic_months": round(drift_days / SYNODIC_MONTH, 2),
            "note": "",
        })

    # Add key insight
    for r in rows:
        if r["prophetic_years"] == 50:
            r["note"] = f"50 prophetic = {r['solar_equivalent']:.2f} solar ≈ 49 solar — ENCODES 49/50 DUALITY"
        elif r["prophetic_years"] == 490:
            r["note"] = f"490 prophetic = {r['solar_equivalent']:.2f} solar ≈ 483 solar — Daniel's 69 weeks"

    return rows


# ── Analysis 3: Daniel Day-Count Projections ────────────────────────────

def analyze_daniel_projections(events):
    """From key anchor events, project Daniel's day-counts and find what they land on."""
    results = []
    event_map = {e["year_ad"]: e for e in events}
    event_years = sorted(event_map.keys())

    for anchor_name, anchor_year, anchor_desc in ANCHOR_EVENTS:
        for day_label, days in DANIEL_DAYS.items():
            # Convert days to solar years
            solar_years = days / SOLAR_YEAR
            target_year = anchor_year + solar_years
            target_year_int = round(target_year)

            # Find nearest event
            nearest_event = ""
            nearest_sig = ""
            nearest_gap = 99999
            for ey in event_years:
                gap = abs(ey - target_year_int)
                if gap < nearest_gap:
                    nearest_gap = gap
                    nearest_event = event_map[ey]["name"]
                    nearest_sig = event_map[ey]["signature"]

            # Also project backwards
            target_back = anchor_year - solar_years
            target_back_int = round(target_back)
            nearest_back = ""
            nearest_back_sig = ""
            nearest_back_gap = 99999
            for ey in event_years:
                gap = abs(ey - target_back_int)
                if gap < nearest_back_gap:
                    nearest_back_gap = gap
                    nearest_back = event_map[ey]["name"]
                    nearest_back_sig = event_map[ey]["signature"]

            results.append({
                "anchor": anchor_name,
                "anchor_year": anchor_year,
                "day_count": days,
                "day_label": day_label,
                "direction": "forward",
                "target_year": round(target_year, 1),
                "nearest_event": nearest_event,
                "event_gap_yr": nearest_gap,
                "event_signature": nearest_sig,
            })

            results.append({
                "anchor": anchor_name,
                "anchor_year": anchor_year,
                "day_count": days,
                "day_label": day_label,
                "direction": "backward",
                "target_year": round(target_back, 1),
                "nearest_event": nearest_back,
                "event_gap_yr": nearest_back_gap,
                "event_signature": nearest_back_sig,
            })

    # Sort by how close a projection hits an event
    results.sort(key=lambda r: r["event_gap_yr"])
    return results


# ── Analysis 4: Clock Beat Frequencies ──────────────────────────────────

def analyze_clock_beats(clocks):
    """Compute when each pair of clocks resynchronizes."""
    results = []
    clock_list = list(clocks.items())

    for i, (name_a, clock_a) in enumerate(clock_list):
        for name_b, clock_b in clock_list[i+1:]:
            ca = clock_a["cycle_years"]
            cb = clock_b["cycle_years"]

            lcm = (ca * cb) // math.gcd(ca, cb)

            # How many cycles of each clock in the LCM
            cycles_a = lcm // ca
            cycles_b = lcm // cb

            # Epoch gap
            epoch_gap = abs(clock_a["start_year_ad"] - clock_b["start_year_ad"])

            # How many LCMs fit in the epoch gap
            lcm_in_gap = epoch_gap / lcm if lcm > 0 else 0

            results.append({
                "clock_a": name_a,
                "cycle_a": ca,
                "clock_b": name_b,
                "cycle_b": cb,
                "beat_lcm_years": lcm,
                "cycles_a_per_beat": cycles_a,
                "cycles_b_per_beat": cycles_b,
                "epoch_gap_years": epoch_gap,
                "lcm_fits_in_gap": round(lcm_in_gap, 4),
                "daniel_cycles_per_beat": round(lcm / 490, 4),
                "note": "",
            })

    # Add key insight notes
    for r in results:
        if r["beat_lcm_years"] == 2450:
            r["note"] = "2450 = 5 × Daniel 490 — five Daniel cycles to resynchronize"
        if r["cycles_a_per_beat"] == 10 or r["cycles_b_per_beat"] == 10:
            if 490 in (r["cycle_a"], r["cycle_b"]):
                r["note"] = "Exact: 1 Daniel = 10 Sabbatical cycles"

    return results


# ── Analysis 5: The 2520 and Sacred Numbers ─────────────────────────────

def analyze_2520():
    """Analyze the mathematical properties of 2520."""
    # LCM(1..10)
    lcm = 1
    for i in range(1, 11):
        lcm = (lcm * i) // math.gcd(lcm, i)

    # Factorization
    n = 2520
    factors = {}
    temp = n
    for p in [2, 3, 5, 7, 11, 13]:
        while temp % p == 0:
            factors[p] = factors.get(p, 0) + 1
            temp //= p

    # Divisibility tests
    divisors = [1,2,3,4,5,6,7,8,9,10,12,14,15,18,20,21,24,28,30,35,36,40,42,45,49,50,60,63,70,72,84,90,105,120,126,140,168,180,210,252,280,315,360,420,504,630,840,1260,2520]
    actual_divisors = [d for d in range(1, 2521) if 2520 % d == 0]

    return {
        "value": 2520,
        "lcm_1_to_10": lcm,
        "is_lcm_1_to_10": lcm == 2520,
        "factorization": " × ".join(f"{p}^{e}" for p, e in sorted(factors.items())),
        "total_divisors": len(actual_divisors),
        "prophetic_years": 2520 / 360,
        "solar_years": round(2520 / SOLAR_YEAR, 4),
        "lunar_years": round(2520 / LUNAR_YEAR, 4),
        "divisible_by_7": 2520 % 7 == 0,
        "divisible_by_12": 2520 % 12 == 0,
        "divisible_by_42": 2520 % 42 == 0,
        "divisible_by_49": 2520 % 49 == 0,
        "divisible_by_50": 2520 % 50 == 0,
        "div_by_360": 2520 / 360,
        "biblical_numbers_as_divisors": [d for d in [7, 12, 30, 40, 42, 49, 50, 70, 120, 360, 490] if 2520 % d == 0],
    }


# ── Analysis 6: 42-Month Window Scanner ─────────────────────────────────

def scan_42_month_windows(events):
    """Find 3.5-year windows with high event density or signature clustering."""
    half_trib_solar = 1260 / SOLAR_YEAR  # ~3.449 solar years

    # Sort events by year
    sorted_events = sorted(events, key=lambda e: e["year_ad"])

    windows = []
    for i, start_event in enumerate(sorted_events):
        start = start_event["year_ad"]
        window_events = []
        for j in range(i, len(sorted_events)):
            end_event = sorted_events[j]
            if end_event["year_ad"] - start > half_trib_solar + 0.5:
                break
            window_events.append(end_event)

        if len(window_events) >= 3:
            sigs = [e["signature"] for e in window_events if e["signature"]]
            unique_sigs = set(sigs)
            windows.append({
                "start_event": start_event["name"],
                "start_year": start,
                "end_year": window_events[-1]["year_ad"],
                "span_years": window_events[-1]["year_ad"] - start,
                "event_count": len(window_events),
                "signatures": " | ".join(sigs),
                "unique_signatures": len(unique_sigs),
                "events": ", ".join(e["name"] for e in window_events),
            })

    # Sort by event density
    windows.sort(key=lambda w: -w["event_count"])
    return windows[:100]  # Top 100 densest windows


# ── Analysis 7: Clock Scale Ratios ──────────────────────────────────────

def analyze_clock_scales(clocks, events):
    """Compare how events map across different clock scales."""
    results = []

    # Key test years
    test_years = [-586, -457, -444, -165, 30, 33, 70, 1948, 1967, 2020]

    for year in test_years:
        row = {"year_ad": year}
        # Find event name if exists
        matching = [e for e in events if e["year_ad"] == year]
        row["event"] = matching[0]["name"] if matching else ""

        for clock_name, clock in clocks.items():
            start = clock["start_year_ad"]
            cycle = clock["cycle_years"]
            elapsed = year - start
            cycles_exact = elapsed / cycle
            remainder = (elapsed % cycle) / cycle
            year_in_cycle = elapsed % cycle

            row[f"{clock_name}_cycles"] = round(cycles_exact, 4)
            row[f"{clock_name}_remainder"] = round(remainder, 4)
            row[f"{clock_name}_year_in_cycle"] = year_in_cycle

        # Also compute prophetic-year equivalents
        elapsed_from_creation = year - (-4004)
        row["am_year"] = elapsed_from_creation
        row["prophetic_jubilees"] = round(elapsed_from_creation / (50 * PROPHETIC_SOLAR_RATIO), 4)
        row["solar_jubilees"] = round(elapsed_from_creation / 50, 4)
        row["jubilee_drift"] = round(row["prophetic_jubilees"] - row["solar_jubilees"], 4)

        results.append(row)

    return results


# ── Main ────────────────────────────────────────────────────────────────

def main():
    print("  Prophetic Calendar Analysis — loading data...")

    events = load_database()
    clocks = load_clocks()

    print(f"  Events: {len(events)}")

    outdir = BASE / "output"

    # ── 1. Prophetic Year = Geometric Mean ──
    print("  [1/7] Prophetic year analysis...")
    py_analysis = analyze_prophetic_year()
    rows = [py_analysis]
    out = outdir / "prophetic_year.csv"
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"        → {out.name}")

    # ── 2. Jubilee Duality ──
    print("  [2/7] Jubilee 49/50 duality...")
    duality = analyze_jubilee_duality()
    out = outdir / "prophetic_duality.csv"
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=duality[0].keys())
        writer.writeheader()
        writer.writerows(duality)
    print(f"        → {out.name}: {len(duality)} rows")

    # ── 3. Daniel Projections ──
    print("  [3/7] Daniel day-count projections...")
    projections = analyze_daniel_projections(events)
    out = outdir / "prophetic_projections.csv"
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=projections[0].keys())
        writer.writeheader()
        writer.writerows(projections)
    print(f"        → {out.name}: {len(projections)} rows")

    # ── 4. Clock Beats ──
    print("  [4/7] Clock beat frequencies...")
    beats = analyze_clock_beats(clocks)
    out = outdir / "prophetic_beats.csv"
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=beats[0].keys())
        writer.writeheader()
        writer.writerows(beats)
    print(f"        → {out.name}: {len(beats)} rows")

    # ── 5. The Number 2520 ──
    print("  [5/7] 2520 analysis...")
    num_2520 = analyze_2520()
    rows = [num_2520]
    out = outdir / "prophetic_2520.csv"
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"        → {out.name}")

    # ── 6. 42-Month Windows ──
    print("  [6/7] 42-month window scan...")
    windows = scan_42_month_windows(events)
    out = outdir / "prophetic_windows.csv"
    if windows:
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=windows[0].keys())
            writer.writeheader()
            writer.writerows(windows)
        print(f"        → {out.name}: {len(windows)} windows")

    # ── 7. Clock Scale Ratios ──
    print("  [7/7] Clock scale comparison...")
    scales = analyze_clock_scales(clocks, events)
    out = outdir / "prophetic_scales.csv"
    if scales:
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=scales[0].keys())
            writer.writeheader()
            writer.writerows(scales)
        print(f"        → {out.name}: {len(scales)} rows")

    # ── Print Key Findings ──
    print("\n  ═══ KEY FINDINGS ═══\n")

    print("  1. THE PROPHETIC YEAR")
    print(f"     360-day year = geometric mean of lunar ({LUNAR_YEAR}) and solar ({SOLAR_YEAR})")
    print(f"     Geometric mean: {py_analysis['geometric_mean']} days — error: {py_analysis['geo_mean_error_days']} days")
    print(f"     The prophetic calendar is the mathematical BRIDGE between moon and sun.")
    print()

    print("  2. THE 49/50 DUALITY")
    for d in duality:
        if d["prophetic_years"] in (50, 490):
            print(f"     {d['label']}: {d['solar_equivalent']} solar years — {d['note']}")
    print(f"     → 50 prophetic years = 49.28 solar years (between 49 and 50)")
    print(f"     → The Jubilee system's 49/50 ambiguity IS the calendar conversion factor")
    print()

    print("  3. CLOCK BEAT FREQUENCIES")
    for b in beats:
        if b["beat_lcm_years"] <= 5000:
            print(f"     {b['clock_a']}({b['cycle_a']}) × {b['clock_b']}({b['cycle_b']}): "
                  f"resync every {b['beat_lcm_years']} yr = {b['cycles_a_per_beat']} × {b['cycles_b_per_beat']} cycles"
                  f"  {b['note']}")
    print()

    print("  4. THE NUMBER 2520")
    print(f"     2520 = LCM(1 through 10) = 7 × 360 = {num_2520['factorization']}")
    print(f"     = {num_2520['solar_years']} solar years = {num_2520['lunar_years']} lunar years")
    print(f"     Divisible by biblical numbers: {num_2520['biblical_numbers_as_divisors']}")
    print()

    print("  5. DANIEL PROJECTIONS (closest hits):")
    for p in projections[:10]:
        if p["event_gap_yr"] <= 3:
            print(f"     {p['anchor']} ({p['anchor_year']}) + {p['day_count']}d ({p['direction']}) "
                  f"→ {p['target_year']} ≈ {p['nearest_event']} [{p['event_signature']}] (gap {p['event_gap_yr']}yr)")
    print()

    print("  6. DENSEST 42-MONTH WINDOWS:")
    for w in windows[:5]:
        print(f"     {w['start_year']}-{w['end_year']}: {w['event_count']} events — {w['signatures']}")
    print()

    print(f"  Output: 7 CSV files in {outdir}/prophetic_*.csv")


if __name__ == "__main__":
    main()
