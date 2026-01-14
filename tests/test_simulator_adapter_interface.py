"""Adapter boundary tests for the local PPP simulator."""

from __future__ import annotations

from sim.adapters.local_ppp_sim_adapter import LocalPPPSimulatorAdapter
from sim.config import (
    ChannelQualityConfig,
    SatellitesConfig,
    SimulationConfig,
    UsersConfig,
    VisibilityConfig,
    WorldConfig,
)


def test_local_ppp_adapter_deterministic_trial():
    """Ensure adapter determinism given identical design and seed."""
    config = SimulationConfig(
        world=WorldConfig(earth_radius_km=6371.0),
        users=UsersConfig(ground_lambda=50.0, lat_min_deg=-5.0, lat_max_deg=5.0),
        satellites=SatellitesConfig(altitude_km=550.0),
        visibility=VisibilityConfig(max_off_nadir_deg=60.0),
        channel_quality=ChannelQualityConfig(
            sinr_mu_db=0.0,
            sinr_sigma_db=1.0,
            bandwidth_hz=1.0,
        ),
    )

    adapter = LocalPPPSimulatorAdapter()
    adapter.configure(config)

    # Two trials with identical inputs should yield identical metrics.
    metrics_a = adapter.run_trial(design=10.0, seed=123)
    metrics_b = adapter.run_trial(design=10.0, seed=123)

    assert metrics_a == metrics_b
    assert "coverage" in metrics_a
    assert "throughput" in metrics_a
    assert "outage_rate" in metrics_a
    # Outage is defined as one minus coverage under the default semantics.
    assert metrics_a["outage_rate"] == 1.0 - metrics_a["coverage"]
