"""Build the separate Title Page document.

Contents per the Building Simulation author guide (§3.1):
  - Cover letter to the Editor-in-Chief
  - Paper title
  - Authors (with corresponding marked *)
  - Affiliations
  - Corresponding author email
  - Author contributions statement
  - Compliance with ethical standards (competing interest + ethical approval)
  - Acknowledgements (if any)

Author/affiliation/email are placeholders and must be filled in before
submission.
"""
import docx
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

TEMPLATE = "../../12273_Building_Simulation_Template_2025/Template_12273_Title_Page_Cover_letter.docx"
OUT = "Title_Page.docx"

TITLE = (
    "Safe Reinforcement Learning with Conservation-Aware Constraints for "
    "HVAC Control in Art Museums: Encoding EN 15757 Rate Limits as a "
    "Constrained MDP"
)

COVER_LETTER = """Dear Editor-in-Chief,

Please find enclosed our manuscript entitled "Safe Reinforcement Learning with Conservation-Aware Constraints for HVAC Control in Art Museums: Encoding EN 15757 Rate Limits as a Constrained MDP" for consideration as a research article in Building Simulation.

Museum HVAC systems run year-round at energy intensities two to three times those of comparable office buildings, because preventive conservation requires narrow-band control of both temperature and relative humidity. Data-driven controllers proposed for office and residential HVAC do not transfer cleanly to museum settings, because conservation constraints from EN 15757 and ASHRAE Class A1 differ qualitatively from comfort constraints. Existing work either treats these limits as soft reward penalties, which is inconsistent with the safety semantics of the standards, or uses classical multi-objective optimization that cannot react to time-varying visitor and weather loads.

This paper contributes the following. First, museum HVAC control is formulated as a Constrained Markov Decision Process in which ASHRAE static envelopes and the EN 15757 dynamic rate caps on dT/dt and dRH/dt are aggregated into a scalar cost. To the best of our knowledge, this is the first CMDP formulation that includes the rate clauses. Second, a Lagrangian-PPO controller with a PID-tuned multiplier is implemented, and an implementation pitfall in subprocess-based vectorized training is identified and resolved: the Lagrange multiplier must be propagated to parallel workers via the set_attr mechanism. Third, on a five-zone differentiated museum simulator the controller traces a clean energy-conservation Pareto front whose anisotropy gives operators a principled trade-off tool. Fourth, per-zone analysis shows that residual violations are confined to a single constraint-coupled zone, which provides actionable guidance for targeted retrofits.

We believe the manuscript fits the scope of Building Simulation, particularly the journal's interest in modeling tools that bridge building science with closed-loop control. The five-zone simulator and the Lagrangian-PPO implementation are designed to plug into Sinergym and EnergyPlus without code change, supporting reproducibility and extension by other groups. Code, simulator, and evaluation scripts will be released upon publication.

The manuscript has not been published previously and is not under consideration elsewhere. All authors have approved the submission and have no competing interests to declare.

Thank you for your time and consideration. We look forward to your response.

Sincerely,
He Zhao (on behalf of all authors)
School of Art, Guilin University of Technology
12 Jiangan Road, Qixing District, Guilin 541004, China
E-mail: 2010011@glut.edu.cn
"""

# Authors with affiliation superscripts. Each tuple is (name, superscript,
# is_corresponding). Names use given-name-first romanization to match the
# manuscript byline.
AUTHORS = [
    ("He Zhao", "1", True),
    ("Wei Xiong", "2", False),
    ("Zhanhao Liang", "3", False),
    ("Qitao Zou", "4", False),
    ("Lü Tan", "1", False),
    ("Yiming Lei", "1", False),
]

AFFILIATIONS = [
    "1. School of Art, Guilin University of Technology, Guilin 541004, China.",
    "2. School of Mechanical and Control Engineering, Guilin University of "
    "Technology, Guilin 541004, China.",
    "3. School of Materials Science and Engineering, South China University of "
    "Technology, Guangzhou, China.",
    "4. School of Information Engineering, Guilin University, Guilin, China.",
]

CORRESPONDING_EMAIL = (
    "* Corresponding author: He Zhao, School of Art, Guilin University of "
    "Technology, 12 Jiangan Road, Qixing District, Guilin 541004, China. "
    "E-mail: 2010011@glut.edu.cn"
)

# Co-author e-mail addresses (kept on the title page for the editorial office).
COAUTHOR_EMAILS = (
    "Co-author e-mail addresses: Wei Xiong (xiongwei@glut.edu.cn); "
    "Zhanhao Liang (lyon@cumt.edu.cn); Qitao Zou (2294252051@qq.com); "
    "Lü Tan (2354339206@qq.com); Yiming Lei (305275591@qq.com)."
)

