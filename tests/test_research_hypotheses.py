"""Research-scale tests for attenuation-study research hypotheses.

Scope:
- Encode and test the attenuation-study hypotheses directly.
- Start with a first study case using a few hundred expected users in the beam
  footprint.
- Support later scaling of the same study logic to a few thousand expected
  users.
- Use a PRB-demand cap of 10 resource blocks per user.
- Use a budget grid whose top end is at most about 20 times the expected user
  count, giving headroom beyond the 10-PRB-per-user cap for PPP count
  variation while still staying in a finite, interpretable regime.

Why this file exists:
- The smaller smoke tests are useful for shape, typing, and reproducibility
  checks, but they operate in a toy regime with only a handful of expected
  users.
- This file is intended to become the repository location where research-paper
  hypotheses are turned into explicit, runnable tests.
- The current few-hundred-user regime is the first explicit study case, not a
  placeholder standing "close to" the study.
- As the study expands, new cases at the few-thousand-user scale should be
  added here under the same research-hypothesis framing.

How to read the experimental procedure in this file:
1. Fix one research-scale experiment setup:
   - one circular beam,
   - one PPP intensity,
   - one PRB-demand model with a 10-PRB-per-user cap,
   - one budget grid,
   - one uniform model,
   - one Gaussian model,
   - one controlled family of equal-area square-fragmentation scenarios.
2. For budget-level truth-anchored comparison:
   - run repeated PPP trials;
   - on each trial, compute the truth-side total demand from the deterministic
     obstruction pattern;
   - on that same user geometry, run the model-side samplers;
   - aggregate overload indicators over the budget grid;
   - select required budgets from the tested grid.
3. For the trial-level Gaussian-versus-uniform certificate:
   - each PPP trial is one Bernoulli comparison unit;
   - on that one fixed PPP geometry, truth is deterministic;
   - uniform and Gaussian remain stochastic because they draw shadowing values;
   - repeated inner model draws are averaged to estimate each model's
     predicted mean total demand for that fixed geometry;
   - Gaussian wins the trial if its absolute demand-prediction error is
     strictly smaller than uniform's.
4. Pool those Bernoulli outcomes across scenarios, seeds, and trials to obtain
   the certificate summary.

Research-hypothesis note:
- The long-term goal is for each test in this file to correspond to a concrete
  scientific claim we are willing to defend in the paper.
- As the study matures, today’s broad consistency assertions can be tightened
  into stronger hypothesis checks with fixed configurations, preserved result
  summaries, and explicit expected comparisons between models.

Budget-grid note:
- The "top budget is at most about 20 times expected users" rule in this file
  is a practical testing rule of thumb, not a strict mathematical maximum.
- PPP user count is random and unbounded, so there is no finite absolute cap on
  total demand across all trials.
- The rule is meant to keep the tested regime interpretable while still giving
  substantial headroom above the 10-PRB-per-user cap evaluated at the expected
  user count.
"""

from __future__ import annotations

import math
from pathlib import Path
from statistics import mean

from experiments.satellites.attenuation_comparison import (
    certify_gaussian_better_from_error_pairs,
    run_gaussian_vs_uniform_certificate,
    run_truth_anchored_attenuation_comparison,
)
from experiments.satellites.attenuation_contracts import (
    DiscreteLogShadowingMarginal,
    ExperimentConfig,
    GaussianParams,
    GaussianVsUniformCertificateResult,
    ModelSpec,
    UniformParams,
)
from sim.prb_demand import PRBDemandParams
from sim.stochastic.obstruction_field import ObstructionFieldSpec
from sim.stochastic.user_locations import CircularBeam


def _summary_path() -> Path:
    """Return the root-level summary file used by research-hypothesis tests."""

    return Path(__file__).resolve().parents[1] / "result_summary.txt"


def _table_path() -> Path:
    """Return the root-level raw table file used by research-hypothesis tests."""

    return Path(__file__).resolve().parents[1] / "result_table.txt"


def _format_float(value: float) -> str:
    """Format floats in a stable human-readable form for result files."""

    return f"{value:.10f}"


def _truth_mean_log_for_binary_obstruction(
    *,
    extra_loss_db: float,
    blocked_area_fraction: float,
    base_log_shadowing: float = 0.0,
) -> float:
    """Return the truth-side mean log shadowing for the current binary family.

    For the obstruction patterns used in this file, the truth field takes only
    two values:
    - ``base_log_shadowing`` on the unblocked fraction ``1 - p`` of the beam;
    - ``base_log_shadowing - loss_shift`` on the blocked fraction ``p``,
      where ``loss_shift = ln(10) / 10 * extra_loss_db`` converts the dB loss
      increment into natural-log scale.

    That makes the beam-average truth mean explicit:

        E[G_truth] = base_log_shadowing - p * loss_shift.

    Why this helper exists:
    - the first calibration step we want is mean matching only;
    - for the current binary obstruction family, the truth mean is simple
      enough to compute analytically instead of estimating numerically;
    - keeping the formula in one place avoids repeating a silent conversion
      from dB loss to natural-log shadowing mean.
    """

    loss_shift = (math.log(10.0) / 10.0) * extra_loss_db
    return base_log_shadowing - (blocked_area_fraction * loss_shift)


def _truth_variance_log_for_binary_obstruction(
    *,
    extra_loss_db: float,
    blocked_area_fraction: float,
) -> float:
    """Return the truth-side log-shadowing variance for the binary family.

    In the current obstruction family, the truth field takes two values:
    - ``0`` on the unblocked fraction ``1 - p`` of the beam;
    - ``-loss_shift`` on the blocked fraction ``p``,
      where ``loss_shift = ln(10) / 10 * extra_loss_db``.

    That makes the variance explicit:

        Var(G_truth) = p * (1 - p) * loss_shift^2.

    Why this helper exists:
    - after mean matching, variance is the next obvious marginal confound to
      remove;
    - for the current binary obstruction family, the truth variance is again
      analytic, so there is no reason to estimate it numerically at this
      stage.
    """

    loss_shift = (math.log(10.0) / 10.0) * extra_loss_db
    return blocked_area_fraction * (1.0 - blocked_area_fraction) * (loss_shift ** 2)


