#!/usr/bin/env python3
"""Read xlsx files using only Python standard library. Outputs JSON to stdout."""
import json, re, sys, zipfile, xml.etree.ElementTree as ET

def col_to_num(col):
    """Convert column letters to number: A=0, B=1, ..., Z=25, AA=26."""
    n = 0
    for c in col:
        n = n * 26 + (ord(c.upper()) - 64)
    return n - 1

def parse_xlsx(filepath, max_rows=500, max_sheets=20):
    z = zipfile.ZipFile(filepath)
    # Namespace helper
    def ns(tag):
        m = re.match(r'\{(.+?)\}', tag)
        return m.group(1) if m else ''

    # Sheet names from workbook.xml
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

    # Map rId to sheet file from relationships
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

    # Get rIds in order from workbook
    sheet_rids = []
    for s in wb.findall(f'{{{wns}}}sheets/{{{wns}}}sheet'):
        rid = s.get(f'{{{ns_rels}}}id') if (ns_rels := 'http://schemas.openxmlformats.org/officeDocument/2006/relationships') else ''
        if not rid:
            for attr_name, attr_val in s.attrib.items():
                if attr_name.endswith('}id') or attr_name == 'r:id':
                    rid = attr_val
                    break
        sheet_rids.append(rid)

    sheets = []
    for i, name in enumerate(sheet_names[:max_sheets]):
        try:
            # Try to find the right sheet file
            sheet_file = None
            if i < len(sheet_rids) and sheet_rids[i] in rels:
                sheet_file = rels[sheet_rids[i]]
            if not sheet_file:
                # Fallback: try sheet{i+1}.xml
                for candidate in [f'xl/worksheets/sheet{i+1}.xml', f'xl/worksheets/sheet{i}.xml']:
                    if candidate in z.namelist():
                        sheet_file = candidate
                        break
            if not sheet_file:
                sheets.append({'name': name, 'headers': [], 'rows': [], 'totalRows': 0})
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

            # Build column headers (A, B, C, ...)
            def num_to_col(n):
                s = ''
                while n >= 0:
                    s = chr(65 + n % 26) + s
                    n = n // 26 - 1
                return s

            all_cols = list(range(max_col + 1)) if rows_data else []
            col_names = [num_to_col(c) for c in all_cols]

            # Use first row as headers if it looks like headers
            use_first_as_header = False
            if rows_data:
                first = rows_data[0]
                vals = [first.get(c, '') for c in all_cols]
                if all(isinstance(v, str) and v and not v.replace('.', '').replace('-', '').isdigit() for v in vals if v):
                    use_first_as_header = True

            if use_first_as_header and rows_data:
                headers = [rows_data[0].get(c, f'Col{c}') for c in all_cols]
                data_rows = rows_data[1:max_rows + 1]
            else:
                headers = col_names
                data_rows = rows_data[:max_rows]

            rows_list = []
            for r in data_rows:
                row_dict = {}
                for c_idx, h in zip(all_cols, headers):
                    row_dict[h] = r.get(c_idx, '')
                rows_list.append(row_dict)

            sheets.append({
                'name': name,
                'headers': headers,
                'rows': rows_list,
                'totalRows': len(rows_data) - (1 if use_first_as_header else 0)
            })
        except Exception as e:
            sheets.append({'name': name, 'headers': [], 'rows': [], 'totalRows': 0, 'error': str(e)})

    json.dump({'sheets': sheets}, sys.stdout)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: xlsx_reader.py <file.xlsx>', file=sys.stderr)
        sys.exit(1)
    parse_xlsx(sys.argv[1])
