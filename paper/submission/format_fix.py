"""Bring Blinded_Manuscript.docx into compliance with the Building Simulation
author template.

Issues addressed:
  1. Section headings lack the decimal numbering required by the template
     (e.g., "1 Introduction", "2.1 Museum HVAC ...").
  2. Heading-4 paragraphs (\\paragraph{} in LaTeX) violate the
     "no more than three heading levels" rule. They are demoted to bold
     inline lead-ins on the following body paragraph.
  3. Figure captions need a "Fig. N " prefix.
  4. Table captions need a "Table N " prefix.
  5. The References heading is currently styled Normal; promote to Heading 1.
  6. The Highlights section is not part of the Building Simulation template
     and is removed.
"""
import re
import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

DOC = "Blinded_Manuscript.docx"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Headings that should NOT be numbered.
UNNUMBERED = {
    "Abstract", "Highlights", "Code and data availability", "References",
}

# Heading-4 paragraphs are paragraph lead-ins; convert to inline bold on the
# next body paragraph. The trailing period is kept.
H4_TO_INLINE = True


def make_run(text, bold=False, italic=False, preserve_space=True):
    r = OxmlElement("w:r")
    if bold or italic:
        rpr = OxmlElement("w:rPr")
        if bold:
            rpr.append(OxmlElement("w:b"))
        if italic:
            rpr.append(OxmlElement("w:i"))
        r.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    if preserve_space:
        t.set(qn("xml:space"), "preserve")
    r.append(t)
    return r


def fix_references_heading(doc):
    """Ensure a Heading-1 'References' paragraph precedes the bibliography."""
    import re
    # 1. If a Normal-styled "References" paragraph exists, promote it.
    for p in doc.paragraphs:
        if p.text.strip() == "References" and (
            not p.style or not p.style.name.startswith("Heading")
        ):
            pelem = p._element
            ppr = pelem.find(qn("w:pPr"))
            if ppr is None:
                ppr = OxmlElement("w:pPr")
                pelem.insert(0, ppr)
            existing_pstyle = ppr.find(qn("w:pStyle"))
            if existing_pstyle is not None:
                ppr.remove(existing_pstyle)
            ps = OxmlElement("w:pStyle")
            ps.set(qn("w:val"), "Heading1")
            ppr.insert(0, ps)
            print("[fix] References heading promoted to Heading 1")
            return
    # 2. If already a Heading-1 'References' exists, nothing to do.
    for p in doc.paragraphs:
        if (p.text.strip() == "References"
                and p.style and p.style.name.startswith("Heading")):
            print("[fix] References heading already present")
            return
    # 3. Otherwise, insert one before the first bibliography entry.
    # Find an existing Heading-1 paragraph and clone its pPr so we inherit the
    # right style ID (the docx may not literally name it "Heading1").
    h1_template = None
    for p in doc.paragraphs:
        if p.style and p.style.name == "Heading 1":
            h1_template = p
            break
    first_ref = None
    paras = list(doc.paragraphs)
    for i, p in enumerate(paras):
        t = p.text.strip()
        if i < len(paras) // 2:
            continue
        if re.match(r"^[A-ZÀ-ſ][\w\-’\.]+\s+[A-Z][\w\-’\.]*[^()]*\(\d{4}", t):
            first_ref = p
            break
    if first_ref is None:
        print("[warn] References heading not found, no first reference detected")
        return
    new_p = OxmlElement("w:p")
    if h1_template is not None:
        # Clone pPr from a known-good Heading 1 paragraph.
        from copy import deepcopy
        existing_ppr = h1_template._element.find(qn("w:pPr"))
        if existing_ppr is not None:
            new_p.append(deepcopy(existing_ppr))
    else:
        ppr = OxmlElement("w:pPr")
        ps = OxmlElement("w:pStyle")
        ps.set(qn("w:val"), "Heading1")
        ppr.append(ps)
        new_p.append(ppr)
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "References"
    r.append(t)
    new_p.append(r)
    first_ref._element.addprevious(new_p)
    print("[fix] References heading inserted before bibliography")


def remove_highlights(doc):
    """Delete the Highlights heading and all paragraphs up to the next heading."""
    body = doc.element.body
    paras = list(doc.paragraphs)
    to_remove = []
    in_section = False
    for p in paras:
        text = p.text.strip()
        if text == "Highlights" and p.style and p.style.name.startswith("Heading"):
            in_section = True
            to_remove.append(p._element)
            continue
        if in_section:
            if p.style and p.style.name.startswith("Heading") and text != "Highlights":
                break  # next heading reached
            to_remove.append(p._element)
    for elem in to_remove:
        elem.getparent().remove(elem)
    print(f"[fix] removed Highlights section ({len(to_remove)} paragraphs)")


