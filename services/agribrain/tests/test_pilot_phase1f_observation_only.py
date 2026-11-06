"""Phase 1F fail-closed observation-only readout contracts.

The store stub is intentional: these tests prove the no-authority and
native-reader wiring, NOT independently sourced Plot A field provenance.
Run: py -m pytest -q services/agribrain/tests/test_pilot_phase1f_observation_only.py
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer05_asmae import plot_snapshot_store
from services.agribrain.orchestrator_v2.pilot_observation_only_gate import (
    read_observation_only_pilot_status,
    require_observation_only_runtime,
)
from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.scientific_contracts.prescription_authorization import (
    CANONICAL_PUBLICATION_VALIDATION_FLAGS,
)

NOW = datetime(2026, 11, 6, 14, tzinfo=timezone.utc)
NAMESPACE = PlotNamespace(
    tenant_id="6aa9a259c805efbecad312f6",
    farm_id="6aa9a259c805efbecad312f7",
    plot_id="6ab14f59ad442f274c3f2a62",
)
SNAPSHOT = "ASMAE-SNAPSHOT-6f-observation-fixture"
GEOMETRY = "a" * 64
CYCLE = "winter-wheat-2026"


def _publication(**overrides):
    source = {
        "snapshot_kind": "asmae",
        "tenant_id": NAMESPACE.tenant_id,
        "farm_id": NAMESPACE.farm_id,
        "plot_id": NAMESPACE.plot_id,
        "geometry_hash": GEOMETRY,
        "crop_cycle_id": CYCLE,
        "snapshot_id": SNAPSHOT,
        "publication_receipt_hash": "b" * 64,
        "manifest_hash": "c" * 64,
        "observation_window": {
            "start": "2026-11-01T00:00:00Z",
            "end": "2026-11-04T12:00:00Z",
        },
        "evidence_cutoff_at": "2026-11-04T13:00:00Z",
        "published_at": "2026-11-05T12:00:00Z",
        "validation": {k: True for k in CANONICAL_PUBLICATION_VALIDATION_FLAGS},
        "proof_attestation_valid": None,
    }
    return {**source, **overrides}


def _read(monkeypatch, source=None, at=NOW):
    monkeypatch.setenv("AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION", "false")
    monkeypatch.setattr(
        plot_snapshot_store, "load_latest_plot_snapshot",
        lambda _scope: source if source is not None else _publication(),
    )
    return read_observation_only_pilot_status(
        NAMESPACE, expected_snapshot_id=SNAPSHOT,
        expected_geometry_hash=GEOMETRY,
        expected_crop_cycle_id=CYCLE, now=at,
    )


def test_current_observation_projection_has_no_action_or_scientific_authority(monkeypatch):
    result = _read(monkeypatch)
    assert result["status"] == "OBSERVATION_ONLY_READABLE"
    assert result["publication_integrity_checked"] is True
    assert result["publication_validation_flags_checked"] == 10
    assert result["snapshot_id"] == SNAPSHOT
    assert result["observation_window"]["start"] == "2026-11-01T00:00:00Z"
    assert result["recommendations"] == []
    assert result["actions"] == []
    for name in (
        "signed_irrigation_enabled", "actuator_control_authorized",
        "machine_execution_allowed", "scientific_publication_authorized",
        "independent_field_accuracy_verified",
        "live_sensor_to_asmae_chain_verified",
        "real_time_observation_claim",
    ):
        assert result[name] is False
    assert "proof_attestation" not in result
    assert "authorization_envelope" not in result
    assert "signing_key" not in result
    assert "payload" not in result


@pytest.mark.parametrize("value", ["true", "1", "YES", "invalid", "on"])
def test_signed_irrigation_flag_blocks_before_any_publication_read(monkeypatch, value):
    monkeypatch.setenv("AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION", value)
    def forbidden(_scope):
        pytest.fail("No canonical store read allowed while L3 is enabled")
    monkeypatch.setattr(plot_snapshot_store, "load_latest_plot_snapshot", forbidden)
    with pytest.raises(ContractViolation, match="observation_only_pilot_requires_signed_irrigation_disabled"):
        read_observation_only_pilot_status(
            NAMESPACE, expected_snapshot_id=SNAPSHOT,
            expected_geometry_hash=GEOMETRY,
            expected_crop_cycle_id=CYCLE, now=NOW,
        )


def test_no_flag_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION", raising=False)
    require_observation_only_runtime()


@pytest.mark.parametrize("delta", [
    {"plot_id": "different-plot"},
    {"tenant_id": "other-tenant"},
    {"geometry_hash": "d"*64},
    {"snapshot_id": "ASMAE-SNAPSHOT-other"},
    {"crop_cycle_id": "another-cycle"},
])
def test_current_reader_rejects_wrong_scope_and_identity(monkeypatch, delta):
    with pytest.raises(ContractViolation):
        _read(monkeypatch, _publication(**delta))


def test_reader_rejects_invalid_cryptographic_validation_flags(monkeypatch):
    flags = {k: True for k in CANONICAL_PUBLICATION_VALIDATION_FLAGS}
    flags["receiptValid"] = False
    with pytest.raises(ContractViolation, match="not fully integrity-validated"):
        _read(monkeypatch, _publication(validation=flags))


def test_stale_snapshot_remains_readable_but_never_current(monkeypatch):
    stale = _read(monkeypatch, _publication(
        observation_window={
            "start": "2026-09-25T00:00:00Z",
            "end": "2026-09-30T12:00:00Z",
        },
        evidence_cutoff_at="2026-09-30T13:00:00Z",
        published_at="2026-10-01T12:00:00Z",
    ))
    assert stale["status"] == "STALE_OBSERVATION_ONLY"
    assert stale["machine_execution_allowed"] is False


def test_future_published_snapshot_rejected(monkeypatch):
    with pytest.raises(ContractViolation, match="observation_publication_from_future"):
        _read(monkeypatch, _publication(published_at="2026-11-08T12:00:00Z"))


def test_naive_evaluation_time_rejected(monkeypatch):
    with pytest.raises(ContractViolation, match="evaluation_time_not_utc_aware"):
        _read(monkeypatch, _publication(), datetime(2026, 11, 6, 14))


def test_missing_canonical_head_rejected(monkeypatch):
    monkeypatch.setenv("AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION", "false")
    monkeypatch.setattr(
        plot_snapshot_store, "load_latest_plot_snapshot", lambda _scope: None,
    )
    with pytest.raises(ContractViolation, match="unavailable"):
        read_observation_only_pilot_status(
            NAMESPACE, expected_snapshot_id=SNAPSHOT,
            expected_geometry_hash=GEOMETRY,
            expected_crop_cycle_id=CYCLE, now=NOW,
        )
