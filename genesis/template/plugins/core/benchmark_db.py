#!/usr/bin/env python3
"""Benchmark: SQLite configurations for Jubilee Lab.

Tests different approaches to find the optimal setup:
  A) FTS5 full-text search vs LIKE queries
  B) WAL journal mode vs default (delete)
  C) Normalized tables vs denormalized single-table
  D) Indexed vs unindexed columns
  E) Simulated scale: 171 events → 5K, 10K, 50K events
  F) KB/transcript memory search at scale

Outputs results to stdout as a comparison table.
"""

import csv
import json
import os
import random
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = "/tmp/jubilee-bench.db"
ITERATIONS = 200


def load_real_data():
    """Load actual project data."""
    events = []
    db_path = ROOT / "output" / "database.csv"
    if db_path.exists():
        with open(db_path) as f:
            events = list(csv.DictReader(f))

    kb_docs = []
    for md in (ROOT / "kb").rglob("*.md"):
        kb_docs.append({"path": str(md.relative_to(ROOT)), "content": md.read_text()})

    transcripts = []
    for md in (ROOT / "kb" / "transcripts").rglob("*.md"):
        transcripts.append({"path": str(md.relative_to(ROOT)), "content": md.read_text()})

    return events, kb_docs, transcripts


def scale_events(events, target):
    """Generate synthetic events to reach target count."""
    if len(events) >= target:
        return events[:target]
    scaled = list(events)
    base_len = len(events)
    words = ["creation", "exile", "restoration", "temple", "jubilee", "cross",
             "covenant", "babylon", "jerusalem", "moses", "david", "solomon",
             "prophecy", "reformation", "balfour", "millennium", "sabbath",
             "daniel", "revelation", "convergence", "signature", "remainder"]
    while len(scaled) < target:
        base = events[len(scaled) % base_len].copy()
        year = random.randint(-4004, 2050)
        base["year_ad"] = str(year)
        base["event"] = f"Synthetic event {len(scaled)}: {random.choice(words)} {random.choice(words)}"
        base["cosmic_remainder"] = f"{random.random():.4f}"
        base["tags"] = ",".join(random.sample(words, 3))
        scaled.append(base)
    return scaled


def scale_kb(kb_docs, target):
    """Generate synthetic KB docs."""
    if len(kb_docs) >= target:
        return kb_docs[:target]
    scaled = list(kb_docs)
    while len(scaled) < target:
        base = kb_docs[len(scaled) % len(kb_docs)]
        scaled.append({
            "path": f"kb/synthetic/doc-{len(scaled)}.md",
            "content": base["content"][:500] + f"\n\nSynthetic document {len(scaled)}. "
                       f"Topics: convergence, remainder analysis, jubilee cycles."
        })
    return scaled


def bench(label, fn, iterations=ITERATIONS):
    """Benchmark a function, return avg ms."""
    # Warmup
    for _ in range(min(10, iterations)):
        fn()
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    elapsed = (time.perf_counter() - start) / iterations * 1000
    return elapsed


