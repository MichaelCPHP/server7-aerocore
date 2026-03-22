#!/usr/bin/env python3
"""
Astronomy Overlay — Maps astronomical cycles against the Jubilee grid.

Tests whether planetary periods, eclipses, conjunctions, and blood moon
tetrads correlate with biblical prophetic cycles and remainder signatures.

Psalm 19:1 — "The heavens declare the glory of God"
Isaiah 40:12 — "Who has measured the heavens by the span of his hand?"

Usage:
  python3 astronomy.py                # full analysis
  python3 astronomy.py --verbose      # show detailed output
"""

import os
import csv
import json
import math
import argparse
from pathlib import Path
from collections import defaultdict

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

# ── Astronomical constants ──────────────────────────────────────────────

BIBLICAL_CYCLES = {
    "Shemitah":    7,
    "Sabbatical":  49,
    "Jubilee":     50,
    "Daniel":      490,
    "Cosmic Day":  1000,
    "Full Plan":   6000,
}

# ── Loaders ─────────────────────────────────────────────────────────────

def load_database():
    """Load the main event database."""
    events = []
    db_path = BASE / "output" / "database.csv"
    if not db_path.exists():
        print(f"  ERROR: {db_path} not found — run engine first")
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
                "tags": row.get("tags", ""),
            })
    return events


def load_clocks():
    with open(BASE / "data" / "clocks.json") as f:
        return json.load(f)


def load_conjunctions():
    rows = []
    p = BASE / "data" / "astro_conjunctions.csv"
    if not p.exists():
        return rows
    with open(p) as f:
        for row in csv.DictReader(f):
            try:
                rows.append({
                    "year_ad": int(row["year_ad"]),
                    "type": row.get("type", ""),
                    "constellation": row.get("constellation", ""),
                    "notes": row.get("notes", ""),
                })
            except (ValueError, KeyError):
                continue
    return rows


def load_blood_moons():
    rows = []
    p = BASE / "data" / "astro_blood_moons.csv"
    if not p.exists():
        return rows
    with open(p) as f:
        for row in csv.DictReader(f):
            try:
                rows.append({
                    "tetrad_id": int(row["tetrad_id"]),
                    "year_start": int(row["year_start"]),
                    "year_end": int(row["year_end"]),
                    "historical_event": row.get("historical_event", ""),
                    "significance": row.get("significance", ""),
                })
            except (ValueError, KeyError):
                continue
    return rows


def load_eclipses():
    rows = []
    p = BASE / "data" / "astro_eclipses.csv"
    if not p.exists():
        return rows
    with open(p) as f:
        for row in csv.DictReader(f):
            try:
                rows.append({
                    "year_ad": int(row["year_ad"]),
                    "type": row.get("type", ""),
                    "path": row.get("path", ""),
                    "historical_event": row.get("historical_event", ""),
                    "biblical_relevance": row.get("biblical_relevance", ""),
                })
            except (ValueError, KeyError):
                continue
    return rows


def load_astro_cycles():
    rows = []
    p = BASE / "data" / "astro_cycles.csv"
    if not p.exists():
        return rows
    with open(p) as f:
        for row in csv.DictReader(f):
            try:
                rows.append({
                    "cycle_name": row["cycle_name"],
                    "period_years": float(row["period_years"]),
                    "category": row.get("category", ""),
                    "description": row.get("description", ""),
                })
            except (ValueError, KeyError):
                continue
    return rows


# ── Analysis functions ──────────────────────────────────────────────────

def compute_jubilee_remainder(year_ad, clock_start, cycle_years):
    """Compute the Jubilee-normalized remainder for any year."""
    elapsed = year_ad - clock_start
    if cycle_years <= 0:
        return 0.0
    return (elapsed % cycle_years) / cycle_years


def resonance_score(ratio):
    """How close a ratio is to the nearest integer. 1.0 = perfect."""
    return 1.0 - abs(ratio - round(ratio))


