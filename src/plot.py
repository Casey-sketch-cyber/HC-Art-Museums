"""Publication-grade figures for the Safe-RL museum HVAC paper.

Style follows the nature-figure skill conventions:
  * Editable SVG text (svg.fonttype = 'none').
  * Arial primary, DejaVu fallback.
  * No right/top spines, frameless legends.
  * Unified palette (DEFAULT_COLORS) across panels.
  * Each figure saved as .svg (primary), .pdf, .png at 600 dpi.

Outputs go to results/figs/.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml


# ---------------------------------------------------------------------------
# Palette & style
# ---------------------------------------------------------------------------

PALETTE = {
    "blue_main":       "#0F4D92",
    "blue_secondary":  "#3775BA",
    "green_3":         "#8BCF8B",
    "red_strong":      "#B64342",
    "neutral_light":   "#CFCECE",
    "neutral_mid":     "#767676",
    "neutral_dark":    "#4D4D4D",
    "neutral_black":   "#272727",
    "gold":            "#FFD700",
    "teal":            "#42949E",
    "violet":          "#9A4D8E",
}

DEFAULT_COLORS = [
    PALETTE["blue_main"],
    PALETTE["green_3"],
    PALETTE["red_strong"],
    PALETTE["teal"],
    PALETTE["violet"],
    PALETTE["neutral_light"],
]

CONTROLLER_COLORS = {
    "rule_fixed":    PALETTE["neutral_mid"],
    "schedule":      PALETTE["neutral_light"],
    "vanilla":       PALETTE["violet"],
    "soft":          PALETTE["teal"],
    "soft_penalty":  PALETTE["teal"],
    "lagrangian":    PALETTE["red_strong"],
    "lagr":          PALETTE["red_strong"],
}


def apply_publication_style(font_size: int = 8, axes_linewidth: float = 0.8):
    """Apply Nature-style rcParams. Call once before any figure creation."""
    plt.rcParams["font.family"]     = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
    plt.rcParams["svg.fonttype"]    = "none"   # editable text in SVG
    plt.rcParams["pdf.fonttype"]    = 42       # editable TrueType in PDF
    plt.rcParams["font.size"]       = font_size
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["axes.spines.top"]   = False
    plt.rcParams["axes.linewidth"]    = axes_linewidth
    plt.rcParams["xtick.major.width"] = axes_linewidth
    plt.rcParams["ytick.major.width"] = axes_linewidth
    plt.rcParams["xtick.major.size"]  = 3
    plt.rcParams["ytick.major.size"]  = 3
    plt.rcParams["legend.frameon"]    = False
    plt.rcParams["legend.fontsize"]   = font_size - 1


def add_panel_label(ax, label: str, x: float = -0.18, y: float = 1.02,
                    fontsize: int = 11):
    ax.text(x, y, label, transform=ax.transAxes, fontsize=fontsize,
            fontweight="bold", ha="left", va="bottom")


def save_pub_py(fig, basename: Path, dpi: int = 600) -> None:
    """Save SVG (primary), PDF, and PNG."""
    basename = Path(basename)
    basename.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(basename.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(basename.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(basename.with_suffix(".png"), bbox_inches="tight", dpi=dpi)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

RESULTS = Path("results")
FIGS    = RESULTS / "figs"
CONSERVATION = Path(__file__).resolve().parent.parent / "configs" / "conservation.yaml"


def _short_name(controller: str) -> str:
    """Strip seed/env suffixes from run names to get a controller family."""
    n = controller
    for sfx in ("_seed0", "_seed1", "_seed2"):
        n = n.replace(sfx, "")
    for env in ("_mock", "_sinergym"):
        n = n.replace(env, "")
    return n


def _controller_color(name: str) -> str:
    short = _short_name(name)
    return CONTROLLER_COLORS.get(short, PALETTE["blue_main"])


def collect_summaries(runs: list[Path]) -> pd.DataFrame:
    rows = []
    for r in runs:
        s_path = r / "eval.summary.json"
        if not s_path.exists():
            continue
        d = json.loads(s_path.read_text())
        d["controller_short"] = _short_name(d["controller"])
        rows.append(d)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Aggregate across seeds: mean + SEM for the headline metrics.
    return df


def aggregate_by_controller(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    metrics = ["total_energy_kwh", "conservation_cost_total",
               "violation_steps", "mean_pmv"]
    g = df.groupby("controller_short")
    agg = g[metrics].agg(["mean", "sem"]).reset_index()
    agg.columns = ["controller"] + [f"{m}_{s}" for m, s in agg.columns[1:]]
    # carry per-zone breakdown means
    zone_cols = [c for c in df.columns if c.startswith("violation_steps_")]
    for c in zone_cols:
        agg[c] = g[c].mean().values
    return agg


# ---------------------------------------------------------------------------
# Figure 1 — hero: 2x2 panel summary
# ---------------------------------------------------------------------------

def fig_hero(df: pd.DataFrame, out: Path):
    """Four-panel hero: a) energy, b) violations, c) Pareto, d) per-zone stack."""
    if df.empty:
        return
    df = df.sort_values("conservation_cost_total_mean").reset_index(drop=True)
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 5.0))
    ax_a, ax_b, ax_c, ax_d = axes.flatten()

    # ---- (a) annual energy ------------------------------------------------
    x = np.arange(len(df))
    colors = [_controller_color(c) for c in df["controller"]]
    ax_a.bar(x, df["total_energy_kwh_mean"] / 1e3,
             yerr=df["total_energy_kwh_sem"] / 1e3,
             color=colors, edgecolor=PALETTE["neutral_black"], linewidth=0.6,
             error_kw={"elinewidth": 0.8, "capsize": 2})
    ax_a.set_xticks(x)
    ax_a.set_xticklabels(df["controller"], rotation=35, ha="right", fontsize=5.5)
    ax_a.set_ylabel("Annual HVAC energy (MWh)")
    add_panel_label(ax_a, "a")

    # Shared controller-family color key (placed above panel a).
    from matplotlib.patches import Patch
    family_handles = [
        Patch(facecolor=PALETTE["blue_main"],     edgecolor="none",
              label="Lagr. sweep"),
        Patch(facecolor=PALETTE["neutral_light"], edgecolor="none",
              label="schedule"),
        Patch(facecolor=PALETTE["neutral_mid"],   edgecolor="none",
              label="rule-fixed"),
        Patch(facecolor=PALETTE["red_strong"],    edgecolor="none",
              label="Lagr. 500k"),
        Patch(facecolor=PALETTE["violet"],        edgecolor="none",
              label="vanilla"),
        Patch(facecolor=PALETTE["teal"],          edgecolor="none",
              label="soft"),
    ]
    ax_a.legend(handles=family_handles, ncol=6, fontsize=5.5,
                loc="lower center", bbox_to_anchor=(1.05, 1.10),
                handlelength=1.0, handletextpad=0.4, columnspacing=0.8,
                borderaxespad=0)

    # ---- (b) conservation violation steps --------------------------------
    ax_b.bar(x, df["violation_steps_mean"],
             yerr=df["violation_steps_sem"],
             color=colors, edgecolor=PALETTE["neutral_black"], linewidth=0.6,
             error_kw={"elinewidth": 0.8, "capsize": 2})
    ax_b.set_xticks(x)
    ax_b.set_xticklabels(df["controller"], rotation=35, ha="right", fontsize=5.5)
    ax_b.set_ylabel("Violation steps / year (15-min)")
    add_panel_label(ax_b, "b")

    # ---- (c) Pareto from sweep -------------------------------------------
    sweep_path = RESULTS / "pareto_sweep.csv"
    if sweep_path.exists():
        sw = pd.read_csv(sweep_path).sort_values("cost_limit")
        sc = ax_c.scatter(sw["total_energy_kwh"] / 1e3,
                          sw["conservation_cost_total"],
                          c=sw["cost_limit"], cmap="viridis",
                          s=40, edgecolor=PALETTE["neutral_black"], linewidth=0.5)
        cb = plt.colorbar(sc, ax=ax_c, shrink=0.85, pad=0.02)
        cb.set_label("cost_limit", fontsize=7)
        cb.ax.tick_params(labelsize=6)
        ax_c.plot(sw["total_energy_kwh"] / 1e3,
                  sw["conservation_cost_total"],
                  color=PALETTE["neutral_mid"], linewidth=0.8, alpha=0.6, zorder=0)
        ax_c.set_xlabel("Annual energy (MWh)")
        ax_c.set_ylabel("Conservation cost (year-total)")
    else:
        ax_c.text(0.5, 0.5, "pareto sweep not run",
                  transform=ax_c.transAxes, ha="center", va="center",
                  fontsize=8, color=PALETTE["neutral_mid"])
    add_panel_label(ax_c, "c")

    # ---- (d) per-zone violation stack ------------------------------------
    zones = list(yaml.safe_load(CONSERVATION.read_text())["zones"].keys())
    zone_cols = [f"violation_steps_{z}" for z in zones if f"violation_steps_{z}" in df.columns]
    bottom = np.zeros(len(df))
    zone_palette = DEFAULT_COLORS
    for i, c in enumerate(zone_cols):
        label = c.replace("violation_steps_", "")
        ax_d.bar(x, df[c], bottom=bottom,
                 color=zone_palette[i % len(zone_palette)],
                 edgecolor=PALETTE["neutral_black"], linewidth=0.4,
                 label=label)
        bottom += df[c].values
    ax_d.set_xticks(x)
    ax_d.set_xticklabels(df["controller"], rotation=35, ha="right", fontsize=5.5)
    ax_d.set_ylabel("Violation steps / year")
    ax_d.legend(fontsize=6, loc="upper left", bbox_to_anchor=(0.02, 0.98),
                handlelength=1.0, handletextpad=0.4, borderaxespad=0,
                title="zone", title_fontsize=6)
    add_panel_label(ax_d, "d")

    fig.tight_layout()
    save_pub_py(fig, out)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 2 — typical-week trajectory
# ---------------------------------------------------------------------------

def fig_typical_week(rule_csv: Path, lagr_csv: Path, out: Path):
    if not (rule_csv.exists() and lagr_csv.exists()):
        return
    rule = pd.read_csv(rule_csv)
    lagr = pd.read_csv(lagr_csv)
    n = min(7 * 24 * 4, len(rule), len(lagr))
    t = np.arange(n) * 0.25 / 24

    fig, axes = plt.subplots(2, 1, figsize=(6.5, 3.6), sharex=True)
    ax_a, ax_b = axes

    ax_a.plot(t, rule["cost"].iloc[:n], label="Rule (fixed setpoint)",
              color=PALETTE["neutral_mid"], linewidth=1.0)
    ax_a.plot(t, lagr["cost"].iloc[:n], label="Lagrangian PPO (ours)",
              color=PALETTE["red_strong"], linewidth=1.0)
    ax_a.set_ylabel("Conservation cost")
    ax_a.legend(loc="upper right")
    add_panel_label(ax_a, "a")

    ax_b.plot(t, rule["energy_kwh"].iloc[:n], label="Rule",
              color=PALETTE["neutral_mid"], linewidth=1.0)
    ax_b.plot(t, lagr["energy_kwh"].iloc[:n], label="Lagrangian",
              color=PALETTE["red_strong"], linewidth=1.0)
    ax_b.set_xlabel("Days")
    ax_b.set_ylabel("Energy (kWh / 15-min)")
    ax_b.legend(loc="upper right")
    add_panel_label(ax_b, "b")

    fig.tight_layout()
    save_pub_py(fig, out)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 3 — training curves (lambda + cost trajectory)
# ---------------------------------------------------------------------------

def fig_training_curves(out: Path):
    """Extract tensorboard scalars for the Lagrangian runs and plot.

    Looks for run dirs that contain 'lagr' in their name.
    """
    try:
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    except ImportError:
        print("[plot] tensorboard not installed, skipping training-curves fig")
        return

    log_dirs = [d for d in Path("logs").glob("lagr_*/PPO_*")] + \
               [d for d in Path("logs").glob("smoke*/PPO_*")]
    if not log_dirs:
        print("[plot] no tb logs found, skipping training-curves fig")
        return

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6))
    ax_a, ax_b = axes
    for d in log_dirs[:6]:
        ea = EventAccumulator(str(d), size_guidance={"scalars": 0})
        ea.Reload()
        tags = ea.Tags().get("scalars", [])
        if "lagrangian/lambda" in tags:
            ev = ea.Scalars("lagrangian/lambda")
            steps = [e.step for e in ev]
            vals  = [e.value for e in ev]
            ax_a.plot(steps, vals, alpha=0.6, linewidth=0.8,
                      color=PALETTE["red_strong"], label=d.parent.name)
        if "lagrangian/mean_cost" in tags:
            ev = ea.Scalars("lagrangian/mean_cost")
            steps = [e.step for e in ev]
            vals  = [e.value for e in ev]
            ax_b.plot(steps, vals, alpha=0.6, linewidth=0.8,
                      color=PALETTE["blue_main"], label=d.parent.name)
    ax_a.set_xlabel("Training steps")
    ax_a.set_ylabel(r"Lagrange multiplier $\lambda$")
    add_panel_label(ax_a, "a")
    ax_b.set_xlabel("Training steps")
    ax_b.set_ylabel("Mean cost / rollout")
    add_panel_label(ax_b, "b")

    fig.tight_layout()
    save_pub_py(fig, out)
    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runs", nargs="*", default=None)
    p.add_argument("--font-size", type=int, default=8)
    args = p.parse_args()

    apply_publication_style(font_size=args.font_size)
    FIGS.mkdir(parents=True, exist_ok=True)

    if args.runs is None:
        run_dirs = [d for d in RESULTS.iterdir()
                    if d.is_dir() and (d / "eval.summary.json").exists()]
    else:
        run_dirs = [Path(r) for r in args.runs]
    df_raw = collect_summaries(run_dirs)
    if df_raw.empty:
        print("[plot] no eval summaries found")
        return
    df_agg = aggregate_by_controller(df_raw)
    print("\n=== Aggregated controller comparison ===")
    print(df_agg[["controller",
                  "total_energy_kwh_mean", "total_energy_kwh_sem",
                  "violation_steps_mean", "violation_steps_sem",
                  "conservation_cost_total_mean"]].to_string(index=False))

    fig_hero(df_agg, FIGS / "fig1_hero")

    # Typical week: pick rule_fixed and best lagrangian run.
    rule_csv = RESULTS / "rule_fixed" / "eval.csv"
    lagr_runs = sorted([d for d in run_dirs if "lagr" in d.name],
                       key=lambda d: (d / "eval.summary.json").stat().st_mtime,
                       reverse=True)
    if lagr_runs:
        fig_typical_week(rule_csv, lagr_runs[0] / "eval.csv",
                         FIGS / "fig2_typical_week")

    fig_training_curves(FIGS / "fig3_training_curves")

    print(f"\n[plot] wrote figures to {FIGS}")


if __name__ == "__main__":
    main()
