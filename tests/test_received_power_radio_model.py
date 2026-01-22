"""Unit tests for the simulator's received-power radio model.

This file tests the *radio/channel* part of the simulator in isolation, not the
optimization/certification stack. In particular, it tests that the simulator's
"received power -> SINR -> throughput" pipeline behaves sensibly and is fully
deterministic under a fixed seed.

------------------------------------------------------------------------------
What "received-power model" means here
------------------------------------------------------------------------------

For a given user and a set of visible satellites, the simulator models one link
to each visible satellite as follows:

1) Geometry (deterministic given sampled positions)
   - Compute 3D slant range distance ``d`` (meters) between the user and the
     satellite.

2) Propagation (random, but seed-controlled)
   - Sample a Rayleigh small-scale *power* gain ``G`` for that link.
   - In this implementation we use ``G ~ Exp(1)`` (unitless, mean 1).
     This is the standard "Rayleigh fading amplitude -> exponential power gain"
     simplification.

3) Received power (Watts)
   - Compute received power up to a proportionality constant:
       ``P_rx = P_t * G * d^{-gamma}``
     where:
       - ``P_t`` is a per-satellite effective transmit power scale (W),
         represented by ``tx_power_w`` in config.
       - ``gamma`` is the path-loss exponent, represented by
         ``pathloss_exponent``.

4) Serving link selection (best-link association)
   - The serving satellite is the one with the maximum received power ``P_rx``.

5) Interference and noise
   - All other *visible* satellites are treated as interferers:
       ``I = sum(P_rx_other)``
   - Thermal noise power is ``N = N0 * W`` where:
       - ``N0`` is noise spectral density (W/Hz), represented by
         ``noise_density_w_per_hz``.
       - ``W`` is bandwidth (Hz), represented by ``bandwidth_hz``.

6) SINR (dimensionless power ratio)
   - ``SINR = S / (I + N)`` where ``S`` is serving received power (W).

7) Throughput / capacity (bits per second)
   - Use a Shannon-like mapping:
       ``spectral_efficiency = log2(1 + SINR)``  [bits / s / Hz]
       ``capacity_bps = W * spectral_efficiency`` [bits / s]

------------------------------------------------------------------------------
What these tests assert
------------------------------------------------------------------------------

The simulator includes random sampling (PPP counts, point placements, Rayleigh
gains). That randomness must be controlled by the trial seed, so that:

- Determinism: for a fixed seed and design, the output metrics dictionary is
  exactly repeatable.
- Monotonicity sanity checks:
  - Increasing transmit power should increase throughput in a noise-limited
    regime (we choose a strictly positive noise floor for this test).
  - Increasing noise density should decrease throughput, all else equal.

These are not intended as physically complete validations of radio modeling;
they are "smoke tests" that the abstraction is wired correctly and responds to
key parameters in the expected direction.
"""

from __future__ import annotations

import math
import random

from sim.dimensioning_3d import Dimensioning_3D