def _truth_marginal_log_for_binary_obstruction(
    *,
    extra_loss_db: float,
    blocked_area_fraction: float,
    base_log_shadowing: float = 0.0,
) -> DiscreteLogShadowingMarginal:
    """Return the exact truth-side marginal for the current binary family.

    The current square truth is binary in log-shadowing:
    - blocked points take ``base_log_shadowing - loss_shift``;
    - unblocked points take ``base_log_shadowing``.

    For the shared-marginal experiment rewrite, this is the object both
    Gaussian and iid baselines should see directly.
    """

    loss_shift = (math.log(10.0) / 10.0) * extra_loss_db
    return DiscreteLogShadowingMarginal(
        values_log=(base_log_shadowing - loss_shift, base_log_shadowing),
        probabilities=(blocked_area_fraction, 1.0 - blocked_area_fraction),
    )


def _config_with_shared_log_shadowing_marginal(
    config: ExperimentConfig,
    *,
    marginal: DiscreteLogShadowingMarginal,
    corr_length: float | None = None,
    base_seed: int | None = None,
) -> ExperimentConfig:
    """Return a copy of ``config`` where both models use the same marginal."""

    gaussian_model = next(model for model in config.models if model.kind == "gaussian")

    return ExperimentConfig(
        ppp_intensity_lambda=config.ppp_intensity_lambda,
        outage_target_epsilon=config.outage_target_epsilon,
        candidate_rb_budgets=config.candidate_rb_budgets,
        n_trials=config.n_trials,
        base_seed=config.base_seed if base_seed is None else int(base_seed),
        models=(
            ModelSpec(
                model_id="uniform_baseline",
                kind="uniform",
                uniform=UniformParams(marginal=marginal),
            ),
            ModelSpec(
                model_id=gaussian_model.model_id,
                kind="gaussian",
                gaussian=GaussianParams(
                    corr_length=(
                        gaussian_model.gaussian.corr_length
                        if corr_length is None
                        else corr_length
                    ),
                    marginal=marginal,
                ),
            ),
        ),
    )


def _config_for_binary_square_truth(
    config: ExperimentConfig,
    *,
    scenario: ObstructionFieldSpec,
    corr_length: float | None = None,
    base_seed: int | None = None,
) -> ExperimentConfig:
    """Return a scenario-specific shared-marginal config for square truth."""

    marginal = _truth_marginal_log_for_binary_obstruction(
        extra_loss_db=scenario.extra_loss_db,
        blocked_area_fraction=scenario.square_area_fraction,
        base_log_shadowing=scenario.base_log_shadowing,
    )
    return _config_with_shared_log_shadowing_marginal(
        config,
        marginal=marginal,
        corr_length=corr_length,
        base_seed=base_seed,
    )


def _certificate_from_trial_outcomes(
    *,
    outcomes,
    alpha: float = 0.05,
    threshold: float = 0.5,
) -> GaussianVsUniformCertificateResult:
    """Build one certificate summary while preserving the supplied outcomes."""

    summary = certify_gaussian_better_from_error_pairs(
        error_pairs=tuple(
            (
                outcome.uniform_abs_demand_error,
                outcome.gaussian_abs_demand_error,
            )
            for outcome in outcomes
        ),
        alpha=alpha,
        threshold=threshold,
        tie_policy="uniform_wins",
    )
    return GaussianVsUniformCertificateResult(
        alpha=alpha,
        threshold=threshold,
        successes=summary.successes,
        trials=summary.trials,
        p_hat=summary.p_hat,
        lcb=summary.lcb,
        certified=summary.certified,
        ties=summary.ties,
        outcomes=tuple(outcomes),
    )


def _write_research_results(
    *,
    experiment_name: str,
    config: ExperimentConfig,
    beam: CircularBeam,
    prb_params: PRBDemandParams,
    base_seeds: tuple[int, ...],
    prediction_draws_per_trial: int,
    pooled_certificate,
    per_scenario_lines: list[str],
    raw_table_lines: list[str],
    extra_experiment_lines: list[str] | None = None,
) -> None:
    """Write one structured research-result snapshot to summary and raw tables.

    Why this helper exists:
    - research-hypothesis tests should not only pass or fail; they should also
      leave behind a structured, reproducible summary of what was run and what
      was observed;
    - keeping the writer in this file ensures the research-test definitions and
      their result-reporting logic stay together.

    Current policy:
    - overwrite ``result_summary.txt`` with the latest deterministic aggregate
      snapshot from this research file;
    - overwrite ``result_table.txt`` with the corresponding raw outputs from
      the same seeded run;
    - use stable sectioned plain-text formats so future experiments can add
      more sections and columns without losing readability.
    """

    expected_users = config.ppp_intensity_lambda * beam.area
    budgets_csv = ",".join(str(v) for v in config.candidate_rb_budgets)
    seeds_csv = ",".join(str(v) for v in base_seeds)

    lines = [
        "[experiment]",
        f"name = {experiment_name}",
        f"ppp_intensity_lambda = {config.ppp_intensity_lambda}",
        f"beam_radius = {beam.radius}",
        f"beam_area = {_format_float(beam.area)}",
        f"expected_users_per_trial = {_format_float(expected_users)}",
        f"max_prb_per_user = {prb_params.max_prb_per_user}",
        f"candidate_rb_budgets = {budgets_csv}",
        f"n_trials_per_seed_scenario = {config.n_trials}",
        f"base_seeds = {seeds_csv}",
        f"prediction_draws_per_trial = {prediction_draws_per_trial}",
    ]
    if extra_experiment_lines is not None:
        lines.extend(extra_experiment_lines)
    lines.extend(
        [
            "",
        "[pooled_certificate]",
        f"successes = {pooled_certificate.successes}",
        f"trials = {pooled_certificate.trials}",
        f"ties = {pooled_certificate.ties}",
        f"p_hat = {_format_float(pooled_certificate.p_hat)}",
        f"lcb = {_format_float(pooled_certificate.lcb)}",
        f"certified = {pooled_certificate.certified}",
        "",
        ]
    )
    lines.extend(per_scenario_lines)
    _summary_path().write_text("\n".join(lines) + "\n")
    _table_path().write_text("\n".join(raw_table_lines) + "\n")