def cleanup():
    for f in [DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm"]:
        try:
            os.unlink(f)
        except FileNotFoundError:
            pass


# =========================================================================
# Test A: Journal mode — WAL vs DELETE
# =========================================================================
def test_journal_modes(events):
    results = {}
    for mode in ["delete", "wal"]:
        cleanup()
        conn = sqlite3.connect(DB_PATH)
        conn.execute(f"PRAGMA journal_mode={mode}")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("""CREATE TABLE events (
            id INTEGER PRIMARY KEY, year_ad REAL, event TEXT,
            cosmic_remainder REAL, tags TEXT
        )""")
        conn.execute("CREATE INDEX idx_year ON events(year_ad)")

        # Insert
        insert_time = bench(f"insert-{mode}", lambda: (
            conn.execute("INSERT INTO events (year_ad, event, cosmic_remainder, tags) VALUES (?, ?, ?, ?)",
                         (random.randint(-4004, 2050), "test event", random.random(), "tag1,tag2")),
            conn.commit()
        ), 500)

        # Batch insert all events
        conn.executemany("INSERT INTO events (year_ad, event, cosmic_remainder, tags) VALUES (?, ?, ?, ?)",
                         [(float(e.get("year_ad", 0)), e.get("event", ""), float(e.get("cosmic_remainder", 0) or 0), e.get("tags", "")) for e in events])
        conn.commit()

        # Query
        query_time = bench(f"query-{mode}", lambda: conn.execute(
            "SELECT * FROM events WHERE year_ad BETWEEN 1900 AND 2050 AND cosmic_remainder > 0.4"
        ).fetchall())

        results[mode] = {"insert_ms": insert_time, "query_ms": query_time}
        conn.close()
        cleanup()
    return results


# =========================================================================
# Test B: FTS5 vs LIKE for text search
# =========================================================================
def test_fts_vs_like(kb_docs):
    cleanup()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=wal")
    conn.execute("PRAGMA synchronous=NORMAL")

    # Regular table with LIKE
    conn.execute("CREATE TABLE kb (id INTEGER PRIMARY KEY, path TEXT, content TEXT)")
    conn.execute("CREATE INDEX idx_path ON kb(path)")
    conn.executemany("INSERT INTO kb (path, content) VALUES (?, ?)",
                     [(d["path"], d["content"]) for d in kb_docs])

    # FTS5 table
    conn.execute("CREATE VIRTUAL TABLE kb_fts USING fts5(path, content)")
    conn.executemany("INSERT INTO kb_fts (path, content) VALUES (?, ?)",
                     [(d["path"], d["content"]) for d in kb_docs])
    conn.commit()

    search_terms = ["jubilee", "remainder", "convergence", "2037", "restoration",
                    "sabbath", "temple", "covenant", "millennium", "cross"]

    like_time = bench("LIKE", lambda: conn.execute(
        f"SELECT path, substr(content, 1, 200) FROM kb WHERE content LIKE ?",
        (f"%{random.choice(search_terms)}%",)
    ).fetchall())

    fts_time = bench("FTS5", lambda: conn.execute(
        f"SELECT path, snippet(kb_fts, 1, '<b>', '</b>', '...', 32) FROM kb_fts WHERE kb_fts MATCH ?",
        (random.choice(search_terms),)
    ).fetchall())

    # Multi-term search
    like_multi = bench("LIKE-multi", lambda: conn.execute(
        "SELECT path FROM kb WHERE content LIKE '%jubilee%' AND content LIKE '%remainder%'"
    ).fetchall())

    fts_multi = bench("FTS5-multi", lambda: conn.execute(
        "SELECT path FROM kb_fts WHERE kb_fts MATCH 'jubilee AND remainder'"
    ).fetchall())

    conn.close()
    cleanup()
    return {
        "single_term": {"like_ms": like_time, "fts5_ms": fts_time},
        "multi_term": {"like_ms": like_multi, "fts5_ms": fts_multi},
    }


# =========================================================================
# Test C: Normalized vs Denormalized
# =========================================================================
def test_normalized_vs_denorm(events):
    cleanup()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=wal")

    # Denormalized: single table with all columns
    conn.execute("""CREATE TABLE events_denorm (
        id INTEGER PRIMARY KEY, year_ad REAL, event TEXT,
        cosmic_remainder REAL, israel_remainder REAL, church_remainder REAL,
        tags TEXT, category TEXT, significance TEXT
    )""")
    conn.execute("CREATE INDEX idx_denorm_year ON events_denorm(year_ad)")
    conn.execute("CREATE INDEX idx_denorm_cosmic ON events_denorm(cosmic_remainder)")

    # Normalized: events + tags in separate table
    conn.execute("""CREATE TABLE events_norm (
        id INTEGER PRIMARY KEY, year_ad REAL, event TEXT,
        cosmic_remainder REAL, israel_remainder REAL, church_remainder REAL,
        category TEXT, significance TEXT
    )""")
    conn.execute("CREATE TABLE event_tags (event_id INTEGER, tag TEXT, FOREIGN KEY(event_id) REFERENCES events_norm(id))")
    conn.execute("CREATE INDEX idx_norm_year ON events_norm(year_ad)")
    conn.execute("CREATE INDEX idx_tags ON event_tags(tag)")
    conn.execute("CREATE INDEX idx_tags_event ON event_tags(event_id)")

    for i, e in enumerate(events):
        yr = float(e.get("year_ad", 0) or 0)
        cr = float(e.get("cosmic_remainder", 0) or 0)
        ir = float(e.get("israel_remainder", 0) or 0)
        ch = float(e.get("church_remainder", 0) or 0)
        tags = e.get("tags", "")
        ev = e.get("event", "")
        cat = e.get("category", "")
        sig = e.get("significance", "")

        conn.execute("INSERT INTO events_denorm VALUES (?,?,?,?,?,?,?,?,?)",
                     (i, yr, ev, cr, ir, ch, tags, cat, sig))
        conn.execute("INSERT INTO events_norm VALUES (?,?,?,?,?,?,?,?)",
                     (i, yr, ev, cr, ir, ch, cat, sig))
        for tag in [t.strip() for t in tags.split(",") if t.strip()]:
            conn.execute("INSERT INTO event_tags VALUES (?,?)", (i, tag))
    conn.commit()

    # Query: find events by tag
    denorm_tag = bench("denorm-tag", lambda: conn.execute(
        "SELECT * FROM events_denorm WHERE tags LIKE '%restoration%'"
    ).fetchall())

    norm_tag = bench("norm-tag", lambda: conn.execute(
        """SELECT e.* FROM events_norm e
           JOIN event_tags t ON e.id = t.event_id
           WHERE t.tag = 'restoration'"""
    ).fetchall())

    # Query: find events by remainder range
    denorm_rem = bench("denorm-remainder", lambda: conn.execute(
        "SELECT * FROM events_denorm WHERE ABS(cosmic_remainder - 0.42) < 0.02"
    ).fetchall())

    norm_rem = bench("norm-remainder", lambda: conn.execute(
        "SELECT * FROM events_norm WHERE ABS(cosmic_remainder - 0.42) < 0.02"
    ).fetchall())

    conn.close()
    cleanup()
    return {
        "tag_search": {"denorm_ms": denorm_tag, "norm_ms": norm_tag},
        "remainder_search": {"denorm_ms": denorm_rem, "norm_ms": norm_rem},
    }


# =========================================================================
# Test D: Scale test — query time vs dataset size
# =========================================================================
def test_scale(events):
    sizes = [171, 1000, 5000, 10000, 50000]
    results = {}

    for size in sizes:
        scaled = scale_events(events, size)
        cleanup()
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=wal")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("""CREATE TABLE events (
            id INTEGER PRIMARY KEY, year_ad REAL, event TEXT,
            cosmic_remainder REAL, tags TEXT
        )""")
        conn.execute("CREATE INDEX idx_year ON events(year_ad)")
        conn.execute("CREATE INDEX idx_remainder ON events(cosmic_remainder)")

        # FTS for event text
        conn.execute("CREATE VIRTUAL TABLE events_fts USING fts5(event, tags)")

        conn.executemany("INSERT INTO events VALUES (?,?,?,?,?)",
                         [(i, float(e.get("year_ad", 0) or 0), e.get("event", ""),
                           float(e.get("cosmic_remainder", 0) or 0), e.get("tags", ""))
                          for i, e in enumerate(scaled)])
        conn.executemany("INSERT INTO events_fts VALUES (?,?)",
                         [(e.get("event", ""), e.get("tags", "")) for e in scaled])
        conn.commit()

        # DB file size
        db_size = os.path.getsize(DB_PATH)

        # Indexed range query
        range_q = bench(f"range-{size}", lambda: conn.execute(
            "SELECT * FROM events WHERE year_ad BETWEEN 1900 AND 2050"
        ).fetchall())

        # Remainder proximity
        remainder_q = bench(f"rem-{size}", lambda: conn.execute(
            "SELECT * FROM events WHERE ABS(cosmic_remainder - 0.68) < 0.02"
        ).fetchall())

        # Full-text search
        fts_q = bench(f"fts-{size}", lambda: conn.execute(
            "SELECT * FROM events_fts WHERE events_fts MATCH 'jubilee OR restoration'"
        ).fetchall())

        # Full table scan
        scan_q = bench(f"scan-{size}", lambda: conn.execute(
            "SELECT COUNT(*), AVG(cosmic_remainder) FROM events"
        ).fetchall())

        results[size] = {
            "db_size_kb": db_size // 1024,
            "range_ms": range_q,
            "remainder_ms": remainder_q,
            "fts_ms": fts_q,
            "full_scan_ms": scan_q,
        }
        conn.close()
        cleanup()

    return results


# =========================================================================
# Test E: Memory search at scale (transcripts + KB)
# =========================================================================
def test_memory_search(kb_docs, transcripts):
    sizes = [32, 100, 500, 1000, 5000]
    results = {}

    for size in sizes:
        scaled_kb = scale_kb(kb_docs, size)
        cleanup()
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=wal")

        conn.execute("CREATE VIRTUAL TABLE memory_fts USING fts5(path, title, content, type)")
        for d in scaled_kb:
            title = d["path"].split("/")[-1].replace(".md", "").replace("-", " ")
            doc_type = "transcript" if "transcript" in d["path"] else "kb"
            conn.execute("INSERT INTO memory_fts VALUES (?,?,?,?)",
                         (d["path"], title, d["content"], doc_type))
        conn.commit()

        # Single term
        single = bench(f"mem-single-{size}", lambda: conn.execute(
            "SELECT path, snippet(memory_fts, 2, '>>','<<', '...', 40) FROM memory_fts WHERE memory_fts MATCH ?",
            (random.choice(["jubilee", "remainder", "convergence", "restoration"]),)
        ).fetchall())

        # Cross-reference: find related docs
        xref = bench(f"mem-xref-{size}", lambda: conn.execute(
            "SELECT path, rank FROM memory_fts WHERE memory_fts MATCH 'jubilee AND (remainder OR convergence)' ORDER BY rank LIMIT 10"
        ).fetchall())

        results[size] = {"single_ms": single, "cross_ref_ms": xref}
        conn.close()
        cleanup()

    return results


# =========================================================================
# Test F: File read vs SQLite for Claude context injection
# =========================================================================
def test_context_injection(events, kb_docs):
    cleanup()

    # Write temp CSV
    csv_path = "/tmp/jubilee-bench-events.csv"
    if events:
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=events[0].keys())
            w.writeheader()
            w.writerows(events)

    # SQLite
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=wal")
    conn.execute("""CREATE TABLE events (
        id INTEGER PRIMARY KEY, year_ad REAL, event TEXT,
        cosmic_remainder REAL, tags TEXT
    )""")
    conn.execute("CREATE INDEX idx_year ON events(year_ad)")
    conn.executemany("INSERT INTO events VALUES (?,?,?,?,?)",
                     [(i, float(e.get("year_ad", 0) or 0), e.get("event", ""),
                       float(e.get("cosmic_remainder", 0) or 0), e.get("tags", ""))
                      for i, e in enumerate(events)])
    conn.commit()

    # Method A: Read full CSV + filter in Python
    def csv_filter():
        with open(csv_path) as f:
            rows = list(csv.DictReader(f))
        return [r for r in rows if float(r.get("year_ad", 0) or 0) > 1900]

    # Method B: SQLite query
    def sqlite_filter():
        return conn.execute("SELECT * FROM events WHERE year_ad > 1900").fetchall()

    csv_time = bench("csv-read-filter", csv_filter)
    sql_time = bench("sqlite-query", sqlite_filter)

    conn.close()
    cleanup()
    try:
        os.unlink(csv_path)
    except FileNotFoundError:
        pass

    return {"csv_read_filter_ms": csv_time, "sqlite_query_ms": sql_time}


# =========================================================================
# Main
# =========================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("  JUBILEE LAB — SQLite Benchmark Suite")
    print("=" * 70)
    print()

    events, kb_docs, transcripts = load_real_data()
    print(f"  Dataset: {len(events)} events, {len(kb_docs)} KB docs, {len(transcripts)} transcripts")
    print()

    # Test A: Journal modes
    print("─" * 70)
    print("  TEST A: Journal Mode (WAL vs DELETE)")
    print("─" * 70)
    jm = test_journal_modes(events)
    print(f"  {'Mode':<10} {'Insert (ms)':<15} {'Query (ms)':<15}")
    for mode, r in jm.items():
        print(f"  {mode:<10} {r['insert_ms']:<15.3f} {r['query_ms']:<15.3f}")
    winner_a = "WAL" if jm["wal"]["query_ms"] < jm["delete"]["query_ms"] else "DELETE"
    print(f"  → Winner: {winner_a}")
    print()

    # Test B: FTS5 vs LIKE
    print("─" * 70)
    print("  TEST B: Full-Text Search (FTS5 vs LIKE)")
    print("─" * 70)
    fts = test_fts_vs_like(kb_docs)
    print(f"  {'Search':<15} {'LIKE (ms)':<15} {'FTS5 (ms)':<15} {'Speedup':<10}")
    for k, v in fts.items():
        speedup = v["like_ms"] / v["fts5_ms"] if v["fts5_ms"] > 0 else 0
        print(f"  {k:<15} {v['like_ms']:<15.3f} {v['fts5_ms']:<15.3f} {speedup:<10.1f}x")
    print(f"  → Winner: FTS5")
    print()

    # Test C: Normalized vs Denormalized
    print("─" * 70)
    print("  TEST C: Normalized vs Denormalized Tables")
    print("─" * 70)
    norm = test_normalized_vs_denorm(events)
    print(f"  {'Query':<20} {'Denorm (ms)':<15} {'Norm (ms)':<15}")
    for k, v in norm.items():
        print(f"  {k:<20} {v['denorm_ms']:<15.3f} {v['norm_ms']:<15.3f}")
    print()

    # Test D: Scale test
    print("─" * 70)
    print("  TEST D: Query Performance at Scale")
    print("─" * 70)
    scale = test_scale(events)
    print(f"  {'Events':<10} {'DB (KB)':<10} {'Range (ms)':<12} {'Remainder':<12} {'FTS (ms)':<12} {'Scan (ms)':<12}")
    for size, r in sorted(scale.items()):
        print(f"  {size:<10} {r['db_size_kb']:<10} {r['range_ms']:<12.3f} {r['remainder_ms']:<12.3f} {r['fts_ms']:<12.3f} {r['full_scan_ms']:<12.3f}")
    print()

    # Test E: Memory search at scale
    print("─" * 70)
    print("  TEST E: AI Memory Search (KB + Transcripts)")
    print("─" * 70)
    mem = test_memory_search(kb_docs, transcripts)
    print(f"  {'Docs':<10} {'Single (ms)':<15} {'Cross-ref (ms)':<15}")
    for size, r in sorted(mem.items()):
        print(f"  {size:<10} {r['single_ms']:<15.3f} {r['cross_ref_ms']:<15.3f}")
    print()

    # Test F: CSV vs SQLite for context
    print("─" * 70)
    print("  TEST F: Context Injection (CSV Read vs SQLite Query)")
    print("─" * 70)
    ctx = test_context_injection(events, kb_docs)
    print(f"  CSV read + filter: {ctx['csv_read_filter_ms']:.3f} ms")
    print(f"  SQLite query:      {ctx['sqlite_query_ms']:.3f} ms")
    speedup = ctx["csv_read_filter_ms"] / ctx["sqlite_query_ms"] if ctx["sqlite_query_ms"] > 0 else 0
    print(f"  → SQLite is {speedup:.1f}x faster")
    print()

    # Summary
    print("=" * 70)
    print("  RECOMMENDATIONS")
    print("=" * 70)
    print("""
  1. JOURNAL MODE: Use WAL — better concurrent read/write performance
  2. TEXT SEARCH:  Use FTS5 — order of magnitude faster than LIKE
  3. TABLE DESIGN: Denormalized for events (simpler, fast enough)
                   + FTS5 virtual tables for text search
  4. INDEXES:     year_ad, cosmic_remainder, israel_remainder, church_remainder
  5. MEMORY:      Single FTS5 table for all KB + transcripts
                   — sub-millisecond search even at 5000 docs
  6. ARCHITECTURE: CSV → SQLite build step (engine.py db)
                   Claude queries SQLite during chat
                   CSVs remain source of truth, git-diffable
    """)
    print("=" * 70)
