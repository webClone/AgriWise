"""
Test Suite: F36 / T09 ASMAE 13-State Publication & Scientific Support Classification
===================================================================================

Verifies Stage 1 and Stage 2 repairs for ASMAE latent state map publication:
1. Support classification: Missing ledger fails closed to unsupported; missing proof
   never produces Observed, direct_observation=True, or unsupported management eligibility.
   Prior-constrained requires evidence of an actual prior.
2. Water-state linkage: Vigor cannot qualify canopy water; canopy water alone cannot
   certify root-zone water.
3. Five previously unmapped states: Explicit policies for LAI, structure, bare soil,
   thermal stress, and surface wetness event.
4. Hypothesis & model states: Appropriate hypothesis, reconstruction, or memory labels.
5. All 11 registered states receive authorization in the positive fixture with no
   unmapped state gate errors.
"""
import copy
import pytest

from services.agribrain.layer10_sire.schema import (
    Layer10Input,
    SurfaceType,
    ASMAE_STATE_SURFACES,
    ASMAE_DIAGNOSTIC_SURFACES,
    SurfaceArtifact,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData
from services.agribrain.layer10_sire.surfaces.asmae import (
    compute_asmae_support_classification,
    generate_asmae_surfaces,
    generate_asmae_aliases,
)
from services.agribrain.layer10_sire.surface_contract import (
    serialize_surface_artifact,
)
from services.agribrain.layer10_sire.terminal_publication import (
    build_terminal_no_data_output,
)
from services.agribrain.scientific_contracts.state_schema_ref import (
    STATE_ORDER,
    SURFACE_TO_CANONICAL_STATE,
    canonical_state_key,
)
from services.agribrain.scientific_contracts.state_support import (
    StateSupportRecord,
    StateSupportStatus,
    ObservationRelationship,
)
from services.agribrain.scientific_contracts.ledger_adapter import (
    index_state_support_ledger,
)


GRID_SPEC = {
    "crs": "EPSG:4326",
    "bounds": [1.0, 2.0, 1.003, 2.003],
    "transform": [1.0, 0.001, 0.0, 2.003, 0.0, -0.001],
    "width": 3,
    "height": 3,
    "resolution_m": 10.0,
    "resolution": 10.0,
    "transform_convention": "gdal",
}

BASE_META = {
    "confidence": 0.8,
    "uncertainty": 0.2,
    "resolution_m": 10.0,
    "bma_status": "success",
    "diagnostic_only": True,
    "state_update_allowed": False,
    "scene_stack_mode": "real_raster",
    "operator_locked": False,
    "graph_locked": False,
    "radiometric_mode": "proxy",
    "enkf_mode": "proxy",
    "full_enkf_credit_allowed": False,
    "full_radiometric_credit_allowed": False,
    "content_hash": "TEST-CONTENT",
    "artifact_instance_hash": "TEST-INSTANCE",
}

BASE_EVIDENCE_STATE = {
    "state": "model_estimated",
    "state_availability": "CURRENT_SPATIAL_ASSIMILATED",
    "current_spatial_assimilation": True,
    "spatial_raster_available": True,
    "visualization_allowed": True,
    "production_usable": False,
    "real_asmae_evidence": False,
    "source_reality": "model_estimated",
    "current_1m_approval_allowed": False,
    "scientific_surface_allowed": False,
    "state_update_allowed": False,
}


def _build_test_ledger(states=STATE_ORDER, count=1, relationship=ObservationRelationship.INDIRECT):
    return {
        state: StateSupportRecord(
            state=state,
            support_status=StateSupportStatus.ASSIMILATED if count > 0 else StateSupportStatus.PRIOR_CONSTRAINED,
            observation_relationship=relationship,
            source_feature_ids=("TEST_NDMI", "TEST_RED_EDGE", "TEST_SWIR_SALINITY"),
            accepted_update_count=count,
            spatial_support="raster",
            authority_ceiling="DIAGNOSTIC",
        ).to_dict()
        for state in states
    }


def _build_test_output(surfaces, *, states=None, proof_fields=None, state_fields=None, production=False):
    out = build_terminal_no_data_output(
        run_id="TEST-RUN",
        request_run_id="TEST-REQ",
        timestamp="2026-10-22T00:00:00Z",
        reason="TEST-INIT",
        core_asmae_evidence_state=BASE_EVIDENCE_STATE,
    )
    out.surface_pack = copy.deepcopy(surfaces)
    out.asmae_evidence_state = copy.deepcopy(BASE_EVIDENCE_STATE)
    if state_fields:
        out.asmae_evidence_state.update(state_fields)
    out.asmae_evidence_state["production_usable"] = production
    out.asmae_feature_pack = {
        "state_support_ledger": _build_test_ledger() if states is None else states
    }
    out.asmae_proof = {
        "sentinel_proof": {"s2_real_scene_count": 1, "s1_real_scene_count": 0},
        "feature_proof": {"assimilated": ["ndmi", "red_edge", "swir_salinity", "ndvi"]},
        "weather_proof": {"daily_count": 1},
        "enkf_proof": {"full_enkf_credit_allowed": False},
        "retrovalidation_proof": {"real_holdout_count": 1},
        "bma_proof": {"production_bma_valid": True},
    }
    if proof_fields:
        out.asmae_proof.update(copy.deepcopy(proof_fields))
    out.surface_behavior_proof = {"source_signal_used": "ASMAE_VIGOR"}
    return out


def _generate_test_surfaces(*, use_ledger=True, ledger_count=1, real_evidence=False):
    inp = Layer10Input(tenant_id="TEST-TENANT", farm_id="TEST-FARM", plot_id="TEST-PLOT")
    l1 = L1SpatialData(
        height=3,
        width=3,
        grid_spec=copy.deepcopy(GRID_SPEC),
        asmae_evidence_state=copy.deepcopy(BASE_EVIDENCE_STATE),
        real_asmae_evidence=real_evidence,
        asmae_feature_pack={"grid_spec": copy.deepcopy(GRID_SPEC)},
    )
    if use_ledger:
        l1.asmae_feature_pack["state_support_ledger"] = _build_test_ledger(count=ledger_count)
    if real_evidence:
        l1.real_asmae_evidence = True
        l1.asmae_evidence_state.update(real_asmae_evidence=True, source_reality="real_raster")

    test_values = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]]
    for st in ASMAE_STATE_SURFACES:
        key = st.value.lower()
        l1.raster_metadata[key] = copy.deepcopy(BASE_META)
        l1.raster_maps[key] = copy.deepcopy(test_values)

    return generate_asmae_surfaces(inp, 3, 3, l1_data=l1)


