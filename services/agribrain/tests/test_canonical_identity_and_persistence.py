"""
Tests for WP03: Canonical Identity and Persistence.

Covers:
1. Strict Scientific Run ID Derivation (determinism, sensitivity, intent binding, missing evidence markers)
2. Canonical Worldline Persistence (atomic writes, corruption detection, path containment security)
3. Layer 1 Evidence Ledger (superseding lineage, index integrity, audit preservation)
"""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from services.agribrain.orchestrator_v2.hashing import (
    generate_orchestrator_run_id,
    generate_scientific_run_id,
)
from services.agribrain.orchestrator_v2.schema import OrchestratorInput
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
    CorruptedWorldlineError,
    SecurityViolation,
    WorldlineEventProposal,
)
from services.agribrain.layer1_fusion.schemas import EvidenceItem
from services.agribrain.layer1_fusion.evidence_ledger import EvidenceLedger


# ============================================================================
# 1. Scientific Run ID Derivation & Hashing Tests
# ============================================================================

def _make_sample_input(**kwargs) -> OrchestratorInput:
    base = {
        "plot_id": "plot_test_100",
        "tenant_id": "tenant_test",
        "farm_id": "farm_test",
        "geometry_hash": "geo_hash_abc123",
        "date_range": {"start": "2026-06-01", "end": "2026-06-15"},
        "crop_config": {"crop_type": "wheat", "sowing_date": "2025-11-15"},
        "weather_set_hash": "weather_hash_v1",
        "scene_manifest_hash": "scene_hash_v1",
        "evidence_set_hash": "evidence_hash_v1",
        "worldline_head_hash": "head_hash_v1",
    }
    base.update(kwargs)
    return OrchestratorInput(**base)


def test_run_id_determinism():
    inp1 = _make_sample_input()
    inp2 = _make_sample_input()
    layer_versions = {"L1": "1.0", "L2": "1.0"}

    id1 = generate_orchestrator_run_id(inp1, layer_versions, "2.0", intent="DECISION", seed=42)
    id2 = generate_orchestrator_run_id(inp2, layer_versions, "2.0", intent="DECISION", seed=42)

    assert id1.startswith("AGB2-")
    assert id1 == id2
    assert generate_scientific_run_id == generate_orchestrator_run_id


def test_run_id_sensitivity_to_intent():
    inp = _make_sample_input()
    layer_versions = {"L1": "1.0", "L2": "1.0"}

    id_decision = generate_orchestrator_run_id(inp, layer_versions, "2.0", intent="DECISION")
    id_diagnosis = generate_orchestrator_run_id(inp, layer_versions, "2.0", intent="DIAGNOSIS")
    id_planning = generate_orchestrator_run_id(inp, layer_versions, "2.0", intent="PLANNING")

    assert id_decision != id_diagnosis
    assert id_diagnosis != id_planning
    assert id_decision != id_planning


def test_run_id_sensitivity_to_weather_and_scenes():
    inp_base = _make_sample_input(weather_set_hash="weather_hash_a")
    inp_weather_changed = _make_sample_input(weather_set_hash="weather_hash_b")
    inp_scene_changed = _make_sample_input(
        weather_set_hash="weather_hash_a", scene_manifest_hash="scene_hash_diff"
    )

    layer_versions = {"L1": "1.0"}
    id_base = generate_orchestrator_run_id(inp_base, layer_versions, "2.0")
    id_weather = generate_orchestrator_run_id(inp_weather_changed, layer_versions, "2.0")
    id_scene = generate_orchestrator_run_id(inp_scene_changed, layer_versions, "2.0")

    assert id_base != id_weather
    assert id_base != id_scene


def test_run_id_missing_evidence_markers():
    inp_missing_weather = _make_sample_input(weather_set_hash=None)
    inp_with_weather = _make_sample_input(weather_set_hash="actual_weather_hash")

    layer_versions = {"L1": "1.0"}
    id_missing = generate_orchestrator_run_id(inp_missing_weather, layer_versions, "2.0")
    id_present = generate_orchestrator_run_id(inp_with_weather, layer_versions, "2.0")

    assert id_missing != id_present


# ============================================================================
# 2. Canonical Worldline Persistence & Security Tests
# ============================================================================

def test_canonical_worldline_path_containment(tmp_path: Path):
    service = CanonicalWorldlineService(root=tmp_path)

    # Valid tenant and namespace
    plot_dir = service._plot_dir("plot_01", tenant_id="tenant_a", namespace="default")
    assert plot_dir.is_relative_to(tmp_path.resolve())

    # Traversal attempts must raise SecurityViolation
    with pytest.raises(SecurityViolation):
        service._plot_dir("plot_01", tenant_id="../escape", namespace="default")

    with pytest.raises(SecurityViolation):
        service._plot_dir("plot_01", tenant_id="tenant_a", namespace="../../etc")

    with pytest.raises(SecurityViolation):
        service._plot_dir("plot_01", tenant_id="tenant/sub", namespace="default")


