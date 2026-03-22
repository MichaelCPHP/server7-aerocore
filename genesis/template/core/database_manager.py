#!/usr/bin/env python3
"""SQLite database operations — import xlsx, read/write tables.

Usage:
    python3 database_manager.py <db_path> list
    python3 database_manager.py <db_path> get <table> [limit] [offset]
    python3 database_manager.py <db_path> update <table> <row_id> <column> <value>
    python3 database_manager.py <db_path> create <table> <col1> <col2> ...
    python3 database_manager.py <db_path> drop <table>
    python3 database_manager.py <db_path> import <xlsx_path>
    python3 database_manager.py <db_path> add-row <table>
    python3 database_manager.py <db_path> delete-row <table> <row_id>
    python3 database_manager.py <db_path> add-col <table> <col_name>
    python3 database_manager.py <db_path> query <SELECT ...>
    python3 database_manager.py <db_path> export <table>

All output is JSON to stdout (except export, which outputs CSV).
"""
import json, os, re, sqlite3, sys, zipfile, xml.etree.ElementTree as ET


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def list_tables(db_path):
    conn = connect(db_path)
    tables = []
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') "
        "AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall():
        kind = conn.execute(
            "SELECT type FROM sqlite_master WHERE name=?", (name,)
        ).fetchone()[0]
        cols = conn.execute(f'PRAGMA table_info("{name}")').fetchall()
        row_count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        tables.append({
            'name': name,
            'type': kind,
            'columns': [{'name': c[1], 'type': c[2]} for c in cols],
            'columnCount': len(cols),
            'rowCount': row_count,
        })
    conn.close()
    return tables


def get_table(db_path, table_name, limit=500, offset=0):
    conn = connect(db_path)
    # Validate table exists
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name=? AND type IN ('table','view')", (table_name,)
    ).fetchone()
    if not exists:
        conn.close()
        return {'error': f'Table not found: {table_name}'}

    is_view = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name=? AND type='view'", (table_name,)
    ).fetchone() is not None

    cols = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    headers = [c[1] for c in cols]
    col_types = [c[2] for c in cols]
    total = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]

    if is_view:
        rows = conn.execute(
            f'SELECT * FROM "{table_name}" LIMIT ? OFFSET ?', (limit, offset)
        ).fetchall()
        data = []
        for i, row in enumerate(rows):
            row_dict = {'_rowid': offset + i + 1}  # synthetic rowid, view is read-only
            for j, h in enumerate(headers):
                row_dict[h] = row[j]
            data.append(row_dict)
    else:
        rows = conn.execute(
            f'SELECT rowid, * FROM "{table_name}" LIMIT ? OFFSET ?', (limit, offset)
        ).fetchall()
        data = []
        for row in rows:
            row_dict = {'_rowid': row[0]}
            for i, h in enumerate(headers):
                row_dict[h] = row[i + 1]
            data.append(row_dict)

    conn.close()
    return {
        'name': table_name,
        'headers': headers,
        'columnTypes': col_types,
        'rows': data,
        'totalRows': total,
        'limit': limit,
        'offset': offset,
    }


def update_cell(db_path, table_name, row_id, column, value):
    conn = connect(db_path)
    # Check if it's a view
    kind = conn.execute(
        "SELECT type FROM sqlite_master WHERE name=?", (table_name,)
    ).fetchone()
    if not kind:
        conn.close()
        return {'error': f'Table not found: {table_name}'}
    if kind[0] == 'view':
        conn.close()
        return {'error': 'Cannot edit a view — it is a computed sheet'}

    # Validate column exists
    cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()]
    if column not in cols:
        conn.close()
        return {'error': f'Column not found: {column}'}

    # Try numeric conversion
    try:
        if value and '.' in str(value):
            value = float(value)
        elif value and str(value).lstrip('-').isdigit():
            value = int(value)
    except (ValueError, TypeError):
        pass

    conn.execute(f'UPDATE "{table_name}" SET "{column}" = ? WHERE rowid = ?', (value, row_id))
    conn.commit()
    conn.close()
    return {'ok': True, 'table': table_name, 'rowid': row_id, 'column': column, 'value': value}


