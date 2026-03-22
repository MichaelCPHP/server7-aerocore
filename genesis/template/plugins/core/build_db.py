#!/usr/bin/env python3
"""Build SQLite database from all CSVs + KB markdown files.

Reads all CSV files from data/ and output/, all markdown from kb/,
and loads them into a single SQLite database with proper indexes
and FTS5 full-text search tables.

Usage:
    python3 scripts/build_db.py              # Build database
    python3 scripts/build_db.py --stats      # Show database stats
    python3 scripts/build_db.py --query "SQL" # Run a query
"""

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get('LAB_INSTANCE', Path.cwd()))
DB_PATH = ROOT / "output" / "jubilee.db"

# Columns that should be stored as REAL (float)
FLOAT_COLUMNS = {
    "year_ad", "am_year", "cosmic_jubilee", "cosmic_remainder", "cosmic_cycle",
    "cosmic_year_in_cycle", "israel_jubilee", "israel_remainder", "israel_cycle",
    "israel_year_in_cycle", "church_jubilee", "church_remainder", "church_cycle",
    "church_year_in_cycle", "daniel_jubilee", "daniel_remainder", "daniel_cycle",
    "daniel_year_in_cycle", "moadim_jubilee", "moadim_remainder", "moadim_cycle",
    "moadim_year_in_cycle", "pct_of_plan", "balance_to_160", "gap_years",
    "multiple", "convergence_count", "delta_from_1", "sum", "remainder",
    "remainder_a", "remainder_b", "word_count", "turn_count", "event_count",
    "events_per_year", "cluster_size", "value", "digital_root", "digit_sum",
    "years_forward", "target_year", "measure_years", "end_year", "years_from_now",
    "before_distance", "after_distance", "difference", "count",
    # Enrichment columns
    "e_convergence_index", "e_boundary_score", "e_boundary_hits_002",
    "e_clock_alignment", "e_jubilee_clocks", "e_threshold_clocks",
    "e_cascade_count", "e_sig_dormancy_ratio", "e_sig_total_firings",
    # New analysis columns
    "convergence_index", "boundary_count_002", "boundary_count_005",
    "boundary_count_010", "composite_score", "min_boundary_dist",
    "total_channels", "active_clocks", "unique_bands", "jubilee_clocks",
    "threshold_clocks", "spread", "threshold_clock_count", "cascade_count",
    "total_firings", "active_span", "density_per_1000yr", "avg_gap",
    "median_gap", "min_gap", "max_gap", "dormancy_ratio", "gap_regularity_cv",
    "anchor_exact", "anchor_near", "complement_pairs", "astro_proximity",
    "clock_alignment_count",
    # Frequency stats
    "linear_r_squared", "exponential_r_squared", "doubling_time_years",
    "half_ratio", "modern_pct_events", "modern_pct_timeline",
    "concentration_factor", "shemitah_ratio", "quartile_ratio",
    # Epoch precision
    "closest_gap_years", "events_within_10yr", "events_within_50yr",
    "tail_duration", "deviation_from_2000", "density_per_100yr",
    # Signature context
    "member_count", "unique_categories", "dominant_category_pct",
    "homogeneity", "unique_themes", "unique_epochs", "outlier_count",
    # Future convergence
    "convergence_score", "condition_count", "boundary_clocks", "anchor_hits",
    # Patriarch lifecycle
    "span_years", "total_boundary_hits", "total_checks",
    "alignment_score", "vs_random",
    # Gematria resonance
    "digital_root", "total_resonances",
    # Enrichment v2
    "e_sig_homogeneity", "e_sig_mixed_valence",
}

# Columns to index for fast queries
INDEX_COLUMNS = {
    "events": ["year_ad", "cosmic_remainder", "israel_remainder", "church_remainder",
               "daniel_remainder", "moadim_remainder", "signature", "epoch", "slot"],
    "cycles": ["cycle_type", "from_year", "to_year", "gap_years"],
    "gaps": ["gap_years"],
    "signatures": ["signature", "remainder"],
    "convergence": ["year", "convergence_count"],
    "remainder_clusters": ["remainder", "cluster_size"],
    "gematria": ["value", "name"],
    "transcripts": ["date", "title"],
    "convergence_index": ["year_ad", "convergence_index"],
    "multi_clock_analysis": ["year_ad", "jubilee_clocks", "unique_bands"],
    "threshold_analysis": ["year_ad", "threshold_clock_count"],
    "signature_lifecycle": ["signature", "dormancy_ratio", "total_firings"],
    "frequency_stats": ["metric"],
    "epoch_precision": ["boundary"],
    "epoch_summary": ["epoch_id"],
    "signature_context": ["signature", "homogeneity"],
    "future_convergence": ["year", "convergence_score"],
    "patriarch_lifecycle": ["figure", "alignment_score"],
    "gematria_resonance": ["word", "value", "total_resonances"],
}