def test_canonical_worldline_read_clean_initial_state(tmp_path: Path):
    service = CanonicalWorldlineService(root=tmp_path)
    head_path = tmp_path / "tenant_a" / "default" / "plot_01" / "head.json"

    # Does not exist yet -> returns empty dict
    assert service._read(head_path) == {}


def test_canonical_worldline_detects_file_corruption(tmp_path: Path):
    service = CanonicalWorldlineService(root=tmp_path)
    target_dir = tmp_path / "tenant_a" / "default" / "plot_01"
    target_dir.mkdir(parents=True, exist_ok=True)
    head_path = target_dir / "head.json"

    # Truncated or invalid JSON
    head_path.write_text("{\"seq\": 1, \"event_id\": ", encoding="utf-8")
    with pytest.raises(CorruptedWorldlineError):
        service._read(head_path)

    # Empty file
    head_path.write_text("", encoding="utf-8")
    with pytest.raises(CorruptedWorldlineError):
        service._read(head_path)

    # Non-dict JSON (e.g. array)
    head_path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(CorruptedWorldlineError):
        service._read(head_path)


def test_canonical_worldline_roundtrip_publication(tmp_path: Path):
    service = CanonicalWorldlineService(root=tmp_path)
    plot_id = "plot_persist_test"

    proposal = WorldlineEventProposal(
        event_type="OBSERVATION",
        payload={"soil_moisture": 0.28, "ndvi": 0.65},
        geometry_version="geo_v1",
        evidence_set_hash="ev_hash_1",
        model_version="model_v1",
        authority_ref="MEASURED",
        observation_or_valid_time="2026-06-10T12:00:00Z",
    )

    event = service.commit_proposal(
        plot_id=plot_id,
        proposal=proposal,
        tenant_id="tenant_a",
        namespace="default",
        effective_at="2026-06-10T12:00:00Z",
    )

    assert event["sequence"] == 1
    head = service.load_head(plot_id=plot_id, tenant_id="tenant_a", namespace="default")
    assert head is not None
    assert head["sequence"] == 1
    assert head["latest_event_id"] == event["event_id"]


# ============================================================================
# 3. Layer 1 Evidence Ledger Superseding & Immutability Tests
# ============================================================================

def test_evidence_ledger_superseding_and_index_integrity():
    ledger = EvidenceLedger()

    item1 = EvidenceItem(
        evidence_id="ev_raw_001",
        plot_id="plot_01",
        variable="ndvi",
        value=0.62,
        source_family="sentinel2",
        source_id="s2_l2a",
        observation_type="measurement",
        spatial_scope="plot",
        confidence=0.8,
        reliability=0.85,
    )

    violations = ledger.add(item1)
    assert violations == []
    assert ledger.count == 1
    assert ledger.by_variable("ndvi") == [item1]
    assert ledger.by_source("sentinel2") == [item1]
    assert ledger.by_scope("plot") == [item1]

    # Supersede item1 with calibrated item2
    item2 = EvidenceItem(
        evidence_id="ev_calibrated_002",
        plot_id="plot_01",
        variable="ndvi",
        value=0.68,
        source_family="sentinel2",
        source_id="s2_l2a",
        observation_type="measurement",
        spatial_scope="plot",
        confidence=0.95,
        reliability=0.90,
        supersedes_evidence_id="ev_raw_001",
    )

    update_violations = ledger.update_item(item2)
    assert update_violations == []

    # Active items reflect item2 only
    assert ledger.count == 1
    assert ledger.all_items == [item2]
    assert ledger.by_variable("ndvi") == [item2]
    assert ledger.by_source("sentinel2") == [item2]
    assert ledger.by_scope("plot") == [item2]

    # Audit history preserves superseded item1
    assert ledger.superseded_items == [item1]
    assert ledger.get_by_id("ev_raw_001") == item1
    assert ledger.get_by_id("ev_calibrated_002") == item2


def test_evidence_ledger_rejects_invalid_supersede():
    ledger = EvidenceLedger()

    item_orphan = EvidenceItem(
        evidence_id="ev_orphan_001",
        plot_id="plot_01",
        variable="ndvi",
        value=0.70,
        source_family="sentinel2",
        source_id="s2_l2a",
        observation_type="measurement",
        spatial_scope="plot",
        supersedes_evidence_id="non_existent_id",
    )

    violations = ledger.update_item(item_orphan)
    assert any("not found" in v for v in violations)
    assert ledger.count == 0
