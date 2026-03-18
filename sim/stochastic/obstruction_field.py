"""Ground-truth obstruction-field models for attenuation experiments.

This module defines deterministic spatial loss patterns used as simulated
ground truth when evaluating model-based dimensioning methods.

Supported obstruction patterns:
- centered square (high-loss square at beam center),
- vertical bands (alternating high-loss strips),
- multiple circles (union of several high-loss disks).

All patterns apply an additive *loss magnitude* in dB inside obstructed regions.
Because PRB mapping uses natural-log shadowing ``G = ln(S)``, dB loss is
converted to a negative shift in ``G`` using:

    delta_log = -(ln(10)/10) * extra_loss_db
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

import numpy as np

from sim.stochastic.user_locations import CircularBeam


PatternKind = Literal["square_center", "vertical_bands", "multi_circles"]


@dataclass(frozen=True)
class ObstructionFieldSpec:
    """Specification of one deterministic obstruction-field scenario.

    Fields:
        pattern_kind:
            Obstruction geometry to apply in the circular beam.
        extra_loss_db:
            Additional attenuation magnitude (in dB) applied inside obstructed
            regions. Must be non-negative.
        base_log_shadowing:
            Baseline natural-log shadowing value outside obstruction regions.
        square_area_fraction:
            For ``square_center`` pattern only. Target square area fraction of
            full beam area (e.g., 0.5 means square area is ~50% of beam area).
        vertical_band_count:
            For ``vertical_bands`` pattern only. Number of vertical bands across
            beam diameter. Obstruction is applied to alternating bands.
        multi_circle_count:
            For ``multi_circles`` pattern only. Number of obstructed circles.
            One circle is placed at center; remaining circles are placed on a
            ring around center.
        multi_circle_radius_ratio:
            Circle radius as a fraction of beam radius.
        multi_circle_ring_ratio:
            Ring radius (for non-central circles) as a fraction of beam radius.
    """

    pattern_kind: PatternKind
    extra_loss_db: float
    base_log_shadowing: float = 0.0
    square_area_fraction: float = 0.5
    vertical_band_count: int = 6
    multi_circle_count: int = 4
    multi_circle_radius_ratio: float = 0.22
    multi_circle_ring_ratio: float = 0.52

    def __post_init__(self) -> None:
        if self.extra_loss_db < 0.0:
            raise ValueError("extra_loss_db must be non-negative")
        if self.square_area_fraction <= 0.0 or self.square_area_fraction > 1.0:
            raise ValueError("square_area_fraction must be in (0, 1]")
        if self.vertical_band_count <= 0:
            raise ValueError("vertical_band_count must be positive")
        if self.multi_circle_count <= 0:
            raise ValueError("multi_circle_count must be positive")
        if self.multi_circle_radius_ratio <= 0.0:
            raise ValueError("multi_circle_radius_ratio must be positive")
        if self.multi_circle_ring_ratio < 0.0:
            raise ValueError("multi_circle_ring_ratio must be non-negative")
        # Keep non-central circles inside the beam when using ring placement.
        if self.multi_circle_ring_ratio + self.multi_circle_radius_ratio > 1.0:
            raise ValueError(
                "multi_circle_ring_ratio + multi_circle_radius_ratio must be <= 1.0"
            )


def evaluate_obstruction_log_shadowing(
    *,
    user_locations: np.ndarray,
    beam: CircularBeam,
    spec: ObstructionFieldSpec,
) -> np.ndarray:
    """Evaluate deterministic ground-truth log-shadowing at user locations.

    Args:
        user_locations:
            Array of shape ``(n_users, 2)`` with sampled user positions.
        beam:
            Circular beam specification used by PPP trial generation.
        spec:
            Obstruction-field scenario parameters.

    Returns:
        Array of shape ``(n_users,)`` with natural-log shadowing values ``G``.

    Interpretation:
    - Outside obstruction regions: ``G = base_log_shadowing``.
    - Inside obstruction regions: ``G`` is reduced by a dB-derived loss shift.
    """

    x = np.asarray(user_locations, dtype=float)
    if x.ndim != 2 or x.shape[1] != 2:
        raise ValueError("user_locations must have shape (n_users, 2)")
    if x.shape[0] == 0:
        return np.empty(0, dtype=float)

    # Start with baseline log-shadowing everywhere.
    g = np.full(x.shape[0], float(spec.base_log_shadowing), dtype=float)

    # Convert positive dB loss magnitude into a negative shift in ln scale.
    loss_shift_log = (math.log(10.0) / 10.0) * spec.extra_loss_db
    if loss_shift_log == 0.0:
        return g

    # Build obstruction mask per selected pattern.
    if spec.pattern_kind == "square_center":
        mask = _mask_square_center(x, beam, spec.square_area_fraction)
    elif spec.pattern_kind == "vertical_bands":
        mask = _mask_vertical_bands(x, beam, spec.vertical_band_count)
    elif spec.pattern_kind == "multi_circles":
        mask = _mask_multi_circles(
            x,
            beam,
            circle_count=spec.multi_circle_count,
            circle_radius_ratio=spec.multi_circle_radius_ratio,
            ring_ratio=spec.multi_circle_ring_ratio,
        )
    else:
        raise ValueError(f"unsupported pattern_kind: {spec.pattern_kind}")

    # Apply extra attenuation (lower G) only on obstructed locations.
    g[mask] -= loss_shift_log
    return g


def _mask_square_center(
    user_locations: np.ndarray,
    beam: CircularBeam,
    square_area_fraction: float,
) -> np.ndarray:
    """Return mask for centered-square obstruction."""

    target_area = square_area_fraction * beam.area
    side = math.sqrt(target_area)
    half = side / 2.0

    x = user_locations[:, 0]
    y = user_locations[:, 1]
    return (
        np.abs(x - beam.x_center) <= half
    ) & (np.abs(y - beam.y_center) <= half)


def _mask_vertical_bands(
    user_locations: np.ndarray,
    beam: CircularBeam,
    band_count: int,
) -> np.ndarray:
    """Return mask for alternating vertical-band obstruction pattern.

    Bands partition the x-range ``[x_center - R, x_center + R]`` into equal
    strips. Obstruction is applied on even-index bands (0,2,4,...).
    """

    left = beam.x_center - beam.radius
    diameter = 2.0 * beam.radius
    # Normalize x into [0, 1] across beam diameter and map to band index.
    u = (user_locations[:, 0] - left) / diameter
    band_index = np.floor(u * band_count).astype(int)
    band_index = np.clip(band_index, 0, band_count - 1)
    return (band_index % 2) == 0


def _mask_multi_circles(
    user_locations: np.ndarray,
    beam: CircularBeam,
    *,
    circle_count: int,
    circle_radius_ratio: float,
    ring_ratio: float,
) -> np.ndarray:
    """Return mask for union of multiple circular obstructions."""

    circle_radius = circle_radius_ratio * beam.radius
    ring_radius = ring_ratio * beam.radius

    centers: list[tuple[float, float]] = [(beam.x_center, beam.y_center)]
    remaining = circle_count - 1
    if remaining > 0:
        for k in range(remaining):
            theta = 2.0 * math.pi * (k / remaining)
            centers.append(
                (
                    beam.x_center + ring_radius * math.cos(theta),
                    beam.y_center + ring_radius * math.sin(theta),
                )
            )

    x = user_locations[:, 0]
    y = user_locations[:, 1]
    mask = np.zeros(user_locations.shape[0], dtype=bool)
    for cx, cy in centers:
        dx = x - cx
        dy = y - cy
        mask |= (dx * dx + dy * dy) <= (circle_radius * circle_radius)
    return mask

