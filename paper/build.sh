#!/usr/bin/env bash
# Build the manuscript PDF.
# Requires a TeX Live installation with: pdflatex, bibtex, latexmk.
# Ubuntu install:
#   sudo apt-get install -y texlive-latex-recommended texlive-latex-extra \
#       texlive-fonts-recommended texlive-bibtex-extra texlive-science latexmk
set -euo pipefail
cd "$(dirname "$0")"

if command -v latexmk >/dev/null 2>&1; then
    latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
else
    echo "[build] latexmk not found, falling back to manual pdflatex/bibtex cycle"
    pdflatex -interaction=nonstopmode main.tex
    bibtex main || true
    pdflatex -interaction=nonstopmode main.tex
    pdflatex -interaction=nonstopmode main.tex
fi
echo "[build] done -> main.pdf"
