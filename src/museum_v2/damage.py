"""Differentiable heritage damage functions for museum indoor microclimates (Task S2.3).

Implements all four degradation mechanisms specified in ``docs/PLAN_ISCIENCE.md``
Section 5.3 and ``docs/TASKS.md`` Section S2.3:

1. **Chemical degradation** (:func:`chemical_lifetime_multiplier`,
   :func:`chemical_degradation_risk`): Michalski-Martens Lifetime Multiplier ``LM``
   (Martens 2012, Ch. 3, Eq. 3.2, p. 61; Ch. 5, Sec. 5.2.3, p. 103; Michalski 2002),
   supporting both cellulosic/paper collections (``Ea = 100 kJ/mol``, evaluated on
   room air ``T, RH``) and painted/varnished objects (``Ea = 70 kJ/mol``, evaluated
   on object surface ``RH``).
2. **Biological degradation** (:func:`sedlbauer_lim_rh`, :func:`vtt_critical_rh`,
   :func:`mould_germination_rate`, :func:`biological_mould_risk`): Sedlbauer Lowest
   Isopleth for Mould (``LIM_0``, ``LIM_I``, ``LIM_II``) and Substrate Category I
   germination-time isopleths (Sedlbauer et al. 2001, Fig. 5; Krus, Kilian &
   Sedlbauer 2007, p. 186, Fig. 1; Martens 2012, Sec. 5.2.2, p. 102), plus the VTT
   reference threshold (Hukka & Viitanen 1999) for cross-checking.
3. **Mechanical degradation** (:func:`wood_equilibrium_strain`,
   :func:`mechanical_strain_risk`, :func:`estimate_proofed_envelope`,
   :func:`proofed_fluctuation_risk`): Tangential wood swelling strain isotherm
   calibrated to Mecklenburg, Tumosa & Erhardt (1998, pp. 467-468, Fig. 3a & Fig. 4a)
   and Martens (2012, Fig. 3.4, p. 55 & Fig. 3.5, p. 56), yield/tensile-failure
   assessment on ``(surface - bulk)`` for ``panel_painting`` and ``wooden_sculpture``
   or ``(bulk - mean)`` for ``wooden_furniture`` (Martens 2012, Sec. 5.2.4, pp. 104-105),
   and Michalski (2007, pp. 11-15) proofed-fluctuation protection.
4. **Metal corrosion** (:func:`metal_corrosion_risk`): Cumulative hours and smooth
   differentiable surrogates for exceedance of critical RH for copper/bronze alloys
   (CCI *Caring for Metal Objects*, citing Rimmer et al. 2013; Martens 2012, Table 3.1,
   p. 49; Scott 1990).

Every metric works natively on both ``torch.Tensor`` (preserving PyTorch autograd
graphs) and ``numpy.ndarray`` (with exact analytical/AD-compatible VJP helpers for
torch-less verification environments). Non-smooth hinges (``max(0, x)``, ``|x|``,
indicator steps) have documented ``C^infty`` smooth relaxations alongside exact
non-smooth audit counters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Union

import numpy as np

try:
    import torch
    import torch.nn.functional as F

    HAS_TORCH = True
except ImportError:  # pragma: no cover - verified in torch-less environments
    torch = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]
    HAS_TORCH = False

ArrayLike = Union[np.ndarray, "torch.Tensor", float, int, list, tuple]

# ---------------------------------------------------------------------------
# Literature Constants & Provenance Summaries (detailed in docs/DAMAGE_MODELS.md)
# ---------------------------------------------------------------------------

GAS_CONSTANT_J_MOL_K: float = 8.314  # Martens (2012), Eq. 3.2, p. 61
REFERENCE_TEMP_K: float = 293.15  # 20 degC reference (Martens 2012, p. 61; TASKS S2.3)
REFERENCE_RH_PERCENT: float = 50.0  # 50% RH reference (Martens 2012, Eq. 3.2, p. 61)
LM_RH_EXPONENT: float = 1.3  # Michalski (2002/2003); Martens (2012), Eq. 3.2, p. 61

ACTIVATION_ENERGY_PAPER_J_MOL: float = 100_000.0  # Martens (2012), p. 61 & p. 103
ACTIVATION_ENERGY_VARNISH_J_MOL: float = 70_000.0  # Martens (2012), p. 61 & p. 103

# Sedlbauer LIM curve fit to Krus, Kilian & Sedlbauer (2007, p. 186 Fig. 1) &
# Sedlbauer et al. (2001, Fig. 5): LIM_c(T) = a_c + b * exp(-T / T0) [% RH]
SEDLBAUER_EXP_SCALE: float = 23.32
SEDLBAUER_T0_C: float = 7.86
SEDLBAUER_ASYMPTOTE_RH: dict[str, float] = {
    "0": 69.19,   # Optimum culture medium (LIM 0)
    "I": 74.19,   # Biologically recyclable organic materials (LIM_Bau I)
    "II": 78.39,  # Porous biologically adverse substrates (LIM_Bau II)
}
# Germination rate r(e) = (c1 * e + c2 * e^2) [h^-1] fitted to Substrate I
# isopleths [16d, 8d, 4d, 2d, 1d] at excess e = [2.0, 4.5, 7.0, 10.0, 15.0] %RH.
GERM_RATE_C1: float = 5.364750e-4
GERM_RATE_C2: float = 1.497251e-4

# Tangential wood swelling cubic fit calibrated to Mecklenburg, Tumosa & Erhardt
# (1998, pp. 467-468, Fig. 3a & Fig. 4a) and Martens (2012, Fig. 3.4-3.5, pp. 55-56):
#   eps(RH) = c1 * x + c2 * x^2 + c3 * x^3,   x = (RH - 45) / 50
WOOD_STRAIN_C1: float = 0.006577
WOOD_STRAIN_C2: float = -0.000887
WOOD_STRAIN_C3: float = 0.024119

WOOD_YIELD_STRAIN_DEFAULT: float = 0.004  # Martens (2012), pp. 53, 56, 105; Mecklenburg (1998)
WOOD_FAILURE_STRAIN_DEFAULT: float = 0.012  # 3x yield (Martens 2012, p. 53)

METAL_CRH_PRESETS: dict[str, float] = {
    "bronze_chloride": 42.0,     # CCI Caring for Metal Objects, citing Rimmer et al. (2013)
    "bronze_conservative": 35.0,  # Scott (1990) / Thickett conservative bronze disease threshold
    "ashrae_dry_room": 30.0,      # Martens (2012), Table 3.1, p. 49 (ASHRAE Dry room)
    "clean_metal": 65.0,          # CCI Caring for Metal Objects bulk water-film onset
}


# ---------------------------------------------------------------------------
# Backend Helpers
# ---------------------------------------------------------------------------

def _any_torch(*values: Any) -> bool:
    return HAS_TORCH and any(isinstance(v, torch.Tensor) for v in values if v is not None)


def _as_backend(
    value: ArrayLike,
    *,
    use_torch: bool,
    ref_tensor: Any = None,
) -> Any:
    if use_torch:
        if isinstance(value, torch.Tensor):
            return value if value.is_floating_point() else value.to(dtype=torch.float64)
        kwargs: dict[str, Any] = {}
        if ref_tensor is not None:
            kwargs = {"device": ref_tensor.device, "dtype": ref_tensor.dtype}
        else:
            kwargs = {"dtype": torch.float64}
        return torch.as_tensor(value, **kwargs)
    arr = np.asarray(value)
    return arr if np.issubdtype(arr.dtype, np.floating) else arr.astype(np.float64)


def _find_ref_tensor(*values: Any) -> Any:
    for v in values:
        if HAS_TORCH and isinstance(v, torch.Tensor):
            return v
    return None


def _softplus(x: Any, beta: float) -> Any:
    b = float(beta)
    if b <= 0.0:
        raise ValueError(f"beta must be strictly positive, got {beta!r}")
    if _any_torch(x):
        return b * F.softplus(x / b)
    # Overflow-safe softplus: max(x, 0) + b * log1p(exp(-|x| / b))
    return np.maximum(x, 0.0) + b * np.log1p(np.exp(-np.abs(x) / b))


def _sigmoid(x: Any, scale: float) -> Any:
    s = float(scale)
    if s <= 0.0:
        raise ValueError(f"scale must be strictly positive, got {scale!r}")
    z = x / s
    if _any_torch(z):
        return torch.sigmoid(z)
    # Overflow-safe sigmoid
    pos = z >= 0.0
    out = np.empty_like(z, dtype=np.result_type(z, np.float64))
    z_safe = np.clip(z, -60.0, 60.0)
    out[pos] = 1.0 / (1.0 + np.exp(-z_safe[pos]))
    ez = np.exp(z_safe[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


def _smooth_abs(x: Any, delta: float = 1e-8) -> Any:
    if delta <= 0.0:
        raise ValueError(f"delta must be strictly positive, got {delta!r}")
    if _any_torch(x):
        return torch.sqrt(x * x + delta * delta) - delta
    return np.sqrt(x * x + delta * delta) - delta


def _smooth_floor(x: Any, floor_val: float, beta: float) -> Any:
    return floor_val + _softplus(x - floor_val, beta)


def _smooth_cap(x: Any, cap_val: float, beta: float) -> Any:
    return cap_val - _softplus(cap_val - x, beta)


def _smooth_max(x: Any, gamma: float, axis: int) -> Any:
    if gamma <= 0.0:
        raise ValueError(f"gamma must be strictly positive, got {gamma!r}")
    if _any_torch(x):
        n = x.shape[axis]
        return (torch.logsumexp(gamma * x, dim=axis) - np.log(n)) / gamma
    n = x.shape[axis]
    m = np.max(x, axis=axis, keepdims=True)
    lse = np.squeeze(m, axis=axis) + np.log(np.sum(np.exp(gamma * (x - m)), axis=axis)) / gamma
    return lse - np.log(n) / gamma


def _normalize_axis(axis: int, ndim: int) -> int:
    if ndim < 1:
        raise ValueError("Input sequence must have at least 1 dimension")
    norm = axis if axis >= 0 else ndim + axis
    if norm < 0 or norm >= ndim:
        raise ValueError(f"time_axis {axis} out of range for {ndim}D input")
    return norm


def _reduce_mean(x: Any, axis: int | None) -> Any:
    if _any_torch(x):
        return torch.mean(x) if axis is None else torch.mean(x, dim=axis)
    return np.mean(x) if axis is None else np.mean(x, axis=axis)


def _reduce_sum(x: Any, axis: int | None) -> Any:
    if _any_torch(x):
        return torch.sum(x) if axis is None else torch.sum(x, dim=axis)
    return np.sum(x) if axis is None else np.sum(x, axis=axis)


def _exact_max(x: Any, axis: int | None) -> Any:
    if _any_torch(x):
        return torch.max(x) if axis is None else torch.max(x, dim=axis).values
    return np.max(x) if axis is None else np.max(x, axis=axis)


# ---------------------------------------------------------------------------
# 1. Chemical Degradation (Michalski-Martens Lifetime Multiplier)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChemicalRiskResult:
    """Differentiable chemical degradation summary based on Lifetime Multiplier."""

    lm_series: Any
    lm_equivalent: Any  # Harmonic mean: 1 / mean(1 / LM), matches chemical ageing dose
    lm_mean: Any        # Arithmetic mean reported in Martens (2012, Fig. 5.10, p. 103)
    dose_rate: Any      # Mean dimensionless chemical ageing rate: mean(1 / LM)


def chemical_lifetime_multiplier(
    temp_c: ArrayLike,
    rh_percent: ArrayLike,
    ea_j_per_mol: float = ACTIVATION_ENERGY_PAPER_J_MOL,
    *,
    min_rh_percent: float = 1.0,
    rh_floor_beta: float = 0.5,
) -> Any:
    """Compute instantaneous Lifetime Multiplier ``LM(T, RH)``.

    Formula (Martens 2012, Ch. 3, Eq. 3.2, p. 61 & Sec. 5.2.3, p. 103;
    Michalski 2002; HERIe Manual Sec. 3 Eq. 5):

    .. math::
        LM(T, \\mathrm{RH})
        = \\left(\\frac{50}{\\mathrm{RH}}\\right)^{1.3}
          \\exp\\!\\left[\\frac{E_a}{R}
          \\left(\\frac{1}{T + 273.15} - \\frac{1}{293.15}\\right)\\right]

    Parameters
    ----------
    temp_c:
        Air/object temperature [degC] (hourly temperature assumed uniform across
        museum objects per Martens 2012, p. 101).
    rh_percent:
        Relative humidity [%] — room air RH for paper/canvas (100 kJ/mol) or
        object surface RH for varnished panels/furniture/sculptures (70 kJ/mol).
    ea_j_per_mol:
        Activation energy in J/mol (``100_000`` for paper/cellulose, ``70_000``
        for varnish yellowing).
    min_rh_percent, rh_floor_beta:
        Smooth lower regularization preventing division by zero if an optimizer
        explores unphysical ``RH <= 0``. For ``RH >= 5%``, the smooth floor shift
        is ``< 2e-4 %`` (essentially exact at ``20 degC, 50% RH`` where ``LM = 1.0``).
    """
    if float(ea_j_per_mol) <= 0.0:
        raise ValueError(f"ea_j_per_mol must be positive, got {ea_j_per_mol!r}")
    use_torch = _any_torch(temp_c, rh_percent)
    ref = _find_ref_tensor(temp_c, rh_percent)
    t_c = _as_backend(temp_c, use_torch=use_torch, ref_tensor=ref)
    rh = _as_backend(rh_percent, use_torch=use_torch, ref_tensor=ref)

    rh_eff = _smooth_floor(rh, min_rh_percent, rh_floor_beta)
    # Subtract the negligible tail offset at RH = 50% so LM(20 degC, 50% RH) == 1.0 exactly.
    tail_50 = rh_floor_beta * np.log1p(np.exp(-(REFERENCE_RH_PERCENT - min_rh_percent) / rh_floor_beta))
    rh_ratio = (REFERENCE_RH_PERCENT + tail_50) / rh_eff

    t_k = _smooth_floor(t_c + 273.15, 150.0, 2.0)
    tail_t = 2.0 * np.log1p(np.exp(-(REFERENCE_TEMP_K - 150.0) / 2.0))
    t_k_ref = REFERENCE_TEMP_K + tail_t

    exponent = (float(ea_j_per_mol) / GAS_CONSTANT_J_MOL_K) * (1.0 / t_k - 1.0 / t_k_ref)
    if use_torch:
        return torch.pow(rh_ratio, LM_RH_EXPONENT) * torch.exp(exponent)
    return (rh_ratio ** LM_RH_EXPONENT) * np.exp(exponent)


def chemical_degradation_risk(
    temp_c: ArrayLike,
    rh_percent: ArrayLike,
    ea_j_per_mol: float = ACTIVATION_ENERGY_PAPER_J_MOL,
    *,
    time_axis: int = -1,
) -> ChemicalRiskResult:
    """Compute chemical Lifetime Multiplier trajectory and time-aggregated risk."""
    lm = chemical_lifetime_multiplier(temp_c, rh_percent, ea_j_per_mol=ea_j_per_mol)
    use_torch = _any_torch(lm)
    if (use_torch and lm.ndim == 0) or (not use_torch and np.asarray(lm).ndim == 0):
        dose = 1.0 / lm
        return ChemicalRiskResult(
            lm_series=lm,
            lm_equivalent=lm,
            lm_mean=lm,
            dose_rate=dose,
        )
    axis = _normalize_axis(time_axis, lm.ndim)
    dose = _reduce_mean(1.0 / lm, axis=axis)
    lm_eq = 1.0 / dose
    lm_mean = _reduce_mean(lm, axis=axis)
    return ChemicalRiskResult(
        lm_series=lm,
        lm_equivalent=lm_eq,
        lm_mean=lm_mean,
        dose_rate=dose,
    )


def chemical_lifetime_multiplier_grad_numpy(
    temp_c: ArrayLike,
    rh_percent: ArrayLike,
    ea_j_per_mol: float = ACTIVATION_ENERGY_PAPER_J_MOL,
    *,
    min_rh_percent: float = 1.0,
    rh_floor_beta: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Exact analytical derivatives ``(dLM/dtemp_c, dLM/drh_percent)`` in NumPy."""
    t_c = np.asarray(temp_c, dtype=np.float64)
    rh = np.asarray(rh_percent, dtype=np.float64)
    lm = np.asarray(
        chemical_lifetime_multiplier(
            t_c,
            rh,
            ea_j_per_mol=ea_j_per_mol,
            min_rh_percent=min_rh_percent,
            rh_floor_beta=rh_floor_beta,
        ),
        dtype=np.float64,
    )
    rh_eff = min_rh_percent + np.maximum(rh - min_rh_percent, 0.0) + rh_floor_beta * np.log1p(
        np.exp(-np.abs(rh - min_rh_percent) / rh_floor_beta)
    )
    sig_rh = np.asarray(_sigmoid(rh - min_rh_percent, rh_floor_beta), dtype=np.float64)

    t_k = 150.0 + np.maximum(t_c + 273.15 - 150.0, 0.0) + 2.0 * np.log1p(
        np.exp(-np.abs(t_c + 273.15 - 150.0) / 2.0)
    )
    sig_t = np.asarray(_sigmoid(t_c + 273.15 - 150.0, 2.0), dtype=np.float64)

    dlm_dt = -lm * (float(ea_j_per_mol) / GAS_CONSTANT_J_MOL_K) * sig_t / (t_k * t_k)
    dlm_drh = -lm * LM_RH_EXPONENT * sig_rh / rh_eff
    return dlm_dt, dlm_drh


