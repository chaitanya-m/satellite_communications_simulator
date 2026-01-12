# tests/test_dimensioning_3d.py
"""Tests for the 3D spherical PPP dimensioning simulator."""

import random

from experiments.satellites.min_feasible_coverage import MinLambdaForCoverage
from orchestrator.certificates.bernoulli import AllSuccessCertificate
from sim.dimensioning_3d import Dimensioning_3D
from sim.stochastic.poisson import sample_poisson


def test_dimensioning_3d_vacuous_when_no_ground():
    """If no users are sampled, coverage should be 1.0 by convention."""
    sim = Dimensioning_3D(
        ground_lambda=0.0,
        lat_min_deg=-10.0,
        lat_max_deg=10.0,
        altitude_km=550.0,
        max_off_nadir_deg=20.0,
        rng=random.Random(0),
    )

    metrics = sim.evaluate(lambda_sats=5.0)

    # With ground_lambda=0, Poisson must return zero users.
    assert metrics["n_ground"] == 0.0
    # Coverage is vacuous if there are no users to serve.
    assert metrics["coverage"] == 1.0
    # Satellite count is still a Poisson draw and should match simulator state.
    assert sim.last_n_sats is not None
    assert metrics["n_sats"] == float(sim.last_n_sats)


def test_dimensioning_3d_zero_sats_means_no_coverage():
    """If no satellites are sampled, coverage is 0.0 unless no users exist."""
    seed = 42
    ground_lambda = 5.0

    # Mirror the simulator's Poisson draw to make the expectation deterministic.
    rng = random.Random(seed)
    expected_n_ground = sample_poisson(ground_lambda, rng)

    sim = Dimensioning_3D(
        ground_lambda=ground_lambda,
        lat_min_deg=-10.0,
        lat_max_deg=10.0,
        altitude_km=550.0,
        max_off_nadir_deg=20.0,
        rng=random.Random(seed),
    )

    metrics = sim.evaluate(lambda_sats=0.0)

    # Poisson ground count should match the mirrored sample above.
    assert metrics["n_ground"] == float(expected_n_ground)
    # With lambda_sats=0, no satellites are sampled.
    assert metrics["n_sats"] == 0.0
    # Coverage is 0.0 when users exist and no satellites are present.
    if expected_n_ground == 0:
        assert metrics["coverage"] == 1.0
    else:
        assert metrics["coverage"] == 0.0


def test_dimensioning_3d_many_points_nonzero_coverage():
    """With many users and satellites, coverage should be nonzero."""
    seed = 7
    ground_lambda = 500.0
    lambda_sats = 500.0

    rng = random.Random(seed)
    expected_n_ground = sample_poisson(ground_lambda, rng)
    expected_n_sats = sample_poisson(lambda_sats, rng)

    sim = Dimensioning_3D(
        ground_lambda=ground_lambda,
        lat_min_deg=-30.0,
        lat_max_deg=30.0,
        altitude_km=550.0,
        max_off_nadir_deg=90.0,
        rng=random.Random(seed),
    )

    metrics = sim.evaluate(lambda_sats=lambda_sats)

    assert metrics["n_ground"] == float(expected_n_ground)
    assert metrics["n_sats"] == float(expected_n_sats)
    assert metrics["n_ground"] > 0.0
    assert metrics["n_sats"] > 0.0
    assert 0.0 < metrics["coverage"] <= 1.0


def test_dimensioning_3d_sequential_search_stops():
    """Sequentially search N and stop at the first certified feasible design."""
    target_coverage = 0.7
    delta = 0.3
    alpha = 0.05

    experiment = MinLambdaForCoverage(target_coverage=target_coverage)
    certificate = AllSuccessCertificate(alpha=alpha)

    ground_lambda = 500.0
    max_designs = 400
    evals_per_design = 100
    seed = 1000

    design = None
    for n in range(1, max_designs + 1, 10):
        lam = float(n)
        for _ in range(evals_per_design):
            rng = random.Random(seed)
            seed += 1

            sim = Dimensioning_3D(
                ground_lambda=ground_lambda,
                lat_min_deg=-10.0,
                lat_max_deg=10.0,
                altitude_km=550.0,
                max_off_nadir_deg=60.0,
                rng=rng,
            )

            metrics = sim.evaluate(lambda_sats=lam)
            experiment.on_evaluation(lam, metrics)

        lcb = certificate.lower_confidence_bound(
            experiment._successes.get(lam, 0),
            experiment._trials.get(lam, 0),
        )
        if lcb >= 1.0 - delta:
            design = n
            print(f"certified N={n} with LCB={lcb:.3f}")
            break

    assert design is not None, "No design certified feasible within the search budget"
    assert design > 100
