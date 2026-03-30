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
    ExperimentConfig,
    GaussianParams,
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
    lines.extend(per_scenario_lines)
    _summary_path().write_text("\n".join(lines) + "\n")
    _table_path().write_text("\n".join(raw_table_lines) + "\n")


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
    - keep the comparison simple by using one shared target mean/variance for
      both candidate models;
    - for the Gaussian model, that target is supplied directly as
      ``mean_log`` and ``variance_log`` because the Gaussian parameterization
      exposes those moments explicitly;
    - for the uniform model, variance is not a direct parameter: the model is
      parameterized by ``low_log`` and ``high_log`` instead, so those bounds
      must be computed from the desired mean/variance;
    - for ``U ~ Uniform[a, b]``, we have
      ``E[U] = (a + b) / 2`` and ``Var(U) = (b - a)^2 / 12``;
    - solving those equations for target mean ``m`` and variance ``v`` gives
      half-width ``sqrt(3v)``, so
      ``low_log = m - sqrt(3v)`` and ``high_log = m + sqrt(3v)``.

    Why this is the first calibration step:
    - without at least matching the first two moments, the comparison is
      confounded by a trivial marginal mismatch before we even get to the
      intended question of model structure;
    - this is still the simplest possible calibration change because it does
      not alter the rest of the experiment flow or introduce scenario-specific
      fitting logic.

    The values here are intended as the first stable baseline for the
    fragmentation experiment. They are not yet claimed to be the final
    publication configuration, but they are explicit and controlled enough to
    support scenario-by-scenario comparisons.
    """

    # Simplest fair calibration step:
    # keep one shared mean/variance target for both comparison models, so the
    # experiment is not confounded by an avoidable first-moment or second-
    # moment mismatch before we study anything more subtle.
    comparison_mean_log = -0.75
    comparison_variance_log = 0.4
    # Uniform does have variance, but it is implied by its interval rather than
    # supplied directly. For target variance v, the required half-width is
    # sqrt(3v), because Var(Uniform[m-h, m+h]) = h^2 / 3 = v.
    uniform_half_width = math.sqrt(3.0 * comparison_variance_log)

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
                uniform=UniformParams(
                    low_log=comparison_mean_log - uniform_half_width,
                    high_log=comparison_mean_log + uniform_half_width,
                ),
            ),
            ModelSpec(
                model_id="gaussian_l1",
                kind="gaussian",
                gaussian=GaussianParams(
                    mean_log=comparison_mean_log,
                    variance_log=comparison_variance_log,
                    corr_length=2.0,
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

    # Derive one per-scenario certificate summary from the pooled trial
    # outcomes, without rerunning the experiment. This keeps the reporting
    # deterministic and avoids duplicate computation.
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
    for scenario_label in sorted(scenario_labels):
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
    for scenario_label in sorted(scenario_labels):
        scenario = scenarios_by_label[scenario_label]
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
        experiment_name="fragmentation_experiment_v1",
        config=config,
        beam=beam,
        prb_params=prb_params,
        base_seeds=base_seeds,
        prediction_draws_per_trial=10,
        pooled_certificate=cert,
        per_scenario_lines=per_scenario_lines,
        raw_table_lines=raw_table_lines,
    )

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