# ---------------------------------------------------------------------------
# 2. Biological Degradation (Sedlbauer Isopleth / Germination Hazard + VTT)
# ---------------------------------------------------------------------------

def sedlbauer_lim_rh(
    temp_c: ArrayLike,
    substrate: str = "I",
    *,
    temp_beta: float = 0.5,
    rh_cap_beta: float = 0.5,
) -> Any:
    """Critical relative humidity boundary from Sedlbauer LIM curves [% RH].

    Analytical curve fitted to Sedlbauer et al. (2001, ASHRAE IAQ, Fig. 5) and
    Krus, Kilian & Sedlbauer (2007, *Museum Microclimates*, p. 186, Fig. 1)
    across ``0 <= T <= 30 degC``:

    .. math::
        \\mathrm{LIM}_c(T) = a_c + 23.32 \\exp\\!\\left(-\\frac{T_{\\mathrm{eff}}}{7.86}\\right)

    where ``a_0 = 69.19``, ``a_I = 74.19``, ``a_II = 78.39``. For ``T > 30 degC``
    ``T_eff`` smoothly saturates near ``30 degC`` (conservative warm-end plateau),
    and below freezing the output caps smoothly at ``100 %RH``.
    """
    if substrate not in SEDLBAUER_ASYMPTOTE_RH:
        raise ValueError(
            f"Unknown Sedlbauer substrate {substrate!r}; choose from {sorted(SEDLBAUER_ASYMPTOTE_RH)}"
        )
    use_torch = _any_torch(temp_c)
    t_c = _as_backend(temp_c, use_torch=use_torch, ref_tensor=_find_ref_tensor(temp_c))
    # Smoothly cap effective temperature at 30 degC (upper limit of Sedlbauer plot)
    t_eff = _smooth_cap(t_c, 30.0, temp_beta)
    a_c = SEDLBAUER_ASYMPTOTE_RH[substrate]
    if use_torch:
        raw_lim = a_c + SEDLBAUER_EXP_SCALE * torch.exp(-t_eff / SEDLBAUER_T0_C)
    else:
        raw_lim = a_c + SEDLBAUER_EXP_SCALE * np.exp(-t_eff / SEDLBAUER_T0_C)
    return _smooth_cap(raw_lim, 100.0, rh_cap_beta)


