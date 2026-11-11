"""Regenerate main_blinded.tex from main.tex with the blinding transforms.

Keeping main_blinded.tex hand-edited caused drift (deleted-preprint citations
lingered). This script derives the blinded source from main.tex每次, so the two
never diverge again. Transforms:
  1. drop \linenumbers
  2. remove the author/affiliation center block
  3. remove the Acknowledgments section (funding goes on the Title Page)
  4. point figures at the 600-dpi PNGs used for the Word build
"""
import re
from pathlib import Path

SRC = Path("../main.tex")
OUT = Path("main_blinded.tex")

s = SRC.read_text()

# 1. Drop the \linenumbers line.
s = re.sub(r'\n\\linenumbers[^\n]*\n', '\n', s)

# 2. Remove the author center block: the SECOND \begin{center}..\end{center}
#    (the first is the title). It starts after the title block's \vspace.
#    Match the center block whose body contains a "$^{...}$" author marker.
def drop_author_block(text):
    blocks = list(re.finditer(r'\\begin\{center\}.*?\\end\{center\}',
                              text, re.DOTALL))
    for b in blocks:
        if 'Corresponding author' in b.group(0) or 'School of' in b.group(0):
            start, end = b.span()
            # also swallow a preceding \vspace{...} and surrounding blank lines
            pre = re.search(r'\n\\vspace\{[^}]*\}\s*$', text[:start])
            if pre:
                start = pre.start()
            return text[:start] + '\n' + text[end:]
    return text
s = drop_author_block(s)

# 3. Remove the Acknowledgments section up to the next \section*.
s = re.sub(
    r'% =+ *ACKNOWLEDGMENTS.*?\n\\section\*\{Acknowledgments\}.*?(?=% =+ *DATA|\\section\*\{Code and data)',
    '% Acknowledgments removed for the blinded manuscript (placed on Title Page).\n\n',
    s, flags=re.DOTALL)

# 4. Figure paths -> PNG for the Word build.
for stem in ('fig1_hero', 'fig2_typical_week', 'fig3_training_curves'):
    s = s.replace(f'figures/{stem}.pdf', f'figures/{stem}.png')

# A blinding note instead of the line-number comment.
s = s.replace(
    '\\begin{document}\n',
    '\\begin{document}\n\n% Blinded manuscript: line numbers and author block '
    'removed (double-blind).\n', 1)

OUT.write_text(s)

# sanity
removed_ok = ('He Zhao' not in s and 'Guike' not in s
              and '\\linenumbers' not in s)
print(f"wrote {OUT}; author/ack/linenumbers removed: {removed_ok}")
for k in ('lagrangian_empirical_2025', 'schulman2017ppo',
          'constrained_heatpump_2024', 'iot_modular_heritage_2025'):
    print(f"  residual {k}: {s.count(k)}")
