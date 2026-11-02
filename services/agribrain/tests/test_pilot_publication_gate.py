"""Scientific pilot current-head read and negative issuer preflight gates.

Exercises genuine source gate functions with a patched snapshot-store return.
No publication, signature, permission promotion or real run is performed.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.orchestrator_v2.pilot_publication_gate import (
    preflight_pilot_issuer, read_trusted_current_asmae_publication,
)
from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.scientific_contracts.prescription_authorization import (
    CANONICAL_PUBLICATION_VALIDATION_FLAGS, canonical_hash,
    PrescriptionAuthorizationEnvelopeV2, validate_published_pilot_envelope,
)


NAMESPACE = PlotNamespace("tenant-A", "farm-A", "6ab14f59ad442f274c3f2a62")
SNAPSHOT = "ASMAE-SNAPSHOT-test-qualified"
GEOM = canonical_hash({"fixture": "geometry"})
JOB_MANIFEST = canonical_hash({"fixture": "job_manifest"})
RECEIPT = canonical_hash({"fixture": "publication_receipt"})
CYCLE = "wheat-cycle-A"
START = "2026-10-29T00:00:00Z"
END = "2026-10-30T16:00:00Z"
CUTOFF = "2026-10-30T17:44:46Z"
PUBLISHED = "2026-10-30T18:00:00Z"


def store_node():
    return {
        "snapshot_id": SNAPSHOT, "snapshot_kind": "asmae",
        "tenant_id": NAMESPACE.tenant_id, "farm_id": NAMESPACE.farm_id,
        "plot_id": NAMESPACE.plot_id, "geometry_hash": GEOM,
        "crop_cycle_id": CYCLE, "publication_receipt_hash": RECEIPT,
        "manifest_hash": JOB_MANIFEST, "evidence_cutoff_at": CUTOFF,
        "published_at": PUBLISHED, "observation_window": {"start": START, "end": END},
        "validation": {flag: True for flag in CANONICAL_PUBLICATION_VALIDATION_FLAGS},
        "scientific_result": {"raw_plot_data": "must_not_leak"},
    }


def read(source=None, namespace=NAMESPACE, **kwargs):
    with patch(
        "services.agribrain.layer05_asmae.plot_snapshot_store.load_latest_plot_snapshot",
        return_value=store_node() if source is None else source,
    ) as loaded:
        response = read_trusted_current_asmae_publication(
            namespace, expected_snapshot_id=kwargs.get("snapshot_id", SNAPSHOT),
            expected_geometry_hash=kwargs.get("geometry_hash", GEOM),
            expected_crop_cycle_id=kwargs.get("crop_cycle_id", CYCLE),
        )
        loaded.assert_called_once_with(namespace)
        return response


def preflight(artifact=None, source=None):
    with patch(
        "services.agribrain.layer05_asmae.plot_snapshot_store.load_latest_plot_snapshot",
        return_value=store_node() if source is None else source,
    ):
        return preflight_pilot_issuer(
            NAMESPACE, expected_snapshot_id=SNAPSHOT,
            expected_geometry_hash=GEOM, expected_crop_cycle_id=CYCLE,
            artifact=artifact,
        )


def artifact(policy=None, gate=None, namespace=NAMESPACE):
    return SimpleNamespace(
        inputs=SimpleNamespace(
            plot_namespace=namespace, policy_snapshot=policy if policy is not None else {}
        ),
        diagnostic_integration={"prescription_gate": gate if gate is not None else {}},
    )


def test_real_loader_adapter_yields_strict_v2_head_shape_not_raw_data():
    head = read()
    assert head["available"] is True
    assert head["snapshot_id"] == SNAPSHOT
    assert head["publication_receipt_hash"] == RECEIPT
    assert head["manifest_hash"] == JOB_MANIFEST
    assert head["observation_window"] == {"start": START, "end": END}
    assert "scientific_result" not in head
    assert len(head["validation"]) == 10
    assert not any("authorized_actions" in name for name in head)


def test_read_requires_valid_authenticated_namespace():
    for candidate in (None, "tenant:plot", PlotNamespace("tenant", "", "plot")):
        with pytest.raises(ContractViolation, match="authenticated PlotNamespace"):
            read(namespace=candidate)


@pytest.mark.parametrize("key, value", [
    ("snapshot_id", "ASMAE-SNAPSHOT-stale"),
    ("snapshot_kind", "layer10_terminal"),
    ("tenant_id", "another-tenant"),
    ("farm_id", "another-farm"),
    ("plot_id", "another-plot"),
    ("geometry_hash", canonical_hash({"different": True})),
    ("crop_cycle_id", "other-cycle"),
])
def test_wrong_current_identity_fails_closed(key, value):
    node = store_node()
    node[key] = value
    with pytest.raises(ContractViolation):
        read(source=node)


@pytest.mark.parametrize("flag", CANONICAL_PUBLICATION_VALIDATION_FLAGS)
def test_partial_or_invalid_snapshot_validation_fails_closed(flag):
    node = store_node()
    node["validation"][flag] = False
    with pytest.raises(ContractViolation, match="not fully integrity-validated"):
        read(source=node)


@pytest.mark.parametrize("key, value", [
    ("publication_receipt_hash", "not-a-hash"),
    ("manifest_hash", ""),
    ("geometry_hash", "bad-geometry"),
    ("crop_cycle_id", ""),
    ("evidence_cutoff_at", None),
    ("published_at", "2026-10-30"),
])
def test_missing_core_publication_fields_fail_closed(key, value):
    node = store_node()
    node[key] = value
    with pytest.raises(ContractViolation):
        read(source=node)


def test_invalid_chronological_order_or_no_current_head_fails():
    for node in (
        {},
        {**store_node(), "evidence_cutoff_at": "2026-10-30T15:00:00Z"},
        {**store_node(), "published_at": "2026-10-30T17:00:00Z"},
    ):
        with pytest.raises(ContractViolation):
            read(source=node)


def test_issuer_preflight_is_never_a_positive_authorization():
    prior = preflight(None)
    assert prior.status == "BLOCKED"
    assert prior.reason == "NO_RECORDED_PLOT_RUN"
    assert not hasattr(prior, "authorization")
    mismatch = preflight(artifact(namespace=PlotNamespace("foreign", "farm", "plot")))
    assert mismatch.reason == "ORCHESTRATOR_NAMESPACE_MISMATCH"
    no_policy = preflight(artifact())
    assert no_policy.reason == "MANDATORY_EVIDENCE_RECEIPT_POLICY_ABSENT"
    only_policy = preflight(artifact(policy={"require_evidence_receipts": True}))
    assert only_policy.reason == "DIAGNOSTIC_PROMOTION_GATE_UNAVAILABLE"
    all_present = preflight(artifact(
        policy={"require_evidence_receipts": True},
        gate={
            "status": "completed",
            "influence_manifest": {"requested_use": "PRESCRIPTION_DRIVER"},
        },
    ))
    assert all_present.status == "BLOCKED"
    assert all_present.reason == "ASSIMILATION_TO_L8_MEMBERSHIP_AND_UNCERTAINTY_UNVERIFIED"


def test_current_head_adapter_not_self_authorizing():
    head = read()
    assert "authorized_actions" not in head
    assert "signature" not in head
    # A valid publication is a necessary input to V2, not an issuer.
    assert "authorization_envelope" not in head


def test_no_server_head_makes_preflight_fail_not_authorize():
    with patch(
        "services.agribrain.layer05_asmae.plot_snapshot_store.load_latest_plot_snapshot",
        return_value=None,
    ):
        with pytest.raises(ContractViolation, match="unavailable"):
            preflight_pilot_issuer(
                NAMESPACE, expected_snapshot_id=SNAPSHOT,
                expected_geometry_hash=GEOM, expected_crop_cycle_id=CYCLE,
                artifact=artifact(),
            )
