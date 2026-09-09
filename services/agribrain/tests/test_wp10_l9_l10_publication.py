"""
Test Suite for Work Package 10 (WP10): Consolidate L9/L10 Publication.

Verifies:
1. Fix for Defect A19: Hallucination Guard context- and unit-scoped validation (temperature 25°C cannot validate 25 kg/ha rate).
2. Forbid conversational certainty on UNRESOLVED diagnostic states with safe scouting fallback.
3. Forbid recommending blocked/restricted actions with safe restriction replacement.
4. Formalized resolution metadata in L10 surfaces: native, display, and effective resolutions, and explicit masks.
5. Authority ceilings on GroundingClass.INTERPOLATED_PROXY surfaces (state_update_allowed=False, prescription_driver_allowed=False).
6. Fix for Defect A24: Pre-initialization of one_meter_visual_coverage_pct and strict_one_meter_candidate_pct in Layer 10 runner.
"""

import pytest
from services.agribrain.layer9_interface.hallucination_guard import (
    HallucinationGuard, GroundedFact, HallucinationFlag,
)
from services.agribrain.layer10_sire.schema import (
    GroundingClass, SurfaceArtifact, SurfaceType, PaletteId,
    Layer10Input,
)
from services.agribrain.layer10_sire.surface_contract import serialize_surface_artifact
from services.agribrain.layer10_sire.surfaces.spatial_modulation import (
    modulate_by_ndvi, build_modulation_masks,
)


def test_defect_a19_unit_and_domain_scoped_validation():
    """
    Verify Defect A19: Cross-domain validation bypass is eliminated.
    A 25°C weather reading must NOT validate a 25 kg/ha fertilizer recommendation.
    """
    # Upstream data contains weather 25°C, but fertilizer rate is 150 kg/ha
    guard = HallucinationGuard(
        grounded_facts=[
            GroundedFact(domain="temperature", variable="air_temperature", value=25.0, unit="°C"),
            GroundedFact(domain="application_rate", variable="fertilizer_rate", value=150.0, unit="kg/ha"),
            GroundedFact(domain="soil_moisture", variable="soil_moisture", value=30.0, unit="%"),
        ]
    )

    # 1. Hallucinated fertilizer rate (25 kg/ha) matching temperature value (25°C) must be FLAGGED
    text_bad_rate = "We recommend applying 25 kg/ha of fertilizer across the field."
    cleaned, flags = guard.validate(text_bad_rate)
    num_flags = [f for f in flags if f.claim_type == "number"]
    assert len(num_flags) > 0, "25 kg/ha must be flagged as an ungrounded number"
    assert any("25" in f.claim_value for f in num_flags)

    # 2. Legitimate temperature claim (25°C) must PASS without flags
    text_good_temp = "The forecast predicts a temperature of 25°C today."
    cleaned_temp, flags_temp = guard.validate(text_good_temp)
    num_flags_temp = [f for f in flags_temp if f.claim_type == "number"]
    assert len(num_flags_temp) == 0, "25°C must be recognized as grounded temperature"

    # 3. Legitimate fertilizer rate (150 kg/ha) must PASS without flags
    text_good_rate = "We recommend applying 150 kg/ha of fertilizer across the field."
    cleaned_rate, flags_rate = guard.validate(text_good_rate)
    num_flags_rate = [f for f in flags_rate if f.claim_type == "number"]
    assert len(num_flags_rate) == 0, "150 kg/ha must be recognized as grounded rate"


