"""Tests for deterministic obstruction-field ground-truth patterns.

These tests validate geometry masks and loss-application behavior for:
- centered square,
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

