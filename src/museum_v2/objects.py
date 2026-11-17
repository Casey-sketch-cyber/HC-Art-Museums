"""Differentiable first-order hygroscopic RH response model for museum objects.

Implements the museum object microclimate response model described in
``docs/PLAN_ISCIENCE.md`` Section 5.2 and Task ``S2.2``, parameterized strictly
from primary conservation literature recorded in ``configs/objects.yaml``.

Continuous-time model
---------------------
For each response channel (``surface`` or ``bulk``) of an object category with
1/e step-response time constant :math:`\\tau > 0` [hours]:

.. math::
    \\tau \\frac{d\\,\\mathrm{RH}_{\\mathrm{obj}}(t)}{dt}
    = \\mathrm{RH}_{\\mathrm{air}}(t) - \\mathrm{RH}_{\\mathrm{obj}}(t)

Exact zero-order-hold (ZOH) discretization over step :math:`\\Delta t` [hours]:

.. math::
    \\mathrm{RH}_{\\mathrm{obj}}[k]
    = \\alpha\\,\\mathrm{RH}_{\\mathrm{obj}}[k-1] + (1 - \\alpha)\\,\\mathrm{RH}_{\\mathrm{air}}[k],
    \\qquad \\alpha = \\exp\\!\\left(-\\frac{\\Delta t}{\\tau}\\right).

Time-constant convention
------------------------
Here :math:`\\tau` is the standard ``1 - 1/e`` (63.212056%) step-response time
constant (matching ``kupczak2018herie``). Martens (2012, Ch. 5, Sec. 5.2.1,
pp. 98-99, Eq. 5.2, and Definitions, p. 170) reports 95% step-response times
:math:`t_{95}` via ``a = exp(-3 * dt / t_95)``, giving the exact equivalence
``tau = t_95 / 3``.

Backends
--------
Supports both ``torch.Tensor`` (preserving computation graph and supporting
``torch.autograd`` gradients w.r.t. ``rh_air``, ``tau_hours``, and ``rh_init``)
and ``numpy.ndarray`` (with an exact analytical reverse-mode VJP helper
``first_order_lowpass_vjp`` so environments without PyTorch can verify both
forward dynamics and exact gradients).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, NamedTuple, Union

import numpy as np
import yaml

try:
    import torch
    import torch.nn as nn

    HAS_TORCH = True
except ImportError:  # pragma: no cover - tested in torch-less environments
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    HAS_TORCH = False

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OBJECTS_CONFIG = ROOT / "configs" / "objects.yaml"

ArrayLike = Union[np.ndarray, "torch.Tensor", float, int, list, tuple]


class ObjectResponse(NamedTuple):
    """Surface and bulk relative humidity experienced by a museum object."""

    surface: Any
    bulk: Any


@dataclass(frozen=True)
class TimeConstantSpec:
    """Verified time-constant entry loaded from ``configs/objects.yaml``."""

    tau_hours: float
    reported_value: float
    reported_unit: str
    reported_hours: float
    reported_definition: str
    conversion_formula: str
    bib_key: str
    document: str
    pages: str
    table_or_figure: str


@dataclass(frozen=True)
class ObjectSpec:
    """Museum object category specification with surface/bulk time constants."""

    name: str
    label_en: str
    label_zh: str
    description: str
    surface: TimeConstantSpec
    bulk: TimeConstantSpec
    notes: str = ""
    field_corroboration: dict[str, Any] | None = None


def martens_t95_to_tau(t95_hours: float) -> float:
    """Convert a Martens (2012) 95% response time ``t_95`` [h] to ``tau`` [h].

    Martens (2012, Eq. 5.2, p. 99) uses ``a = exp(-3 * dt / t_95)``, whereas the
    standard 1 - 1/e (63.2%) time constant uses ``alpha = exp(-dt / tau)``.
    Equating exponents yields ``tau = t_95 / 3``.
    """
    value = float(t95_hours)
    if value <= 0.0:
        raise ValueError(f"t95_hours must be positive, got {t95_hours!r}")
    return value / 3.0


def load_objects_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load the raw ``configs/objects.yaml`` dictionary."""
    path = Path(config_path) if config_path is not None else DEFAULT_OBJECTS_CONFIG
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, Mapping) or "objects" not in data:
        raise ValueError(f"Invalid objects configuration in {path}")
    return dict(data)


