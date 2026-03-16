"""Shadowing samplers used by attenuation-model comparison experiments.

This module provides the two shadowing simulators requested in the experiment
plan:

1) Uniform log-shadowing baseline (independent per user).
2) Gaussian random-field log-shadowing (spatially correlated per user).

The functions here are intentionally small and explicit so they can be tested
in isolation before wiring the full experiment loop.

Notation used across functions:
- ``G`` is log-shadowing in natural-log units.
- ``S = exp(G)`` is the multiplicative linear shadowing factor.
- User locations are passed as an ``(n_users, n_dims)`` array.
"""

from __future__ import annotations

import random
from typing import Sequence

import numpy as np


def _numpy_generator_from_rng(rng: random.Random) -> np.random.Generator:
    """Create a NumPy generator deterministically from ``random.Random``.

    This follows the same reproducibility pattern as other stochastic helpers
    in the repository: callers control reproducibility through a Python
    ``random.Random`` instance, and this helper derives a stable 64-bit seed
    for NumPy sampling.

    Reproducibility note: for a fixed Python seed path and fixed NumPy version,
    generated draws are deterministic. Changing NumPy version/RNG algorithms may
    change exact draw sequences.
    """

    seed = rng.getrandbits(64)
    return np.random.default_rng(seed)


def sample_uniform_log_shadowing(
    n_users: int,
    *,
    low_log: float,
    high_log: float,
    rng: random.Random,
) -> np.ndarray:
    """Sample independent uniform log-shadowing values for one trial.

    Args:
        n_users: Number of users in the trial.
        low_log: Lower bound of the uniform interval for ``G``.
        high_log: Upper bound of the uniform interval for ``G``.
        rng: Python RNG controlling reproducibility.

    Returns:
        A NumPy array of shape ``(n_users,)`` containing sampled ``G`` values.

    Why this exists:
        This is the baseline model where users do *not* share spatial
        correlation. It is useful as a structural comparison against the
        Gaussian correlated field model.

    Parameter-selection note:
        ``low_log`` and ``high_log`` are manual modeling choices. They should be
        set deliberately (for example from measurement-informed ranges, or to
        match target moments against a Gaussian baseline), because these bounds
        directly control outage tails and therefore RB-dimensioning conclusions.
    """

    if n_users < 0:
        raise ValueError("n_users must be non-negative")
    if low_log >= high_log:
        raise ValueError("uniform bounds must satisfy low_log < high_log")
    if n_users == 0:
        return np.empty(0, dtype=float)

    generator = _numpy_generator_from_rng(rng)
    return generator.uniform(low=low_log, high=high_log, size=n_users).astype(float)


def build_gaussian_log_shadowing_covariance(
    user_locations: Sequence[Sequence[float]] | np.ndarray,
    *,
    variance_log: float,
    corr_length: float,
    jitter: float = 1e-9,
) -> np.ndarray:
    """Build an RBF covariance matrix for Gaussian log-shadowing.

    Why this is needed:
        To sample a Gaussian shadowing field over many user positions, we need
        to specify not only per-location variability but also how positions
        influence each other. The covariance matrix is that coupling object.
        It encodes which positions should move together strongly (nearby) and
        which should be nearly independent (far apart). The resulting matrix is
        then passed to multivariate-normal sampling to generate one correlated
        log-shadowing realization for a trial.

    The covariance model is:

    ``Cov(G_i, G_j) = variance_log * exp(-||x_i - x_j||^2 / (2*corr_length^2))``

    Here ``Cov(G_i, G_j)`` means: how strongly log-shadowing at location
    ``x_i`` and location ``x_j`` tend to move together across repeated random
    draws. A large positive value means they usually go up/down together; a
    value near zero means they are nearly independent.

    Args:
        user_locations: User coordinates with shape ``(n_users, n_dims)``.
        variance_log: Per-location spread of log-shadowing values around the mean.
            Larger values produce wider up/down fluctuations at each location.
        corr_length: Distance scale that controls how quickly correlation
            decays with separation. Large values mean far-apart locations still
            behave similarly; small values mean similarity fades quickly.
        jitter: Non-negative diagonal stabilizer added numerically.

    Returns:
        Covariance matrix with shape ``(n_users, n_users)``.

    Notes:
    - ``jitter`` is a numerical safeguard for matrix factorization in sampling.
    - The diagonal becomes ``variance_log + jitter``.
    """

    # Convert input to a dense float array for vectorized distance operations.
    x = np.asarray(user_locations, dtype=float)
    # Expect one row per user position and one column per spatial axis
    # (for example x,y in 2D or x,y,z in 3D).
    if x.ndim != 2:
        raise ValueError("user_locations must be a 2D array (n_users, n_dims)")
    # Empty trial: return an empty covariance matrix by convention.
    if x.shape[0] == 0:
        return np.empty((0, 0), dtype=float)
    if variance_log <= 0.0:
        raise ValueError("variance_log must be positive")
    if corr_length <= 0.0:
        raise ValueError("corr_length must be positive")
    if jitter < 0.0:
        raise ValueError("jitter must be non-negative")
    if not np.all(np.isfinite(x)):
        raise ValueError("user_locations must contain only finite values")

    # Pairwise squared Euclidean distances: shape (n_users, n_users).
    deltas = x[:, None, :] - x[None, :, :]
    sq_dist = np.sum(deltas * deltas, axis=2)

    covariance = variance_log * np.exp(-sq_dist / (2.0 * corr_length * corr_length))
    if jitter > 0.0:
        covariance = covariance + np.eye(x.shape[0]) * jitter
    return covariance