# ==============================================================================
# Stage 1: Support Classification Tests (compute_asmae_support_classification)
# ==============================================================================

class TestSupportClassification:
    def test_canonical_state_key_resolves_all_13_states_and_aliases(self):
        for state in STATE_ORDER:
            # direct name
            assert canonical_state_key(state) == state
            # prefixed
            assert canonical_state_key(f"asmae_{state}") == state

        assert canonical_state_key("CANOPY_ASMAE_VIGOR") == "vigor"
        assert canonical_state_key("WATER_ASMAE_CANOPY_WATER") == "canopy_water"
        assert canonical_state_key("WATER_ASMAE_ROOT_ZONE_WATER") == "root_zone_water"
        assert canonical_state_key("NUTRIENT_ASMAE_CHLOROPHYLL_PROXY") == "chlorophyll"
        assert canonical_state_key("SALINITY_ASMAE_STRESS") == "salinity_stress"
        assert canonical_state_key("ASMAE_BARE_SOIL") == "bare_soil_fraction"
        assert canonical_state_key("ASMAE_SURFACE_WETNESS_EVENT") == "surface_wetness_event"

    def test_missing_ledger_fails_closed_to_unsupported_even_with_real_raster(self):
        """Missing ledger must fail closed to unsupported without manufacturing Observed."""
        for st in (
            SurfaceType.ASMAE_VIGOR,
            SurfaceType.ASMAE_LAI,
            SurfaceType.ASMAE_CHLOROPHYLL,
            SurfaceType.ASMAE_CANOPY_WATER,
            SurfaceType.ASMAE_ROOT_ZONE_WATER,
            SurfaceType.ASMAE_SURFACE_WETNESS_EVENT,
            SurfaceType.ASMAE_STRUCTURE,
            SurfaceType.ASMAE_BARE_SOIL,
            SurfaceType.ASMAE_SALINITY_STRESS,
            SurfaceType.ASMAE_THERMAL_STRESS,
            SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK,
        ):
            res = compute_asmae_support_classification(
                real_ev=True,
                source_reality="real_raster",
                meta=copy.deepcopy(BASE_META),
                stype=st,
                state_support_ledger={},  # Missing/empty ledger
                feature_name=st.value.lower(),
            )
            assert res["support_class"] == "unsupported", f"Expected unsupported for {st.value}, got {res['support_class']}"
            assert res["evidence_class"] == "Unsupported"
            assert res["direct_observation"] is False
            assert res["scouting_zone_eligible"] is False
            assert res["management_zone_eligible"] is False
            assert res["zone_statistics_eligible"] is False

    def test_prior_constrained_requires_evidence_of_actual_prior(self):
        """prior_constrained requires evidence of an actual prior in meta or ledger."""
        # Case A: explicit prior in ledger
        ledger_with_prior = _build_test_ledger(count=0)
        res_ledger = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger=ledger_with_prior,
            feature_name="vigor",
        )
        assert res_ledger["support_class"] == "prior_constrained"
        assert res_ledger["evidence_class"] == "Prior-Constrained"
        assert res_ledger["direct_observation"] is False

        # Case B: explicit prior flag in metadata
        res_meta = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={"has_prior_evidence": True},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_meta["support_class"] == "prior_constrained"
        assert res_meta["evidence_class"] == "Prior-Constrained"

        # Case C: no prior evidence anywhere fails closed to unsupported
        res_none = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_none["support_class"] == "unsupported"

    def test_accepted_indirect_ledger_gives_indirectly_constrained(self):
        ledger = _build_test_ledger(count=1, relationship=ObservationRelationship.INDIRECT)
        res = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={},
            stype=SurfaceType.ASMAE_CANOPY_WATER,
            state_support_ledger=ledger,
            feature_name="canopy_water",
        )
        assert res["support_class"] == "indirectly_constrained"
        assert res["evidence_class"] == "Indirectly-Constrained"
        assert res["direct_observation"] is False
        assert res["scouting_zone_eligible"] is True
        assert res["management_zone_eligible"] is False

    def test_diagnostic_surfaces_remain_derived_diagnostic(self):
        for st in (
            SurfaceType.ASMAE_POSTERIOR_CONCENTRATION,
            SurfaceType.ASMAE_UNCERTAINTY,
            SurfaceType.ASMAE_EFFECTIVE_RESOLUTION,
            SurfaceType.ASMAE_RETROVALIDATION_SCORE,
            SurfaceType.ASMAE_BMA_DISAGREEMENT,
        ):
            res = compute_asmae_support_classification(
                real_ev=True,
                source_reality="real_raster",
                meta={},
                stype=st,
                state_support_ledger={},
                feature_name=st.value.lower(),
            )
            assert res["support_class"] == "derived_diagnostic"
            assert res["evidence_class"] == "Derived diagnostic"
            assert res["direct_observation"] is False
            assert res["management_zone_eligible"] is False

    def test_management_zone_eligibility_strictly_guarded_by_authority_ceiling(self):
        """States with DIAGNOSTIC ceiling (LAI, chlorophyll, etc.) never get management eligibility."""
        # Simulated directly_assimilated entry for LAI (ceiling=DIAGNOSTIC)
        lai_ledger = {
            "lai": {
                "support_status": "directly_assimilated",
                "direct_observation_count": 5,
                "observation_relationship": "direct",
                "accepted_update_count": 5,
            }
        }
        res_lai = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={},
            stype=SurfaceType.ASMAE_LAI,
            state_support_ledger=lai_ledger,
            feature_name="lai",
        )
        assert res_lai["support_class"] == "directly_assimilated"
        assert res_lai["direct_observation"] is True
        assert res_lai["management_zone_eligible"] is False, "LAI must not be management eligible"

        # Vigor has PRESCRIPTION_ELIGIBLE ceiling
        vigor_ledger = {
            "vigor": {
                "support_status": "directly_assimilated",
                "direct_observation_count": 5,
                "observation_relationship": "direct",
                "accepted_update_count": 5,
            }
        }
        res_vigor = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger=vigor_ledger,
            feature_name="vigor",
        )
        assert res_vigor["management_zone_eligible"] is True


