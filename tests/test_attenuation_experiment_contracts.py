"""Tests for model-comparison attenuation experiment contracts."""

from __future__ import annotations

import pytest

from experiments.satellites.attenuation_contracts import (
    ComparisonResult,
    ExperimentConfig,
    GaussianParams,
    ModelBudgetEstimate,
    ModelSpec,
    UniformParams,
)


def test_experiment_config_round_trip() -> None:
    """ExperimentConfig should round-trip through dict serialization."""
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


def test_model_spec_requires_matching_params() -> None:
    """ModelSpec should enforce kind/parameter compatibility."""
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
    """ExperimentConfig should require unique model identifiers."""
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
    """ModelBudgetEstimate should reject invalid outage values."""
    with pytest.raises(ValueError, match="in \\[0, 1\\]"):
        ModelBudgetEstimate(
            model_id="uniform_baseline",
            outage_by_budget=(0.2, 1.1),
            required_budget=10,
            n_trials=100,
        )


def test_comparison_result_requires_baseline_in_estimates() -> None:
    """ComparisonResult baseline id should appear in estimates."""
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
    """UniformParams should enforce strict lower/upper bound ordering."""
    with pytest.raises(ValueError, match="low_log < high_log"):
        UniformParams(low_log=1.0, high_log=1.0)

