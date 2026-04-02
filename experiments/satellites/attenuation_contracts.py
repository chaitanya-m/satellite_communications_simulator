"""Contracts for model-comparison RB-dimensioning experiments.

This file fixes the data interfaces used by the attenuation-study workflow so
that the simulator, experiment runner, and downstream analysis all agree on
what statistical object is being passed around.

This file defines three kinds of experiment objects:

1. Model/configuration inputs:
   These describe which stochastic models are being compared and under what
   common experiment settings they are run. For example, the Gaussian field
   parameters and the target outage level are part of this layer.

2. Budget-level comparison outputs:
   These summarize repeated trials through outage-by-budget vectors and derived
   required budgets. They are used for the dimensioning-style question:
   "what RB budget would this model choose at the target outage?"

3. Trial-level certificate outputs:
   Each independent trial is treated as one Bernoulli comparison between
   Gaussian and uniform, based on which model predicts the realized total
   demand more accurately on that trial.

Keeping these object types separate is important so budget-level summaries are
not confused with trial-level certificate logic.

A repeated-trial dimensioning run with 250 trials should produce one
``ComparisonResult``-style budget summary object, where the 250 trials are
aggregated into outage estimates over the tested RB budget grid.

Those same 250 trials can also contribute 250 trial-level Bernoulli comparison
outcomes for the Gaussian-versus-uniform certificate, where each trial asks
which model predicted the realized total demand more accurately for that trial.

A ``GaussianVsUniformCertificateResult`` then summarizes whatever collection of
independent trial outcomes is supplied to the certificate procedure. That
collection may be broader than a single repeated-trial block, depending on how
calling code assembles the certificate inputs. The runner-specific details for
that assembly belong in the experiment-runner docstrings rather than here.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, Literal, Tuple


ModelKind = Literal["uniform", "gaussian"]


@dataclass(frozen=True)
class DiscreteLogShadowingMarginal:
    """Discrete marginal distribution for natural-log shadowing values.

    This is the shared one-point distribution used in the new fair comparison:
    both the iid uniform-style baseline and the Gaussian spatial model can be
    driven by exactly the same marginal, while differing only in dependence
    structure across user locations.
    """

    values_log: Tuple[float, ...]
    probabilities: Tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.values_log) == 0:
            raise ValueError("values_log must be non-empty")
        if len(self.values_log) != len(self.probabilities):
            raise ValueError("values_log and probabilities must have the same length")
        if any(not math.isfinite(v) for v in self.values_log):
            raise ValueError("values_log must contain only finite values")
        if any((not math.isfinite(p)) or p < 0.0 for p in self.probabilities):
            raise ValueError("probabilities must be finite and non-negative")
        if sum(self.probabilities) <= 0.0:
            raise ValueError("probabilities must contain at least one positive entry")
        if not math.isclose(sum(self.probabilities), 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("probabilities must sum to 1")

    @property
    def mean_log(self) -> float:
        """Return the marginal mean of ``G`` under this discrete distribution."""

        return sum(v * p for v, p in zip(self.values_log, self.probabilities, strict=True))

    @property
    def variance_log(self) -> float:
        """Return the marginal variance of ``G`` under this distribution."""

        mean_log = self.mean_log
        return sum(
            ((v - mean_log) ** 2) * p
            for v, p in zip(self.values_log, self.probabilities, strict=True)
        )


@dataclass(frozen=True)
class GaussianParams:
    """Parameterization for one Gaussian-field simulator variant.

    Two Gaussian modes are supported:
    - direct Gaussian mode: ``mean_log`` and ``variance_log`` define a
      Gaussian marginal for ``G`` directly;
    - shared-marginal mode: ``marginal`` defines the one-point distribution,
      while the Gaussian branch contributes only the spatial dependence.

    In both modes, ``corr_length`` sets the distance scale over which nearby
    user locations tend to experience similar shadowing.

    This object does not perform any simulation itself; it is just the typed
    parameter bundle consumed later by the Gaussian shadowing sampler.
    """

    corr_length: float
    mean_log: float | None = None
    variance_log: float | None = None
    marginal: DiscreteLogShadowingMarginal | None = None

    def __post_init__(self) -> None:
        if self.corr_length <= 0.0:
            raise ValueError("corr_length must be positive")
        uses_direct_gaussian = self.mean_log is not None or self.variance_log is not None
        if self.marginal is None:
            if not uses_direct_gaussian:
                raise ValueError(
                    "gaussian params require either marginal or mean_log/variance_log"
                )
            if self.mean_log is None or self.variance_log is None:
                raise ValueError(
                    "gaussian direct mode requires both mean_log and variance_log"
                )
            if self.variance_log <= 0.0:
                raise ValueError("variance_log must be positive")
            return
        if uses_direct_gaussian:
            raise ValueError(
                "gaussian params must use either marginal or mean_log/variance_log, not both"
            )


@dataclass(frozen=True)
class UniformParams:
    """Uniform baseline on log-shadowing, sampled independently per user.

    Two baseline modes are supported:
    - interval mode: iid draws from ``Uniform[low_log, high_log]``;
    - shared-marginal mode: iid draws from ``marginal`` exactly.

    In both cases, the model ignores spatial correlation and treats each user's
    log-shadowing value as conditionally independent.
    """

    low_log: float | None = None
    high_log: float | None = None
    marginal: DiscreteLogShadowingMarginal | None = None

    def __post_init__(self) -> None:
        uses_interval = self.low_log is not None or self.high_log is not None
        if self.marginal is None:
            if not uses_interval:
                raise ValueError("uniform params require either marginal or interval bounds")
            if self.low_log is None or self.high_log is None:
                raise ValueError("uniform interval mode requires both low_log and high_log")
            if self.low_log >= self.high_log:
                raise ValueError("uniform bounds must satisfy low_log < high_log")
            return
        if uses_interval:
            raise ValueError("uniform params must use either marginal or interval bounds, not both")


@dataclass(frozen=True)
class ModelSpec:
    """One simulator model used in the comparison set.

    ``ModelSpec`` is a small tagged union:
    - ``kind="uniform"`` means the model must carry ``UniformParams`` only;
    - ``kind="gaussian"`` means the model must carry ``GaussianParams`` only.

    Why this exists:
    - experiment runners should not need to inspect ad hoc dictionaries;
    - the choice of model family and its parameterization should be explicit;
    - invalid combinations should fail immediately when the object is created.
    """

    model_id: str
    kind: ModelKind
    uniform: UniformParams | None = None
    gaussian: GaussianParams | None = None

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("model_id must be non-empty")
        if self.kind == "uniform":
            if self.uniform is None:
                raise ValueError("uniform model requires uniform params")
            if self.gaussian is not None:
                raise ValueError("uniform model must not include gaussian params")
        elif self.kind == "gaussian":
            if self.gaussian is None:
                raise ValueError("gaussian model requires gaussian params")
            if self.uniform is not None:
                raise ValueError("gaussian model must not include uniform params")
        else:
            raise ValueError(f"unsupported kind: {self.kind}")


@dataclass(frozen=True)
class ExperimentConfig:
    """Top-level common settings for model-comparison experiments.

    This object holds the settings shared across all compared models in one
    experiment run.

    Interpretation of the main fields:
    - ``ppp_intensity_lambda``:
      user intensity per unit area for the homogeneous spatial PPP, not a fixed
      user count.
    - ``outage_target_epsilon``:
      target overload probability used when converting an outage estimate into a
      required RB budget.
    - ``candidate_rb_budgets``:
      discrete budget grid on which outage is evaluated. Required budgets are
      selected from this grid, so coarse grids produce coarse results.
    - ``n_trials``:
      number of independent PPP realizations used in a repeated-trial
      experiment.
    - ``base_seed``:
      master seed controlling reproducibility of the full run.

    This contract is shared by both:
    - the budget-level comparison workflow, and
    - the trial-level Gaussian-vs-uniform certificate workflow.
    """

    ppp_intensity_lambda: float
    outage_target_epsilon: float
    candidate_rb_budgets: Tuple[int, ...]
    n_trials: int
    base_seed: int = 0
    models: Tuple[ModelSpec, ...] = ()

    def __post_init__(self) -> None:
        if self.ppp_intensity_lambda <= 0.0:
            raise ValueError("ppp_intensity_lambda must be positive")
        if not (0.0 < self.outage_target_epsilon < 1.0):
            raise ValueError("outage_target_epsilon must be in (0, 1)")
        if self.n_trials <= 0:
            raise ValueError("n_trials must be positive")
        if self.base_seed < 0:
            raise ValueError("base_seed must be non-negative")
        if len(self.candidate_rb_budgets) == 0:
            raise ValueError("candidate_rb_budgets must be non-empty")
        if any(b <= 0 for b in self.candidate_rb_budgets):
            raise ValueError("all candidate_rb_budgets must be positive")
        if tuple(sorted(self.candidate_rb_budgets)) != self.candidate_rb_budgets:
            raise ValueError("candidate_rb_budgets must be sorted in non-decreasing order")
        if len(self.models) == 0:
            raise ValueError("models must be non-empty")
        model_ids = [m.model_id for m in self.models]
        if len(set(model_ids)) != len(model_ids):
            raise ValueError("model_id values must be unique")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain Python data for logs/checkpointing."""
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ExperimentConfig":
        """Deserialize from plain Python data."""
        models: list[ModelSpec] = []

        def _restore_marginal(
            marginal_payload: Dict[str, Any] | None,
        ) -> DiscreteLogShadowingMarginal | None:
            if marginal_payload is None:
                return None
            return DiscreteLogShadowingMarginal(
                values_log=tuple(float(v) for v in marginal_payload["values_log"]),
                probabilities=tuple(float(v) for v in marginal_payload["probabilities"]),
            )

        for m in payload["models"]:
            uniform = None
            if m.get("uniform"):
                uniform = UniformParams(
                    low_log=m["uniform"].get("low_log"),
                    high_log=m["uniform"].get("high_log"),
                    marginal=_restore_marginal(m["uniform"].get("marginal")),
                )
            gaussian = None
            if m.get("gaussian"):
                gaussian = GaussianParams(
                    corr_length=float(m["gaussian"]["corr_length"]),
                    mean_log=m["gaussian"].get("mean_log"),
                    variance_log=m["gaussian"].get("variance_log"),
                    marginal=_restore_marginal(m["gaussian"].get("marginal")),
                )
            models.append(
                ModelSpec(
                    model_id=str(m["model_id"]),
                    kind=m["kind"],
                    uniform=uniform,
                    gaussian=gaussian,
                )
            )
        return cls(
            ppp_intensity_lambda=float(payload["ppp_intensity_lambda"]),
            outage_target_epsilon=float(payload["outage_target_epsilon"]),
            candidate_rb_budgets=tuple(int(v) for v in payload["candidate_rb_budgets"]),
            n_trials=int(payload["n_trials"]),
            base_seed=int(payload["base_seed"]),
            models=tuple(models),
        )


