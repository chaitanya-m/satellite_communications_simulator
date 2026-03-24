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
   - several obstruction scenarios.
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


def _results_path() -> Path:
    """Return the root-level results file used by research-hypothesis tests."""

    return Path(__file__).resolve().parents[1] / "results.txt"


def _format_float(value: float) -> str:
    """Format floats in a stable human-readable form for results.txt."""

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
) -> None:
    """Write one structured research-result snapshot to ``results.txt``.

    Why this helper exists:
    - research-hypothesis tests should not only pass or fail; they should also
      leave behind a structured, reproducible summary of what was run and what
      was observed;
    - keeping the writer in this file ensures the research-test definitions and
      their result-reporting logic stay together.

    Current policy:
    - overwrite ``results.txt`` with the latest deterministic snapshot from this
      research file;
    - use a stable sectioned plain-text format so future experiments can add
      more sections without losing readability.
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
    _results_path().write_text("\n".join(lines) + "\n")


def _research_scale_setup() -> tuple[
    ExperimentConfig,
    CircularBeam,
    PRBDemandParams,
    tuple[ObstructionFieldSpec, ...],
    tuple[int, ...],
]:
    """Return one documented research-scale setup for research-hypothesis tests.

    Chosen regime:
    - beam radius = 10, so beam area is ``pi * 10^2 ~= 314.16``;
    - PPP intensity = 1 user per unit area, so expected users per trial are
      also about 314, i.e. a few hundred users in the footprint;
    - PRB-demand parameters are chosen so ``max_prb_per_user = 10`` exactly;
    - the tested budget grid runs from 500 to 6000, which stays below
      ``20 * expected_users ~= 6283``.
    - the outer experiment uses 10 independent seed paths and 100 PPP trials
      per seed-scenario block.

    Two levels of randomness are important:
    - outer randomness comes from the PPP user geometry changing from trial to
      trial;
    - inner randomness comes from the model-side shadowing draws performed on
      one fixed user geometry when the certificate runner estimates each
      model's predicted mean total demand.

    The values here are intended as a stable research-scale baseline for
    hypothesis testing. They are not yet claimed to be the final publication
    configuration, but they are explicitly chosen to live in the same part of
    the parameter space as the intended study.
    """

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
                uniform=UniformParams(low_log=-1.5, high_log=0.2),
            ),
            ModelSpec(
                model_id="gaussian_l1",
                kind="gaussian",
                gaussian=GaussianParams(mean_log=-0.75, variance_log=0.4, corr_length=2.0),
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
    scenarios = (
        ObstructionFieldSpec(pattern_kind="square_center", extra_loss_db=10.0),
        ObstructionFieldSpec(
            pattern_kind="vertical_bands",
            extra_loss_db=10.0,
            vertical_band_count=6,
        ),
        ObstructionFieldSpec(
            pattern_kind="multi_circles",
            extra_loss_db=10.0,
            multi_circle_count=4,
            multi_circle_radius_ratio=0.18,
            multi_circle_ring_ratio=0.45,
        ),
    )
    # Standard seed set for this research-scale test regime.
    base_seeds = tuple(range(101, 111))
    return config, beam, prb_params, scenarios, base_seeds


def test_research_scale_truth_anchored_run_uses_few_hundred_users_and_bounded_grid() -> None:
    """Run a truth-anchored research-hypothesis setup in a study-scale regime.

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
    - a truth-anchored comparison run returns required budgets that lie on the
      tested grid for both truth and models.
    """

    config, beam, prb_params, scenarios, _base_seeds = _research_scale_setup()
    expected_users = config.ppp_intensity_lambda * beam.area

    assert 200.0 <= expected_users <= 400.0
    assert math.isclose(expected_users, math.pi * 100.0, rel_tol=1e-12)
    assert prb_params.max_prb_per_user == 10
    assert max(config.candidate_rb_budgets) <= 20.0 * expected_users
    assert config.n_trials == 100

    result = run_truth_anchored_attenuation_comparison(
        config=config,
        beam=beam,
        prb_params=prb_params,
        ground_truth_spec=scenarios[0],
        scenario_label="research_square_center",
    )

    assert result.scenario_label == "research_square_center"
    assert result.ground_truth_required_budget in set(config.candidate_rb_budgets)
    for estimate in result.model_comparison.estimates:
        assert estimate.required_budget in set(config.candidate_rb_budgets)


def test_research_scale_certificate_runs_across_multiple_scenarios() -> None:
    """Run the pooled certificate in the same research-scale regime.

    Why this matters:
    - the certificate runner is the part of the code most closely tied to the
      current research question;
    - this test documents and checks the current pooling behavior across
      scenarios, seeds, and trials in a non-trivial user regime;
    - it also documents the standard repeated-trial scale used in this file:
      10 seed paths and 100 PPP trials per seed-scenario block.
    - this test is meant to evolve toward an explicit research claim about when
      Gaussian should or should not outperform uniform.

    Checks performed:
    - the number of Bernoulli outcomes matches scenarios x seeds x trials;
    - the certificate summary fields are internally coherent;
    - all requested scenario labels appear in the returned trial outcomes;
    - the same run writes a structured research snapshot to ``results.txt``.
    """

    config, beam, prb_params, scenarios, base_seeds = _research_scale_setup()

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
    assert scenario_labels == {"square_center", "vertical_bands", "multi_circles"}

    # Derive one per-scenario certificate summary from the pooled trial
    # outcomes, without rerunning the experiment. This keeps the reporting
    # deterministic and avoids duplicate computation.
    per_scenario_lines: list[str] = []
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

    _write_research_results(
        experiment_name="research_scale_v1",
        config=config,
        beam=beam,
        prb_params=prb_params,
        base_seeds=base_seeds,
        prediction_draws_per_trial=10,
        pooled_certificate=cert,
        per_scenario_lines=per_scenario_lines,
    )

    results_text = _results_path().read_text()
    assert "[pooled_certificate]" in results_text
    assert "[scenario.square_center]" in results_text
    assert "[scenario.vertical_bands]" in results_text
    assert "[scenario.multi_circles]" in results_text
