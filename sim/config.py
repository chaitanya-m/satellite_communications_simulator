"""Simulator configuration types for adapter-boundary integrations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class WorldConfig:
    """Global geometry and constants."""

    earth_radius_km: float = 6371.0


@dataclass(frozen=True)
class UsersConfig:
    """User distribution parameters."""

    ground_lambda: float
    lat_min_deg: float
    lat_max_deg: float


@dataclass(frozen=True)
class SatellitesConfig:
    """Satellite orbital shell parameters."""

    altitude_km: float


@dataclass(frozen=True)
class VisibilityConfig:
    """Visibility gating parameters."""

    max_off_nadir_deg: float


@dataclass(frozen=True)
class ChannelQualityConfig:
    """Channel-quality model parameters and throughput mapping.

    The simulator uses a simple received-power model:
    - per visible link: received power is
        P(x,y) = P_t * G_xy * ||x-y||^{-gamma}
      where:
        - P_t (tx_power_w) is an effective per-satellite power scale (W)
        - G_xy ~ Exp(1) is a Rayleigh fading *power* gain (unitless, mean 1)
        - ||x-y|| is the 3D link distance (m)
        - gamma (pathloss_exponent) is the path-loss exponent
    - the serving satellite is the one with maximum received power
    - interference is the sum of received powers from other visible satellites
    - thermal noise power is N0 * W, with N0 (noise_density_w_per_hz) and
      bandwidth W (bandwidth_hz)

    Per-user throughput is computed from SINR using a Shannon-like formula:
        C = W * log2(1 + SINR)
    """

    bandwidth_hz: float
    # Aggregation over per-user capacities: mean (default) or sum.
    throughput_aggregation: str = "mean"
    # Per-user service threshold used to compute outage_rate (bps). If zero,
    # outage_rate reduces to 1 - coverage under the default visibility-only
    # serving semantics.
    min_user_throughput_bps: float = 0.0

    tx_power_w: float = 1.0
    pathloss_exponent: float = 2.0
    noise_density_w_per_hz: float = 0.0


@dataclass(frozen=True)
class SimulationConfig:
    """Root simulator config passed from the orchestrator to the adapter."""

    world: WorldConfig
    users: UsersConfig
    satellites: SatellitesConfig
    visibility: VisibilityConfig
    channel_quality: ChannelQualityConfig

    def to_dict(self) -> Dict[str, Any]:
        """Serialize config to a plain dictionary for JSON/YAML output."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SimulationConfig":
        """Construct config from a plain dictionary."""

        return cls(
            world=WorldConfig(**payload["world"]),
            users=UsersConfig(**payload["users"]),
            satellites=SatellitesConfig(**payload["satellites"]),
            visibility=VisibilityConfig(**payload["visibility"]),
            channel_quality=ChannelQualityConfig(**payload["channel_quality"]),
        )
