"""Tests for Scientific Contracts V2 (Canonical Contracts).

Verifies the 7 Canonical Contracts:
  1. EvidenceRef
  2. StateRef
  3. DiagnosticResult
  4. CapabilityReceipt
  5. ForcingEvent
  6. ScenarioRef
  7. ActionAuthorization
and their validation, hashing, and diagnostic adapter integration.
"""

from datetime import datetime, timedelta, timezone
import pytest

from services.agribrain.scientific_contracts.authority import (
    AUTHORITY_DIAGNOSTIC,
    SpatialSupport,
)
from services.agribrain.scientific_contracts.contracts_v2 import (
    ActionAuthorization,
    CapabilityReceipt,
    DiagnosticResult,
    EvidenceRef,
    EvidenceRole,
    FeasibilityReceipt,
    ForcingEvent,
    ForcingExecutionStatus,
    InfluenceUse,
    OwnershipContext,
    ScenarioRef,
    StateRef,
    ValidityDomain,
    YieldDistribution,
    canonical_hash,
)
from services.agribrain.scientific_contracts.exceptions import ContractViolation
from services.agribrain.diagnostic_integration.adapters import AdapterContext, adapt_diagnostic_result


# ---------------------------------------------------------------------------
# 1. EvidenceRef Tests
# ---------------------------------------------------------------------------

def test_evidence_ref_valid():
    t0 = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=15)
    ownership = OwnershipContext("tenant_mitidja", "farm_01", "plot_algeria_1")

    ev = EvidenceRef(
        evidence_id="ev_sar_vv_001",
        ownership=ownership,
        variable_name="surface_soil_moisture",
        units="m3/m3",
        observed_at=t0,
        knowledge_available_at=t1,
        spatial_support=SpatialSupport.PIXEL_NATIVE,
        transformation_lineage=("raw_radiometry", "radiometric_terrain_correction"),
        admissible_roles=(EvidenceRole.OBSERVATION_NATIVE,),
        quality_grade="A",
        raw_payload_uri="s3://agribrain-archive/s1/scene_001.tif",
    )

    assert ev.evidence_id == "ev_sar_vv_001"
    assert ev.units == "m3/m3"
    d = ev.to_dict()
    assert d["ownership"]["tenant_id"] == "tenant_mitidja"
    h = ev.compute_hash()
    assert isinstance(h, str) and len(h) == 64


def test_evidence_ref_invalid_temporal_order():
    t0 = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    t_past = t0 - timedelta(minutes=15)
    ownership = OwnershipContext("t1", "f1", "p1")

    # Knowledge available before observation violates physics/causality
    with pytest.raises(ContractViolation, match="observed_at cannot be later than knowledge_available_at"):
        EvidenceRef(
            evidence_id="ev_future",
            ownership=ownership,
            variable_name="temp",
            units="K",
            observed_at=t0,
            knowledge_available_at=t_past,
            spatial_support=SpatialSupport.PLOT,
        )


def test_evidence_ref_missing_units():
    t0 = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    ownership = OwnershipContext("t1", "f1", "p1")

    with pytest.raises(ContractViolation, match="requires non-blank units"):
        EvidenceRef(
            evidence_id="ev_nounits",
            ownership=ownership,
            variable_name="vwc",
            units="",
            observed_at=t0,
            knowledge_available_at=t0,
            spatial_support=SpatialSupport.PLOT,
        )


# ---------------------------------------------------------------------------
# 2. StateRef Tests
# ---------------------------------------------------------------------------

def test_state_ref_valid():
    t0 = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    vec = (0.28, 0.32, 2.5, 0.78)
    # 4x4 covariance
    cov = tuple(tuple(1.0 if i == j else 0.05 for j in range(4)) for i in range(4))

    state = StateRef(
        state_id="state_mitidja_20260501",
        schema_version="asmae_state_v1_13",
        snapshot_timestamp=t0,
        knowledge_cutoff=t0,
        lattice_reference="lattice_10m_epsg32631",
        state_vector=vec,
        state_covariance=cov,
        identifiability_classes={"root_zone_moisture": "IDENTIFIED", "lai": "IDENTIFIED"},
        worldline_head_hash="hash_event_head_098",
    )

    assert state.state_id == "state_mitidja_20260501"
    assert len(state.state_vector) == 4
    d = state.to_dict()
    assert d["schema_version"] == "asmae_state_v1_13"
    assert len(state.compute_hash()) == 64


