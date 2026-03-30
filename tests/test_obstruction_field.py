"""Tests for deterministic obstruction-field ground-truth patterns.

These tests validate geometry masks and loss-application behavior for:
- centered square,
- fixed-area square fragments,
- vertical bands,
- multiple circles.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from sim.stochastic.obstruction_field import (
    ObstructionFieldSpec,
    evaluate_obstruction_log_shadowing,
)
from sim.stochastic.user_locations import CircularBeam


def test_square_center_pattern_applies_extra_loss_inside_square_only() -> None:
    """Centered-square obstruction should reduce G only inside square mask."""

    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=10.0)
    spec = ObstructionFieldSpec(
        pattern_kind="square_center",
        extra_loss_db=20.0,
        base_log_shadowing=0.0,
        square_area_fraction=0.5,
    )

    # Center point is inside square. Second point is outside square but inside beam.
    points = np.array(
        [
            [0.0, 0.0],
            [8.0, 0.0],
        ],
        dtype=float,
    )
    g = evaluate_obstruction_log_shadowing(user_locations=points, beam=beam, spec=spec)

    loss_shift = (math.log(10.0) / 10.0) * 20.0
    assert np.isclose(g[0], -loss_shift)
    assert np.isclose(g[1], 0.0)


def test_square_fragments_with_one_fragment_matches_center_square() -> None:
    """A one-fragment lattice should reduce exactly to the centered square."""

    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=10.0)
    points = np.array(
        [
            [0.0, 0.0],
            [6.0, 0.0],
            [7.0, 0.0],
            [0.0, 6.0],
            [0.0, 7.0],
        ],
        dtype=float,
    )
    centered = ObstructionFieldSpec(
        pattern_kind="square_center",
        extra_loss_db=10.0,
        square_area_fraction=0.5,
    )
    fragments = ObstructionFieldSpec(
        pattern_kind="square_fragments",
        extra_loss_db=10.0,
        square_area_fraction=0.5,
        fragment_square_count=1,
        scenario_label="square_fragments_k1",
    )

    g_center = evaluate_obstruction_log_shadowing(
        user_locations=points,
        beam=beam,
        spec=centered,
    )
    g_fragments = evaluate_obstruction_log_shadowing(
        user_locations=points,
        beam=beam,
        spec=fragments,
    )

    np.testing.assert_allclose(g_fragments, g_center)


def test_square_fragments_spread_blocked_area_away_from_center_for_four_squares() -> None:
    """Four fragments should preserve area while opening the beam center."""

    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=10.0)
    spec = ObstructionFieldSpec(
        pattern_kind="square_fragments",
        extra_loss_db=10.0,
        square_area_fraction=0.5,
        fragment_square_count=4,
        scenario_label="square_fragments_k4",
    )

    total_area = spec.square_area_fraction * beam.area
    side = math.sqrt(total_area / spec.fragment_square_count)
    half = side / 2.0
    center_offset = (beam.radius / math.sqrt(2.0)) - half
    points = np.array(
        [
            [0.0, 0.0],  # center gap
            [center_offset, center_offset],  # top-right square center
            [-center_offset, center_offset],  # top-left square center
            [center_offset, -center_offset],  # bottom-right square center
            [-center_offset, -center_offset],  # bottom-left square center
        ],
        dtype=float,
    )
    g = evaluate_obstruction_log_shadowing(user_locations=points, beam=beam, spec=spec)
    loss_shift = (math.log(10.0) / 10.0) * 10.0

    assert np.isclose(g[0], 0.0)
    assert np.allclose(g[1:], -loss_shift)


def test_square_fragments_preserve_total_blocked_area_across_fragment_counts() -> None:
    """Changing fragment count should preserve the total blocked beam fraction."""

    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=1.0)
    xs = np.linspace(-beam.radius, beam.radius, 401)
    xx, yy = np.meshgrid(xs, xs, indexing="xy")
    grid_points = np.column_stack([xx.ravel(), yy.ravel()])
    inside_beam = (grid_points[:, 0] ** 2 + grid_points[:, 1] ** 2) <= beam.radius**2
    sample_points = grid_points[inside_beam]

    blocked_fraction_estimates = []
    for square_count in (1, 4, 9, 16, 25):
        spec = ObstructionFieldSpec(
            pattern_kind="square_fragments",
            extra_loss_db=8.0,
            square_area_fraction=0.5,
            fragment_square_count=square_count,
            scenario_label=f"square_fragments_k{square_count}",
        )
        g = evaluate_obstruction_log_shadowing(
            user_locations=sample_points,
            beam=beam,
            spec=spec,
        )
        blocked_fraction_estimates.append(float(np.mean(g < 0.0)))

    for estimate in blocked_fraction_estimates:
        assert abs(estimate - 0.5) < 0.02
    assert max(blocked_fraction_estimates) - min(blocked_fraction_estimates) < 0.02


def test_vertical_bands_pattern_alternates_obstructed_strips() -> None:
    """Vertical-band obstruction should alternate blocked/unblocked strips."""

    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=10.0)
    spec = ObstructionFieldSpec(
        pattern_kind="vertical_bands",
        extra_loss_db=10.0,
        base_log_shadowing=0.0,
        vertical_band_count=4,
    )

    # With 4 bands across x in [-10,10], obstructed bands are indices 0 and 2.
    points = np.array(
        [
            [-7.0, 0.0],  # band 0 -> obstructed
            [-2.0, 0.0],  # band 1 -> clear
            [2.0, 0.0],  # band 2 -> obstructed
            [7.0, 0.0],  # band 3 -> clear
        ],
        dtype=float,
    )
    g = evaluate_obstruction_log_shadowing(user_locations=points, beam=beam, spec=spec)
    loss_shift = (math.log(10.0) / 10.0) * 10.0

    assert np.isclose(g[0], -loss_shift)
    assert np.isclose(g[1], 0.0)
    assert np.isclose(g[2], -loss_shift)
    assert np.isclose(g[3], 0.0)


def test_multi_circles_pattern_covers_center_and_ring_centers() -> None:
    """Multi-circle obstruction should apply loss inside any selected circle."""

    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=10.0)
    spec = ObstructionFieldSpec(
        pattern_kind="multi_circles",
        extra_loss_db=6.0,
        base_log_shadowing=0.0,
        multi_circle_count=3,
        multi_circle_radius_ratio=0.2,
        multi_circle_ring_ratio=0.5,
    )

    # For count=3: centers are (0,0), (5,0), (-5,0), circle radius=2.
    points = np.array(
        [
            [0.0, 0.0],  # center circle
            [5.0, 0.0],  # right ring circle center
            [-5.0, 0.0],  # left ring circle center
            [0.0, 5.0],  # outside all circles
        ],
        dtype=float,
    )
    g = evaluate_obstruction_log_shadowing(user_locations=points, beam=beam, spec=spec)
    loss_shift = (math.log(10.0) / 10.0) * 6.0

    assert np.isclose(g[0], -loss_shift)
    assert np.isclose(g[1], -loss_shift)
    assert np.isclose(g[2], -loss_shift)
    assert np.isclose(g[3], 0.0)


def test_obstruction_spec_validates_parameter_ranges() -> None:
    """ObstructionFieldSpec should reject invalid geometry/loss parameters."""

    with pytest.raises(ValueError, match="non-negative"):
        ObstructionFieldSpec(pattern_kind="square_center", extra_loss_db=-1.0)

    with pytest.raises(ValueError, match="square_area_fraction"):
        ObstructionFieldSpec(
            pattern_kind="square_center",
            extra_loss_db=1.0,
            square_area_fraction=0.0,
        )

    with pytest.raises(ValueError, match="fragment_square_count"):
        ObstructionFieldSpec(
            pattern_kind="square_fragments",
            extra_loss_db=1.0,
            fragment_square_count=3,
        )

    with pytest.raises(ValueError, match="2/pi"):
        ObstructionFieldSpec(
            pattern_kind="square_fragments",
            extra_loss_db=1.0,
            square_area_fraction=0.8,
            fragment_square_count=4,
        )

    with pytest.raises(ValueError, match="vertical_band_count"):
        ObstructionFieldSpec(
            pattern_kind="vertical_bands",
            extra_loss_db=1.0,
            vertical_band_count=0,
        )

    with pytest.raises(ValueError, match="multi_circle_count"):
        ObstructionFieldSpec(
            pattern_kind="multi_circles",
            extra_loss_db=1.0,
            multi_circle_count=0,
        )

    with pytest.raises(ValueError, match="must be <= 1.0"):
        ObstructionFieldSpec(
            pattern_kind="multi_circles",
            extra_loss_db=1.0,
            multi_circle_radius_ratio=0.7,
            multi_circle_ring_ratio=0.5,
        )


def test_evaluate_obstruction_log_shadowing_rejects_bad_location_shape() -> None:
    """Evaluator should require (n_users, 2) location arrays."""

    beam = CircularBeam(x_center=0.0, y_center=0.0, radius=1.0)
    spec = ObstructionFieldSpec(pattern_kind="square_center", extra_loss_db=1.0)
    with pytest.raises(ValueError, match="shape \\(n_users, 2\\)"):
        evaluate_obstruction_log_shadowing(
            user_locations=np.array([0.0, 1.0, 2.0]),
            beam=beam,
            spec=spec,
        )