def _run_certificate_experiment_and_write_results(
    *,
    experiment_name: str,
    config: ExperimentConfig,
    beam: CircularBeam,
    prb_params: PRBDemandParams,
    scenarios: tuple[ObstructionFieldSpec, ...],
    base_seeds: tuple[int, ...],
    prediction_draws_per_trial: int,
) -> GaussianVsUniformCertificateResult:
    """Run one certificate experiment and persist summary plus raw tables.

    Why this helper exists:
    - multiple research-hypothesis tests in this file use the same reporting
      path: run the certificate, derive per-scenario summaries, write raw
      trial rows, then write seed-level dimensioning rows for the same
      scenario family;
    - centralizing that workflow keeps the research tests focused on what
      varies scientifically from one experiment to the next.
    """

    all_outcomes = []
    for scenario in scenarios:
        scenario_config = _config_for_binary_square_truth(config, scenario=scenario)
        scenario_cert = run_gaussian_vs_uniform_certificate(
            config=scenario_config,
            beam=beam,
            prb_params=prb_params,
            scenarios=(scenario,),
            base_seeds=base_seeds,
            alpha=0.05,
            threshold=0.5,
            prediction_draws_per_trial=prediction_draws_per_trial,
        )
        all_outcomes.extend(scenario_cert.outcomes)
    cert = _certificate_from_trial_outcomes(outcomes=all_outcomes)

    raw_table_lines: list[str] = [
        "[trial_level_certificate_rows]",
        (
            "scenario_label,base_seed,trial_index,true_total_demand,"
            "uniform_predicted_total_demand,gaussian_predicted_total_demand,"
            "uniform_abs_demand_error,gaussian_abs_demand_error,"
            "gaussian_better,tie"
        ),
    ]
    for outcome in cert.outcomes:
        raw_table_lines.append(
            ",".join(
                [
                    outcome.scenario_label,
                    str(outcome.base_seed),
                    str(outcome.trial_index),
                    str(outcome.true_total_demand),
                    _format_float(outcome.uniform_predicted_total_demand),
                    _format_float(outcome.gaussian_predicted_total_demand),
                    _format_float(outcome.uniform_abs_demand_error),
                    _format_float(outcome.gaussian_abs_demand_error),
                    str(outcome.gaussian_better),
                    str(outcome.tie),
                ]
            )
        )
    raw_table_lines.append("")

    scenario_labels_in_order = [
        scenario.scenario_label or scenario.pattern_kind for scenario in scenarios
    ]
    per_scenario_lines: list[str] = []
    raw_table_lines.extend(
        [
            "[seed_level_dimensioning_rows]",
            (
                "scenario_label,base_seed,truth_required_budget,"
                "uniform_required_budget,gaussian_required_budget"
            ),
        ]
    )

    for scenario_label in scenario_labels_in_order:
        scenario_outcomes = tuple(
            outcome for outcome in cert.outcomes if outcome.scenario_label == scenario_label
        )
        scenario_cert = certify_gaussian_better_from_error_pairs(
            error_pairs=tuple(
                (
                    outcome.uniform_abs_demand_error,
                    outcome.gaussian_abs_demand_error,
                )
                for outcome in scenario_outcomes
            ),
            alpha=0.05,
            threshold=0.5,
            tie_policy="uniform_wins",
        )
        mean_uniform_abs_error = mean(
            outcome.uniform_abs_demand_error for outcome in scenario_outcomes
        )
        mean_gaussian_abs_error = mean(
            outcome.gaussian_abs_demand_error for outcome in scenario_outcomes
        )
        per_scenario_lines.extend(
            [
                f"[scenario.{scenario_label}]",
                f"successes = {scenario_cert.successes}",
                f"trials = {scenario_cert.trials}",
                f"ties = {scenario_cert.ties}",
                f"p_hat = {_format_float(scenario_cert.p_hat)}",
                f"lcb = {_format_float(scenario_cert.lcb)}",
                f"certified = {scenario_cert.certified}",
                f"mean_uniform_abs_error = {_format_float(mean_uniform_abs_error)}",
                f"mean_gaussian_abs_error = {_format_float(mean_gaussian_abs_error)}",
                "",
            ]
        )

    scenarios_by_label = {
        (scenario.scenario_label or scenario.pattern_kind): scenario for scenario in scenarios
    }
    for scenario_label in scenario_labels_in_order:
        scenario = scenarios_by_label[scenario_label]
        for seed in base_seeds:
            seed_config = _config_for_binary_square_truth(
                config,
                scenario=scenario,
                base_seed=int(seed),
            )
            dimensioning_result = run_truth_anchored_attenuation_comparison(
                config=seed_config,
                beam=beam,
                prb_params=prb_params,
                ground_truth_spec=scenario,
                scenario_label=scenario_label,
            )
            budgets_by_model = {
                estimate.model_id: estimate.required_budget
                for estimate in dimensioning_result.model_comparison.estimates
            }
            raw_table_lines.append(
                ",".join(
                    [
                        scenario_label,
                        str(seed),
                        str(dimensioning_result.ground_truth_required_budget),
                        str(budgets_by_model["uniform_baseline"]),
                        str(budgets_by_model["gaussian_l1"]),
                    ]
                )
            )
    raw_table_lines.append("")

    _write_research_results(
        experiment_name=experiment_name,
        config=config,
        beam=beam,
        prb_params=prb_params,
        base_seeds=base_seeds,
        prediction_draws_per_trial=prediction_draws_per_trial,
        pooled_certificate=cert,
        per_scenario_lines=per_scenario_lines,
        raw_table_lines=raw_table_lines,
    )
    return cert