AUTHOR_CONTRIBUTIONS = (
    "All authors contributed to the study conception and design. "
    "He Zhao led the study, developed the constrained Markov decision process "
    "formulation and the conservation cost, implemented the Lagrangian-PPO "
    "controller and the five-zone simulator, ran the experiments, and wrote "
    "the first draft of the manuscript. Wei Xiong contributed to the control "
    "methodology and the analysis of the training dynamics. Zhanhao Liang "
    "contributed to the materials and preventive-conservation framing of the "
    "conservation envelopes. Qitao Zou contributed to the data processing and "
    "the evaluation pipeline. Lü Tan and Yiming Lei contributed to the "
    "literature survey and the preparation of figures. All authors commented "
    "on subsequent versions of the manuscript and approved the final "
    "manuscript."
)

COMPETING_INTEREST = (
    "The authors have no competing interests to declare that are relevant to "
    "the content of this article."
)

ETHICAL_APPROVAL = (
    "This study does not contain any studies with human or animal subjects "
    "performed by any of the authors."
)

ACKNOWLEDGMENTS = (
    "This work was supported by the Guangxi Key Research and Development "
    "Program (Guike AB23075096)."
)

GENAI_DISCLOSURE = (
    "Declaration of generative AI and AI-assisted technologies in the writing "
    "process. During the preparation of this work, the authors used an "
    "AI assistant to polish the language of the manuscript and to help with "
    "formatting and layout. After using this tool, the authors reviewed and "
    "edited the content as needed and take full responsibility for the "
    "content of the publication."
)


def add_heading(doc, text, level=2):
    p = doc.add_heading(text, level=level)
    return p


def add_paragraph(doc, text, style=None, bold=False, align=None):
    p = doc.add_paragraph()
    if style is not None:
        try:
            p.style = doc.styles[style]
        except KeyError:
            pass
    # Default to left alignment: the template's Normal style is justified,
    # which stretches short lines (e.g. the signature block) across the page.
    p.alignment = align if align is not None else WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    if bold:
        run.bold = True
    return p


def add_author_line(doc, authors):
    """Render the author byline with superscript affiliation markers."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for i, (name, sup, is_corr) in enumerate(authors):
        if i > 0:
            p.add_run(", ")
        p.add_run(name)
        sup_run = p.add_run(sup + ("*" if is_corr else ""))
        sup_run.font.superscript = True
    return p


def main():
    doc = docx.Document(TEMPLATE)
    # Clear all existing paragraphs in the template (keep styles).
    body = doc.element.body
    sectPr = body.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sectPr"
    )
    for child in list(body):
        if child is sectPr:
            continue
        body.remove(child)

    # Cover letter
    add_paragraph(doc, "Cover Letter", bold=True)
    for para in COVER_LETTER.strip().split("\n\n"):
        add_paragraph(doc, para.strip())
    doc.add_paragraph()  # blank spacer

    # Title
    add_paragraph(doc, "Title", bold=True)
    add_paragraph(doc, TITLE)
    doc.add_paragraph()

    # Authors
    add_paragraph(doc, "Authors", bold=True)
    add_author_line(doc, AUTHORS)
    doc.add_paragraph()

    # Affiliations
    add_paragraph(doc, "Affiliations", bold=True)
    for aff in AFFILIATIONS:
        add_paragraph(doc, aff)
    doc.add_paragraph()

    # Corresponding author + co-author e-mails
    add_paragraph(doc, CORRESPONDING_EMAIL)
    add_paragraph(doc, COAUTHOR_EMAILS)
    doc.add_paragraph()

    # Author contributions
    add_paragraph(doc, "Author Contributions", bold=True)
    add_paragraph(doc, AUTHOR_CONTRIBUTIONS)
    doc.add_paragraph()

    # Compliance with ethical standards
    add_paragraph(doc, "Compliance with Ethical Standards", bold=True)
    add_paragraph(doc, "Declaration of competing interest.", bold=True)
    add_paragraph(doc, COMPETING_INTEREST)
    add_paragraph(doc, "Ethical approval.", bold=True)
    add_paragraph(doc, ETHICAL_APPROVAL)
    doc.add_paragraph()

    # Acknowledgments
    add_paragraph(doc, "Acknowledgements", bold=True)
    add_paragraph(doc, ACKNOWLEDGMENTS)
    doc.add_paragraph()

    # GenAI disclosure
    add_paragraph(doc, "Use of generative AI", bold=True)
    add_paragraph(doc, GENAI_DISCLOSURE)

    doc.save(OUT)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
