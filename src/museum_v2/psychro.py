"""Differentiable moist-air psychrometric relations (PyTorch and NumPy backends).

Implements ASHRAE Handbook--Fundamentals (SI, Ch. 1) thermodynamic relations
paired with the Alduchov & Eskridge (1996, J. Appl. Meteorol. 35:601-609,
Eq. 21) Magnus saturation vapor pressure formulation so humidity ratio, relative
humidity, dew-point temperature, moist-air enthalpy, and latent heat of
vaporization remain C^infinity smooth and accurate within < 0.1% over 5-35 degC
and 10-90% RH.
"""
from __future__ import annotations

from typing import Any, Union

import numpy as np

try:
    import torch

    HAS_TORCH = True
except ImportError:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    HAS_TORCH = False

ArrayLike = Union[float, np.ndarray, "torch.Tensor"]

# Physical constants (ASHRAE Handbook--Fundamentals, Ch. 1, SI)
STANDARD_ATM_PRESSURE_PA: float = 101_325.0
GAS_RATIO_MW_MA: float = 0.621945  # M_water / M_dry_air = 18.01528 / 28.966
CP_DRY_AIR_J_KG_K: float = 1006.0
CP_VAPOR_J_KG_K: float = 1860.0
H_FG0_J_KG: float = 2_501_000.0
LATENT_SLOPE_J_KG_K: float = 2381.0
R_DRY_AIR_J_KG_K: float = 287.055
VAPOR_DENSITY_RATIO: float = 1.6078  # R_v / R_da = 1 / 0.621945

# Alduchov & Eskridge (1996) Eq. 21 Magnus coefficients over liquid water (-40 to +50 C)
MAGNUS_A_PA: float = 610.94
MAGNUS_B: float = 17.625
MAGNUS_C_C: float = 243.04


def _any_torch(*values: Any) -> bool:
    return HAS_TORCH and any(isinstance(v, torch.Tensor) for v in values if v is not None)


def _find_ref_tensor(*values: Any) -> Any:
    if not HAS_TORCH:
        return None
    for v in values:
        if isinstance(v, torch.Tensor):
            return v
    return None


def _as_backend(val: ArrayLike, *, use_torch: bool, ref_tensor: Any = None) -> Any:
    if use_torch:
        if isinstance(val, torch.Tensor):
            if ref_tensor is not None and (val.device != ref_tensor.device or val.dtype != ref_tensor.dtype):
                return val.to(device=ref_tensor.device, dtype=ref_tensor.dtype)
            return val
        dtype = ref_tensor.dtype if ref_tensor is not None else torch.float64
        device = ref_tensor.device if ref_tensor is not None else None
        return torch.as_tensor(val, dtype=dtype, device=device)
    return np.asarray(val, dtype=np.float64)


def _softplus_pos(x: Any, beta: float) -> Any:
    """Smooth approximation to max(x, 0) using softplus with scale ``beta > 0``."""
    b = float(beta)
    if _any_torch(x):
        return torch.nn.functional.softplus(x / b) * b
    z = np.asarray(x, dtype=np.float64) / b
    return b * (np.maximum(z, 0.0) + np.log1p(np.exp(-np.abs(z))))


def _smooth_floor(x: Any, floor_val: float, beta: float) -> Any:
    return float(floor_val) + _softplus_pos(x - float(floor_val), beta)


def _smooth_cap(x: Any, cap_val: float, beta: float) -> Any:
    return float(cap_val) - _softplus_pos(float(cap_val) - x, beta)


def saturation_vapor_pressure(temp_c: ArrayLike) -> Any:
    """Saturation vapor pressure over liquid water [Pa] via Alduchov-Eskridge (1996)."""
    use_torch = _any_torch(temp_c)
    t_c = _as_backend(temp_c, use_torch=use_torch, ref_tensor=_find_ref_tensor(temp_c))
    # Smoothly protect against unphysical temperatures approaching -243 C
    t_safe = _smooth_floor(t_c, -60.0, 2.0)
    exponent = MAGNUS_B * t_safe / (t_safe + MAGNUS_C_C)
    if use_torch:
        return MAGNUS_A_PA * torch.exp(exponent)
    return MAGNUS_A_PA * np.exp(exponent)


def humidity_ratio_from_temp_rh(
    temp_c: ArrayLike,
    rh_percent: ArrayLike,
    pressure_pa: ArrayLike = STANDARD_ATM_PRESSURE_PA,
) -> Any:
    """Compute humidity ratio ``W`` [kg_water / kg_dry_air] from ``(T [degC], RH [%])``."""
    use_torch = _any_torch(temp_c, rh_percent, pressure_pa)
    ref = _find_ref_tensor(temp_c, rh_percent, pressure_pa)
    t_c = _as_backend(temp_c, use_torch=use_torch, ref_tensor=ref)
    rh = _as_backend(rh_percent, use_torch=use_torch, ref_tensor=ref)
    p = _as_backend(pressure_pa, use_torch=use_torch, ref_tensor=ref)

    p_ws = saturation_vapor_pressure(t_c)
    p_w_raw = (rh / 100.0) * p_ws
    # Keep vapor partial pressure smoothly bounded inside (0, 0.99 * P)
    p_w = _smooth_cap(_smooth_floor(p_w_raw, 0.0, 1e-3), 0.99 * p, 50.0)
    # Subtract zero-floor offset at physical inputs? Notice 1e-3 * ln(1 + exp(-x/1e-3)) < 1e-90 for p_w >= 1 Pa
    return GAS_RATIO_MW_MA * p_w / (p - p_w)


