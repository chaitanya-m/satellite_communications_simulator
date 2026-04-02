"""Tests for model-comparison attenuation experiment contracts.

Scope:
- Validate that the typed experiment contracts reject malformed inputs early.
- Validate that configuration objects preserve their meaning when serialized and
  deserialized.
- Validate the distinction between budget-level result objects and the
  trial-level Gaussian-versus-uniform certificate objects.

Out of scope:
- PPP sampling.
- Obstruction geometry.
- Shadowing-field simulation.
- PRB-demand mapping.
- End-to-end experiment-runner behavior.
"""

from __future__ import annotations

import pytest

from experiments.satellites.attenuation_contracts import (
    ComparisonResult,
    DiscreteLogShadowingMarginal,
    ExperimentConfig,
    GaussianParams,
    GaussianVsUniformCertificateResult,
    ModelBudgetEstimate,
    ModelSpec,
    TruthAnchoredComparisonResult,
    UniformParams,
)


def test_experiment_config_round_trip() -> None:
    """ExperimentConfig should round-trip through plain-Python serialization.

    Why this matters:
    - experiment configurations are likely to be logged, checkpointed, or
      passed between scripts;
    - a round-trip should preserve the statistical meaning of the run, not just
      the field names.

    Checks performed:
    - a populated ``ExperimentConfig`` converts to a plain dict;
    - reconstructing from that dict yields an object equal to the original.
    """
    cfg = ExperimentConfig(
        ppp_intensity_lambda=1_000.0,
        outage_target_epsilon=0.05,
        candidate_rb_budgets=(2_000_000, 2_250_000, 2_500_000),
        n_trials=500,
        base_seed=123,
        models=(
            ModelSpec(
                model_id="uniform_baseline",
                kind="uniform",
                uniform=UniformParams(low_log=-2.0, high_log=0.5),
            ),
            ModelSpec(
                model_id="gauss_l100",
                kind="gaussian",
                gaussian=GaussianParams(mean_log=-0.75, variance_log=0.3, corr_length=100.0),
            ),
        ),
    )

    payload = cfg.to_dict()
    restored = ExperimentConfig.from_dict(payload)
    assert restored == cfg


def test_experiment_config_round_trip_with_shared_marginal_models() -> None:
    """Shared-marginal configs should round-trip through serialization too."""

    marginal = DiscreteLogShadowingMarginal(
        values_log=(-2.302585093, 0.0),
        probabilities=(0.5, 0.5),
    )
    cfg = ExperimentConfig(
        ppp_intensity_lambda=50.0,
        outage_target_epsilon=0.2,
        candidate_rb_budgets=(200, 400, 600),
        n_trials=20,
        base_seed=7,
        models=(
            ModelSpec(
                model_id="uniform_baseline",
                kind="uniform",
                uniform=UniformParams(marginal=marginal),
            ),
            ModelSpec(
                model_id="gaussian_l1",
                kind="gaussian",
                gaussian=GaussianParams(corr_length=2.0, marginal=marginal),
            ),
        ),
    )

    restored = ExperimentConfig.from_dict(cfg.to_dict())
    assert restored == cfg


def test_model_spec_requires_matching_params() -> None:
    """ModelSpec should enforce kind/parameter compatibility.

    Why this matters:
    - ``ModelSpec`` is a tagged union, so its ``kind`` field must agree with
      the attached parameter object;
    - invalid combinations should fail immediately instead of leaking into the
      runner logic.

    Checks performed:
    - ``kind="uniform"`` without ``UniformParams`` is rejected;
    - ``kind="gaussian"`` without ``GaussianParams`` is rejected;
    - a uniform model carrying Gaussian parameters is rejected.
    """
    with pytest.raises(ValueError, match="requires uniform"):
        ModelSpec(model_id="u", kind="uniform")

    with pytest.raises(ValueError, match="requires gaussian"):
        ModelSpec(model_id="g", kind="gaussian")

    with pytest.raises(ValueError, match="must not include gaussian"):
        ModelSpec(
            model_id="bad",
            kind="uniform",
            uniform=UniformParams(low_log=-1.0, high_log=1.0),
            gaussian=GaussianParams(mean_log=0.0, variance_log=1.0, corr_length=10.0),
        )


def test_experiment_config_rejects_duplicate_model_ids() -> None:
    """ExperimentConfig should require unique model identifiers.

    Why this matters:
    - model ids are used later to match estimates, baselines, and deltas;
    - duplicate ids would make downstream comparison objects ambiguous.
    - example failure: gaussian and uniform models accidentally sharing the same id

    Checks performed:
    - repeated ``model_id`` values raise ``ValueError``.
    """
    with pytest.raises(ValueError, match="unique"):
        ExperimentConfig(
            ppp_intensity_lambda=100.0,
            outage_target_epsilon=0.1,
            candidate_rb_budgets=(10, 20),
            n_trials=10,
            models=(
                ModelSpec(
                    model_id="m1",
                    kind="uniform",
                    uniform=UniformParams(low_log=-1.0, high_log=1.0),
                ),
                ModelSpec(
                    model_id="m1",
                    kind="gaussian",
                    gaussian=GaussianParams(mean_log=0.0, variance_log=1.0, corr_length=10.0),
                ),
            ),
        )


