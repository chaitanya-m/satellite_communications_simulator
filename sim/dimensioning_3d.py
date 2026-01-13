# sim/dimensioning_3d.py
"""3D spherical PPP coverage simulator for dimensioning.

This module intentionally keeps the model minimal and closed-form:
- users are a Poisson point process (PPP) on a spherical Earth surface
- satellites are a PPP on a spherical orbital shell
- coverage is evaluated per user with a simple off-nadir visibility gate
- channel quality uses a lognormal SINR model to produce throughput
"""

from __future__ import annotations

import math
import random

from sim.stochastic.poisson import sample_poisson


class Dimensioning_3D:
    """
    3D spherical PPP coverage simulator.

    Ground users:
        PPP with mean `ground_lambda` on a spherical Earth surface,
        restricted to a latitude band [lat_min_deg, lat_max_deg].

    Satellites:
        PPP with mean `lambda_sats` on a spherical orbital shell at
        altitude_km. Sampling is gated by a coarse visibility proxy:
        only satellites within an expanded latitude band (lat +/- max off-nadir)
        are considered.

    Coverage:
        A ground user is covered if at least one satellite is within the
        max off-nadir angle (per-user visibility).

    Throughput:
        Per-user capacity uses the best visible link (highest sampled SINR),
        aggregated across users by mean (default) or sum.

    Outputs:
        - coverage: fraction of users with at least one visible satellite
        - throughput: aggregated per-user capacity via a lognormal SINR model
        - n_ground: sampled user count for the trial
        - n_sats: sampled satellite count for the trial
    """

    def __init__(
        self,
        *,
        ground_lambda: float,
        lat_min_deg: float,
        lat_max_deg: float,
        altitude_km: float,
        max_off_nadir_deg: float,
        earth_radius_km: float = 6371.0,
        sinr_mu_db: float = 0.0,
        sinr_sigma_db: float = 1.0,
        bandwidth_hz: float = 1.0,
        throughput_aggregation: str = "mean",
        rng: random.Random | None = None,
    ):
        self.ground_lambda = float(ground_lambda)
        self.lat_min_deg = float(lat_min_deg)
        self.lat_max_deg = float(lat_max_deg)
        self.altitude_km = float(altitude_km)
        self.max_off_nadir_deg = float(max_off_nadir_deg)
        self.earth_radius_km = float(earth_radius_km)
        self.sinr_mu_db = float(sinr_mu_db)
        self.sinr_sigma_db = float(sinr_sigma_db)
        self.bandwidth_hz = float(bandwidth_hz)
        self.throughput_aggregation = throughput_aggregation
        self.rng = rng or random.Random()

        # Last realised counts (for inspection / testing only)
        self.last_n_ground: int | None = None
        self.last_n_sats: int | None = None

        if self.throughput_aggregation not in {"mean", "sum"}:
            raise ValueError("throughput_aggregation must be 'mean' or 'sum'")

        self._cos_off_nadir_max = math.cos(math.radians(self.max_off_nadir_deg))
        self._sat_lat_min, self._sat_lat_max = self._satellite_lat_bounds()
        # Horizon gating constant: cos(phi_horizon) = R / r. Any satellite with
        # cos(phi) < cos(phi_horizon) is below the horizon and cannot be visible,
        # regardless of off-nadir angle.
        r = self.earth_radius_km + self.altitude_km
        self._cos_horizon = self.earth_radius_km / r

    def _satellite_lat_bounds(self) -> tuple[float, float]:
        """Return a coarse latitude band for satellite sampling.

        The band is expanded by the off-nadir angle so satellites that cannot
        possibly be visible from the user band are not sampled. This is a
        sampling optimization, not the per-user visibility rule itself.
        """
        # Coarse gating using the visibility angle as a latitude expansion.
        delta = self.max_off_nadir_deg
        lat_min = max(-90.0, self.lat_min_deg - delta)
        lat_max = min(90.0, self.lat_max_deg + delta)
        return (lat_min, lat_max)

    @staticmethod
    def _sample_lat_lon(
        rng: random.Random,
        lat_min_deg: float,
        lat_max_deg: float,
    ) -> tuple[float, float]:
        """Sample a uniform point on a spherical surface within a latitude band.

        Uniform area sampling on a sphere uses a uniform draw in sin(latitude).
        Longitude is uniform on [-pi, pi].
        """
        # Uniform by area on a sphere: uniform in sin(latitude).
        sin_min = math.sin(math.radians(lat_min_deg))
        sin_max = math.sin(math.radians(lat_max_deg))
        s = rng.uniform(sin_min, sin_max)
        lat_rad = math.asin(s)
        lon_rad = rng.uniform(-math.pi, math.pi)
        return (math.degrees(lat_rad), math.degrees(lon_rad))

    @staticmethod
    def _cos_central_angle(
        lat1_deg: float,
        lon1_deg: float,
        lat2_deg: float,
        lon2_deg: float,
    ) -> float:
        """Return cos(phi), where phi is the Earth-centered angle between points.

        This is stable and avoids an extra acos unless needed.
        """
        lat1 = math.radians(lat1_deg)
        lat2 = math.radians(lat2_deg)
        dlon = math.radians(lon2_deg - lon1_deg)
        return (
            math.sin(lat1) * math.sin(lat2)
            + math.cos(lat1) * math.cos(lat2) * math.cos(dlon)
        )

    def _cos_off_nadir(self, cos_phi: float) -> float:
        """Compute cos(psi), the off-nadir angle at the satellite.

        Geometry:
        - R: Earth radius
        - r: orbit radius
        - phi: central angle between ground point and sub-satellite point
        - psi: off-nadir angle from satellite to ground point
        """
        R = self.earth_radius_km
        r = self.earth_radius_km + self.altitude_km
        denom = math.sqrt(r * r + R * R - 2.0 * r * R * cos_phi)
        if denom == 0.0:
            return 1.0
        cos_psi = (r - R * cos_phi) / denom
        return max(-1.0, min(1.0, cos_psi))

    def _sample_sinr_linear(self) -> float:
        """Sample per-link SINR in linear scale from a lognormal model."""
        sinr_db = self.rng.gauss(self.sinr_mu_db, self.sinr_sigma_db)
        return 10.0 ** (sinr_db / 10.0)

    def evaluate(self, lambda_sats: float) -> dict[str, float]:
        """Run a single Monte Carlo trial at a given satellite intensity."""
        n_ground = sample_poisson(self.ground_lambda, self.rng)
        n_sats = sample_poisson(float(lambda_sats), self.rng)

        self.last_n_ground = n_ground
        self.last_n_sats = n_sats

        if n_ground == 0:
            return {
                "coverage": 1.0,  # vacuously covered
                "throughput": 0.0,
                "n_ground": 0.0,
                "n_sats": float(n_sats),
            }

        if n_sats == 0:
            return {
                "coverage": 0.0,
                "throughput": 0.0,
                "n_ground": float(n_ground),
                "n_sats": 0.0,
            }

        # Sample PPP points for users and satellites.
        ground_points = [
            self._sample_lat_lon(self.rng, self.lat_min_deg, self.lat_max_deg)
            for _ in range(n_ground)
        ]
        sat_points = [
            self._sample_lat_lon(self.rng, self._sat_lat_min, self._sat_lat_max)
            for _ in range(n_sats)
        ]

        # Per-user visibility gating: require at least one satellite within off-nadir limit.
        covered = 0
        throughput_sum = 0.0
        for glat, glon in ground_points:
            visible = False
            best_capacity = 0.0
            for slat, slon in sat_points:
                cos_phi = self._cos_central_angle(glat, glon, slat, slon)
                cos_phi = max(-1.0, min(1.0, cos_phi))
                # Line-of-sight / horizon gate: if the satellite is beyond the
                # geometric horizon, skip it before applying off-nadir gating.
                if cos_phi < self._cos_horizon:
                    continue
                cos_psi = self._cos_off_nadir(cos_phi)
                if cos_psi >= self._cos_off_nadir_max:
                    visible = True
                    sinr_linear = self._sample_sinr_linear()
                    capacity = self.bandwidth_hz * math.log1p(sinr_linear)
                    if capacity > best_capacity:
                        best_capacity = capacity
            if visible:
                covered += 1
            throughput_sum += best_capacity

        coverage = covered / n_ground
        if self.throughput_aggregation == "sum":
            throughput = throughput_sum
        else:
            throughput = throughput_sum / n_ground
        return {
            "coverage": coverage,
            "throughput": throughput,
            "n_ground": float(n_ground),
            "n_sats": float(n_sats),
        }
