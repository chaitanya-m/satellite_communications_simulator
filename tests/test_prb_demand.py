"""Unit tests for PRB-demand mapping from log-shadowing inputs.

Scope:
- These tests validate PRB-demand mapping and aggregation behavior only.
- They do not test shadowing-field generation or end-to-end outage loops.

Convention used by these tests:
- ``G = ln(S)`` where ``S`` is the multiplicative shadowing factor.
- ``S < 1`` means attenuation (worse channel), so ``G`` is more negative.
- Larger ``G`` therefore means less attenuation and should not require more PRBs.
- ``snr0_linear`` is the reference SNR when ``G = 0`` (equivalently ``S = 1``,
  meaning no additional shadowing gain/loss). For any user,
  ``SNR = snr0_linear * exp(G)``.
- if explicit pathloss is enabled, a normalized slant-range term multiplies the
  SNR:
  ``SNR = snr0_linear * (d/h)^(-gamma) * exp(G)``,
  where ``h`` is altitude and ``d`` is slant range from the beam center.
- Choosing ``snr0_linear = 1.0`` means the reference SNR is ``1`` in linear scale
  (that is ``0 dB``). This is a neutral baseline used to keep tests easy to interpret.
- Choosing ``rb_bandwidth_hz = 180_000`` uses a common PRB-like bandwidth scale,
  so demand values are in a realistic order of magnitude.
- Choosing ``eta_min = 0.1`` provides a conservative spectral-efficiency floor:
  at very low SNR the model does not let demand blow up to infinity, and instead
  caps per-user demand at a finite maximum.
"""

from __future__ import annotations

import pytest

from sim.prb_demand import PRBDemandParams, prb_demand_from_log_shadowing, total_prb_demand


def test_prb_demand_is_monotone_with_log_shadowing() -> None:
    """Check monotonic behavior under the paper's log-shadowing convention.

    As ``G`` increases, channel quality improves (because ``S = exp(G)`` increases).
    Improved channel quality should not increase required PRBs for a fixed rate.

    dB example: changing shadowing from -20 dB to -10 dB means less loss.
    In linear scale, ``S`` goes from 0.01 to 0.1, so SNR increases by 10x.
    With higher SNR, each RB carries more bits, so PRB demand should not rise.

    Checks performed:
    - output PRB demand is monotone non-increasing as ``G`` increases,
    - no shape/content errors on a valid 1D input vector.
    """
    params = PRBDemandParams(
        required_rate_bps=1_000_000.0,  # Per-user target data rate (bits/s).
        rb_bandwidth_hz=180_000.0,  # PRB-like bandwidth scale (180 kHz).
        snr0_linear=1.0,  # Reference SNR at G=0, i.e., 1.0 linear = 0 dB.
        eta_min=0.1,  # Conservative floor to keep max PRB demand finite.
    )
    # ln(S) values from strong attenuation (more negative) to weaker attenuation.
    log_shadowing = [-3.0, -1.0, 0.0, 1.0, 2.0]

    prb = prb_demand_from_log_shadowing(log_shadowing, params=params)

    assert all(prb[i + 1] <= prb[i] for i in range(len(prb) - 1))


def test_prb_demand_respects_min_and_max_caps() -> None:
    """Check that the implementation enforces PRB-demand hard bounds.

    The output must be at least 1 PRB and at most ``max_prb_per_user`` implied
    by the ``eta_min`` floor.

    Checks performed:
    - severe attenuation path reaches the configured max cap,
    - very favorable channel path reaches the minimum demand of 1 PRB.
    """
    params = PRBDemandParams(
        required_rate_bps=1_000_000.0,  # Per-user target data rate (bits/s).
        rb_bandwidth_hz=180_000.0,  # PRB-like bandwidth scale (180 kHz).
        snr0_linear=1.0,  # Reference SNR at G=0, i.e., 1.0 linear = 0 dB.
        eta_min=0.1,  # Conservative floor to keep max PRB demand finite.
    )

    # Extreme ln(S): very negative should hit max cap, very positive should hit min cap.
    prb = prb_demand_from_log_shadowing([-100.0, 100.0], params=params)

    assert prb[0] == params.max_prb_per_user
    assert prb[1] == 1