def vtt_critical_rh(temp_c: ArrayLike) -> Any:
    """Hukka & Viitanen (1999) VTT critical RH [% RH] for timber/wooden substrates.

    Exact equation from Hukka & Viitanen (1999, *Wood Sci. Technol.* 33(6):475-485):
    ``-0.00267 * T^3 + 0.160 * T^2 - 3.13 * T + 100.0`` for ``T <= 20 degC`` and
    ``80.0`` for ``T > 20 degC`` (clamped to ``[80, 100]``). Provided as a standard
    reference comparison alongside Sedlbauer's Substrate I curve.
    """
    use_torch = _any_torch(temp_c)
    t_c = _as_backend(temp_c, use_torch=use_torch, ref_tensor=_find_ref_tensor(temp_c))
    t_clipped = t_c.clamp(0.0, 20.0) if use_torch else np.clip(t_c, 0.0, 20.0)
    poly = -0.00267 * (t_clipped ** 3) + 0.160 * (t_clipped ** 2) - 3.13 * t_clipped + 100.0
    if use_torch:
        return torch.where(t_c <= 20.0, poly, torch.full_like(poly, 80.0))
    return np.where(t_c <= 20.0, poly, 80.0)


def mould_germination_rate(
    temp_c: ArrayLike,
    rh_percent: ArrayLike,
    substrate: str = "I",
    *,
    beta_rh: float = 1.0,
) -> Any:
    """Smooth hourly spore germination progress rate [1/hour] above Sedlbauer LIM.

    Calibrated to Sedlbauer Substrate I germination isopleths (Krus, Kilian &
    Sedlbauer 2007, p. 186, Fig. 1): ``+2% -> 16 d``, ``+4.5% -> 8 d``,
    ``+7% -> 4 d``, ``+10% -> 2 d``, ``+15% -> 1 d``. A cumulative integral over
    time of ``>= 1.0`` corresponds to predicted spore germination onset (Martens
    2012, Sec. 5.2.2, p. 102).
    """
    use_torch = _any_torch(temp_c, rh_percent)
    ref = _find_ref_tensor(temp_c, rh_percent)
    t_c = _as_backend(temp_c, use_torch=use_torch, ref_tensor=ref)
    rh = _as_backend(rh_percent, use_torch=use_torch, ref_tensor=ref)

    lim = sedlbauer_lim_rh(t_c, substrate=substrate)
    excess = _softplus(rh - lim, beta_rh)
    # Subtract the tiny baseline value at boundary so steady-state well below LIM
    # contributes ~0 (< 1e-12/year at 50% RH).
    gate = _sigmoid(rh - lim, beta_rh)
    return gate * (GERM_RATE_C1 * excess + GERM_RATE_C2 * (excess * excess))


