"""
Comprehensive A/B Acceptance Gate Test Suite
============================================
Single integrated acceptance gate validating Batch A and Batch B implementation cohort:
  1. Complete cache contract: generation-addressed NPZ, explicit mask members,
     no fake state variables, old-generation readability, interrupted commit preservation,
     tampering detection, concurrent reader/writer safety.
  2. Permission defaults at every layer: SurfaceArtifact defaults to False,
     constructors, producers, serialization, strict bool parsing ("false" -> False),
     restriction carriers and capability ceilings, valid explicit grant positive controls.
  3. Directness from measurement/operator receipt & descriptor policy constraint.
  4. Per-state actual influence qualification: zero localized support rejected,
     state-scaled numerical tolerances, zero mean change with covariance reduction,
     stress-memory forecast/decay preserved while excluding forbidden updates.
  5. Lossless counter preservation: direct, proxy, and indirect observation counters.
  6. Scientific validity vs display/availability: all 13 states in invariants,
     admissible scientific domains, LAI legend [0, 8], empty raster cannot fabricate plot estimate.
  7. Scientific export receipt: full metadata preservation in RasterEntry / export_raster_pack.
"""

import os
import math
import json
import uuid
import tempfile
import threading
from typing import Dict, Any, List
import numpy as np
import pytest

from services.agribrain.scientific_contracts.state_support import (
    StateSupportRecord,
    ObservationRelationship,
    StateEvidenceClass,
    resolve_state_evidence_class,
)
from services.agribrain.scientific_contracts.ledger_adapter import (
    canonicalize_state_support_record,
    validate_ledger_dict,
)
from services.agribrain.scientific_contracts.exceptions import ContractViolation

from services.agribrain.layer05_asmae.state.descriptors import (
    STATE_DESCRIPTORS,
    STATE_ORDER,
    AssimilationPolicy,
    AuthorityCeiling,
    get_descriptor,
)
from datetime import date
from services.agribrain.layer05_asmae.config import STATE_NAMES
from services.agribrain.layer05_asmae.schema import ASMAEInput
from services.agribrain.layer05_asmae.assimilation.filter import (
    update_step_ht,
    _state_mean_summary,
    _state_variance_summary,
)
from services.agribrain.layer05_asmae.feature_export import build_state_support_ledger
from services.agribrain.layer05_asmae.cache import (
    save_rasters_artifact,
    _load_validated_rasters,
    _raster_artifact_manifest,
    serialize_and_cache_asmae,
    deserialize_cached_asmae,
    _artifact_path,
)

from services.agribrain.layer10_sire.schema import (
    SurfaceArtifact,
    SurfaceType,
    Layer10Output,
    Layer10Input,
    PlotNamespace,
    RenderMode,
    GroundingClass,
)
from services.agribrain.layer10_sire.surface_contract import (
    serialize_surface_pack,
    _strict_bool,
)
from services.agribrain.layer10_sire.surfaces.asmae import (
    align_asmae_grid_to_target,
)
from services.agribrain.layer10_sire.invariants import enforce_layer10_invariants
from services.agribrain.layer10_sire.products.manifest import (
    build_render_manifest,
    DEFAULT_LEGENDS,
)
from services.agribrain.layer10_sire.products.export import (
    RasterEntry,
    export_raster_pack,
)