def _fragmentation_experiment_setup() -> tuple[
    ExperimentConfig,
    CircularBeam,
    PRBDemandParams,
    tuple[ObstructionFieldSpec, ...],
    tuple[int, ...],
]:
    """Return the first controlled fragmentation experiment configuration.

    Chosen regime:
    - beam radius = 10, so beam area is ``pi * 10^2 ~= 314.16``;
    - PPP intensity = 1 user per unit area, so expected users per trial are
      also about 314, i.e. a few hundred users in the footprint;
    - PRB-demand parameters are chosen so ``max_prb_per_user = 10`` exactly;
    - explicit distance-based pathloss is enabled with exponent ``2.0`` and a
      baseline altitude of ``250`` units;
    - the tested budget grid runs from 500 to 6000, which stays below
      ``20 * expected_users ~= 6283``.
    - the outer experiment uses 10 independent seed paths and 100 PPP trials
      per seed-scenario block;
    - the truth-side scenarios are a fixed-area square-fragmentation family
      with fragment counts ``K in {1, 4, 9, 16, 25}``.

    Fragmentation axis:
    - ``K = 1`` is one large square, i.e. the non-fragmented case;
    - larger ``K`` values split the same total blocked area into more equal
      squares, spread on a centered lattice inside the beam;
    - extra loss and total blocked area are held fixed across all ``K`` so the
      intended changing variable is spatial fragmentation, not blocked-area
      magnitude.

    Two levels of randomness are important:
    - outer randomness comes from the PPP user geometry changing from trial to
      trial;
    - inner randomness comes from the model-side shadowing draws performed on
      one fixed user geometry when the certificate runner estimates each
      model's predicted mean total demand.

    Calibration policy used here:
    - both compared models see the exact same truth-side one-point marginal
      for the 50%-blocked binary square family;
    - the iid baseline draws independently from that marginal;
    - the Gaussian model uses that same marginal but adds spatial correlation
      through its RBF covariance model.

    The values here are intended as the first stable baseline for the
    fragmentation experiment. They are not yet claimed to be the final
    publication configuration, but they are explicit and controlled enough to
    support scenario-by-scenario comparisons.
    """

    comparison_marginal = _truth_marginal_log_for_binary_obstruction(
        extra_loss_db=10.0,
        blocked_area_fraction=0.5,
    )

    config = ExperimentConfig(
        ppp_intensity_lambda=1.0,
        outage_target_epsilon=0.2,
        candidate_rb_budgets=tuple(range(500, 6500, 500)),
        n_trials=100,
        base_seed=20260324,
        models=(
            ModelSpec(
                model_id="uniform_baseline",
                kind="uniform",
                uniform=UniformParams(marginal=comparison_marginal),
            ),
            ModelSpec(
                model_id="gaussian_l1",
                kind="gaussian",
                gaussian=GaussianParams(
                    corr_length=2.0,
                    marginal=comparison_marginal,
                ),
            ),
        ),
    )
    # Radius 10 gives beam area pi*10^2 ~= 314.16, so with lambda=1 the
    # expected PPP user count is also about 314 users per trial.
    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=10.0)
    # These values are chosen so max_prb_per_user = ceil(1000 / (1000 * 0.1)) = 10.
    prb_params = PRBDemandParams(
        required_rate_bps=1_000.0,
        rb_bandwidth_hz=1_000.0,
        snr0_linear=1.0,
        eta_min=0.1,
        pathloss_exponent=2.0,
        satellite_altitude_units=250.0,
    )
    scenarios = tuple(
        ObstructionFieldSpec(
            pattern_kind="square_fragments",
            scenario_label=f"square_fragments_k{square_count:02d}",
            extra_loss_db=10.0,
            square_area_fraction=0.5,
            fragment_square_count=square_count,
        )
        for square_count in (1, 4, 9, 16, 25)
    )
    # Standard seed set for this first fragmentation regime.
    base_seeds = tuple(range(101, 111))
    return config, beam, prb_params, scenarios, base_seeds


def _blocked_area_experiment_setup() -> tuple[
    ExperimentConfig,
    CircularBeam,
    PRBDemandParams,
    tuple[ObstructionFieldSpec, ...],
    tuple[int, ...],
]:
    """Return the first blocked-area sweep with fixed square-family geometry.

    Scientific axis:
    - hold the truth family to squares only, with fragment counts ``K in {1,4}``;
    - hold extra loss fixed at 10 dB;
    - sweep blocked area fraction from larger values to smaller values;
    - ask whether smaller blocked area shifts the advantage toward the uniform
      baseline.

    Current sweep:
    - area fractions = ``(0.50, 0.40, 0.30, 0.20, 0.10)``;
    - for each area fraction, run both ``K=1`` and ``K=4``.

    Everything else stays aligned with the fragmentation experiment:
    - same beam,
    - same PPP intensity,
    - same PRB mapping,
    - same Gaussian/uniform shared-moment calibration,
    - same seed/trial structure.

    Current calibration policy:
    - for each scenario in the sweep, rebuild the compared models from that
      scenario's exact binary truth marginal before running the experiment;
    - this keeps the area sweep fair even though the blocked fraction changes.
    """

    config, beam, prb_params, _scenarios, base_seeds = _fragmentation_experiment_setup()
    area_fractions = (0.50, 0.40, 0.30, 0.20, 0.10)
    scenarios = tuple(
        ObstructionFieldSpec(
            pattern_kind="square_fragments",
            scenario_label=f"area_{int(area_fraction * 100):02d}_k{square_count:02d}",
            extra_loss_db=10.0,
            square_area_fraction=area_fraction,
            fragment_square_count=square_count,
        )
        for area_fraction in area_fractions
        for square_count in (1, 4)
    )
    return config, beam, prb_params, scenarios, base_seeds


def _altitude_experiment_setup() -> tuple[
    ExperimentConfig,
    CircularBeam,
    PRBDemandParams,
    tuple[float, ...],
    tuple[int, ...],
]:
    """Return the first altitude sweep for the pathloss-enabled study.

    Scientific axis:
    - hold the obstruction family fixed to the 50%-blocked square cases;
    - hold pathloss exponent fixed at ``2.0``;
    - vary only altitude across ``(50, 150, 250, 350, 450)`` units;
    - ask whether model accuracy degrades as altitude increases.

    Scope choice:
    - use ``K=1`` and ``K=4`` for completeness, but keep blocked area fixed at
      0.50 because fragmentation has already been shown to be largely inert
      under the current truth model;
    - this keeps altitude as the intended changing factor.
    """

    config, beam, prb_params, _scenarios, base_seeds = _fragmentation_experiment_setup()
    altitudes = (50.0, 150.0, 250.0, 350.0, 450.0)
    return config, beam, prb_params, altitudes, base_seeds


