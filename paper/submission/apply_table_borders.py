"""Apply the journal's three-line (booktabs-style) borders to all tables.

The Building Simulation template renders tables as three-line tables:
  - a top rule (above the header),
  - a mid rule (below the header row(s)),
  - a bottom rule (below the last data row),
  - no vertical lines and no lines between data rows.

Pandoc emits the LaTeX booktabs tables with the "Normal Table" style and no
borders at all, so we re-apply the three-line structure here. This mirrors the
explicit border scheme used by the template's own example table
(style "Table Grid"; table-level left/right/insideV = none; a single sz=8
rule below the header).

Header-row counts differ per table and are detected from the first column:
  - the per-zone envelope table has TWO header rows (labels + units);
  - the two result tables have ONE header row.
The headline result table also carries an internal "Pareto sweep" divider,
which receives its own top rule.
"""
import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

DOC = "Blinded_Manuscript.docx"

RULE_SZ = "8"   # eighths of a point -> 1.0 pt, matching the template


def _set(el, tag, **attrs):
    child = el.find(qn(f"w:{tag}"))
    if child is None:
        child = OxmlElement(f"w:{tag}")
        el.append(child)
    for k, v in attrs.items():
        child.set(qn(f"w:{k}"), v)
    return child


def table_level_borders(table):
    """Top + bottom single rules; no verticals, no inter-row horizontals."""
    tblPr = table._tbl.tblPr
    # remove any existing tblBorders
    old = tblPr.find(qn("w:tblBorders"))
    if old is not None:
        tblPr.remove(old)
    b = OxmlElement("w:tblBorders")
    tblPr.append(b)
    _set(b, "top",     val="single", sz=RULE_SZ, space="0", color="auto")
    _set(b, "bottom",  val="single", sz=RULE_SZ, space="0", color="auto")
    _set(b, "left",    val="none",   sz="0", space="0", color="auto")
    _set(b, "right",   val="none",   sz="0", space="0", color="auto")
    _set(b, "insideV", val="none",   sz="0", space="0", color="auto")
    _set(b, "insideH", val="none",   sz="0", space="0", color="auto")


def set_row_border(row, edge):
    """Set a single rule on the given edge ('bottom'/'top') of every cell."""
    for cell in row.cells:
        tcPr = cell._tc.get_or_add_tcPr()
        borders = tcPr.find(qn("w:tcBorders"))
        if borders is None:
            borders = OxmlElement("w:tcBorders")
            tcPr.append(borders)
        _set(borders, edge, val="single", sz=RULE_SZ, space="0", color="auto")


def apply_three_line(table, header_rows):
    table.style = "Table Grid"
    table_level_borders(table)
    # mid rule = bottom border on the last header row
    if header_rows >= 1 and len(table.rows) > header_rows:
        set_row_border(table.rows[header_rows - 1], "bottom")


def main():
    doc = docx.Document(DOC)
    for t in doc.tables:
        first = t.rows[0].cells[0].text.strip().lower() if t.rows else ""
        # envelope table has a 2-row header (labels + units)
        header_rows = 2 if first.startswith("zone") else 1
        apply_three_line(t, header_rows)

        # Headline result table: add a top rule above the "Pareto sweep" divider.
        for r in t.rows:
            if r.cells[0].text.strip().lower().startswith("pareto sweep"):
                set_row_border(r, "top")
                break

    doc.save(DOC)
    print(f"[fix] applied three-line borders to {len(doc.tables)} tables")


if __name__ == "__main__":
    main()