def analyze_cycle_harmonics(astro_cycles):
    """Test each astronomical cycle against each biblical cycle for integer resonance."""
    results = []
    for ac in astro_cycles:
        if ac["period_years"] < 0.1 or ac["period_years"] > 30000:
            continue
        for bc_name, bc_years in BIBLICAL_CYCLES.items():
            ratio = bc_years / ac["period_years"]
            if ratio < 0.5:
                continue  # Skip trivially small ratios
            res = resonance_score(ratio)
            nearest_int = round(ratio)
            drift_years = abs(ratio - nearest_int) * ac["period_years"]
            drift_pct = (drift_years / bc_years) * 100 if bc_years else 0

            results.append({
                "astro_cycle": ac["cycle_name"],
                "astro_period_yr": round(ac["period_years"], 4),
                "biblical_cycle": bc_name,
                "biblical_period_yr": bc_years,
                "ratio": round(ratio, 4),
                "nearest_integer": nearest_int,
                "resonance": round(res, 4),
                "drift_years": round(drift_years, 2),
                "drift_pct": round(drift_pct, 2),
                "category": ac["category"],
                "interpretation": "",
            })

    # Sort by resonance descending
    results.sort(key=lambda r: -r["resonance"])

    # Add interpretations for top results
    for r in results:
        if r["resonance"] >= 0.99:
            r["interpretation"] = f"EXACT: {r['nearest_integer']} {r['astro_cycle']} = 1 {r['biblical_cycle']}"
        elif r["resonance"] >= 0.95:
            r["interpretation"] = f"STRONG: ~{r['nearest_integer']} {r['astro_cycle']} per {r['biblical_cycle']} (drift {r['drift_years']}yr)"
        elif r["resonance"] >= 0.90:
            r["interpretation"] = f"NOTABLE: ~{r['nearest_integer']} {r['astro_cycle']} per {r['biblical_cycle']}"

    return results


def analyze_conjunction_signatures(conjunctions, clocks):
    """Map each Jupiter-Saturn conjunction to its Jubilee remainder and signature position."""
    results = []
    cosmic_start = clocks["cosmic"]["start_year_ad"]
    cosmic_cycle = clocks["cosmic"]["cycle_years"]

    for conj in conjunctions:
        year = conj["year_ad"]
        remainder = compute_jubilee_remainder(year, cosmic_start, cosmic_cycle)
        # Compute what AM year this is
        am_year = year - cosmic_start

        results.append({
            "year_ad": year,
            "am_year": am_year,
            "constellation": conj["constellation"],
            "cosmic_remainder": round(remainder, 4),
            "cosmic_jubilee": round(am_year / cosmic_cycle, 2),
            "year_in_cycle": am_year % cosmic_cycle,
            "notes": conj["notes"],
        })

    return results


def analyze_blood_moon_positions(blood_moons, clocks):
    """Map each blood moon tetrad to its position in all prophetic clocks."""
    results = []
    for bm in blood_moons:
        year = bm["year_start"]
        row = {
            "tetrad_id": bm["tetrad_id"],
            "year_ad": year,
            "historical_event": bm["historical_event"],
        }
        for clock_name, clock in clocks.items():
            start = clock["start_year_ad"]
            cycle = clock["cycle_years"]
            rem = compute_jubilee_remainder(year, start, cycle)
            row[f"{clock_name}_remainder"] = round(rem, 4)
            row[f"{clock_name}_year_in_cycle"] = (year - start) % cycle

        results.append(row)
    return results


def analyze_eclipse_proximity(eclipses, events, clocks):
    """For each eclipse, find the nearest biblical event and compute its clock position."""
    results = []
    event_years = [(e["year_ad"], e["name"], e["signature"]) for e in events]

    cosmic_start = clocks["cosmic"]["start_year_ad"]
    cosmic_cycle = clocks["cosmic"]["cycle_years"]

    for ecl in eclipses:
        year = ecl["year_ad"]

        # Find nearest event
        nearest_event = ""
        nearest_sig = ""
        nearest_gap = 99999
        for ey, en, es in event_years:
            gap = abs(year - ey)
            if gap < nearest_gap:
                nearest_gap = gap
                nearest_event = en
                nearest_sig = es

        remainder = compute_jubilee_remainder(year, cosmic_start, cosmic_cycle)

        results.append({
            "year_ad": year,
            "eclipse_type": ecl["type"],
            "path": ecl["path"],
            "biblical_relevance": ecl["biblical_relevance"],
            "cosmic_remainder": round(remainder, 4),
            "year_in_jubilee": (year - cosmic_start) % cosmic_cycle,
            "nearest_event": nearest_event,
            "nearest_event_gap_yr": nearest_gap,
            "nearest_signature": nearest_sig,
        })

    return results