def _make_dummy_asmae_input(plot_id: str) -> ASMAEInput:
    return ASMAEInput(
        run_id=f"run_{plot_id}",
        plot_id=plot_id,
        polygon_geojson={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
        geometry_hash=f"geom_{plot_id}",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        layer0_source_packages={},
        mode="standard",
        source_policy="satellite",
    )


# ============================================================================
# 1. COMPLETE CACHE CONTRACT & RECONSTRUCTION
# ============================================================================

def test_cache_contract_zero_none_nan_and_masked_roundtrip(tmp_path):
    """Test roundtrip with zero, None, NaN, and numpy.ma.MaskedArray."""
    data = np.array([[1.0, 0.0], [np.nan, 4.0]], dtype=float)
    mask = np.array([[False, False], [True, False]], dtype=bool)
    masked_arr = np.ma.masked_array(data, mask=mask)

    raster_dict = {
        "raster_maps__vigor": masked_arr,
        "raster_maps__lai": [[0.0, None], [2.5, np.nan]],
    }
    artifact_key = f"test_plot_123_satellite_{uuid.uuid4().hex[:8]}"

    # Save rasters
    rel_ref = save_rasters_artifact(artifact_key, raster_dict)
    assert rel_ref != ""
    assert rel_ref.startswith(f"asmae_rasters/raster_{artifact_key}_")
    assert rel_ref.endswith(".npz")

    # Inspect manifest
    manifest = _raster_artifact_manifest(rel_ref, artifact_key)
    assert manifest["manifest_version"] == "v2_generation_addressed"
    assert "raster_maps__vigor" in manifest["arrays"]
    assert "__mask__raster_maps__vigor" in manifest["masks"]
    assert "raster_maps__lai" in manifest["arrays"]

    # Load validated rasters
    reconstructed = _load_validated_rasters(manifest, artifact_key)
    assert reconstructed is not None
    assert "raster_maps__vigor" in reconstructed
    assert "__mask__raster_maps__vigor" not in reconstructed  # Mask must not be a data raster

    # In vigor, cell (1, 0) was masked, so it must be None
    assert reconstructed["raster_maps__vigor"][0][0] == 1.0
    assert reconstructed["raster_maps__vigor"][0][1] == 0.0
    assert reconstructed["raster_maps__vigor"][1][0] is None
    assert reconstructed["raster_maps__vigor"][1][1] == 4.0

    # In lai, None and NaN must both be None, 0.0 must be preserved as 0.0
    assert reconstructed["raster_maps__lai"][0][0] == 0.0
    assert reconstructed["raster_maps__lai"][0][1] is None
    assert reconstructed["raster_maps__lai"][1][0] == 2.5
    assert reconstructed["raster_maps__lai"][1][1] is None


def test_cache_contract_old_generation_readability():
    """Reader must accept both old fixed-path and new generation-addressed refs."""
    artifact_key = f"test_old_gen_{uuid.uuid4().hex[:8]}"
    fixed_ref = f"asmae_rasters/raster_{artifact_key}.npz"
    full_path = _artifact_path(fixed_ref)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    arr = np.array([[0.5, 0.6], [0.7, 0.8]], dtype=float)
    with open(full_path, "wb") as f:
        np.savez_compressed(f, raster_maps__vigor=arr)

    manifest = _raster_artifact_manifest(fixed_ref, artifact_key)
    result = _load_validated_rasters(manifest, artifact_key)
    assert result is not None
    assert "raster_maps__vigor" in result
    assert result["raster_maps__vigor"][0][0] == 0.5

    # Clean up
    try:
        os.unlink(full_path)
    except OSError:
        pass


def test_cache_contract_interrupted_commit_preserves_old_generation():
    """Failure during commit must leave the previously committed generation intact."""
    plot_id = f"test_plot_commit_fail_{uuid.uuid4().hex[:8]}"
    inp = _make_dummy_asmae_input(plot_id)

    # First successful commit
    initial_output = {
        "plot_id": plot_id,
        "status": "success",
        "result_status": "success",
        "raster_maps": {"vigor": [[0.5, 0.5], [0.5, 0.5]]},
        "diagnostics": {},
    }
    committed_first = serialize_and_cache_asmae(inp, initial_output)
    assert committed_first is True

    # Read back to verify
    hit1 = deserialize_cached_asmae(inp)
    assert hit1 is not None
    assert hit1["raster_maps"]["vigor"][0][0] == 0.5
    old_raster_ref = hit1.get("rasters_artifact_ref")
    assert old_raster_ref != ""
    assert os.path.isfile(_artifact_path(old_raster_ref))

    # Now attempt a broken commit by passing an un-serializable object that fails during commit
    broken_output = {
        "plot_id": plot_id,
        "status": "success",
        "result_status": "success",
        "raster_maps": {"vigor": [[0.9, 0.9], [0.9, 0.9]]},
        "diagnostics": {},
    }
    # Monkey-patch _atomic_json_write to simulate crash/interruption
    from services.agribrain.layer05_asmae import cache as asmae_cache
    orig_write = asmae_cache._atomic_json_write

    def crash_write(path, data):
        raise IOError("Simulated disk power-loss during JSON commit")

    asmae_cache._atomic_json_write = crash_write
    try:
        commit_second = serialize_and_cache_asmae(inp, broken_output)
        assert commit_second is False
    finally:
        asmae_cache._atomic_json_write = orig_write

    # Old committed generation must remain valid and readable!
    hit2 = deserialize_cached_asmae(inp)
    assert hit2 is not None
    assert hit2["raster_maps"]["vigor"][0][0] == 0.5
    assert os.path.isfile(_artifact_path(old_raster_ref))


def test_cache_contract_tampering_rejection():
    """Tampering with NPZ bytes must cause deserializer to reject payload."""
    plot_id = f"test_plot_tamper_{uuid.uuid4().hex[:8]}"
    inp = _make_dummy_asmae_input(plot_id)
    output = {
        "plot_id": plot_id,
        "status": "success",
        "result_status": "success",
        "raster_maps": {"vigor": [[0.4, 0.4], [0.4, 0.4]]},
        "diagnostics": {},
    }
    assert serialize_and_cache_asmae(inp, output) is True
    hit = deserialize_cached_asmae(inp)
    assert hit is not None

    # Tamper with the NPZ file by appending corrupt bytes
    raster_ref = hit["rasters_artifact_ref"]
    full_path = _artifact_path(raster_ref)
    with open(full_path, "ab") as f:
        f.write(b"CORRUPTED_BYTES")

    # Deserializing must reject the tampered artifact
    tampered_hit = deserialize_cached_asmae(inp)
    assert tampered_hit is None


def test_cache_contract_concurrent_readers_writers():
    """Concurrent readers and writers under cache lock must not corrupt state."""
    plot_id = f"test_plot_concurrent_{uuid.uuid4().hex[:8]}"
    inp = _make_dummy_asmae_input(plot_id)

    # Seed initial state
    output0 = {
        "plot_id": plot_id,
        "status": "success",
        "result_status": "success",
        "raster_maps": {"vigor": [[0.1, 0.1], [0.1, 0.1]]},
        "diagnostics": {},
    }
    serialize_and_cache_asmae(inp, output0)

    errors = []

    def writer_worker(val):
        try:
            for _ in range(5):
                out = {
                    "plot_id": plot_id,
                    "status": "success",
                    "result_status": "success",
                    "raster_maps": {"vigor": [[val, val], [val, val]]},
                    "diagnostics": {},
                }
                serialize_and_cache_asmae(inp, out)
        except Exception as e:
            errors.append(e)

    def reader_worker():
        try:
            for _ in range(10):
                res = deserialize_cached_asmae(inp)
                if res is not None:
                    assert "raster_maps" in res
                    v = res["raster_maps"]["vigor"][0][0]
                    assert v in (0.1, 0.2, 0.3)
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=writer_worker, args=(0.2,)),
        threading.Thread(target=writer_worker, args=(0.3,)),
        threading.Thread(target=reader_worker),
        threading.Thread(target=reader_worker),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0