def _make_received_power_sim(
    *,
    seed: int,
    tx_power_w: float,
    noise_density_w_per_hz: float,
    pathloss_exponent: float = 2.2,
    bandwidth_hz: float = 1e6,
    min_user_throughput_bps: float = 0.0,
    ground_lambda: float = 50.0,
    altitude_km: float = 550.0,
    max_off_nadir_deg: float = 60.0,
    lat_min_deg: float = -5.0,
    lat_max_deg: float = 5.0,
) -> Dimensioning_3D:
    """Create a deterministic simulator instance for received-power testing.

    We construct a fresh ``random.Random`` instance seeded with ``seed`` and
    pass it to the simulator. The simulator uses this RNG for *all*
    stochasticity in the trial:

    - Poisson sampling of user and satellite counts
    - Sampling user/satellite positions on the sphere within latitude bounds
    - Sampling Rayleigh fading gains for each visible user-satellite link

    Therefore, using the same ``seed`` makes the entire trial deterministic.

    Parameters
    ----------
    seed:
        Trial seed controlling all randomness.
    tx_power_w:
        Effective per-satellite power scale (W). Higher values should tend to
        increase SINR and throughput when noise is present.
    noise_density_w_per_hz:
        Thermal noise spectral density N0 (W/Hz). Higher values increase noise
        power N = N0 * W and should reduce SINR and throughput.

    Other parameters (advanced)
    ---------------------------
    The remaining parameters exist to let tests isolate specific effects:

    - ``pathloss_exponent`` controls the steepness of distance-based attenuation
      in ``d^{-gamma}``.
    - ``bandwidth_hz`` controls the Hz->bps scaling in
      ``capacity_bps = W * log2(1 + SINR)``.
    - ``min_user_throughput_bps`` affects the derived ``outage_rate`` only:
      a user is "served" iff best-link throughput meets this threshold.
    - geometry and visibility settings (PPP intensity, altitude, off-nadir, and
      latitude band) affect how many links are visible and how strong/weak
      typical link distances are.
    """
    rng = random.Random(seed)
    return Dimensioning_3D(
        ground_lambda=ground_lambda,
        lat_min_deg=lat_min_deg,
        lat_max_deg=lat_max_deg,
        altitude_km=altitude_km,
        max_off_nadir_deg=max_off_nadir_deg,
        earth_radius_km=6371.0,
        bandwidth_hz=bandwidth_hz,
        throughput_aggregation="mean",
        min_user_throughput_bps=min_user_throughput_bps,
        tx_power_w=tx_power_w,
        pathloss_exponent=pathloss_exponent,
        noise_density_w_per_hz=noise_density_w_per_hz,
        rng=rng,
    )


def test_received_power_model_deterministic_given_seed():
    """Same seed and design yield identical metrics (strong determinism).

    This test uses two independent simulator instances constructed with the same
    RNG seed and the same configuration, then evaluates the same satellite
    intensity (design). Because all randomness is driven from the supplied seed,
    we expect the returned metrics dict to match exactly (not just approximately).

    In addition to equality, we assert basic bounds for two key rates:
    - coverage is a fraction in [0, 1]
    - outage_rate is also a fraction in [0, 1]
    """
    sim_a = _make_received_power_sim(seed=123, tx_power_w=10.0, noise_density_w_per_hz=1e-20)
    sim_b = _make_received_power_sim(seed=123, tx_power_w=10.0, noise_density_w_per_hz=1e-20)

    metrics_a = sim_a.evaluate(lambda_sats=200.0)
    metrics_b = sim_b.evaluate(lambda_sats=200.0)

    assert metrics_a == metrics_b
    assert 0.0 <= metrics_a["coverage"] <= 1.0
    assert 0.0 <= metrics_a["outage_rate"] <= 1.0


def test_received_power_throughput_increases_with_tx_power_when_noise_present():
    """Throughput increases with transmit power in a noise-limited regime.

    To make this monotonicity check meaningful, we ensure a strictly positive
    thermal noise floor (``noise_density_w_per_hz > 0``). With noise present:

    - Increasing ``tx_power_w`` scales all received powers up proportionally.
    - Noise power N = N0 * W does *not* scale with tx power (not an interference).
    - Therefore, SINR should (weakly) increase, and the Shannon mapping
      ``W * log2(1 + SINR)`` should increase as well.

    We use identical seeds for both sims so that the geometry (PPP counts and
    placements) and fading draws are identical. The only difference is tx power,
    which isolates the effect we are testing.
    """
    # Using identical seeds ensures the same geometry and fading draws.
    low_power = _make_received_power_sim(seed=321, tx_power_w=1.0, noise_density_w_per_hz=1e-18)
    high_power = _make_received_power_sim(seed=321, tx_power_w=100.0, noise_density_w_per_hz=1e-18)

    metrics_low = low_power.evaluate(lambda_sats=200.0)
    metrics_high = high_power.evaluate(lambda_sats=200.0)

    assert metrics_high["throughput"] > metrics_low["throughput"]