def _config_with_gaussian_corr_length(
    config: ExperimentConfig,
    *,
    corr_length: float,
) -> ExperimentConfig:
    """Return a copy of the experiment config with a new Gaussian length scale.

    Why this helper exists:
    - after matching the field-wide first and second moments, the main
      remaining Gaussian parameter is the correlation length;
    - the correlation-length experiment should vary only that one parameter and
      keep the rest of the calibrated setup fixed.
    """

    uniform_model = next(model for model in config.models if model.kind == "uniform")
    gaussian_model = next(model for model in config.models if model.kind == "gaussian")

    if gaussian_model.gaussian.marginal is not None:
        gaussian_params = GaussianParams(
            corr_length=corr_length,
            marginal=gaussian_model.gaussian.marginal,
        )
    else:
        gaussian_params = GaussianParams(
            corr_length=corr_length,
            mean_log=gaussian_model.gaussian.mean_log,
            variance_log=gaussian_model.gaussian.variance_log,
        )

    return ExperimentConfig(
        ppp_intensity_lambda=config.ppp_intensity_lambda,
        outage_target_epsilon=config.outage_target_epsilon,
        candidate_rb_budgets=config.candidate_rb_budgets,
        n_trials=config.n_trials,
        base_seed=config.base_seed,
        models=(
            uniform_model,
            ModelSpec(
                model_id=gaussian_model.model_id,
                kind=gaussian_model.kind,
                gaussian=gaussian_params,
            ),
        ),
    )


def _corr_length_experiment_setup() -> tuple[
    ExperimentConfig,
    CircularBeam,
    PRBDemandParams,
    tuple[float, ...],
    tuple[int, ...],
    ObstructionFieldSpec,
]:
    """Return the first fixed-altitude correlation-length sweep.

    Scientific axis:
    - hold altitude fixed at ``250`` units;
    - hold blocked area fixed at ``0.50``;
    - hold the truth scenario to one large square (``K=1``), since
      fragmentation has already been shown to be inert under the current truth
      model;
    - vary only the Gaussian correlation length.

    Why this is the next step:
    - the Gaussian sampler already uses a covariance matrix;
    - after matching mean and variance, the main remaining Gaussian parameter
      is the correlation length controlling how quickly covariance decays with
      distance.
    """

    config, beam, prb_params, _scenarios, base_seeds = _fragmentation_experiment_setup()
    corr_lengths = (0.5, 1.0, 2.0, 4.0, 8.0)
    scenario = ObstructionFieldSpec(
        pattern_kind="square_fragments",
        scenario_label="corr_length_area50_k01",
        extra_loss_db=10.0,
        square_area_fraction=0.5,
        fragment_square_count=1,
    )
    return config, beam, prb_params, corr_lengths, base_seeds, scenario


def test_fragmentation_experiment_truth_anchored_run_uses_few_hundred_users_and_bounded_grid() -> None:
    """Run one truth-anchored fragmentation block in the study-scale regime.

    Why this matters:
    - this test checks that the runner can operate in a regime with a few
      hundred expected users rather than only in tiny toy examples;
    - it also documents the intended budget-grid scaling rule for this regime:
      with at most 10 PRBs per user, a grid topping out near 20 times expected
      user count is generous but still finite.

    Checks performed:
    - expected user count in the beam is a few hundred;
    - the PRB-demand cap is exactly 10 per user;
    - the tested budget grid stays below 20 times expected user count;
    - the standard research-scale setup uses 100 PPP trials per repeated-trial
      block;
    - the scenario family holds total blocked area fixed while varying fragment
      count;
    - a truth-anchored comparison run returns required budgets that lie on the
      tested grid for both truth and models.
    """

    config, beam, prb_params, scenarios, _base_seeds = _fragmentation_experiment_setup()
    expected_users = config.ppp_intensity_lambda * beam.area

    assert 200.0 <= expected_users <= 400.0
    assert math.isclose(expected_users, math.pi * 100.0, rel_tol=1e-12)
    assert prb_params.max_prb_per_user == 10
    assert max(config.candidate_rb_budgets) <= 20.0 * expected_users
    assert config.n_trials == 100
    assert {scenario.pattern_kind for scenario in scenarios} == {"square_fragments"}
    assert {scenario.square_area_fraction for scenario in scenarios} == {0.5}
    assert tuple(scenario.fragment_square_count for scenario in scenarios) == (1, 4, 9, 16, 25)

    result = run_truth_anchored_attenuation_comparison(
        config=config,
        beam=beam,
        prb_params=prb_params,
        ground_truth_spec=scenarios[0],
        scenario_label="square_fragments_k01",
    )

    assert result.scenario_label == "square_fragments_k01"
    assert result.ground_truth_required_budget in set(config.candidate_rb_budgets)
    for estimate in result.model_comparison.estimates:
        assert estimate.required_budget in set(config.candidate_rb_budgets)


def test_fragmentation_experiment_certificate_runs_across_multiple_fragment_counts() -> None:
    """Run the pooled certificate across the controlled fragmentation family.

    Why this matters:
    - the certificate runner is the part of the code most closely tied to the
      current research question;
    - this test documents and checks pooling across fragment counts, seeds,
      and trials in a non-trivial user regime;
    - it uses the simplest possible fair calibration step: uniform and
      Gaussian share the same target mean/variance before any stronger fitting
      ideas are considered;
    - it also documents the standard repeated-trial scale used in this file:
      10 seed paths and 100 PPP trials per seed-scenario block.
    - this test is meant to evolve toward an explicit research claim about when
      Gaussian should or should not outperform uniform.

    Checks performed:
    - the number of Bernoulli outcomes matches fragment-count scenarios x seeds
      x trials;
    - the certificate summary fields are internally coherent;
    - all requested fragment-count scenario labels appear in the returned trial
      outcomes;
    - the same run writes both a structured summary snapshot and raw tables.
    """

    config, beam, prb_params, scenarios, base_seeds = _fragmentation_experiment_setup()

    cert = _run_certificate_experiment_and_write_results(
        experiment_name="fragmentation_experiment_v1",
        config=config,
        beam=beam,
        prb_params=prb_params,
        scenarios=scenarios,
        base_seeds=base_seeds,
        prediction_draws_per_trial=10,
    )

    expected_outcomes = len(scenarios) * len(base_seeds) * config.n_trials
    assert len(base_seeds) == 10
    assert config.n_trials == 100
    assert cert.trials == expected_outcomes
    assert len(cert.outcomes) == expected_outcomes
    assert 0 <= cert.successes <= cert.trials
    assert 0.0 <= cert.p_hat <= 1.0
    assert 0.0 <= cert.lcb <= 1.0

    scenario_labels = {outcome.scenario_label for outcome in cert.outcomes}
    assert scenario_labels == {
        "square_fragments_k01",
        "square_fragments_k04",
        "square_fragments_k09",
        "square_fragments_k16",
        "square_fragments_k25",
    }

    summary_text = _summary_path().read_text()
    table_text = _table_path().read_text()
    assert "[pooled_certificate]" in summary_text
    assert "[scenario.square_fragments_k01]" in summary_text
    assert "[scenario.square_fragments_k04]" in summary_text
    assert "[scenario.square_fragments_k09]" in summary_text
    assert "[scenario.square_fragments_k16]" in summary_text
    assert "[scenario.square_fragments_k25]" in summary_text
    assert "[trial_level_certificate_rows]" in table_text
    assert "[seed_level_dimensioning_rows]" in table_text


