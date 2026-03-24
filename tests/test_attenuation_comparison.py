"""Smoke tests for attenuation-comparison experiment runners.

Scope:
- Validate that the runner functions return coherent objects in small,
  fast-to-execute regimes.
- Validate reproducibility and basic counting logic.

Out of scope:
- Establishing a research result.
- Running a study-scale configuration with hundreds of expected users.
- Proving that Gaussian should beat uniform under a particular scientific
  hypothesis.

Why this file exists:
- These tests are intentionally small so they can run quickly in the regular
  test suite.
- The more reader-facing explanation of the intended experimental procedure now
  lives in ``tests/test_research_hypotheses.py``.
"""

from __future__ import annotations

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


def _is_non_increasing(values: tuple[float, ...]) -> bool:
    return all(values[i + 1] <= values[i] for i in range(len(values) - 1))


def test_truth_anchored_comparison_smoke_run_outputs_consistent_shapes() -> None:
    """A small truth-anchored run should produce coherent typed outputs.

    Why this matters:
    - the truth-anchored runner combines PPP sampling, truth-side obstruction
      evaluation, model-side simulation, budget-level aggregation, and typed
      result assembly;
    - this smoke test checks that those pieces fit together coherently in a
      small regime.

    Checks performed:
    - truth-side outage vector length matches the tested budget grid;
    - truth-side outage values lie in ``[0, 1]`` and are non-increasing in
      budget;
    - truth-side required budget lies on the tested grid;
    - each model estimate has the same structural properties;
    - the model-vs-truth delta entries contain the expected model ids.
    """

    config = ExperimentConfig(
        ppp_intensity_lambda=2.0,
        outage_target_epsilon=0.2,
        candidate_rb_budgets=(100, 300, 600, 1000),
        n_trials=30,
        base_seed=123,
        models=(
            ModelSpec(
                model_id="uniform_baseline",
                kind="uniform",
                uniform=UniformParams(low_log=-1.5, high_log=0.2),
            ),
            ModelSpec(
                model_id="gaussian_l1",
                kind="gaussian",
                gaussian=GaussianParams(mean_log=-0.6, variance_log=0.4, corr_length=0.8),
            ),
        ),
    )
    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=1.0)
    prb_params = PRBDemandParams(
        required_rate_bps=1_000.0,
        rb_bandwidth_hz=100.0,
        snr0_linear=1.0,
        eta_min=0.1,
    )
    truth_spec = ObstructionFieldSpec(
        pattern_kind="square_center",
        extra_loss_db=12.0,
        square_area_fraction=0.5,
    )

    result = run_truth_anchored_attenuation_comparison(
        config=config,
        beam=beam,
        prb_params=prb_params,
        ground_truth_spec=truth_spec,
        scenario_label="square_center_fixed_loss",
    )

    assert result.scenario_label == "square_center_fixed_loss"
    assert len(result.ground_truth_outage_by_budget) == len(config.candidate_rb_budgets)
    assert all(0.0 <= p <= 1.0 for p in result.ground_truth_outage_by_budget)
    assert _is_non_increasing(result.ground_truth_outage_by_budget)
    assert result.ground_truth_required_budget in set(config.candidate_rb_budgets)

    assert len(result.model_comparison.estimates) == 2
    for estimate in result.model_comparison.estimates:
        assert len(estimate.outage_by_budget) == len(config.candidate_rb_budgets)
        assert _is_non_increasing(estimate.outage_by_budget)
        assert estimate.required_budget in set(config.candidate_rb_budgets)

    delta_ids = {model_id for model_id, _ in result.delta_required_budget_vs_truth}
    assert delta_ids == {"uniform_baseline", "gaussian_l1"}