@dataclass(frozen=True)
class ModelBudgetEstimate:
    """Estimated outage curve and derived required budget for one model.

    This is a budget-level summary object.

    It answers:
    - what outage probability was estimated at each tested RB budget?
    - after looking across that grid, which budget was selected as the required
      one for the chosen target outage?

    It does not store trial-level demand realizations. Those belong to the
    certificate workflow and are handled by separate contracts below.
    """

    model_id: str
    outage_by_budget: Tuple[float, ...]
    required_budget: int
    n_trials: int

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("model_id must be non-empty")
        if self.n_trials <= 0:
            raise ValueError("n_trials must be positive")
        if self.required_budget <= 0:
            raise ValueError("required_budget must be positive")
        if len(self.outage_by_budget) == 0:
            raise ValueError("outage_by_budget must be non-empty")
        if any((p < 0.0 or p > 1.0) for p in self.outage_by_budget):
            raise ValueError("all outage probabilities must be in [0, 1]")


@dataclass(frozen=True)
class ComparisonResult:
    """Aggregate budget-level comparison outputs for one experiment run.

    This object groups several ``ModelBudgetEstimate`` records obtained under a
    shared ``ExperimentConfig`` and records their required-budget differences
    relative to one designated baseline model.

    It is the natural output for the question:
    "under this experiment setup, how do the compared models differ in the RB
    budget they would recommend?"
    """

    baseline_model_id: str
    estimates: Tuple[ModelBudgetEstimate, ...]
    delta_required_budget_vs_baseline: Tuple[Tuple[str, int], ...]

    def __post_init__(self) -> None:
        if not self.baseline_model_id:
            raise ValueError("baseline_model_id must be non-empty")
        if len(self.estimates) == 0:
            raise ValueError("estimates must be non-empty")
        ids = [e.model_id for e in self.estimates]
        if len(set(ids)) != len(ids):
            raise ValueError("estimate model_id values must be unique")
        if self.baseline_model_id not in set(ids):
            raise ValueError("baseline_model_id must exist in estimates")
        seen_delta_ids: set[str] = set()
        for model_id, _delta in self.delta_required_budget_vs_baseline:
            if model_id in seen_delta_ids:
                raise ValueError("delta entries must have unique model_id values")
            seen_delta_ids.add(model_id)


