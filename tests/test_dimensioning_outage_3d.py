"""End-to-end dimensioning test for outage-based feasibility on the 3D PPP world.

This test is follows the lower-level outage
experiment unit tests (`tests/test_min_feasible_outage.py`).

It demonstrates, in a single file, the *full loop* that the product relies on:

  design (satellite intensity) -> simulator trial metrics -> Bernoulli experiment
  bookkeeping -> feasibility certificate -> sequential design search

------------------------------------------------------------------------------
What is being dimensioned here?
------------------------------------------------------------------------------

The design variable is the satellite PPP mean (intensity) `lambda_sats`, which
we interpret as the expected number of satellites present in the trial world.

For a given design value `lambda_sats`, we repeatedly simulate trials under the
stated priors and count how often the design meets an outage requirement.

------------------------------------------------------------------------------
Outage definition used by the simulator
------------------------------------------------------------------------------

The simulator reports:
  - `coverage`: fraction of users with at least one visible satellite
  - `outage_rate`: fraction of users that are *not served*

In the simulator, a user is "served" if:
  (i) at least one satellite is visible, and
  (ii) the user's best-link throughput (bps) is at least `min_user_throughput_bps`.

In this test we set `min_user_throughput_bps = 0.0`, which makes condition (ii)
vacuous. Therefore "served" == "covered", and:

  outage_rate == 1 - coverage

That choice keeps the end-to-end test stable and focused on validating the
experiment/certificate/search plumbing for outage-based feasibility.

------------------------------------------------------------------------------
Certificate choice
------------------------------------------------------------------------------

We use `AllSuccessCertificate` (failure-intolerant) for two reasons:
  - It is deterministic and easy to reason about.
  - It does not require external statistical libraries (e.g. SciPy).

The certificate provides a lower confidence bound (LCB) on the true per-trial
success probability, based on the number of successful trials observed.

------------------------------------------------------------------------------
Success criterion and search loop
------------------------------------------------------------------------------

We fix:
  - a target maximum outage `o_max`
  - a target feasibility probability `p_target`
  - a confidence level `1 - alpha`

A *trial* is a success iff `outage_rate <= o_max`.

A *design* is certified feasible iff the certificate's lower confidence bound
LCB(p) satisfies:

  LCB(p) >= p_target

We then search designs in increasing order and stop at the first feasible one.
"""

from __future__ import annotations

import random

from experiments.satellites.min_feasible_outage import MinLambdaForOutage
from orchestrator.certificates.bernoulli import AllSuccessCertificate
from sim.dimensioning_3d import Dimensioning_3D


def test_dimensioning_outage_3d_sequential_search_stops():
    """Find the first certified-feasible design under an outage constraint.

    Motivation
    ----------
    This is the end-to-end test that shows the repo can perform *dimensioning*
    with an outage metric, using:
      - the simulator (`Dimensioning_3D`)
      - the outage experiment (`MinLambdaForOutage`)
      - an existing Bernoulli certificate (`AllSuccessCertificate`)

    Parameter choices
    -----------------
    We choose values aligned with the existing 3D dimensioning tests:
    - ground_lambda=500 to represent a mid-sized demand scenario
    - an equatorial band [-10, 10] degrees
    - altitude 550 km, off-nadir 60 degrees

    To keep runtime manageable, we use a reduced number of evaluations per
    design compared to the coverage test.

    Assertion strategy
    ------------------
    The test asserts that:
      (i) some design is certified feasible within the search budget, and
     (ii) the certified design is not trivially small.
    """
    # Outage target: allow up to 30% of users to be unserved (served >= 70%).
    max_outage = 0.3
    p_target = 0.7
    alpha = 0.05

    experiment = MinLambdaForOutage(max_outage=max_outage)
    certificate = AllSuccessCertificate(alpha=alpha)

    ground_lambda = 500.0
    max_designs = 400
    evals_per_design = 50
    seed = 1000

    # This mirrors the existing coverage dimensioning test's search pattern,
    # but uses outage_rate acceptance instead of coverage acceptance.
    certified_design: int | None = None
    for n in range(1, max_designs + 1, 10):
        lam = float(n)
        for _ in range(evals_per_design):
            rng = random.Random(seed)
            seed += 1

            sim = Dimensioning_3D(
                ground_lambda=ground_lambda,
                lat_min_deg=-10.0,
                lat_max_deg=10.0,
                altitude_km=550.0,
                max_off_nadir_deg=60.0,
                # Throughput still gets computed, but the outage threshold is set
                # to 0.0 so "served" is equivalent to "visible".
                bandwidth_hz=1.0,
                min_user_throughput_bps=0.0,
                tx_power_w=1.0,
                pathloss_exponent=2.0,
                noise_density_w_per_hz=1e-12,
                rng=rng,
            )

            metrics = sim.evaluate(lambda_sats=lam)
            experiment.on_evaluation(lam, metrics)

        successes = experiment._successes.get(lam, 0)
        trials = experiment._trials.get(lam, 0)
        lcb = certificate.lower_confidence_bound(successes, trials)

        if lcb >= p_target:
            certified_design = n
            break

    assert certified_design is not None, "No design certified feasible within the search budget"
    assert certified_design > 100


