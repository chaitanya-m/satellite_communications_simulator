"""PRB-demand model for log-shadowing-driven dimensioning experiments.

This module implements the capped integer-demand mapping used in the paper:

    range_factor(x) = (d(x) / h)^(-gamma)   if pathloss is enabled
                    = 1                      otherwise
    SNR(x) = SNR0 * range_factor(x) * exp(G(x))
    eta_eff(x) = max(eta_min, log2(1 + SNR(x)))
    N_RB(x) = ceil(c / (W_RB * eta_eff(x)))

with the implied cap:

    N_RB(x) <= ceil(c / (W_RB * eta_min)).

Why this exists:
    Shadowing generators produce per-user log-shadowing values ``G``. Those are
    not directly usable for outage dimensioning until we map them to per-user
    PRB demand and aggregate over users. This module provides that mapping.

Conventions:
    - ``G = ln(S)`` where ``S`` is multiplicative shadowing in linear scale.
    - ``G`` can be negative (attenuation, ``S<1``) or positive (gain, ``S>1``).
    - ``snr0_linear`` is the reference SNR when ``G=0`` (that is ``S=1``).
      Example: ``snr0_linear=1.0`` means reference SNR = 1 (0 dB).
    - if pathloss is enabled, ``d(x) = sqrt(h^2 + r(x)^2)`` is the user slant
      range under altitude ``h`` and horizontal beam-center offset ``r(x)``,
      while ``gamma`` is the pathloss exponent.
    - the pathloss term is normalized by ``h`` so that at beam center
      (``r=0 -> d=h``) we still have ``range_factor = 1`` and therefore
      ``SNR = snr0_linear * exp(G)`` at that reference point.

Practical modeling note:
    ``eta_min`` is a minimum spectral-efficiency floor used to avoid unbounded
    PRB demand at very low SNR. This corresponds to a practical floor from
    robust MCS behavior and creates a finite per-user demand cap.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class PRBDemandParams:
    """Parameters for per-user PRB-demand computation.

    Fields:
        required_rate_bps: Target user rate to be supported (bits/s).
        rb_bandwidth_hz: Bandwidth represented by one PRB (Hz).
        snr0_linear: Reference SNR at ``G=0`` (no shadowing gain/loss).
        eta_min: Minimum spectral-efficiency floor (bits/s/Hz).
        pathloss_exponent:
            Optional distance-decay exponent ``gamma``. Use ``0.0`` to disable
            explicit distance-based pathloss in this simplified model.
        satellite_altitude_units:
            Altitude ``h`` used in the normalized slant-range term. The unit is
            intentionally abstract here; the experiments can interpret it as km,
            m, or any other consistent length scale.
    """

    required_rate_bps: float
    rb_bandwidth_hz: float
    snr0_linear: float
    eta_min: float
    pathloss_exponent: float = 0.0
    satellite_altitude_units: float | None = None

    def __post_init__(self) -> None:
        if self.required_rate_bps <= 0.0:
            raise ValueError("required_rate_bps must be positive")
        if self.rb_bandwidth_hz <= 0.0:
            raise ValueError("rb_bandwidth_hz must be positive")
        if self.snr0_linear <= 0.0:
            raise ValueError("snr0_linear must be positive")
        if self.eta_min <= 0.0:
            raise ValueError("eta_min must be positive")
        if self.pathloss_exponent < 0.0:
            raise ValueError("pathloss_exponent must be non-negative")
        if self.satellite_altitude_units is not None and self.satellite_altitude_units <= 0.0:
            raise ValueError("satellite_altitude_units must be positive when provided")
        if self.pathloss_exponent > 0.0 and self.satellite_altitude_units is None:
            raise ValueError(
                "satellite_altitude_units must be provided when pathloss_exponent > 0"
            )

    @property
    def max_prb_per_user(self) -> int:
        """Maximum PRB demand implied by the ``eta_min`` floor.

        If a user's effective spectral efficiency falls to ``eta_min``, this
        is the largest demand that can be assigned by the capped model.
        """
        return int(math.ceil(self.required_rate_bps / (self.rb_bandwidth_hz * self.eta_min)))


def prb_demand_from_log_shadowing(
    log_shadowing: Sequence[float] | np.ndarray,
    *,
    params: PRBDemandParams,
    user_locations: Sequence[Sequence[float]] | np.ndarray | None = None,
    beam_center_xy: tuple[float, float] = (0.0, 0.0),
) -> np.ndarray:
    """Compute capped integer PRB demand per user.

    Args:
        log_shadowing: Per-user natural-log shadowing values ``G=ln(S)``.
        params: PRB-demand model parameters.
        user_locations:
            Optional user coordinates of shape ``(n_users, 2)``. Required when
            explicit pathloss is enabled in ``params``.
        beam_center_xy:
            Horizontal reference point used for the slant-range computation.
            By default the beam is assumed centered at the origin.

    Returns:
        Integer NumPy array of per-user PRB demands.

    Why this is needed:
        End-to-end outage experiments require integer per-user PRB demands so
        they can be summed and compared against candidate RB budgets.
        This function converts sampled field values to that scheduler-facing
        demand quantity.
    """

    # Convert to a dense float vector for vectorized math.
    g = np.asarray(log_shadowing, dtype=float)
    # Expect one log-shadowing value per sampled user.
    if g.ndim != 1:
        raise ValueError("log_shadowing must be a 1D sequence")
    # Empty input is rejected because demand is undefined without users.
    if g.size == 0:
        raise ValueError("log_shadowing must be non-empty")

    if params.pathloss_exponent > 0.0:
        if user_locations is None:
            raise ValueError("user_locations must be provided when pathloss is enabled")
        xy = np.asarray(user_locations, dtype=float)
        if xy.ndim != 2 or xy.shape[1] != 2:
            raise ValueError("user_locations must have shape (n_users, 2)")
        if xy.shape[0] != g.size:
            raise ValueError("user_locations length must match log_shadowing length")
        dx = xy[:, 0] - float(beam_center_xy[0])
        dy = xy[:, 1] - float(beam_center_xy[1])
        horizontal_distance = np.sqrt(dx * dx + dy * dy)
        altitude = float(params.satellite_altitude_units)
        slant_range = np.sqrt((altitude * altitude) + (horizontal_distance * horizontal_distance))
        range_factor = (slant_range / altitude) ** (-params.pathloss_exponent)
    else:
        range_factor = 1.0

    # Map log-shadowing to SNR using the normalized slant-range term.
    snr = params.snr0_linear * range_factor * np.exp(g)
    # Shannon-like spectral efficiency in bits/s/Hz.
    spectral_eff = np.log2(1.0 + snr)
    # Apply practical floor to avoid unbounded demand in deep fades.
    eta_eff = np.maximum(params.eta_min, spectral_eff)

    # Continuous PRB requirement before integer scheduling.
    raw_prb = params.required_rate_bps / (params.rb_bandwidth_hz * eta_eff)
    # Scheduler uses integer PRBs, so round up.
    demand = np.ceil(raw_prb).astype(int)

    # Enforce finite per-user cap implied by eta_min.
    max_prb = params.max_prb_per_user
    # Also enforce minimum 1 PRB for any active user in this model.
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
        user_weights: Optional positive integer weights per sampled user.
            Use this when a sampled user represents multiple population users
            (for example, 1 sampled user standing in for 1000 users).

    Returns:
        Integer total PRB demand.

    Why this is needed:
        Some experiments run on sampled users for tractability. Weighted
        aggregation recovers a population-scale total demand estimate.
    """

    # Convert to dense integer vector and validate shape/content.
    prb = np.asarray(per_user_prb, dtype=int)
    if prb.ndim != 1:
        raise ValueError("per_user_prb must be a 1D sequence")
    if prb.size == 0:
        raise ValueError("per_user_prb must be non-empty")
    if np.any(prb <= 0):
        raise ValueError("per_user_prb values must be positive")

    # Unweighted case: sampled users are treated as one-to-one.
    if user_weights is None:
        return int(prb.sum())

    # Weighted case: each sampled user contributes multiple represented users.
    w = np.asarray(user_weights, dtype=int)
    if w.ndim != 1:
        raise ValueError("user_weights must be a 1D sequence")
    if w.size != prb.size:
        raise ValueError("user_weights length must match per_user_prb length")
    if np.any(w <= 0):
        raise ValueError("user_weights values must be positive")

    # Population-scale total via weighted sum.
    return int(np.dot(prb, w))
