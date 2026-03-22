#!/usr/bin/env python3
"""Database manager for the Lab Database pane.

Provides CRUD operations on SQLite databases via CLI commands.
Called by server.js for all database pane interactions.

Usage:
    python3 database_manager.py <db_path> <command> [args...]

Commands:
    list                          - List all tables with row counts and columns
    get <table> [limit] [offset]  - Get table data with pagination
    create <table> <col1> <col2>  - Create a new table with columns
    drop <table>                  - Drop a table
    update <table> <rowid> <col> <val> - Update a cell
    add-row <table>               - Add an empty row
    delete-row <table> <rowid>    - Delete a row
    add-col <table> <column>      - Add a column
    import <xlsx_or_csv_path>     - Import XLSX or CSV file
    query                         - Execute a SELECT query (read from stdin)
    export <table>                - Export table as CSV
    create-db                     - Create an empty database file
    import-csv <table> <csv_path> - Import CSV into a specific table
"""

import csv
import json
import os
import sqlite3
import sys
from pathlib import Path


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def list_tables(db_path):
    conn = connect(db_path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != '_meta' ORDER BY name"
    ).fetchall()
    result = []
    for (name,) in tables:
        row_count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        cols = conn.execute(f'PRAGMA table_info("{name}")').fetchall()
        result.append({
            "name": name,
            "rowCount": row_count,
            "columnCount": len(cols),
            "columns": [{"name": c[1], "type": c[2]} for c in cols],
        })
    conn.close()
    return result


def get_table(db_path, table, limit=500, offset=0):
    conn = connect(db_path)
    conn.row_factory = sqlite3.Row

    # Get column info
    cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    columns = [{"name": c[1], "type": c[2]} for c in cols]

    # Get total count
    total = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]

    # Get rows with rowid
    rows = conn.execute(
        f'SELECT rowid, * FROM "{table}" LIMIT ? OFFSET ?', (int(limit), int(offset))
    ).fetchall()

    data = []
    for row in rows:
        d = {"_rowid": row[0]}
        for i, col in enumerate(columns):
            d[col["name"]] = row[i + 1]
        data.append(d)

    conn.close()
    headers = [c["name"] for c in columns]
    return {"table": table, "columns": columns, "headers": headers, "rows": data, "total": total, "limit": int(limit), "offset": int(offset)}


def create_table(db_path, table, columns):
    conn = connect(db_path)
    col_defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
    for col in columns:
        clean = col.strip('"').strip("'")
        col_defs.append(f'"{clean}" TEXT')
    conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({", ".join(col_defs)})')
    conn.commit()
    conn.close()
    return {"success": True, "table": table, "columns": columns}


def drop_table(db_path, table):
    conn = connect(db_path)
    conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    conn.commit()
    conn.close()
    return {"success": True, "dropped": table}


def update_cell(db_path, table, rowid, column, value):
    conn = connect(db_path)
    conn.execute(f'UPDATE "{table}" SET "{column}" = ? WHERE rowid = ?', (value, int(rowid)))
    conn.commit()
    conn.close()
    return {"success": True}


def add_row(db_path, table):
    conn = connect(db_path)
    cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    non_id_cols = [c for c in cols if c[1].lower() != "id"]
    if non_id_cols:
        col_names = ", ".join([f'"{c[1]}"' for c in non_id_cols])
        placeholders = ", ".join(["NULL"] * len(non_id_cols))
        conn.execute(f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})')
    else:
        conn.execute(f'INSERT INTO "{table}" DEFAULT VALUES')
    conn.commit()
    rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return {"success": True, "rowid": rowid}


def delete_row(db_path, table, rowid):
    conn = connect(db_path)
    conn.execute(f'DELETE FROM "{table}" WHERE rowid = ?', (int(rowid),))
    conn.commit()
    conn.close()
    return {"success": True}


def add_column(db_path, table, column):
    conn = connect(db_path)
    conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" TEXT')
    conn.commit()
    conn.close()
    return {"success": True, "column": column}


def run_query(db_path, sql):
    conn = connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(sql)
    rows = cursor.fetchall()
    if not rows:
        conn.close()
        return {"columns": [], "rows": [], "count": 0}
    columns = list(rows[0].keys())
    data = [dict(row) for row in rows]
    conn.close()
    return {"columns": columns, "rows": data, "count": len(data)}


def export_table(db_path, table):
    conn = connect(db_path)
    conn.row_factory = sqlite3.Row
    cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    col_names = [c[1] for c in cols]
    rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
    conn.close()

    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(col_names)
    for row in rows:
        writer.writerow([row[c] for c in col_names])
    return output.getvalue()


