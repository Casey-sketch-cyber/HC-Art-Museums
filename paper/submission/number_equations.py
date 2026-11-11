"""Add right-aligned equation numbers (1)..(N) to display equations.

Pandoc converts LaTeX display equations to Word OMML but drops the equation
numbers. The journal requires every equation to be numbered, and the body
text already references "Eq. (1)..(12)". This post-processor numbers each
display-equation paragraph in document order using the standard Word layout:
a centre tab (equation) + a right tab (number), so the equation stays centred
and the number sits at the right margin.

Assumes the align block has been split into separate equation environments in
the LaTeX source, so each numbered equation is its own <m:oMathPara> block and
document order == equation number.
"""
import re
import shutil
import zipfile
from pathlib import Path

DOC = Path("Blinded_Manuscript.docx")

# Text width from sectPr: pgSz w=11907, left=right=1077 -> 9753 twips.
CENTER_POS = "4876"
RIGHT_POS = "9753"


def number_equations(doc_path: Path) -> None:
    with zipfile.ZipFile(doc_path) as zin:
        xml = zin.read("word/document.xml").decode("utf-8")
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}

    # Split document into paragraphs, transforming each that holds an oMathPara.
    counter = {"n": 0}

    def repl(match):
        para = match.group(0)
        if "<m:oMathPara>" not in para:
            return para
        counter["n"] += 1
        n = counter["n"]
        # Extract the inner <m:oMath>...</m:oMath>.
        mo = re.search(r"<m:oMath>.*?</m:oMath>", para, re.DOTALL)
        if not mo:
            return para
        omath = mo.group(0)
        # Preserve an existing pStyle if present.
        ps = re.search(r"<w:pStyle[^/]*/>", para)
        pstyle = ps.group(0) if ps else ""
        tabs = (f'<w:tabs><w:tab w:val="center" w:pos="{CENTER_POS}"/>'
                f'<w:tab w:val="right" w:pos="{RIGHT_POS}"/></w:tabs>')
        new_para = (
            "<w:p><w:pPr>" + pstyle + tabs + "</w:pPr>"
            "<w:r><w:tab/></w:r>"
            + omath +
            "<w:r><w:tab/></w:r>"
            f"<w:r><w:t>({n})</w:t></w:r>"
            "</w:p>"
        )
        return new_para

    new_xml = re.sub(r"<w:p\b[^>]*>.*?</w:p>", repl, xml, flags=re.DOTALL)

    data["word/document.xml"] = new_xml.encode("utf-8")
    tmp = doc_path.with_suffix(".tmp.docx")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(n, data[n])
    shutil.move(tmp, doc_path)
    print(f"[fix] numbered {counter['n']} display equations")


if __name__ == "__main__":
    number_equations(DOC)
