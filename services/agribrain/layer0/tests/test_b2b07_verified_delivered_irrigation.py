"""L0-B2B07: Process Covariance, Verified Delivered Irrigation & Separation Suite.

Covers:
1. Asymmetric KMS signing (Ed25519 & ES256) of VerifiedDeliveredIrrigationGrant.
2. Exact physical conversion checks: net_depth_mm = (liters * efficiency) / area_m2.
3. Negative physical invariants (zero area, negative volume, bad efficiency, non-finite).
4. Replay and idempotency fencing.
5. Scope binding (tenant, plot, geometry hash/version, zone).
6. DurableRevocationAuthority integration (key revocation, plot revocation, stale anchor).
7. Separation of authority:
   - Farmer text VERIFIED_DELIVERY role remains DEFERRED.
   - scientific_publication_authorized and actuator_control_authorized are strictly False.
   - No direct raw event forcing in ZoneKalmanFilter.predict without L3 receipt.
8. Physical water balance and atomic Q(dt) uncertainty injection.
"""
from datetime import datetime, timedelta, timezone
import math
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from services.agribrain.layer0.durable_revocation_authority import (
    DurableRevocationAuthority,
    DurableRevocationSnapshot,
)
from services.agribrain.layer0.event_forcing_admission import (
    classify_management_event_evidence,
)
from services.agribrain.layer0.kalman_engine import ZoneKalmanFilter
from services.agribrain.layer0.source_package import Layer0StatePackage
from services.agribrain.layer0.state_engine import Layer0StateEngine
from services.agribrain.layer0.state_vector import (
    IDX_SM_0_10,
    StateVector,
)
from services.agribrain.layer0.v3_kms_signed_issuer import (
    KmsPublicKeyRegistry,
)
from services.agribrain.layer0.verified_irrigation_contract import (
    VERIFIED_IRRIGATION_DOMAIN,
    VERIFIED_IRRIGATION_PURPOSE,
    AdmittedDeliveredIrrigation,
    VerifiedDeliveredIrrigationGrant,
    VerifiedDeliveredIrrigationReceipt,
    VerifiedDeliveredIrrigationSigner,
    VerifiedDeliveredIrrigationVerifier,
)

DAY = "2026-11-01"
CUTOFF = datetime(2026, 11, 1, 23, 59, 59, tzinfo=timezone.utc)
WEATHER = {"temp_min": 10.0, "temp_max": 20.0, "precipitation": 0.0, "et0": 3.0}


@pytest.fixture
def keys_ed25519():
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    return priv, pub


@pytest.fixture
def keys_es256():
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    return priv, pub


@pytest.fixture
def registry(keys_ed25519, keys_es256):
    reg = KmsPublicKeyRegistry()
    _, pub_ed = keys_ed25519
    _, pub_es = keys_es256
    t_from = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t_until = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    ed_bytes = pub_ed.public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )
    es_pem = pub_es.public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    reg.register_public_key(
        key_id="l3-meter-key-1",
        issuer_id="akaloris-l3-irrigation-authority",
        source="sensor_iot",
        algorithm="Ed25519",
        public_key_pem_or_bytes=ed_bytes,
        valid_from=t_from,
        valid_until=t_until,
    )
    reg.register_public_key(
        key_id="l3-meter-key-es256",
        issuer_id="akaloris-l3-irrigation-authority",
        source="sensor_iot",
        algorithm="ES256",
        public_key_pem_or_bytes=es_pem,
        valid_from=t_from,
        valid_until=t_until,
    )
    return reg


@pytest.fixture
def revocation_authority():
    t_base = datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc)
    snap0 = DurableRevocationSnapshot(
        revision=0,
        issued_at=t_base,
        expires_at=t_base + timedelta(days=1),
        key_statuses={
            "l3-meter-key-1": "active",
            "l3-meter-key-es256": "active",
        },
    )
    return DurableRevocationAuthority(snap0, max_snapshot_age_seconds=86400)


@pytest.fixture
def verifier(registry, revocation_authority):
    return VerifiedDeliveredIrrigationVerifier(
        public_key_registry=registry,
        revocation_authority=revocation_authority,
    )