def test_blocked_area_experiment_starts_large_and_decreases_area_for_k1_and_k4() -> None:
    """Run the first blocked-area sweep while holding the square family fixed.

    Why this matters:
    - the fragmentation experiment showed that changing ``K`` alone does not
      separate Gaussian from uniform under the current truth model;
    - the next disciplined axis is blocked area itself, while keeping the
      shape family fixed to squares and using only ``K=1`` and ``K=4`` for
      completeness;
    - this experiment is meant to expose whether smaller blocked area moves
      the comparison toward the uniform baseline.

    Checks performed:
    - the scenario family uses only ``K in {1,4}``;
    - area fractions are ordered from larger to smaller values;
    - the certificate returns one outcome per scenario x seed x trial;
    - the experiment writes the expected summary and raw-table sections.
    """

    config, beam, prb_params, scenarios, base_seeds = _blocked_area_experiment_setup()

    assert tuple(scenario.square_area_fraction for scenario in scenarios[::2]) == (
        0.50,
        0.40,
        0.30,
        0.20,
        0.10,
    )
    assert {scenario.fragment_square_count for scenario in scenarios} == {1, 4}

    cert = _run_certificate_experiment_and_write_results(
        experiment_name="blocked_area_experiment_v1",
        config=config,
        beam=beam,
        prb_params=prb_params,
        scenarios=scenarios,
        base_seeds=base_seeds,
        prediction_draws_per_trial=10,
    )

    expected_outcomes = len(scenarios) * len(base_seeds) * config.n_trials
    assert cert.trials == expected_outcomes
    assert len(cert.outcomes) == expected_outcomes
    assert 0.0 <= cert.p_hat <= 1.0
    assert 0.0 <= cert.lcb <= 1.0

    summary_text = _summary_path().read_text()
    table_text = _table_path().read_text()
    assert "name = blocked_area_experiment_v1" in summary_text
    assert "[scenario.area_50_k01]" in summary_text
    assert "[scenario.area_50_k04]" in summary_text
    assert "[scenario.area_10_k01]" in summary_text
    assert "[scenario.area_10_k04]" in summary_text
    assert "[trial_level_certificate_rows]" in table_text
    assert "[seed_level_dimensioning_rows]" in table_text