def create_table(db_path, table_name, columns):
    conn = connect(db_path)
    # Sanitize table name
    safe_name = re.sub(r'[^\w\s-]', '', table_name).strip().replace(' ', '_')
    if not safe_name:
        conn.close()
        return {'error': 'Invalid table name'}

    col_defs = ['id INTEGER PRIMARY KEY AUTOINCREMENT']
    for col in columns:
        safe_col = re.sub(r'[^\w\s-]', '', col).strip().replace(' ', '_')
        if safe_col and safe_col.lower() != 'id':
            col_defs.append(f'"{safe_col}" TEXT')

    conn.execute(f'CREATE TABLE IF NOT EXISTS "{safe_name}" ({", ".join(col_defs)})')
    conn.commit()
    conn.close()
    return {'ok': True, 'table': safe_name, 'columns': len(col_defs)}


def drop_table(db_path, table_name):
    conn = connect(db_path)
    kind = conn.execute(
        "SELECT type FROM sqlite_master WHERE name=?", (table_name,)
    ).fetchone()
    if not kind:
        conn.close()
        return {'error': f'Table not found: {table_name}'}

    if kind[0] == 'view':
        conn.execute(f'DROP VIEW IF EXISTS "{table_name}"')
    else:
        conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    conn.commit()
    conn.close()
    return {'ok': True, 'dropped': table_name}


def add_row(db_path, table_name):
    conn = connect(db_path)
    kind = conn.execute(
        "SELECT type FROM sqlite_master WHERE name=?", (table_name,)
    ).fetchone()
    if not kind or kind[0] == 'view':
        conn.close()
        return {'error': 'Cannot add rows to a view'}

    cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall() if c[1] != 'id']
    if not cols:
        conn.close()
        return {'error': 'Table has no columns'}

    placeholders = ', '.join(['NULL'] * len(cols))
    col_names = ', '.join([f'"{c}"' for c in cols])
    cursor = conn.execute(f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})')
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return {'ok': True, 'table': table_name, 'rowid': row_id}


def delete_row(db_path, table_name, row_id):
    conn = connect(db_path)
    conn.execute(f'DELETE FROM "{table_name}" WHERE rowid = ?', (row_id,))
    conn.commit()
    conn.close()
    return {'ok': True, 'table': table_name, 'deleted': row_id}


def add_column(db_path, table_name, col_name):
    conn = connect(db_path)
    safe_col = re.sub(r'[^\w\s-]', '', col_name).strip().replace(' ', '_')
    if not safe_col:
        conn.close()
        return {'error': 'Invalid column name'}
    conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{safe_col}" TEXT')
    conn.commit()
    conn.close()
    return {'ok': True, 'table': table_name, 'column': safe_col}


# ── xlsx import ──────────────────────────────────────────────────────────────

def col_to_num(col):
    n = 0
    for c in col:
        n = n * 26 + (ord(c.upper()) - 64)
    return n - 1


def num_to_col(n):
    s = ''
    while n >= 0:
        s = chr(65 + n % 26) + s
        n = n // 26 - 1
    return s