@dataclass(frozen=True)
class BiologicalRiskResult:
    """Differentiable biological mould risk summary."""

    lim_rh: Any
    exceedance_rh_hours: Any      # Integral of softplus(RH - LIM) dt [%RH * h]
    exceedance_hours_smooth: Any  # Integral of sigmoid((RH - LIM)/beta) dt [h]
    germination_index: Any        # Cumulative dimensionless germination dose (>= 1: germination)
    exceedance_hours_exact: Any   # Exact non-smooth hours where RH > LIM(T)


def biological_mould_risk(
    temp_c: ArrayLike,
    rh_percent: ArrayLike,
    *,
    substrate: str = "I",
    dt_hours: float = 1.0,
    beta_rh: float = 1.0,
    time_axis: int = -1,
) -> BiologicalRiskResult:
    """Evaluate Sedlbauer LIM mould germination dose and exceedance metrics."""
    if float(dt_hours) <= 0.0:
        raise ValueError(f"dt_hours must be positive, got {dt_hours!r}")
    use_torch = _any_torch(temp_c, rh_percent)
    ref = _find_ref_tensor(temp_c, rh_percent)
    t_c = _as_backend(temp_c, use_torch=use_torch, ref_tensor=ref)
    rh = _as_backend(rh_percent, use_torch=use_torch, ref_tensor=ref)

    lim = sedlbauer_lim_rh(t_c, substrate=substrate)
    diff = rh - lim
    rh_excess = _softplus(diff, beta_rh)
    prob = _sigmoid(diff, beta_rh)
    rate = mould_germination_rate(t_c, rh, substrate=substrate, beta_rh=beta_rh)

    exact_ind = (diff > 0.0).to(dtype=rh.dtype) if use_torch else (diff > 0.0).astype(np.float64)

    if rh.ndim == 0:
        dt = float(dt_hours)
        return BiologicalRiskResult(
            lim_rh=lim,
            exceedance_rh_hours=rh_excess * dt,
            exceedance_hours_smooth=prob * dt,
            germination_index=rate * dt,
            exceedance_hours_exact=exact_ind * dt,
        )

    axis = _normalize_axis(time_axis, rh.ndim)
    dt = float(dt_hours)
    return BiologicalRiskResult(
        lim_rh=lim,
        exceedance_rh_hours=_reduce_sum(rh_excess, axis=axis) * dt,
        exceedance_hours_smooth=_reduce_sum(prob, axis=axis) * dt,
        germination_index=_reduce_sum(rate, axis=axis) * dt,
        exceedance_hours_exact=_reduce_sum(exact_ind, axis=axis) * dt,
    )