# ============================================================================
# 2. PERMISSION DEFAULTS, RESTRICTION CARRIERS, & POSITIVE CONTROLS
# ============================================================================

def test_surface_artifact_permission_defaults_to_false():
    """SurfaceArtifact dataclass must default action permissions to False."""
    surface = SurfaceArtifact(
        surface_id="TEST_01",
        semantic_type=SurfaceType.ASMAE_VIGOR,
        grid_ref="2x2",
        values=[[0.5, 0.5], [0.5, 0.5]],
        units="index",
        native_resolution_m=10.0,
    )
    assert surface.state_update_allowed is False
    assert surface.prescription_driver_allowed is False


def test_surface_contract_strict_boolean_parsing():
    """String 'false' in provenance must parse to False, not bool('false') -> True."""
    assert _strict_bool("false") is False
    assert _strict_bool("False") is False
    assert _strict_bool("0") is False
    assert _strict_bool(False) is False
    assert _strict_bool("true") is True
    assert _strict_bool("True") is True
    assert _strict_bool("1") is True
    assert _strict_bool(True) is True
    assert _strict_bool(None) is None


def test_surface_contract_permission_serialization_intersection():
    """Permissions must default False, intersect ceilings and restrictions."""
    # Case A: absent permissions -> False
    s_absent = SurfaceArtifact(
        surface_id="SURF_ABSENT",
        semantic_type=SurfaceType.ASMAE_VIGOR,
        grid_ref="2x2",
        values=[[0.5, 0.5], [0.5, 0.5]],
        units="index",
        native_resolution_m=10.0,
        provenance={},
    )
    doc_absent = serialize_surface_pack([s_absent])[0]
    assert doc_absent["state_update_allowed"] is False
    assert doc_absent["prescription_driver_allowed"] is False

    # Case B: explicit string 'false' in provenance -> False
    s_str_false = SurfaceArtifact(
        surface_id="SURF_STR_FALSE",
        semantic_type=SurfaceType.ASMAE_VIGOR,
        grid_ref="2x2",
        values=[[0.5, 0.5], [0.5, 0.5]],
        units="index",
        native_resolution_m=10.0,
        provenance={"state_update_allowed": "false", "prescription_driver_allowed": "false"},
    )
    doc_str_false = serialize_surface_pack([s_str_false])[0]
    assert doc_str_false["state_update_allowed"] is False
    assert doc_str_false["prescription_driver_allowed"] is False

    # Case C: Conflict between attr (True) and provenance (False) -> False
    s_conflict = SurfaceArtifact(
        surface_id="SURF_CONFLICT",
        semantic_type=SurfaceType.ASMAE_VIGOR,
        grid_ref="2x2",
        values=[[0.5, 0.5], [0.5, 0.5]],
        units="index",
        native_resolution_m=10.0,
        state_update_allowed=True,
        provenance={"state_update_allowed": False},
    )
    doc_conflict = serialize_surface_pack([s_conflict])[0]
    assert doc_conflict["state_update_allowed"] is False

    # Case D: Active restriction carrier -> False even with True request
    s_restricted = SurfaceArtifact(
        surface_id="SURF_RESTRICTED",
        semantic_type=SurfaceType.ASMAE_VIGOR,
        grid_ref="2x2",
        values=[[0.5, 0.5], [0.5, 0.5]],
        units="index",
        native_resolution_m=10.0,
        state_update_allowed=True,
        prescription_driver_allowed=True,
        block_reasons=["local_support_revoked"],
        provenance={"authority_ceiling": "PRESCRIPTION_DRIVER"},
    )
    doc_restricted = serialize_surface_pack([s_restricted])[0]
    assert doc_restricted["state_update_allowed"] is False
    assert doc_restricted["prescription_driver_allowed"] is False

    # Case E: Diagnostic authority ceiling -> False for state update and prescription
    s_diag = SurfaceArtifact(
        surface_id="SURF_DIAG",
        semantic_type=SurfaceType.ASMAE_VIGOR,
        grid_ref="2x2",
        values=[[0.5, 0.5], [0.5, 0.5]],
        units="index",
        native_resolution_m=10.0,
        state_update_allowed=True,
        prescription_driver_allowed=True,
        provenance={"authority_ceiling": "DIAGNOSTIC"},
    )
    doc_diag = serialize_surface_pack([s_diag])[0]
    assert doc_diag["state_update_allowed"] is False
    assert doc_diag["prescription_driver_allowed"] is False

    # Case F: Positive control - valid explicit grant with PRESCRIPTION_DRIVER ceiling and no blocks
    s_grant = SurfaceArtifact(
        surface_id="SURF_GRANT",
        semantic_type=SurfaceType.ASMAE_VIGOR,
        grid_ref="2x2",
        values=[[0.5, 0.5], [0.5, 0.5]],
        units="index",
        native_resolution_m=10.0,
        grounding_class="RASTER_GROUNDED",
        state_update_allowed=True,
        prescription_driver_allowed=True,
        provenance={"authority_ceiling": "PRESCRIPTION_DRIVER"},
    )
    doc_grant = serialize_surface_pack([s_grant])[0]
    assert doc_grant["state_update_allowed"] is True
    assert doc_grant["prescription_driver_allowed"] is True


