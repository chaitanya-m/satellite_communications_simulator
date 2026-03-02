"""Contracts for model-comparison RB-dimensioning experiments.

This module supports the workflow:
1) define common experiment settings (PPP intensity, outage target, budget grid);
2) define a model set (uniform baseline + Gaussian parameterizations);
3) run repeated trials per model and estimate outage curves;
4) extract required budgets and compare deltas against the baseline.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Literal, Tuple


ModelKind = Literal["uniform", "gaussian"]


@dataclass(frozen=True)
class GaussianParams:
    """Parameterization for a Gaussian-field simulator variant."""

    mean_log: float
    variance_log: float
    corr_length: float

    def __post_init__(self) -> None:
        if self.variance_log <= 0.0:
            raise ValueError("variance_log must be positive")
        if self.corr_length <= 0.0:
            raise ValueError("corr_length must be positive")


@dataclass(frozen=True)
class UniformParams:
    """Uniform baseline on log-shadowing, sampled independently per user."""

    low_log: float
    high_log: float

    def __post_init__(self) -> None:
        if self.low_log >= self.high_log:
            raise ValueError("uniform bounds must satisfy low_log < high_log")


@dataclass(frozen=True)
class ModelSpec:
    """One simulator model used in the comparison set."""

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
    """Top-level common settings for model-comparison experiments."""

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
        for m in payload["models"]:
            uniform = UniformParams(**m["uniform"]) if m.get("uniform") else None
            gaussian = GaussianParams(**m["gaussian"]) if m.get("gaussian") else None
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
    """Estimated outage curve and derived required budget for one model."""

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
    """Aggregate model-comparison outputs for one experiment run."""

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