def test_altitude_experiment_sweeps_from_balloon_height_to_upper_leo() -> None:
    """Run the first altitude sweep under the pathloss-enabled radio model.

    Why this matters:
    - once explicit slant-range pathloss is present, altitude becomes a real
      experiment axis instead of a missing parameter;
    - this test holds the obstruction family fixed to the 50%-blocked square
      cases and varies only altitude, so the resulting summaries can be read as
      an altitude effect rather than an area or fragmentation effect;
    - the aim is to measure whether model accuracy degrades as altitude rises
      from balloon-like heights toward upper LEO.

    Checks performed:
    - the altitude grid is exactly ``50, 150, 250, 350, 450`` units;
    - the pathloss exponent is fixed at ``2.0``;
    - the pooled outcome count matches altitude x scenario x seed x trial;
    - the written summary contains altitude sections for the endpoints of the
      sweep as well as the scenario-level sections beneath them.
    """

    config, beam, base_prb_params, altitudes, base_seeds = _altitude_experiment_setup()

    assert altitudes == (50.0, 150.0, 250.0, 350.0, 450.0)
    assert base_prb_params.pathloss_exponent == 2.0

    all_outcomes = []
    per_scenario_lines: list[str] = []
    raw_table_lines: list[str] = [
        "[trial_level_certificate_rows]",
        (
            "altitude_units,scenario_label,base_seed,trial_index,true_total_demand,"
            "uniform_predicted_total_demand,gaussian_predicted_total_demand,"
            "uniform_abs_demand_error,gaussian_abs_demand_error,"
            "gaussian_better,tie"
        ),
    ]

    for altitude in altitudes:
        prb_params = PRBDemandParams(
            required_rate_bps=base_prb_params.required_rate_bps,
            rb_bandwidth_hz=base_prb_params.rb_bandwidth_hz,
            snr0_linear=base_prb_params.snr0_linear,
            eta_min=base_prb_params.eta_min,
            pathloss_exponent=base_prb_params.pathloss_exponent,
            satellite_altitude_units=altitude,
        )
        scenarios = tuple(
            ObstructionFieldSpec(
                pattern_kind="square_fragments",
                scenario_label=f"alt_{int(altitude):03d}_k{square_count:02d}",
                extra_loss_db=10.0,
                square_area_fraction=0.5,
                fragment_square_count=square_count,
            )
            for square_count in (1, 4)
        )
        cert = run_gaussian_vs_uniform_certificate(
            config=config,
            beam=beam,
            prb_params=prb_params,
            scenarios=scenarios,
            base_seeds=base_seeds,
            alpha=0.05,
            threshold=0.5,
            prediction_draws_per_trial=10,
        )
        all_outcomes.extend(cert.outcomes)

        for outcome in cert.outcomes:
            raw_table_lines.append(
                ",".join(
                    [
                        _format_float(altitude),
                        outcome.scenario_label,
                        str(outcome.base_seed),
                        str(outcome.trial_index),
                        str(outcome.true_total_demand),
                        _format_float(outcome.uniform_predicted_total_demand),
                        _format_float(outcome.gaussian_predicted_total_demand),
                        _format_float(outcome.uniform_abs_demand_error),
                        _format_float(outcome.gaussian_abs_demand_error),
                        str(outcome.gaussian_better),
                        str(outcome.tie),
                    ]
                )
            )

        altitude_cert = certify_gaussian_better_from_error_pairs(
            error_pairs=tuple(
                (
                    outcome.uniform_abs_demand_error,
                    outcome.gaussian_abs_demand_error,
                )
                for outcome in cert.outcomes
            ),
            alpha=0.05,
            threshold=0.5,
            tie_policy="uniform_wins",
        )
        per_scenario_lines.extend(
            [
                f"[altitude.{int(altitude):03d}]",
                f"successes = {altitude_cert.successes}",
                f"trials = {altitude_cert.trials}",
                f"ties = {altitude_cert.ties}",
                f"p_hat = {_format_float(altitude_cert.p_hat)}",
                f"lcb = {_format_float(altitude_cert.lcb)}",
                f"certified = {altitude_cert.certified}",
                f"mean_uniform_abs_error = {_format_float(mean(outcome.uniform_abs_demand_error for outcome in cert.outcomes))}",
                f"mean_gaussian_abs_error = {_format_float(mean(outcome.gaussian_abs_demand_error for outcome in cert.outcomes))}",
                "",
            ]
        )

        for scenario in scenarios:
            scenario_label = scenario.scenario_label or scenario.pattern_kind
            scenario_outcomes = tuple(
                outcome for outcome in cert.outcomes if outcome.scenario_label == scenario_label
            )
            scenario_cert = certify_gaussian_better_from_error_pairs(
                error_pairs=tuple(
                    (
                        outcome.uniform_abs_demand_error,
                        outcome.gaussian_abs_demand_error,
                    )
                    for outcome in scenario_outcomes
                ),
                alpha=0.05,
                threshold=0.5,
                tie_policy="uniform_wins",
            )
            per_scenario_lines.extend(
                [
                    f"[scenario.{scenario_label}]",
                    f"successes = {scenario_cert.successes}",
                    f"trials = {scenario_cert.trials}",
                    f"ties = {scenario_cert.ties}",
                    f"p_hat = {_format_float(scenario_cert.p_hat)}",
                    f"lcb = {_format_float(scenario_cert.lcb)}",
                    f"certified = {scenario_cert.certified}",
                    f"mean_uniform_abs_error = {_format_float(mean(outcome.uniform_abs_demand_error for outcome in scenario_outcomes))}",
                    f"mean_gaussian_abs_error = {_format_float(mean(outcome.gaussian_abs_demand_error for outcome in scenario_outcomes))}",
                    "",
                ]
            )

    raw_table_lines.append("")
    raw_table_lines.extend(
        [
            "[seed_level_dimensioning_rows]",
            (
                "altitude_units,scenario_label,base_seed,truth_required_budget,"
                "uniform_required_budget,gaussian_required_budget"
            ),
        ]
    )
    for altitude in altitudes:
        prb_params = PRBDemandParams(
            required_rate_bps=base_prb_params.required_rate_bps,
            rb_bandwidth_hz=base_prb_params.rb_bandwidth_hz,
            snr0_linear=base_prb_params.snr0_linear,
            eta_min=base_prb_params.eta_min,
            pathloss_exponent=base_prb_params.pathloss_exponent,
            satellite_altitude_units=altitude,
        )
        for square_count in (1, 4):
            scenario_label = f"alt_{int(altitude):03d}_k{square_count:02d}"
            scenario = ObstructionFieldSpec(
                pattern_kind="square_fragments",
                scenario_label=scenario_label,
                extra_loss_db=10.0,
                square_area_fraction=0.5,
                fragment_square_count=square_count,
            )
            for seed in base_seeds:
                seed_config = ExperimentConfig(
                    ppp_intensity_lambda=config.ppp_intensity_lambda,
                    outage_target_epsilon=config.outage_target_epsilon,
                    candidate_rb_budgets=config.candidate_rb_budgets,
                    n_trials=config.n_trials,
                    base_seed=int(seed),
                    models=config.models,
                )
                dimensioning_result = run_truth_anchored_attenuation_comparison(
                    config=seed_config,
                    beam=beam,
                    prb_params=prb_params,
                    ground_truth_spec=scenario,
                    scenario_label=scenario_label,
                )
                budgets_by_model = {
                    estimate.model_id: estimate.required_budget
                    for estimate in dimensioning_result.model_comparison.estimates
                }
                raw_table_lines.append(
                    ",".join(
                        [
                            _format_float(altitude),
                            scenario_label,
                            str(seed),
                            str(dimensioning_result.ground_truth_required_budget),
                            str(budgets_by_model["uniform_baseline"]),
                            str(budgets_by_model["gaussian_l1"]),
                        ]
                    )
                )
    raw_table_lines.append("")

    pooled_certificate = certify_gaussian_better_from_error_pairs(
        error_pairs=tuple(
            (
                outcome.uniform_abs_demand_error,
                outcome.gaussian_abs_demand_error,
            )
            for outcome in all_outcomes
        ),
        alpha=0.05,
        threshold=0.5,
        tie_policy="uniform_wins",
    )
    _write_research_results(
        experiment_name="altitude_experiment_v1",
        config=config,
        beam=beam,
        prb_params=base_prb_params,
        base_seeds=base_seeds,
        prediction_draws_per_trial=10,
        pooled_certificate=pooled_certificate,
        per_scenario_lines=per_scenario_lines,
        raw_table_lines=raw_table_lines,
        extra_experiment_lines=[
            f"pathloss_exponent = {_format_float(base_prb_params.pathloss_exponent)}",
            "altitude_units = 50,150,250,350,450",
        ],
    )

    expected_outcomes = len(altitudes) * 2 * len(base_seeds) * config.n_trials
    assert pooled_certificate.trials == expected_outcomes
    assert 0.0 <= pooled_certificate.p_hat <= 1.0
    assert 0.0 <= pooled_certificate.lcb <= 1.0

    summary_text = _summary_path().read_text()
    table_text = _table_path().read_text()
    assert "name = altitude_experiment_v1" in summary_text
    assert "[altitude.050]" in summary_text
    assert "[altitude.450]" in summary_text
    assert "[scenario.alt_050_k01]" in summary_text
    assert "[scenario.alt_450_k04]" in summary_text
    assert "[trial_level_certificate_rows]" in table_text
    assert "[seed_level_dimensioning_rows]" in table_text