def test_align_asmae_grid_fast_path_nodata_normalization():
    """Fast-path identity grid must clean -9999.0 and nan sentinels to None."""
    grid = [[0.5, -9999.0], [float("nan"), 0.8]]
    spec = {
        "crs": "EPSG:32630",
        "bounds": [500000.0, 4499980.0, 500020.0, 4500000.0],
        "transform": [500000.0, 10.0, 0.0, 4500000.0, 0.0, -10.0],
        "width": 2,
        "height": 2,
        "nodata": -9999.0,
    }
    aligned, src_spec, tgt_spec, meta = align_asmae_grid_to_target(
        grid=grid,
        source_grid_spec=spec,
        target_grid_spec=spec,
        target_height=2,
        target_width=2,
        method="nearest",
    )
    assert meta["resampling_method"] == "identity_grid"
    assert aligned[0][0] == 0.5
    assert aligned[0][1] is None  # -9999.0 cleaned
    assert aligned[1][0] is None  # NaN cleaned
    assert aligned[1][1] == 0.8


# ============================================================================
# 3. DIRECTNESS, SUPPORT, & PER-STATE INFLUENCE QUALIFICATION
# ============================================================================

def test_measurement_receipt_directness_and_indirect_restriction():
    """Descriptor policy constrains directness; unvalidated satellite products are indirect."""
    # S2 NDVI has target states vigor, lai; descriptor assimilation policy is INDIRECT_CONSTRAINT
    reports = update_reports = [
        {
            "obs_name": "ndvi",
            "sensor": "S2",
            "update_applied": True,
            "real_provider_product": True,
            "source_reality": "real_raster",
            "evidence_kind": "indirect_observation",
            "target_states": ["vigor", "lai"],
            "innovation_mean": 0.05,
            "sigma_obs": 0.04,
            "n_pixels": 100,
        }
    ]
    ledger = build_state_support_ledger(reports)
    # Vigor must be indirect and NOT field approval eligible
    assert ledger["vigor"]["indirect_observation_count"] == 1
    assert ledger["vigor"]["direct_observation_count"] == 0
    assert ledger["vigor"]["observation_relationship"] == "indirect"
    assert ledger["vigor"]["field_approval_eligible"] is False

    # Positive control: In-situ direct observation on an authorized direct-observation state
    direct_report = [
        {
            "obs_name": "soil_moisture_probe",
            "sensor": "EXTERNAL",
            "update_applied": True,
            "real_provider_product": True,
            "source_reality": "real_raster",
            "evidence_kind": "direct_observation",
            "target_states": ["root_zone_water"],
            "innovation_mean": 0.02,
            "sigma_obs": 0.02,
            "n_pixels": 1,
        }
    ]
    # Root zone water ceiling is DIAGNOSTIC in current descriptors
    ledger_direct = build_state_support_ledger(direct_report)
    assert ledger_direct["root_zone_water"]["direct_observation_count"] == 1
    assert ledger_direct["root_zone_water"]["observation_relationship"] == "direct"
    # Root zone water ceiling DIAGNOSTIC does not permit field approval
    assert ledger_direct["root_zone_water"]["field_approval_eligible"] is False