def test_hallucination_guard_from_layer9_input_domain_separation():
    """Verify that from_layer9_input builds distinct GroundedFact domains."""
    l9_input = {
        "actions": [
            {
                "action_id": "ACT-NITRO",
                "action_type": "FERTILIZE",
                "is_allowed": True,
                "rate": {"recommended": 120.0, "unit": "kg/ha"},
            }
        ],
        "diagnoses": [],
        "schedule": [],
        "zone_plan": {},
        "l1_fusion_data": {
            "temperature": 28.0,
            "soil_moisture": 24.0,
        },
    }

    guard = HallucinationGuard.from_layer9_input(l9_input)

    # Assert facts are separated by domain
    domains = {f.domain for f in guard.grounded_facts}
    assert "application_rate" in domains
    assert "temperature" in domains
    assert "soil_moisture" in domains

    # 28 kg/ha is ungrounded even though temperature is 28°C
    _, flags = guard.validate("Apply 28 kg/ha of fertilizer.")
    assert any(f.claim_type == "number" and "28" in f.claim_value for f in flags)


def test_forbid_conversational_certainty_on_unresolved_diagnoses():
    """Verify that conversational certainty on UNRESOLVED diagnostic states is blocked and replaced."""
    guard = HallucinationGuard(
        unresolved_diagnoses={"NITROGEN_DEFICIENCY", "LEAF_RUST"}
    )

    # LLM text expressing certainty about an unconfirmed hypothesis
    text_assertive = "The field is definitely suffering from nitrogen deficiency. We observed severe symptoms."
    cleaned, flags = guard.validate(text_assertive)

    diag_flags = [f for f in flags if f.claim_type == "unresolved_diagnosis"]
    assert len(diag_flags) == 1
    assert "NITROGEN_DEFICIENCY" in diag_flags[0].claim_value
    assert diag_flags[0].action == "replaced"

    # Cleaned text must communicate uncertainty and recommend field scouting
    assert "UNRESOLVED" in cleaned
    assert "scouting" in cleaned.lower()
    assert "definitely suffering" not in cleaned


def test_forbid_recommending_blocked_actions():
    """Verify that recommending blocked/restricted actions is flagged and sanitized."""
    guard = HallucinationGuard(
        blocked_actions={"ACT-002", "TILL", "toxic_spray_xyz"}
    )

    # LLM suggests executing a blocked action
    text_bad_action = "We recommend you proceed with ACT-002 tomorrow morning."
    cleaned, flags = guard.validate(text_bad_action)

    action_flags = [f for f in flags if f.claim_type == "action"]
    assert len(action_flags) > 0
    assert "ACT-002" in action_flags[0].claim_value
    assert action_flags[0].action == "replaced"

    # Cleaned text must warn the user of the restriction
    assert "[RESTRICTED]" in cleaned
    assert "BLOCKED" in cleaned
    assert "proceed with ACT-002" not in cleaned


def test_l10_resolution_metadata_and_serialization():
    """Verify resolution metadata (native, display, effective) and mask serialization in L10."""
    obs_mask = [[True, False], [True, True]]
    inf_mask = [[False, True], [False, False]]

    surface = SurfaceArtifact(
        surface_id="SURF-TEST-001",
        semantic_type=SurfaceType.NDVI_CLEAN,
        grid_ref="2x2",
        values=[[0.65, 0.45], [0.70, 0.80]],
        units="index",
        native_resolution_m=10.0,
        display_resolution_m=1.0,
        effective_resolution_m=10.0,
        observed_mask=obs_mask,
        inferred_mask=inf_mask,
        grounding_class=GroundingClass.RASTER_GROUNDED,
    )

    serialized = serialize_surface_artifact(surface)

    # Check resolution fields
    assert serialized["native_resolution_m"] == 10.0
    assert serialized["display_resolution_m"] == 1.0
    assert serialized["effective_resolution_m"] == 10.0

    # Check mask fields
    assert serialized["observed_mask"] == obs_mask
    assert serialized["inferred_mask"] == inf_mask
    assert serialized["grounding_class"] == "RASTER_GROUNDED"