def test_corr_length_experiment_tunes_gaussian_correlation_at_fixed_altitude_250() -> None:
    """Sweep Gaussian correlation length at fixed altitude and fixed blockage.

    Why this matters:
    - the Gaussian sampler already uses a covariance matrix built from user
      locations, so after mean and variance matching the main remaining
      Gaussian degree of freedom is ``corr_length``;
    - fixing altitude at ``250`` and using one 50%-blocked square isolates that
      one spatial parameter without mixing in altitude or fragmentation again.

    Checks performed:
    - the correlation-length grid matches the intended sweep;
    - the altitude is fixed at ``250`` units throughout;
    - the pooled outcome count matches correlation lengths x seeds x trials;
    - the written summary contains sections for the shortest and longest
      correlation lengths.
    """

    base_config, beam, prb_params, corr_lengths, base_seeds, scenario = (
        _corr_length_experiment_setup()
    )

    assert corr_lengths == (0.5, 1.0, 2.0, 4.0, 8.0)
    assert prb_params.satellite_altitude_units == 250.0

    all_outcomes = []
    per_scenario_lines: list[str] = []
    raw_table_lines: list[str] = [
        "[trial_level_certificate_rows]",
        (
            "corr_length,scenario_label,base_seed,trial_index,true_total_demand,"
            "uniform_predicted_total_demand,gaussian_predicted_total_demand,"
            "uniform_abs_demand_error,gaussian_abs_demand_error,"
            "gaussian_better,tie"
        ),
    ]

    for corr_length in corr_lengths:
        config = _config_with_gaussian_corr_length(base_config, corr_length=corr_length)
        cert = run_gaussian_vs_uniform_certificate(
            config=config,
            beam=beam,
            prb_params=prb_params,
            scenarios=(scenario,),
            base_seeds=base_seeds,
            alpha=0.05,
            threshold=0.5,
            prediction_draws_per_trial=10,
        )
        all_outcomes.extend(cert.outcomes)

        for outcome in cert.outcomes:
            raw_table_lines.append(
                ",".join(
                    [
                        _format_float(corr_length),
                        outcome.scenario_label,
                        str(outcome.base_seed),
                        str(outcome.trial_index),
                        str(outcome.true_total_demand),
                        _format_float(outcome.uniform_predicted_total_demand),
                        _format_float(outcome.gaussian_predicted_total_demand),
                        _format_float(outcome.uniform_abs_demand_error),
                        _format_float(outcome.gaussian_abs_demand_error),
                        str(outcome.gaussian_better),
                        str(outcome.tie),
                    ]
                )
            )

        corr_cert = certify_gaussian_better_from_error_pairs(
            error_pairs=tuple(
                (
                    outcome.uniform_abs_demand_error,
                    outcome.gaussian_abs_demand_error,
                )
                for outcome in cert.outcomes
            ),
            alpha=0.05,
            threshold=0.5,
            tie_policy="uniform_wins",
        )
        per_scenario_lines.extend(
            [
                f"[corr_length.{str(corr_length).replace('.', 'p')}]",
                f"successes = {corr_cert.successes}",
                f"trials = {corr_cert.trials}",
                f"ties = {corr_cert.ties}",
                f"p_hat = {_format_float(corr_cert.p_hat)}",
                f"lcb = {_format_float(corr_cert.lcb)}",
                f"certified = {corr_cert.certified}",
                f"mean_uniform_abs_error = {_format_float(mean(outcome.uniform_abs_demand_error for outcome in cert.outcomes))}",
                f"mean_gaussian_abs_error = {_format_float(mean(outcome.gaussian_abs_demand_error for outcome in cert.outcomes))}",
                "",
            ]
        )

    raw_table_lines.append("")
    raw_table_lines.extend(
        [
            "[seed_level_dimensioning_rows]",
            (
                "corr_length,scenario_label,base_seed,truth_required_budget,"
                "uniform_required_budget,gaussian_required_budget"
            ),
        ]
    )
    for corr_length in corr_lengths:
        config = _config_with_gaussian_corr_length(base_config, corr_length=corr_length)
        for seed in base_seeds:
            seed_config = ExperimentConfig(
                ppp_intensity_lambda=config.ppp_intensity_lambda,
                outage_target_epsilon=config.outage_target_epsilon,
                candidate_rb_budgets=config.candidate_rb_budgets,
                n_trials=config.n_trials,
                base_seed=int(seed),
                models=config.models,
            )
            dimensioning_result = run_truth_anchored_attenuation_comparison(
                config=seed_config,
                beam=beam,
                prb_params=prb_params,
                ground_truth_spec=scenario,
                scenario_label=scenario.scenario_label,
            )
            budgets_by_model = {
                estimate.model_id: estimate.required_budget
                for estimate in dimensioning_result.model_comparison.estimates
            }
            raw_table_lines.append(
                ",".join(
                    [
                        _format_float(corr_length),
                        scenario.scenario_label,
                        str(seed),
                        str(dimensioning_result.ground_truth_required_budget),
                        str(budgets_by_model["uniform_baseline"]),
                        str(budgets_by_model["gaussian_l1"]),
                    ]
                )
            )
    raw_table_lines.append("")

    pooled_certificate = certify_gaussian_better_from_error_pairs(
        error_pairs=tuple(
            (
                outcome.uniform_abs_demand_error,
                outcome.gaussian_abs_demand_error,
            )
            for outcome in all_outcomes
        ),
        alpha=0.05,
        threshold=0.5,
        tie_policy="uniform_wins",
    )
    _write_research_results(
        experiment_name="corr_length_experiment_v1",
        config=base_config,
        beam=beam,
        prb_params=prb_params,
        base_seeds=base_seeds,
        prediction_draws_per_trial=10,
        pooled_certificate=pooled_certificate,
        per_scenario_lines=per_scenario_lines,
        raw_table_lines=raw_table_lines,
        extra_experiment_lines=[
            f"pathloss_exponent = {_format_float(prb_params.pathloss_exponent)}",
            f"altitude_units = {_format_float(prb_params.satellite_altitude_units)}",
            "corr_lengths = 0.5,1.0,2.0,4.0,8.0",
        ],
    )

    expected_outcomes = len(corr_lengths) * len(base_seeds) * base_config.n_trials
    assert pooled_certificate.trials == expected_outcomes
    assert 0.0 <= pooled_certificate.p_hat <= 1.0
    assert 0.0 <= pooled_certificate.lcb <= 1.0

    summary_text = _summary_path().read_text()
    table_text = _table_path().read_text()
    assert "name = corr_length_experiment_v1" in summary_text
    assert "[corr_length.0p5]" in summary_text
    assert "[corr_length.8p0]" in summary_text
    assert "[trial_level_certificate_rows]" in table_text
    assert "[seed_level_dimensioning_rows]" in table_text