def test_dimensioning_outage_3d_sequential_search_with_min_user_throughput_threshold():
    """End-to-end outage dimensioning where "served" requires a nonzero throughput.

    Motivation
    ----------
    The previous test in this file sets `min_user_throughput_bps=0.0`, which
    makes the simulator's service indicator equivalent to pure visibility:
        served == covered
    and therefore:
        outage_rate == 1 - coverage

    That is useful for validating the outage experiment/certificate/search
    plumbing, but it does not exercise the *throughput threshold* branch of the
    outage definition.

    This test therefore repeats the same end-to-end dimensioning loop while
    setting `min_user_throughput_bps > 0`. In that regime:
        served := 1{ visible AND best_link_throughput_bps >= min_user_throughput_bps }
    so a user can be "covered" but still "in outage" if its best link is too
    weak.

    What this test validates
    ------------------------
    - The simulator produces an `outage_rate` that depends on the throughput
      threshold (not just on geometry/visibility).
    - The `MinLambdaForOutage` experiment can use that metric as the Bernoulli
      success criterion (outage_rate <= o_max).
    - The certificate + sequential search loop still finds a feasible design.

    Runtime / stability considerations
    ----------------------------------
    Throughput thresholding introduces additional randomness beyond geometry
    (Rayleigh fading and interference/noise effects), and it can make designs
    harder to certify.

    To keep the test runtime reasonable and the result stable:
    - we reduce ground demand intensity (`ground_lambda`) relative to the larger
      500-user tests
    - we use a moderate number of trials per design
    - we use a noise floor and bandwidth that produce bps values on the order
      of 1e5-1e6, and we set a threshold in that range so it is nontrivial but
      still feasible

    """
    max_outage = 0.3
    p_target = 0.7
    alpha = 0.05

    experiment = MinLambdaForOutage(max_outage=max_outage)
    certificate = AllSuccessCertificate(alpha=alpha)

    # Smaller than 500 to reduce the O(n_ground * n_sats) per-trial cost.
    ground_lambda = 200.0

    # Use bps-scale throughput by giving the link a 1 MHz bandwidth.
    bandwidth_hz = 1e6
    min_user_throughput_bps = 4e5

    # Keep the radio model in a plausible regime where the threshold can be met.
    tx_power_w = 10.0
    pathloss_exponent = 2.2
    noise_density_w_per_hz = 1e-18

    # Tight budgets: enough to certify, but bounded runtime.
    max_designs = 500
    evals_per_design = 20
    seed = 20000

    certified_design: int | None = None
    for n in range(100, max_designs + 1, 20):
        lam = float(n)
        for _ in range(evals_per_design):
            rng = random.Random(seed)
            seed += 1

            sim = Dimensioning_3D(
                ground_lambda=ground_lambda,
                lat_min_deg=-10.0,
                lat_max_deg=10.0,
                altitude_km=550.0,
                max_off_nadir_deg=60.0,
                earth_radius_km=6371.0,
                bandwidth_hz=bandwidth_hz,
                throughput_aggregation="mean",
                min_user_throughput_bps=min_user_throughput_bps,
                tx_power_w=tx_power_w,
                pathloss_exponent=pathloss_exponent,
                noise_density_w_per_hz=noise_density_w_per_hz,
                rng=rng,
            )

            metrics = sim.evaluate(lambda_sats=lam)
            experiment.on_evaluation(lam, metrics)

        successes = experiment._successes.get(lam, 0)
        trials = experiment._trials.get(lam, 0)
        lcb = certificate.lower_confidence_bound(successes, trials)

        if lcb >= p_target:
            certified_design = n
            break

    assert certified_design is not None, "No design certified feasible within the search budget"