def _parse_time_constant(raw: Mapping[str, Any]) -> TimeConstantSpec:
    return TimeConstantSpec(
        tau_hours=float(raw["tau_hours"]),
        reported_value=float(raw["reported_value"]),
        reported_unit=str(raw["reported_unit"]),
        reported_hours=float(raw["reported_hours"]),
        reported_definition=str(raw["reported_definition"]),
        conversion_formula=str(raw["conversion_formula"]),
        bib_key=str(raw["bib_key"]),
        document=str(raw["document"]),
        pages=str(raw["pages"]),
        table_or_figure=str(raw["table_or_figure"]),
    )


def load_object_specs(
    config_path: str | Path | None = None,
) -> dict[str, ObjectSpec]:
    """Load all verified object specifications keyed by category name."""
    raw = load_objects_config(config_path)
    specs: dict[str, ObjectSpec] = {}
    for name, entry in raw["objects"].items():
        specs[name] = ObjectSpec(
            name=name,
            label_en=str(entry["label_en"]),
            label_zh=str(entry["label_zh"]),
            description=str(entry["description"]).strip(),
            surface=_parse_time_constant(entry["surface"]),
            bulk=_parse_time_constant(entry["bulk"]),
            notes=str(entry.get("notes", "")).strip(),
            field_corroboration=entry.get("field_corroboration"),
        )
    return specs


def get_object_spec(
    category: str,
    config_path: str | Path | None = None,
) -> ObjectSpec:
    """Return the :class:`ObjectSpec` for a configured category name."""
    specs = load_object_specs(config_path)
    if category not in specs:
        available = ", ".join(sorted(specs))
        raise KeyError(
            f"Unknown or unverified object category {category!r}. "
            f"Available configured categories: [{available}]"
        )
    return specs[category]


def list_omitted_categories(
    config_path: str | Path | None = None,
) -> dict[str, dict[str, str]]:
    """Return documented candidate categories omitted for lack of verifiable taus."""
    raw = load_objects_config(config_path)
    omitted = raw.get("omitted_categories", {})
    return {str(k): dict(v) for k, v in omitted.items()}


def _is_torch_tensor(value: Any) -> bool:
    return HAS_TORCH and isinstance(value, torch.Tensor)


def _any_torch_tensor(*values: Any) -> bool:
    return HAS_TORCH and any(isinstance(v, torch.Tensor) for v in values if v is not None)


def _normalize_axis(axis: int, ndim: int) -> int:
    if ndim < 1:
        raise ValueError("rh_air must have at least 1 dimension (the time axis)")
    norm = axis if axis >= 0 else ndim + axis
    if norm < 0 or norm >= ndim:
        raise ValueError(f"time_axis {axis} out of range for {ndim}D input")
    return norm


def _prepare_torch_param(
    value: Any,
    ref: "torch.Tensor",
    *,
    name: str,
) -> "torch.Tensor":
    if isinstance(value, torch.Tensor):
        out = value.to(device=ref.device, dtype=ref.dtype)
    else:
        out = torch.as_tensor(value, device=ref.device, dtype=ref.dtype)
    if name in ("tau_hours", "dt_hours") and torch.any(out <= 0):
        raise ValueError(f"{name} must be strictly positive")
    return out


def _prepare_numpy_param(
    value: Any,
    dtype: np.dtype,
    *,
    name: str,
) -> np.ndarray:
    out = np.asarray(value, dtype=dtype)
    if name in ("tau_hours", "dt_hours") and np.any(out <= 0):
        raise ValueError(f"{name} must be strictly positive")
    return out


def _broadcast_init_shape_numpy(
    rh_init: np.ndarray,
    batch_shape: tuple[int, ...],
) -> np.ndarray:
    """Broadcast ``rh_init`` to ``(*batch_shape, 1)`` along moved time axis."""
    if rh_init.ndim == 0:
        return np.broadcast_to(rh_init, batch_shape)[..., np.newaxis]
    if rh_init.shape == batch_shape:
        return rh_init[..., np.newaxis]
    if rh_init.shape == (*batch_shape, 1):
        return rh_init
    return np.broadcast_to(rh_init, batch_shape)[..., np.newaxis]


