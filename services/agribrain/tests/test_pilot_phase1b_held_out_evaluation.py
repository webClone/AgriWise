"""
Akaloris Scientific Pilot Phase 1B — Synthetic Longitudinal Engineering Qualification Test.

Proves:
  1. File-Backed Telemetry Mechanics: 540 persistent gateway records across 30 days
     with 6-depth profiling and immutable SHA-256 source record digests.
  2. Causal Integrity & Blind Separation: Zero leakage from held-out Station Beta
     into Layer 1 evidence packages, Layer 0 hydrological model, or ASMAE estimators.
  3. Strict Fail-Closed Ground Truth: Missing validation depths raise ValueError
     without default fallback assumptions.
  4. Numerical Integrity: 3-way hash binding enforced across snapshot record, proof,
     and lineage upon reload from disk.
  5. Assimilation Benefit: Descriptively observed error reduction over BOTH the
     archive-only baseline (Config A) and independent Layer 0 hydrological model (Config B)
     in the synthetic benchmark.
  6. Safety Interlock: Zero physical actuator delivery commands under fail-closed lock.

NOTE: This qualification establishes engineering pipeline reliability over a synthetic
multi-depth benchmark. Real-world empirical field validation claims remain held pending
physical sensor logger data exports.
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from services.agribrain.evaluation.phase1b_held_out_validation import (
    run_phase1b_evaluation,
    MAX_ALLOWED_MAE,
    MAX_ALLOWED_RMSE,
    MAX_ALLOWED_ABS_MBE,
    MIN_ALLOWED_95PCT_COVERAGE,
    EVALUATION_CHECKPOINTS,
)
from services.agribrain.datasets.pilot_phase1b_telemetry import (
    DEFAULT_GATEWAY_LOG_PATH,
    ensure_phase1b_gateway_logs,
)
from services.agribrain.layer1_fusion.tests.trust_fixtures import (
    provision_test_issuer_keypair,
)
from services.agribrain.layer1_fusion import truth_bridge as tb
from services.agribrain.layer05_asmae import plot_snapshot_store as asmae_store
from services.agribrain.app.production_delivery_runtime import (
    verified_irrigation_enabled,
    bootstrap_server_verified_irrigation,
    ENABLE_FLAG,
)


@pytest.fixture(autouse=True)
def _setup_phase1b_environment(tmp_path, monkeypatch):
    """Enforce strict observation-only interlock and isolated runtime stores."""
    monkeypatch.setenv(ENABLE_FLAG, "false")
    rev_path = str(tmp_path / "revocation_store_p1b.json")
    store = tb.DurableRevocationStore(persistence_path=rev_path)
    tb.set_revocation_store(store)
    monkeypatch.setattr(asmae_store, "PLOT_SNAPSHOT_ROOT", tmp_path / "snapshots")
    yield
    tb.clear_sensor_receipts()
    tb.clear_publication_receipts()


def test_pilot_phase1b_synthetic_longitudinal_engineering_qualification(tmp_path):
    """
    Complete Phase 1B qualification gate proving all acceptance dimensions:
    File-backed telemetry ingestion, causal integrity, leak-free Layer 0 baseline,
    3-way numerical binding, active scalar Kalman gain, error reduction over both
    baselines, and fail-closed safety interlock.
    """
    issuer = "agriwise:trust:sensor_authority"
    priv_key, pub_key = provision_test_issuer_keypair(issuer)
    tb.register_trusted_issuer_public_key(issuer, pub_key)

    # 1. Dataset Verification: Assert file-backed persistent telemetry log exists
    gateway_file = tmp_path / "gateway_logs_p1b.json"
    records = ensure_phase1b_gateway_logs(gateway_file)
    assert gateway_file.exists()
    # Correct accounting: 30 days * 3 readings/day = 90 intervals; 6 probes = 540 records
    assert len(records) == 540

    # Verify record schema attributes
    sample = records[0]
    assert "source_record_hash" in sample and len(sample["source_record_hash"]) == 64
    assert "depth_cm" in sample and sample["depth_cm"] in (10.0, 15.0, 20.0, 30.0, 40.0, 60.0)
    assert "observed_at_utc" in sample
    assert "ingested_at_utc" in sample
    assert "calibration_profile_id" in sample

    # 2. Execute Phase 1B evaluation protocol across the 3 configurations
    res = run_phase1b_evaluation(
        signing_key=priv_key,
        issuer=issuer,
        log_path=gateway_file,
    )

    metrics = res["metrics"]
    arch = metrics["archive_only"]
    l0 = metrics["kalman_l0"]
    assimilated = metrics["assimilating_asmae"]

    # Verify record accounting breakdown
    assert res["total_telemetry_records"] == 540
    assert res["station_alpha_records"] == 270
    assert res["station_beta_records"] == 270
    assert res["independent_field_validation_claimed"] is False
    assert res["engineering_qualification_passed"] is True

    # 3. Assert Predictive Accuracy against Pre-Declared Acceptance Thresholds
    assert assimilated.mae <= MAX_ALLOWED_MAE, f"MAE {assimilated.mae} > threshold {MAX_ALLOWED_MAE}"
    assert assimilated.rmse <= MAX_ALLOWED_RMSE, f"RMSE {assimilated.rmse} > threshold {MAX_ALLOWED_RMSE}"
    assert abs(assimilated.mbe) <= MAX_ALLOWED_ABS_MBE, f"|MBE| {abs(assimilated.mbe)} > threshold {MAX_ALLOWED_ABS_MBE}"
    assert assimilated.coverage_95pct >= MIN_ALLOWED_95PCT_COVERAGE, f"Coverage {assimilated.coverage_95pct} < threshold {MIN_ALLOWED_95PCT_COVERAGE}"
    assert res["all_thresholds_met"] is True

    # 4. Assert Descriptively Observed Assimilation Benefit Over BOTH Baselines in the Synthetic Benchmark
    # Must outperform BOTH Config A (archive prior) AND Config B (leak-free Layer 0 hydrological model)
    assert res["delta_mae_vs_archive"] > 0.0, f"Expected positive MAE reduction vs archive, got {res['delta_mae_vs_archive']}"
    assert res["delta_rmse_vs_archive"] > 0.0, f"Expected positive RMSE reduction vs archive, got {res['delta_rmse_vs_archive']}"
    assert res["delta_mae_vs_l0"] > 0.0, f"Expected positive MAE reduction vs Layer 0, got {res['delta_mae_vs_l0']}"
    assert res["delta_rmse_vs_l0"] > 0.0, f"Expected positive RMSE reduction vs Layer 0, got {res['delta_rmse_vs_l0']}"
    assert res["assimilation_benefit_verified"] is True

    # Assert active Kalman gain recorded
    kalman_gains = [p.kalman_gain for p in assimilated.point_evaluations]
    assert any(g > 0.0 for g in kalman_gains), "Sensor assimilation must record active Kalman gain > 0"

    # 5. Assert Uncertainty Interval Shrinkage
    # Assimilated posterior uncertainty interval should be narrower than archive prior
    assert assimilated.mean_interval_width < arch.mean_interval_width, (
        f"Assimilated interval width ({assimilated.mean_interval_width}) should shrink relative to archive ({arch.mean_interval_width})"
    )

    # 6. Safety Invariant: Hardware Actuation Interlock
    assert res["actuation_strictly_blocked"] is True
    assert verified_irrigation_enabled() is False
    assert bootstrap_server_verified_irrigation(database=None) is None


def test_pilot_phase1b_missing_ground_truth_depth_fails_closed(tmp_path):
    """
    Negative control proving Finding 2 resolution:
    If any required depth measurement is missing from the held-out validation set,
    extract_held_out_ground_truth MUST fail closed with ValueError rather than
    silently assuming default values.
    """
    from services.agribrain.evaluation.phase1b_held_out_validation import extract_held_out_ground_truth
    from datetime import datetime, timezone

    t_eval = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    # Provide only 10cm and 20cm, omitting required 40cm
    incomplete_records = [
        {
            "station_id": "station_beta",
            "observed_at_utc": t_eval.isoformat(),
            "depth_cm": 10.0,
            "value": 0.35,
        },
        {
            "station_id": "station_beta",
            "observed_at_utc": t_eval.isoformat(),
            "depth_cm": 20.0,
            "value": 0.36,
        },
    ]

    with pytest.raises(ValueError, match="missing required depths"):
        extract_held_out_ground_truth(t_eval, incomplete_records)


def test_pilot_phase1b_rejected_sensor_cannot_alter_asmae_posterior():
    """
    Negative control proving admission-to-ASMAE enforcement:
    A sensor observation rejected or downgraded by Layer 1 (e.g., unverified / unadmitted)
    is strictly excluded by build_asmae_timeseries_from_admitted_evidence(), and
    CANNOT alter the ASMAE biophysical posterior or trigger a Kalman update.
    """
    from datetime import datetime, timezone, timedelta
    from services.agribrain.layer0.observation_packet import (
        ObservationPacket,
        ObservationSource,
        DataStatus,
        QAMetadata,
        UncertaintyModel,
    )
    from services.agribrain.layer0.source_package import Layer0SourcePackage
    from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
    from services.agribrain.layer1_fusion.schemas import Layer1InputBundle
    from services.agribrain.layer05_asmae.schema import ASMAEInput
    from services.agribrain.layer05_asmae.resilient_posterior import (
        estimate_resilient_plot_posterior,
        ARCHIVE_POSTERIOR_CONTRACT_VERSION,
    )
    from services.agribrain.layer05_asmae.config import STATE_NAMES
    from services.agribrain.evaluation.phase1b_held_out_validation import (
        build_asmae_timeseries_from_admitted_evidence,
        PLOT_ID,
        GEOMETRY_HASH,
    )

    t0 = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    # Unverified / unadmitted sensor packet with spoofed high reading (0.5500)
    unverified_pkt = ObservationPacket(
        packet_id="pkt_unverified_spoof_001",
        source=ObservationSource.SENSOR_IOT,
        obs_type="measurement",
        timestamp=t0,
        plot_id=PLOT_ID,
        spatial_scope="point",
        data_status=DataStatus.FALLBACK,  # Fallback data status: diagnostic only, state_update_allowed=False
        qa=QAMetadata(sensor_health=1.0, scene_score=1.0),
        uncertainty=UncertaintyModel(sigmas={"soil_moisture_vwc": 0.015}),
        payload={
            "device_id": "sensor_unregistered_dev",
            "variable": "soil_moisture_vwc",
            "value": 0.5500,
            "unit": "fraction",
            "observation_instant": t0.isoformat(),
            "first_available_at": t0.isoformat(),
            "depth_cm": 15.0,
        },
    )

    pkg0 = Layer0SourcePackage(source_family="sensor", plot_id=PLOT_ID, packets=[unverified_pkt])
    bundle = Layer1InputBundle(
        plot_id=PLOT_ID,
        run_id="run_test_unverified_guard",
        run_timestamp=t0,
        as_of_cutoff=t0,
        window_start=t0 - timedelta(days=1),
        window_end=t0,
        is_historical_replay=True,
        layer0_source_packages={"sensor": [pkg0]},
    )
    engine = Layer1FusionEngine()
    fused_pkg = engine.fuse(bundle)

    # 1. Assert Layer 1 rejected state update authority for this sensor
    sensor_evidence = [e for e in fused_pkg.evidence_items if e.source_family == "sensor"]
    assert not any(e.state_update_allowed for e in sensor_evidence)

    # 2. Assert admission safeguard excludes unadmitted reading from ASMAE timeseries
    timeseries = build_asmae_timeseries_from_admitted_evidence(fused_pkg, [unverified_pkt])
    assert timeseries == []

    # 3. Assert ASMAE posterior remains completely unaltered at archive prior
    archive = {
        "contract_version": ARCHIVE_POSTERIOR_CONTRACT_VERSION,
        "state_means": {
            "lai": 1.70,
            "canopy_water": 0.365,
            "vigor": 0.531,
            "root_zone_water": 0.365,
        },
        "state_covariance": {st: 0.0263 for st in STATE_NAMES},
        "last_update_date": "2026-08-13",
        "geometry_hash": GEOMETRY_HASH,
        "crop_context": {"crop_type": "citrus"},
        "state_support_ledger": {
            st: {
                "source_feature_ids": ["S2_scene_A", "S2_scene_B"],
                "support_status": "archive_conditioned",
                "spatial_support": "plot_level_only",
                "observation_count": 2,
            }
            for st in STATE_NAMES
        },
        "content_distinct_scene_ids": ["S2_scene_A", "S2_scene_B"],
        "historical_validation_status": "validated",
    }
    inp = ASMAEInput(
        plot_id=PLOT_ID,
        run_id="run_safeguard_asmae",
        polygon_geojson={"type": "Polygon", "coordinates": [[[2.65, 36.50], [2.65, 36.51], [2.66, 36.51], [2.65, 36.50]]]},
        geometry_hash=GEOMETRY_HASH,
        start_date=(t0 - timedelta(days=10)).date(),
        end_date=t0.date(),
        layer0_source_packages={"sensor": [pkg0]},
        plot_timeseries=timeseries,  # Strictly admitted timeseries (empty)
        archive_posterior=archive,
        historical_scene_refs=["S2_scene_A", "S2_scene_B"],
        mode="standard",
        crop_context={"crop_type": "citrus"},
    )
    est = estimate_resilient_plot_posterior(inp, as_of=t0)
    post = est["plot_level_posterior"]
    ledger = est["state_support_ledger"]

    # Posterior root-zone water is completely unaltered from archive prior 0.365
    assert float(post["root_zone_water"]["mean"]) == 0.365
    assert float(ledger["root_zone_water"].get("kalman_gain", 0.0)) == 0.0
    assert ledger["root_zone_water"].get("update_mode") == "certified_archive_age_propagation"


def test_pilot_phase1b_mixed_batch_admission_safeguard() -> None:
    """
    Mixed-batch regression: When a batch contains one valid/admitted reading
    and one unadmitted/rejected reading, verify:
      1. Layer 1 admits only the valid reading with state_update_allowed=True.
      2. build_asmae_timeseries_from_admitted_evidence admits strictly the valid reading
         and excludes the rejected reading.
      3. The resulting ASMAE timeseries aggregates only authorized readings.
    """
    import math
    from datetime import datetime, timezone, timedelta
    from services.agribrain.layer0.observation_packet import (
        ObservationPacket,
        ObservationSource,
        DataStatus,
        QAMetadata,
    )
    from services.agribrain.layer0.source_package import Layer0SourcePackage
    from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
    from services.agribrain.layer1_fusion.schemas import Layer1InputBundle
    from services.agribrain.evaluation.phase1b_held_out_validation import (
        build_asmae_timeseries_from_admitted_evidence,
        PLOT_ID,
    )
    from services.agribrain.datasets.pilot_phase1b_telemetry import (
        ensure_phase1b_gateway_logs,
        load_telemetry_observation_packets,
    )

    issuer = "agriwise:trust:sensor_authority"
    priv, _ = provision_test_issuer_keypair(issuer)
    ensure_phase1b_gateway_logs()

    t0 = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    alpha_packets = load_telemetry_observation_packets(
        as_of_cutoff=t0,
        stations=("station_alpha",),
        signing_key=priv,
        issuer=issuer,
    )
    valid_pkt = alpha_packets[0]  # Valid 15cm probe reading, value 0.3375

    # Unverified / unadmitted sensor packet at 30cm
    rejected_pkt = ObservationPacket(
        packet_id="lora_msg_rejected_30cm_test",
        source=ObservationSource.SENSOR_IOT,
        obs_type="measurement",
        timestamp=valid_pkt.timestamp,
        plot_id=PLOT_ID,
        spatial_scope="point",
        data_status=DataStatus.FALLBACK,
        qa=QAMetadata(sensor_health=1.0, scene_score=1.0),
        payload={
            "device_id": "sensor_unregistered_dev_30cm",
            "variable": "soil_moisture_vwc",
            "value": 0.4900,
            "unit": "fraction",
            "depth_cm": 30.0,
        },
    )

    pkg0 = Layer0SourcePackage(source_family="sensor", plot_id=PLOT_ID, packets=[valid_pkt, rejected_pkt])
    bundle = Layer1InputBundle(
        plot_id=PLOT_ID,
        run_id="run_test_mixed_batch",
        run_timestamp=t0,
        as_of_cutoff=t0,
        window_start=t0 - timedelta(days=10),
        window_end=t0,
        is_historical_replay=True,
        layer0_source_packages={"sensor": [pkg0]},
    )
    engine = Layer1FusionEngine()
    fused_pkg = engine.fuse(bundle)

    # Layer 1 admits valid_pkt and rejects rejected_pkt
    admitted_items = [e for e in fused_pkg.evidence_items if e.source_family == "sensor" and e.state_update_allowed]
    assert len(admitted_items) == 1
    assert admitted_items[0].source_id == valid_pkt.packet_id
    assert math.isclose(float(admitted_items[0].value), float(valid_pkt.payload["value"]), abs_tol=1e-5)

    # Helper filters out rejected_pkt and admits strictly valid_pkt
    mixed_batch = [valid_pkt, rejected_pkt]
    timeseries = build_asmae_timeseries_from_admitted_evidence(fused_pkg, mixed_batch)
    assert len(timeseries) == 1
    assert timeseries[0]["soil_moisture"] == round(float(valid_pkt.payload["value"]), 4)
    assert timeseries[0]["source_id"] == "station_alpha"


def test_pilot_phase1b_reused_packet_id_content_mismatch_rejected() -> None:
    """
    Test packet-content identity binding against packet-ID reuse attacks:
    If an attacker reuses an admitted packet ID but provides altered measurement values,
    different timestamps, or tampered payload contents:
      1. The helper recomputes the canonical content digest and compares it with
         the admitted EvidenceItem.content_hash.
      2. Content hash and numerical value equality checks fail-closed.
      3. The tampered packet is excluded from ASMAE timeseries construction.
      4. Feeding the tampered packet produces no state update in ASMAE, leaving the
         posterior at the certified archive prior.
    """
    import copy
    from datetime import datetime, timezone, timedelta
    from services.agribrain.layer0.source_package import Layer0SourcePackage
    from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
    from services.agribrain.layer1_fusion.schemas import Layer1InputBundle
    from services.agribrain.evaluation.phase1b_held_out_validation import (
        build_asmae_timeseries_from_admitted_evidence,
        PLOT_ID,
        GEOMETRY_HASH,
    )
    from services.agribrain.datasets.pilot_phase1b_telemetry import (
        ensure_phase1b_gateway_logs,
        load_telemetry_observation_packets,
    )
    from services.agribrain.layer05_asmae.schema import ASMAEInput
    from services.agribrain.layer05_asmae.resilient_posterior import (
        estimate_resilient_plot_posterior,
        ARCHIVE_POSTERIOR_CONTRACT_VERSION,
    )
    from services.agribrain.layer05_asmae.config import STATE_NAMES

    issuer = "agriwise:trust:sensor_authority"
    priv, _ = provision_test_issuer_keypair(issuer)
    ensure_phase1b_gateway_logs()

    t0 = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    alpha_packets = load_telemetry_observation_packets(
        as_of_cutoff=t0,
        stations=("station_alpha",),
        signing_key=priv,
        issuer=issuer,
    )
    valid_pkt = alpha_packets[0]  # Valid 15cm probe reading, value 0.3375

    pkg0 = Layer0SourcePackage(source_family="sensor", plot_id=PLOT_ID, packets=[valid_pkt])
    bundle = Layer1InputBundle(
        plot_id=PLOT_ID,
        run_id="run_test_content_binding",
        run_timestamp=t0,
        as_of_cutoff=t0,
        window_start=t0 - timedelta(days=10),
        window_end=t0,
        is_historical_replay=True,
        layer0_source_packages={"sensor": [pkg0]},
    )
    engine = Layer1FusionEngine()
    fused_pkg = engine.fuse(bundle)

    # Verify that valid_pkt was admitted in fused_pkg
    admitted = [e for e in fused_pkg.evidence_items if e.source_family == "sensor" and e.state_update_allowed]
    assert len(admitted) == 1
    ev = admitted[0]
    assert ev.source_id == valid_pkt.packet_id
    assert ev.content_hash is not None

    # Construct spoofed packet that REUSES the admitted packet_id, but tampers with value
    spoofed_pkt = copy.deepcopy(valid_pkt)
    spoofed_pkt.payload["value"] = 0.5500  # Tampered measurement value

    # Helper must detect content mismatch (value and canonical hash) and reject spoofed packet
    timeseries_spoofed = build_asmae_timeseries_from_admitted_evidence(fused_pkg, [spoofed_pkt])
    assert timeseries_spoofed == [], "Spoofed packet with reused ID but altered content must be rejected"

    # Also test mixed list: valid packet + spoofed packet with reused ID
    timeseries_mixed = build_asmae_timeseries_from_admitted_evidence(fused_pkg, [valid_pkt, spoofed_pkt])
    assert len(timeseries_mixed) == 1
    # Only the authentic value is ingested
    assert timeseries_mixed[0]["soil_moisture"] == round(float(valid_pkt.payload["value"]), 4)

    # Assert ASMAE posterior given the spoofed packet receives zero Kalman update
    archive = {
        "contract_version": ARCHIVE_POSTERIOR_CONTRACT_VERSION,
        "state_means": {
            "lai": 1.70,
            "canopy_water": 0.365,
            "vigor": 0.531,
            "root_zone_water": 0.365,
        },
        "state_covariance": {st: 0.0263 for st in STATE_NAMES},
        "last_update_date": "2026-08-13",
        "geometry_hash": GEOMETRY_HASH,
        "crop_context": {"crop_type": "citrus"},
        "state_support_ledger": {
            st: {
                "source_feature_ids": ["S2_scene_A", "S2_scene_B"],
                "support_status": "archive_conditioned",
                "spatial_support": "plot_level_only",
                "observation_count": 2,
            }
            for st in STATE_NAMES
        },
        "content_distinct_scene_ids": ["S2_scene_A", "S2_scene_B"],
        "historical_validation_status": "validated",
    }
    inp = ASMAEInput(
        plot_id=PLOT_ID,
        run_id="run_spoof_content_asmae",
        polygon_geojson={"type": "Polygon", "coordinates": [[[2.65, 36.50], [2.65, 36.51], [2.66, 36.51], [2.65, 36.50]]]},
        geometry_hash=GEOMETRY_HASH,
        start_date=(t0 - timedelta(days=10)).date(),
        end_date=t0.date(),
        layer0_source_packages={"sensor": [pkg0]},
        plot_timeseries=timeseries_spoofed,
        archive_posterior=archive,
        historical_scene_refs=["S2_scene_A", "S2_scene_B"],
        mode="standard",
        crop_context={"crop_type": "citrus"},
    )
    est = estimate_resilient_plot_posterior(inp, as_of=t0)
    post = est["plot_level_posterior"]
    ledger = est["state_support_ledger"]

    assert float(post["root_zone_water"]["mean"]) == 0.365
    assert float(ledger["root_zone_water"].get("kalman_gain", 0.0)) == 0.0
    assert ledger["root_zone_water"].get("update_mode") == "certified_archive_age_propagation"


def test_pilot_phase1b_tampered_packet_depth_or_availability_cannot_alter_qualified_input() -> None:
    """Batch C verification: Changing raw packet depth or availability after admission cannot change qualified ASMAE input."""
    import copy
    from datetime import datetime, timezone, timedelta
    from services.agribrain.layer0.source_package import Layer0SourcePackage
    from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
    from services.agribrain.layer1_fusion.schemas import Layer1InputBundle
    from services.agribrain.evaluation.phase1b_held_out_validation import (
        build_asmae_timeseries_from_admitted_evidence,
        PLOT_ID,
    )
    from services.agribrain.datasets.pilot_phase1b_telemetry import (
        ensure_phase1b_gateway_logs,
        load_telemetry_observation_packets,
    )

    issuer = "agriwise:trust:sensor_authority"
    priv, _ = provision_test_issuer_keypair(issuer)
    ensure_phase1b_gateway_logs()

    t0 = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    alpha_packets = load_telemetry_observation_packets(
        as_of_cutoff=t0,
        stations=("station_alpha",),
        signing_key=priv,
        issuer=issuer,
    )
    assert len(alpha_packets) >= 3

    pkg0 = Layer0SourcePackage(source_family="sensor", plot_id=PLOT_ID, packets=alpha_packets)
    bundle = Layer1InputBundle(
        plot_id=PLOT_ID,
        run_id="run_batch_c_tamper_test",
        run_timestamp=t0,
        as_of_cutoff=t0,
        window_start=t0 - timedelta(days=10),
        window_end=t0,
        is_historical_replay=True,
        layer0_source_packages={"sensor": [pkg0]},
    )
    engine = Layer1FusionEngine()
    fused_pkg = engine.fuse(bundle)

    # Baseline qualified ASMAE timeseries
    baseline_timeseries = build_asmae_timeseries_from_admitted_evidence(fused_pkg, alpha_packets)
    assert len(baseline_timeseries) > 0

    # Tamper with raw packets AFTER admission:
    # 1. Modify raw depth in packet payload
    # 2. Modify raw first_available_at in packet payload
    # 3. Modify raw observation_instant in packet payload
    tampered_packets = []
    for pkt in alpha_packets:
        p_copy = copy.deepcopy(pkt)
        p_copy.payload["depth_cm"] = 999.0
        p_copy.payload["first_available_at"] = "2099-12-31T23:59:59Z"
        p_copy.payload["observation_instant"] = "1970-01-01T00:00:00Z"
        tampered_packets.append(p_copy)

    # Recompute timeseries using the tampered raw packets
    tampered_timeseries = build_asmae_timeseries_from_admitted_evidence(fused_pkg, tampered_packets)

    # Batch C assertion: qualified ASMAE input is identical because depth is derived from
    # registered device support and availability from signed receipts, not raw packet payload.
    assert len(tampered_timeseries) == len(baseline_timeseries)
    for b_rec, t_rec in zip(baseline_timeseries, tampered_timeseries):
        assert b_rec["soil_moisture"] == t_rec["soil_moisture"]
        assert b_rec["timestamp"] == t_rec["timestamp"]
        assert b_rec["ingested_at"] == t_rec["ingested_at"]
        assert b_rec["profile_coverage"] == t_rec["profile_coverage"]


def test_pilot_phase1b_missing_registration_or_unverified_receipt_fails_closed() -> None:
    """Batch C verification: Unregistered sensors or missing availability receipts are excluded with strict boundaries."""
    from datetime import datetime, timezone, timedelta
    from services.agribrain.layer0.observation_packet import (
        ObservationPacket,
        ObservationSource,
        DataStatus,
        QAMetadata,
    )
    from services.agribrain.layer0.source_package import Layer0SourcePackage
    from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
    from services.agribrain.layer1_fusion.schemas import Layer1InputBundle
    from services.agribrain.evaluation.phase1b_held_out_validation import (
        build_asmae_timeseries_from_admitted_evidence,
        PLOT_ID,
    )

    t0 = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Unregistered device packet
    unregistered_pkt = ObservationPacket(
        packet_id="lora_msg_unregistered_probe",
        source=ObservationSource.SENSOR_IOT,
        obs_type="measurement",
        timestamp=t0,
        plot_id=PLOT_ID,
        spatial_scope="point",
        data_status=DataStatus.OBSERVED,
        qa=QAMetadata(sensor_health=1.0, scene_score=1.0),
        payload={
            "device_id": "sensor_unregistered_probe_xyz",
            "variable": "soil_moisture_vwc",
            "value": 0.3500,
            "unit": "fraction",
        },
    )

    pkg0 = Layer0SourcePackage(source_family="sensor", plot_id=PLOT_ID, packets=[unregistered_pkt])
    bundle = Layer1InputBundle(
        plot_id=PLOT_ID,
        run_id="run_batch_c_unregistered",
        run_timestamp=t0,
        as_of_cutoff=t0,
        window_start=t0 - timedelta(days=10),
        window_end=t0,
        is_historical_replay=True,
        layer0_source_packages={"sensor": [pkg0]},
    )
    engine = Layer1FusionEngine()
    fused_pkg = engine.fuse(bundle)

    # Must be excluded because device registration is absent
    ts = build_asmae_timeseries_from_admitted_evidence(fused_pkg, [unregistered_pkt])
    assert ts == [], "Unregistered sensor without registered depth support must fail closed and be excluded"

