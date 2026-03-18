"""End-to-end model-comparison loop for attenuation-based RB dimensioning.

This module wires together the pieces already implemented:
- PPP user-location trial generation,
- shadowing samplers (uniform baseline, Gaussian field variants),
- PRB-demand mapping and aggregation,
- outage-vs-budget estimation and required-budget extraction.

The result is returned using the typed contracts in
``experiments/satellites/attenuation_contracts.py``.
"""

from __future__ import annotations

from dataclasses import replace
import random
from typing import Iterable, Literal

from orchestrator.certificates.bernoulli import HoeffdingCertificate
from experiments.satellites.attenuation_contracts import (
    ComparisonResult,
    ExperimentConfig,
    GaussianUniformTrialOutcome,
    GaussianVsUniformCertificateResult,
    ModelBudgetEstimate,
    ModelSpec,
    TruthAnchoredComparisonResult,
)
from sim.prb_demand import PRBDemandParams, prb_demand_from_log_shadowing, total_prb_demand
from sim.stochastic.obstruction_field import (
    ObstructionFieldSpec,
    evaluate_obstruction_log_shadowing,
)
from sim.stochastic.shadowing import (
    sample_gaussian_log_shadowing,
    sample_uniform_log_shadowing,
)
from sim.stochastic.user_locations import CircularBeam, sample_user_locations_ppp


def run_attenuation_model_comparison(
    *,
    config: ExperimentConfig,
    beam: CircularBeam,
    prb_params: PRBDemandParams,
) -> ComparisonResult:
    """Run a complete model-comparison experiment and return typed results.

    Args:
        config: Experiment-level settings and model list.
        beam: Spatial beam footprint for PPP user-location generation.
        prb_params: Parameters for mapping shadowing to per-user PRB demand.

    Returns:
        ``ComparisonResult`` containing one outage curve per model, required
        budgets, and deltas against the baseline model.

    Fairness policy used here:
        For each trial index ``t``, user locations are sampled once and reused
        across all models. This keeps demand differences attributable primarily
        to shadowing-model differences rather than user-placement noise.
    """

    budgets = config.candidate_rb_budgets
    n_models = len(config.models)
    n_budgets = len(budgets)

    # overload_counts[m][k] = number of trials where model m overloaded budget k.
    overload_counts = [[0] * n_budgets for _ in range(n_models)]

    # Master RNG controls the full experiment seed path.
    master_rng = random.Random(config.base_seed)

    for _trial_idx in range(config.n_trials):
        # Sample user locations once, then reuse across all models for this trial.
        user_rng = random.Random(master_rng.getrandbits(64))
        user_locations = sample_user_locations_ppp(
            lambda_intensity=config.ppp_intensity_lambda,
            beam=beam,
            rng=user_rng,
        )

        for model_idx, model in enumerate(config.models):
            model_rng = random.Random(master_rng.getrandbits(64))
            total_demand = _sample_total_prb_demand_for_model(
                model=model,
                user_locations=user_locations,
                prb_params=prb_params,
                rng=model_rng,
            )
            for budget_idx, budget in enumerate(budgets):
                if total_demand > budget:
                    overload_counts[model_idx][budget_idx] += 1

    estimates: list[ModelBudgetEstimate] = []
    for model_idx, model in enumerate(config.models):
        outage_by_budget = tuple(
            overload_counts[model_idx][k] / config.n_trials for k in range(n_budgets)
        )
        required_budget = _select_required_budget(
            budgets=budgets,
            outage_by_budget=outage_by_budget,
            outage_target=config.outage_target_epsilon,
        )
        estimates.append(
            ModelBudgetEstimate(
                model_id=model.model_id,
                outage_by_budget=outage_by_budget,
                required_budget=required_budget,
                n_trials=config.n_trials,
            )
        )

    baseline_model_id = _select_baseline_model_id(config.models)
    baseline_required_budget = _required_budget_for_model_id(estimates, baseline_model_id)
    deltas = tuple(
        (e.model_id, e.required_budget - baseline_required_budget)
        for e in estimates
        if e.model_id != baseline_model_id
    )

    return ComparisonResult(
        baseline_model_id=baseline_model_id,
        estimates=tuple(estimates),
        delta_required_budget_vs_baseline=deltas,
    )


