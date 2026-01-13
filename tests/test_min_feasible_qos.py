# tests/test_min_feasible_qos.py
"""Tests for throughput-aware QoS experiments."""

from __future__ import annotations

from orchestrator.certificates.bernoulli import AllSuccessCertificate
from experiments.satellites.min_feasible_qos import MinLambdaForQoS


def test_min_lambda_for_qos_accepts_only_when_both_constraints_met():
    """Accept only when coverage and throughput both clear thresholds."""
    experiment = MinLambdaForQoS(min_coverage=0.7, min_throughput=2.5)

    assert experiment.accept({"coverage": 0.7, "throughput": 2.5}) is True
    assert experiment.accept({"coverage": 0.69, "throughput": 2.5}) is False
    assert experiment.accept({"coverage": 0.7, "throughput": 2.4}) is False


def test_min_lambda_for_qos_ignores_trivial_trials():
    """Ignore trials with no ground demand to preserve experiment semantics."""
    experiment = MinLambdaForQoS(min_coverage=0.5, min_throughput=1.0)

    experiment.on_evaluation(
        10.0,
        {"coverage": 1.0, "throughput": 10.0, "n_ground": 0.0},
    )

    assert experiment._trials == {}
    assert experiment._successes == {}


def test_min_lambda_for_qos_certificate_tracks_successes():
    """Bernoulli certificate consumes the experiment's success/trial counts."""
    experiment = MinLambdaForQoS(min_coverage=0.5, min_throughput=1.0)
    certificate = AllSuccessCertificate(alpha=0.1)

    # Feed a handful of successful trials to exercise bookkeeping and LCB usage.
    for _ in range(5):
        experiment.on_evaluation(
            5.0,
            {"coverage": 0.8, "throughput": 1.2, "n_ground": 1.0},
        )

    successes = experiment._successes.get(5.0, 0)
    trials = experiment._trials.get(5.0, 0)
    lcb = certificate.lower_confidence_bound(successes, trials)

    assert successes == trials == 5
    assert 0.0 < lcb <= 1.0