def biological_mould_vjp_numpy(
    grad_exceedance_rh_hours: ArrayLike,
    grad_germination_index: ArrayLike,
    temp_c: ArrayLike,
    rh_percent: ArrayLike,
    *,
    substrate: str = "I",
    dt_hours: float = 1.0,
    beta_rh: float = 1.0,
    time_axis: int = -1,
) -> tuple[np.ndarray, np.ndarray]:
    """Exact analytical VJP for :func:`biological_mould_risk` in NumPy."""
    t_c = np.asarray(temp_c, dtype=np.float64)
    rh = np.asarray(rh_percent, dtype=np.float64)
    dt = float(dt_hours)

    # Forward intermediates
    temp_beta = 0.5
    rh_cap_beta = 0.5
    t_eff = 30.0 - np.maximum(30.0 - t_c, 0.0) - temp_beta * np.log1p(
        np.exp(-np.abs(30.0 - t_c) / temp_beta)
    )
    a_c = SEDLBAUER_ASYMPTOTE_RH[substrate]
    raw_lim = a_c + SEDLBAUER_EXP_SCALE * np.exp(-t_eff / SEDLBAUER_T0_C)
    lim = np.asarray(sedlbauer_lim_rh(t_c, substrate=substrate), dtype=np.float64)

    # d(lim)/d(t_c):
    dt_eff_dtc = np.asarray(_sigmoid(30.0 - t_c, temp_beta), dtype=np.float64)
    draw_dt_eff = -(SEDLBAUER_EXP_SCALE / SEDLBAUER_T0_C) * np.exp(-t_eff / SEDLBAUER_T0_C)
    dlim_draw = np.asarray(_sigmoid(100.0 - raw_lim, rh_cap_beta), dtype=np.float64)
    dlim_dtc = dlim_draw * draw_dt_eff * dt_eff_dtc

    diff = rh - lim
    e = np.asarray(_softplus(diff, beta_rh), dtype=np.float64)
    p = np.asarray(_sigmoid(diff, beta_rh), dtype=np.float64)

    # Broadcast upstream gradients along time_axis
    g_exc = np.asarray(grad_exceedance_rh_hours, dtype=np.float64)
    g_germ = np.asarray(grad_germination_index, dtype=np.float64)
    if rh.ndim > 0:
        axis = _normalize_axis(time_axis, rh.ndim)
        if g_exc.ndim < rh.ndim:
            g_exc = np.expand_dims(g_exc, axis=axis)
        if g_germ.ndim < rh.ndim:
            g_germ = np.expand_dims(g_germ, axis=axis)
        g_exc = np.broadcast_to(g_exc, rh.shape)
        g_germ = np.broadcast_to(g_germ, rh.shape)

    de_ddiff = p
    dp_ddiff = p * (1.0 - p) / float(beta_rh)
    poly_e = GERM_RATE_C1 * e + GERM_RATE_C2 * e * e
    dpoly_de = GERM_RATE_C1 + 2.0 * GERM_RATE_C2 * e
    drate_ddiff = dp_ddiff * poly_e + p * dpoly_de * de_ddiff

    dloss_ddiff = dt * (g_exc * de_ddiff + g_germ * drate_ddiff)
    grad_rh = dloss_ddiff
    grad_t = -dloss_ddiff * dlim_dtc
    return grad_t, grad_rh


# ---------------------------------------------------------------------------
# 3. Mechanical Degradation & Proofed Fluctuations
# ---------------------------------------------------------------------------

def wood_equilibrium_strain(rh_percent: ArrayLike) -> Any:
    """Tangential moisture-related strain curve ``eps(RH)`` for wood [-].

    Smooth cubic isotherm calibrated to Mecklenburg, Tumosa & Erhardt (1998,
    pp. 467-468, Fig. 3a & Fig. 4a) and Martens (2012, Fig. 3.4, p. 55 & Fig. 3.5,
    p. 56) in the tangential (worst-case) grain direction:

    .. math::
        \\varepsilon(\\mathrm{RH})
        = c_1 x + c_2 x^2 + c_3 x^3, \\qquad x = \\frac{\\mathrm{RH} - 45}{50}.
    """
    use_torch = _any_torch(rh_percent)
    rh = _as_backend(rh_percent, use_torch=use_torch, ref_tensor=_find_ref_tensor(rh_percent))
    x = (rh - 45.0) / 50.0
    return WOOD_STRAIN_C1 * x + WOOD_STRAIN_C2 * (x * x) + WOOD_STRAIN_C3 * (x * x * x)


