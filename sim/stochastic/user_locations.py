"""PPP user-location trial generator for attenuation experiments.

This module provides a minimal, reusable primitive for step (1) of the
experiment workflow: generating user positions for one trial.

Model:
- Users follow a homogeneous planar Poisson point process (PPP).
- The beam footprint is modeled as a 2D circle.
- User count is Poisson with mean ``lambda_intensity * area``.
- Conditional on count, user positions are iid uniform in that circle.

Homogeneous-PPP note:
- This construction is exact for a homogeneous spatial PPP.
- One can either sample the PPP on the whole plane and keep only the points
  that fall inside the beam, or directly sample a Poisson point count in the
  beam and then place that many points iid uniformly in the beam.
- Those two constructions give the same point-process distribution inside the
  beam region.

Why this exists:
- Shadowing generators (uniform / Gaussian) require per-trial user locations.
- End-to-end outage comparison loops need a single function that returns those
  locations with deterministic seed control.
"""

from __future__ import annotations

from dataclasses import dataclass
import random

import numpy as np

from sim.stochastic.poisson import sample_poisson


@dataclass(frozen=True)
class CircularBeam:
    """Circular beam footprint in 2D.

    Coordinates are generic spatial axes (for example x/y in km or meters). The
    same unit is reused by the Gaussian correlation length parameter.
    """

    x_center: float
    y_center: float
    radius: float

    def __post_init__(self) -> None:
        if self.radius <= 0.0:
            raise ValueError("radius must be positive")

    @property
    def area(self) -> float:
        """Return beam area in squared coordinate units."""

        return float(np.pi * self.radius * self.radius)


def sample_user_locations_ppp(
    *,
    lambda_intensity: float,
    beam: CircularBeam,
    rng: random.Random,
) -> np.ndarray:
    """Sample one PPP user-location realization in a circular beam.

    Args:
        lambda_intensity: User intensity per unit area (not total count).
        beam: Circular beam footprint.
        rng: Python RNG controlling reproducibility.

    Returns:
        NumPy array with shape ``(n_users, 2)``. Each row is one sampled user
        position ``[x, y]``.

    Homogeneous-PPP note:
        This function is exact only for a homogeneous spatial PPP. For that
        model, "sample on the plane then crop to the beam" is equivalent to
        "sample a Poisson count in the beam and then place that many points iid
        uniformly in the beam". This function uses the second form because it
        is simpler and more efficient on a bounded beam footprint.

    Why this is needed:
        The comparison experiments repeatedly require fresh user positions per
        trial. This function isolates that logic so it can be reused and tested
        independently from shadowing and PRB-demand code.

    Experiment implication:
        Larger ``lambda_intensity`` increases expected user count linearly, so
        total PRB demand and overload frequency typically rise.
    """

    if lambda_intensity < 0.0:
        raise ValueError("lambda_intensity must be non-negative")
    if lambda_intensity == 0.0:
        return np.empty((0, 2), dtype=float)

    # PPP count for this trial: Poisson(lambda * area).
    mean_count = lambda_intensity * beam.area
    n_users = sample_poisson(mean_count, rng)
    if n_users == 0:
        return np.empty((0, 2), dtype=float)

    # Conditional on count, draw iid uniform points in the beam circle.
    # For uniform area density in polar coordinates, use:
    # - angle ~ Uniform(0, 2*pi)
    # - radius = R * sqrt(U), U~Uniform(0,1)
    points = np.empty((n_users, 2), dtype=float)
    for i in range(n_users):
        theta = rng.uniform(0.0, 2.0 * np.pi)
        radial = beam.radius * np.sqrt(rng.random())
        points[i, 0] = beam.x_center + radial * np.cos(theta)
        points[i, 1] = beam.y_center + radial * np.sin(theta)
    return points
