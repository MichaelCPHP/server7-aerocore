#!/usr/bin/env python3
"""Real-world benchmark: test actual API endpoint performance.

Simulates the kinds of queries Claude would run during a research session.
"""

import json
import time
import urllib.request

API = "http://localhost:3210/api/sql"

QUERIES = [
    ("Simple lookup: event by name",
     "SELECT * FROM events WHERE name LIKE '%Crucifixion%'"),

    ("Remainder proximity: .42 cluster",
     "SELECT name, year_ad, cosmic_remainder, signature FROM events WHERE ABS(cosmic_remainder - 0.42) < 0.02 ORDER BY year_ad"),

    ("Cross-clock: all 3 remainders near .68",
     "SELECT name, year_ad, cosmic_remainder, israel_remainder, church_remainder FROM events WHERE ABS(cosmic_remainder - 0.68) < 0.03 AND israel_remainder IS NOT NULL ORDER BY year_ad"),

    ("Tag join: find all 'restoration' tagged events",
     "SELECT e.name, e.year_ad, e.signature FROM events e JOIN event_tags t ON e.id = t.event_id WHERE t.tag = 'restoration' ORDER BY e.year_ad"),

    ("Cycles: sacred 50-year cycles in modern era",
     "SELECT * FROM cycles WHERE cycle_type = '50' AND from_year > 1900 ORDER BY from_year"),

    ("Aggregate: signature distribution",
     "SELECT signature, COUNT(*) as count, ROUND(AVG(cosmic_remainder), 4) as avg_rem FROM events WHERE signature IS NOT NULL GROUP BY signature ORDER BY count DESC"),

    ("Window: rank events by remainder proximity to .00",
     "SELECT name, year_ad, cosmic_remainder, ROW_NUMBER() OVER (ORDER BY ABS(cosmic_remainder)) as rank FROM events WHERE cosmic_remainder IS NOT NULL LIMIT 10"),

    ("FTS: search KB for 'convergence 2037'",
     "SELECT path, title FROM kb_fts WHERE kb_fts MATCH 'convergence AND 2037' ORDER BY rank LIMIT 5"),

    ("FTS: search events for 'temple'",
     "SELECT name, tags, signature FROM events_fts WHERE events_fts MATCH 'temple' LIMIT 10"),

    ("FTS: search all KB for 'remainder pattern'",
     "SELECT path, title FROM kb_fts WHERE kb_fts MATCH 'remainder AND pattern' ORDER BY rank LIMIT 10"),

    ("Complex join: gaps that are exact jubilees",
     "SELECT event_a, date_a, event_b, date_b, gap_years FROM gaps WHERE gap_years IN (50, 100, 150, 200, 250, 300, 350, 400, 450, 500) ORDER BY gap_years"),

    ("Subquery: events with above-average cosmic remainder",
     "SELECT name, year_ad, cosmic_remainder FROM events WHERE cosmic_remainder > (SELECT AVG(cosmic_remainder) FROM events WHERE cosmic_remainder IS NOT NULL) ORDER BY cosmic_remainder DESC LIMIT 10"),

    ("Multi-table: Daniel 490 projections hitting known events",
     "SELECT d.anchor, d.multiple, d.target_year, d.event_hit, e.signature FROM daniel_490 d LEFT JOIN events e ON e.year_ad = d.target_year WHERE d.event_hit IS NOT NULL AND d.event_hit != '' ORDER BY d.target_year"),

    ("Heavy aggregate: per-signature stats with min/max/count",
     "SELECT signature, COUNT(*) as n, MIN(year_ad) as earliest, MAX(year_ad) as latest, ROUND(AVG(cosmic_remainder),4) as avg_rem, ROUND(MIN(cosmic_remainder),4) as min_rem, ROUND(MAX(cosmic_remainder),4) as max_rem FROM events WHERE signature IS NOT NULL AND signature != '' GROUP BY signature ORDER BY n DESC"),

    ("Full scan: count all rows across 5 tables",
     "SELECT 'events' as tbl, COUNT(*) as n FROM events UNION ALL SELECT 'cycles', COUNT(*) FROM cycles UNION ALL SELECT 'gaps', COUNT(*) FROM gaps UNION ALL SELECT 'gematria', COUNT(*) FROM gematria UNION ALL SELECT 'kb', COUNT(*) FROM knowledge_base"),
]


