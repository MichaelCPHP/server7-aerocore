"""VisiData file browser plugin for Jubilee Lab.

Opens an index sheet listing all CSV files from data/ and output/.
Press Enter on any row to open that CSV.
Press 'b' from any sheet to return to the browser.

Usage: vd -p scripts/vd_browser.py
"""

import os
from pathlib import Path
from visidata import vd, Sheet, Column, ItemColumn

LAB_DIR = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))


class FileBrowserSheet(Sheet):
    rowtype = "files"
    columns = [
        ItemColumn("folder", 0, width=10),
        ItemColumn("filename", 1, width=30),
        ItemColumn("rows", 2, width=8, type=int),
        ItemColumn("size", 3, width=12),
    ]

    def iterload(self):
        for subdir in ["data", "output"]:
            dirpath = LAB_DIR / subdir
            if not dirpath.exists():
                continue
            for f in sorted(dirpath.glob("*.csv")):
                stat = f.stat()
                size_kb = f"{stat.st_size / 1024:.1f} KB"
                try:
                    lines = sum(1 for _ in open(f)) - 1
                except Exception:
                    lines = 0
                yield (subdir, f.name, lines, size_kb)

    def openRow(self, row):
        folder, filename = row[0], row[1]
        filepath = LAB_DIR / folder / filename
        return vd.openSource(filepath)


# Keybinding: press 'b' to jump back to browser from any sheet
Sheet.addCommand("b", "open-browser", "vd.push(FileBrowserSheet('File Browser'))")

# On load, push the browser as the start sheet
vd.push(FileBrowserSheet("File Browser"))
