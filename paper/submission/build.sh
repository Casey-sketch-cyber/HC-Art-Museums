#!/usr/bin/env bash
# Build pipeline for the Building Simulation submission.
# Run from /workspace/guangxi/paper/submission/.
set -euo pipefail
export PATH="$HOME/bin:$PATH"

cd "$(dirname "$0")"

echo "[0] Regenerating main_blinded.tex from main.tex (keeps them in sync)"
python3 make_blinded.py

echo "[1/5] Copying current references.bib"
cp ../references.bib references.bib

echo "[2/5] Resolving \\ref / \\eqref against main.aux"
python3 resolve_refs.py

echo "[3/5] Running pandoc (latex -> docx with reference template + citeproc)"
pandoc main_blinded_resolved.tex \
    --from=latex --to=docx \
    --reference-doc=ref_template.docx \
    --bibliography=references.bib \
    --citeproc \
    --csl=springer-basic-author-date.csl \
    --resource-path=.:figures \
    -o Blinded_Manuscript.docx

echo "[4/5] Post-processing (Algorithm 1 + B1..B5 labels)"
python3 post_process.py

echo "[5/5] Format fixes (numbering, captions, H4 demotion, References, Highlights removal)"
python3 format_fix.py

echo "[6/7] Restoring λ in Heading 4.2 / 6.5"
python3 - <<'PY'
import docx
d = docx.Document('Blinded_Manuscript.docx')
for p in d.paragraphs:
    if p.text.strip() == "4.2 Implementation pitfall: cross-process  propagation":
        for r in p.runs:
            r.text = r.text.replace("cross-process  propagation",
                                    "cross-process λ propagation")
    if p.text.strip() == "6.5 saturation":
        for r in p.runs:
            r.text = r.text.replace("6.5 saturation", "6.5 λ saturation")
d.save('Blinded_Manuscript.docx')
PY

echo "[7/8] Stripping auto-numbering from heading-1 style"
python3 strip_heading_autonumber.py

echo "[8/9] Applying three-line table borders"
python3 apply_table_borders.py

echo "[9/9] Numbering display equations"
python3 number_equations.py

echo
echo "[done] outputs:"
ls -la Blinded_Manuscript.docx Title_Page.docx 2>/dev/null || true