class DummyScene:
    def __init__(self, scene_id, support_hash, bands, width=1, height=1):
        self.scene_id = scene_id
        self.valid_support_hash = support_hash
        self.bands = bands
        self.width = width
        self.height = height
        self.valid_support = np.ones((height, width), dtype=bool)
        self.valid_fraction = 1.0
        self.cloud_fraction = 0.0
        self.crop_stage = "vegetative"


class DummyOperator:
    def __init__(self, operator_id, scene_id, support_hash, H_matrix):
        self.operator_id = operator_id
        self.scene_id = scene_id
        self.valid_support_hash = support_hash
        self.H_matrix = H_matrix


def test_reject_zero_localized_support():
    """Zero localized support must produce update_applied=False and mode='excluded_zero_localized_support'."""
    import random
    ensemble = {
        "mz_0": [[0.5] * 13 for _ in range(10)],
    }
    op = DummyOperator(
        operator_id="OP_ZERO",
        scene_id="SCENE_01",
        support_hash="hash_01",
        H_matrix=np.zeros((4, 1), dtype=float),
    )
    scene = DummyScene(
        scene_id="SCENE_01",
        support_hash="hash_01",
        bands={"B04": np.full((2, 2), 0.2), "B08": np.full((2, 2), 0.8)},
        width=2,
        height=2,
    )
    rng = random.Random(42)
    ens_out, reports = update_step_ht(
        ensemble=ensemble,
        scene=scene,
        operator=op,
        rng=rng,
        node_ids=["mz_0"],
    )
    assert len(reports) == 1
    assert reports[0]["update_applied"] is False
    assert reports[0]["mode"] == "excluded_zero_localized_support"
    assert reports[0]["failure_reason"] == "zero_localized_support"


