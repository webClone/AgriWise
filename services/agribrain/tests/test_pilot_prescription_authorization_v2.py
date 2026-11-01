"""Additive V2 publication-bound prescription authorization contract gates.

Fixture heads emulate already-verified ASMAE publications. These tests do NOT
create a scientific publication, issue an operational authorization, or prove
that any production signing service exists.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.scientific_contracts.prescription_authorization import (
    AuthorizedActionV1,
    CANONICAL_PUBLICATION_VALIDATION_FLAGS,
    PRESCRIPTION_AUTHORIZATION_ENVELOPE_V2,
    PrescriptionAuthorizationEnvelopeV1,
    PrescriptionAuthorizationEnvelopeV2,
    canonical_hash,
    parse_prescription_authorization_envelope,
    validate_published_pilot_envelope,
)


def digest(label: str) -> str:
    return canonical_hash({"fixture": label})


def action(*, rate=None, machine_execution_allowed=False) -> AuthorizedActionV1:
    return AuthorizedActionV1(
        action_id="A-L8-1", action_type="FERTILIZE", priority_score=0.8,
        urgency_score=0.7, confidence="MODERATE", rationale="fixture",
        rate=rate if rate is not None else {
            "recommended": 40.0, "min_safe": 35.0,
            "max_safe": 45.0, "unit": "kg_N/ha",
        },
        zone_targets=("plot",), requires_confirmation=not machine_execution_allowed,
        machine_execution_allowed=machine_execution_allowed,
    )


def common():
    return {
        "input_belief_id": "belief-a",
        "tribunal_content_hash": digest("tribunal"),
        "prescription_manifest_hash": digest("prescription-manifest"),
        "prescription_manifest_entry_ids": ("DC-A-1",),
        "policy_snapshot_hash": digest("policy"),
        "l8_run_id": "l8-001",
        "l8_content_hash": digest("l8"),
        "final_execution_plan_hash": digest("plan"),
        "actions": (action(),),
    }


def pilot_fields():
    return {
        "tenant_id": "tenant-a",
        "farm_id": "farm-a",
        "plot_id": "6ab14f59ad442f274c3f2a62",
        "geometry_hash": digest("geometry"),
        "crop_cycle_id": "cycle-wheat-2026",
        "snapshot_id": "ASMAE-SNAPSHOT-pilot-a",
        "canonical_publication_receipt_hash": digest("publication"),
        "evidence_manifest_hash": digest("admitted-evidence-manifest"),
        "evidence_cutoff_at": "2026-10-30T17:44:46+00:00",
        "observation_window_start": "2026-10-29T00:00:00+00:00",
        "observation_window_end": "2026-10-30T16:00:00+00:00",
        "published_at": "2026-10-30T18:00:00+00:00",
        "issued_at": "2026-10-30T18:20:00+00:00",
        "expires_at": "2026-11-02T18:20:00+00:00",
        "uncertainty_receipt_hash": digest("verified-uncertainty"),
    }


def v2(**updates) -> PrescriptionAuthorizationEnvelopeV2:
    return PrescriptionAuthorizationEnvelopeV2(**{**common(), **pilot_fields(), **updates})


def head():
    fields = pilot_fields()
    return {
        "available": True, "snapshot_kind": "asmae",
        "tenant_id": fields["tenant_id"],
        "farm_id": fields["farm_id"],
        "plot_id": fields["plot_id"],
        "geometry_hash": fields["geometry_hash"],
        "crop_cycle_id": fields["crop_cycle_id"],
        "snapshot_id": fields["snapshot_id"],
        "publication_receipt_hash": fields["canonical_publication_receipt_hash"],
        "manifest_hash": fields["evidence_manifest_hash"],
        "evidence_cutoff_at": fields["evidence_cutoff_at"],
        "published_at": fields["published_at"],
        "observation_window": {
            "start": fields["observation_window_start"],
            "end": fields["observation_window_end"],
        },
        "validation": {name: True for name in CANONICAL_PUBLICATION_VALIDATION_FLAGS},
    }


def context():
    f = pilot_fields()
    return {
        "tenant_id": f["tenant_id"], "farm_id": f["farm_id"],
        "plot_id": f["plot_id"], "crop_cycle_id": f["crop_cycle_id"],
        "geometry_hash": f["geometry_hash"],
        "now": "2026-10-31T15:00:00Z",
        "verified_uncertainty_receipt_hash": f["uncertainty_receipt_hash"],
    }


def check(candidate=None, publication=None, **context_overrides):
    return validate_published_pilot_envelope(
        candidate if candidate is not None else v2().to_dict(),
        canonical_head=publication if publication is not None else head(),
        **{**context(), **context_overrides},
    )


def test_v1_contract_is_unchanged_and_still_parseable():
    legacy = PrescriptionAuthorizationEnvelopeV1(**common())
    parsed = parse_prescription_authorization_envelope(legacy.to_dict())
    assert type(parsed) is PrescriptionAuthorizationEnvelopeV1
    assert parsed.to_dict() == legacy.to_dict()
    assert parsed.content_hash == canonical_hash(legacy.identity_payload())
    with pytest.raises(ContractViolation, match="requires V2"):
        check(legacy.to_dict())


def test_v2_content_hash_round_trip_and_publication_match():
    envelope = v2()
    assert envelope.schema_version == PRESCRIPTION_AUTHORIZATION_ENVELOPE_V2
    assert envelope.content_hash == canonical_hash(envelope.identity_payload())
    assert envelope.content_hash != PrescriptionAuthorizationEnvelopeV1(**common()).content_hash
    as_json = envelope.to_dict()
    assert as_json["evidence_cutoff_at"].endswith("Z")
    restored = parse_prescription_authorization_envelope(as_json)
    assert isinstance(restored, PrescriptionAuthorizationEnvelopeV2)
    assert restored.content_hash == envelope.content_hash
    assert check(as_json) == envelope
    assert PrescriptionAuthorizationEnvelopeV2.from_mapping(as_json) == envelope
    with pytest.raises(ContractViolation, match="Unsupported prescription authorization schema"):
        PrescriptionAuthorizationEnvelopeV1.from_mapping(as_json)


@pytest.mark.parametrize("field", [
    "tenant_id", "farm_id", "plot_id", "crop_cycle_id", "snapshot_id",
    "geometry_hash", "canonical_publication_receipt_hash",
    "evidence_manifest_hash", "evidence_cutoff_at", "published_at",
    "observation_window_start", "observation_window_end",
    "issued_at", "expires_at", "uncertainty_receipt_hash",
])
def test_each_publication_or_validity_field_changes_identity_hash(field):
    baseline = v2()
    original = baseline.to_dict()
    changed = dict(original)
    # Make a valid enough change for identity-hash testing where possible;
    # some changes violate structural/order checks and must be rejected.
    if field.endswith("_hash"):
        changed[field] = digest("different-" + field)
    elif field in ("evidence_cutoff_at", "published_at", "issued_at", "expires_at",
                   "observation_window_start", "observation_window_end"):
        changed[field] = "2026-10-30T17:30:00Z"
    else:
        changed[field] = original[field] + "-different"
    with pytest.raises(ContractViolation):
        PrescriptionAuthorizationEnvelopeV2.from_mapping(changed)


@pytest.mark.parametrize("field", [
    "tenant_id", "farm_id", "plot_id", "geometry_hash", "crop_cycle_id",
    "snapshot_id", "publication_receipt_hash", "manifest_hash",
    "evidence_cutoff_at", "published_at", "observation_window",
])
def test_mismatched_current_canonical_head_fails_closed(field):
    actual = head()
    if field == "observation_window":
        actual[field] = {**actual[field], "end": "2026-10-30T15:59:59Z"}
    elif field.endswith("_hash"):
        actual[field] = digest("swapped")
    else:
        actual[field] = "other"
    with pytest.raises(ContractViolation):
        check(publication=actual)


@pytest.mark.parametrize("flag", CANONICAL_PUBLICATION_VALIDATION_FLAGS)
def test_each_missing_or_false_publication_validation_flag_fails(flag):
    for value in (False, None):
        actual = head()
        actual["validation"][flag] = value
        with pytest.raises(ContractViolation, match="validation is incomplete"):
            check(publication=actual)


def test_non_current_or_non_asmae_publication_fails():
    publication = head()
    publication["available"] = False
    with pytest.raises(ContractViolation, match="unavailable"):
        check(publication=publication)
    publication = head()
    publication["snapshot_kind"] = "layer10"
    with pytest.raises(ContractViolation, match="ASMAE"):
        check(publication=publication)


def test_current_tenant_geometry_crop_cycle_and_uncertainty_scope_fails():
    for name, value in (
        ("tenant_id", "foreign"),
        ("farm_id", "foreign"),
        ("plot_id", "foreign"),
        ("crop_cycle_id", "different"),
        ("geometry_hash", digest("other geometry")),
        ("verified_uncertainty_receipt_hash", digest("other uncertainty")),
    ):
        with pytest.raises(ContractViolation):
            check(**{name: value})


@pytest.mark.parametrize("now", [
    "2026-10-30T18:19:59Z",  # Not yet authorized
    "2026-11-02T18:20:00Z",  # Exactly at expiry
    "2026-11-03T15:00:00Z",  # Expired
])
def test_v2_temporal_validity_fails_closed(now):
    with pytest.raises(ContractViolation, match="not yet valid or expired"):
        check(now=now)


@pytest.mark.parametrize("field, invalid", [
    ("evidence_cutoff_at", "2026-10-30"),
    ("issued_at", "2026-10-30T18:20:00"),  # timezone not qualified
    ("expires_at", "2026-10-30T18:00:00Z"),
    ("observation_window_end", "2026-10-31T18:00:00Z"),
])
def test_malformed_or_out_of_order_temporal_identity_is_rejected(field, invalid):
    with pytest.raises(ContractViolation):
        v2(**{field: invalid})


def test_timestamp_with_fractional_seconds_compares_chronologically():
    with pytest.raises(ContractViolation, match="temporal window"):
        v2(
            observation_window_end="2026-10-30T17:44:46.900Z",
            evidence_cutoff_at="2026-10-30T17:44:46Z",
        )


@pytest.mark.parametrize("rate", [
    {"recommended": 50.0, "min_safe": 35.0, "max_safe": 45.0, "unit": "kg/ha"},
    {"recommended": -1, "min_safe": 0, "max_safe": 10, "unit": "kg/ha"},
    {"recommended": float("nan"), "min_safe": 0, "max_safe": 10, "unit": "kg/ha"},
    {"recommended": 1, "min_safe": 0, "max_safe": float("inf"), "unit": "kg/ha"},
    {"recommended": 1, "max_safe": 10, "unit": "kg/ha"},
    {"recommended": 1, "min_safe": 0, "max_safe": 10, "unit": ""},
])
def test_v2_rejects_unbounded_or_nonfinite_rates(rate):
    with pytest.raises(ContractViolation):
        v2(actions=(action(rate=rate),))


def test_v2_disallows_dose_free_physical_interventions():
    physical = action(rate={})
    with pytest.raises(ContractViolation, match="requires explicit bounded rate"):
        v2(actions=(physical,))
    observational = replace(physical, action_type="MONITOR")
    assert v2(actions=(observational,)).actions[0].rate == {}


def test_v2_rejects_machine_execution_and_keeps_action_hash_bound():
    with pytest.raises(ContractViolation, match="machine execution"):
        v2(actions=(action(machine_execution_allowed=True),))
    serialized = v2().to_dict()
    serialized["actions"][0]["rate"]["recommended"] = 41.0
    with pytest.raises(ContractViolation, match="content_hash does not match"):
        PrescriptionAuthorizationEnvelopeV2.from_mapping(serialized)


def test_v2_rejects_unknown_fields_and_missing_publication_identity():
    serialized = v2().to_dict()
    serialized["debug_authorized"] = True
    with pytest.raises(ContractViolation, match="unrecognized"):
        PrescriptionAuthorizationEnvelopeV2.from_mapping(serialized)
    serialized = v2().to_dict()
    serialized.pop("canonical_publication_receipt_hash")
    with pytest.raises(ContractViolation):
        PrescriptionAuthorizationEnvelopeV2.from_mapping(serialized)
    with pytest.raises(ContractViolation):
        parse_prescription_authorization_envelope({"schema_version": "unknown"})


def test_v2_requires_explicit_uncertainty_receipt_and_never_issues_real_authority():
    # The fixture supplies a hash for the validator: it does not cryptographically
    # establish an upstream uncertainty certificate or a production signing act.
    with pytest.raises(ContractViolation):
        check(verified_uncertainty_receipt_hash="")
    result = check()
    assert all(not action.machine_execution_allowed for action in result.actions)
