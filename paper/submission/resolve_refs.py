"""Pre-resolve LaTeX \\ref{} and \\eqref{} into hard-coded numbers using main.aux.

This is needed because pandoc without pandoc-crossref leaves them as
[eq:cmdp_constraint] placeholders.
"""
import re
import sys
from pathlib import Path

AUX = Path("../main.aux")
SRC = Path("main_blinded.tex")
OUT = Path("main_blinded_resolved.tex")

# Parse aux: \newlabel{KEY}{{NUMBER}{PAGE}{...}{...}{}}
labels = {}
for m in re.finditer(r"\\newlabel\{([^}]+)\}\{\{([^}]+)\}\{", AUX.read_text()):
    labels[m.group(1)] = m.group(2)

print(f"loaded {len(labels)} labels from main.aux")

src = SRC.read_text()


def eqref_sub(m):
    key = m.group(1)
    num = labels.get(key, key)
    return f"(\\textbf{{NOFMT}}{num}\\textbf{{NOFMT}})"  # placeholder, fix below


def ref_sub(m):
    key = m.group(1)
    return labels.get(key, key)


# \eqref{key} -> (N)
src = re.sub(r"\\eqref\{([^}]+)\}", lambda m: f"({labels.get(m.group(1), m.group(1))})", src)
# \ref{key} -> N (plain)
src = re.sub(r"\\ref\{([^}]+)\}", lambda m: labels.get(m.group(1), m.group(1)), src)

OUT.write_text(src)
print(f"wrote {OUT} ({len(src)} chars)")

# Sanity: any unresolved \ref left?
remaining = re.findall(r"\\(?:ref|eqref)\{[^}]+\}", src)
if remaining:
    print(f"WARNING: {len(remaining)} unresolved refs: {remaining[:5]}")
else:
    print("all refs resolved")