def run_truth_anchored_attenuation_comparison(
    *,
    config: ExperimentConfig,
    beam: CircularBeam,
    prb_params: PRBDemandParams,
    ground_truth_spec: ObstructionFieldSpec,
    scenario_label: str | None = None,
) -> TruthAnchoredComparisonResult:
    """Run model comparison against a scenario-defined ground-truth field.

    Workflow:
    1) Sample PPP user locations per trial.
    2) Evaluate deterministic ground-truth obstruction field on those locations.
    3) Compute true total demand and true outage-vs-budget curve.
    4) On the same trial locations, run uniform/Gaussian model samplers and
       compute model outage-vs-budget curves.
    5) Compare required budgets of each model against ground truth.

    Args:
        config: Experiment-level settings and model list.
        beam: Circular beam footprint for PPP trial generation.
        prb_params: PRB demand-mapping parameters.
        ground_truth_spec: Obstruction-field scenario definition.
        scenario_label: Optional human-readable label. If omitted, pattern kind
            from ``ground_truth_spec`` is used.
    """

    budgets = config.candidate_rb_budgets
    n_models = len(config.models)
    n_budgets = len(budgets)

    # Model overload counts indexed as [model_idx][budget_idx].
    overload_counts = [[0] * n_budgets for _ in range(n_models)]
    # Ground-truth overload counts indexed as [budget_idx].
    true_overload_counts = [0] * n_budgets

    # Master RNG controls the full experiment seed path.
    master_rng = random.Random(config.base_seed)

    for _trial_idx in range(config.n_trials):
        # Sample trial user locations once and reuse across truth and all models.
        user_rng = random.Random(master_rng.getrandbits(64))
        user_locations = sample_user_locations_ppp(
            lambda_intensity=config.ppp_intensity_lambda,
            beam=beam,
            rng=user_rng,
        )

        # ---- Ground truth branch -------------------------------------------------
        true_log_shadowing = evaluate_obstruction_log_shadowing(
            user_locations=user_locations,
            beam=beam,
            spec=ground_truth_spec,
        )
        if true_log_shadowing.size == 0:
            true_total_demand = 0
        else:
            true_per_user_prb = prb_demand_from_log_shadowing(
                true_log_shadowing, params=prb_params
            )
            true_total_demand = total_prb_demand(true_per_user_prb)
        for budget_idx, budget in enumerate(budgets):
            if true_total_demand > budget:
                true_overload_counts[budget_idx] += 1

        # ---- Model branches ------------------------------------------------------
        for model_idx, model in enumerate(config.models):
            model_rng = random.Random(master_rng.getrandbits(64))
            total_demand = _sample_total_prb_demand_for_model(
                model=model,
                user_locations=user_locations,
                prb_params=prb_params,
                rng=model_rng,
            )
            for budget_idx, budget in enumerate(budgets):
                if total_demand > budget:
                    overload_counts[model_idx][budget_idx] += 1

    # Build model comparison output using existing contract.
    model_estimates: list[ModelBudgetEstimate] = []
    for model_idx, model in enumerate(config.models):
        outage_by_budget = tuple(
            overload_counts[model_idx][k] / config.n_trials for k in range(n_budgets)
        )
        required_budget = _select_required_budget(
            budgets=budgets,
            outage_by_budget=outage_by_budget,
            outage_target=config.outage_target_epsilon,
        )
        model_estimates.append(
            ModelBudgetEstimate(
                model_id=model.model_id,
                outage_by_budget=outage_by_budget,
                required_budget=required_budget,
                n_trials=config.n_trials,
            )
        )

    baseline_model_id = _select_baseline_model_id(config.models)
    baseline_required_budget = _required_budget_for_model_id(model_estimates, baseline_model_id)
    delta_vs_baseline = tuple(
        (e.model_id, e.required_budget - baseline_required_budget)
        for e in model_estimates
        if e.model_id != baseline_model_id
    )
    model_comparison = ComparisonResult(
        baseline_model_id=baseline_model_id,
        estimates=tuple(model_estimates),
        delta_required_budget_vs_baseline=delta_vs_baseline,
    )

    # Build ground-truth required budget and model-vs-truth deltas.
    true_outage_by_budget = tuple(c / config.n_trials for c in true_overload_counts)
    true_required_budget = _select_required_budget(
        budgets=budgets,
        outage_by_budget=true_outage_by_budget,
        outage_target=config.outage_target_epsilon,
    )
    delta_vs_truth = tuple(
        (e.model_id, e.required_budget - true_required_budget) for e in model_estimates
    )

    return TruthAnchoredComparisonResult(
        scenario_label=scenario_label or ground_truth_spec.pattern_kind,
        ground_truth_outage_by_budget=true_outage_by_budget,
        ground_truth_required_budget=true_required_budget,
        model_comparison=model_comparison,
        delta_required_budget_vs_truth=delta_vs_truth,
    )


