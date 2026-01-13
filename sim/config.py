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
class SimulationConfig:
    """Root simulator config passed from the orchestrator to the adapter."""

    world: WorldConfig
    users: UsersConfig
    satellites: SatellitesConfig
    visibility: VisibilityConfig

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
        )