def _broadcast_init_shape_torch(
    rh_init: "torch.Tensor",
    batch_shape: tuple[int, ...],
) -> "torch.Tensor":
    """Broadcast ``rh_init`` to ``(*batch_shape, 1)`` along moved time axis."""
    if rh_init.ndim == 0:
        return rh_init.expand(batch_shape).unsqueeze(-1)
    if tuple(rh_init.shape) == batch_shape:
        return rh_init.unsqueeze(-1)
    if tuple(rh_init.shape) == (*batch_shape, 1):
        return rh_init
    return rh_init.expand(batch_shape).unsqueeze(-1)


def _validate_tau_broad_shape(
    alpha_shape: tuple[int, ...],
    batch_shape: tuple[int, ...],
) -> tuple[int, ...]:
    """Validate and return alpha broadcast shape compatible with ``batch_shape``."""
    try:
        return tuple(np.broadcast_shapes(alpha_shape, batch_shape))
    except ValueError as exc:
        raise ValueError(
            f"tau_hours shape {alpha_shape} cannot broadcast with spatial/batch shape {batch_shape}"
        ) from exc


def _lowpass_torch_last_axis(
    u: "torch.Tensor",
    alpha: "torch.Tensor",
    rh_init: Any,
) -> "torch.Tensor":
    """Hillis-Steele associative scan for ``y[k] = alpha * y[k-1] + (1 - alpha) * u[k]``."""
    t_len = u.shape[-1]
    batch_shape = tuple(u.shape[:-1])
    if alpha.ndim > 0:
        _validate_tau_broad_shape(tuple(alpha.shape), batch_shape)
        alpha = alpha.expand(batch_shape).unsqueeze(-1)
    else:
        alpha = alpha.reshape((1,) * len(batch_shape) + (1,))

    y_init = (
        u[..., :1]
        if rh_init is None
        else _broadcast_init_shape_torch(
            _prepare_torch_param(rh_init, u, name="rh_init"),
            batch_shape,
        )
    )

    if t_len == 0:
        return u.clone()

    # Exact recurrence starting from k = 0:
    #   y[0] = alpha * y_init + (1 - alpha) * u[0]
    #   y[k] = alpha * y[k-1] + (1 - alpha) * u[k], k >= 1
    b_seq = (1.0 - alpha) * u
    b0 = b_seq[..., :1] + alpha * y_init
    if t_len == 1:
        return b0

    b_cur = torch.cat([b0, b_seq[..., 1:]], dim=-1)
    a_cur = alpha.expand(*batch_shape, t_len)

    stride = 1
    while stride < t_len:
        a_right = a_cur[..., stride:]
        b_next_tail = a_right * b_cur[..., :-stride] + b_cur[..., stride:]
        a_next_tail = a_right * a_cur[..., :-stride]
        b_cur = torch.cat([b_cur[..., :stride], b_next_tail], dim=-1)
        a_cur = torch.cat([a_cur[..., :stride], a_next_tail], dim=-1)
        stride *= 2
    return b_cur


def _lowpass_numpy_last_axis(
    u: np.ndarray,
    alpha: np.ndarray,
    rh_init: Any,
) -> np.ndarray:
    """Hillis-Steele associative scan in NumPy for exact ZOH first-order low-pass."""
    t_len = u.shape[-1]
    batch_shape = u.shape[:-1]
    if alpha.ndim > 0:
        _validate_tau_broad_shape(alpha.shape, batch_shape)
        alpha_b = np.broadcast_to(alpha, batch_shape)[..., np.newaxis]
    else:
        alpha_b = alpha.reshape((1,) * len(batch_shape) + (1,))

    y_init = (
        u[..., :1]
        if rh_init is None
        else _broadcast_init_shape_numpy(
            _prepare_numpy_param(rh_init, u.dtype, name="rh_init"),
            batch_shape,
        )
    )

    if t_len == 0:
        return u.copy()

    b_seq = (1.0 - alpha_b) * u
    b0 = b_seq[..., :1] + alpha_b * y_init
    if t_len == 1:
        return b0.copy()

    b_cur = np.concatenate([b0, b_seq[..., 1:]], axis=-1)
    a_cur = np.broadcast_to(alpha_b, (*batch_shape, t_len)).copy()

    stride = 1
    while stride < t_len:
        b_next = b_cur.copy()
        a_next = a_cur.copy()
        a_right = a_cur[..., stride:]
        b_next[..., stride:] = a_right * b_cur[..., :-stride] + b_cur[..., stride:]
        a_next[..., stride:] = a_right * a_cur[..., :-stride]
        b_cur = b_next
        a_cur = a_next
        stride *= 2
    return b_cur


