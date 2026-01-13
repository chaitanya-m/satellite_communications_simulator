"""Adapter boundary tests for the local PPP simulator."""

from __future__ import annotations

from sim.adapters.local_ppp_sim_adapter import LocalPPPSimulatorAdapter
from sim.config import SimulationConfig, SatellitesConfig, UsersConfig, VisibilityConfig, WorldConfig


def test_local_ppp_adapter_deterministic_trial():
    config = SimulationConfig(
        world=WorldConfig(earth_radius_km=6371.0),
        users=UsersConfig(ground_lambda=50.0, lat_min_deg=-5.0, lat_max_deg=5.0),
        satellites=SatellitesConfig(altitude_km=550.0),
        visibility=VisibilityConfig(max_off_nadir_deg=60.0),
    )

    adapter = LocalPPPSimulatorAdapter()
    adapter.configure(config)

    metrics_a = adapter.run_trial(design=10.0, seed=123)
    metrics_b = adapter.run_trial(design=10.0, seed=123)

    assert metrics_a == metrics_b
    assert "coverage" in metrics_a
