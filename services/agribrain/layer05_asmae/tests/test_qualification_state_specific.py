"""Tests for Work Package 05: Make ASMAE Qualification State-Specific.

Verifies:
1. Dynamic prospective forecast propagation vs frozen persistence baseline in retrovalidation.
2. BMA consensus preservation: independent physics models agreeing with base estimate (< 0.02 delta)
   remain active and are not excluded.
3. Per-variable authority ceilings: root_zone_water capped at DIAGNOSTIC; vigor/bare_soil_fraction
   are PRESCRIPTION_ELIGIBLE; salinity_stress/biotic_confounder_risk are MONITORING_ONLY.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from services.agribrain.layer05_asmae.config import STATE_NAMES
from services.agribrain.layer05_asmae.retrovalidation.future_projection import (
    forecast_held_out_scene,
    persistence_baseline_held_out_scene,
    predict_held_out_scene,
)
from services.agribrain.layer05_asmae.bma.posterior import run_bma
from services.agribrain.layer05_asmae.state.descriptors import (
    AuthorityCeiling,
    STATE_DESCRIPTORS,
    descriptor_for,
)
from services.agribrain.layer05_asmae.state.support_ledger import (
    PerVariableSupportLedger,
    VariableSupport,
)


# ---------------------------------------------------------------------------
# 1. Finding #10: Dynamic Prospective Forecast Closure vs Persistence Baseline
# ---------------------------------------------------------------------------

def test_dynamic_forecast_held_out_scene_computes_skill_score():
    """Verify that forecast_held_out_scene advances state forward and computes skill score."""
    # 1 zone, 13 states
    zone_id = "zone_alpha"
    # Base training state vector: vigor (index 0) = 0.5, root_zone_water (index 4) = 0.35, etc.
    training_state = {zone_id: [0.5, 2.0, 30.0, 0.6, 0.35, 0.0, 0.5, 0.1, 0.0, 0.0, 0.0, 0.4, 0.0]}

    # Mock operator
    operator = MagicMock()
    operator.scene_id = "scene_s2_001"
    operator.valid_support_hash = "hash_geom_123"
    operator.H_matrix = np.eye(1)  # 1 pixel, 1 zone

    # Mock holdout scene with 1 observation (NDVI)
    holdout_scene = MagicMock()
    holdout_scene.scene_id = "scene_s2_001"
    holdout_scene.valid_support_hash = "hash_geom_123"

    mock_pixel_obs = MagicMock()
    mock_pixel_obs.is_per_pixel = True
    mock_pixel_obs.n_pixels = 1
    # Suppose observed NDVI evolved to 0.55
    mock_pixel_obs.values = [0.55]
    mock_pixel_obs.valid_mask = [True]

    # Patch extract_pixel_observations where it is defined
    with patch(
        "services.agribrain.layer05_asmae.observation.pixel_extraction.extract_pixel_observations",
        return_value={"ndvi": mock_pixel_obs},
    ):
        result = forecast_held_out_scene(
            training_state=training_state,
            holdout_scene=holdout_scene,
            operator=operator,
            weather_day={"precipitation_mm": 5.0, "et0_mm": 2.0},
            delta_days=3.0,
        )

        assert result["status"] == "predicted"
        assert "persistence_rmse" in result
        assert "prospective_forecast_rmse" in result
        assert "forecast_skill_score" in result
        assert "forecast_state" in result
        assert result["delta_days"] == 3.0
        assert isinstance(result["forecast_skill_score"], float)

        # Baseline persistence function gives same persistence_rmse
        baseline = persistence_baseline_held_out_scene(
            training_state=training_state,
            holdout_scene=holdout_scene,
            operator=operator,
        )
        assert baseline["status"] == "predicted"
        assert np.isclose(result["persistence_rmse"], baseline["mean_error"])


# ---------------------------------------------------------------------------
# 2. Finding #11: Decoupled BMA Consensus Invariant
# ---------------------------------------------------------------------------

def test_bma_consensus_preserved_when_independent_models_agree():
    """Verify that independent physics models agreeing with base estimate (<0.02 delta) remain active."""
    # Base state has 1 zone
    zone_id = "zone_beta"
    base_state = [0.5, 2.0, 30.0, 0.6, 0.35, 0.0, 0.5, 0.1, 0.0, 0.0, 0.0, 0.4, 0.0]
    state_result = {
        "raster_maps": {zone_id: list(base_state)},
        "uncertainty_maps": {zone_id: [0.05] * len(base_state)},
    }

    # Two independent physics models predicting root_zone_water within 0.005 of base
    # (normalized delta = 0.005 / (1.0 - 0.0) = 0.005 < 0.02)
    pred1 = list(base_state)
    pred1[4] = 0.355  # 0.005 delta
    pred2 = list(base_state)
    pred2[4] = 0.353  # 0.003 delta

    mock_experts = {
        "water_balance": {
            "predictions": {zone_id: pred1},
            "target_states": ["root_zone_water"],
            "input_evidence": ["weather_daily_series", "soil_context"],
            "independence_key": "weather_soil_water_balance",
            "model_version": "water_balance_v1",
        },
        "optical_physiology": {
            "predictions": {zone_id: pred2},
            "target_states": ["root_zone_water"],
            "input_evidence": ["optical_reflectance_s2"],
            "independence_key": "optical_canopy_reflectance",
            "model_version": "optical_physiology_v1",
        },
    }

    retro_result = {
        "status": "success_with_holdouts",
        "expert_holdout_errors": {
            "water_balance": 0.04,
            "optical_physiology": 0.05,
        },
    }

    with patch(
        "services.agribrain.layer05_asmae.bma.physics_experts.compute_physics_experts",
        return_value=mock_experts,
    ):
        bma_output = run_bma(
            state_result=state_result,
            priors={},
            graph=None,
            retro_result=retro_result,
            evidence_context={},
        )

        # Invariant: Neither expert should be disqualified with target_state_delta_below_threshold
        proof = bma_output["expert_proof"]
        assert proof["water_balance"]["active"] is True
        assert proof["optical_physiology"]["active"] is True
        assert proof["water_balance"]["target_state_normalized_delta_from_base"] < 0.02
        assert proof["optical_physiology"]["target_state_normalized_delta_from_base"] < 0.02

        # Invariant: BMA must NOT fail with insufficient_experts
        assert bma_output["status"] == "success"
        assert len(bma_output["weights"]) == 2
        assert "water_balance" in bma_output["weights"]
        assert "optical_physiology" in bma_output["weights"]


# ---------------------------------------------------------------------------
# 3. Finding #12: Per-Variable Authority Ceilings
# ---------------------------------------------------------------------------

def test_per_variable_authority_ceilings():
    """Verify that authority ceilings are strictly scoped per state variable."""
    # Root-zone water must be DIAGNOSTIC (SAR fit cannot promote it to prescription)
    assert descriptor_for("root_zone_water").authority_ceiling == AuthorityCeiling.DIAGNOSTIC

    # Vigor and bare soil fraction are prescription eligible with high-res optical
    assert descriptor_for("vigor").authority_ceiling == AuthorityCeiling.PRESCRIPTION_ELIGIBLE
    assert descriptor_for("bare_soil_fraction").authority_ceiling == AuthorityCeiling.PRESCRIPTION_ELIGIBLE

    # Salinity stress and biotic risk are hypotheses requiring external evidence -> MONITORING_ONLY
    assert descriptor_for("salinity_stress").authority_ceiling == AuthorityCeiling.MONITORING_ONLY
    assert descriptor_for("biotic_confounder_risk").authority_ceiling == AuthorityCeiling.MONITORING_ONLY

    # PerVariableSupportLedger validates correctly with all 13 states
    ledger = PerVariableSupportLedger()
    for desc in STATE_DESCRIPTORS:
        ledger.set_support(
            VariableSupport(
                state_index=desc.index,
                canonical_name=desc.canonical_name,
                units=desc.units,
                identifiability_class=desc.identifiability_class,
                authority_ceiling=desc.authority_ceiling,
            )
        )
    violations = ledger.validate()
    assert violations == [], f"Ledger violations found: {violations}"
