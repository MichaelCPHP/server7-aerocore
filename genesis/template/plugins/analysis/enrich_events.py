#!/usr/bin/env python3
"""
Event Enrichment — Feeds analysis results back into the dataset.

Reads analysis outputs (boundary scores, convergence index, multi-clock
analysis, threshold detection) and writes enrichment columns back to the
database.csv. This closes the feedback loop: data -> analysis -> enrichment.

IMPORTANT: This does NOT modify events.csv (source of truth). It enriches
output/database.csv with computed properties from downstream analysis.

Usage:
  python3 enrich_events.py
"""

import os
import csv
from pathlib import Path

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))


def load_csv_lookup(filename, key_col="name"):
    """Load a CSV into a dict keyed by key_col."""
    p = BASE / "output" / filename
    if not p.exists():
        return {}
    lookup = {}
    with open(p) as f:
        for row in csv.DictReader(f):
            lookup[row.get(key_col, "")] = row
    return lookup


def main():
    print("  Event Enrichment — feeding analysis back into database...")

    db_path = BASE / "output" / "database.csv"
    if not db_path.exists():
        print("    ERROR: database.csv not found")
        return

    # Load database
    with open(db_path) as f:
        reader = csv.DictReader(f)
        original_fields = list(reader.fieldnames)
        events = list(reader)

    # Load enrichment sources
    boundary = load_csv_lookup("boundary_scores.csv")
    convergence = load_csv_lookup("convergence_index.csv")
    multi_clock = load_csv_lookup("multi_clock_analysis.csv")
    threshold = load_csv_lookup("threshold_analysis.csv")
    sig_context = load_csv_lookup("signature_context.csv", key_col="signature")
    patriarch = load_csv_lookup("patriarch_lifecycle.csv", key_col="figure")
    lifecycle = {}
    lc_path = BASE / "output" / "signature_lifecycle.csv"
    if lc_path.exists():
        with open(lc_path) as f:
            for row in csv.DictReader(f):
                lifecycle[row.get("signature", "")] = row

    # Define enrichment columns
    enrich_cols = [
        "e_convergence_index",
        "e_boundary_score",
        "e_boundary_hits_002",
        "e_clock_alignment",
        "e_has_conflict",
        "e_jubilee_clocks",
        "e_threshold_clocks",
        "e_multi_threshold",
        "e_cascade_count",
        "e_sig_dormancy_ratio",
        "e_sig_total_firings",
        "e_sig_reactivation",
        "e_sig_homogeneity",
        "e_sig_mixed_valence",
    ]

    # Build figure-event map for patriarch enrichment
    FIGURES = [
        "Adam", "Seth", "Enoch", "Noah", "Abraham", "Isaac", "Jacob", "Joseph",
        "Moses", "Joshua", "Samuel", "David", "Solomon", "Elijah", "Elisha",
        "Isaiah", "Jeremiah", "Daniel", "Ezra", "Nehemiah",
        "Jesus", "Paul", "John",
    ]

    def match_figure(event_name):
        name_lower = event_name.lower()
        aliases = {
            "jesus": ["christ", "crucifixion", "resurrection", "baptism", "transfiguration",
                       "sermon on the mount", "last supper", "ascension", "temptation"],
            "moses": ["exodus", "burning bush", "red sea", "sinai", "tabernacle built"],
            "abraham": ["abram"],
            "jacob": ["israel wrestles"],
            "paul": ["saul converted", "damascus road", "shipwreck"],
        }
        for fig in FIGURES:
            if fig.lower() in name_lower:
                return fig
            for alias in aliases.get(fig.lower(), []):
                if alias in name_lower:
                    return fig
        return None

    # Enrich each event
    for row in events:
        name = row["name"]
        sig = row.get("signature", "").strip()

        # From convergence_index
        ci = convergence.get(name, {})
        row["e_convergence_index"] = ci.get("convergence_index", "")
        row["e_clock_alignment"] = ci.get("clock_alignment_count", "")

        # From boundary_scores
        bd = boundary.get(name, {})
        row["e_boundary_score"] = bd.get("composite_score", "")
        row["e_boundary_hits_002"] = bd.get("boundary_count_002", "")

        # From multi_clock_analysis
        mc = multi_clock.get(name, {})
        row["e_has_conflict"] = mc.get("has_conflict", "")
        row["e_jubilee_clocks"] = mc.get("jubilee_clocks", "")
        row["e_threshold_clocks"] = mc.get("threshold_clocks", "")

        # From threshold_analysis
        th = threshold.get(name, {})
        row["e_multi_threshold"] = th.get("multi_clock_threshold", "")
        row["e_cascade_count"] = th.get("cascade_count", "")

        # From signature_lifecycle
        lc = lifecycle.get(sig, {})
        row["e_sig_dormancy_ratio"] = lc.get("dormancy_ratio", "")
        row["e_sig_total_firings"] = lc.get("total_firings", "")
        row["e_sig_reactivation"] = lc.get("recent_reactivation", "")

        # From signature_context
        sc = sig_context.get(sig, {})
        row["e_sig_homogeneity"] = sc.get("homogeneity", "")
        row["e_sig_mixed_valence"] = sc.get("has_mixed_valence", "")

    # Write enriched database (separate file — does not overwrite database.csv)
    all_fields = original_fields + [c for c in enrich_cols if c not in original_fields]

    outfile = BASE / "output" / "database_enriched.csv"
    with open(outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(events)

    enriched_count = sum(1 for row in events if row.get("e_convergence_index"))
    print(f"        -> database_enriched.csv: {len(events)} events, {len(enrich_cols)} enrichment columns added")
    print(f"        -> {enriched_count} events with convergence index")

    # Summary stats
    if enriched_count:
        cis = [float(row["e_convergence_index"]) for row in events if row.get("e_convergence_index")]
        if cis:
            print(f"        -> CI range: {min(cis):.1f} - {max(cis):.1f}, mean: {sum(cis)/len(cis):.1f}")


if __name__ == "__main__":
    main()