def _sample_total_prb_demand_for_model(
    *,
    model: ModelSpec,
    user_locations,
    prb_params: PRBDemandParams,
    rng: random.Random,
) -> int:
    """Sample one trial's total PRB demand under a specific shadowing model."""

    n_users = int(user_locations.shape[0])
    if n_users == 0:
        return 0

    if model.kind == "uniform":
        assert model.uniform is not None  # guaranteed by contract
        log_shadowing = sample_uniform_log_shadowing(
            n_users,
            low_log=model.uniform.low_log,
            high_log=model.uniform.high_log,
            rng=rng,
        )
    elif model.kind == "gaussian":
        assert model.gaussian is not None  # guaranteed by contract
        log_shadowing = sample_gaussian_log_shadowing(
            user_locations=user_locations,
            mean_log=model.gaussian.mean_log,
            variance_log=model.gaussian.variance_log,
            corr_length=model.gaussian.corr_length,
            rng=rng,
        )
    else:
        raise ValueError(f"unsupported model kind: {model.kind}")

    per_user_prb = prb_demand_from_log_shadowing(log_shadowing, params=prb_params)
    return total_prb_demand(per_user_prb)


def _select_required_budget(
    *,
    budgets: tuple[int, ...],
    outage_by_budget: tuple[float, ...],
    outage_target: float,
) -> int:
    """Return the smallest budget whose estimated outage is at or below target.

    If none of the tested budgets meets the target, return the largest budget
    in the provided grid as a clipped outcome.
    """

    for budget, outage in zip(budgets, outage_by_budget, strict=True):
        if outage <= outage_target:
            return budget
    return budgets[-1]


def _select_baseline_model_id(models: tuple[ModelSpec, ...]) -> str:
    """Select baseline model id, preferring the first uniform model."""

    for model in models:
        if model.kind == "uniform":
            return model.model_id
    return models[0].model_id


def _required_budget_for_model_id(
    estimates: list[ModelBudgetEstimate], model_id: str
) -> int:
    """Read required_budget from estimates for a specific model id."""

    for estimate in estimates:
        if estimate.model_id == model_id:
            return estimate.required_budget
    raise ValueError(f"baseline model_id not found in estimates: {model_id}")


def certify_gaussian_better_from_error_pairs(
    *,
    error_pairs: Iterable[tuple[float, float]],
    alpha: float = 0.05,
    threshold: float = 0.5,
    tie_policy: Literal["uniform_wins", "exclude"] = "uniform_wins",
) -> GaussianVsUniformCertificateResult:
    """Build a Gaussian-vs-uniform certificate from trial-level error pairs.

    Args:
        error_pairs:
            Iterable of ``(uniform_abs_error, gaussian_abs_error)`` pairs.
        alpha:
            One-sided confidence level parameter (e.g. 0.05 for 95% confidence).
        threshold:
            Success-probability threshold to certify against. For
            ``P(gaussian better) > 0.5``, use ``threshold=0.5``.
        tie_policy:
            How ties (equal absolute error) are handled:
            - ``uniform_wins``: ties count as non-success.
            - ``exclude``: ties are removed from Bernoulli trial count.

    Returns:
        ``GaussianVsUniformCertificateResult`` with ``p_hat``, one-sided LCB,
        and certification decision ``lcb > threshold``.
    """

    if tie_policy not in {"uniform_wins", "exclude"}:
        raise ValueError("tie_policy must be 'uniform_wins' or 'exclude'")
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0, 1)")
    if not (0.0 < threshold < 1.0):
        raise ValueError("threshold must be in (0, 1)")

    outcomes: list[GaussianUniformTrialOutcome] = []
    successes = 0
    trials = 0
    ties = 0

    for idx, (uniform_err, gaussian_err) in enumerate(error_pairs):
        if uniform_err < 0 or gaussian_err < 0:
            raise ValueError("absolute errors must be non-negative")

        tie = gaussian_err == uniform_err
        gaussian_better = gaussian_err < uniform_err
        outcomes.append(
            GaussianUniformTrialOutcome(
                scenario_label=f"pair_{idx}",
                base_seed=idx,
                trial_index=idx,
                true_total_demand=0,
                uniform_predicted_total_demand=0.0,
                gaussian_predicted_total_demand=0.0,
                uniform_abs_demand_error=float(uniform_err),
                gaussian_abs_demand_error=float(gaussian_err),
                gaussian_better=gaussian_better,
                tie=tie,
            )
        )

        if tie and tie_policy == "exclude":
            ties += 1
            continue

        trials += 1
        if gaussian_better:
            successes += 1
        if tie:
            ties += 1

    if trials == 0:
        p_hat = 0.0
        lcb = 0.0
    else:
        p_hat = successes / trials
        # Hoeffding is distribution-free and does not require SciPy.
        certificate = HoeffdingCertificate(alpha=alpha)
        lcb = certificate.lower_confidence_bound(successes, trials)

    return GaussianVsUniformCertificateResult(
        alpha=alpha,
        threshold=threshold,
        successes=successes,
        trials=trials,
        p_hat=p_hat,
        lcb=lcb,
        certified=lcb > threshold,
        ties=ties,
        outcomes=tuple(outcomes),
    )