def test_truth_anchored_comparison_is_reproducible_for_same_seed() -> None:
    """Same settings and base seed should reproduce identical truth-side output.

    Why this matters:
    - the experiment runners are stochastic, so reproducibility under fixed
      seeds is essential for debugging and for preserving study artifacts.

    Checks performed:
    - running the truth-anchored runner twice with identical inputs yields
      identical result objects.
    """

    config = ExperimentConfig(
        ppp_intensity_lambda=1.5,
        outage_target_epsilon=0.25,
        candidate_rb_budgets=(80, 120, 180),
        n_trials=20,
        base_seed=999,
        models=(
            ModelSpec(
                model_id="uniform_baseline",
                kind="uniform",
                uniform=UniformParams(low_log=-1.0, high_log=0.0),
            ),
            ModelSpec(
                model_id="gaussian_l1",
                kind="gaussian",
                gaussian=GaussianParams(mean_log=-0.5, variance_log=0.2, corr_length=0.6),
            ),
        ),
    )
    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=1.0)
    prb_params = PRBDemandParams(
        required_rate_bps=800.0,
        rb_bandwidth_hz=100.0,
        snr0_linear=1.0,
        eta_min=0.1,
    )
    truth_spec = ObstructionFieldSpec(
        pattern_kind="vertical_bands",
        extra_loss_db=8.0,
        vertical_band_count=6,
    )

    r1 = run_truth_anchored_attenuation_comparison(
        config=config,
        beam=beam,
        prb_params=prb_params,
        ground_truth_spec=truth_spec,
    )
    r2 = run_truth_anchored_attenuation_comparison(
        config=config,
        beam=beam,
        prb_params=prb_params,
        ground_truth_spec=truth_spec,
    )

    assert r1 == r2


def test_certify_gaussian_better_from_error_pairs_success_case() -> None:
    """Certificate helper should count trial-level wins correctly.

    Why this matters:
    - this helper is the smallest piece of the certificate logic, so it is the
      easiest place to verify the Bernoulli counting rules directly.

    Checks performed:
    - strict Gaussian wins are counted as successes;
    - with ``tie_policy="uniform_wins"``, a tie counts as a non-success;
    - the empirical success rate ``p_hat`` is computed correctly;
    - one trial-level outcome object is emitted per supplied error pair.
    """

    result = certify_gaussian_better_from_error_pairs(
        error_pairs=((5, 2), (3, 1), (7, 4), (4, 4)),
        alpha=0.05,
        threshold=0.5,
        tie_policy="uniform_wins",
    )

    # Three strict wins out of four Bernoulli trials (tie counts as non-success).
    assert result.successes == 3
    assert result.trials == 4
    assert result.p_hat == 0.75
    assert 0.0 <= result.lcb <= 1.0
    assert len(result.outcomes) == 4
    assert result.outcomes[0].trial_index == 0


def test_run_gaussian_vs_uniform_certificate_smoke() -> None:
    """Run a small certificate configuration and validate output consistency.

    Why this matters:
    - the certificate runner has a different statistical meaning from the
      budget-level runners: its Bernoulli unit is one PPP trial rather than one
      budget-grid summary;
    - this smoke test checks the pooling logic across scenarios, seeds, and
      trials in a small regime.

    Checks performed:
    - the number of returned trial outcomes matches
      scenarios x seeds x trials;
    - certificate summary fields stay in valid numeric ranges;
    - returned trial-level outcome objects contain sensible non-negative
      demand/error fields.
    """

    config = ExperimentConfig(
        ppp_intensity_lambda=2.0,
        outage_target_epsilon=0.2,
        candidate_rb_budgets=(100, 300, 600, 1000),
        n_trials=20,
        base_seed=123,
        models=(
            ModelSpec(
                model_id="uniform_baseline",
                kind="uniform",
                uniform=UniformParams(low_log=-1.5, high_log=0.2),
            ),
            ModelSpec(
                model_id="gaussian_l1",
                kind="gaussian",
                gaussian=GaussianParams(mean_log=-0.75, variance_log=0.4, corr_length=0.8),
            ),
        ),
    )
    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=1.0)
    prb_params = PRBDemandParams(
        required_rate_bps=1_000.0,
        rb_bandwidth_hz=100.0,
        snr0_linear=1.0,
        eta_min=0.1,
    )
    scenarios = (
        ObstructionFieldSpec(pattern_kind="square_center", extra_loss_db=10.0),
        ObstructionFieldSpec(pattern_kind="vertical_bands", extra_loss_db=10.0, vertical_band_count=6),
    )
    base_seeds = (101, 202, 303)

    cert = run_gaussian_vs_uniform_certificate(
        config=config,
        beam=beam,
        prb_params=prb_params,
        scenarios=scenarios,
        base_seeds=base_seeds,
        alpha=0.05,
        threshold=0.5,
        prediction_draws_per_trial=8,
    )

    expected_outcomes = len(scenarios) * len(base_seeds) * config.n_trials
    assert cert.trials == expected_outcomes
    assert len(cert.outcomes) == expected_outcomes
    assert 0.0 <= cert.p_hat <= 1.0
    assert 0.0 <= cert.lcb <= 1.0
    first = cert.outcomes[0]
    assert first.trial_index >= 0
    assert first.true_total_demand >= 0
    assert first.uniform_abs_demand_error >= 0.0
    assert first.gaussian_abs_demand_error >= 0.0
