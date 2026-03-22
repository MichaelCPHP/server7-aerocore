#!/usr/bin/env python3
"""
Signature-Context Analyzer — Cross-tabulates signatures with category tags
to detect when mathematical patterns contain mixed theological meanings.

Inspired by the discovery that Abraham (patriarchal covenant) and Islamic
conquest events share the .666 remainder band — same number, very different
meaning. This script systematically finds all such mismatches.

Usage:
  python3 signature_context.py
"""

import os
import csv
import re
from pathlib import Path
from collections import defaultdict

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))


def extract_tags(tag_string):
    """Extract individual tags from a space-separated tag string."""
    if not tag_string:
        return []
    return [t.strip() for t in tag_string.split() if t.strip().startswith("#")]


def get_category(tags):
    """Extract primary category from tags (e.g., #cat.judgment -> judgment)."""
    cats = []
    for t in tags:
        if t.startswith("#cat."):
            cats.append(t.replace("#cat.", ""))
    return cats


def get_themes(tags):
    """Extract themes from tags."""
    themes = []
    for t in tags:
        if t.startswith("#theme."):
            themes.append(t.replace("#theme.", ""))
    return themes


def get_nations(tags):
    """Extract nations from tags."""
    nations = []
    for t in tags:
        if t.startswith("#nation."):
            nations.append(t.replace("#nation.", ""))
    return nations


def main():
    print("  Signature-Context Analyzer — detecting meaning mismatches...")

    db_path = BASE / "output" / "database.csv"
    if not db_path.exists():
        print("    ERROR: database.csv not found")
        return

    events = []
    with open(db_path) as f:
        events = list(csv.DictReader(f))

    # Group events by signature
    sig_groups = defaultdict(list)
    for row in events:
        sig = row.get("signature", "").strip()
        if not sig:
            continue
        tags = extract_tags(row.get("tags", ""))
        cats = get_category(tags)
        themes = get_themes(tags)
        nations = get_nations(tags)

        sig_groups[sig].append({
            "name": row["name"],
            "year_ad": int(row["year_ad"]),
            "categories": cats,
            "themes": themes,
            "nations": nations,
            "epoch": row.get("epoch", ""),
            "tags": tags,
        })

    results = []

    for sig_name, members in sig_groups.items():
        if len(members) < 2:
            continue

        # Collect all categories and themes across members
        all_cats = defaultdict(int)
        all_themes = defaultdict(int)
        all_nations = defaultdict(int)
        all_epochs = defaultdict(int)

        for m in members:
            for c in m["categories"]:
                all_cats[c] += 1
            for t in m["themes"]:
                all_themes[t] += 1
            for n in m["nations"]:
                all_nations[n] += 1
            all_epochs[m["epoch"]] += 1

        # Detect category spread (diversity within signature)
        unique_cats = len(all_cats)
        dominant_cat = max(all_cats, key=all_cats.get) if all_cats else ""
        dominant_cat_pct = (all_cats[dominant_cat] / len(members)) * 100 if dominant_cat else 0

        # Detect theme conflicts
        unique_themes = len(all_themes)

        # Check for judgment+covenant mixed (classic conflict)
        has_judgment = "judgment" in all_cats
        has_covenant = "covenant" in all_cats
        has_creation = "creation" in all_cats
        has_destruction = "destruction" in all_cats
        has_mixed_valence = (has_judgment and has_covenant) or (has_creation and has_destruction)

        # Epoch spread
        unique_epochs = len(all_epochs)

        # Outlier detection: member whose categories don't match dominant
        outliers = []
        for m in members:
            if dominant_cat and dominant_cat not in m["categories"] and m["categories"]:
                outliers.append(m["name"])

        # Homogeneity score: 1.0 = all same category, 0.0 = all different
        if len(members) > 0 and all_cats:
            homogeneity = all_cats[dominant_cat] / len(members)
        else:
            homogeneity = 0

        results.append({
            "signature": sig_name,
            "member_count": len(members),
            "unique_categories": unique_cats,
            "dominant_category": dominant_cat,
            "dominant_category_pct": round(dominant_cat_pct, 1),
            "homogeneity": round(homogeneity, 3),
            "has_mixed_valence": "YES" if has_mixed_valence else "",
            "unique_themes": unique_themes,
            "unique_epochs": unique_epochs,
            "category_distribution": " | ".join(f"{c}:{n}" for c, n in sorted(all_cats.items(), key=lambda x: -x[1])),
            "theme_distribution": " | ".join(f"{t}:{n}" for t, n in sorted(all_themes.items(), key=lambda x: -x[1])[:8]),
            "outlier_events": " | ".join(outliers) if outliers else "",
            "outlier_count": len(outliers),
            "members": " | ".join(f"{m['name']}({m['year_ad']})" for m in members),
        })

    # Sort by lowest homogeneity (most mixed signatures first)
    results.sort(key=lambda r: (r["homogeneity"], -r["member_count"]))

    outfile = BASE / "output" / "signature_context.csv"
    if results:
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    print(f"        -> {outfile.name}: {len(results)} signatures profiled")

    # Report mixed-valence signatures
    mixed = [r for r in results if r["has_mixed_valence"]]
    if mixed:
        print()
        print(f"  MIXED-VALENCE SIGNATURES ({len(mixed)} — contain both positive and negative events):")
        print(f"    {'Signature':<25} {'#':>4} {'Homo':>6} {'Categories'}")
        print("    " + "-" * 75)
        for r in mixed:
            print(f"    {r['signature'][:25]:<25} {r['member_count']:>4} {r['homogeneity']:>6.2f} "
                  f"{r['category_distribution'][:50]}")

    # Report low-homogeneity signatures
    low_homo = [r for r in results if r["homogeneity"] < 0.5 and r["member_count"] >= 3]
    if low_homo:
        print()
        print(f"  LOW HOMOGENEITY ({len(low_homo)} — category assignment may need review):")
        for r in low_homo:
            print(f"    {r['signature']}: {r['category_distribution']}")
            if r["outlier_events"]:
                print(f"      Outliers: {r['outlier_events']}")


if __name__ == "__main__":
    main()