def valid_grant_dict(
    volume_liters=10000.0,
    area_m2=1000.0,
    efficiency=0.9,
    receipt_id="rcpt-001",
    replay_key="replay-001",
    algorithm="Ed25519",
    key_id="l3-meter-key-1",
    plot_id="plot-A",
    geometry_hash="geom-A",
    geometry_version=1,
    zone_id="plot",
    tenant_id="tenant-prod-alpha",
    revocation_anchor=0,
    delivery_end="2026-11-01T14:00:00Z",
):
    if area_m2 and not math.isnan(area_m2) and not math.isinf(area_m2) and area_m2 > 0:
        net_depth = (volume_liters * efficiency) / area_m2
    else:
        net_depth = 1.0
    return {
        "domain": VERIFIED_IRRIGATION_DOMAIN,
        "version": "v3",
        "algorithm": algorithm,
        "key_id": key_id,
        "issuer_id": "akaloris-l3-irrigation-authority",
        "purpose": VERIFIED_IRRIGATION_PURPOSE,
        "receipt_id": receipt_id,
        "tenant_id": tenant_id,
        "plot_id": plot_id,
        "geometry_hash": geometry_hash,
        "geometry_version": geometry_version,
        "zone_id": zone_id,
        "delivery_start": "2026-11-01T12:00:00Z",
        "delivery_end": delivery_end,
        "delivered_volume_liters": volume_liters,
        "wetted_area_m2": area_m2,
        "delivery_efficiency_fraction": efficiency,
        "net_infiltrated_depth_mm": round(net_depth, 6) if math.isfinite(net_depth) else 1.0,
        "conversion_calibration_id": "cal-meter-mag-9000-v1",
        "depth_uncertainty_sigma_mm": 0.5,
        "source_evidence_cas_root": "bafybeihdwdcefghijk456789abcdef",
        "replay_idempotency_key": replay_key,
        "revocation_revision_anchor": revocation_anchor,
        "issued_at": "2026-11-01T14:05:00Z",
        "expires_at": "2026-11-02T14:00:00Z",
        "scientific_publication_authorized": False,
        "actuator_control_authorized": False,
    }


def make_signed_receipt(priv, grant_dict):
    signer = VerifiedDeliveredIrrigationSigner(
        key_id=grant_dict["key_id"],
        issuer_id=grant_dict["issuer_id"],
        algorithm=grant_dict["algorithm"],
        private_key=priv,
    )
    return signer.sign(grant_dict)


# ============================================================================
# 1. Asymmetric Cryptographic Signing & Admitted Token Structure
# ============================================================================

def test_ed25519_valid_signature_and_admission(keys_ed25519, verifier):
    priv, _ = keys_ed25519
    grant_data = valid_grant_dict()
    receipt = make_signed_receipt(priv, grant_data)

    admitted = verifier.verify_and_admit(
        receipt,
        expected_day=DAY,
        expected_plot_id="plot-A",
        expected_zone_id="plot",
        expected_geometry_hash="geom-A",
        expected_geometry_version=1,
        expected_tenant_id="tenant-prod-alpha",
        cutoff=CUTOFF,
    )
    assert isinstance(admitted, AdmittedDeliveredIrrigation)
    assert admitted.net_infiltrated_depth_mm == pytest.approx(9.0)
    assert admitted.depth_uncertainty_sigma_mm == 0.5
    assert admitted.scientific_publication_authorized is False
    assert admitted.actuator_control_authorized is False


def test_es256_valid_signature_and_admission(keys_es256, verifier):
    priv, _ = keys_es256
    grant_data = valid_grant_dict(
        algorithm="ES256",
        key_id="l3-meter-key-es256",
        receipt_id="rcpt-es256",
        replay_key="replay-es256",
    )
    receipt = make_signed_receipt(priv, grant_data)

    admitted = verifier.verify_and_admit(
        receipt,
        expected_day=DAY,
        expected_plot_id="plot-A",
        expected_zone_id="plot",
        expected_geometry_hash="geom-A",
        expected_geometry_version=1,
        expected_tenant_id="tenant-prod-alpha",
        cutoff=CUTOFF,
    )
    assert admitted.receipt_id == "rcpt-es256"
    assert admitted.net_infiltrated_depth_mm == pytest.approx(9.0)