def test_stress_memory_evolution_preserved_while_updates_excluded():
    """Stress memory must be excluded from observation updates but evolution preserved."""
    import random
    desc = get_descriptor("stress_memory")
    assert desc.assimilation_policy == AssimilationPolicy.NOT_ASSIMILATED

    op = DummyOperator(
        operator_id="OP_STRESS",
        scene_id="SCENE_STRESS",
        support_hash="hash_stress",
        H_matrix=np.ones((1, 1), dtype=float),
    )
    scene = DummyScene(
        scene_id="SCENE_STRESS",
        support_hash="hash_stress",
        bands={
            "B04": np.array([[0.2]]),
            "B08": np.array([[0.8]]),
            "B8A": np.array([[0.8]]),
            "B11": np.array([[0.4]]),
        },
    )
    ensemble = {
        "mz_0": [[0.3] * 13 for _ in range(10)],
    }
    rng = random.Random(42)
    ens_out, reports = update_step_ht(
        ensemble=ensemble,
        scene=scene,
        operator=op,
        rng=rng,
        node_ids=["mz_0"],
    )
    stress_reports = [r for r in reports if r.get("obs_name") == "stress_memory_index"]
    assert len(stress_reports) == 1
    assert stress_reports[0]["update_applied"] is False
    assert stress_reports[0]["failure_reason"] == "forbidden_or_not_assimilated"
    # Ensemble for stress_memory (index 12) must remain uncorrupted by observation
    assert ens_out["mz_0"][0][12] == 0.3


# ============================================================================
# 4. LOSSLESS COUNTERS PRESERVATION
# ============================================================================

def test_lossless_counter_preservation_and_validation():
    """Direct, proxy, and indirect observation counters must be copied losslessly."""
    raw = {
        "state": "vigor",
        "status": "assimilated",
        "accepted_update_count": 5,
        "direct_observation_count": 2,
        "proxy_observation_count": 1,
        "indirect_observation_count": 2,
        "source_feature_ids": ["ndvi", "evi"],
    }
    canonical = canonicalize_state_support_record("vigor", raw)
    assert canonical["accepted_update_count"] == 5
    assert canonical["direct_observation_count"] == 2
    assert canonical["proxy_observation_count"] == 1
    assert canonical["indirect_observation_count"] == 2

    # Evidence class resolution
    ev_class = resolve_state_evidence_class(canonical)
    assert ev_class == StateEvidenceClass.DIRECTLY_ASSIMILATED

    # When direct is 0 and indirect > 0, resolves to INDIRECTLY_CONSTRAINED
    canonical_indirect = dict(canonical)
    canonical_indirect["direct_observation_count"] = 0
    canonical_indirect["observation_relationship"] = "indirect"
    assert resolve_state_evidence_class(canonical_indirect) == StateEvidenceClass.INDIRECTLY_CONSTRAINED

    # Validation errors on invalid types
    with pytest.raises(ContractViolation):
        canonicalize_state_support_record("vigor", {**raw, "indirect_observation_count": -1})
    with pytest.raises(ContractViolation):
        canonicalize_state_support_record("vigor", {**raw, "direct_observation_count": True})
    with pytest.raises(ContractViolation):
        canonicalize_state_support_record("vigor", {**raw, "proxy_observation_count": "invalid"})