def test_received_power_throughput_decreases_with_noise_density():
    """Throughput decreases as thermal noise density increases.

    With fixed transmit power and geometry/fading held constant by reusing the
    same seed:

    - Increasing noise density N0 increases noise power N = N0 * W.
    - Signal and interference powers are unchanged.
    - The denominator of SINR = S / (I + N) increases, so SINR decreases.
    - Therefore throughput ``W * log2(1 + SINR)`` decreases.
    """
    low_noise = _make_received_power_sim(seed=456, tx_power_w=10.0, noise_density_w_per_hz=1e-21)
    high_noise = _make_received_power_sim(seed=456, tx_power_w=10.0, noise_density_w_per_hz=1e-16)

    metrics_low = low_noise.evaluate(lambda_sats=200.0)
    metrics_high = high_noise.evaluate(lambda_sats=200.0)

    assert metrics_low["throughput"] > metrics_high["throughput"]


def test_received_power_throughput_approximately_invariant_to_tx_power_when_interference_dominates():
    """Throughput is approximately invariant to tx power in an interference-limited regime.

    Motivation
    ----------
    In many wireless models, if *interference dominates noise* (I >> N), then
    scaling all transmit powers by a common factor should not materially change
    SINR, because the desired signal and the aggregate interference scale
    together. This is the intuition behind calling some regimes
    "interference-limited".

    Intuition (in symbols)
    ----------------------
    Let a user's SINR be:
        ``SINR = S / (I + N)``
    where:
    - S is the serving received power (W)
    - I is aggregate interference power (W)
    - N is thermal noise power (W), N = N0 * W, independent of tx power

    Now scale transmit power by a factor k > 0. In our received-power model,
    every received power term is proportional to tx power, so:
        S' = k S
        I' = k I
        N' = N
    Hence:
        SINR' = S' / (I' + N) = (k S) / (k I + N)

    If k I >> N (noise negligible compared to interference), then:
        SINR' ≈ (k S) / (k I) = S / I
    so SINR is approximately invariant to k, and so is throughput
    ``W * log2(1 + SINR)``.

    What we test
    ------------
    We choose parameters intended to produce many visible satellites per user:
    - a large satellite intensity (design)
    - a wide off-nadir angle so "visible" is generous
    - a tiny but non-zero noise floor to avoid any divide-by-zero corner case

    We then compare mean throughput for two different tx powers under the same
    seed. Because the seed is identical, geometry and fading draws are
    identical; only tx power changes.

    Since this is an *approximate* invariance claim (finite I, small but nonzero
    N), we assert closeness within a tolerance rather than exact equality.
    """
    seed = 777
    design = 5000.0

    # Keep bandwidth small so N = N0 * W stays tiny; keep N0 nonzero to ensure
    # SINR stays finite even if a user sees only one satellite.
    bandwidth_hz = 1.0
    noise_density_w_per_hz = 1e-20

    low_power = _make_received_power_sim(
        seed=seed,
        tx_power_w=1.0,
        noise_density_w_per_hz=noise_density_w_per_hz,
        bandwidth_hz=bandwidth_hz,
        max_off_nadir_deg=90.0,
    )
    high_power = _make_received_power_sim(
        seed=seed,
        tx_power_w=100.0,
        noise_density_w_per_hz=noise_density_w_per_hz,
        bandwidth_hz=bandwidth_hz,
        max_off_nadir_deg=90.0,
    )

    metrics_low = low_power.evaluate(lambda_sats=design)
    metrics_high = high_power.evaluate(lambda_sats=design)

    assert metrics_low["throughput"] > 0.0
    rel_diff = abs(metrics_high["throughput"] - metrics_low["throughput"]) / metrics_low["throughput"]
    assert rel_diff < 0.02


