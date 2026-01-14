# tests/test_min_feasible_outage.py
"""Tests for outage-driven dimensioning experiments."""

from experiments.satellites.min_feasible_outage import MinLambdaForOutage


def test_min_lambda_for_outage_accepts_below_threshold():
    """Accept when outage is at or below the configured maximum."""
    experiment = MinLambdaForOutage(max_outage=0.2)

    assert experiment.accept({"outage_rate": 0.2}) is True
    assert experiment.accept({"outage_rate": 0.21}) is False


def test_min_lambda_for_outage_ignores_trivial_trials():
    """No-demand trials should not count toward trials or successes."""
    experiment = MinLambdaForOutage(max_outage=0.2)
    experiment.on_evaluation(5.0, {"outage_rate": 0.0, "n_ground": 0.0})

    assert experiment._trials == {}
    assert experiment._successes == {}
