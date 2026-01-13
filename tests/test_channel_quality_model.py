# tests/test_channel_quality_model.py
"""Tests for lognormal SINR channel-quality modeling."""

from __future__ import annotations

import math
import random

from sim.adapters.local_ppp_sim_adapter import LocalPPPSimulatorAdapter
from sim.config import (
    ChannelQualityConfig,
    SatellitesConfig,
    SimulationConfig,
    UsersConfig,
    VisibilityConfig,
    WorldConfig,
)
from sim.stochastic.poisson import sample_poisson


def test_channel_quality_sigma_zero_matches_coverage_scaling():
    """With sigma=0, throughput should equal coverage times constant capacity."""
    seed = 42
    ground_lambda = 50.0

    expected_n_ground = sample_poisson(ground_lambda, random.Random(seed))
    assert expected_n_ground > 0

    config = SimulationConfig(
        world=WorldConfig(earth_radius_km=6371.0),
        users=UsersConfig(ground_lambda=ground_lambda, lat_min_deg=-5.0, lat_max_deg=5.0),
        satellites=SatellitesConfig(altitude_km=550.0),
        visibility=VisibilityConfig(max_off_nadir_deg=60.0),
        channel_quality=ChannelQualityConfig(
            sinr_mu_db=0.0,
            sinr_sigma_db=0.0,
            bandwidth_hz=2.0,
        ),
    )

    adapter = LocalPPPSimulatorAdapter()
    adapter.configure(config)

    metrics = adapter.run_trial(design=20.0, seed=seed)

    assert metrics["n_ground"] == float(expected_n_ground)

    sinr_linear = 10.0 ** (config.channel_quality.sinr_mu_db / 10.0)
    capacity = config.channel_quality.bandwidth_hz * math.log1p(sinr_linear)
    expected_throughput = metrics["coverage"] * capacity
    assert math.isclose(metrics["throughput"], expected_throughput, rel_tol=1e-6)


def test_channel_quality_mu_shift_increases_throughput():
    """Higher mean SINR should increase throughput for the same geometry."""
    seed = 11
    ground_lambda = 80.0

    base_kwargs = dict(
        world=WorldConfig(earth_radius_km=6371.0),
        users=UsersConfig(ground_lambda=ground_lambda, lat_min_deg=-10.0, lat_max_deg=10.0),
        satellites=SatellitesConfig(altitude_km=550.0),
        visibility=VisibilityConfig(max_off_nadir_deg=80.0),
    )

    config_low = SimulationConfig(
        **base_kwargs,
        channel_quality=ChannelQualityConfig(
            sinr_mu_db=0.0,
            sinr_sigma_db=2.0,
            bandwidth_hz=1.0,
        ),
    )
    config_high = SimulationConfig(
        **base_kwargs,
        channel_quality=ChannelQualityConfig(
            sinr_mu_db=10.0,
            sinr_sigma_db=2.0,
            bandwidth_hz=1.0,
        ),
    )

    adapter_low = LocalPPPSimulatorAdapter()
    adapter_low.configure(config_low)
    metrics_low = adapter_low.run_trial(design=30.0, seed=seed)

    adapter_high = LocalPPPSimulatorAdapter()
    adapter_high.configure(config_high)
    metrics_high = adapter_high.run_trial(design=30.0, seed=seed)

    assert metrics_low["coverage"] == metrics_high["coverage"]
    if metrics_low["coverage"] == 0.0:
        assert metrics_high["throughput"] == 0.0
    else:
        assert metrics_high["throughput"] > metrics_low["throughput"]