# ==============================================================================
# Stage 2: Publication Predicates & Authorization Tests (runner.py)
# ==============================================================================

class TestPublicationPredicates:
    @pytest.fixture(autouse=True)
    def setup_surfaces(self):
        self.surfaces = _generate_test_surfaces(use_ledger=True, ledger_count=1)

    def _execute_runner_authorizations(self, output, display_grid_spec=None, pipeline_grid_valid=True):
        grid = display_grid_spec or copy.deepcopy(GRID_SPEC)

        
        # Test helper extracting the exact runner authorization function
        import ast
        from pathlib import Path
        import numpy as np
        from typing import Any, Dict, List, Optional, Tuple, Set, Mapping
        from services.agribrain.layer10_sire.schema import GroundingClass, RenderMode, SurfaceArtifact
        from services.agribrain.layer10_sire.surface_contract import RENDER_AUTHORIZATION_VERSION

        runner_path = Path("services/agribrain/layer10_sire/runner.py")
        runner_ast = ast.parse(runner_path.read_text(encoding="utf-8"))

        base_env = dict(globals())
        base_env.update({
            "np": np,
            "Any": Any,
            "Dict": Dict,
            "List": List,
            "Optional": Optional,
            "Tuple": Tuple,
            "Set": Set,
            "Mapping": Mapping,
            "GroundingClass": GroundingClass,
            "RenderMode": RenderMode,
            "SurfaceType": SurfaceType,
            "SurfaceArtifact": SurfaceArtifact,
            "RENDER_AUTHORIZATION_VERSION": RENDER_AUTHORIZATION_VERSION,
            "ASMAE_STATE_SURFACES": ASMAE_STATE_SURFACES,
            "ASMAE_DIAGNOSTIC_SURFACES": ASMAE_DIAGNOSTIC_SURFACES,
        })

        # Collect required top-level functions from runner
        required_defs = {
            "validate_spatial_grid_spec",
            "has_salinity_specific_feature_evidence",
            "_surface_type_name",
            "is_render_dependency_surface",
            "surface_grid_validity",
            "separate_asmae_evidence_and_publication",
        }
        required_assigns = {
            "RENDER_DEPENDENCY_MASK_TYPES",
            "SALINITY_EVIDENCE_MARKERS",
            "ALL_BACKEND_KNOWN_SURFACES",
        }
        selected = []
        for node in runner_ast.body:
            if isinstance(node, ast.FunctionDef) and node.name in required_defs:
                selected.append(node)
            elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in required_assigns for t in node.targets
            ):
                selected.append(node)

        auth_nodes = None
        for node in ast.walk(runner_ast):
            if not isinstance(node, ast.Try):
                continue
            for start, stmt in enumerate(node.body):
                if isinstance(stmt, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "render_authorizations" for t in stmt.targets
                ):
                    for end in range(start, len(node.body)):
                        last = node.body[end]
                        if isinstance(last, ast.Assign) and any(
                            isinstance(t, ast.Attribute) and t.attr == "render_authorization_version"
                            for t in last.targets
                        ):
                            auth_nodes = node.body[start : end + 1]
                            break
                    break
            if auth_nodes:
                break
        assert auth_nodes, "Could not find render_authorizations block in runner.py"

        exec(compile(ast.Module(body=selected, type_ignores=[]), str(runner_path), "exec"), base_env)

        env = dict(
            base_env,
            output=output,
            display_grid_spec=grid,
            render_as_spatial=pipeline_grid_valid,
            grid_spec_status="ok" if pipeline_grid_valid else "missing_grid_spec",
        )
        exec(compile(ast.Module(body=auth_nodes, type_ignores=[]), str(runner_path), "exec"), env)
        return env


    def test_water_state_linkage_vigor_cannot_qualify_canopy_water(self):
        """Vigor support alone must NOT qualify canopy water."""
        out = _build_test_output(
            self.surfaces,
            states=_build_test_ledger(["vigor"], count=1),  # ONLY vigor supported
        )
        env = self._execute_runner_authorizations(out)
        gate_ok, reason = env["asmae_state_gate"]("ASMAE_CANOPY_WATER")
        assert gate_ok is False
        assert reason == "missing_state_support:canopy_water"

        # With canopy water supported, it passes
        out_ok = _build_test_output(
            self.surfaces,
            states=_build_test_ledger(["canopy_water"], count=1),
        )
        env_ok = self._execute_runner_authorizations(out_ok)
        gate_ok2, reason2 = env_ok["asmae_state_gate"]("ASMAE_CANOPY_WATER")
        assert gate_ok2 is True
        assert reason2 == ""

    def test_water_state_linkage_canopy_water_cannot_certify_root_zone_water(self):
        """Canopy water support alone must NOT certify root-zone water."""
        out = _build_test_output(
            self.surfaces,
            states=_build_test_ledger(["canopy_water"], count=1),  # ONLY canopy water supported
        )
        env = self._execute_runner_authorizations(out)
        gate_ok, reason = env["asmae_state_gate"]("ASMAE_ROOT_ZONE_WATER")
        assert gate_ok is False
        assert reason == "missing_state_support:root_zone_water"

        # With root-zone water supported, it passes
        out_ok = _build_test_output(
            self.surfaces,
            states=_build_test_ledger(["root_zone_water"], count=1),
        )
        env_ok = self._execute_runner_authorizations(out_ok)
        gate_ok2, reason2 = env_ok["asmae_state_gate"]("ASMAE_ROOT_ZONE_WATER")
        assert gate_ok2 is True
        assert reason2 == ""

    def test_five_previously_unmapped_states_have_explicit_predicates(self):
        """LAI, structure, bare_soil, thermal_stress, and surface_wetness are explicit."""
        unmapped_states = [
            ("ASMAE_LAI", "lai"),
            ("ASMAE_STRUCTURE", "structure"),
            ("ASMAE_BARE_SOIL", "bare_soil_fraction"),
            ("ASMAE_THERMAL_STRESS", "thermal_stress"),
            ("ASMAE_SURFACE_WETNESS_EVENT", "surface_wetness_event"),
        ]

        for stype_str, state_key in unmapped_states:
            # Case 1: Supported
            out_supp = _build_test_output(
                self.surfaces,
                states=_build_test_ledger([state_key], count=1),
            )
            env_supp = self._execute_runner_authorizations(out_supp)
            gate_ok, reason = env_supp["asmae_state_gate"](stype_str)
            assert gate_ok is True, f"{stype_str} should pass when {state_key} is supported"
            assert reason == ""

            # Case 2: Unsupported
            out_unsupp = _build_test_output(
                self.surfaces,
                states=_build_test_ledger([], count=0),  # empty ledger
            )
            env_unsupp = self._execute_runner_authorizations(out_unsupp)
            gate_unsupp, reason_unsupp = env_unsupp["asmae_state_gate"](stype_str)
            assert gate_unsupp is False
            assert reason_unsupp == f"missing_state_support:{state_key}"
            assert reason_unsupp != "surface_state_requirement_unmapped"

    def test_surface_wetness_event_requires_water_evidence_family(self):
        """Surface wetness event requires water family evidence in family gate."""
        ledger_no_water = {
            "surface_wetness_event": StateSupportRecord(
                state="surface_wetness_event",
                support_status=StateSupportStatus.ASSIMILATED,
                observation_relationship=ObservationRelationship.INDIRECT,
                source_feature_ids=("TEST_RED_EDGE", "TEST_NIR"),
                accepted_update_count=1,
                spatial_support="raster",
                authority_ceiling="DIAGNOSTIC",
            ).to_dict()
        }
        out = _build_test_output(
            self.surfaces,
            states=ledger_no_water,
            proof_fields={"weather_proof": {"daily_count": 0}},  # Remove weather daily count
        )
        # Clear water evidence features from assimilated
        out.asmae_proof["feature_proof"]["assimilated"] = ["red_edge"]
        env = self._execute_runner_authorizations(out)
        fam_ok, fam_reason = env["asmae_family_gate"]("ASMAE_SURFACE_WETNESS_EVENT")
        assert fam_ok is False
        assert fam_reason == "missing_water_evidence_family"

    def test_biotic_confounder_risk_requires_bma_and_own_state_support(self):
        """Biotic confounder risk requires global proof AND state ledger presence."""
        # Case A: BMA missing
        out_no_bma = _build_test_output(
            self.surfaces,
            states=_build_test_ledger(["biotic_confounder_risk"], count=1),
            proof_fields={"bma_proof": {"production_bma_valid": False}},
        )
        env_no_bma = self._execute_runner_authorizations(out_no_bma)
        ok_a, reason_a = env_no_bma["asmae_state_gate"]("ASMAE_BIOTIC_CONFOUNDER_RISK")
        assert ok_a is False
        assert reason_a == "missing_risk_bma_retro_support"

        # Case B: Proof present but own state support missing
        out_no_ledger = _build_test_output(
            self.surfaces,
            states=_build_test_ledger([], count=0),
            proof_fields={
                "bma_proof": {"production_bma_valid": True},
                "retrovalidation_proof": {"real_holdout_count": 1},
            },
        )
        env_no_ledger = self._execute_runner_authorizations(out_no_ledger)
        ok_b, reason_b = env_no_ledger["asmae_state_gate"]("ASMAE_BIOTIC_CONFOUNDER_RISK")
        assert ok_b is False
        assert reason_b == "missing_state_support:biotic_confounder_risk"

        # Case C: Both present
        out_both = _build_test_output(
            self.surfaces,
            states=_build_test_ledger(["biotic_confounder_risk"], count=1),
            proof_fields={
                "bma_proof": {"production_bma_valid": True},
                "retrovalidation_proof": {"real_holdout_count": 1},
            },
        )
        env_both = self._execute_runner_authorizations(out_both)
        ok_c, reason_c = env_both["asmae_state_gate"]("ASMAE_BIOTIC_CONFOUNDER_RISK")
        assert ok_c is True
        assert reason_c == ""

    def test_positive_fixture_authorizes_all_11_registered_states(self):
        """In positive fixture where all states have accepted updates, all 11 registered states pass."""
        out = _build_test_output(self.surfaces, states=_build_test_ledger(count=1))
        env = self._execute_runner_authorizations(out)

        auth_results = {}
        for st in ASMAE_STATE_SURFACES:
            stype = st.value
            gate_ok, reason = env["asmae_state_gate"](stype)
            auth_results[stype] = (gate_ok, reason)
            assert gate_ok is True, f"Failed state gate for {stype}: {reason}"
            assert reason == ""

        # All 11 registered states passed
        assert len(auth_results) == 11
        assert all(res[0] for res in auth_results.values())


