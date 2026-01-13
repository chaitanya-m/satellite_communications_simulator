"""Adapter boundary for simulator integrations."""

from __future__ import annotations

from typing import Any, Dict, Protocol

from sim.config import SimulationConfig


class SimulatorAdapterError(RuntimeError):
    """Base error type for simulator adapter failures."""


class ConfigValidationError(SimulatorAdapterError):
    """Raised when the simulator configuration is invalid."""


class ExecutionError(SimulatorAdapterError):
    """Raised when the simulator backend fails to execute."""


class OutputParsingError(SimulatorAdapterError):
    """Raised when simulator outputs cannot be parsed into metrics."""


class SimulatorAdapter(Protocol):
    """Adapter contract between orchestrator and simulator backend."""

    def configure(self, config: SimulationConfig) -> None:
        """Validate and store simulator configuration."""

    def run_trial(self, *, design: Any, seed: int) -> Dict[str, float]:
        """Run one simulation trial for a given design and seed."""

    def describe(self) -> Dict[str, str]:
        """Return backend metadata for logging and diagnostics."""
