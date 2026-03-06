"""PRB-demand model for log-shadowing-driven dimensioning experiments.

This module implements the capped integer-demand mapping used in the paper:

    SNR(x) = SNR0 * exp(G(x))
    eta_eff(x) = max(eta_min, log2(1 + SNR(x)))
    N_RB(x) = ceil(c / (W_RB * eta_eff(x)))

with the implied cap:

    N_RB(x) <= ceil(c / (W_RB * eta_min)).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class PRBDemandParams:
    """Parameters for per-user PRB-demand computation."""

    required_rate_bps: float
    rb_bandwidth_hz: float
    snr0_linear: float
    eta_min: float

    def __post_init__(self) -> None:
        if self.required_rate_bps <= 0.0:
            raise ValueError("required_rate_bps must be positive")
        if self.rb_bandwidth_hz <= 0.0:
            raise ValueError("rb_bandwidth_hz must be positive")
        if self.snr0_linear <= 0.0:
            raise ValueError("snr0_linear must be positive")
        if self.eta_min <= 0.0:
            raise ValueError("eta_min must be positive")

    @property
    def max_prb_per_user(self) -> int:
        """Maximum PRB demand implied by the eta_min cap."""
        return int(math.ceil(self.required_rate_bps / (self.rb_bandwidth_hz * self.eta_min)))


def prb_demand_from_log_shadowing(
    log_shadowing: Sequence[float] | np.ndarray,
    *,
    params: PRBDemandParams,
) -> np.ndarray:
    """Compute capped integer PRB demand per user.

    Args:
        log_shadowing: Per-user natural-log shadowing values G(x)=ln(S(x)).
        params: PRB-demand model parameters.

    Returns:
        Integer NumPy array of per-user PRB demands.
    """

    g = np.asarray(log_shadowing, dtype=float)
    if g.ndim != 1:
        raise ValueError("log_shadowing must be a 1D sequence")
    if g.size == 0:
        raise ValueError("log_shadowing must be non-empty")

    snr = params.snr0_linear * np.exp(g)
    spectral_eff = np.log2(1.0 + snr)
    eta_eff = np.maximum(params.eta_min, spectral_eff)

    raw_prb = params.required_rate_bps / (params.rb_bandwidth_hz * eta_eff)
    demand = np.ceil(raw_prb).astype(int)

    max_prb = params.max_prb_per_user
    demand = np.clip(demand, 1, max_prb)
    return demand


def total_prb_demand(
    per_user_prb: Sequence[int] | np.ndarray,
    *,
    user_weights: Sequence[int] | np.ndarray | None = None,
) -> int:
    """Aggregate total PRB demand with optional per-user weights.

    Args:
        per_user_prb: Integer PRB demands per sampled user.
        user_weights: Optional positive integer weights per user.

    Returns:
        Integer total PRB demand.
    """

    prb = np.asarray(per_user_prb, dtype=int)
    if prb.ndim != 1:
        raise ValueError("per_user_prb must be a 1D sequence")
    if prb.size == 0:
        raise ValueError("per_user_prb must be non-empty")
    if np.any(prb <= 0):
        raise ValueError("per_user_prb values must be positive")

    if user_weights is None:
        return int(prb.sum())

    w = np.asarray(user_weights, dtype=int)
    if w.ndim != 1:
        raise ValueError("user_weights must be a 1D sequence")
    if w.size != prb.size:
        raise ValueError("user_weights length must match per_user_prb length")
    if np.any(w <= 0):
        raise ValueError("user_weights values must be positive")

    return int(np.dot(prb, w))