class TestStage12ResidualCorrections:
    """Tests verifying the 5 residual groups S12-01 to S12-05 identified in independent review."""

    def test_s12_01_unsupported_biotic_ingredient_excluded_from_risk_composite(self, monkeypatch):
        """S12-01: Unsupported biotic ingredient is excluded from risk composite, preventing value leakage."""
        monkeypatch.setenv("ASMAE_ENABLED", "true")
        monkeypatch.setenv("ASMAE_DIAGNOSTIC_SHADOW_RUN_ENABLED", "true")
        monkeypatch.setenv("L10_ASMAE_SURFACES_ENABLED", "true")
        H, W = 3, 3
        inp = Layer10Input(tenant_id="T1", farm_id="F1", plot_id="p1")

        def _make_surfaces(scale):
            spatial_data = L1SpatialData(
                height=H,
                width=W,
                grid_spec=copy.deepcopy(GRID_SPEC),
                asmae_evidence_state={
                    **BASE_EVIDENCE_STATE,
                    "real_asmae_evidence": True,
                    "source_reality": "real_raster",
                },
                real_asmae_evidence=True,
                asmae_feature_pack={"grid_spec": copy.deepcopy(GRID_SPEC)},
            )
            # Biotic state with scale and no ledger -> unsupported
            spatial_data.raster_maps["asmae_biotic_confounder_risk"] = [
                [scale * 0.5, scale * 0.6, scale * 0.7],
                [scale * 0.5, scale * 0.6, scale * 0.7],
                [scale * 0.5, scale * 0.6, scale * 0.7],
            ]
            spatial_data.raster_metadata["asmae_biotic_confounder_risk"] = copy.deepcopy(BASE_META)
            # Add other risk ingredients (thermal stress, bma disagreement, conflict)
            for st in (SurfaceType.ASMAE_THERMAL_STRESS, SurfaceType.ASMAE_BMA_DISAGREEMENT, SurfaceType.ASMAE_CROSS_LAYER_CONFLICT):
                spatial_data.raster_maps[st.value.lower()] = [[0.2, 0.3, 0.4]] * 3
                spatial_data.raster_metadata[st.value.lower()] = copy.deepcopy(BASE_META)

            surfs = generate_asmae_surfaces(inp, H, W, l1_data=spatial_data)
            aliases = generate_asmae_aliases(H, W, surfs, inp, grid_spec_dict=GRID_SPEC)
            return surfs, aliases

        surfs_01, aliases_01 = _make_surfaces(0.1)
        surfs_10, aliases_10 = _make_surfaces(1.0)

        raw_biotic_01 = next(s for s in surfs_01 if s.semantic_type == SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK)
        assert raw_biotic_01.provenance["support_class"] == "unsupported"

        risk_01 = next(s for s in aliases_01 if s.semantic_type == SurfaceType.RISK_ASMAE_DIAGNOSTIC)
        risk_10 = next(s for s in aliases_10 if s.semantic_type == SurfaceType.RISK_ASMAE_DIAGNOSTIC)

        # Biotic risk was excluded from active risk ingredients
        assert SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK.value not in risk_01.provenance["risk_ingredients"]
        assert any(e["surface"] == SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK.value for e in risk_01.provenance["excluded_ingredients"])

        # Changing the unsupported biotic input scale does NOT alter the risk composite values
        assert risk_01.values == risk_10.values

    def test_s12_02_current_restrictions_and_block_reasons_override_historical_counts(self):
        """S12-02: A current unsupported status or block reason fails closed, overriding accepted_update_count > 0."""
        # A record with accepted_update_count=1, but support_status=unsupported and block reason
        entry = StateSupportRecord(
            state="vigor",
            support_status=StateSupportStatus.UNSUPPORTED,
            observation_relationship=ObservationRelationship.INDIRECT,
            source_feature_ids=("TEST_NDVI",),
            accepted_update_count=1,
            authority_ceiling="DIAGNOSTIC",
            block_reasons=("local_support_revoked",),
        ).to_dict()

        surfaces = [
            SurfaceArtifact(
                surface_id="ASMAE_VIGOR_TEST",
                semantic_type=SurfaceType.ASMAE_VIGOR,
                grid_ref="3x3",
                values=[[0.5] * 3] * 3,
                units="score",
                native_resolution_m=10.0,
                render_range=(0.0, 1.0),
                palette_id="viridis",
                source_layers=["L1"],
                provenance={"support_class": "unsupported", "block_reasons": ["local_support_revoked"]},
                grid_spec=GRID_SPEC,
            )
        ]
        out = _build_test_output(surfaces, states={"vigor": entry})
        # Execute runner gate
        runner_test = TestPublicationPredicates()
        env = runner_test._execute_runner_authorizations(out)
        gate_ok, reason = env["asmae_state_gate"]("ASMAE_VIGOR")
        assert gate_ok is False
        assert "blocked" in reason or "denied" in reason or "missing_state_support" in reason

    def test_s12_02_management_zone_eligibility_intercepted_by_runtime_ceiling_and_block_reasons(self):
        """S12-02: Static descriptor maximum is intersected with current runtime ceiling and block reasons."""
        # Vigor has static descriptor ceiling PRESCRIPTION_ELIGIBLE
        # Case A: runtime ceiling is DIAGNOSTIC -> mgmt must be False
        res_diag = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={
                "vigor": {
                    "support_status": "directly_assimilated",
                    "direct_observation_count": 1,
                    "observation_relationship": "direct",
                    "authority_ceiling": "DIAGNOSTIC",
                }
            },
            feature_name="vigor",
        )
        assert res_diag["support_class"] == "directly_assimilated"
        assert res_diag["management_zone_eligible"] is False

        # Case B: runtime ceiling is VISUALIZATION -> mgmt must be False
        res_vis = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={
                "vigor": {
                    "support_status": "directly_assimilated",
                    "direct_observation_count": 1,
                    "observation_relationship": "direct",
                    "authority_ceiling": "VISUALIZATION",
                }
            },
            feature_name="vigor",
        )
        assert res_vis["management_zone_eligible"] is False

        # Case C: has block reasons -> mgmt must be False
        res_blocked = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={
                "vigor": {
                    "support_status": "directly_assimilated",
                    "direct_observation_count": 1,
                    "observation_relationship": "direct",
                    "block_reasons": ["reference_cohort_not_validated"],
                }
            },
            feature_name="vigor",
        )
        assert res_blocked["management_zone_eligible"] is False

        # Case D: PRESCRIPTION_ELIGIBLE runtime ceiling with direct proof and no block reasons -> mgmt is True
        res_ok = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={"support_class": "directly_assimilated", "direct_observation_count": 1},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_ok["management_zone_eligible"] is True

    def test_s12_03_canonical_serialization_preserves_explicit_denials(self):
        """S12-03: Serializer preserves state_update_allowed=False and prescription_driver_allowed=False."""
        surf = SurfaceArtifact(
            surface_id="ASMAE_VIGOR_P1",
            semantic_type=SurfaceType.ASMAE_VIGOR,
            grid_ref="3x3",
            values=[[0.5] * 3] * 3,
            units="score",
            native_resolution_m=10.0,
            render_range=(0.0, 1.0),
            palette_id="viridis",
            source_layers=["L1"],
            provenance={
                "state_update_allowed": False,
                "prescription_driver_allowed": False,
                "diagnostic_only": True,
            },
            state_update_allowed=False,
            prescription_driver_allowed=False,
        )
        serialized = serialize_surface_artifact(surf)
        assert serialized["state_update_allowed"] is False
        assert serialized["prescription_driver_allowed"] is False

        # Even with legacy SurfaceArtifact defaults (True), explicit False in provenance wins
        surf_legacy = SurfaceArtifact(
            surface_id="CANOPY_ASMAE_VIGOR_P1",
            semantic_type=SurfaceType.CANOPY_ASMAE_VIGOR,
            grid_ref="3x3",
            values=[[0.5] * 3] * 3,
            units="score",
            native_resolution_m=10.0,
            render_range=(0.0, 1.0),
            palette_id="viridis",
            source_layers=["L1"],
            provenance={
                "state_update_allowed": False,
                "prescription_driver_allowed": False,
            },
            # state_update_allowed defaults to True
            # prescription_driver_allowed defaults to True
        )
        serialized_legacy = serialize_surface_artifact(surf_legacy)
        assert serialized_legacy["state_update_allowed"] is False
        assert serialized_legacy["prescription_driver_allowed"] is False

    def test_s12_04_strict_prior_variance_qualification(self):
        """S12-04: Bare labels, NaN, negative, boolean, and string variance fail closed to unsupported."""
        # Bare label without prior evidence fails closed
        res_bare = compute_asmae_support_classification(
            real_ev=False,
            source_reality="unknown",
            meta={"support_class": "prior_constrained"},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_bare["support_class"] == "unsupported"

        # NaN variance fails closed
        res_nan = compute_asmae_support_classification(
            real_ev=False,
            source_reality="unknown",
            meta={"prior_variance": float("nan")},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_nan["support_class"] == "unsupported"

        # Negative variance fails closed
        res_neg = compute_asmae_support_classification(
            real_ev=False,
            source_reality="unknown",
            meta={"prior_variance": -1.0},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_neg["support_class"] == "unsupported"

        # Boolean False variance fails closed
        res_bool = compute_asmae_support_classification(
            real_ev=False,
            source_reality="unknown",
            meta={"prior_variance": False},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_bool["support_class"] == "unsupported"

        # String 'false' flag fails closed
        res_str_flag = compute_asmae_support_classification(
            real_ev=False,
            source_reality="unknown",
            meta={"has_prior_evidence": "false"},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_str_flag["support_class"] == "unsupported"

        # Finite nonnegative zero variance qualifies
        res_zero = compute_asmae_support_classification(
            real_ev=False,
            source_reality="unknown",
            meta={"prior_variance": 0.0},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_zero["support_class"] == "prior_constrained"

    def test_s12_05_direct_proof_count_non_boolean_qualification_and_null_resilience(self):
        """S12-05: Direct counts must be non-boolean positive numbers; None and string do not raise exceptions."""
        # Boolean True count does not qualify as Observed
        res_bool = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={"support_class": "directly_assimilated", "direct_observation_count": True},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_bool["support_class"] == "indirectly_constrained"
        assert res_bool["direct_observation"] is False

        # Infinity count does not qualify
        res_inf = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={"support_class": "directly_assimilated", "direct_observation_count": float("inf")},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_inf["support_class"] == "indirectly_constrained"

        # None direct count does NOT raise TypeError
        res_none = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={"support_class": "directly_assimilated", "direct_observation_count": None},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_none["support_class"] == "indirectly_constrained"

        # String '1' count does NOT raise TypeError
        res_str = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={"support_class": "directly_assimilated", "direct_observation_count": "1"},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_str["support_class"] == "indirectly_constrained"

        # Valid positive integer direct count qualifies
        res_valid = compute_asmae_support_classification(
            real_ev=True,
            source_reality="real_raster",
            meta={"support_class": "directly_assimilated", "direct_observation_count": 1},
            stype=SurfaceType.ASMAE_VIGOR,
            state_support_ledger={},
            feature_name="vigor",
        )
        assert res_valid["support_class"] == "directly_assimilated"
        assert res_valid["direct_observation"] is True