@dataclass(frozen=True)
class MechanicalRiskResult:
    """Differentiable hygroscopic mechanical strain & failure risk metrics."""

    strain: Any
    abs_strain: Any
    max_strain_ratio: Any
    exact_max_strain_ratio: Any
    yield_exceedance_fraction_smooth: Any
    failure_exceedance_fraction_smooth: Any
    yield_exceedance_fraction_exact: Any
    failure_exceedance_fraction_exact: Any


def mechanical_strain_risk(
    rh_primary: ArrayLike,
    rh_reference: ArrayLike | None = None,
    *,
    mode: str = "gradient",
    eps_yield: float = WOOD_YIELD_STRAIN_DEFAULT,
    eps_failure: float = WOOD_FAILURE_STRAIN_DEFAULT,
    smooth_abs_delta: float = 1e-8,
    smooth_beta_strain: float = 2e-4,
    smooth_max_gamma: float = 2500.0,
    time_axis: int = -1,
) -> MechanicalRiskResult:
    """Evaluate mechanical strain against yield and tensile-failure thresholds.

    Modes
    -----
    - ``mode="gradient"`` (``panel_painting``, ``wooden_sculpture``): compares
      ``rh_primary = rh_surface`` against ``rh_reference = rh_bulk`` per Martens
      (2012, Sec. 5.2.4, pp. 104-105, Fig. 5.11 & Fig. 5.14).
    - ``mode="acclimatized"`` (``wooden_furniture``): compares ``rh_primary = rh_bulk``
      against ``rh_reference = long_term_mean_rh`` (if ``rh_reference is None``,
      defaults to the mean of ``rh_primary`` along ``time_axis``) per Martens (2012,
      Sec. 5.2.4, p. 105, Fig. 5.13).
    """
    if float(eps_yield) <= 0.0 or float(eps_failure) <= 0.0:
        raise ValueError("eps_yield and eps_failure must be strictly positive")
    if mode not in ("gradient", "acclimatized"):
        raise ValueError(f"Unknown mode {mode!r}; expected 'gradient' or 'acclimatized'")

    use_torch = _any_torch(rh_primary, rh_reference)
    ref_t = _find_ref_tensor(rh_primary, rh_reference)
    rh_p = _as_backend(rh_primary, use_torch=use_torch, ref_tensor=ref_t)

    if rh_reference is None:
        if mode == "gradient":
            raise ValueError("rh_reference (rh_bulk) is required when mode='gradient'")
        if rh_p.ndim == 0:
            rh_r = rh_p
        else:
            ax = _normalize_axis(time_axis, rh_p.ndim)
            rh_r = (
                torch.mean(rh_p, dim=ax, keepdim=True)
                if use_torch
                else np.mean(rh_p, axis=ax, keepdims=True)
            )
    else:
        rh_r = _as_backend(rh_reference, use_torch=use_torch, ref_tensor=ref_t)

    strain = wood_equilibrium_strain(rh_p) - wood_equilibrium_strain(rh_r)
    abs_strain = _smooth_abs(strain, delta=smooth_abs_delta)
    # Tensile fracture happens on outer drying / contraction (strain < 0), Martens p. 104
    tensile_strain = -strain

    y_prob = _sigmoid(abs_strain - float(eps_yield), smooth_beta_strain)
    f_prob = _sigmoid(tensile_strain - float(eps_failure), smooth_beta_strain)

    exact_abs = torch.abs(strain) if use_torch else np.abs(strain)
    y_exact = (
        (exact_abs > float(eps_yield)).to(dtype=rh_p.dtype)
        if use_torch
        else (exact_abs > float(eps_yield)).astype(np.float64)
    )
    f_exact = (
        (tensile_strain > float(eps_failure)).to(dtype=rh_p.dtype)
        if use_torch
        else (tensile_strain > float(eps_failure)).astype(np.float64)
    )

    if rh_p.ndim == 0:
        return MechanicalRiskResult(
            strain=strain,
            abs_strain=abs_strain,
            max_strain_ratio=abs_strain / float(eps_yield),
            exact_max_strain_ratio=exact_abs / float(eps_yield),
            yield_exceedance_fraction_smooth=y_prob,
            failure_exceedance_fraction_smooth=f_prob,
            yield_exceedance_fraction_exact=y_exact,
            failure_exceedance_fraction_exact=f_exact,
        )

    axis = _normalize_axis(time_axis, rh_p.ndim)
    return MechanicalRiskResult(
        strain=strain,
        abs_strain=abs_strain,
        max_strain_ratio=_smooth_max(abs_strain, smooth_max_gamma, axis=axis) / float(eps_yield),
        exact_max_strain_ratio=_exact_max(exact_abs, axis=axis) / float(eps_yield),
        yield_exceedance_fraction_smooth=_reduce_mean(y_prob, axis=axis),
        failure_exceedance_fraction_smooth=_reduce_mean(f_prob, axis=axis),
        yield_exceedance_fraction_exact=_reduce_mean(y_exact, axis=axis),
        failure_exceedance_fraction_exact=_reduce_mean(f_exact, axis=axis),
    )


def _wood_strain_derivative_drh(rh_percent: np.ndarray) -> np.ndarray:
    """Derivative d(wood_equilibrium_strain)/d(RH) in pure NumPy."""
    x = (rh_percent - 45.0) / 50.0
    return (WOOD_STRAIN_C1 + 2.0 * WOOD_STRAIN_C2 * x + 3.0 * WOOD_STRAIN_C3 * x * x) / 50.0


