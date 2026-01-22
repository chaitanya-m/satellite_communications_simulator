"""End-to-end dimensioning test for outage-based feasibility on the 3D PPP world.

This test is the "v0.4.2" harness-level companion to the lower-level outage
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