def first_order_lowpass(
    rh_air: ArrayLike,
    tau_hours: ArrayLike,
    dt_hours: float = 1.0,
    rh_init: ArrayLike | None = None,
    time_axis: int = -1,
) -> Any:
    """Apply exact ZOH first-order low-pass hygroscopic filtering along ``time_axis``.

    Parameters
    ----------
    rh_air:
        Ambient/zone air relative humidity sequence (scalar-like rejected; >=1D).
        Can be ``np.ndarray``, Python sequence, or ``torch.Tensor``.
    tau_hours:
        Object 1/e (63.2%) step-response time constant in hours (``> 0``). Must
        be scalar or broadcastable with the non-time shape of ``rh_air``.
    dt_hours:
        Simulation step duration in hours (``> 0``), default ``1.0``.
    rh_init:
        Optional initial object RH at step ``k = -1`` (immediately before
        ``rh_air[0]``). If ``None`` (default), the object is assumed in hygric
        equilibrium with ``rh_air[0]``, so ``rh_obj[0] == rh_air[0]``.
    time_axis:
        Axis of ``rh_air`` corresponding to time. Default ``-1``.

    Returns
    -------
    np.ndarray or torch.Tensor
        Filtered object RH sequence with the same shape (and backend/dtype) as
        ``rh_air``.
    """
    use_torch = _any_torch_tensor(rh_air, tau_hours, rh_init)
    if use_torch:
        if isinstance(rh_air, torch.Tensor):
            u = rh_air
            if not u.is_floating_point():
                u = u.to(dtype=torch.float32)
        else:
            ref_tensor = (
                tau_hours if isinstance(tau_hours, torch.Tensor) else rh_init
            )
            u = torch.as_tensor(
                rh_air, device=ref_tensor.device, dtype=ref_tensor.dtype
            )
            if not u.is_floating_point():
                u = u.to(dtype=torch.float32)

        axis = _normalize_axis(time_axis, u.ndim)
        tau_t = _prepare_torch_param(tau_hours, u, name="tau_hours")
        dt_t = _prepare_torch_param(dt_hours, u, name="dt_hours")
        alpha = torch.exp(-dt_t / tau_t)

        u_moved = torch.movedim(u, axis, -1)
        y_moved = _lowpass_torch_last_axis(u_moved, alpha, rh_init)
        return torch.movedim(y_moved, -1, axis)

    u_np = np.asarray(rh_air)
    if not np.issubdtype(u_np.dtype, np.floating):
        u_np = u_np.astype(np.float64)
    axis = _normalize_axis(time_axis, u_np.ndim)
    tau_np = _prepare_numpy_param(tau_hours, u_np.dtype, name="tau_hours")
    dt_np = _prepare_numpy_param(dt_hours, u_np.dtype, name="dt_hours")
    alpha_np = np.exp(-dt_np / tau_np)

    u_moved = np.moveaxis(u_np, axis, -1)
    y_moved = _lowpass_numpy_last_axis(u_moved, alpha_np, rh_init)
    return np.moveaxis(y_moved, -1, axis)