def run_query(sql):
    """Run query via API and return (rows, elapsed_ms)."""
    data = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(API, data=data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read())
    if "error" in result:
        return 0, 0, result["error"]
    d = result["data"]
    return d["rowCount"], d["elapsed_ms"], None


def main():
    print("=" * 75)
    print("  JUBILEE LAB — Real-World API Benchmark")
    print("=" * 75)
    print()

    total_ms = 0
    results = []

    for label, sql in QUERIES:
        # Run 3 times, take best
        times = []
        rows = 0
        err = None
        for _ in range(3):
            r, ms, e = run_query(sql)
            if e:
                err = e
                break
            times.append(ms)
            rows = r
        if err:
            results.append((label, "ERROR", 0, err))
            continue
        best = min(times)
        avg = sum(times) / len(times)
        total_ms += avg
        results.append((label, rows, best, avg))

    print(f"  {'Query':<55} {'Rows':>5}  {'Best':>7}  {'Avg':>7}")
    print("-" * 82)
    for label, rows, best, avg in results:
        if isinstance(rows, str):
            print(f"  {label:<55} {rows}")
            continue
        print(f"  {label:<55} {rows:>5}  {best:>6.1f}ms  {avg:>6.1f}ms")

    print("-" * 82)
    print(f"  {'TOTAL':<55} {'':>5}  {'':>7}  {total_ms:>6.1f}ms")
    print()

    # Categorize by speed
    fast = [(l, r, b, a) for l, r, b, a in results if isinstance(r, int) and a < 1]
    medium = [(l, r, b, a) for l, r, b, a in results if isinstance(r, int) and 1 <= a < 5]
    slow = [(l, r, b, a) for l, r, b, a in results if isinstance(r, int) and a >= 5]

    print(f"  < 1ms:  {len(fast)} queries (instant)")
    print(f"  1-5ms:  {len(medium)} queries (fast)")
    print(f"  > 5ms:  {len(slow)} queries (needs optimization)")
    print()

    # Compare to CSV approach
    print("─" * 75)
    print("  COMPARISON: SQLite API vs CSV file read")
    print("─" * 75)

    # Time a CSV read via file API
    csv_start = time.perf_counter()
    for _ in range(10):
        req = urllib.request.Request("http://localhost:3210/api/file?path=output/database.csv")
        resp = urllib.request.urlopen(req)
        _ = json.loads(resp.read())
    csv_ms = (time.perf_counter() - csv_start) / 10 * 1000

    # Time equivalent SQL query
    sql_times = []
    for _ in range(10):
        _, ms, _ = run_query("SELECT * FROM events")
        sql_times.append(ms)
    sql_ms = sum(sql_times) / len(sql_times)

    print(f"  CSV file read (all events): {csv_ms:.1f}ms")
    print(f"  SQL query (all events):     {sql_ms:.1f}ms")
    print(f"  SQL filtered (year > 1900): ", end="")
    _, filt_ms, _ = run_query("SELECT * FROM events WHERE year_ad > 1900")
    print(f"{filt_ms:.1f}ms")
    print()

    if sql_ms > 0:
        print(f"  Full read: SQL is {csv_ms/sql_ms:.1f}x {'faster' if sql_ms < csv_ms else 'slower'} than CSV")
    print(f"  Filtered queries: SQL returns only matching rows (no client-side filtering needed)")
    print()
    print("=" * 75)


if __name__ == "__main__":
    main()