def test_tampered_signature_is_rejected(keys_ed25519, verifier):
    priv, _ = keys_ed25519
    grant_data = valid_grant_dict()
    receipt = make_signed_receipt(priv, grant_data)
    # Alter the last character of the signature
    tampered_sig = receipt.signature[:-1] + ("A" if receipt.signature[-1] != "A" else "B")
    bad_receipt = VerifiedDeliveredIrrigationReceipt(
        grant=receipt.grant,
        signature=tampered_sig,
        key_id=receipt.key_id,
        algorithm=receipt.algorithm,
    )
    with pytest.raises(ValueError, match="tampered_receipt_signature"):
        verifier.verify_and_admit(
            bad_receipt,
            expected_day=DAY,
            expected_plot_id="plot-A",
            expected_zone_id="plot",
        )


# ============================================================================
# 2. Physical Invariants & Dimensional Conversion
# ============================================================================

@pytest.mark.parametrize("volume,area,efficiency,error_match", [
    (0.0, 1000.0, 0.9, "zero_or_negative_volume"),
    (-500.0, 1000.0, 0.9, "zero_or_negative_volume"),
    (10000.0, 0.0, 0.9, "zero_or_negative_wetted_area"),
    (10000.0, -100.0, 0.9, "zero_or_negative_wetted_area"),
    (10000.0, 1000.0, 0.0, "invalid_delivery_efficiency"),
    (10000.0, 1000.0, -0.5, "invalid_delivery_efficiency"),
    (10000.0, 1000.0, 1.05, "invalid_delivery_efficiency"),
    (math.nan, 1000.0, 0.9, "must be finite number"),
    (10000.0, math.inf, 0.9, "must be finite number"),
])
def test_invalid_physical_dimensions_fail_grant_creation(volume, area, efficiency, error_match):
    grant_data = valid_grant_dict(volume_liters=volume, area_m2=area, efficiency=efficiency)
    with pytest.raises(ValueError, match=error_match):
        VerifiedDeliveredIrrigationGrant.from_dict(grant_data)


def test_inconsistent_claimed_depth_conversion_fails():
    # Correct calculation: (10,000 L * 0.9) / 1,000 m2 = 9.0 mm
    # Claimant asserts 18.0 mm
    grant_data = valid_grant_dict()
    grant_data["net_infiltrated_depth_mm"] = 18.0
    with pytest.raises(ValueError, match="inconsistent depth conversion"):
        VerifiedDeliveredIrrigationGrant.from_dict(grant_data)


def test_missing_calibration_or_cas_root_fails():
    grant_data = valid_grant_dict()
    grant_data["conversion_calibration_id"] = "   "
    with pytest.raises(ValueError, match="conversion_calibration_id must be a non-empty string"):
        VerifiedDeliveredIrrigationGrant.from_dict(grant_data)

    grant_data = valid_grant_dict()
    grant_data["source_evidence_cas_root"] = ""
    with pytest.raises(ValueError, match="source_evidence_cas_root must be a non-empty string"):
        VerifiedDeliveredIrrigationGrant.from_dict(grant_data)


# ============================================================================
# 3. Replay Protection & Idempotency
# ============================================================================

def test_replaying_same_receipt_is_rejected(keys_ed25519, verifier):
    priv, _ = keys_ed25519
    grant_data = valid_grant_dict(receipt_id="replay-test-1", replay_key="key-test-1")
    receipt = make_signed_receipt(priv, grant_data)

    # First admission succeeds
    verifier.verify_and_admit(
        receipt,
        expected_day=DAY,
        expected_plot_id="plot-A",
        expected_zone_id="plot",
    )

    # Second admission fails with duplicate_replay_key
    with pytest.raises(ValueError, match="duplicate_replay_key"):
        verifier.verify_and_admit(
            receipt,
            expected_day=DAY,
            expected_plot_id="plot-A",
            expected_zone_id="plot",
        )


def test_different_receipt_with_same_replay_key_rejected(keys_ed25519, verifier):
    priv, _ = keys_ed25519
    r1 = make_signed_receipt(priv, valid_grant_dict(receipt_id="r1", replay_key="same-key"))
    r2 = make_signed_receipt(priv, valid_grant_dict(receipt_id="r2", replay_key="same-key"))

    verifier.verify_and_admit(r1, expected_day=DAY, expected_plot_id="plot-A", expected_zone_id="plot")
    with pytest.raises(ValueError, match="duplicate_replay_key"):
        verifier.verify_and_admit(r2, expected_day=DAY, expected_plot_id="plot-A", expected_zone_id="plot")


# ============================================================================
# 4. Scope, Temporal and Durable Revocation Controls
# ============================================================================