def first_order_lowpass_vjp(
    grad_output: ArrayLike,
    rh_air: ArrayLike,
    tau_hours: ArrayLike,
    dt_hours: float = 1.0,
    rh_init: ArrayLike | None = None,
    time_axis: int = -1,
) -> tuple[Any, Any, Any]:
    """Exact reverse-mode VJP of :func:`first_order_lowpass`.

    Given ``g = dL / d(y)``, returns ``(grad_rh_air, grad_tau_hours, grad_rh_init)``.
    Works in pure NumPy (for torch-free environments) and delegates to
    ``torch.autograd`` if Torch tensors are supplied.
    """
    if _any_torch_tensor(grad_output, rh_air, tau_hours, rh_init):
        u = (
            rh_air.detach().clone()
            if isinstance(rh_air, torch.Tensor)
            else torch.as_tensor(rh_air, dtype=torch.float64)
        ).requires_grad_(True)
        tau_t = (
            tau_hours.detach().clone()
            if isinstance(tau_hours, torch.Tensor)
            else torch.as_tensor(tau_hours, device=u.device, dtype=u.dtype)
        ).requires_grad_(True)
        init_t = None
        if rh_init is not None:
            init_t = (
                rh_init.detach().clone()
                if isinstance(rh_init, torch.Tensor)
                else torch.as_tensor(rh_init, device=u.device, dtype=u.dtype)
            ).requires_grad_(True)
        g_t = (
            grad_output
            if isinstance(grad_output, torch.Tensor)
            else torch.as_tensor(grad_output, device=u.device, dtype=u.dtype)
        )
        y = first_order_lowpass(
            u, tau_t, dt_hours=dt_hours, rh_init=init_t, time_axis=time_axis
        )
        inputs = [u, tau_t] + ([init_t] if init_t is not None else [])
        grads = torch.autograd.grad(y, inputs, grad_outputs=g_t)
        return grads[0], grads[1], (grads[2] if init_t is not None else None)

    u_np = np.asarray(rh_air)
    dtype = u_np.dtype if np.issubdtype(u_np.dtype, np.floating) else np.float64
    u_np = np.asarray(u_np, dtype=dtype)
    g_np = np.asarray(grad_output, dtype=dtype)
    if u_np.shape != g_np.shape:
        raise ValueError(
            f"grad_output shape {g_np.shape} does not match rh_air shape {u_np.shape}"
        )

    axis = _normalize_axis(time_axis, u_np.ndim)
    tau_np = _prepare_numpy_param(tau_hours, dtype, name="tau_hours")
    dt_np = _prepare_numpy_param(dt_hours, dtype, name="dt_hours")
    alpha_scalar_or_arr = np.exp(-dt_np / tau_np)

    u_m = np.moveaxis(u_np, axis, -1)
    g_m = np.moveaxis(g_np, axis, -1)
    t_len = u_m.shape[-1]
    batch_shape = u_m.shape[:-1]

    if alpha_scalar_or_arr.ndim > 0:
        _validate_tau_broad_shape(alpha_scalar_or_arr.shape, batch_shape)
        alpha_b = np.broadcast_to(alpha_scalar_or_arr, batch_shape)[..., np.newaxis]
        tau_b = np.broadcast_to(tau_np, batch_shape)[..., np.newaxis]
    else:
        alpha_b = alpha_scalar_or_arr.reshape((1,) * len(batch_shape) + (1,))
        tau_b = tau_np.reshape((1,) * len(batch_shape) + (1,))

    y_m = _lowpass_numpy_last_axis(u_m, alpha_scalar_or_arr, rh_init)

    # Adjoint recurrence (reverse in time):
    #   lam[T-1] = g[T-1]
    #   lam[k]   = alpha * lam[k+1] + g[k],  k = T-2 .. 0
    # Reversing g along time reduces this to an associative scan with a = alpha, b = g_rev!
    g_rev = g_m[..., ::-1]
    a_rev = np.broadcast_to(alpha_b, (*batch_shape, t_len)).copy()
    b_rev = g_rev.copy()
    stride = 1
    while stride < t_len:
        b_next = b_rev.copy()
        a_next = a_rev.copy()
        a_right = a_rev[..., stride:]
        b_next[..., stride:] = a_right * b_rev[..., :-stride] + b_rev[..., stride:]
        a_next[..., stride:] = a_right * a_rev[..., :-stride]
        b_rev = b_next
        a_rev = a_next
        stride *= 2
    lam_m = b_rev[..., ::-1]

    grad_u_m = (1.0 - alpha_b) * lam_m
    if rh_init is None:
        # y[-1] == u[0] contributes alpha * lam[0] through y[0]
        grad_u_m = grad_u_m.copy()
        grad_u_m[..., :1] += alpha_b * lam_m[..., :1]
        grad_init = None
    else:
        raw_grad_init = alpha_b * lam_m[..., 0:1]
        init_arr = _prepare_numpy_param(rh_init, dtype, name="rh_init")
        grad_init = _unbroadcast_numpy(raw_grad_init[..., 0], init_arr.shape)

    # Forward sensitivity w.r.t. alpha:
    #   dy[0]/dalpha     = y[-1] - u[0]
    #   dy[k]/dalpha_raw = y[k-1] - u[k]  (local forced increment)
    # Sum over time weighted by lam[k], times d(alpha)/d(tau) = alpha * dt / tau^2.
    if rh_init is None:
        y_prev_first = u_m[..., :1]
    else:
        init_arr = _prepare_numpy_param(rh_init, dtype, name="rh_init")
        y_prev_first = _broadcast_init_shape_numpy(init_arr, batch_shape)
    y_prev_m = np.concatenate([y_prev_first, y_m[..., :-1]], axis=-1) if t_len > 1 else y_prev_first
    grad_alpha_full = np.sum(lam_m * (y_prev_m - u_m), axis=-1, keepdims=True)
    grad_tau_full = grad_alpha_full * alpha_b * (dt_np / (tau_b ** 2))
    grad_tau = _unbroadcast_numpy(grad_tau_full[..., 0], tau_np.shape)

    grad_u = np.moveaxis(grad_u_m, -1, axis)
    return grad_u, grad_tau, grad_init