def safe_float(val):
    """Convert to float, return None if not possible."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def table_name_from_csv(csv_path):
    """Convert CSV filename to table name."""
    return csv_path.stem.replace("-", "_")


def load_csv(csv_path):
    """Load a CSV file and return (headers, rows)."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)
    return headers, rows


def create_table(conn, table_name, headers):
    """Create a table with appropriate column types."""
    cols = []
    has_id = False
    for h in headers:
        clean = h.strip().replace(" ", "_").replace("-", "_").lower()
        if clean == "id":
            has_id = True
            cols.append('"id" INTEGER PRIMARY KEY')
            continue
        if clean in FLOAT_COLUMNS:
            cols.append(f'"{clean}" REAL')
        else:
            cols.append(f'"{clean}" TEXT')
    col_def = ", ".join(cols)
    if not has_id:
        col_def = "id INTEGER PRIMARY KEY AUTOINCREMENT, " + col_def
    conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    conn.execute(f'CREATE TABLE "{table_name}" ({col_def})')


def insert_rows(conn, table_name, headers, rows):
    """Insert rows with type coercion."""
    clean_headers = [h.strip().replace(" ", "_").replace("-", "_").lower() for h in headers]
    placeholders = ", ".join(["?"] * len(clean_headers))
    col_names = ", ".join([f'"{h}"' for h in clean_headers])
    sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})'

    batch = []
    for row in rows:
        values = []
        for h_orig, h_clean in zip(headers, clean_headers):
            val = row.get(h_orig, "")
            if h_clean in FLOAT_COLUMNS:
                values.append(safe_float(val))
            else:
                values.append(val if val else None)
        batch.append(values)

    conn.executemany(sql, batch)


def create_indexes(conn, table_name):
    """Create indexes for known important columns."""
    if table_name in INDEX_COLUMNS:
        # Get actual columns in table
        cursor = conn.execute(f'PRAGMA table_info("{table_name}")')
        actual_cols = {row[1] for row in cursor.fetchall()}

        for col in INDEX_COLUMNS[table_name]:
            if col in actual_cols:
                idx_name = f"idx_{table_name}_{col}"
                conn.execute(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table_name}"("{col}")')


def parse_frontmatter(content):
    """Extract YAML-ish frontmatter from markdown."""
    meta = {}
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            fm = content[3:end]
            for line in fm.strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip().lower()
                    val = val.strip().strip('"').strip("'")
                    # Handle [tag1, tag2] arrays
                    if val.startswith("[") and val.endswith("]"):
                        val = val[1:-1]
                    meta[key] = val
    return meta


def build_kb_table(conn):
    """Build knowledge base table from all markdown files."""
    conn.execute("DROP TABLE IF EXISTS knowledge_base")
    conn.execute("""CREATE TABLE knowledge_base (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL,
        category TEXT,
        title TEXT,
        date TEXT,
        tags TEXT,
        summary TEXT,
        content TEXT NOT NULL,
        word_count INTEGER
    )""")
    conn.execute('CREATE INDEX idx_kb_category ON knowledge_base(category)')
    conn.execute('CREATE INDEX idx_kb_date ON knowledge_base(date)')

    count = 0
    for md_file in sorted((ROOT / "kb").rglob("*.md")):
        rel = str(md_file.relative_to(ROOT))
        content = md_file.read_text(encoding="utf-8", errors="replace")
        meta = parse_frontmatter(content)

        # Derive category from path: kb/analysis/foo.md → analysis
        parts = rel.split("/")
        category = parts[1] if len(parts) > 2 else "root"

        title = meta.get("title", md_file.stem.replace("-", " ").title())
        date = meta.get("date", "")
        tags = meta.get("tags", "")
        summary = meta.get("summary", "")
        word_count = len(content.split())

        conn.execute(
            "INSERT INTO knowledge_base (path, category, title, date, tags, summary, content, word_count) VALUES (?,?,?,?,?,?,?,?)",
            (rel, category, title, date, tags, summary, content, word_count)
        )
        count += 1

    return count