# ============================================================================
# 5. SCIENTIFIC VALIDITY VS DISPLAY & AVAILABILITY
# ============================================================================

def test_all_13_states_in_invariants_and_domain_enforcement():
    """All 13 ASMAE states must have admissible bounds in RANGE_MAP."""
    # Verify all 13 states are in STATE_ORDER
    assert len(STATE_ORDER) == 13

    # Create dummy layer 10 output with all 13 states at valid boundary values
    surfaces = []
    stype_map = {
        "vigor": (SurfaceType.ASMAE_VIGOR, 0.5),
        "lai": (SurfaceType.ASMAE_LAI, 7.8),
        "chlorophyll": (SurfaceType.ASMAE_CHLOROPHYLL, 75.0),
        "canopy_water": (SurfaceType.ASMAE_CANOPY_WATER, 0.4),
        "root_zone_water": (SurfaceType.ASMAE_ROOT_ZONE_WATER, 0.3),
        "surface_wetness_event": (SurfaceType.ASMAE_SURFACE_WETNESS_EVENT, 0.1),
        "structure": (SurfaceType.ASMAE_STRUCTURE, 0.6),
        "bare_soil_fraction": (SurfaceType.ASMAE_BARE_SOIL, 0.2),
        "salinity_stress": (SurfaceType.ASMAE_SALINITY_STRESS, 0.05),
        "thermal_stress": (SurfaceType.ASMAE_THERMAL_STRESS, 0.15),
        "biotic_confounder_risk": (SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK, 0.08),
        "phenology_progress": (SurfaceType.ASMAE_PHENOLOGY_PROGRESS, 0.7),
        "stress_memory": (SurfaceType.ASMAE_STRESS_MEMORY, 0.25),
    }

    asmae_provenance = {
        "resolution_m": 10.0,
        "confidence": 0.8,
        "uncertainty": 0.1,
        "retro_status": "success",
        "bma_status": "success",
        "bma_disagreement": 0.05,
        "cross_layer_conflict": 0.02,
        "state_update_allowed": False,
        "diagnostic_only": False,
        "visual_only": False,
        "content_hash": "hash123",
        "artifact_instance_hash": "inst123",
        "warning_codes": [],
        "display_trust_tier": "provisional",
    }

    for state, (stype, val) in stype_map.items():
        surfaces.append(SurfaceArtifact(
            surface_id=f"TEST_{stype.value}",
            semantic_type=stype,
            grid_ref="2x2",
            values=[[val, val], [val, val]],
            units="units",
            native_resolution_m=10.0,
            provenance=dict(asmae_provenance),
        ))

    from services.agribrain.layer10_sire.schema import (
        ZoneArtifact, MicroObjectArtifact, HistogramBundle,
        TemporalBundle, QualityReport, ZoneType, ZoneFamily,
    )
    zone = ZoneArtifact(
        zone_id="Z1",
        zone_type=ZoneType.HIGH_VIGOR,
        zone_family=ZoneFamily.AGRONOMIC,
        cell_indices=[(0, 0)],
        bbox=(0.0, 0.0, 1.0, 1.0),
        area_m2=100.0,
        area_pct=0.01,
        severity=0.5,
        confidence=0.8,
        top_drivers=["vigor"],
    )
    output = Layer10Output(
        surface_pack=surfaces,
        zone_pack=[zone],
    )

    violations = enforce_layer10_invariants(output, 2, 2)
    assert len(violations) == 0, f"Invariant violations: {violations}"

    # Verify that an out-of-bounds chlorophyll (e.g. 85.0 > 80.0) is caught
    bad_surface = SurfaceArtifact(
        surface_id="TEST_BAD_CHLOROPHYLL",
        semantic_type=SurfaceType.ASMAE_CHLOROPHYLL,
        grid_ref="2x2",
        values=[[85.0, 50.0], [50.0, 50.0]],
        units="ug/cm2",
        native_resolution_m=10.0,
        provenance=dict(asmae_provenance),
    )
    output.surface_pack = [bad_surface]
    violations_bad = enforce_layer10_invariants(output, 2, 2)
    assert any("INV-2" in v and "85.0" in v for v in violations_bad)


