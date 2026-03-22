#!/usr/bin/env python3
"""Lab Pipeline Runner — runs all analysis scripts in dependency order.

Uses Python's built-in graphlib.TopologicalSorter to determine execution
order. Skips steps whose inputs haven't changed (mtime-based caching).

Usage:
    python3 pipeline.py              # run all (skip unchanged)
    python3 pipeline.py --force      # force re-run everything
    python3 pipeline.py --dry-run    # show what would run
    python3 pipeline.py --status     # show pipeline status
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from graphlib import TopologicalSorter
from pathlib import Path

# Resolve paths
SCRIPT_DIR = Path(__file__).parent
PLATFORM_DIR = SCRIPT_DIR.parent.parent
INSTANCE_DIR = Path(os.environ.get('LAB_INSTANCE', PLATFORM_DIR / 'instances' / 'jubilee'))
PLUGINS_DIR = PLATFORM_DIR / 'plugins'
CACHE_FILE = INSTANCE_DIR / 'output' / '.pipeline-cache.json'
RUNS_FILE = INSTANCE_DIR / 'output' / 'runs.jsonl'

# Pipeline steps — each step has inputs (files it reads) and outputs (files it writes)
# Dependencies are inferred: if step B reads a file that step A writes, B depends on A.
STEPS = [
    {
        "id": "engine",
        "name": "Core Engine",
        "command": ["python3", "engine.py", "all"],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["data/events.csv", "data/clocks.json", "data/signatures.json"],
        "outputs": ["output/database.csv", "output/clocks.csv", "output/gaps.csv", "output/signatures.csv"],
    },
    {
        "id": "cycles",
        "name": "Cycle Finder",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "cycle_finder.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/cycles.csv"],
    },
    {
        "id": "remainder",
        "name": "Remainder Scan",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "remainder_scan.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/remainder_clusters.csv"],
    },
    {
        "id": "convergence",
        "name": "Convergence Analysis",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "convergence.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/convergence.csv"],
    },
    {
        "id": "mirror",
        "name": "Mirror Symmetry",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "mirror_symmetry.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/mirror_symmetry.csv"],
    },
    {
        "id": "anchor",
        "name": "Anchor Dates",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "anchor_dates.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/anchor_dates.csv"],
    },
    {
        "id": "complement",
        "name": "Complement Pairs",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "complement_pairs.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/complement_pairs.csv"],
    },
    {
        "id": "frequency",
        "name": "Frequency Analysis",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "frequency.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/frequency.csv"],
    },
    {
        "id": "gematria",
        "name": "Gematria Analysis",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "gematria.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv", "data/signatures.json"],
        "outputs": ["output/gematria.csv"],
    },
    {
        "id": "islamic",
        "name": "Islamic Overlay",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "islamic_overlay.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/islamic_overlay.csv"],
    },
    {
        "id": "sabbatical",
        "name": "Sabbatical Slots",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "sabbatical_slots.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/sabbatical_slots.csv"],
    },
    {
        "id": "daniel",
        "name": "Daniel 490 Projection",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "daniel_490.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/daniel_490.csv"],
    },
    {
        "id": "milestones",
        "name": "AM Milestones",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "am_milestones.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/am_milestones.csv"],
    },
    {
        "id": "prophetic_calendar",
        "name": "Prophetic Calendar",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "prophetic_calendar.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv", "data/clocks.json"],
        "outputs": ["output/prophetic_year.csv", "output/prophetic_duality.csv",
                    "output/prophetic_projections.csv", "output/prophetic_beats.csv",
                    "output/prophetic_2520.csv", "output/prophetic_windows.csv",
                    "output/prophetic_scales.csv"],
    },
    {
        "id": "astronomy",
        "name": "Astronomy Overlay",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "astronomy.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv", "data/astro_conjunctions.csv", "data/astro_blood_moons.csv",
                   "data/astro_eclipses.csv", "data/astro_cycles.csv"],
        "outputs": ["output/astro_harmonics.csv", "output/astro_conjunction_grid.csv",
                    "output/astro_blood_moon_grid.csv", "output/astro_eclipse_grid.csv",
                    "output/astro_multiplier_hits.csv", "output/astro_event_conjunctions.csv",
                    "output/astro_summary.csv"],
    },
    {
        "id": "calendar_grid",
        "name": "Calendar Grid (50-channel)",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "calendar_engine.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv", "data/clocks.json"],
        "outputs": ["output/calendar_grid.csv"],
    },
    {
        "id": "boundary_scores",
        "name": "Boundary Scores",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "boundary_scores.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/calendar_grid.csv"],
        "outputs": ["output/boundary_scores.csv"],
    },
    {
        "id": "event_harmonics",
        "name": "Event Harmonics",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "event_harmonics.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/event_harmonics.csv"],
    },
    {
        "id": "tags",
        "name": "Tag Analysis",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "tag_analyze.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/tag_matrix.csv", "output/tag_clusters.csv", "output/tag_bridges.csv", "output/taxonomy.csv"],
    },
    {
        "id": "tag_index",
        "name": "Tag Index",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "tag_index.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/tag_index.csv", "output/tag_cooccurrence.csv"],
    },
    {
        "id": "multi_clock",
        "name": "Multi-Clock Analyzer",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "multi_clock_analyzer.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/multi_clock_analysis.csv"],
    },
    {
        "id": "threshold",
        "name": "Threshold Analysis",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "threshold_analysis.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/threshold_analysis.csv"],
    },
    {
        "id": "signature_lifecycle",
        "name": "Signature Lifecycle",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "signature_lifecycle.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/signature_lifecycle.csv"],
    },
    {
        "id": "convergence_index",
        "name": "Convergence Index",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "convergence_index.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv", "output/boundary_scores.csv", "output/complement_pairs.csv"],
        "outputs": ["output/convergence_index.csv"],
    },
    {
        "id": "frequency_stats",
        "name": "Frequency Statistics",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "frequency_stats.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/frequency_stats.csv"],
    },
    {
        "id": "epoch_precision",
        "name": "Epoch Precision",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "epoch_precision.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/epoch_precision.csv", "output/epoch_summary.csv"],
    },
    {
        "id": "signature_context",
        "name": "Signature Context",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "signature_context.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/signature_context.csv"],
    },
    {
        "id": "future_convergence",
        "name": "Future Convergence Monitor",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "future_convergence.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv", "data/clocks.json"],
        "outputs": ["output/future_convergence.csv"],
    },
    {
        "id": "patriarch_lifecycle",
        "name": "Patriarch Lifecycle",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "patriarch_lifecycle.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv"],
        "outputs": ["output/patriarch_lifecycle.csv"],
    },
    {
        "id": "gematria_resonance",
        "name": "Gematria Resonance",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "gematria_resonance.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv", "data/clocks.json"],
        "outputs": ["output/gematria_resonance.csv"],
    },
    {
        "id": "enrich",
        "name": "Event Enrichment",
        "command": ["python3", str(PLUGINS_DIR / "analysis" / "enrich_events.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database.csv", "output/boundary_scores.csv", "output/convergence_index.csv",
                   "output/multi_clock_analysis.csv", "output/threshold_analysis.csv",
                   "output/signature_lifecycle.csv", "output/signature_context.csv",
                   "output/patriarch_lifecycle.csv"],
        "outputs": ["output/database_enriched.csv"],
    },
    {
        "id": "build_db",
        "name": "Build SQLite Database",
        "command": ["python3", str(PLUGINS_DIR / "core" / "build_db.py")],
        "cwd": str(INSTANCE_DIR),
        "inputs": ["output/database_enriched.csv", "output/cycles.csv", "output/gaps.csv", "output/convergence.csv",
                   "output/remainder_clusters.csv", "output/signatures.csv", "output/gematria.csv",
                   "output/astro_summary.csv", "output/calendar_grid.csv", "output/boundary_scores.csv",
                   "output/event_harmonics.csv", "output/convergence_index.csv",
                   "output/multi_clock_analysis.csv", "output/threshold_analysis.csv",
                   "output/signature_lifecycle.csv", "output/frequency_stats.csv",
                   "output/epoch_precision.csv", "output/epoch_summary.csv",
                   "output/signature_context.csv", "output/future_convergence.csv",
                   "output/patriarch_lifecycle.csv", "output/gematria_resonance.csv"],
        "outputs": ["output/jubilee.db"],
    },
]


def file_hash(filepath):
    """Get mtime-based hash for a file."""
    p = INSTANCE_DIR / filepath
    if p.exists():
        return f"{p.stat().st_mtime:.6f}:{p.stat().st_size}"
    return "missing"


def load_cache():
    try:
        return json.loads(CACHE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def needs_run(step, cache, force=False):
    """Check if a step needs to run based on input file changes."""
    if force:
        return True
    step_cache = cache.get(step["id"], {})
    for f in step["inputs"]:
        current = file_hash(f)
        if current != step_cache.get(f):
            return True
    # Check if outputs exist
    for f in step["outputs"]:
        if not (INSTANCE_DIR / f).exists():
            return True
    return False


def build_dag():
    """Build dependency graph from step inputs/outputs."""
    # Map output files to the step that produces them
    output_to_step = {}
    for step in STEPS:
        for f in step["outputs"]:
            output_to_step[f] = step["id"]

    # Build dependency dict
    deps = {}
    for step in STEPS:
        step_deps = set()
        for f in step["inputs"]:
            if f in output_to_step:
                step_deps.add(output_to_step[f])
        deps[step["id"]] = step_deps

    return deps


def get_git_hash():
    """Get current git commit hash, or 'unknown' if not in a repo."""
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True, timeout=5,
                                cwd=str(INSTANCE_DIR))
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def load_params_snapshot():
    """Load params.json for logging, or return empty dict."""
    params_path = INSTANCE_DIR / "data" / "params.json"
    try:
        data = json.loads(params_path.read_text())
        data.pop("_description", None)
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def log_run(ran, skipped, failed, step_timings, duration_s, force):
    """Append a run record to runs.jsonl for experiment tracking."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_hash": get_git_hash(),
        "total_steps": len(STEPS),
        "ran": ran,
        "skipped": skipped,
        "failed": failed,
        "forced": force,
        "duration_s": round(duration_s, 2),
        "step_timings": step_timings,
        "params_hash": hashlib.md5(
            json.dumps(load_params_snapshot(), sort_keys=True).encode()
        ).hexdigest()[:8],
        "output_sizes": {},
    }

    # Snapshot output file sizes
    output_dir = INSTANCE_DIR / "output"
    if output_dir.exists():
        for f in sorted(output_dir.glob("*.csv")):
            record["output_sizes"][f.name] = f.stat().st_size
        db = output_dir / "jubilee.db"
        if db.exists():
            record["output_sizes"]["jubilee.db"] = db.stat().st_size

    # Append to runs.jsonl
    RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RUNS_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def run_pipeline(force=False, dry_run=False):
    deps = build_dag()
    ts = TopologicalSorter(deps)
    order = list(ts.static_order())

    step_map = {s["id"]: s for s in STEPS}
    cache = load_cache()

    print(f"\n  Pipeline: {len(STEPS)} steps")
    print(f"  Instance: {INSTANCE_DIR}\n")

    pipeline_start = time.perf_counter()
    ran = 0
    skipped = 0
    failed = 0
    step_timings = {}

    for step_id in order:
        step = step_map.get(step_id)
        if not step:
            continue

        if not needs_run(step, cache, force):
            skipped += 1
            if dry_run:
                print(f"  SKIP  {step['name']}")
            continue

        if dry_run:
            print(f"  RUN   {step['name']}: {' '.join(step['command'])}")
            ran += 1
            continue

        print(f"  ► {step['name']}...", end=" ", flush=True)
        start = time.perf_counter()

        try:
            result = subprocess.run(
                step["command"],
                cwd=step["cwd"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            elapsed = time.perf_counter() - start

            if result.returncode != 0:
                print(f"FAILED ({elapsed:.1f}s)")
                if result.stderr:
                    print(f"    {result.stderr[:200]}")
                failed += 1
                continue

            # Update cache with current input hashes
            step_cache = {}
            for f in step["inputs"]:
                step_cache[f] = file_hash(f)
            cache[step_id] = step_cache
            save_cache(cache)

            print(f"OK ({elapsed:.1f}s)")
            step_timings[step_id] = round(elapsed, 2)
            ran += 1

        except subprocess.TimeoutExpired:
            print("TIMEOUT (120s)")
            step_timings[step_id] = "timeout"
            failed += 1

    pipeline_duration = time.perf_counter() - pipeline_start
    print(f"\n  Done: {ran} ran, {skipped} skipped, {failed} failed")
    print(f"  Total: {pipeline_duration:.1f}s\n")

    # Log run to runs.jsonl (skip for dry runs)
    if not dry_run:
        log_run(ran, skipped, failed, step_timings, pipeline_duration, force)

    return failed == 0


def show_status():
    cache = load_cache()
    deps = build_dag()

    print(f"\n  Pipeline Status")
    print(f"  Instance: {INSTANCE_DIR}\n")
    print(f"  {'Step':<25} {'Status':<10} {'Outputs'}")
    print("  " + "-" * 65)

    for step in STEPS:
        needs = needs_run(step, cache)
        status = "STALE" if needs else "CURRENT"
        outputs = ", ".join(os.path.basename(f) for f in step["outputs"])
        marker = "●" if not needs else "○"
        print(f"  {marker} {step['name']:<23} {status:<10} {outputs}")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lab Pipeline Runner")
    parser.add_argument("--force", action="store_true", help="Force re-run all steps")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run")
    parser.add_argument("--status", action="store_true", help="Show pipeline status")
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        success = run_pipeline(force=args.force, dry_run=args.dry_run)
        sys.exit(0 if success else 1)
