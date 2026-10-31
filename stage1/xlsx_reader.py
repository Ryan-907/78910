"""
Paper III — Stage 1c: Minimal XLSX Reader

An .xlsx file is a zip of XML, so it can be read with the standard library alone.
This module exists so an annotator can do the human pass in Excel without the
project acquiring a spreadsheet dependency, and without a lossy manual re-export
step between annotating and scoring.

Deliberately minimal. It reads the first worksheet as rows of strings and nothing
else: no formulas (the cached value is used), no formatting, no dates, no multiple
sheets. That is all an annotation sheet needs, and a larger surface would be more
to get wrong.

Two details that matter for correctness:

* Shared strings. Excel stores most text once in `xl/sharedStrings.xml` and has
  cells reference it by index (`t="s"`). A reader that ignores this returns
  integers where the text should be.
* Sparse rows. Excel omits empty cells entirely rather than emitting a blank, and
  a row that ends early simply stops. Cell references (`A1`, `P42`) are therefore
  the only reliable way to know which column a value belongs to — position in the
  XML is not. Unfilled `true_class` cells are exactly the case this affects, so
  getting it wrong would silently shift every verdict one column left.

Exports
-------
read_rows(path)   -> list[list[str]]   every row, padded to the header width
read_dicts(path)  -> list[dict]        rows keyed by the header row
"""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_CELL_REF = re.compile(r"^([A-Z]+)(\d+)$")


def _col_index(ref: str) -> int:
    """'A' -> 0, 'B' -> 1, ... 'AA' -> 26."""
    m = _CELL_REF.match(ref)
    letters = m.group(1) if m else ref
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    try:
        raw = z.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    out: list[str] = []
    for si in ET.fromstring(raw).findall("m:si", NS):
        # Text may be split across several runs (<r><t>..</t></r>); join them all.
        # Walked explicitly rather than with iter(), so <rPh> phonetic hints --
        # which also contain <t> -- are not folded into the value.
        parts: list[str] = []
        for child in si:
            tag = child.tag.split("}")[-1]
            if tag == "t":
                parts.append(child.text or "")
            elif tag == "r":
                for sub in child:
                    if sub.tag.split("}")[-1] == "t":
                        parts.append(sub.text or "")
        out.append("".join(parts))
    return out


def _first_sheet_name(z: zipfile.ZipFile) -> str:
    names = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet")]
    if not names:
        raise ValueError("no worksheet found in workbook")
    # sheet1.xml, sheet2.xml … — take the lowest-numbered.
    def num(n: str) -> int:
        m = re.search(r"sheet(\d+)\.xml$", n)
        return int(m.group(1)) if m else 10**6
    return min(names, key=num)


def read_rows(path: str | Path) -> list[list[str]]:
    """Every row of the first worksheet, padded to the width of the header row."""
    path = Path(path)
    with zipfile.ZipFile(path) as z:
        shared = _shared_strings(z)
        root = ET.fromstring(z.read(_first_sheet_name(z)))

        rows: list[list[str]] = []
        for row in root.iter("{%s}row" % NS["m"]):
            cells: dict[int, str] = {}
            for c in row:
                if c.tag.split("}")[-1] != "c":
                    continue
                ref = c.get("r") or ""
                idx = _col_index(ref) if ref else len(cells)
                ctype = c.get("t")
                value = ""
                if ctype == "inlineStr":
                    value = "".join(
                        t.text or "" for t in c.iter("{%s}t" % NS["m"]))
                else:
                    v = c.find("m:v", NS)
                    if v is not None and v.text is not None:
                        if ctype == "s":          # shared-string index
                            try:
                                value = shared[int(v.text)]
                            except (ValueError, IndexError):
                                value = v.text
                        else:
                            value = v.text
                cells[idx] = value
            width = (max(cells) + 1) if cells else 0
            rows.append([cells.get(i, "") for i in range(width)])

    if not rows:
        return []
    header_width = len(rows[0])
    return [r + [""] * (header_width - len(r)) if len(r) < header_width else r
            for r in rows]


def read_dicts(path: str | Path) -> list[dict]:
    """Rows keyed by the header row, mirroring csv.DictReader."""
    rows = read_rows(path)
    if not rows:
        return []
    header = [h.strip().lstrip("﻿") for h in rows[0]]
    return [dict(zip(header, r)) for r in rows[1:]]


if __name__ == "__main__":
    import sys
    from collections import Counter

    src = sys.argv[1]
    rows = read_dicts(src)
    print(f"{src}: {len(rows)} data rows, {len(rows[0]) if rows else 0} columns")
    if rows:
        print("columns:", ", ".join(rows[0].keys()))
        filled = sum(1 for r in rows if (r.get("true_class") or "").strip())
        print(f"true_class filled: {filled}")
        print(Counter((r.get("true_class") or "(blank)").strip() for r in rows))
