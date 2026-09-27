# -*- coding: utf-8 -*-
"""Regression and verification tests for ASMAE Retrovalidation Fidelity fixes."""

from __future__ import annotations

import datetime
from datetime import timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch
from pathlib import Path

import numpy as np
import pytest

from services.agribrain.layer05_asmae.resilient_posterior import (
    _is_proven_before_cutoff,
    _strip_dynamic_recursive,
    _prior_state_estimates,
)
from services.agribrain.layer05_asmae.retrovalidation.future_projection import (
    predict_held_out_scene,
)
from services.agribrain.layer05_asmae.background_jobs import (
    BoundedJobExecutor,
)


def test_is_proven_before_cutoff():
    cutoff = datetime.datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Valid prior observation
    past_data = {
        "recorded_at": "2026-05-01T10:00:00Z",
        "source_timestamp": "2026-05-01T09:30:00Z",
        "soil_moisture": 24.5,
    }
    assert _is_proven_before_cutoff(past_data, cutoff) is True

    # Leaked future observation
    future_data = {
        "recorded_at": "2026-05-02T10:00:00Z",
        "source_timestamp": "2026-05-02T09:30:00Z",
        "soil_moisture": 18.2,
    }
    assert _is_proven_before_cutoff(future_data, cutoff) is False

    # Missing timestamps
    no_ts_data = {
        "soil_moisture": 21.0,
    }
    assert _is_proven_before_cutoff(no_ts_data, cutoff) is False


def test_strip_dynamic_recursive_preserves_static_and_filters_future():
    cutoff = datetime.datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)

    soil_payload = {
        # Static properties should always be preserved
        "soil_type": "clay_loam",
        "texture": "loam",
        "field_capacity": 0.35,
        "wilting_point": 0.15,
        # Dynamic unproven or future measurements should be stripped
        "root_zone_water": 0.28,
        "soil_moisture": 0.25,
        "sub_measurements": {
            "future_reading": {
                "recorded_at": "2026-05-05T00:00:00Z",
                "source_timestamp": "2026-05-05T00:00:00Z",
                "root_zone_water": 0.12,
            },
            "past_reading": {
                "recorded_at": "2026-04-30T12:00:00Z",
                "source_timestamp": "2026-04-30T12:00:00Z",
                "root_zone_water": 0.31,
            },
        },
    }

    filtered = _strip_dynamic_recursive(soil_payload, cutoff, is_proven=False)
    assert filtered["soil_type"] == "clay_loam"
    assert filtered["texture"] == "loam"
    assert filtered["field_capacity"] == 0.35
    # Dynamic values at top level stripped because is_proven was False
    assert "root_zone_water" not in filtered
    assert "soil_moisture" not in filtered
    # Inside sub_measurements, past_reading retains dynamic values, future_reading has dynamic values stripped
    assert "sub_measurements" in filtered
    assert "root_zone_water" not in filtered["sub_measurements"]["future_reading"]
    assert filtered["sub_measurements"]["past_reading"]["root_zone_water"] == 0.31


def test_prior_state_estimates_dynamic_leakage_prevention():
    cutoff = datetime.datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    mock_input = MagicMock()
    mock_input.coarse_layer_outputs = {
        "chlorophyll_proxy": 45.0,
        "root_zone_water": 0.40,
    }
    mock_input.soil_context = {
        "texture": "sandy_loam",
        "root_zone_water": 0.22,  # unproven top-level
    }

    estimates = _prior_state_estimates(mock_input, as_of="2026-05-01T12:00:00Z")
    # With cutoff set, coarse outputs are zeroed, unproven dynamic soil is stripped
    assert "chlorophyll" not in estimates
    assert "root_zone_water" not in estimates


def test_predict_held_out_scene_expert_state_gating():
    # Setup mock operator and scene
    operator = MagicMock()
    operator.scene_id = "scene_123"
    operator.valid_support_hash = "hash_abc"
    operator.H_matrix = np.eye(2)

    scene = MagicMock()
    scene.scene_id = "scene_123"
    scene.valid_support_hash = "hash_abc"

    # Training state
    training_state = {
        "node_1": [0.5, 0.3],
        "node_2": [0.6, 0.4],
    }

    # When expert_state_indices specifies state index 99 (which no observation maps to),
    # all observation channels should be gated out and result in empty errors dict
    result = predict_held_out_scene(
        training_state=training_state,
        holdout_scene=scene,
        operator=operator,
        expert_state_indices={99},
    )
    assert isinstance(result, dict)
    assert result["errors"] == {}


def test_bounded_job_executor_capacity_and_completion():
    executor = BoundedJobExecutor(max_workers=2)

    with patch.object(executor, "get_active_worker_pids", return_value=[1234]):
        assert executor.get_active_worker_count() == 1
        assert executor.can_spawn() is True

    with patch.object(executor, "get_active_worker_pids", return_value=[1234, 5678]):
        assert executor.get_active_worker_count() == 2
        assert executor.can_spawn() is False

    with patch.object(executor, "process_next_queued_job") as mock_process:
        executor.on_worker_completed(Path("dummy.job.json"))
        mock_process.assert_called_once()
