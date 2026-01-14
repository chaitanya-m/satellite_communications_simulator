# tests/test_dimensioning_qos_3d.py
"""End-to-end dimensioning tests for throughput-aware QoS in 3D."""

from __future__ import annotations

import math
import multiprocessing as mp
import random

from orchestrator.certificates.bernoulli import (
    AllSuccessCertificate,
    ClopperPearsonCertificate,
    HoeffdingCertificate,
)
from sim.dimensioning_3d import Dimensioning_3D

_QOS_SEARCH_CACHE: dict[str, int | None] | None = None


def _evaluate_design_qos(args: tuple) -> tuple[int, int, int, float, float, float, float]:
    """Return aggregated QoS stats for a single design."""
    (
        design,
        evals_per_design,
        seed_base,
        target_coverage,
        target_throughput,
        sim_kwargs,
    ) = args

    successes = 0
    trials = 0
    sum_coverage = 0.0
    sum_throughput = 0.0
    sum_n_sats = 0.0
    sum_n_ground = 0.0
    for offset in range(evals_per_design):
        rng = random.Random(seed_base + offset)
        sim = Dimensioning_3D(rng=rng, **sim_kwargs)
        metrics = sim.evaluate(lambda_sats=float(design))
        n_ground = float(metrics.get("n_ground", 0.0))
        if n_ground == 0.0:
            continue
        trials += 1
        sum_coverage += float(metrics["coverage"])
        sum_throughput += float(metrics["throughput"])
        sum_n_sats += float(metrics.get("n_sats", 0.0))
        sum_n_ground += n_ground
        if (
            metrics["coverage"] >= target_coverage
            and metrics["throughput"] >= target_throughput
        ):
            successes += 1

    return (
        int(design),
        successes,
        trials,
        sum_coverage,
        sum_throughput,
        sum_n_sats,
        sum_n_ground,
    )


def _run_qos_search() -> dict[str, int | None]:
    """Run the QoS search once and return first feasible designs per certificate."""
    global _QOS_SEARCH_CACHE
    if _QOS_SEARCH_CACHE is not None:
        return _QOS_SEARCH_CACHE

    target_coverage = 0.7
    alpha = 0.05
    delta = 0.3

    sinr_mu_db = 0.0
    sinr_sigma_db = 0.0
    bandwidth_hz = 1.0

    # With sigma=0, throughput = coverage * capacity; set throughput stricter than coverage.
    capacity = bandwidth_hz * math.log1p(10.0 ** (sinr_mu_db / 10.0))
    target_throughput = 0.7 * capacity

    certificate_order = ["all_success", "clopper_pearson", "hoeffding"]
    certificates = {
        "all_success": AllSuccessCertificate(alpha=alpha),
        "clopper_pearson": ClopperPearsonCertificate(alpha=alpha),
        "hoeffding": HoeffdingCertificate(alpha=alpha),
    }
    found: dict[str, int | None] = {name: None for name in certificates}
    threshold = 1.0 - delta

    ground_lambda = 500.0
    max_designs = 10000
    evals_per_design = 100
    seed = 1000

    designs = list(range(1, max_designs + 1, 1000))
    sim_kwargs = dict(
        ground_lambda=ground_lambda,
        lat_min_deg=-10.0,
        lat_max_deg=10.0,
        altitude_km=550.0,
        max_off_nadir_deg=20.0,
        sinr_mu_db=sinr_mu_db,
        sinr_sigma_db=sinr_sigma_db,
        bandwidth_hz=bandwidth_hz,
        throughput_aggregation="mean",
    )
    tasks = [
        (
            design,
            evals_per_design,
            seed + idx * evals_per_design,
            target_coverage,
            target_throughput,
            sim_kwargs,
        )
        for idx, design in enumerate(designs)
    ]

    results: dict[int, tuple[int, int, float, float, float, float]] = {}
    next_index = 0
    worker_count = min(len(tasks), max(1, mp.cpu_count()))

    print(
        "design successes/trials phat cov thr n_sats n_ground "
        + " ".join(f"{name}_lcb" for name in certificate_order)
    )

    pool = mp.get_context("spawn").Pool(processes=worker_count)
    try:
        for (
            design,
            successes,
            trials,
            sum_coverage,
            sum_throughput,
            sum_n_sats,
            sum_n_ground,
        ) in pool.imap_unordered(
            _evaluate_design_qos, tasks, chunksize=1
        ):
            results[design] = (
                successes,
                trials,
                sum_coverage,
                sum_throughput,
                sum_n_sats,
                sum_n_ground,
            )

            while next_index < len(designs) and designs[next_index] in results:
                candidate = designs[next_index]
                (
                    successes,
                    trials,
                    sum_coverage,
                    sum_throughput,
                    sum_n_sats,
                    sum_n_ground,
                ) = results[candidate]
                mean_coverage = sum_coverage / trials if trials else 0.0
                mean_throughput = sum_throughput / trials if trials else 0.0
                mean_n_sats = sum_n_sats / trials if trials else 0.0
                mean_n_ground = sum_n_ground / trials if trials else 0.0
                phat = successes / trials if trials else 0.0
                lcb_values = {
                    name: cert.lower_confidence_bound(successes, trials)
                    for name, cert in certificates.items()
                }
                statuses = {
                    name: "pass" if lcb >= threshold else "fail"
                    for name, lcb in lcb_values.items()
                }
                print(
                    f"{candidate} {successes}/{trials} {phat:.3f} "
                    f"cov={mean_coverage:.3f} thr={mean_throughput:.3f} "
                    f"n_sats={mean_n_sats:.1f} n_ground={mean_n_ground:.1f} "
                    + " ".join(
                        f"{lcb_values[name]:.3f}({statuses[name]})"
                        for name in certificate_order
                    )
                )

                for name, lcb in lcb_values.items():
                    if found[name] is None and lcb >= threshold:
                        found[name] = candidate

                next_index += 1

                if all(value is not None for value in found.values()):
                    pool.terminate()
                    break

            if all(value is not None for value in found.values()):
                break

        if not all(value is not None for value in found.values()):
            pool.close()
    finally:
        pool.join()

    _QOS_SEARCH_CACHE = found
    return found


def test_dimensioning_qos_all_success_certificate():
    """All-success certificate is expected to be the strictest."""
    found = _run_qos_search()
    assert found["all_success"] is not None, f"no all_success design found: {found}"


def test_dimensioning_qos_clopper_pearson_certificate():
    """Clopper-Pearson should certify with fewer failures than all-success."""
    found = _run_qos_search()
    assert found["clopper_pearson"] is not None, f"no clopper_pearson design found: {found}"


def test_dimensioning_qos_hoeffding_certificate():
    """Hoeffding bound should be the loosest certificate in the set."""
    found = _run_qos_search()
    assert found["hoeffding"] is not None, f"no hoeffding design found: {found}"
