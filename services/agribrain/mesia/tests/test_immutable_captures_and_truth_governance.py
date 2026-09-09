"""Tests for Work Package 06: Rebuild MESIA Ingestion Around Immutable Captures.

Verifies:
1. Atomic SigMF capture manifests binding binary data & metadata via identical SHA-256 ID.
2. Strict prohibition of synthetic timestamping; missing metadata triggers QuarantinedCaptureException.
3. Cryptographic qualification signature validation rejects empty/whitespace strings.
4. Tenant/plot namespace isolation and path traversal prevention.
5. Strict truth-tier separation between native RF waveform captures and derived biological inferences.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import pytest

from services.agribrain.mesia.contracts.capture_manifest import (
    QuarantinedCaptureException,
    RadioProfile,
    SigMFCaptureManifest,
)
from services.agribrain.mesia.contracts.truth_hierarchy import (
    TruthClass,
    TruthTier,
    classify_proposal_truth,
)
from services.agribrain.mesia.ingestion.sigmf_ingest import (
    ingest_sigmf_capture,
    parse_capture_timestamp,
    verify_capture_integrity,
)
from services.agribrain.mesia.lanes.wifi.csi_extractor import NativeWifiCsiExtractor
from services.agribrain.mesia.lanes.wifi_csi_lane import WifiCsiLaneAdapter
from services.agribrain.mesia.assimilation.capability_governance import (
    CapabilityGovernanceAuthority,
)


# ---------------------------------------------------------------------------
# 1. Finding #17: Atomic SigMF Capture Manifests & Integrity
# ---------------------------------------------------------------------------

def test_atomic_sigmf_ingestion_and_manifest_binding(tmp_path: Path):
    """Verify atomic ingestion creates content-addressed .sigmf-data and .sigmf-meta."""
    tenant_id = "tenant_alpha"
    plot_id = "plot_olive_01"
    raw_bytes = b"\x00\x01\x02\x03\x04\x05\x06\x07" * 32  # 256 bytes

    meta = {
        "global": {
            "core:datatype": "cf32_le",
            "core:sample_rate": 20.0e6,
            "core:hw": "iwlwifi_test",
        },
        "captures": [
            {
                "core:sample_start": 0,
                "core:frequency": 2.437e9,
                "core:datetime": "2026-05-10T14:30:00+00:00",
            }
        ],
        "annotations": [
            {
                "core:sample_start": 0,
                "core:sample_count": 32,
                "mesia:agc_gain_db": 28.5,
            }
        ],
    }

    manifest = ingest_sigmf_capture(
        tenant_id=tenant_id,
        plot_id=plot_id,
        raw_data_bytes=raw_bytes,
        metadata_dict=meta,
        storage_root=tmp_path,
    )

    assert isinstance(manifest, SigMFCaptureManifest)
    assert manifest.tenant_id == tenant_id
    assert manifest.plot_id == plot_id
    assert manifest.capture_timestamp_utc == datetime(2026, 5, 10, 14, 30, 0, tzinfo=timezone.utc)
    assert len(manifest.capture_id) == 64

    # Both files must exist under the scoped path
    data_path = Path(manifest.data_path)
    meta_path = Path(manifest.meta_path)
    assert data_path.exists()
    assert meta_path.exists()
    assert data_path.name == f"{manifest.capture_id}.sigmf-data"
    assert meta_path.name == f"{manifest.capture_id}.sigmf-meta"

    # Integrity verification
    assert verify_capture_integrity(manifest) is True

    # Tamper detection
    data_path.write_bytes(b"tampered_data")
    assert verify_capture_integrity(manifest) is False


# ---------------------------------------------------------------------------
# 2. Finding #17: Zero Synthetic Timestamps & Fail-Closed Quarantine
# ---------------------------------------------------------------------------

def test_missing_timestamp_quarantines_ingestion(tmp_path: Path):
    """Verify that captures missing timestamps raise QuarantinedCaptureException."""
    raw_bytes = b"sample_bytes_12345678"
    meta_no_ts = {
        "global": {"core:datatype": "cf32_le", "core:sample_rate": 20.0e6},
        "captures": [{"core:sample_start": 0, "core:frequency": 2.437e9}],  # No datetime!
    }

    with pytest.raises(QuarantinedCaptureException, match="Missing capture timestamp"):
        ingest_sigmf_capture(
            tenant_id="tenant_a",
            plot_id="plot_b",
            raw_data_bytes=raw_bytes,
            metadata_dict=meta_no_ts,
            storage_root=tmp_path,
        )


def test_reader_rejects_unaccompanied_sigmf_data(tmp_path: Path):
    """Verify NativeWifiCsiExtractor.read_sigmf fails closed when .sigmf-meta is missing."""
    orphaned_data = tmp_path / "orphan_capture.sigmf-data"
    orphaned_data.write_bytes(b"\x00" * 64)

    # Must raise QuarantinedCaptureException rather than defaulting to datetime.now()
    with pytest.raises(QuarantinedCaptureException, match="SigMF metadata missing"):
        NativeWifiCsiExtractor.read_sigmf(str(orphaned_data))


def test_wifi_lane_adapter_rejects_missing_timestamp():
    """Verify WifiCsiLaneAdapter.from_sigmf_dict never falls back to datetime.now()."""
    with pytest.raises(QuarantinedCaptureException, match="Missing capture timestamp"):
        WifiCsiLaneAdapter.from_sigmf_dict({"center_frequency_hz": 2.4e9})


# ---------------------------------------------------------------------------
# 3. Finding #18: Cryptographic Qualification Signature Hardening
# ---------------------------------------------------------------------------

def test_capability_governance_rejects_superficial_signature():
    """Verify CapabilityGovernanceAuthority rejects empty string or whitespace signatures."""
    all_gates = {
        "gate_repeatability_passed": True,
        "gate_sensitivity_passed": True,
        "gate_specificity_passed": True,
        "gate_observability_passed": True,
        "gate_transfer_passed": True,
        "gate_closure_passed": True,
        "gate_incremental_value_passed": True,
        "gate_governance_passed": True,
    }

    # Empty string signature must NOT qualify
    rec_empty = CapabilityGovernanceAuthority.issue_qualification_record(
        capability_id="cap-001",
        capability_name="WiFi Canopy Moisture",
        target_variable="canopy_water",
        supported_radios=["WIFI_CSI"],
        supported_soils=["SANDY_LOAM"],
        supported_crops=["OLIVE"],
        validation_signature="",  # Empty string
        **all_gates,
    )
    assert rec_empty.state == "UNQUALIFIED_PENDING_EVIDENCE"

    # Whitespace-only signature must NOT qualify
    rec_ws = CapabilityGovernanceAuthority.issue_qualification_record(
        capability_id="cap-002",
        capability_name="WiFi Canopy Moisture",
        target_variable="canopy_water",
        supported_radios=["WIFI_CSI"],
        supported_soils=["SANDY_LOAM"],
        supported_crops=["OLIVE"],
        validation_signature="   \t\n   ",
        **all_gates,
    )
    assert rec_ws.state == "UNQUALIFIED_PENDING_EVIDENCE"

    # Short trivial signature must NOT qualify (<16 chars)
    rec_short = CapabilityGovernanceAuthority.issue_qualification_record(
        capability_id="cap-003",
        capability_name="WiFi Canopy Moisture",
        target_variable="canopy_water",
        supported_radios=["WIFI_CSI"],
        supported_soils=["SANDY_LOAM"],
        supported_crops=["OLIVE"],
        validation_signature="short_sig",
        **all_gates,
    )
    assert rec_short.state == "UNQUALIFIED_PENDING_EVIDENCE"

    # Genuine signature (>= 16 chars) qualifies
    rec_valid = CapabilityGovernanceAuthority.issue_qualification_record(
        capability_id="cap-004",
        capability_name="WiFi Canopy Moisture",
        target_variable="canopy_water",
        supported_radios=["WIFI_CSI"],
        supported_soils=["SANDY_LOAM"],
        supported_crops=["OLIVE"],
        validation_signature="SIG_AUDIT_APPROVED_2026_RSA_SHA256",
        **all_gates,
    )
    assert rec_valid.state == "QUALIFIED"


# ---------------------------------------------------------------------------
# 4. Finding #21: Namespace Isolation & Path Traversal Protection
# ---------------------------------------------------------------------------

def test_namespace_isolation_and_path_traversal_blocked(tmp_path: Path):
    """Verify path traversal characters in tenant or plot ID are rejected."""
    raw_bytes = b"valid_data"
    meta = {
        "global": {"core:datatype": "cf32_le", "core:sample_rate": 20.0e6},
        "captures": [{"core:sample_start": 0, "core:frequency": 2.4e9, "core:datetime": "2026-06-01T00:00:00Z"}],
    }

    with pytest.raises(ValueError, match="forbidden path traversal"):
        ingest_sigmf_capture("../tenant_malicious", "plot_01", raw_bytes, meta, storage_root=tmp_path)

    with pytest.raises(ValueError, match="forbidden path traversal"):
        ingest_sigmf_capture("tenant_01", "../../etc/passwd", raw_bytes, meta, storage_root=tmp_path)


# ---------------------------------------------------------------------------
# 5. Finding #16: Truth Hierarchy & Proposal Classification
# ---------------------------------------------------------------------------

def test_truth_tier_and_epistemic_classification():
    """Verify biological proposals are classified as BIOLOGICAL_INFERENCE and DERIVED_MODEL_INFERRED."""
    # Biological feature with real in-situ radio
    bio_res = classify_proposal_truth("mesia_wifi_csi_canopy_foliar", has_real_sensor=True)
    assert bio_res["truth_tier"] == TruthTier.BIOLOGICAL_INFERENCE.value
    assert bio_res["truth_class"] == TruthClass.DERIVED_MODEL_INFERRED.value
    assert bio_res["is_derived_model_inference"] is True

    # Biological feature without real in-situ radio
    sim_res = classify_proposal_truth("mesia_wifi_csi_canopy_foliar", has_real_sensor=False)
    assert sim_res["truth_tier"] == TruthTier.ASMAE_INNOVATION_PROPOSAL.value
    assert sim_res["truth_class"] == TruthClass.SIMULATED.value
    assert sim_res["is_derived_model_inference"] is True

    # Pure physical RF metric
    rf_res = classify_proposal_truth("mesia_wifi_csi_raw_phase_variance", has_real_sensor=True)
    assert rf_res["truth_tier"] == TruthTier.NATIVE_RF_CAPTURE.value
    assert rf_res["truth_class"] == TruthClass.MEASURED_NATIVE.value
    assert rf_res["is_derived_model_inference"] is False