def mechanical_strain_vjp_numpy(
    grad_max_strain_ratio: ArrayLike,
    grad_yield_fraction_smooth: ArrayLike,
    grad_failure_fraction_smooth: ArrayLike,
    rh_primary: ArrayLike,
    rh_reference: ArrayLike,
    *,
    eps_yield: float = WOOD_YIELD_STRAIN_DEFAULT,
    eps_failure: float = WOOD_FAILURE_STRAIN_DEFAULT,
    smooth_abs_delta: float = 1e-8,
    smooth_beta_strain: float = 2e-4,
    smooth_max_gamma: float = 2500.0,
    time_axis: int = -1,
) -> tuple[np.ndarray, np.ndarray]:
    """Exact analytical VJP w.r.t. ``(rh_primary, rh_reference)`` in NumPy."""
    rh_p = np.asarray(rh_primary, dtype=np.float64)
    rh_r = np.asarray(rh_reference, dtype=np.float64)
    strain = np.asarray(wood_equilibrium_strain(rh_p) - wood_equilibrium_strain(rh_r), dtype=np.float64)
    abs_strain = np.sqrt(strain * strain + smooth_abs_delta * smooth_abs_delta) - smooth_abs_delta
    dabs_ds = strain / np.sqrt(strain * strain + smooth_abs_delta * smooth_abs_delta)

    g_max = np.asarray(grad_max_strain_ratio, dtype=np.float64)
    g_y = np.asarray(grad_yield_fraction_smooth, dtype=np.float64)
    g_f = np.asarray(grad_failure_fraction_smooth, dtype=np.float64)

    y_p = np.asarray(_sigmoid(abs_strain - float(eps_yield), smooth_beta_strain), dtype=np.float64)
    f_p = np.asarray(_sigmoid(-strain - float(eps_failure), smooth_beta_strain), dtype=np.float64)
    dy_dabs = y_p * (1.0 - y_p) / float(smooth_beta_strain)
    df_ds = -f_p * (1.0 - f_p) / float(smooth_beta_strain)

    if rh_p.ndim == 0:
        dloss_ds = (g_max / float(eps_yield) + g_y * dy_dabs) * dabs_ds + g_f * df_ds
    else:
        axis = _normalize_axis(time_axis, rh_p.ndim)
        n_t = float(rh_p.shape[axis])
        if g_max.ndim < rh_p.ndim:
            g_max = np.expand_dims(g_max, axis=axis)
        if g_y.ndim < rh_p.ndim:
            g_y = np.expand_dims(g_y, axis=axis)
        if g_f.ndim < rh_p.ndim:
            g_f = np.expand_dims(g_f, axis=axis)
        g_max = np.broadcast_to(g_max, rh_p.shape)
        g_y = np.broadcast_to(g_y, rh_p.shape)
        g_f = np.broadcast_to(g_f, rh_p.shape)

        # Softmax weights for logsumexp derivative along time_axis
        shifted = smooth_max_gamma * (abs_strain - np.max(abs_strain, axis=axis, keepdims=True))
        exp_s = np.exp(shifted)
        sm_weights = exp_s / np.sum(exp_s, axis=axis, keepdims=True)
        dloss_ds = (g_max * sm_weights / float(eps_yield) + (g_y / n_t) * dy_dabs) * dabs_ds + (
            g_f / n_t
        ) * df_ds

    grad_p = dloss_ds * _wood_strain_derivative_drh(rh_p)
    grad_r_full = -dloss_ds * _wood_strain_derivative_drh(rh_r)
    # Sum over any axes where rh_reference was broadcast against rh_primary
    grad_r = grad_r_full
    while grad_r.ndim > rh_r.ndim:
        grad_r = grad_r.sum(axis=0)
    for ax, (so, st) in enumerate(zip(grad_r.shape, rh_r.shape)):
        if st == 1 and so != 1:
            grad_r = grad_r.sum(axis=ax, keepdims=True)
    return grad_p, grad_r.reshape(rh_r.shape)


@dataclass(frozen=True)
class ProofedEnvelope:
    """Historical proofed climate/strain bounds (Michalski 2007, pp. 11-15)."""

    rh_min: float
    rh_max: float
    strain_max: float


def estimate_proofed_envelope(
    rh_history: ArrayLike,
    *,
    rh_surface_history: ArrayLike | None = None,
    rh_bulk_history: ArrayLike | None = None,
) -> ProofedEnvelope:
    """Extract historical proofed bounds from observed museum climate history."""
    rh_arr = np.asarray(rh_history, dtype=np.float64)
    rh_min = float(np.min(rh_arr))
    rh_max = float(np.max(rh_arr))
    if rh_surface_history is not None and rh_bulk_history is not None:
        s_hist = wood_equilibrium_strain(np.asarray(rh_surface_history, dtype=np.float64)) - (
            wood_equilibrium_strain(np.asarray(rh_bulk_history, dtype=np.float64))
        )
        strain_max = float(np.max(np.abs(s_hist)))
    else:
        rh_mid = 0.5 * (rh_min + rh_max)
        strain_max = float(
            max(
                abs(wood_equilibrium_strain(rh_max) - wood_equilibrium_strain(rh_mid)),
                abs(wood_equilibrium_strain(rh_min) - wood_equilibrium_strain(rh_mid)),
            )
        )
    return ProofedEnvelope(rh_min=rh_min, rh_max=rh_max, strain_max=strain_max)


@dataclass(frozen=True)
class ProofedRiskResult:
    """Differentiable mechanical risk accounting for Michalski proofed fluctuations."""

    unproofed_rh_exceedance_hours: Any
    unproofed_fraction_smooth: Any
    unproofed_strain_exceedance: Any
    unproofed_fraction_exact: Any