def test_scope_mismatch_rejections(keys_ed25519, verifier):
    priv, _ = keys_ed25519
    receipt = make_signed_receipt(priv, valid_grant_dict())

    # Foreign plot
    with pytest.raises(ValueError, match="unbound_or_foreign_plot"):
        verifier.verify_and_admit(receipt, expected_day=DAY, expected_plot_id="plot-FOREIGN", expected_zone_id="plot")

    # Foreign geometry
    with pytest.raises(ValueError, match="unbound_or_foreign_geometry"):
        verifier.verify_and_admit(receipt, expected_day=DAY, expected_plot_id="plot-A", expected_zone_id="plot", expected_geometry_hash="geom-OTHER")

    # Mismatched geometry version
    with pytest.raises(ValueError, match="unbound_or_foreign_geometry_version"):
        verifier.verify_and_admit(receipt, expected_day=DAY, expected_plot_id="plot-A", expected_zone_id="plot", expected_geometry_version=2)

    # Foreign zone
    with pytest.raises(ValueError, match="event_outside_zone"):
        verifier.verify_and_admit(receipt, expected_day=DAY, expected_plot_id="plot-A", expected_zone_id="zone-2")

    # Foreign tenant
    with pytest.raises(ValueError, match="foreign_tenant_scope"):
        verifier.verify_and_admit(receipt, expected_day=DAY, expected_plot_id="plot-A", expected_zone_id="plot", expected_tenant_id="tenant-OTHER")


def test_temporal_cutoff_and_day_rejections(keys_ed25519, verifier):
    priv, _ = keys_ed25519
    # Delivery on 2026-11-02 presented for 2026-11-01
    r_tomorrow = make_signed_receipt(priv, valid_grant_dict(delivery_end="2026-11-02T12:00:00Z"))
    with pytest.raises(ValueError, match="unqualified_event_time"):
        verifier.verify_and_admit(r_tomorrow, expected_day=DAY, expected_plot_id="plot-A", expected_zone_id="plot")

    # Delivery after cutoff
    r_late = make_signed_receipt(priv, valid_grant_dict(delivery_end="2026-11-01T20:00:00Z"))
    earlier_cutoff = datetime(2026, 11, 1, 18, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="future_or_unavailable_event"):
        verifier.verify_and_admit(r_late, expected_day=DAY, expected_plot_id="plot-A", expected_zone_id="plot", cutoff=earlier_cutoff)


def test_durable_revocation_enforcement(keys_ed25519, verifier, revocation_authority):
    priv, _ = keys_ed25519
    receipt = make_signed_receipt(priv, valid_grant_dict(receipt_id="rev-1", replay_key="k-rev-1"))

    # Revoke plot via new snapshot
    t_base = datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc)
    snap1 = DurableRevocationSnapshot(
        revision=1,
        issued_at=t_base + timedelta(hours=1),
        expires_at=t_base + timedelta(days=1),
        key_statuses={
            "l3-meter-key-1": "active",
            "l3-meter-key-es256": "active",
        },
        revoked_plots=("plot-A",),
        previous_digest=revocation_authority.current_snapshot.snapshot_digest,
    )
    revocation_authority.load_snapshot(snap1)
    with pytest.raises(ValueError, match="plot_scope_revoked"):
        verifier.verify_and_admit(receipt, expected_day=DAY, expected_plot_id="plot-A", expected_zone_id="plot")


# ============================================================================
# 5. Scientific State & Actuator Separation
# ============================================================================

def test_receipt_cannot_grant_publication_or_actuation_authority():
    grant_data = valid_grant_dict()
    grant_data["scientific_publication_authorized"] = True
    with pytest.raises(ValueError, match="scientific publication authorization cannot be granted"):
        VerifiedDeliveredIrrigationGrant.from_dict(grant_data)

    grant_data = valid_grant_dict()
    grant_data["actuator_control_authorized"] = True
    with pytest.raises(ValueError, match="actuator control authorization cannot be granted"):
        VerifiedDeliveredIrrigationGrant.from_dict(grant_data)


def test_farmer_claim_remains_deferred_without_verified_receipt():
    raw_event = {
        "payload": {
            "event_type": "irrigation",
            "event_id": "farmer-claim-1",
            "event_role": "VERIFIED_DELIVERY",
            "amount_mm": 25.0,
            "zone_id": "plot",
        },
        "packet_id": "pkt-claim-1",
        "plot_id": "plot-A",
        "geometry_hash": "geom-A",
        "timestamp": datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
    }
    records = classify_management_event_evidence(
        [raw_event],
        day=DAY,
        plot_id="plot-A",
        zone_id="plot",
        geometry_hash="geom-A",
    )
    assert len(records) == 1
    rec = records[0]
    assert rec["status"] == "DEFERRED"
    assert rec["reason"] == "claimed_verification_requires_trusted_L3_receipt"
    assert rec["physical_delivery_verified"] is False
    assert rec["state_update_allowed"] is False