@dataclass(frozen=True)
class TruthAnchoredComparisonResult:
    """Comparison outputs anchored to scenario-defined ground truth.

    This contract is used when experiments include an explicit simulated
    obstruction field treated as ground truth. Model-based required budgets are
    then compared against the ground-truth required budget.

    Statistical role:
    - ``ground_truth_outage_by_budget`` and ``ground_truth_required_budget``
      come from the scenario-defined truth branch;
    - ``model_comparison`` contains the corresponding model-side budget
      summaries;
    - ``delta_required_budget_vs_truth`` records how far each model's selected
      budget is above or below the truth-side selected budget.

    This is still a budget-level object. It is about dimensioning outcomes on a
    tested budget grid. It is not the same as the trial-level certificate that
    asks whether Gaussian predicts realized demand better than uniform.
    """

    scenario_label: str
    ground_truth_outage_by_budget: Tuple[float, ...]
    ground_truth_required_budget: int
    model_comparison: ComparisonResult
    delta_required_budget_vs_truth: Tuple[Tuple[str, int], ...]

    def __post_init__(self) -> None:
        if not self.scenario_label:
            raise ValueError("scenario_label must be non-empty")
        if self.ground_truth_required_budget <= 0:
            raise ValueError("ground_truth_required_budget must be positive")
        if len(self.ground_truth_outage_by_budget) == 0:
            raise ValueError("ground_truth_outage_by_budget must be non-empty")
        if any((p < 0.0 or p > 1.0) for p in self.ground_truth_outage_by_budget):
            raise ValueError("ground_truth_outage_by_budget values must be in [0, 1]")
        seen_ids: set[str] = set()
        for model_id, _delta in self.delta_required_budget_vs_truth:
            if model_id in seen_ids:
                raise ValueError("delta_required_budget_vs_truth must have unique model_id values")
            seen_ids.add(model_id)