def analyze_signature_clustering(conjunctions, events, clocks):
    """Test whether conjunctions cluster at specific remainder/signature positions
    vs being uniformly distributed."""
    cosmic_start = clocks["cosmic"]["start_year_ad"]
    cosmic_cycle = clocks["cosmic"]["cycle_years"]

    # Build signature map from events
    sig_map = defaultdict(list)
    for e in events:
        if e["signature"]:
            sig_map[e["signature"]].append(e["cosmic_remainder"])

    # Compute remainder for each conjunction
    conj_remainders = []
    for c in conjunctions:
        r = compute_jubilee_remainder(c["year_ad"], cosmic_start, cosmic_cycle)
        conj_remainders.append(r)

    # Bin remainders into 50 slots (one per year of Jubilee cycle)
    bins = [0] * 50
    for r in conj_remainders:
        slot = int(r * 50) % 50
        bins[slot] += 1

    total = len(conj_remainders)
    expected = total / 50

    # Chi-squared test against uniform distribution
    chi_sq = sum((b - expected) ** 2 / expected for b in bins) if expected > 0 else 0

    # Degrees of freedom = 49
    # Chi-squared critical value at p=0.05, df=49 is ~66.34
    uniform = chi_sq < 66.34

    results = {
        "total_conjunctions": total,
        "chi_squared": round(chi_sq, 2),
        "critical_value_p05": 66.34,
        "distribution": "UNIFORM" if uniform else "NON-UNIFORM (clustered)",
        "bins": bins,
        "expected_per_bin": round(expected, 2),
    }

    # Find the hottest slots
    hot_slots = sorted(range(50), key=lambda i: -bins[i])[:10]
    results["hot_slots"] = [(s, bins[s]) for s in hot_slots]

    return results


def analyze_event_conjunction_alignment(events, conjunctions):
    """For each biblical event, find the nearest conjunction and compute the gap."""
    results = []
    conj_years = [c["year_ad"] for c in conjunctions]

    for e in events:
        year = e["year_ad"]
        # Binary search for nearest conjunction
        nearest_year = min(conj_years, key=lambda cy: abs(cy - year))
        gap = year - nearest_year

        results.append({
            "event": e["name"],
            "event_year": year,
            "nearest_conjunction_year": nearest_year,
            "gap_years": gap,
            "abs_gap": abs(gap),
            "signature": e["signature"],
        })

    # Sort by absolute gap
    results.sort(key=lambda r: r["abs_gap"])
    return results


def analyze_multiplier_hits(astro_cycles):
    """Test 7× and 12× multipliers of astronomical periods against biblical numbers."""
    sacred_targets = {
        7: "Shemitah", 12: "Tribes/Apostles", 40: "Testing",
        49: "Sabbatical", 50: "Jubilee", 70: "Lifespan/Exile",
        120: "Striving (Gen 6:3)", 400: "Sojourn", 430: "Egypt sojourn",
        490: "70 weeks", 1000: "Cosmic Day", 6000: "Full Plan",
    }

    results = []
    multipliers = [7, 12, 40, 49, 50, 70]

    for ac in astro_cycles:
        period = ac["period_years"]
        if period < 1 or period > 1000:
            continue
        for mult in multipliers:
            product = period * mult
            for target, label in sacred_targets.items():
                pct_off = abs(product - target) / target * 100
                if pct_off <= 5.0:  # Within 5%
                    results.append({
                        "astro_cycle": ac["cycle_name"],
                        "period_yr": round(period, 4),
                        "multiplier": mult,
                        "product_yr": round(product, 2),
                        "biblical_target": target,
                        "target_name": label,
                        "pct_off": round(pct_off, 2),
                        "interpretation": f"{mult} × {ac['cycle_name']} ({period:.2f} yr) = {product:.1f} ≈ {target} ({label})",
                    })

    results.sort(key=lambda r: r["pct_off"])
    return results