def test_total_prb_demand_without_weights() -> None:
    """Check unweighted aggregation equals a simple integer sum.

    Checks performed:
    - aggregate demand equals direct sum of per-user demands.
    """
    # Per-user PRB demands for three users.
    assert total_prb_demand([2, 3, 5]) == 10


def test_total_prb_demand_with_weights() -> None:
    """Check weighted aggregation for sampled-user scaling.

    This models the case where one sampled user represents multiple real users.

    Checks performed:
    - weighted total equals dot product of per-user demands and weights.
    """
    # Two sampled users, each representing 1000 users in the population.
    assert total_prb_demand([2, 3], user_weights=[1000, 1000]) == 5000


def test_prb_demand_rejects_invalid_log_shadowing_shape() -> None:
    """Reject malformed log-shadowing inputs early.

    The demand map expects a non-empty 1D array-like input with one value
    per user.

    Checks performed:
    - non-1D arrays are rejected,
    - empty vectors are rejected.
    """
    params = PRBDemandParams(
        required_rate_bps=1_000_000.0,  # Per-user target data rate (bits/s).
        rb_bandwidth_hz=180_000.0,  # PRB-like bandwidth scale (180 kHz).
        snr0_linear=1.0,  # Reference SNR at G=0, i.e., 1.0 linear = 0 dB.
        eta_min=0.1,  # Conservative floor to keep max PRB demand finite.
    )

    # Invalid shape: 2D input instead of a 1D per-user vector.
    with pytest.raises(ValueError, match="1D"):
        prb_demand_from_log_shadowing([[0.0, 1.0]], params=params)

    # Invalid shape: empty per-user vector.
    with pytest.raises(ValueError, match="non-empty"):
        prb_demand_from_log_shadowing([], params=params)


def test_total_prb_demand_rejects_invalid_weights() -> None:
    """Reject invalid weight vectors for weighted PRB aggregation.

    Weight vectors must be positive and match the per-user PRB array length.

    Checks performed:
    - mismatched vector lengths are rejected,
    - non-positive weights are rejected.
    """
    # Invalid parameterization: number of weights does not match number of users.
    with pytest.raises(ValueError, match="length must match"):
        total_prb_demand([1, 2], user_weights=[1])

    # Invalid parameterization: non-positive weight is not allowed.
    with pytest.raises(ValueError, match="must be positive"):
        total_prb_demand([1, 2], user_weights=[1, 0])


def test_prb_demand_increases_with_distance_when_pathloss_is_enabled() -> None:
    """With pathloss enabled, farther users should not need fewer PRBs.

    Checks performed:
    - users with the same shadowing but larger beam-center offset receive lower
      SNR from the slant-range term;
    - lower SNR translates into weakly larger PRB demand.
    """

    params = PRBDemandParams(
        required_rate_bps=1_000_000.0,
        rb_bandwidth_hz=180_000.0,
        snr0_linear=1.0,
        eta_min=0.1,
        pathloss_exponent=2.0,
        satellite_altitude_units=50.0,
    )
    log_shadowing = [0.0, 0.0]
    user_locations = [[0.0, 0.0], [30.0, 0.0]]

    prb = prb_demand_from_log_shadowing(
        log_shadowing,
        params=params,
        user_locations=user_locations,
        beam_center_xy=(0.0, 0.0),
    )

    assert prb[1] > prb[0]


def test_prb_demand_requires_user_locations_when_pathloss_is_enabled() -> None:
    """Pathloss-enabled demand mapping must receive user coordinates.

    Checks performed:
    - enabling the slant-range term without user positions is rejected.
    """

    params = PRBDemandParams(
        required_rate_bps=1_000_000.0,
        rb_bandwidth_hz=180_000.0,
        snr0_linear=1.0,
        eta_min=0.1,
        pathloss_exponent=2.0,
        satellite_altitude_units=50.0,
    )

    with pytest.raises(ValueError, match="user_locations must be provided"):
        prb_demand_from_log_shadowing([0.0], params=params)