def test_state_ref_covariance_dimension_mismatch():
    t0 = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    vec = (0.28, 0.32, 2.5)  # 3 elements
    cov = ((1.0, 0.0), (0.0, 1.0))  # 2x2 covariance!

    with pytest.raises(ContractViolation, match="matching state_vector dimension"):
        StateRef(
            state_id="state_bad_cov",
            schema_version="v1",
            snapshot_timestamp=t0,
            knowledge_cutoff=t0,
            lattice_reference="grid1",
            state_vector=vec,
            state_covariance=cov,
            identifiability_classes={},
            worldline_head_hash="head1",
        )


# ---------------------------------------------------------------------------
# 3. DiagnosticResult Tests
# ---------------------------------------------------------------------------

def test_diagnostic_result_valid():
    diag = DiagnosticResult(
        diagnosis_id="diag_water_001",
        layer_id="L3",
        target_hypothesis="WATER_DEFICIT_STRESS",
        severity=0.72,
        probability=0.85,
        confidence=0.90,
        evidence_strength_log_odds=2.15,
        confounders_evaluated=("ROOT_ASPHYXIA", "SALINITY_OSMOTIC_STRESS"),
        unresolved_status=False,
        input_evidence_ids=("ev_s1_01", "ev_iot_02"),
    )

    assert diag.probability == 0.85
    assert diag.confidence == 0.90
    d = diag.to_dict()
    assert d["severity"] == 0.72
    assert len(diag.compute_hash()) == 64


def test_diagnostic_result_out_of_bounds_probability():
    with pytest.raises(ContractViolation, match="probability must be finite in"):
        DiagnosticResult(
            diagnosis_id="diag_bad",
            layer_id="L3",
            target_hypothesis="WATER_STRESS",
            severity=0.5,
            probability=1.25,  # Invalid > 1.0
            confidence=0.8,
        )


# ---------------------------------------------------------------------------
# 4. CapabilityReceipt Tests
# ---------------------------------------------------------------------------

def test_capability_receipt_valid_and_expiration():
    t_issue = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
    t_expire = t_issue + timedelta(days=7)
    domain = ValidityDomain(bounding_box=(2.9, 36.5, 3.2, 36.8), crop_species="wheat")

    receipt = CapabilityReceipt(
        receipt_id="cap_rec_001",
        target_variable="irrigation_recommendation",
        permitted_use=InfluenceUse.PRESCRIPTION_DRIVER,
        validity_domain=domain,
        evidence_support_hash="ev_hash_abc",
        qualification_certificate_id="cert_inra_2026_01",
        issued_at=t_issue,
        expires_at=t_expire,
        signature="sig_ed25519_authoritative",
    )

    assert receipt.is_valid_at(t_issue + timedelta(days=1))
    assert not receipt.is_valid_at(t_issue + timedelta(days=8))
    d = receipt.to_dict()
    assert d["permitted_use"] == "PRESCRIPTION_DRIVER"


def test_capability_receipt_invalid_dates():
    t_issue = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
    t_expire = t_issue - timedelta(hours=1)
    domain = ValidityDomain()

    with pytest.raises(ContractViolation, match="issued_at must be strictly before expires_at"):
        CapabilityReceipt(
            receipt_id="cap_bad",
            target_variable="var1",
            permitted_use=InfluenceUse.DIAGNOSIS,
            validity_domain=domain,
            evidence_support_hash="h1",
            qualification_certificate_id="cert1",
            issued_at=t_issue,
            expires_at=t_expire,
        )


# ---------------------------------------------------------------------------
# 5. ForcingEvent Tests
# ---------------------------------------------------------------------------