@dataclass(frozen=True)
class GaussianUniformTrialOutcome:
    """One trial-level outcome for Gaussian-vs-uniform comparison.

    This is the correct Bernoulli unit for the certificate:
    one trial = one realized user PPP configuration under one scenario and seed.
    The trial records which model gives the smaller absolute prediction error
    against the true realized total demand for that instant.

    Why this object is important:
    - it prevents accidental aggregation of raw RB totals across independent
      trials;
    - it makes the Bernoulli unit explicit;
    - it stores enough information to audit why a trial counted as a Gaussian
      win, a uniform win, or a tie.

    Interpretation:
    - ``true_total_demand`` is the realized demand from the ground-truth
      obstruction scenario for that trial's user geometry;
    - ``uniform_predicted_total_demand`` and
      ``gaussian_predicted_total_demand`` are model-based predicted demands for
      that same geometry;
    - ``uniform_abs_demand_error`` and ``gaussian_abs_demand_error`` are the
      absolute prediction errors against truth;
    - ``gaussian_better`` is true exactly when the Gaussian absolute error is
      strictly smaller;
    - ``tie`` marks equal absolute errors.
    """

    scenario_label: str
    base_seed: int
    trial_index: int
    true_total_demand: int
    uniform_predicted_total_demand: float
    gaussian_predicted_total_demand: float
    uniform_abs_demand_error: float
    gaussian_abs_demand_error: float
    gaussian_better: bool
    tie: bool

    def __post_init__(self) -> None:
        if not self.scenario_label:
            raise ValueError("scenario_label must be non-empty")
        if self.base_seed < 0:
            raise ValueError("base_seed must be non-negative")
        if self.trial_index < 0:
            raise ValueError("trial_index must be non-negative")
        if self.true_total_demand < 0:
            raise ValueError("true_total_demand must be non-negative")
        if self.uniform_abs_demand_error < 0.0:
            raise ValueError("uniform_abs_demand_error must be non-negative")
        if self.gaussian_abs_demand_error < 0.0:
            raise ValueError("gaussian_abs_demand_error must be non-negative")


