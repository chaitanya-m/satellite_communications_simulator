"""Local PPP simulator adapter for the Dimensioning_3D backend."""

from __future__ import annotations

import random
from typing import Any, Dict

from sim.config import SimulationConfig
from sim.dimensioning_3d import Dimensioning_3D
from sim.interface import ConfigValidationError, SimulatorAdapter


class LocalPPPSimulatorAdapter(SimulatorAdapter):
    """Adapter that runs the in-process PPP simulator with a config contract."""

    def __init__(self) -> None:
        self._config: SimulationConfig | None = None

    def configure(self, config: SimulationConfig) -> None:
        if config.users.lat_min_deg > config.users.lat_max_deg:
            raise ConfigValidationError("lat_min_deg must be <= lat_max_deg")
        if config.satellites.altitude_km <= 0.0:
            raise ConfigValidationError("altitude_km must be positive")
        if config.visibility.max_off_nadir_deg <= 0.0:
            raise ConfigValidationError("max_off_nadir_deg must be positive")
        if config.channel_quality.bandwidth_hz <= 0.0:
            raise ConfigValidationError("bandwidth_hz must be positive")
        if config.channel_quality.sinr_sigma_db < 0.0:
            raise ConfigValidationError("sinr_sigma_db must be non-negative")
        if config.channel_quality.throughput_aggregation not in {"mean", "sum"}:
            raise ConfigValidationError("throughput_aggregation must be 'mean' or 'sum'")
        self._config = config

    def run_trial(self, *, design: Any, seed: int) -> Dict[str, float]:
        if self._config is None:
            raise ConfigValidationError("adapter must be configured before use")

        cfg = self._config
        rng = random.Random(seed)
        sim = Dimensioning_3D(
            ground_lambda=cfg.users.ground_lambda,
            lat_min_deg=cfg.users.lat_min_deg,
            lat_max_deg=cfg.users.lat_max_deg,
            altitude_km=cfg.satellites.altitude_km,
            max_off_nadir_deg=cfg.visibility.max_off_nadir_deg,
            earth_radius_km=cfg.world.earth_radius_km,
            sinr_mu_db=cfg.channel_quality.sinr_mu_db,
            sinr_sigma_db=cfg.channel_quality.sinr_sigma_db,
            bandwidth_hz=cfg.channel_quality.bandwidth_hz,
            throughput_aggregation=cfg.channel_quality.throughput_aggregation,
            rng=rng,
        )
        metrics = sim.evaluate(lambda_sats=float(design))
        if "outage_rate" not in metrics:
            # Default outage definition uses coverage-only serving semantics.
            metrics["outage_rate"] = 1.0 - float(metrics["coverage"])
        return metrics

    def describe(self) -> Dict[str, str]:
        return {
            "name": "local_ppp_3d",
            "supports": "coverage, throughput",
        }