def import_xlsx(db_path, xlsx_path):
    """Import XLSX file — delegates to xlsx_reader.py if available."""
    script_dir = Path(__file__).parent
    xlsx_reader = script_dir / "xlsx_reader.py"
    if xlsx_reader.exists():
        import subprocess
        result = subprocess.run(
            ["python3", str(xlsx_reader), xlsx_path, db_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return {"success": True, "message": result.stdout.strip()}
        return {"error": result.stderr.strip()}
    return {"error": "xlsx_reader.py not found"}


def import_csv_file(db_path, table, csv_path):
    """Import a CSV file into a specific table."""
    conn = connect(db_path)

    with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        if not headers:
            conn.close()
            return {"error": "CSV has no headers"}

        # Clean column names
        clean_headers = [h.strip().replace(" ", "_").replace("-", "_") for h in headers]

        # Create table — use existing 'id' column as primary key if present
        has_id = "id" in clean_headers
        col_defs = []
        if not has_id:
            col_defs.append("id INTEGER PRIMARY KEY AUTOINCREMENT")
        for ch in clean_headers:
            if ch == "id":
                col_defs.append('"id" TEXT PRIMARY KEY')
            else:
                col_defs.append(f'"{ch}" TEXT')
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        conn.execute(f'CREATE TABLE "{table}" ({", ".join(col_defs)})')

        # Insert rows in batches
        placeholders = ", ".join(["?"] * len(clean_headers))
        col_names = ", ".join([f'"{h}"' for h in clean_headers])
        sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})'

        batch = []
        total = 0
        for row in reader:
            values = [row.get(h, "") or None for h in headers]
            batch.append(values)
            if len(batch) >= 5000:
                conn.executemany(sql, batch)
                total += len(batch)
                batch = []
        if batch:
            conn.executemany(sql, batch)
            total += len(batch)

        conn.commit()

    # Create indexes on common filter columns
    index_candidates = ["segment", "source", "stage_id", "location", "county", "city", "company", "phone", "email"]
    actual_cols = {h for h in clean_headers}
    for col in index_candidates:
        if col in actual_cols:
            try:
                conn.execute(f'CREATE INDEX IF NOT EXISTS "idx_{table}_{col}" ON "{table}"("{col}")')
            except sqlite3.Error:
                pass
    conn.commit()
    conn.close()
    return {"success": True, "table": table, "rows": total, "columns": len(clean_headers)}


def insert_row(db_path, table, data):
    """Insert a row with data (dict)."""
    conn = connect(db_path)
    cols = [k for k in data.keys()]
    vals = [data[k] for k in cols]
    col_names = ", ".join([f'"{c}"' for c in cols])
    placeholders = ", ".join(["?"] * len(cols))
    conn.execute(f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})', vals)
    conn.commit()
    rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return {"success": True, "rowid": rowid}


def update_row(db_path, table, row_id, data):
    """Update multiple columns in a row by primary key."""
    conn = connect(db_path)
    sets = ", ".join([f'"{k}" = ?' for k in data.keys()])
    vals = list(data.values()) + [row_id]
    conn.execute(f'UPDATE "{table}" SET {sets} WHERE id = ?', vals)
    conn.commit()
    conn.close()
    return {"success": True}


def delete_by_id(db_path, table, row_id):
    """Delete a row by primary key id."""
    conn = connect(db_path)
    conn.execute(f'DELETE FROM "{table}" WHERE id = ?', (row_id,))
    conn.commit()
    conn.close()
    return {"success": True}


def create_empty_db(db_path):
    """Create an empty database file."""
    conn = connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR REPLACE INTO _meta VALUES ('created', datetime('now'))")
    conn.commit()
    conn.close()
    return {"success": True, "path": db_path}


def import_file(db_path, file_path):
    """Import a file (CSV or XLSX) into the database."""
    ext = Path(file_path).suffix.lower()
    if ext == ".csv":
        table = Path(file_path).stem.replace("-", "_").replace(" ", "_")
        return import_csv_file(db_path, table, file_path)
    elif ext in (".xlsx", ".xls"):
        return import_xlsx(db_path, file_path)
    else:
        return {"error": f"Unsupported file type: {ext}"}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: database_manager.py <db_path> <command> [args...]"}))
        sys.exit(1)

    db_path = sys.argv[1]
    command = sys.argv[2]

    try:
        if command == "list":
            result = list_tables(db_path)
        elif command == "get":
            table = sys.argv[3]
            limit = sys.argv[4] if len(sys.argv) > 4 else 500
            offset = sys.argv[5] if len(sys.argv) > 5 else 0
            result = get_table(db_path, table, limit, offset)
        elif command == "create":
            table = sys.argv[3]
            columns = sys.argv[4:]
            result = create_table(db_path, table, columns)
        elif command == "drop":
            table = sys.argv[3]
            result = drop_table(db_path, table)
        elif command == "update":
            table = sys.argv[3]
            rowid = sys.argv[4]
            column = sys.argv[5]
            value = sys.argv[6] if len(sys.argv) > 6 else ""
            result = update_cell(db_path, table, rowid, column, value)
        elif command == "add-row":
            table = sys.argv[3]
            result = add_row(db_path, table)
        elif command == "delete-row":
            table = sys.argv[3]
            rowid = sys.argv[4]
            result = delete_row(db_path, table, rowid)
        elif command == "add-col":
            table = sys.argv[3]
            column = sys.argv[4]
            result = add_column(db_path, table, column)
        elif command == "query":
            sql = sys.stdin.read().strip()
            result = run_query(db_path, sql)
        elif command == "export":
            table = sys.argv[3]
            # Export returns raw CSV, not JSON
            print(export_table(db_path, table), end="")
            sys.exit(0)
        elif command == "create-db":
            result = create_empty_db(db_path)
        elif command == "import":
            file_path = sys.argv[3]
            result = import_file(db_path, file_path)
        elif command == "import-csv":
            table = sys.argv[3]
            csv_path = sys.argv[4]
            result = import_csv_file(db_path, table, csv_path)
        elif command == "insert":
            table = sys.argv[3]
            data = json.loads(sys.stdin.read().strip())
            result = insert_row(db_path, table, data)
        elif command == "update-row":
            table = sys.argv[3]
            row_id = sys.argv[4]
            data = json.loads(sys.stdin.read().strip())
            result = update_row(db_path, table, row_id, data)
        elif command == "delete-by-id":
            table = sys.argv[3]
            row_id = sys.argv[4]
            result = delete_by_id(db_path, table, row_id)
        else:
            result = {"error": f"Unknown command: {command}"}

        print(json.dumps(result))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