def test_outage_rate_increases_when_min_user_throughput_threshold_is_raised():
    """Raising min_user_throughput_bps increases outage_rate (served fraction decreases).

    Motivation
    ----------
    The simulator reports both:
    - ``coverage``: a *geometric* notion (is there at least one visible satellite?)
    - ``outage_rate``: a *service* notion (is a user both visible and above a throughput threshold?)

    Intuition
    ---------
    For a fixed trial (fixed seed, fixed design), each user has a computed
    best-link throughput value (bps). Defining service requires a threshold:

        served(x) = 1{ best_throughput_bps(x) >= min_user_throughput_bps }

    If we increase ``min_user_throughput_bps``, some users that previously met
    the threshold may now fail it, but no failing user can become served. Thus
    the served fraction is non-increasing, and ``outage_rate = 1 - served`` is
    non-decreasing.

    What we test
    ------------
    We run two simulations with identical randomness and geometry, differing
    only in ``min_user_throughput_bps``:
    - coverage should be identical (threshold does not affect visibility)
    - throughput should be identical (threshold does not change SINR sampling)
    - outage_rate should be higher (or equal) for the larger threshold
    """
    seed = 2024
    design = 200.0

    sim_lo = _make_received_power_sim(
        seed=seed,
        tx_power_w=10.0,
        noise_density_w_per_hz=1e-18,
        min_user_throughput_bps=0.0,
    )
    sim_hi = _make_received_power_sim(
        seed=seed,
        tx_power_w=10.0,
        noise_density_w_per_hz=1e-18,
        min_user_throughput_bps=1e6,
    )

    metrics_lo = sim_lo.evaluate(lambda_sats=design)
    metrics_hi = sim_hi.evaluate(lambda_sats=design)

    assert metrics_lo["coverage"] == metrics_hi["coverage"]
    assert metrics_lo["throughput"] == metrics_hi["throughput"]
    assert metrics_hi["outage_rate"] >= metrics_lo["outage_rate"]


def test_throughput_decreases_with_pathloss_exponent_in_noise_limited_regime():
    """Higher pathloss_exponent reduces throughput when thermal noise dominates.

    Motivation
    ----------
    In the received-power model, link power includes distance-based attenuation
    ``d^{-gamma}``. Increasing ``gamma`` makes the received power drop faster
    with distance, reducing SINR and therefore throughput.

    Why choose a noise-limited regime?
    ---------------------------------
    If interference dominated, both the desired signal and the interference
    would be attenuated, and the net effect on SINR could be ambiguous. To make
    the direction of change unambiguous, we choose parameters where noise is
    the main impairment, so SINR behaves roughly like S/N.

    What we test
    ------------
    For a fixed seed and design, we compare two simulations that differ only in
    ``pathloss_exponent``. Because coverage depends only on visibility geometry,
    coverage should be identical; the throughput should be strictly smaller for
    the larger path-loss exponent.
    """
    seed = 4242
    design = 50.0

    # Strong noise and small bandwidth -> noise dominates; keep a modest design
    # to avoid excessive interference.
    bandwidth_hz = 1.0
    noise_density_w_per_hz = 1e-10

    sim_gamma_low = _make_received_power_sim(
        seed=seed,
        tx_power_w=10.0,
        noise_density_w_per_hz=noise_density_w_per_hz,
        bandwidth_hz=bandwidth_hz,
        pathloss_exponent=2.0,
    )
    sim_gamma_high = _make_received_power_sim(
        seed=seed,
        tx_power_w=10.0,
        noise_density_w_per_hz=noise_density_w_per_hz,
        bandwidth_hz=bandwidth_hz,
        pathloss_exponent=3.0,
    )

    metrics_low = sim_gamma_low.evaluate(lambda_sats=design)
    metrics_high = sim_gamma_high.evaluate(lambda_sats=design)

    assert metrics_low["coverage"] == metrics_high["coverage"]
    assert metrics_low["throughput"] > metrics_high["throughput"]


def test_received_power_outputs_are_finite_with_positive_noise():
    """Metrics are finite (no NaN/inf) when noise_density_w_per_hz is positive.

    Motivation
    ----------
    SINR is computed as S / (I + N). If both I and N were exactly zero (for
    example, ``noise_density_w_per_hz = 0`` and only one visible satellite),
    then the denominator would be zero and SINR would be treated as infinity.

    For most downstream experiments, we want finite throughput values, so we
    typically run with a positive noise floor.

    What we test
    ------------
    We run a representative trial with a positive noise floor and then assert:
    - coverage and outage_rate remain valid fractions in [0, 1]
    - throughput is non-negative and finite
    """
    sim = _make_received_power_sim(
        seed=9001,
        tx_power_w=10.0,
        noise_density_w_per_hz=1e-18,
        bandwidth_hz=1e6,
    )
    metrics = sim.evaluate(lambda_sats=200.0)

    assert 0.0 <= metrics["coverage"] <= 1.0
    assert 0.0 <= metrics["outage_rate"] <= 1.0
    assert metrics["throughput"] >= 0.0
    assert math.isfinite(metrics["throughput"])