def proofed_fluctuation_risk(
    rh_series: ArrayLike,
    *,
    rh_hist_min: float,
    rh_hist_max: float,
    strain_series: ArrayLike | None = None,
    proofed_strain_max: float | None = None,
    dt_hours: float = 1.0,
    beta_rh: float = 0.5,
    beta_strain: float = 2e-4,
    time_axis: int = -1,
) -> ProofedRiskResult:
    """Evaluate excess mechanical hazard beyond historical proofed fluctuations.

    Per Michalski (2007, pp. 11-15) and ``PLAN_ISCIENCE.md`` Section 5.3,
    fluctuations inside ``[rh_hist_min, rh_hist_max]`` (or within
    ``proofed_strain_max``) carry minimal excess risk of new fracture. Excursions
    beyond the historical proofed band are smoothly accumulated via ``softplus``.
    """
    if rh_hist_min > rh_hist_max:
        raise ValueError(f"Expected rh_hist_min <= rh_hist_max, got {(rh_hist_min, rh_hist_max)}")
    use_torch = _any_torch(rh_series, strain_series)
    ref_t = _find_ref_tensor(rh_series, strain_series)
    rh = _as_backend(rh_series, use_torch=use_torch, ref_tensor=ref_t)

    over_hi = _softplus(rh - float(rh_hist_max), beta_rh)
    over_lo = _softplus(float(rh_hist_min) - rh, beta_rh)
    band_exc = over_hi + over_lo
    prob = _sigmoid(rh - float(rh_hist_max), beta_rh) + _sigmoid(float(rh_hist_min) - rh, beta_rh)
    prob = prob.clamp(0.0, 1.0) if use_torch else np.clip(prob, 0.0, 1.0)

    out_exact = (rh > float(rh_hist_max)) | (rh < float(rh_hist_min))
    out_exact = out_exact.to(dtype=rh.dtype) if use_torch else out_exact.astype(np.float64)

    if strain_series is not None and proofed_strain_max is not None:
        s = _as_backend(strain_series, use_torch=use_torch, ref_tensor=ref_t)
        s_abs = _smooth_abs(s, 1e-8)
        s_exc = _softplus(s_abs - float(proofed_strain_max), beta_strain)
    else:
        s_exc = 0.0 * band_exc

    dt = float(dt_hours)
    if rh.ndim == 0:
        return ProofedRiskResult(
            unproofed_rh_exceedance_hours=band_exc * dt,
            unproofed_fraction_smooth=prob,
            unproofed_strain_exceedance=s_exc * dt,
            unproofed_fraction_exact=out_exact,
        )

    axis = _normalize_axis(time_axis, rh.ndim)
    return ProofedRiskResult(
        unproofed_rh_exceedance_hours=_reduce_sum(band_exc, axis=axis) * dt,
        unproofed_fraction_smooth=_reduce_mean(prob, axis=axis),
        unproofed_strain_exceedance=_reduce_sum(s_exc, axis=axis) * dt,
        unproofed_fraction_exact=_reduce_mean(out_exact, axis=axis),
    )


# ---------------------------------------------------------------------------
# 4. Metal / Bronze Corrosion Risk
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MetalRiskResult:
    """Differentiable metal/bronze critical-RH exceedance summary."""

    exceedance_hours_exact: Any
    exceedance_fraction_exact: Any
    exceedance_hours_smooth: Any
    exceedance_fraction_smooth: Any
    exceedance_rh_hours: Any


def metal_corrosion_risk(
    rh_air: ArrayLike,
    *,
    rh_crit: float = METAL_CRH_PRESETS["bronze_chloride"],
    dt_hours: float = 1.0,
    beta_rh: float = 1.0,
    time_axis: int = -1,
) -> MetalRiskResult:
    """Evaluate cumulative exceedance of critical RH for copper/bronze objects.

    Smooth relaxation replaces the discontinuous step indicator
    ``1[RH > rh_crit]`` with ``sigmoid((RH - rh_crit) / beta_rh)`` and adds
    ``softplus(RH - rh_crit; beta_rh)`` for severity-weighted gradient signal.
    """
    if float(dt_hours) <= 0.0:
        raise ValueError(f"dt_hours must be strictly positive, got {dt_hours!r}")
    use_torch = _any_torch(rh_air)
    rh = _as_backend(rh_air, use_torch=use_torch, ref_tensor=_find_ref_tensor(rh_air))
    diff = rh - float(rh_crit)

    prob = _sigmoid(diff, beta_rh)
    rh_exc = _softplus(diff, beta_rh)
    exact_ind = (diff > 0.0).to(dtype=rh.dtype) if use_torch else (diff > 0.0).astype(np.float64)
    dt = float(dt_hours)

    if rh.ndim == 0:
        return MetalRiskResult(
            exceedance_hours_exact=exact_ind * dt,
            exceedance_fraction_exact=exact_ind,
            exceedance_hours_smooth=prob * dt,
            exceedance_fraction_smooth=prob,
            exceedance_rh_hours=rh_exc * dt,
        )

    axis = _normalize_axis(time_axis, rh.ndim)
    return MetalRiskResult(
        exceedance_hours_exact=_reduce_sum(exact_ind, axis=axis) * dt,
        exceedance_fraction_exact=_reduce_mean(exact_ind, axis=axis),
        exceedance_hours_smooth=_reduce_sum(prob, axis=axis) * dt,
        exceedance_fraction_smooth=_reduce_mean(prob, axis=axis),
        exceedance_rh_hours=_reduce_sum(rh_exc, axis=axis) * dt,
    )


def metal_corrosion_vjp_numpy(
    grad_exceedance_hours_smooth: ArrayLike,
    grad_exceedance_rh_hours: ArrayLike,
    rh_air: ArrayLike,
    *,
    rh_crit: float = METAL_CRH_PRESETS["bronze_chloride"],
    dt_hours: float = 1.0,
    beta_rh: float = 1.0,
    time_axis: int = -1,
) -> np.ndarray:
    """Exact analytical gradient w.r.t. ``rh_air`` for :func:`metal_corrosion_risk`."""
    rh = np.asarray(rh_air, dtype=np.float64)
    diff = rh - float(rh_crit)
    p = np.asarray(_sigmoid(diff, beta_rh), dtype=np.float64)
    dp_drh = p * (1.0 - p) / float(beta_rh)

    g_hrs = np.asarray(grad_exceedance_hours_smooth, dtype=np.float64)
    g_rhh = np.asarray(grad_exceedance_rh_hours, dtype=np.float64)
    if rh.ndim > 0:
        axis = _normalize_axis(time_axis, rh.ndim)
        if g_hrs.ndim < rh.ndim:
            g_hrs = np.expand_dims(g_hrs, axis=axis)
        if g_rhh.ndim < rh.ndim:
            g_rhh = np.expand_dims(g_rhh, axis=axis)
        g_hrs = np.broadcast_to(g_hrs, rh.shape)
        g_rhh = np.broadcast_to(g_rhh, rh.shape)

    return float(dt_hours) * (g_hrs * dp_drh + g_rhh * p)