def _unbroadcast_numpy(arr: np.ndarray, target_shape: tuple[int, ...]) -> np.ndarray:
    """Sum ``arr`` over dimensions that were broadcast from ``target_shape``."""
    out = arr
    while out.ndim > len(target_shape):
        out = out.sum(axis=0)
    for ax, (s_out, s_tgt) in enumerate(zip(out.shape, target_shape)):
        if s_tgt == 1 and s_out != 1:
            out = out.sum(axis=ax, keepdims=True)
    return out.reshape(target_shape)


def compute_object_response(
    rh_air: ArrayLike,
    category: str | ObjectSpec,
    dt_hours: float = 1.0,
    rh_init_surface: ArrayLike | None = None,
    rh_init_bulk: ArrayLike | None = None,
    time_axis: int = -1,
    tau_scale: float = 1.0,
    config_path: str | Path | None = None,
) -> ObjectResponse:
    """Compute surface and bulk RH time series for one configured object category.

    Parameters
    ----------
    rh_air:
        Zone air relative humidity trajectory (1D or batched N-D array/tensor).
    category:
        Object category key in ``configs/objects.yaml`` (e.g., ``panel_painting``,
        ``wooden_sculpture``, ``wooden_furniture``) or a pre-loaded
        :class:`ObjectSpec`.
    dt_hours:
        Timestep size in hours (default ``1.0``).
    rh_init_surface, rh_init_bulk:
        Optional initial surface/bulk RH prior to ``rh_air[0]``. Default ``None``
        initializes at hygric equilibrium with ``rh_air[0]``.
    time_axis:
        Axis representing time in ``rh_air`` (default ``-1``).
    tau_scale:
        Multiplicative sensitivity factor on time constants (e.g. ``0.5`` or
        ``2.0`` for Section 5.7 sensitivity analysis). Default ``1.0``.
    config_path:
        Optional alternative YAML path overriding ``configs/objects.yaml``.
    """
    spec = (
        category
        if isinstance(category, ObjectSpec)
        else get_object_spec(category, config_path=config_path)
    )
    if float(tau_scale) <= 0.0:
        raise ValueError(f"tau_scale must be strictly positive, got {tau_scale!r}")

    tau_surf = spec.surface.tau_hours * float(tau_scale)
    tau_bulk = spec.bulk.tau_hours * float(tau_scale)

    surf = first_order_lowpass(
        rh_air,
        tau_hours=tau_surf,
        dt_hours=dt_hours,
        rh_init=rh_init_surface,
        time_axis=time_axis,
    )
    if tau_bulk == tau_surf and rh_init_bulk is rh_init_surface:
        # Coated furniture where intact lacquer forces surface == bulk beneath coating.
        bulk = surf.clone() if _is_torch_tensor(surf) else surf.copy()
    else:
        bulk = first_order_lowpass(
            rh_air,
            tau_hours=tau_bulk,
            dt_hours=dt_hours,
            rh_init=rh_init_bulk,
            time_axis=time_axis,
        )
    return ObjectResponse(surface=surf, bulk=bulk)


def compute_all_object_responses(
    rh_air: ArrayLike,
    categories: list[str] | tuple[str, ...] | None = None,
    dt_hours: float = 1.0,
    time_axis: int = -1,
    tau_scale: float = 1.0,
    config_path: str | Path | None = None,
) -> dict[str, ObjectResponse]:
    """Evaluate object responses for multiple (or all configured) categories."""
    specs = load_object_specs(config_path)
    chosen = list(specs.keys()) if categories is None else list(categories)
    return {
        cat: compute_object_response(
            rh_air,
            specs[cat] if cat in specs else cat,
            dt_hours=dt_hours,
            time_axis=time_axis,
            tau_scale=tau_scale,
            config_path=config_path,
        )
        for cat in chosen
    }