def build_fts_tables(conn):
    """Build FTS5 full-text search tables."""
    # Events FTS (searchable event names, tags, notes)
    conn.execute("DROP TABLE IF EXISTS events_fts")
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
    if cursor.fetchone():
        conn.execute("""CREATE VIRTUAL TABLE events_fts USING fts5(
            name, tags, notes, signature, epoch,
            content='events', content_rowid='id'
        )""")
        conn.execute("""INSERT INTO events_fts(rowid, name, tags, notes, signature, epoch)
            SELECT id, name, tags, notes, signature, epoch FROM events""")

    # Knowledge base FTS (searchable title, tags, content)
    conn.execute("DROP TABLE IF EXISTS kb_fts")
    conn.execute("""CREATE VIRTUAL TABLE kb_fts USING fts5(
        path, title, tags, summary, content, category,
        content='knowledge_base', content_rowid='id'
    )""")
    conn.execute("""INSERT INTO kb_fts(rowid, path, title, tags, summary, content, category)
        SELECT id, path, title, tags, summary, content, category FROM knowledge_base""")

    # Tags table (normalized from events)
    conn.execute("DROP TABLE IF EXISTS event_tags")
    conn.execute("""CREATE TABLE event_tags (
        event_id INTEGER NOT NULL,
        tag TEXT NOT NULL,
        FOREIGN KEY(event_id) REFERENCES events(id)
    )""")
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
    if cursor.fetchone():
        rows = conn.execute("SELECT id, tags FROM events WHERE tags IS NOT NULL AND tags != ''").fetchall()
        tag_rows = []
        for eid, tags in rows:
            for tag in [t.strip() for t in tags.split(",") if t.strip()]:
                tag_rows.append((eid, tag))
        conn.executemany("INSERT INTO event_tags VALUES (?,?)", tag_rows)
        conn.execute("CREATE INDEX idx_event_tags_tag ON event_tags(tag)")
        conn.execute("CREATE INDEX idx_event_tags_eid ON event_tags(event_id)")


