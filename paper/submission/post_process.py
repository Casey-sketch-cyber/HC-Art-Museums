"""Post-process the pandoc-generated docx.

Two known issues from pandoc's LaTeX -> docx conversion:
  (1) The algorithm environment is collapsed into a single run-on paragraph.
  (2) The B1..B5 description-list labels are dropped.

We fix both. Math symbols inside the algorithm are written as Unicode so the
content is readable; the journal typesetter reformats during production.
"""
import re
import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

DOC = "Blinded_Manuscript.docx"

ALG_CAPTION = (
    "Algorithm 1. Lagrangian PPO with PID multiplier and "
    "subprocess-safe λ propagation."
)

ALG_STEPS = [
    "1:  Initialize policy π_θ, value V_φ, multiplier λ ← λ_0, integrator I ← 0.",
    "2:  Create N parallel envs {E_n}_{n=1..N} wrapped with CostRewardWrapper, "
        "each holding an internal attribute _lambda_scalar initialized to λ_0.",
    "3:  for rollout k = 1, 2, ... do",
    "4:      Collect a rollout of length T in each E_n using the current policy. "
        "Each step emits r̃_t = r_t − E_n._lambda_scalar · c_t and stores c_t "
        "in an in-process per-env cost buffer.",
    "5:      Run a PPO update on the rollout buffer (clipped surrogate + GAE) "
        "for K epochs.",
    "6:      [End-of-rollout callback] Pull the {c_t} buffers from all N envs "
        "via VecEnv.env_method(\"pop_cost_buffer\"), compute Ĵ_c ← mean(c).",
    "7:      Update λ via Eq. (12).",
    "8:      Push λ to all parallel envs via "
        "VecEnv.set_attr(\"_lambda_scalar\", λ).",
    "9:  end for",
]

# B1..B5 labels with the lead-in text that pandoc dropped.
BASELINE_LABELS = [
    ("Constant setpoint", "B1: Rule-fixed.  "),
    ("Setpoints relaxed during closed hours", "B2: Schedule.  "),
    ("PPO trained on energy and comfort only", "B3: Vanilla-PPO.  "),
    ("PPO with a fixed-weight soft penalty", "B4: Soft-PPO.  "),
    ("Algorithm\xa01.", "B5: Lagrangian-PPO (ours).  "),  # nbsp from pandoc
    ("Algorithm 1.", "B5: Lagrangian-PPO (ours).  "),
]


def fix_baseline_labels(doc):
    """Prepend bold B1..B5 labels to the baseline list paragraphs."""
    fixed = 0
    # Idempotency: skip paragraphs that already start with B<n>: prefix.
    for p in doc.paragraphs:
        text = p.text.strip()
        if re.match(r"^B[1-5]:", text):
            continue
        for needle, label in BASELINE_LABELS:
            if text.startswith(needle):
                # Insert a bold run at the start of the paragraph.
                pelem = p._element
                # Find first run; insert a new run before it.
                runs = pelem.findall(qn("w:r"))
                new_run = OxmlElement("w:r")
                rpr = OxmlElement("w:rPr")
                b = OxmlElement("w:b")
                rpr.append(b)
                new_run.append(rpr)
                t = OxmlElement("w:t")
                t.text = label
                t.set(qn("xml:space"), "preserve")
                new_run.append(t)
                if runs:
                    runs[0].addprevious(new_run)
                else:
                    pelem.append(new_run)
                fixed += 1
                break
    print(f"baseline labels fixed: {fixed}/{len(BASELINE_LABELS)}")


def fix_algorithm(doc):
    """Replace the collapsed algorithm paragraph with a numbered structure."""
    target = None
    for p in doc.paragraphs:
        if p.text.strip().startswith("Initialize policy"):
            target = p
            break
    if target is None:
        print("WARNING: algorithm anchor not found")
        return
    # Replace the run content with the algorithm caption (bold).
    for r in list(target._element.findall(qn("w:r"))):
        target._element.remove(r)
    # Also remove OMML math that was in the run-on paragraph.
    for m in list(target._element.findall(qn("m:oMath"))) + \
             list(target._element.findall(qn("m:oMathPara"))):
        target._element.remove(m)
    caption_run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    b = OxmlElement("w:b")
    rpr.append(b)
    caption_run.append(rpr)
    ct = OxmlElement("w:t")
    ct.text = ALG_CAPTION
    ct.set(qn("xml:space"), "preserve")
    caption_run.append(ct)
    target._element.append(caption_run)

    # Insert step paragraphs after the caption.
    prev = target._element
    for step in ALG_STEPS:
        new_p = OxmlElement("w:p")
        # Inherit Body Text style from the caption paragraph.
        ppr = OxmlElement("w:pPr")
        pstyle = OxmlElement("w:pStyle")
        pstyle.set(qn("w:val"), "BodyText")
        ppr.append(pstyle)
        new_p.append(ppr)
        new_r = OxmlElement("w:r")
        new_t = OxmlElement("w:t")
        new_t.text = step
        new_t.set(qn("xml:space"), "preserve")
        new_r.append(new_t)
        new_p.append(new_r)
        prev.addnext(new_p)
        prev = new_p
    print(f"algorithm reconstructed with {len(ALG_STEPS)} step paragraphs")


def main():
    doc = docx.Document(DOC)
    fix_baseline_labels(doc)
    fix_algorithm(doc)
    doc.save(DOC)
    print(f"saved {DOC}")


if __name__ == "__main__":
    main()