def test_interpolated_proxy_authority_ceilings():
    """Verify GroundingClass.INTERPOLATED_PROXY strictly disables state updates and prescription driving."""
    surface = SurfaceArtifact(
        surface_id="SURF-MOD-001",
        semantic_type=SurfaceType.NUTRIENT_STRESS_PROB,
        grid_ref="2x2",
        values=[[0.3, 0.4], [0.5, 0.6]],
        units="probability",
        native_resolution_m=10.0,
        grounding_class=GroundingClass.INTERPOLATED_PROXY,
        # Intentionally attempting to enable authority
        state_update_allowed=True,
        prescription_driver_allowed=True,
    )

    serialized = serialize_surface_artifact(surface)

    # Authority ceiling must be clamped to False
    assert serialized["grounding_class"] == "INTERPOLATED_PROXY"
    assert serialized["state_update_allowed"] is False
    assert serialized["prescription_driver_allowed"] is False
    assert "authority_block_reason" in serialized
    assert "ceiling" in serialized["authority_block_reason"].lower()


def test_build_modulation_masks():
    """Verify build_modulation_masks produces accurate observed and inferred masks for proxy surfaces."""
    ndvi_r = [
        [0.5, None],
        [0.8, 0.2]
    ]
    H, W = 2, 2
    obs_mask, inf_mask = build_modulation_masks(ndvi_r, H, W)

    # Proxy surfaces have no direct native observation (observed_mask is all False)
    assert all(not obs_mask[r][c] for r in range(H) for c in range(W))

    # Inferred mask is True where NDVI proxy was valid
    assert inf_mask[0][0] is True
    assert inf_mask[0][1] is False
    assert inf_mask[1][0] is True
    assert inf_mask[1][1] is True


def test_defect_a24_experimental_policy_no_name_error(monkeypatch):
    """
    Verify Defect A24: Layer 10 runner pre-initializes one_meter_visual_coverage_pct
    and strict_one_meter_candidate_pct, preventing NameError during experimental policy execution.
    """
    from types import SimpleNamespace
    from services.agribrain.layer10_sire import runner as layer10_runner
    from services.agribrain.common.plot_namespace import PlotNamespace

    monkeypatch.setattr(layer10_runner, "load_layer10_from_cache", lambda _key: None)
    monkeypatch.setattr(layer10_runner, "save_layer10_to_cache", lambda *_args: 0)

    grid_spec = {
        "crs": "EPSG:4326",
        "transform": [1.0, 0.01, 0.0, 2.0, 0.0, -0.01],
        "width": 2,
        "height": 2,
        "bounds": [1.0, 1.98, 1.02, 2.0],
        "resolution": 10.0,
    }
    field_geometry = {
        "type": "Polygon",
        "coordinates": [[
            [1.0, 1.98], [1.02, 1.98], [1.02, 2.0],
            [1.0, 2.0], [1.0, 1.98],
        ]],
    }
    field_tensor = SimpleNamespace(
        run_id="tensor-test-run",
        maps={"ndvi": [[0.4, 0.5], [0.6, 0.7]]},
        map_metadata={"ndvi": {"resolution": 10.0, "source": "sentinel-2"}},
        data=[],
        channels=["ndvi"],
        plot_timeseries=[{"date": "2026-09-01", "ndvi": 0.55}],
        daily_state={},
        zone_stats={},
        zones={},
        provenance={"sensor": "S2A"},
        static={"soil_clay": 25.0},
        grid_spec=grid_spec,
    )

    l10_inp = Layer10Input(
        plot_namespace=PlotNamespace("tenant-test", "farm-test", "plot-sire-test"),
        field_tensor=field_tensor,
        field_geometry=field_geometry,
        grid_height=2,
        grid_width=2,
        source_policy="experimental",
        requested_modes=["standard"],
        user_mode="farmer",
    )

    try:
        output = layer10_runner.run_layer10_sire(l10_inp)
        assert output is not None
        assert output.display_trace is not None
        # Verify coverage metrics in display_trace are present and did NOT raise NameError
        assert "visual_detail_mask_pct" in output.display_trace
        assert "strict_candidate_pct" in output.display_trace
        assert output.display_trace["requested_policy"] == "experimental"
    except NameError as e:
        pytest.fail(f"Defect A24 regression: NameError raised during experimental policy execution: {e}")