def test_model_budget_estimate_validates_probability_bounds() -> None:
    """ModelBudgetEstimate should reject invalid outage values.

    Why this matters:
    - ``ModelBudgetEstimate`` is a budget-level summary object;
    - its ``outage_by_budget`` entries are probabilities and therefore must
      stay within ``[0, 1]``.

    Checks performed:
    - an outage value above 1 is rejected.
    """
    with pytest.raises(ValueError, match="in \\[0, 1\\]"):
        ModelBudgetEstimate(
            model_id="uniform_baseline",
            outage_by_budget=(0.2, 1.1),
            required_budget=10,
            n_trials=100,
        )


def test_comparison_result_requires_baseline_in_estimates() -> None:
    """ComparisonResult baseline id should appear in estimates.

    Why this matters:
    - baseline-relative budget deltas only make sense if the baseline estimate
      is actually present in the comparison set.

    Checks performed:
    - a result without a baseline estimate is rejected
    """
    with pytest.raises(ValueError, match="must exist"):
        ComparisonResult(
            baseline_model_id="uniform_baseline",
            estimates=(
                ModelBudgetEstimate(
                    model_id="gauss_l100",
                    outage_by_budget=(0.3, 0.2, 0.1),
                    required_budget=20,
                    n_trials=100,
                ),
            ),
            delta_required_budget_vs_baseline=(("gauss_l100", 5),),
        )


def test_uniform_params_ordering_constraint() -> None:
    """UniformParams should enforce strict lower/upper bound ordering.

    Why this matters:
    - the uniform baseline uses a closed interval on log-shadowing;
    - if the lower bound is not strictly below the upper bound, the parameter
      object does not describe a valid sampling interval.
    - correct usage example: UniformParams(low_log=-1.0, high_log=1.0), which means 
    sampling from [10^-1, 10^1] = [0.1, 10]., where the low_log and high_log are the
    attenuation factors in log10 scale.

    Checks performed:
    - equal lower and upper bounds are rejected.
    """
    with pytest.raises(ValueError, match="low_log < high_log"):
        UniformParams(low_log=1.0, high_log=1.0)


def test_discrete_log_shadowing_marginal_requires_probabilities_to_sum_to_one() -> None:
    """The shared marginal contract should fail fast on invalid probabilities."""

    with pytest.raises(ValueError, match="sum to 1"):
        DiscreteLogShadowingMarginal(
            values_log=(-1.0, 0.0),
            probabilities=(0.2, 0.7),
        )


def test_truth_anchored_result_validates_probability_bounds() -> None:
    """TruthAnchoredComparisonResult should reject invalid truth probabilities.

    Why this matters:
    - ``TruthAnchoredComparisonResult`` is still a budget-level object;
    - its ground-truth side stores outage probabilities over a tested budget
      grid, so those values must remain in ``[0, 1]``.

    Checks performed:
    - a ground-truth outage value above 1 is rejected.
    """

    comparison = ComparisonResult(
        baseline_model_id="uniform_baseline",
        estimates=(
            ModelBudgetEstimate(
                model_id="uniform_baseline",
                outage_by_budget=(0.4, 0.2),
                required_budget=100,
                n_trials=20,
            ),
        ),
        delta_required_budget_vs_baseline=(),
    )

    with pytest.raises(ValueError, match="in \\[0, 1\\]"):
        TruthAnchoredComparisonResult(
            scenario_label="square_center",
            ground_truth_outage_by_budget=(0.2, 1.2),
            ground_truth_required_budget=100,
            model_comparison=comparison,
            delta_required_budget_vs_truth=(("uniform_baseline", 0),),
        )


def test_gaussian_vs_uniform_certificate_validates_success_counts() -> None:
    """GaussianVsUniformCertificateResult should reject invalid count relations.

    Why this matters:
    - the certificate summary stores Bernoulli counts aggregated from many
      trial-level comparison outcomes;
    - those counts must obey basic consistency rules before any statistical
      interpretation is possible.

    Checks performed:
    - ``successes > trials`` is rejected.
    """

    with pytest.raises(ValueError, match="successes must be <= trials"):
        GaussianVsUniformCertificateResult(
            alpha=0.05,
            threshold=0.5,
            successes=3,
            trials=2,
            p_hat=0.5,
            lcb=0.4,
            certified=False,
            ties=0,
            outcomes=(),
        )
