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
            rng=rng,
        )
        return sim.evaluate(lambda_sats=float(design))

    def describe(self) -> Dict[str, str]:
        return {
            "name": "local_ppp_3d",
            "supports": "coverage",
        }