def import_xlsx(xlsx_path, db_path):
    z = zipfile.ZipFile(xlsx_path)

    def ns(tag):
        m = re.match(r'\{(.+?)\}', tag)
        return m.group(1) if m else ''

    # Sheet names
    wb = ET.parse(z.open('xl/workbook.xml')).getroot()
    wns = ns(wb.tag)
    sheet_names = [s.get('name') for s in wb.findall(f'{{{wns}}}sheets/{{{wns}}}sheet')]

    # Shared strings
    ss = []
    try:
        ss_xml = ET.parse(z.open('xl/sharedStrings.xml')).getroot()
        sns = ns(ss_xml.tag)
        for si in ss_xml.findall(f'{{{sns}}}si'):
            texts = si.findall(f'.//{{{sns}}}t')
            ss.append(''.join(t.text or '' for t in texts))
    except (KeyError, ET.ParseError):
        pass

    # Relationships
    rels = {}
    try:
        rels_xml = ET.parse(z.open('xl/_rels/workbook.xml.rels')).getroot()
        for rel in rels_xml:
            rid = rel.get('Id', '')
            target = rel.get('Target', '')
            if 'worksheet' in target.lower():
                rels[rid] = 'xl/' + target if not target.startswith('/') else target.lstrip('/')
    except (KeyError, ET.ParseError):
        pass

    # Get rIds
    ns_rels = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    sheet_rids = []
    for s in wb.findall(f'{{{wns}}}sheets/{{{wns}}}sheet'):
        rid = ''
        for attr_name, attr_val in s.attrib.items():
            if attr_name.endswith('}id') or attr_name == 'r:id':
                rid = attr_val
                break
        sheet_rids.append(rid)

    conn = connect(db_path)
    imported = []

    for i, sheet_name in enumerate(sheet_names):
        safe_name = re.sub(r'[^\w\s-]', '', sheet_name).strip().replace(' ', '_')
        if not safe_name:
            safe_name = f'Sheet_{i+1}'

        try:
            # Find sheet file
            sheet_file = None
            if i < len(sheet_rids) and sheet_rids[i] in rels:
                sheet_file = rels[sheet_rids[i]]
            if not sheet_file:
                for candidate in [f'xl/worksheets/sheet{i+1}.xml']:
                    if candidate in z.namelist():
                        sheet_file = candidate
                        break
            if not sheet_file:
                continue

            ws = ET.parse(z.open(sheet_file)).getroot()
            wns2 = ns(ws.tag)
            rows_data = []
            max_col = 0

            for row in ws.findall(f'.//{{{wns2}}}row'):
                cells = {}
                for cell in row.findall(f'{{{wns2}}}c'):
                    ref = cell.get('r', '')
                    col_letter = re.sub(r'[0-9]', '', ref)
                    col_idx = col_to_num(col_letter)
                    if col_idx > max_col:
                        max_col = col_idx

                    val_el = cell.find(f'{{{wns2}}}v')
                    val = val_el.text if val_el is not None else ''
                    cell_type = cell.get('t', '')
                    if cell_type == 's' and val:
                        idx = int(val)
                        val = ss[idx] if idx < len(ss) else val
                    elif cell_type == 'inlineStr':
                        is_el = cell.find(f'.//{{{wns2}}}t')
                        val = is_el.text if is_el is not None else ''
                    cells[col_idx] = val or ''

                if cells:
                    rows_data.append(cells)

            if not rows_data:
                continue

            # Detect headers from first row
            all_cols = list(range(max_col + 1))
            first_row = rows_data[0]
            headers = []
            for c in all_cols:
                val = first_row.get(c, '').strip()
                if val:
                    headers.append(re.sub(r'[^\w\s-]', '', val).strip().replace(' ', '_') or f'col_{num_to_col(c)}')
                else:
                    headers.append(f'col_{num_to_col(c)}')

            # Deduplicate headers
            seen = {}
            unique_headers = []
            for h in headers:
                if h in seen:
                    seen[h] += 1
                    unique_headers.append(f'{h}_{seen[h]}')
                else:
                    seen[h] = 0
                    unique_headers.append(h)

            # Create table
            conn.execute(f'DROP TABLE IF EXISTS "{safe_name}"')
            col_defs = 'id INTEGER PRIMARY KEY AUTOINCREMENT, ' + ', '.join(
                [f'"{h}" TEXT' for h in unique_headers]
            )
            conn.execute(f'CREATE TABLE "{safe_name}" ({col_defs})')

            # Insert data rows (skip header row)
            data_rows = rows_data[1:]
            if data_rows:
                placeholders = ', '.join(['?'] * len(unique_headers))
                col_names = ', '.join([f'"{h}"' for h in unique_headers])
                batch = []
                for r in data_rows:
                    vals = [r.get(c, '') for c in all_cols]
                    batch.append(vals)
                conn.executemany(
                    f'INSERT INTO "{safe_name}" ({col_names}) VALUES ({placeholders})',
                    batch
                )

            imported.append({
                'name': safe_name,
                'originalName': sheet_name,
                'columns': len(unique_headers),
                'rows': len(data_rows),
            })

        except Exception as e:
            imported.append({
                'name': safe_name,
                'originalName': sheet_name,
                'error': str(e),
            })

    conn.commit()
    conn.close()
    return {'ok': True, 'tables': imported, 'total': len(imported)}


