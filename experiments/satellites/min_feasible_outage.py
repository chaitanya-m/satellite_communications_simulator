# experiments/satellites/min_feasible_outage.py

from __future__ import annotations
from typing import Any

from experiments.single_objective_discrete import (
    BernoulliExperiment,
)


class MinLambdaForOutage(BernoulliExperiment):
    """
    Outage experiment for dimensioning.

    The design parameter is a single scalar supplied by the caller.
    In this repo it is typically the satellite Poisson mean (lambda),
    passed through the experiment loop rather than stored here. A trial
    succeeds when the observed outage rate is at or below the target.
    """

    def __init__(
        self,
        *,
        max_outage: float,
    ):
        super().__init__()
        self.max_outage = max_outage

    # ------------------------------------------------------------------
    # Bernoulli semantics (canonical)
    # ------------------------------------------------------------------

    def is_valid_trial(self, metrics: dict[str, float]) -> bool:
        """Ignore trivial worlds (no ground demand)."""
        return metrics.get("n_ground", 1) != 0

    def accept(self, Z: dict[str, float]) -> bool:
        """Success requires outage rate at or below the target."""
        return float(Z["outage_rate"]) <= self.max_outage

    def objective(self, design: Any, metrics: dict[str, float]) -> float:
        """
        Smooth optimisation signal for the optimiser.

        Uses negative outage as a monotone proxy for feasibility.
        """
        return -float(metrics["outage_rate"])