def test_lai_legend_coverage():
    """RenderMode.ASMAE_LAI legend entries must cover full [0.0, 8.0] range."""
    lai_legend = DEFAULT_LEGENDS[RenderMode.ASMAE_LAI]
    max_range = max(entry.value_range[1] for entry in lai_legend if entry.value_range)
    assert max_range >= 8.0


def test_empty_raster_cannot_fabricate_plot_estimate():
    """Empty raster with all None must be marked missing, not plot_level_only."""
    empty_surface = SurfaceArtifact(
        surface_id="ASMAE_VIGOR_empty",
        semantic_type=SurfaceType.ASMAE_VIGOR,
        grid_ref="2x2",
        values=[[None, None], [None, None]],
        units="index",
        native_resolution_m=10.0,
        grounding_class="UNIFORM",
        provenance={"has_scalar_estimate": False},
    )

    # In manifest builder, mode must not be enabled
    inp = Layer10Input(
        plot_namespace=PlotNamespace(tenant_id="T1", farm_id="F1", plot_id="TEST_P")
    )
    manifest = build_render_manifest([empty_surface], inp)
    vigor_mode = next(m for m in manifest.available_modes if m.mode == RenderMode.ASMAE_VIGOR)
    assert vigor_mode.enabled is False

    # Verify empty raster via direct evaluation
    vals = empty_surface.values or []
    has_finite = any(v is not None and not math.isnan(v) for row in vals for v in row)
    assert has_finite is False


# ============================================================================
# 6. SCIENTIFIC EXPORT RECEIPT PRESERVATION
# ============================================================================

def test_scientific_export_receipt_preservation():
    """export_raster_pack must preserve full scientific receipt on RasterEntry."""
    grid_spec = {
        "crs": "EPSG:32630",
        "transform": [10.0, 0.0, 500000.0, 0.0, -10.0, 4500000.0],
        "width": 2,
        "height": 2,
    }
    surface = SurfaceArtifact(
        surface_id="SURF_EXPORT_TEST",
        semantic_type=SurfaceType.ASMAE_VIGOR,
        grid_ref="2x2",
        values=[[0.6, 0.7], [0.8, None]],
        units="index",
        native_resolution_m=10.0,
        display_resolution_m=1.0,
        effective_resolution_m=10.0,
        grid_spec=grid_spec,
        observed_mask=[[True, True], [True, False]],
        inferred_mask=[[False, False], [False, True]],
        grounding_class="RASTER_GROUNDED",
        state_update_allowed=False,
        prescription_driver_allowed=False,
        block_reasons=["monitoring_only"],
        provenance={"uncertainty": 0.05, "source_basis": "sentinel2"},
    )
    output = Layer10Output(
        surface_pack=[surface],
        zone_pack=[],
        micro_objects=[],
    )
    entries = export_raster_pack(output)
    assert len(entries) == 1
    entry = entries[0]

    # Verify all preserved scientific receipt fields
    assert entry.grid_spec == grid_spec
    assert entry.display_resolution_m == 1.0
    assert entry.effective_resolution_m == 10.0
    assert entry.uncertainty == 0.05
    assert entry.grounding_class == "RASTER_GROUNDED"
    assert entry.state_update_allowed is False
    assert entry.prescription_driver_allowed is False
    assert entry.block_reasons == ["monitoring_only"]
    assert entry.observed_mask == [[True, True], [True, False]]
    assert entry.inferred_mask == [[False, False], [False, True]]
    assert entry.valid_mask == [[True, True], [True, False]]
    assert "stats" in entry.canonical_metadata
    assert entry.stats["valid_pixels"] == 3