@dataclass(frozen=True)
class GaussianVsUniformCertificateResult:
    """Certificate summary for the hypothesis: Gaussian beats uniform.

    We model each trial as a Bernoulli success event:
    success = 1 if Gaussian absolute demand-prediction error is strictly
    smaller than uniform absolute demand-prediction error.

    This object therefore summarizes a trial-level prediction-accuracy study,
    not directly a required-budget study.

    Main fields:
    - ``successes`` / ``trials`` define the empirical success rate ``p_hat``;
    - ``lcb`` is a one-sided lower confidence bound on that success
      probability;
    - ``certified`` records whether that lower bound exceeds the chosen
      threshold (typically 0.5);
    - ``outcomes`` stores the underlying trial-level comparison records.

    In plain terms, this contract answers:
    "do we have statistically supported evidence that Gaussian predicts
    realized total demand more accurately than uniform on independent trials?"
    """

    alpha: float
    threshold: float
    successes: int
    trials: int
    p_hat: float
    lcb: float
    certified: bool
    ties: int
    outcomes: Tuple[GaussianUniformTrialOutcome, ...]

    def __post_init__(self) -> None:
        if not (0.0 < self.alpha < 1.0):
            raise ValueError("alpha must be in (0, 1)")
        if not (0.0 < self.threshold < 1.0):
            raise ValueError("threshold must be in (0, 1)")
        if self.successes < 0:
            raise ValueError("successes must be non-negative")
        if self.trials < 0:
            raise ValueError("trials must be non-negative")
        if self.successes > self.trials:
            raise ValueError("successes must be <= trials")
        if self.ties < 0:
            raise ValueError("ties must be non-negative")
        if self.ties > self.trials:
            raise ValueError("ties must be <= trials")
        if not (0.0 <= self.p_hat <= 1.0):
            raise ValueError("p_hat must be in [0, 1]")
        if not (0.0 <= self.lcb <= 1.0):
            raise ValueError("lcb must be in [0, 1]")