def demote_heading4_to_inline(doc):
    """Convert each Heading 4 paragraph into a bold lead-in on the next paragraph."""
    paras = list(doc.paragraphs)
    fixed = 0
    for i, p in enumerate(paras):
        if not (p.style and p.style.name == "Heading 4"):
            continue
        lead = p.text.strip()
        if not lead:
            p._element.getparent().remove(p._element)
            continue
        if not lead.endswith("."):
            lead = lead + "."
        # Find next sibling paragraph in body
        nxt_p = None
        for j in range(i + 1, len(paras)):
            if paras[j]._element.getparent() is not None:
                nxt_p = paras[j]
                break
        if nxt_p is None:
            print(f"[warn] Heading 4 '{lead}' has no following paragraph")
            continue
        # Prepend a bold run + space at the start of the next paragraph.
        new_run_bold = make_run(lead + " ", bold=True)
        first_child = nxt_p._element.find(qn("w:r"))
        if first_child is not None:
            first_child.addprevious(new_run_bold)
        else:
            # Insert after pPr if it exists, else at top.
            ppr = nxt_p._element.find(qn("w:pPr"))
            if ppr is not None:
                ppr.addnext(new_run_bold)
            else:
                nxt_p._element.insert(0, new_run_bold)
        # Remove the Heading 4 paragraph
        p._element.getparent().remove(p._element)
        fixed += 1
    print(f"[fix] demoted {fixed} Heading-4 paragraphs to inline bold lead-ins")


def add_section_numbering(doc):
    """Walk Heading 1 / Heading 2 in document order, prepend decimal numbers."""
    h1_counter = 0
    h2_counter = 0
    for p in doc.paragraphs:
        if not (p.style and p.style.name.startswith("Heading")):
            continue
        text = p.text.strip()
        if text in UNNUMBERED:
            continue
        if p.style.name == "Heading 1":
            h1_counter += 1
            h2_counter = 0
            prefix = f"{h1_counter} "
        elif p.style.name == "Heading 2":
            h2_counter += 1
            prefix = f"{h1_counter}.{h2_counter} "
        else:
            continue
        # Skip if already prefixed (idempotent).
        if re.match(r"^\d+(\.\d+)?\s", text):
            continue
        # Replace text by inserting a new run at the front.
        # Pandoc puts the heading text in a single run typically; rebuild.
        # Strategy: remove all existing runs, add a single run with prefix+text.
        pelem = p._element
        for r in list(pelem.findall(qn("w:r"))):
            pelem.remove(r)
        # Also remove any inline math objects in the heading (these are placeholders).
        for m in list(pelem.findall(qn("m:oMath"))):
            pelem.remove(m)
        new_run = make_run(prefix + text)
        pelem.append(new_run)
        print(f"[fix] {p.style.name}: '{prefix}{text[:60]}'")


def add_caption_prefixes(doc):
    """Prepend 'Fig. N ' / 'Table N ' to captions.

    Figure captions are the paragraph immediately following an image paragraph
    (pandoc places caption AFTER the image).
    Table captions are the paragraph immediately BEFORE a table.
    """
    body = doc.element.body
    children = list(body)
    # Walk children: find drawings (images) and tables in document order.
    fig_n = 0
    table_n = 0
    # Map: position of image paragraphs and table elements
    # We need to find adjacent <w:p> elements relative to images / tables.
    def find_text_run(p_elem):
        for r in p_elem.findall(qn("w:r")):
            t = r.find(qn("w:t"))
            if t is not None and t.text and t.text.strip():
                return t
        return None

    # Find image-bearing paragraphs: <w:p> containing <w:drawing>
    for idx, child in enumerate(children):
        if child.tag != f"{{{W_NS}}}p":
            # Tables are <w:tbl>; check immediately before for caption
            if child.tag == f"{{{W_NS}}}tbl":
                table_n += 1
                # Caption is the previous sibling that is a paragraph with text
                for j in range(idx - 1, -1, -1):
                    sib = children[j]
                    if sib.tag != f"{{{W_NS}}}p":
                        break
                    t_elem = find_text_run(sib)
                    if t_elem is not None and t_elem.text.strip():
                        # Prepend "Table N " to this run if not already there
                        if not t_elem.text.lstrip().startswith(f"Table {table_n}"):
                            t_elem.text = f"Table {table_n} " + t_elem.text
                            t_elem.set(qn("xml:space"), "preserve")
                            print(f"[fix] Table {table_n} caption: '{t_elem.text[:80]}...'")
                        break
            continue
        # Paragraph: check if it contains a drawing (image)
        has_drawing = child.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}graphic") is not None
        if not has_drawing:
            continue
        fig_n += 1
        # Caption is the NEXT paragraph with non-empty text content (skip empties).
        for j in range(idx + 1, len(children)):
            sib = children[j]
            if sib.tag != f"{{{W_NS}}}p":
                break
            t_elem = find_text_run(sib)
            if t_elem is not None and t_elem.text.strip():
                if not t_elem.text.lstrip().startswith(f"Fig. {fig_n}"):
                    t_elem.text = f"Fig. {fig_n} " + t_elem.text
                    t_elem.set(qn("xml:space"), "preserve")
                    print(f"[fix] Fig. {fig_n} caption: '{t_elem.text[:80]}...'")
                break


def main():
    doc = docx.Document(DOC)
    print(f"loaded {DOC}")
    print(f"  paragraphs={len(doc.paragraphs)}, tables={len(doc.tables)}")

    # Order matters: do deletions first (Highlights), then H4 demotion, then
    # numbering, then caption prefixes. References style is independent.
    remove_highlights(doc)
    demote_heading4_to_inline(doc)
    fix_references_heading(doc)
    add_section_numbering(doc)
    add_caption_prefixes(doc)

    doc.save(DOC)
    print(f"\nsaved {DOC}")


if __name__ == "__main__":
    main()