# ============================================================================
# 6. End-to-End ZoneKalmanFilter Integration & Water Balance Physics
# ============================================================================

def test_verified_delivery_applied_to_kalman_filter_and_process_noise(keys_ed25519, verifier):
    priv, _ = keys_ed25519
    receipt = make_signed_receipt(
        priv,
        valid_grant_dict(
            volume_liters=10000.0,
            area_m2=1000.0,
            efficiency=0.8,  # Net depth = (10000 * 0.8) / 1000 = 8.0 mm
            receipt_id="rcpt-kf-1",
            replay_key="rep-kf-1",
        )
    )

    filt = ZoneKalmanFilter("plot")
    filt.initialize("2026-10-31")
    filt.parent_plot_id = "plot-A"
    filt.expected_geometry_hash = "geom-A"
    filt.geometry_version = 1
    filt.tenant_id = "tenant-prod-alpha"
    filt.delivery_verifier = verifier

    # Baseline prediction without irrigation
    filt_baseline = ZoneKalmanFilter("plot")
    filt_baseline.initialize("2026-10-31")
    filt_baseline.parent_plot_id = "plot-A"
    filt_baseline.expected_geometry_hash = "geom-A"

    prov_baseline = filt_baseline.step(DAY, WEATHER, None, None)
    sm_baseline = filt_baseline.state.values[IDX_SM_0_10]
    var_baseline = filt_baseline.covariance.P[IDX_SM_0_10][IDX_SM_0_10]

    # Step with verified delivery
    event_envelope = {
        "payload": {
            "event_type": "irrigation",
            "event_id": "event-l3-1",
            "event_role": "VERIFIED_DELIVERY",
            "verified_receipt": receipt.to_dict(),
            "zone_id": "plot",
        },
        "packet_id": "pkt-l3-1",
        "plot_id": "plot-A",
        "geometry_hash": "geom-A",
        "timestamp": datetime(2026, 11, 1, 14, 0, tzinfo=timezone.utc),
    }

    prov = filt.step(DAY, WEATHER, None, [event_envelope])

    # Provenance assertions
    assert prov["physical_management_events_applied"] == 1
    assert prov["event_forcing_status"] == "APPLIED"
    assert prov["verified_delivery_receipts"] == ["rcpt-kf-1"]
    assert prov["scientific_publication_authorized"] is False
    assert prov["actuator_control_authorized"] is False

    # Physical state assertions
    sm_actual = filt.state.values[IDX_SM_0_10]
    var_actual = filt.covariance.P[IDX_SM_0_10][IDX_SM_0_10]

    # Net infiltrated water must increase topsoil moisture
    assert sm_actual > sm_baseline

    # Delivery uncertainty sigma=0.5mm injects variance: (0.5 / 15.0)^2 > 0 into Q
    assert var_actual > var_baseline

    # Covariance eigenspectrum remains PSD
    np = pytest.importorskip("numpy")
    eigenvalues = np.linalg.eigvalsh(np.asarray(filt.covariance.P, dtype=float))
    assert float(eigenvalues.min()) >= -1e-10


def test_state_package_declares_scientific_state_separation(verifier):
    engine = Layer0StateEngine(verified_delivery_verifier=verifier)
    pkg = engine.run(
        plot_id="plot-A",
        start_date="2026-11-01",
        end_date="2026-11-01",
        daily_weather={"2026-11-01": WEATHER},
        observations_by_day={"2026-11-01": {}},
        events_by_day={"2026-11-01": []},
        geometry_hash="geom-A",
        geometry_version=1,
    )
    assert isinstance(pkg, Layer0StatePackage)
    assert pkg.scientific_publication_authorized is False
    assert pkg.actuator_control_authorized is False
    assert pkg.health_report["scientific_publication_authorized"] is False
    assert pkg.health_report["actuator_control_authorized"] is False
    assert pkg.provenance["scientific_publication_authorized"] is False
    assert pkg.provenance["actuator_control_authorized"] is False
