# sim/dimensioning_3d.py
"""3D spherical PPP coverage simulator for dimensioning.

This module intentionally keeps the model minimal and closed-form:
- users are a Poisson point process (PPP) on a spherical Earth surface
- satellites are a PPP on a spherical orbital shell
- coverage is evaluated per user with a simple off-nadir visibility gate
- channel quality uses a received-power model with Rayleigh fading, interference,
  and thermal noise
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
        Per-user capacity is computed on the best (maximum received-power) visible
        link, with interference from other visible satellites and thermal noise.
        Capacities are aggregated across users by mean (default) or sum.

    Outage:
        A user is considered served if (i) at least one satellite is visible and
        (ii) that user's best-link throughput is >= min_user_throughput_bps.
        The outage_rate is 1 - served_fraction. If min_user_throughput_bps=0,
        this reduces to 1 - coverage.

    Outputs:
        - coverage: fraction of users with at least one visible satellite
        - throughput: aggregated per-user capacity from the received-power model
        - outage_rate: 1 - fraction of users that are served
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
        bandwidth_hz: float = 1.0,
        throughput_aggregation: str = "mean",
        min_user_throughput_bps: float = 0.0,
        tx_power_w: float = 1.0,
        pathloss_exponent: float = 2.0,
        noise_density_w_per_hz: float = 0.0,
        rng: random.Random | None = None,
    ):
        self.ground_lambda = float(ground_lambda)
        self.lat_min_deg = float(lat_min_deg)
        self.lat_max_deg = float(lat_max_deg)
        self.altitude_km = float(altitude_km)
        self.max_off_nadir_deg = float(max_off_nadir_deg)
        self.earth_radius_km = float(earth_radius_km)
        self.bandwidth_hz = float(bandwidth_hz)
        self.throughput_aggregation = throughput_aggregation
        self.min_user_throughput_bps = float(min_user_throughput_bps)
        self.tx_power_w = float(tx_power_w)
        self.pathloss_exponent = float(pathloss_exponent)
        self.noise_density_w_per_hz = float(noise_density_w_per_hz)
        self.rng = rng or random.Random()

        # Last realised counts (for inspection / testing only)
        self.last_n_ground: int | None = None
        self.last_n_sats: int | None = None

        if self.throughput_aggregation not in {"mean", "sum"}:
            raise ValueError("throughput_aggregation must be 'mean' or 'sum'")
        if self.min_user_throughput_bps < 0.0:
            raise ValueError("min_user_throughput_bps must be non-negative")
        if self.tx_power_w <= 0.0:
            raise ValueError("tx_power_w must be positive")
        if self.pathloss_exponent <= 0.0:
            raise ValueError("pathloss_exponent must be positive")
        if self.noise_density_w_per_hz < 0.0:
            raise ValueError("noise_density_w_per_hz must be non-negative")

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

    def _slant_range_km(self, cos_phi: float) -> float:
        """Compute slant range (km) from ground point to satellite."""
        R = self.earth_radius_km
        r = self.earth_radius_km + self.altitude_km
        # Law of cosines in 3D using the Earth-centered angle between radial directions.
        return math.sqrt(r * r + R * R - 2.0 * r * R * cos_phi)

    def _sample_received_power_w(self, slant_range_km: float) -> float:
        """Sample received power for one link under a Rayleigh fading model.

        Model:
            P(x,y) = P_t * G_xy * ||x-y||^{-gamma}

        - P_t is an effective per-satellite transmit power scale (W).
        - G_xy ~ Exp(1) is the Rayleigh fading power gain (mean 1).
        - ||x-y|| is the 3D distance between user and satellite.

        Note: This is intentionally simplified (no antenna patterns, no
        atmospheric losses, no frequency-dependent constants). It is meant as a
        tractable stochastic-geometry-style model rather than a full link budget.
        """
        d_m = max(1e-9, slant_range_km * 1000.0)
        fading_gain = self.rng.expovariate(1.0)  # Exp(1): mean 1
        return self.tx_power_w * fading_gain * (d_m ** (-self.pathloss_exponent))

    def _capacity_for_user(self, visible_sats: list[tuple[float, float]]) -> float:
        """Compute best-link capacity for one user given a list of visible satellites.

        This method returns a **rate in bits per second (bps)** for a single user.

        Model (one user, one trial):
        - For each visible satellite link, sample a received power value `P_xy` (W).
        - Choose the serving satellite as the link with maximum received power.
        - Treat all other visible satellites as interferers.
        - Compute linear SINR (dimensionless power ratio):
            SINR = S / (I + N)
          where:
            - S is the serving received power (W)
            - I is the sum of interfering received powers (W)
            - N is thermal noise power (W) computed as N = N0 * W
              with noise spectral density N0 (W/Hz) and bandwidth W (Hz)
        - Map SINR to throughput using a Shannon-like capacity formula:
            spectral_efficiency = log2(1 + SINR)    [bits / second / Hz]
            capacity_bps = bandwidth_hz * spectral_efficiency

        Notes:
        - This is a deliberately minimal abstraction: it is not a full link budget
          (no antenna patterns, coding gaps, frequency terms, etc.).
        - There is no scheduling or sharing here: each user is evaluated on its
          best link independently, and interference is modelled as a sum over all
          other visible satellites for that user.
        """
        if not visible_sats:
            return 0.0

        received_powers: list[float] = []
        for cos_phi, _cos_psi in visible_sats:
            slant_range_km = self._slant_range_km(cos_phi)
            received_powers.append(self._sample_received_power_w(slant_range_km))

        signal_w = max(received_powers)
        interference_w = sum(received_powers) - signal_w
        # Thermal noise power (W) = noise spectral density (W/Hz) * bandwidth (Hz).
        noise_w = self.noise_density_w_per_hz * self.bandwidth_hz
        denom_w = interference_w + noise_w
        if denom_w <= 0.0:
            # If both interference and noise are exactly zero, SINR is infinite.
            # This can only happen if noise_density_w_per_hz=0 and there is only
            # one visible satellite (no interferers).
            sinr_linear = float("inf")  # dimensionless
        else:
            sinr_linear = signal_w / denom_w  # dimensionless

        # Spectral efficiency in bits/s/Hz, then multiply by Hz -> bits/s (bps).
        spectral_efficiency = math.log2(1.0 + sinr_linear)
        return self.bandwidth_hz * spectral_efficiency

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
                "outage_rate": 0.0,
                "n_ground": 0.0,
                "n_sats": float(n_sats),
            }

        if n_sats == 0:
            return {
                "coverage": 0.0,
                "throughput": 0.0,
                "outage_rate": 1.0,
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
        served = 0
        throughput_sum = 0.0
        for glat, glon in ground_points:
            visible_links: list[tuple[float, float]] = []
            for slat, slon in sat_points:
                cos_phi = self._cos_central_angle(glat, glon, slat, slon)
                cos_phi = max(-1.0, min(1.0, cos_phi))
                # Line-of-sight / horizon gate: if the satellite is beyond the
                # geometric horizon, skip it before applying off-nadir gating.
                if cos_phi < self._cos_horizon:
                    continue
                cos_psi = self._cos_off_nadir(cos_phi)
                if cos_psi >= self._cos_off_nadir_max:
                    visible_links.append((cos_phi, cos_psi))

            if visible_links:
                covered += 1
                best_capacity = self._capacity_for_user(visible_links)
                if best_capacity >= self.min_user_throughput_bps:
                    served += 1
                throughput_sum += best_capacity
            else:
                throughput_sum += 0.0

        coverage = covered / n_ground
        outage_rate = 1.0 - (served / n_ground)
        if self.throughput_aggregation == "sum":
            throughput = throughput_sum
        else:
            throughput = throughput_sum / n_ground
        return {
            "coverage": coverage,
            "throughput": throughput,
            "outage_rate": outage_rate,
            "n_ground": float(n_ground),
            "n_sats": float(n_sats),
        }