def build_summary(harmonics, clustering, multiplier_hits, blood_moon_positions,
                  eclipse_proximity, event_alignment):
    """Build a summary table of key findings."""
    rows = []

    # Top harmonic resonances
    strong = [h for h in harmonics if h["resonance"] >= 0.95 and h["nearest_integer"] >= 2]
    for h in strong[:15]:
        rows.append({
            "finding_type": "HARMONIC",
            "description": h["interpretation"],
            "score": h["resonance"],
            "detail": f"{h['astro_cycle']} ({h['astro_period_yr']} yr) × {h['nearest_integer']} = {h['biblical_cycle']} ({h['biblical_period_yr']} yr) — drift {h['drift_years']} yr ({h['drift_pct']}%)",
        })

    # Conjunction clustering
    rows.append({
        "finding_type": "CLUSTERING",
        "description": f"Conjunction distribution: {clustering['distribution']}",
        "score": round(clustering["chi_squared"], 2),
        "detail": f"Chi-sq={clustering['chi_squared']:.2f} (critical={clustering['critical_value_p05']}) — {clustering['total_conjunctions']} conjunctions in 50 Jubilee slots",
    })

    # Best multiplier hits
    for m in multiplier_hits[:10]:
        rows.append({
            "finding_type": "MULTIPLIER",
            "description": m["interpretation"],
            "score": round(1 - m["pct_off"] / 100, 4),
            "detail": f"{m['pct_off']}% off target",
        })

    # Blood moon insights
    for bm in blood_moon_positions:
        cosmic_r = bm.get("cosmic_remainder", 0)
        rows.append({
            "finding_type": "BLOOD MOON",
            "description": f"Tetrad {bm['tetrad_id']} ({bm['year_ad']}) — {bm['historical_event']}",
            "score": cosmic_r,
            "detail": f"Cosmic R={cosmic_r} | Israel R={bm.get('israel_remainder', 'N/A')} | Church R={bm.get('church_remainder', 'N/A')}",
        })

    # Events landing ON conjunctions (gap=0 or ±1)
    exact_hits = [ea for ea in event_alignment if ea["abs_gap"] <= 2]
    for ea in exact_hits[:20]:
        rows.append({
            "finding_type": "EVENT-CONJUNCTION",
            "description": f"{ea['event']} ({ea['event_year']}) — on conjunction year ({ea['nearest_conjunction_year']})",
            "score": 1.0 - (ea["abs_gap"] / 20),
            "detail": f"Gap: {ea['gap_years']} yr | Signature: {ea['signature']}",
        })

    return rows


# ── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Astronomy overlay analysis")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("  Astronomy Overlay — loading data...")

    events = load_database()
    clocks = load_clocks()
    conjunctions = load_conjunctions()
    blood_moons = load_blood_moons()
    eclipses = load_eclipses()
    astro_cycles = load_astro_cycles()

    print(f"  Events: {len(events)} | Conjunctions: {len(conjunctions)} | "
          f"Blood Moons: {len(blood_moons)} | Eclipses: {len(eclipses)} | "
          f"Astro Cycles: {len(astro_cycles)}")

    # ── 1. Cycle harmonics ──
    print("  [1/6] Cycle harmonics...")
    harmonics = analyze_cycle_harmonics(astro_cycles)
    out = BASE / "output" / "astro_harmonics.csv"
    if harmonics:
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=harmonics[0].keys())
            writer.writeheader()
            writer.writerows(harmonics)
        print(f"        → {out.name}: {len(harmonics)} rows")

    # ── 2. Conjunction signatures ──
    print("  [2/6] Conjunction signatures...")
    conj_sigs = analyze_conjunction_signatures(conjunctions, clocks)
    out = BASE / "output" / "astro_conjunction_grid.csv"
    if conj_sigs:
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=conj_sigs[0].keys())
            writer.writeheader()
            writer.writerows(conj_sigs)
        print(f"        → {out.name}: {len(conj_sigs)} rows")

    # ── 3. Blood moon positions ──
    print("  [3/6] Blood moon positions...")
    bm_positions = analyze_blood_moon_positions(blood_moons, clocks)
    out = BASE / "output" / "astro_blood_moon_grid.csv"
    if bm_positions:
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=bm_positions[0].keys())
            writer.writeheader()
            writer.writerows(bm_positions)
        print(f"        → {out.name}: {len(bm_positions)} rows")

    # ── 4. Eclipse proximity ──
    print("  [4/6] Eclipse proximity to events...")
    ecl_prox = analyze_eclipse_proximity(eclipses, events, clocks)
    out = BASE / "output" / "astro_eclipse_grid.csv"
    if ecl_prox:
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ecl_prox[0].keys())
            writer.writeheader()
            writer.writerows(ecl_prox)
        print(f"        → {out.name}: {len(ecl_prox)} rows")

    # ── 5. Signature clustering ──
    print("  [5/6] Conjunction clustering test...")
    clustering = analyze_signature_clustering(conjunctions, events, clocks)

    # ── 6. Multiplier hits ──
    print("  [6/6] Multiplier search (7×, 12×, 40×, 49×, 50×, 70×)...")
    mult_hits = analyze_multiplier_hits(astro_cycles)
    out = BASE / "output" / "astro_multiplier_hits.csv"
    if mult_hits:
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=mult_hits[0].keys())
            writer.writeheader()
            writer.writerows(mult_hits)
        print(f"        → {out.name}: {len(mult_hits)} rows")

    # ── Event-conjunction alignment ──
    event_alignment = analyze_event_conjunction_alignment(events, conjunctions)
    out = BASE / "output" / "astro_event_conjunctions.csv"
    if event_alignment:
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=event_alignment[0].keys())
            writer.writeheader()
            writer.writerows(event_alignment)
        print(f"        → {out.name}: {len(event_alignment)} rows")

    # ── Summary ──
    summary = build_summary(harmonics, clustering, mult_hits, bm_positions,
                            ecl_prox, event_alignment)
    out = BASE / "output" / "astro_summary.csv"
    if summary:
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=summary[0].keys())
            writer.writeheader()
            writer.writerows(summary)
        print(f"        → {out.name}: {len(summary)} rows")

    # ── Print key findings ──
    print("\n  ═══ KEY FINDINGS ═══\n")

    # Harmonics
    strong_harmonics = [h for h in harmonics if h["resonance"] >= 0.95 and h["nearest_integer"] >= 2]
    if strong_harmonics:
        print("  PLANETARY HARMONICS (resonance ≥ 0.95):")
        for h in strong_harmonics[:12]:
            marker = "★" if h["resonance"] >= 0.99 else "●"
            print(f"    {marker} {h['interpretation']}")
        print()

    # Clustering
    print(f"  CONJUNCTION DISTRIBUTION: {clustering['distribution']}")
    print(f"    Chi-squared: {clustering['chi_squared']:.2f} (critical @ p=0.05: {clustering['critical_value_p05']})")
    top_slots = clustering["hot_slots"][:5]
    print(f"    Hottest Jubilee slots: {', '.join(f'yr {s}={n}' for s,n in top_slots)}")
    print()

    # Blood moons
    print("  BLOOD MOON TETRAD POSITIONS:")
    for bm in bm_positions:
        cr = bm.get("cosmic_remainder", 0)
        print(f"    Tetrad {bm['tetrad_id']} ({bm['year_ad']}): Cosmic R={cr:.4f} | "
              f"{bm['historical_event']}")
    print()

    # Multiplier hits
    if mult_hits:
        print("  SACRED MULTIPLIER HITS (within 5%):")
        for m in mult_hits[:8]:
            print(f"    {m['interpretation']} — {m['pct_off']}% off")
        print()

    # Events on conjunctions
    exact = [ea for ea in event_alignment if ea["abs_gap"] <= 2]
    if exact:
        print(f"  EVENTS ON CONJUNCTION YEARS (gap ≤ 2 yr): {len(exact)}")
        for ea in exact[:15]:
            print(f"    {ea['event']} ({ea['event_year']}) ↔ conjunction {ea['nearest_conjunction_year']} "
                  f"[gap {ea['gap_years']:+d}yr] — {ea['signature']}")
        print()

    print(f"  Output: 7 CSV files in {BASE / 'output'}/astro_*.csv")


if __name__ == "__main__":
    main()
