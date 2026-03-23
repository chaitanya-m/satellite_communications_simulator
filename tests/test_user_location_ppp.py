"""Tests for PPP user-location generation in circular beams.

Scope:
- Validate count/placement logic for the PPP trial generator.
- Validate reproducibility and input guardrails.

Out of scope:
- Shadowing-field sampling.
- PRB-demand mapping and outage aggregation.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from sim.stochastic.poisson import sample_poisson
from sim.stochastic.user_locations import CircularBeam, sample_user_locations_ppp


def test_circular_beam_validates_radius() -> None:
    """CircularBeam should reject non-positive radius.

    Checks performed:
    - radius <= 0 is rejected.
    """

    with pytest.raises(ValueError, match="radius must be positive"):
        CircularBeam(x_center=0.0, y_center=0.0, radius=0.0)


def test_sample_user_locations_ppp_reproducible_for_same_seed() -> None:
    """Same seed path should produce identical PPP location realizations.

    Checks performed:
    - number of sampled users matches between runs,
    - sampled positions are identical for identical RNG seeds.
    """

    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=3.0)
    rng_a = random.Random(2026)
    rng_b = random.Random(2026)

    pts_a = sample_user_locations_ppp(lambda_intensity=50.0, beam=beam, rng=rng_a)
    pts_b = sample_user_locations_ppp(lambda_intensity=50.0, beam=beam, rng=rng_b)

    assert pts_a.shape == pts_b.shape
    assert np.allclose(pts_a, pts_b)


def test_sample_user_locations_ppp_points_stay_inside_beam() -> None:
    """All sampled points should lie inside the configured beam circle.

    Checks performed:
    - every sampled point distance to center is <= radius.
    """

    beam = CircularBeam(x_center=10.0, y_center=-5.0, radius=7.0)
    pts = sample_user_locations_ppp(
        lambda_intensity=25.0,
        beam=beam,
        rng=random.Random(7),
    )

    if pts.shape[0] > 0:
        dx = pts[:, 0] - beam.x_center
        dy = pts[:, 1] - beam.y_center
        radii = np.sqrt(dx * dx + dy * dy)
        assert np.all(radii <= beam.radius + 1e-12)


def test_sample_user_locations_ppp_is_uniform_over_beam_area() -> None:
    """Sampled points should be consistent with uniform area density in a disk.

    Why this test matters:
    - Merely checking that points stay inside the beam is not enough.
    - A buggy sampler could still place too many points near the center or near
      the edge while remaining inside the disk.
    - For a point drawn uniformly over a disk of radius ``R``, the normalized
      squared radius ``r^2 / R^2`` is Uniform(0,1), so its mean should be 0.5.

    Checks performed:
    - over many sampled points, the empirical mean of ``r^2 / R^2`` is close
      to 0.5, which is the correct uniform-area target.
    """

    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=1.0)
    pts = sample_user_locations_ppp(
        lambda_intensity=10_000.0,
        beam=beam,
        rng=random.Random(12345),
    )

    assert pts.shape[0] > 0
    dx = pts[:, 0] - beam.x_center
    dy = pts[:, 1] - beam.y_center
    normalized_squared_radius = (dx * dx + dy * dy) / (beam.radius * beam.radius)
    assert abs(float(np.mean(normalized_squared_radius)) - 0.5) < 0.03


def test_sample_user_locations_ppp_count_matches_poisson_draw_for_seed() -> None:
    """PPP count should match Poisson(lambda * area) under same RNG seed path.

    Checks performed:
    - trial user count equals the Poisson draw expected from identical seed.
    """

    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=2.0)  # area=4*pi
    lam = 5.0
    seed = 99

    # Mirror the count draw on a separate RNG with the same seed path.
    rng_expected = random.Random(seed)
    expected_count = sample_poisson(lam * beam.area, rng_expected)

    rng_actual = random.Random(seed)
    pts = sample_user_locations_ppp(lambda_intensity=lam, beam=beam, rng=rng_actual)

    assert pts.shape[0] == expected_count


def test_sample_user_locations_ppp_handles_zero_intensity() -> None:
    """Zero intensity should return an empty location set.

    Checks performed:
    - lambda_intensity=0 returns shape (0,2),
    - no exception is raised.
    """

    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=1.0)
    pts = sample_user_locations_ppp(lambda_intensity=0.0, beam=beam, rng=random.Random(0))
    assert pts.shape == (0, 2)


def test_sample_user_locations_ppp_rejects_negative_intensity() -> None:
    """Negative intensity should be rejected.

    Checks performed:
    - lambda_intensity < 0 raises ValueError.
    """

    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=1.0)
    with pytest.raises(ValueError, match="non-negative"):
        sample_user_locations_ppp(lambda_intensity=-1.0, beam=beam, rng=random.Random(0))
