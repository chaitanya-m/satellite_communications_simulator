"""Core contracts for the attenuation-outage experimental procedure.

This module defines the typed data contracts used across the full workflow.
The goal is to keep each stage small and testable by fixing clear inputs and
outputs between stages.

Contracts present:
1) ``ExperimentConfig``
   - Global run settings (population/sample sizes, MC draws, snapshots,
     outage target, candidate RB budgets, base seed).
   - Used to make runs reproducible and to centralize all knobs.

2) ``Snapshot``
   - One realization of active users and measurements:
     user locations, user weights, measured shadowing values, and optional
     latent ground truth (simulation-only).
   - Produced by snapshot generation (procedure point (i)).
   - Consumed by GPR update and label construction (points (ii)-(iii)).

3) ``Posterior``
   - GPR posterior of the shadowing field conditioned on data, represented as a
     mean vector and covariance matrix on chosen evaluation locations.
   - Produced by the GPR stage (point (ii)).
   - Consumed by posterior Monte Carlo outage estimation (point (iv)).

4) ``BudgetResult``
   - Per-candidate-budget result for one snapshot:
     observed overload label, model-predicted outage probability, and MC counts.
   - Produced after points (iii)-(iv).
   - Consumed by snapshot comparison/calibration and final dimensioning
     decisions (points (v)-(vii)).
   - Practical implication: after calibration across snapshots, these records
     are used to choose the smallest RB budget whose predicted outage
     probability is at or below the target epsilon.

Why strict validation:
- shape mismatches (e.g., different lengths for users/weights/measurements)
  fail early;
- probability/count constraints are enforced at object creation;
- contract-level tests can be written before simulator details are implemented.

How to use this interface in the full procedure:
1) Set up ``ExperimentConfig``.
   Choose your outage target (``outage_target_epsilon``), candidate RB budgets,
   number of snapshots, and Monte Carlo draws.
2) For each snapshot, create one ``Snapshot``.
   Put in sampled user locations, user weights (to represent population users),
   and measured shadowing values. In simulator runs, also keep the latent truth
   for evaluation.
3) Run the GPR update on that snapshot's measurements and store the output as
   ``Posterior(mean, covariance)``.
4) For each candidate RB budget, compute one ``BudgetResult``:
   - observed overload label from the snapshot truth (0/1), and
   - model-predicted outage probability from posterior Monte Carlo.
5) Repeat across snapshots, then check calibration (
   if the model predicts about 10% outage, observed overload should occur
   about 10% of the time over many snapshots).
6) Final decision: pick the smallest RB budget whose calibrated predicted
   outage is at or below ``outage_target_epsilon``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Tuple


UserLocation = Tuple[float, float]


@dataclass(frozen=True)
class Snapshot:
    """One fixed snapshot used in points (i)-(v) of the procedure.

    A snapshot contains:
    - sampled active user locations (fixed inside this snapshot),
    - per-user sample weights used to represent population users,
    - noisy measurement values used for GPR conditioning,
    - optional latent ground-truth log-shadowing values (simulation-only).
    """

    snapshot_id: int
    user_locations_xy: Tuple[UserLocation, ...]
    user_weights: Tuple[int, ...]
    measurements_db: Tuple[float, ...]
    latent_log_shadowing_truth: Tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        n = len(self.user_locations_xy)
        if self.snapshot_id < 0:
            raise ValueError("snapshot_id must be non-negative")
        if n == 0:
            raise ValueError("snapshot must contain at least one user")
        if len(self.user_weights) != n:
            raise ValueError("user_weights length must match user_locations_xy")
        if len(self.measurements_db) != n:
            raise ValueError("measurements_db length must match user_locations_xy")
        if any(w <= 0 for w in self.user_weights):
            raise ValueError("all user_weights must be positive")
        if self.latent_log_shadowing_truth is not None and len(self.latent_log_shadowing_truth) != n:
            raise ValueError(
                "latent_log_shadowing_truth length must match user_locations_xy"
            )

    @property
    def sample_size(self) -> int:
        return len(self.user_locations_xy)

    @property
    def represented_population_size(self) -> int:
        return int(sum(self.user_weights))


@dataclass(frozen=True)
class Posterior:
    """Posterior field conditioned on measurements, on chosen evaluation points."""

    mean: Tuple[float, ...]
    covariance: Tuple[Tuple[float, ...], ...]

    def __post_init__(self) -> None:
        n = len(self.mean)
        if n == 0:
            raise ValueError("posterior mean must be non-empty")
        if len(self.covariance) != n:
            raise ValueError("covariance must be square with size len(mean)")
        for row in self.covariance:
            if len(row) != n:
                raise ValueError("covariance must be square with size len(mean)")

    @property
    def dimension(self) -> int:
        return len(self.mean)


@dataclass(frozen=True)
class BudgetResult:
    """Per-budget output for one snapshot.

    `observed_overload_label` is the realized binary label z(N_avail) from the
    snapshot's latent ground truth. `predicted_outage_probability` is the model
    estimate p_out(N_avail | y), typically computed via posterior Monte Carlo.
    Across candidate budgets, these values support selecting the minimum
    required budget that meets the specified outage target.
    """

    n_avail_rb: int
    observed_overload_label: int
    predicted_outage_probability: float
    mc_draws: int
    overloaded_draws: int

    def __post_init__(self) -> None:
        if self.n_avail_rb <= 0:
            raise ValueError("n_avail_rb must be positive")
        if self.observed_overload_label not in (0, 1):
            raise ValueError("observed_overload_label must be 0 or 1")
        if not (0.0 <= self.predicted_outage_probability <= 1.0):
            raise ValueError("predicted_outage_probability must be in [0, 1]")
        if self.mc_draws <= 0:
            raise ValueError("mc_draws must be positive")
        if self.overloaded_draws < 0:
            raise ValueError("overloaded_draws must be non-negative")
        if self.overloaded_draws > self.mc_draws:
            raise ValueError("overloaded_draws cannot exceed mc_draws")


@dataclass(frozen=True)
class ExperimentConfig:
    """Top-level configuration for attenuation outage experiments."""

    n_population_users: int = 1_000_000
    n_sample_users: int = 1_000
    n_posterior_mc_draws: int = 2_000
    n_snapshots: int = 200
    outage_target_epsilon: float = 0.05
    candidate_rb_budgets: Tuple[int, ...] = ()
    base_seed: int = 0

    def __post_init__(self) -> None:
        if self.n_population_users <= 0:
            raise ValueError("n_population_users must be positive")
        if self.n_sample_users <= 0:
            raise ValueError("n_sample_users must be positive")
        if self.n_sample_users > self.n_population_users:
            raise ValueError("n_sample_users cannot exceed n_population_users")
        if self.n_posterior_mc_draws <= 0:
            raise ValueError("n_posterior_mc_draws must be positive")
        if self.n_snapshots <= 0:
            raise ValueError("n_snapshots must be positive")
        if not (0.0 < self.outage_target_epsilon < 1.0):
            raise ValueError("outage_target_epsilon must be in (0, 1)")
        if self.base_seed < 0:
            raise ValueError("base_seed must be non-negative")
        if any(b <= 0 for b in self.candidate_rb_budgets):
            raise ValueError("all candidate_rb_budgets must be positive")
        if tuple(sorted(self.candidate_rb_budgets)) != self.candidate_rb_budgets:
            raise ValueError("candidate_rb_budgets must be sorted in non-decreasing order")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain Python objects for logs/checkpointing."""
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ExperimentConfig":
        """Deserialize from plain Python objects."""
        return cls(
            n_population_users=int(payload["n_population_users"]),
            n_sample_users=int(payload["n_sample_users"]),
            n_posterior_mc_draws=int(payload["n_posterior_mc_draws"]),
            n_snapshots=int(payload["n_snapshots"]),
            outage_target_epsilon=float(payload["outage_target_epsilon"]),
            candidate_rb_budgets=tuple(int(v) for v in payload["candidate_rb_budgets"]),
            base_seed=int(payload["base_seed"]),
        )
