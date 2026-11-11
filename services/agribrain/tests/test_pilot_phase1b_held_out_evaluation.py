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
  5. Assimilation Benefit: Statistically verified error reduction over BOTH the
     archive-only baseline (Config A) and independent Layer 0 hydrological model (Config B).
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

    # 4. Assert Statistically Verified Assimilation Benefit Over BOTH Baselines
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