def build_database():
    """Build the full SQLite database.

    engine.py writes directly to jubilee.db for core tables (events, clocks,
    signatures, gaps, calculator). build_db.py skips those and handles:
    - Plugin-generated output CSVs → tables
    - Source data CSVs → source_* tables
    - JSON configs → config tables
    - KB markdown → knowledge_base + FTS indexes
    """
    start = time.perf_counter()

    # Tables managed by engine.py — do not overwrite from CSVs
    ENGINE_TABLES = {'events', 'clocks', 'signatures', 'gaps', 'calculator'}

    # Do NOT delete jubilee.db — engine.py writes core tables directly
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=OFF")

    # Rename database.csv table to 'events' for clarity
    # If enriched version exists, use that as the events table instead
    TABLE_RENAMES = {"database_enriched": "events", "database": "events_base"}

    # Load all CSVs from output/
    csv_count = 0
    total_rows = 0
    skipped_engine = 0
    for csv_file in sorted((ROOT / "output").glob("*.csv")):
        headers, rows = load_csv(csv_file)
        if not headers or not rows:
            continue
        table = table_name_from_csv(csv_file)
        table = TABLE_RENAMES.get(table, table)

        # Skip tables managed by engine.py
        if table in ENGINE_TABLES:
            skipped_engine += 1
            continue

        create_table(conn, table, headers)
        insert_rows(conn, table, headers, rows)
        create_indexes(conn, table)
        csv_count += 1
        total_rows += len(rows)

    # Load source data CSVs
    for csv_file in sorted((ROOT / "data").glob("*.csv")):
        headers, rows = load_csv(csv_file)
        if not headers or not rows:
            continue
        table = "source_" + table_name_from_csv(csv_file)
        create_table(conn, table, headers)
        insert_rows(conn, table, headers, rows)
        csv_count += 1
        total_rows += len(rows)

    # Load clocks and signatures as config tables
    clocks_path = ROOT / "data" / "clocks.json"
    if clocks_path.exists():
        clocks = json.loads(clocks_path.read_text())
        conn.execute("DROP TABLE IF EXISTS clocks_config")
        conn.execute("""CREATE TABLE clocks_config (
            name TEXT PRIMARY KEY, description TEXT,
            start_year_ad REAL, cycle_years REAL, total_cycles REAL
        )""")
        for name, c in clocks.items():
            conn.execute("INSERT INTO clocks_config VALUES (?,?,?,?,?)",
                         (name, c.get("description", ""), c.get("start_year_ad", 0),
                          c.get("cycle_years", 0), c.get("total_cycles", 0)))

    sigs_path = ROOT / "data" / "signatures.json"
    if sigs_path.exists():
        sigs = json.loads(sigs_path.read_text())
        conn.execute("DROP TABLE IF EXISTS signatures_config")
        conn.execute("""CREATE TABLE signatures_config (
            name TEXT PRIMARY KEY, remainder REAL, tolerance REAL, description TEXT
        )""")
        for s in sigs:
            conn.execute("INSERT INTO signatures_config VALUES (?,?,?,?)",
                         (s["name"], float(s["remainder"]), s.get("tolerance", 0.01), s.get("description", "")))

    # Build KB table
    kb_count = build_kb_table(conn)

    # Build FTS tables
    build_fts_tables(conn)

    conn.commit()

    elapsed = time.perf_counter() - start
    db_size = DB_PATH.stat().st_size

    # Get table list
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    fts_tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_fts%' ORDER BY name").fetchall()

    conn.close()

    print(f"Database built: {DB_PATH}")
    print(f"  Time:     {elapsed:.2f}s")
    print(f"  Size:     {db_size:,} bytes ({db_size // 1024} KB)")
    print(f"  CSVs:     {csv_count} files → {total_rows:,} rows")
    print(f"  Skipped:  {skipped_engine} engine-managed tables (events, clocks, signatures, gaps, calculator)")
    print(f"  KB docs:  {kb_count}")
    print(f"  Tables:   {len(tables)} ({len(fts_tables)} FTS)")
    print(f"  Tables:   {', '.join(t[0] for t in tables)}")


def show_stats():
    """Show database statistics."""
    if not DB_PATH.exists():
        print("Database not found. Run: python3 scripts/build_db.py")
        return

    conn = sqlite3.connect(str(DB_PATH))
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%' AND name NOT LIKE '%_content' AND name NOT LIKE '%_config' ORDER BY name"
    ).fetchall()

    print(f"Database: {DB_PATH} ({DB_PATH.stat().st_size // 1024} KB)")
    print(f"\n{'Table':<25} {'Rows':>8}  {'Columns':>8}")
    print("-" * 50)
    for (table,) in tables:
        row_count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        col_count = len(conn.execute(f'PRAGMA table_info("{table}")').fetchall())
        print(f"  {table:<23} {row_count:>8}  {col_count:>8}")

    # FTS tables
    fts = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_fts' ORDER BY name").fetchall()
    if fts:
        print(f"\nFTS5 search tables: {', '.join(t[0] for t in fts)}")

    # Index count
    idx_count = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
    print(f"Indexes: {idx_count}")

    conn.close()


def run_query(sql):
    """Execute a SQL query and print results."""
    if not DB_PATH.exists():
        print("Database not found. Run: python3 scripts/build_db.py")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        start = time.perf_counter()
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
        elapsed = (time.perf_counter() - start) * 1000

        if not rows:
            print("(no results)")
            return

        headers = rows[0].keys()
        # Print as table
        print("\t".join(headers))
        for row in rows[:50]:
            print("\t".join(str(row[h]) if row[h] is not None else "" for h in headers))

        if len(rows) > 50:
            print(f"\n... ({len(rows)} total rows, showing first 50)")
        print(f"\n[{len(rows)} rows in {elapsed:.1f}ms]")
    except sqlite3.Error as e:
        print(f"SQL Error: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Jubilee Lab SQLite database")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--query", type=str, help="Execute a SQL query")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.query:
        run_query(args.query)
    else:
        build_database()
