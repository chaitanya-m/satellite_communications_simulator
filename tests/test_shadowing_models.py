"""Tests for uniform and Gaussian log-shadowing samplers.

Scope:
- These tests validate only the shadowing generators themselves.
- They do not yet test PPP user-position generation or outage aggregation.

Conventions used:
- ``G`` is log-shadowing in natural-log units.
- Uniform baseline: independent draws for each sampled user position.
- Gaussian model: correlated draws driven by location distance.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from experiments.satellites.attenuation_contracts import DiscreteLogShadowingMarginal
from sim.stochastic.shadowing import (
    build_gaussian_log_shadowing_covariance,
    sample_correlated_log_shadowing_from_discrete_marginal,
    sample_gaussian_log_shadowing,
    sample_log_shadowing_from_discrete_marginal,
    sample_uniform_log_shadowing,
)


def test_uniform_log_shadowing_is_reproducible_and_bounded() -> None:
    """Uniform baseline should be seed-reproducible and respect interval bounds.

    We use the same RNG seed twice and expect the same draw vector. We also
    check that every sampled value falls inside the configured interval.

    Checks performed:
    - output length matches n_users,
    - all draws lie in [low_log, high_log],
    - same seed path reproduces identical draws.
    """

    # Number of sampled user positions in this synthetic trial.
    n_users = 1000
    # Manual uniform bounds for log-shadowing G=ln(S).
    low_log = -2.0
    high_log = 0.5

    # Same seed on two independent RNG objects should reproduce the same vector.
    rng_a = random.Random(12345)
    rng_b = random.Random(12345)

    draws_a = sample_uniform_log_shadowing(
        n_users,
        low_log=low_log,
        high_log=high_log,
        rng=rng_a,
    )
    draws_b = sample_uniform_log_shadowing(
        n_users,
        low_log=low_log,
        high_log=high_log,
        rng=rng_b,
    )

    # Output length should match number of sampled users.
    assert draws_a.shape == (n_users,)
    # Uniform draws must stay inside the configured interval.
    assert np.all(draws_a >= low_log)
    assert np.all(draws_a <= high_log)
    # Reproducibility: same seed path should produce the same values.
    assert np.allclose(draws_a, draws_b)


def test_uniform_log_shadowing_handles_zero_users() -> None:
    """Zero-user trials should return an empty vector without error.

    This matches experiment-loop behavior where a trial can occasionally
    contain no sampled users after PPP generation.

    Checks performed:
    - sampler returns an empty vector,
    - no exception is raised for n_users=0.
    """

    draws = sample_uniform_log_shadowing(
        0,
        low_log=-1.0,
        high_log=1.0,
        rng=random.Random(0),
    )
    assert draws.shape == (0,)


def test_discrete_marginal_sampler_is_reproducible_and_uses_only_supplied_support() -> None:
    """The iid shared-marginal sampler should preserve the provided support."""

    marginal = DiscreteLogShadowingMarginal(
        values_log=(-2.0, -0.5, 0.0),
        probabilities=(0.2, 0.5, 0.3),
    )
    rng_a = random.Random(123)
    rng_b = random.Random(123)

    draws_a = sample_log_shadowing_from_discrete_marginal(
        20_000,
        marginal=marginal,
        rng=rng_a,
    )
    draws_b = sample_log_shadowing_from_discrete_marginal(
        20_000,
        marginal=marginal,
        rng=rng_b,
    )

    assert draws_a.shape == (20_000,)
    assert np.allclose(draws_a, draws_b)
    assert set(np.unique(draws_a)) == set(marginal.values_log)
    observed_probs = np.array(
        [np.mean(draws_a == value) for value in marginal.values_log],
        dtype=float,
    )
    assert np.allclose(observed_probs, np.array(marginal.probabilities), atol=0.02)


def test_uniform_log_shadowing_rejects_invalid_parameters() -> None:
    """Uniform sampler should fail fast on invalid parameter values.

    This keeps misconfigured experiments from silently producing misleading
    results.

    Checks performed:
    - negative n_users is rejected,
    - invalid interval (low_log >= high_log) is rejected.
    """

    with pytest.raises(ValueError, match="non-negative"):
        sample_uniform_log_shadowing(
            -1,
            low_log=-1.0,
            high_log=1.0,
            rng=random.Random(0),
        )

    with pytest.raises(ValueError, match="low_log < high_log"):
        sample_uniform_log_shadowing(
            10,
            low_log=0.0,
            high_log=0.0,
            rng=random.Random(0),
        )


def test_gaussian_covariance_structure_matches_distance_logic() -> None:
    """Nearby points should have higher covariance than farther points.

    We place three sampled user positions on a 1D line:
    position 0 at x=0, position 1 at x=1 (near), position 2 at x=4 (far).
    Under an RBF kernel, cov(0,1) should be greater than cov(0,2).

    Checks performed:
    - covariance matrix has correct square shape,
    - covariance matrix is symmetric,
    - nearer pair has larger covariance than farther pair,
    - diagonal includes variance + jitter (strictly above variance_log).
    """

    # One spatial axis (x only) keeps geometry easy to reason about.
    locations = np.array([[0.0], [1.0], [4.0]], dtype=float)
    covariance = build_gaussian_log_shadowing_covariance(
        locations,
        variance_log=0.3,  # Per-location spread around mean_log.
        corr_length=1.5,  # Correlation decay distance.
        jitter=1e-9,  # Tiny diagonal stabilizer.
    )

    # Covariance matrix must be square and symmetric.
    assert covariance.shape == (3, 3)
    assert np.allclose(covariance, covariance.T)
    # Nearer positions should couple more strongly than farther positions.
    assert covariance[0, 1] > covariance[0, 2]
    # Diagonal includes variance + jitter, so it should exceed variance_log.
    assert np.all(np.diag(covariance) > 0.3)


def test_gaussian_sampler_is_reproducible_for_same_seed() -> None:
    """Gaussian sampler should be deterministic for identical RNG seeds.

    This is critical for repeatable experiment comparisons and debugging.

    Checks performed:
    - output shape is one value per input location,
    - output values are finite,
    - same seed path reproduces identical draws.
    """

    # Simple 2D grid of sampled user positions.
    locations = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0],
        ],
        dtype=float,
    )

    # Independent RNG instances with the same seed.
    rng_a = random.Random(2026)
    rng_b = random.Random(2026)

    draws_a = sample_gaussian_log_shadowing(
        locations,
        mean_log=-0.75,  # Mean level of log-shadowing.
        variance_log=0.3,  # Per-location spread around mean_log.
        corr_length=2.0,  # Correlation decay distance.
        rng=rng_a,
    )
    draws_b = sample_gaussian_log_shadowing(
        locations,
        mean_log=-0.75,
        variance_log=0.3,
        corr_length=2.0,
        rng=rng_b,
    )

    # One draw value per input user position.
    assert draws_a.shape == (4,)
    # No NaN/inf values should appear in sampled output.
    assert np.all(np.isfinite(draws_a))
    # Reproducibility check.
    assert np.allclose(draws_a, draws_b)


def test_gaussian_sampler_handles_zero_users() -> None:
    """Zero-user Gaussian trial should return an empty vector.

    This keeps trial-loop code simple: empty PPP trials do not need special
    handling in caller code.

    Checks performed:
    - sampler returns an empty vector,
    - no exception is raised for empty location input.
    """

    draws = sample_gaussian_log_shadowing(
        np.empty((0, 2), dtype=float),
        mean_log=0.0,
        variance_log=0.2,
        corr_length=10.0,
        rng=random.Random(0),
    )
    assert draws.shape == (0,)


def test_correlated_shared_marginal_sampler_is_reproducible_and_uses_only_support() -> None:
    """Shared-marginal Gaussian sampling should add dependence without changing support."""

    marginal = DiscreteLogShadowingMarginal(
        values_log=(-2.0, 0.0),
        probabilities=(0.5, 0.5),
    )
    locations = np.array([[0.0, 0.0], [0.2, 0.0], [5.0, 0.0]], dtype=float)
    rng_a = random.Random(999)
    rng_b = random.Random(999)

    draws_a = sample_correlated_log_shadowing_from_discrete_marginal(
        locations,
        marginal=marginal,
        corr_length=1.5,
        rng=rng_a,
    )
    draws_b = sample_correlated_log_shadowing_from_discrete_marginal(
        locations,
        marginal=marginal,
        corr_length=1.5,
        rng=rng_b,
    )

    assert draws_a.shape == (3,)
    assert np.allclose(draws_a, draws_b)
    assert set(np.unique(draws_a)).issubset(set(marginal.values_log))


def test_gaussian_sampler_rejects_invalid_inputs() -> None:
    """Gaussian sampler/covariance should validate shape and parameter ranges.

    These checks prevent unstable or undefined covariance construction.

    Checks performed:
    - non-2D location arrays are rejected,
    - non-positive variance_log is rejected,
    - non-positive corr_length is rejected,
    - non-finite location coordinates are rejected.
    """

    with pytest.raises(ValueError, match="2D"):
        sample_gaussian_log_shadowing(
            np.array([0.0, 1.0, 2.0]),
            mean_log=0.0,
            variance_log=0.2,
            corr_length=10.0,
            rng=random.Random(0),
        )

    with pytest.raises(ValueError, match="variance_log must be positive"):
        build_gaussian_log_shadowing_covariance(
            np.array([[0.0], [1.0]]),
            variance_log=0.0,
            corr_length=1.0,
        )

    with pytest.raises(ValueError, match="corr_length must be positive"):
        build_gaussian_log_shadowing_covariance(
            np.array([[0.0], [1.0]]),
            variance_log=0.2,
            corr_length=0.0,
        )

    with pytest.raises(ValueError, match="finite"):
        build_gaussian_log_shadowing_covariance(
            np.array([[0.0], [np.nan]]),
            variance_log=0.2,
            corr_length=1.0,
        )