def run_gaussian_vs_uniform_certificate(
    *,
    config: ExperimentConfig,
    beam: CircularBeam,
    prb_params: PRBDemandParams,
    scenarios: tuple[ObstructionFieldSpec, ...],
    base_seeds: tuple[int, ...],
    alpha: float = 0.05,
    threshold: float = 0.5,
    tie_policy: Literal["uniform_wins", "exclude"] = "uniform_wins",
    prediction_draws_per_trial: int = 64,
) -> GaussianVsUniformCertificateResult:
    """Run a trial-level certificate that Gaussian beats uniform.

    For each scenario, seed, and trial:
    1. sample user PPP locations,
    2. compute true realized total demand from the obstruction field,
    3. estimate each model's predicted total demand for that same user geometry,
    4. compare absolute demand-prediction errors.

    Bernoulli success event:
    ``gaussian_abs_error < uniform_abs_error`` on that trial.

    Important distinction:
    - We do not aggregate raw RB totals across independent trials.
    - The Bernoulli unit is one trial.
    - The only within-trial averaging is the inner Monte Carlo used to estimate
      a model's expected total demand for that fixed user geometry.
    """

    if len(scenarios) == 0:
        raise ValueError("scenarios must be non-empty")
    if len(base_seeds) == 0:
        raise ValueError("base_seeds must be non-empty")
    if prediction_draws_per_trial <= 0:
        raise ValueError("prediction_draws_per_trial must be positive")

    uniform_model_id, gaussian_model_id = _select_uniform_and_gaussian_model_ids(config.models)
    uniform_model = _model_by_id(config.models, uniform_model_id)
    gaussian_model = _model_by_id(config.models, gaussian_model_id)

    trial_outcomes: list[GaussianUniformTrialOutcome] = []
    successes = 0
    trials = 0
    ties = 0

    for scenario in scenarios:
        for seed in base_seeds:
            master_rng = random.Random(int(seed))

            for trial_index in range(config.n_trials):
                # Sample the realized user geometry for this independent trial.
                user_rng = random.Random(master_rng.getrandbits(64))
                user_locations = sample_user_locations_ppp(
                    lambda_intensity=config.ppp_intensity_lambda,
                    beam=beam,
                    rng=user_rng,
                )

                # Compute true realized total demand from the obstruction field.
                true_total_demand = _true_total_prb_demand_for_trial(
                    user_locations=user_locations,
                    beam=beam,
                    ground_truth_spec=scenario,
                    prb_params=prb_params,
                )

                # Predict total demand under each model for the same user geometry.
                uniform_rng = random.Random(master_rng.getrandbits(64))
                gaussian_rng = random.Random(master_rng.getrandbits(64))
                uniform_pred = _estimate_model_mean_total_prb_demand_for_trial(
                    model=uniform_model,
                    user_locations=user_locations,
                    prb_params=prb_params,
                    rng=uniform_rng,
                    prediction_draws=prediction_draws_per_trial,
                )
                gaussian_pred = _estimate_model_mean_total_prb_demand_for_trial(
                    model=gaussian_model,
                    user_locations=user_locations,
                    prb_params=prb_params,
                    rng=gaussian_rng,
                    prediction_draws=prediction_draws_per_trial,
                )

                uniform_abs_error = abs(uniform_pred - true_total_demand)
                gaussian_abs_error = abs(gaussian_pred - true_total_demand)
                tie = gaussian_abs_error == uniform_abs_error
                gaussian_better = gaussian_abs_error < uniform_abs_error

                trial_outcomes.append(
                    GaussianUniformTrialOutcome(
                        scenario_label=scenario.pattern_kind,
                        base_seed=int(seed),
                        trial_index=trial_index,
                        true_total_demand=int(true_total_demand),
                        uniform_predicted_total_demand=float(uniform_pred),
                        gaussian_predicted_total_demand=float(gaussian_pred),
                        uniform_abs_demand_error=float(uniform_abs_error),
                        gaussian_abs_demand_error=float(gaussian_abs_error),
                        gaussian_better=gaussian_better,
                        tie=tie,
                    )
                )

                if tie and tie_policy == "exclude":
                    ties += 1
                    continue

                trials += 1
                if gaussian_better:
                    successes += 1
                if tie:
                    ties += 1

    if trials == 0:
        p_hat = 0.0
        lcb = 0.0
    else:
        p_hat = successes / trials
        # Hoeffding is distribution-free and does not require SciPy.
        certificate = HoeffdingCertificate(alpha=alpha)
        lcb = certificate.lower_confidence_bound(successes, trials)

    return GaussianVsUniformCertificateResult(
        alpha=alpha,
        threshold=threshold,
        successes=successes,
        trials=trials,
        p_hat=p_hat,
        lcb=lcb,
        certified=lcb > threshold,
        ties=ties,
        outcomes=tuple(trial_outcomes),
    )


