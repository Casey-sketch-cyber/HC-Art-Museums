"""Remove automatic Word list-numbering from the heading-1 style.

The Building Simulation reference template's "heading 1" style (styleId "1")
carries a <w:numPr><w:numId w:val="2"/></w:numPr>, which makes Word prepend an
automatic counter (2, 3, 4, ...). Because we already place the section number
as literal text ("1 Introduction"), the two stack into "2  1 Introduction".

Stripping the numPr from the style definition leaves only our manual numbers.
This operates directly on the zipped styles.xml so it can run after pandoc on
every rebuild.
"""
import re
import shutil
import zipfile
from pathlib import Path

DOC = Path("Blinded_Manuscript.docx")


def strip(doc_path: Path) -> None:
    tmp = doc_path.with_suffix(".tmp.docx")
    with zipfile.ZipFile(doc_path) as zin:
        styles = zin.read("word/styles.xml").decode("utf-8")

        # Remove the numPr block from the heading-1 style only (styleId="1").
        m = re.search(r'<w:style [^>]*w:styleId="1"[ >].*?</w:style>',
                      styles, re.DOTALL)
        if not m:
            print("[warn] heading-1 style not found; no change")
            return
        block = m.group(0)
        new_block, n = re.subn(r'<w:numPr>.*?</w:numPr>', '', block,
                               flags=re.DOTALL)
        if n == 0:
            print("[ok] heading-1 already has no auto-numbering")
            return
        styles = styles.replace(block, new_block)

        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = (styles.encode("utf-8")
                        if item.filename == "word/styles.xml"
                        else zin.read(item.filename))
                zout.writestr(item, data)
    shutil.move(tmp, doc_path)
    print(f"[fix] removed auto-numbering from heading-1 style ({n} numPr block)")


if __name__ == "__main__":
    strip(DOC)