_BaseModule = nn.Module if HAS_TORCH else object


class ObjectResponseModel(_BaseModule):
    """Differentiable object RH response layer for simulation and control pipelines.

    Subclasses ``torch.nn.Module`` when PyTorch is available (making it directly
    composable with A-layer ROM rollout and DPC/MPC policies in Tasks S1.1, S3.3,
    S4.2) while remaining usable in pure NumPy environments without PyTorch.
    """

    def __init__(
        self,
        category: str,
        dt_hours: float = 1.0,
        tau_scale: float = 1.0,
        learnable_tau: bool = False,
        config_path: str | Path | None = None,
    ) -> None:
        if HAS_TORCH:
            super().__init__()
        self.spec = get_object_spec(category, config_path=config_path)
        self.category = self.spec.name
        if float(dt_hours) <= 0.0:
            raise ValueError(f"dt_hours must be strictly positive, got {dt_hours!r}")
        if float(tau_scale) <= 0.0:
            raise ValueError(f"tau_scale must be strictly positive, got {tau_scale!r}")
        self.dt_hours = float(dt_hours)
        self.tau_scale = float(tau_scale)
        self.learnable_tau = bool(learnable_tau)

        surf_tau = self.spec.surface.tau_hours * self.tau_scale
        bulk_tau = self.spec.bulk.tau_hours * self.tau_scale

        if HAS_TORCH:
            log_surf = torch.tensor(np.log(surf_tau), dtype=torch.float64)
            log_bulk = torch.tensor(np.log(bulk_tau), dtype=torch.float64)
            if self.learnable_tau:
                self.log_tau_surface = nn.Parameter(log_surf)
                self.log_tau_bulk = nn.Parameter(log_bulk)
            else:
                self.register_buffer("log_tau_surface", log_surf)
                self.register_buffer("log_tau_bulk", log_bulk)
        else:
            self.log_tau_surface = float(np.log(surf_tau))
            self.log_tau_bulk = float(np.log(bulk_tau))

    @property
    def tau_surface_hours(self) -> Any:
        if HAS_TORCH:
            return torch.exp(self.log_tau_surface)
        return float(np.exp(self.log_tau_surface))

    @property
    def tau_bulk_hours(self) -> Any:
        if HAS_TORCH:
            return torch.exp(self.log_tau_bulk)
        return float(np.exp(self.log_tau_bulk))

    def forward(
        self,
        rh_air: ArrayLike,
        rh_init_surface: ArrayLike | None = None,
        rh_init_bulk: ArrayLike | None = None,
        time_axis: int = -1,
    ) -> ObjectResponse:
        """Forward pass returning :class:`ObjectResponse` ``(surface, bulk)``."""
        if _any_torch_tensor(rh_air, rh_init_surface, rh_init_bulk):
            tau_s = self.tau_surface_hours
            tau_b = self.tau_bulk_hours
        else:
            tau_s = float(self.spec.surface.tau_hours * self.tau_scale)
            tau_b = float(self.spec.bulk.tau_hours * self.tau_scale)
            if HAS_TORCH:
                tau_s = float(self.tau_surface_hours.detach().cpu().item())
                tau_b = float(self.tau_bulk_hours.detach().cpu().item())

        surf = first_order_lowpass(
            rh_air,
            tau_hours=tau_s,
            dt_hours=self.dt_hours,
            rh_init=rh_init_surface,
            time_axis=time_axis,
        )
        bulk = first_order_lowpass(
            rh_air,
            tau_hours=tau_b,
            dt_hours=self.dt_hours,
            rh_init=rh_init_bulk,
            time_axis=time_axis,
        )
        return ObjectResponse(surface=surf, bulk=bulk)

    def __call__(
        self,
        rh_air: ArrayLike,
        rh_init_surface: ArrayLike | None = None,
        rh_init_bulk: ArrayLike | None = None,
        time_axis: int = -1,
    ) -> ObjectResponse:
        if HAS_TORCH:
            return super().__call__(
                rh_air,
                rh_init_surface=rh_init_surface,
                rh_init_bulk=rh_init_bulk,
                time_axis=time_axis,
            )
        return self.forward(
            rh_air,
            rh_init_surface=rh_init_surface,
            rh_init_bulk=rh_init_bulk,
            time_axis=time_axis,
        )
