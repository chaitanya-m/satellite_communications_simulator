# experiments/satellites/min_feasible_qos.py

from __future__ import annotations
from typing import Any

from experiments.single_objective_discrete import (
    BernoulliExperiment,
)


class MinLambdaForQoS(BernoulliExperiment):
    """
    QoS experiment with coverage and throughput constraints.

    The design parameter is a single scalar (e.g. lambda), and the goal
    is to find the minimum design value such that, with high probability,
    both coverage and throughput constraints are satisfied.
    """

    def __init__(
        self,
        *,
        min_coverage: float,
        min_throughput: float,
    ):
        super().__init__()
        self.min_coverage = min_coverage
        self.min_throughput = min_throughput

    # ------------------------------------------------------------------
    # Bernoulli semantics (canonical)
    # ------------------------------------------------------------------

    def is_valid_trial(self, metrics: dict[str, float]) -> bool:
        """Ignore trivial worlds (no ground points)."""
        return metrics.get("n_ground", 1) != 0

    def accept(self, Z: dict[str, float]) -> bool:
        """Success requires both coverage and throughput constraints."""
        return (
            float(Z["coverage"]) >= self.min_coverage
            and float(Z["throughput"]) >= self.min_throughput
        )

    def objective(self, design: Any, metrics: dict[str, float]) -> float:
        """
        Smooth optimisation signal for the optimiser.

        Uses the minimum normalised margin across coverage and throughput.
        """
        if self.min_coverage <= 0 or self.min_throughput <= 0:
            return 0.0
        coverage_ratio = float(metrics["coverage"]) / self.min_coverage
        throughput_ratio = float(metrics["throughput"]) / self.min_throughput
        return min(coverage_ratio, throughput_ratio)