def _select_uniform_and_gaussian_model_ids(models: tuple[ModelSpec, ...]) -> tuple[str, str]:
    """Return one uniform model id and one gaussian model id.

    Selection policy:
    - first uniform model in order,
    - first gaussian model in order.
    """

    uniform_id: str | None = None
    gaussian_id: str | None = None
    for model in models:
        if model.kind == "uniform" and uniform_id is None:
            uniform_id = model.model_id
        if model.kind == "gaussian" and gaussian_id is None:
            gaussian_id = model.model_id
    if uniform_id is None:
        raise ValueError("at least one uniform model is required for certification")
    if gaussian_id is None:
        raise ValueError("at least one gaussian model is required for certification")
    return uniform_id, gaussian_id


def _model_by_id(models: tuple[ModelSpec, ...], model_id: str) -> ModelSpec:
    """Return the model spec matching ``model_id``."""

    for model in models:
        if model.model_id == model_id:
            return model
    raise ValueError(f"model_id not found: {model_id}")


def _true_total_prb_demand_for_trial(
    *,
    user_locations,
    beam: CircularBeam,
    ground_truth_spec: ObstructionFieldSpec,
    prb_params: PRBDemandParams,
) -> int:
    """Compute true realized total demand for one trial geometry."""

    true_log_shadowing = evaluate_obstruction_log_shadowing(
        user_locations=user_locations,
        beam=beam,
        spec=ground_truth_spec,
    )
    if true_log_shadowing.size == 0:
        return 0
    true_per_user_prb = prb_demand_from_log_shadowing(true_log_shadowing, params=prb_params)
    return total_prb_demand(true_per_user_prb)


def _estimate_model_mean_total_prb_demand_for_trial(
    *,
    model: ModelSpec,
    user_locations,
    prb_params: PRBDemandParams,
    rng: random.Random,
    prediction_draws: int,
) -> float:
    """Estimate model-expected total demand for one fixed trial geometry.

    The user locations are held fixed. We then average multiple model draws to
    approximate the model's expected total demand conditional on that geometry.
    """

    n_users = int(user_locations.shape[0])
    if n_users == 0:
        return 0.0

    total = 0.0
    for _draw_idx in range(prediction_draws):
        draw_rng = random.Random(rng.getrandbits(64))
        total += float(
            _sample_total_prb_demand_for_model(
                model=model,
                user_locations=user_locations,
                prb_params=prb_params,
                rng=draw_rng,
            )
        )
    return total / prediction_draws
