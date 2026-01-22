# tests/test_channel_quality_model.py
"""Tests for the received-power channel-quality model.

These tests focus on the semantics that matter for experiments/certificates:
- how `min_user_throughput_bps` affects the derived `outage_rate`
- ensuring `outage_rate` is consistent with `coverage` when the threshold is 0
"""

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


def test_outage_equals_one_minus_coverage_when_min_throughput_is_zero():
    """With min_user_throughput_bps=0, served==covered so outage=1-coverage."""
    config = SimulationConfig(
        world=WorldConfig(earth_radius_km=6371.0),
        users=UsersConfig(ground_lambda=50.0, lat_min_deg=-5.0, lat_max_deg=5.0),
        satellites=SatellitesConfig(altitude_km=550.0),
        visibility=VisibilityConfig(max_off_nadir_deg=60.0),
        channel_quality=ChannelQualityConfig(
            bandwidth_hz=1e6,
            min_user_throughput_bps=0.0,
            tx_power_w=10.0,
            noise_density_w_per_hz=1e-18,
        ),
    )

    adapter = LocalPPPSimulatorAdapter()
    adapter.configure(config)

    metrics = adapter.run_trial(design=200.0, seed=123)
    assert metrics["outage_rate"] == 1.0 - metrics["coverage"]


def test_min_throughput_threshold_increases_outage_without_changing_throughput():
    """Raising min_user_throughput_bps should (weakly) increase outage_rate."""
    base = dict(
        world=WorldConfig(earth_radius_km=6371.0),
        users=UsersConfig(ground_lambda=50.0, lat_min_deg=-5.0, lat_max_deg=5.0),
        satellites=SatellitesConfig(altitude_km=550.0),
        visibility=VisibilityConfig(max_off_nadir_deg=60.0),
    )

    config_lo = SimulationConfig(
        **base,
        channel_quality=ChannelQualityConfig(
            bandwidth_hz=1e6,
            min_user_throughput_bps=0.0,
            tx_power_w=10.0,
            noise_density_w_per_hz=1e-18,
        ),
    )
    config_hi = SimulationConfig(
        **base,
        channel_quality=ChannelQualityConfig(
            bandwidth_hz=1e6,
            min_user_throughput_bps=1e5,
            tx_power_w=10.0,
            noise_density_w_per_hz=1e-18,
        ),
    )

    seed = 999
    design = 200.0

    adapter_lo = LocalPPPSimulatorAdapter()
    adapter_lo.configure(config_lo)
    metrics_lo = adapter_lo.run_trial(design=design, seed=seed)

    adapter_hi = LocalPPPSimulatorAdapter()
    adapter_hi.configure(config_hi)
    metrics_hi = adapter_hi.run_trial(design=design, seed=seed)

    # Thresholding changes the "served" indicator but not the sampled link quality.
    assert metrics_lo["coverage"] == metrics_hi["coverage"]
    assert metrics_lo["throughput"] == metrics_hi["throughput"]
    assert metrics_hi["outage_rate"] >= metrics_lo["outage_rate"]