def test_forcing_event_valid():
    t0 = datetime(2026, 5, 1, 6, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=2)

    event = ForcingEvent(
        event_id="force_irr_001",
        forcing_type="IRRIGATION",
        execution_status=ForcingExecutionStatus.OBSERVED_CONFIRMED,
        quantity=25.0,
        units="mm",
        effective_start=t0,
        effective_end=t1,
        spatial_extent=SpatialSupport.ZONE,
        efficiency_factor=0.90,
        provenance_hash="flowmeter_telemetry_hash",
    )

    assert event.quantity == 25.0
    assert event.units == "mm"
    d = event.to_dict()
    assert d["execution_status"] == "OBSERVED_CONFIRMED"
    assert len(event.compute_hash()) == 64


def test_forcing_event_negative_quantity():
    t0 = datetime(2026, 5, 1, 6, 0, tzinfo=timezone.utc)

    with pytest.raises(ContractViolation, match="quantity must be finite and non-negative"):
        ForcingEvent(
            event_id="force_bad",
            forcing_type="IRRIGATION",
            execution_status=ForcingExecutionStatus.PLANNED,
            quantity=-5.0,
            units="mm",
            effective_start=t0,
            effective_end=t0,
            spatial_extent=SpatialSupport.PLOT,
        )


# ---------------------------------------------------------------------------
# 6. ScenarioRef & 7. ActionAuthorization Tests
# ---------------------------------------------------------------------------

def test_scenario_and_action_authorization_flow():
    t_now = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    feasibility = FeasibilityReceipt(
        is_feasible=True,
        constraint_checks={"soil_trafficability": True, "weather_spray_window": True},
        evaluated_at=t_now,
    )
    yield_dist = YieldDistribution(p10=3.2, p50=4.1, p90=4.8, units="t/ha")

    scenario = ScenarioRef(
        scenario_id="scen_irr_rate_a",
        action_type="IRRIGATE_VARIABLE_RATE",
        proposed_timing=t_now + timedelta(hours=18),
        target_zones=("Zone_North", "Zone_South"),
        parameters={"rate_mm": 20.0, "method": "DRIP"},
        feasibility_receipt=feasibility,
        conditional_trajectory_id="traj_future_w90",
        expected_yield_impact=yield_dist,
        assumptions=("no_extreme_heat_wave",),
    )

    assert scenario.scenario_id == "scen_irr_rate_a"
    scen_hash = scenario.compute_hash()
    assert len(scen_hash) == 64

    # Binding Action Authorization
    auth = ActionAuthorization(
        authorization_id="auth_l8_001",
        selected_scenario_id=scenario.scenario_id,
        belief_state_id="state_mitidja_20260501",
        tribunal_receipt_hash="tribunal_sig_0987",
        prescription_manifest_hash=scen_hash,
        policy_snapshot_hash="policy_v6_strict",
        authorized_by="AUTONOMOUS_POLICY_L8",
        authorized_at=t_now,
        exact_action_payload={"target_zones": ["Zone_North"], "rate_mm": 20.0},
    )

    assert auth.authorization_id == "auth_l8_001"
    auth_hash = auth.compute_hash()
    assert len(auth_hash) == 64
    d = auth.to_dict()
    assert d["authorized_by"] == "AUTONOMOUS_POLICY_L8"


# ---------------------------------------------------------------------------
# 8. Diagnostic Integration Adapter Tests
# ---------------------------------------------------------------------------

def test_adapt_diagnostic_result_to_tribunal_contribution():
    diag = DiagnosticResult(
        diagnosis_id="diag_nitrogen_deficiency",
        layer_id="L4",
        target_hypothesis="NITROGEN_DEFICIENCY",
        severity=0.65,
        probability=0.78,
        confidence=0.88,
        evidence_strength_log_odds=1.80,
        input_evidence_ids=("ev_chlorophyll_01",),
    )

    ctx = AdapterContext(
        input_belief_id="belief_state_001",
        authority=AUTHORITY_DIAGNOSTIC,
        input_evidence_ids=("ev_chlorophyll_01",),
    )

    contribs = adapt_diagnostic_result(diag, ctx)
    assert len(contribs) == 1
    c = contribs[0]
    assert c.layer_id == "L4"
    assert c.target_state == "diagnostic.nitrogen_deficiency"
    assert c.confidence == 0.88
    assert c.payload["severity"] == 0.65