# ── CSV export ───────────────────────────────────────────────────────────────

def export_csv(db_path, table_name):
    import csv, io
    conn = connect(db_path)
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name=? AND type IN ('table','view')", (table_name,)
    ).fetchone()
    if not exists:
        conn.close()
        return None  # caller handles error
    cols = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    headers = [c[1] for c in cols]
    rows = conn.execute(f'SELECT * FROM "{table_name}"').fetchall()
    conn.close()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(headers)
    writer.writerows(rows)
    return out.getvalue()


# ── SQL query (read-only) ────────────────────────────────────────────────────

def run_query(db_path, sql):
    # Only allow SELECT statements
    stripped = sql.strip().rstrip(';').strip()
    first_word = stripped.split()[0].upper() if stripped.split() else ''
    if first_word != 'SELECT':
        return {'error': f'Only SELECT queries are allowed (got {first_word})'}
    conn = connect(db_path)
    try:
        cursor = conn.execute(stripped)
        headers = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        data = []
        for row in rows:
            row_dict = {}
            for i, h in enumerate(headers):
                row_dict[h] = row[i]
            data.append(row_dict)
        return {'headers': headers, 'rows': data, 'totalRows': len(data)}
    except Exception as e:
        return {'error': str(e)}
    finally:
        conn.close()


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    db = sys.argv[1]
    cmd = sys.argv[2]

    if cmd == 'list':
        result = list_tables(db)
    elif cmd == 'get':
        table = sys.argv[3] if len(sys.argv) > 3 else ''
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 500
        offset = int(sys.argv[5]) if len(sys.argv) > 5 else 0
        result = get_table(db, table, limit, offset)
    elif cmd == 'update':
        result = update_cell(db, sys.argv[3], int(sys.argv[4]), sys.argv[5], sys.argv[6])
    elif cmd == 'create':
        result = create_table(db, sys.argv[3], sys.argv[4:])
    elif cmd == 'drop':
        result = drop_table(db, sys.argv[3])
    elif cmd == 'import':
        result = import_xlsx(sys.argv[3], db)
    elif cmd == 'add-row':
        result = add_row(db, sys.argv[3])
    elif cmd == 'delete-row':
        result = delete_row(db, sys.argv[3], int(sys.argv[4]))
    elif cmd == 'add-col':
        result = add_column(db, sys.argv[3], sys.argv[4])
    elif cmd == 'query':
        # Read SQL from stdin to avoid shell injection
        sql = sys.stdin.read().strip() if len(sys.argv) <= 3 else ' '.join(sys.argv[3:])
        result = run_query(db, sql)
    elif cmd == 'export':
        csv_data = export_csv(db, sys.argv[3])
        if csv_data is None:
            result = {'error': f'Table not found: {sys.argv[3]}'}
        else:
            sys.stdout.write(csv_data)
            sys.exit(0)
    else:
        result = {'error': f'Unknown command: {cmd}'}

    json.dump(result, sys.stdout)