def rh_from_temp_w(
    temp_c: ArrayLike,
    w: ArrayLike,
    pressure_pa: ArrayLike = STANDARD_ATM_PRESSURE_PA,
    *,
    clip_upper: bool = False,
) -> Any:
    """Compute relative humidity ``RH [%]`` from dry-bulb ``T [degC]`` and humidity ratio ``W``."""
    use_torch = _any_torch(temp_c, w, pressure_pa)
    ref = _find_ref_tensor(temp_c, w, pressure_pa)
    t_c = _as_backend(temp_c, use_torch=use_torch, ref_tensor=ref)
    w_arr = _as_backend(w, use_torch=use_torch, ref_tensor=ref)
    p = _as_backend(pressure_pa, use_torch=use_torch, ref_tensor=ref)

    w_safe = _smooth_floor(w_arr, 0.0, 1e-7)
    p_ws = saturation_vapor_pressure(t_c)
    p_w = (w_safe * p) / (GAS_RATIO_MW_MA + w_safe)
    rh = 100.0 * p_w / p_ws
    if clip_upper:
        return _smooth_cap(rh, 100.0, 0.5)
    return rh


def dew_point_from_w(
    w: ArrayLike,
    pressure_pa: ArrayLike = STANDARD_ATM_PRESSURE_PA,
) -> Any:
    """Invert Magnus formula to compute smooth dew-point temperature ``T_dp [degC]``."""
    use_torch = _any_torch(w, pressure_pa)
    ref = _find_ref_tensor(w, pressure_pa)
    w_arr = _as_backend(w, use_torch=use_torch, ref_tensor=ref)
    p = _as_backend(pressure_pa, use_torch=use_torch, ref_tensor=ref)

    w_safe = _smooth_floor(w_arr, 1e-5, 1e-6)
    p_w = (w_safe * p) / (GAS_RATIO_MW_MA + w_safe)
    p_w_safe = _smooth_floor(p_w, 10.0, 2.0)
    alpha = torch.log(p_w_safe / MAGNUS_A_PA) if use_torch else np.log(p_w_safe / MAGNUS_A_PA)
    # Cap alpha below MAGNUS_B - 1.0 to avoid singularity at high pressure/humidity
    alpha_safe = _smooth_cap(alpha, MAGNUS_B - 1.0, 0.1)
    return MAGNUS_C_C * alpha_safe / (MAGNUS_B - alpha_safe)


def moist_air_enthalpy_j_per_kg(temp_c: ArrayLike, w: ArrayLike) -> Any:
    """Moist-air specific enthalpy ``h [J / kg_dry_air]`` relative to 0 degC dry air."""
    use_torch = _any_torch(temp_c, w)
    ref = _find_ref_tensor(temp_c, w)
    t_c = _as_backend(temp_c, use_torch=use_torch, ref_tensor=ref)
    w_arr = _as_backend(w, use_torch=use_torch, ref_tensor=ref)
    return CP_DRY_AIR_J_KG_K * t_c + w_arr * (H_FG0_J_KG + CP_VAPOR_J_KG_K * t_c)


def latent_heat_vaporization_j_per_kg(temp_c: ArrayLike) -> Any:
    """Specific latent heat of water vaporization ``h_fg(T) [J / kg_water]``."""
    use_torch = _any_torch(temp_c)
    t_c = _as_backend(temp_c, use_torch=use_torch, ref_tensor=_find_ref_tensor(temp_c))
    return H_FG0_J_KG - LATENT_SLOPE_J_KG_K * t_c


def moist_air_density_kg_m3(
    temp_c: ArrayLike,
    w: ArrayLike,
    pressure_pa: ArrayLike = STANDARD_ATM_PRESSURE_PA,
) -> Any:
    """Dry-air partial density ``rho_da [kg_dry_air / m^3]`` from ideal-gas mixture law."""
    use_torch = _any_torch(temp_c, w, pressure_pa)
    ref = _find_ref_tensor(temp_c, w, pressure_pa)
    t_c = _as_backend(temp_c, use_torch=use_torch, ref_tensor=ref)
    w_arr = _as_backend(w, use_torch=use_torch, ref_tensor=ref)
    p = _as_backend(pressure_pa, use_torch=use_torch, ref_tensor=ref)
    t_k = _smooth_floor(t_c + 273.15, 200.0, 2.0)
    return p / (R_DRY_AIR_J_KG_K * t_k * (1.0 + VAPOR_DENSITY_RATIO * _smooth_floor(w_arr, 0.0, 1e-6)))
