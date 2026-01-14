# tests/test_poisson_sampling.py
"""Tests for the Poisson sampler across small and large regimes."""

import random

from sim.stochastic.poisson import sample_poisson


def test_sample_poisson_large_lambda_scales():
    """Large lambda should not saturate at small counts."""
    rng = random.Random(0)
    value = sample_poisson(50000.0, rng)

    # Guard against the small-lambda sampler underflowing at large lambda.
    assert value > 10000