def sample_gaussian_log_shadowing(
    user_locations: Sequence[Sequence[float]] | np.ndarray,
    *,
    mean_log: float,
    variance_log: float,
    corr_length: float,
    rng: random.Random,
    jitter: float = 1e-9,
) -> np.ndarray:
    """Sample correlated Gaussian log-shadowing at user locations.

    Why this is needed:
        In the comparison study, each trial needs one full log-shadowing vector
        over the sampled user positions. This function generates that vector
        from a Gaussian-field assumption: same mean level, same per-location
        spread, and distance-based spatial correlation. The output can then be
        mapped directly to per-user PRB demand and aggregated to total demand
        for outage evaluation.

    Args:
        user_locations: User coordinates with shape ``(n_users, n_dims)``.
        mean_log: Common mean value for log-shadowing ``G``.
            This is an explicit caller input (typically from experiment config,
            e.g. ``GaussianParams.mean_log``); this function does not estimate
            it from data.
        variance_log: Per-location spread of ``G`` around ``mean_log``.
        corr_length: Distance scale for shared behavior across locations.
            Large values -> smoother, more globally correlated field;
            small values -> more local correlation only.
        rng: Python RNG controlling reproducibility.
        jitter: Non-negative covariance diagonal stabilizer.

    Returns:
        Sampled log-shadowing vector of shape ``(n_users,)``.

    Why this exists:
        This is the correlated-field simulator used to test sensitivity of RB
        dimensioning to Gaussian-field assumptions.

    Comparison implication:
        ``mean_log`` shifts the whole Gaussian field up/down. Higher
        ``mean_log`` means less average attenuation, which tends to reduce PRB
        demand and outage; lower ``mean_log`` does the opposite. For a fair
        structure-focused comparison against the uniform baseline, choose
        Gaussian and uniform settings with matched central tendency (and often
        matched spread) so differences are driven mainly by correlation
        structure rather than a trivial mean shift.
    """

    # Convert input to a dense float array for covariance/sampling routines.
    x = np.asarray(user_locations, dtype=float)
    # Expect one row per user position and one column per spatial axis
    # (for example x,y in 2D or x,y,z in 3D).
     # fix to 2D because from the satellite perspective, user locations are points in 2D space (latitude and longitude).
    if x.ndim != 2:
        raise ValueError("user_locations must be a 2D array (n_users, n_dims)")
    # Empty trial: no locations implies no shadowing values to sample.
    if x.shape[0] == 0:
        return np.empty(0, dtype=float)

    # Build the location-to-location covariance matrix from the RBF model.
    covariance = build_gaussian_log_shadowing_covariance(
        x,
        variance_log=variance_log,
        corr_length=corr_length,
        jitter=jitter,
    )
    # Build a constant mean vector (same mean_log at every user position).
    mean = np.full(x.shape[0], float(mean_log), dtype=float)

    # Derive a NumPy RNG from the caller's Python RNG for reproducible sampling.
    generator = _numpy_generator_from_rng(rng)

    # Draw one correlated Gaussian vector for all user positions in this trial.
    sample = generator.multivariate_normal(mean=mean, cov=covariance, method="cholesky")
    
    # Return as a plain float vector with shape (n_users,).
    return np.asarray(sample, dtype=float)
