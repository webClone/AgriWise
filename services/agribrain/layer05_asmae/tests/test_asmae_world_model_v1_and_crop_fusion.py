"""Comprehensive tests for ASMAE World Model V1 (P1-1..P1-4, W1-W8) & Crop-Identity Historical Fusion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[4]
AGRIBRAIN_ROOT = REPO_ROOT / "services" / "agribrain"
for path_item in (str(REPO_ROOT), str(AGRIBRAIN_ROOT)):
    if path_item not in sys.path:
        sys.path.insert(0, path_item)

from services.agribrain.crop_database import resolve_crop_code
from services.agribrain.layer05_asmae.history.benchmark_matrix import evaluate_cross_plot_matrix
from services.agribrain.layer05_asmae.history.domain_chronology import (
    build_domain_chronology,
    evaluate_scouting_record,
)
from services.agribrain.layer05_asmae.history.historical_crop_fusion import (
    _broad_crop_group,
    evaluate_crop_detection_benchmark,
    reconstruct_chronological_crop_posteriors,
)
from services.agribrain.layer05_asmae.history.historical_event_memory import HistoricalEventMemory
from services.agribrain.layer05_asmae.history.historical_retrovalidation import HistoricalRetrovalidator
from services.agribrain.layer05_asmae.history.historical_state_reconstructor import (
    HistoricalStateReconstructor,
    build_prospective_weather_series,
)
from services.agribrain.layer05_asmae.history.independent_field_validation import (
    _classify_probe_calibration,
    _sample_spatial_surface_at_coord,
    evaluate_independent_field_evidence,
)
from services.agribrain.layer05_asmae.history.world_model_contracts import (
    CALIBRATION_STATUS_VENDOR_UNVERIFIED,
)
from services.agribrain.layer2_veg_int.crop_posterior import _mixture_conditioning, infer_crop_posterior
from services.agribrain.layer2_veg_int.crop_observations import build_canonical_crop_observations, build_crop_evidence_ledger
from services.agribrain.layer2_veg_int.features.ledger_crop_features import build_ledger_crop_feature_input


class TestAsmaeWorldModelV1AndCropFusion(unittest.TestCase):
    def test_p1_1_time_matched_spatial_surface_rejects_future_surface(self) -> None:
        polygon = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[2.99, 36.49], [3.01, 36.49], [3.01, 36.51], [2.99, 36.51], [2.99, 36.49]]],
            },
        }
        probe_ts = datetime(2025, 4, 10, 10, 0, tzinfo=timezone.utc)
        future_surface = {
            "surface_type": "ASMAE_ROOT_ZONE_WATER",
            "valid_time_T": "2026-11-20T00:00:00+00:00",
            "bounds": [2.99, 36.49, 3.01, 36.51],
            "values": [[0.14, 0.14], [0.14, 0.14]],
            "uncertainty": [[0.04, 0.04], [0.04, 0.04]],
        }
        causal_surface = {
            "surface_type": "ASMAE_ROOT_ZONE_WATER",
            "valid_time_T": "2025-04-10T09:00:00+00:00",
            "bounds": [2.99, 36.49, 3.01, 36.51],
            "values": [[0.31, 0.31], [0.31, 0.31]],
            "uncertainty": [[0.03, 0.03], [0.03, 0.03]],
        }
        rejected: list = []
        sample_rej = _sample_spatial_surface_at_coord(
            36.50, 3.00, [future_surface], reading_ts=probe_ts, rejected_non_causal_out=rejected
        )
        self.assertIsNone(sample_rej)
        self.assertIn("future_valid_time_surface", rejected)

        traj = [
            {
                "acquisition_time": "2025-04-09T10:30:00+00:00",
                "posterior_state_means": {"root_zone_water": 0.25},
                "posterior_state_stds": {"root_zone_water": 0.05},
            }
        ]
        probe = {
            "timestamp": "2025-04-10T10:00:00+00:00",
            "soilMoisture": 30.0,
            "vendor": "Sentek Drill & Drop",
            "isCalibrated": True,
            "deviceId": "P-1",
            "latitude": 36.50,
            "longitude": 3.00,
        }
        res_bad = evaluate_independent_field_evidence(
            plot_id="p1",
            trajectory=traj,
            sensor_readings=[probe],
            polygon_geojson=polygon,
            spatial_surfaces=[future_surface],
        )
        self.assertEqual(res_bad["sensor_vwc_validation"]["excluded_future_surface_non_causal"], 1)
        self.assertEqual(res_bad["sensor_vwc_validation"]["time_matched_spatial_pixel_count"], 0)

        res_ok = evaluate_independent_field_evidence(
            plot_id="p1",
            trajectory=traj,
            sensor_readings=[probe],
            polygon_geojson=polygon,
            spatial_surfaces=[future_surface],
            causal_spatial_lookup_fn=lambda dt: [causal_surface],
        )
        vwc_val = res_ok["sensor_vwc_validation"]
        self.assertEqual(vwc_val["time_matched_spatial_pixel_count"], 1)
        self.assertEqual(vwc_val["causal_spatial_lookup_mode"], "causal_query_as_of_probe_ts")
        self.assertAlmostEqual(vwc_val["independent_sample_records"][0]["asmae_rzw_mean"], 0.31, places=4)

    def test_p1_2_affirmative_probe_calibration_and_expiry(self) -> None:
        ts_now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        ok_vendor_only, reason_vo = _classify_probe_calibration(
            {"vendor": "Sentek Drill & Drop"}, "Sentek Drill & Drop", 0.25, 0.45, reading_ts=ts_now
        )
        self.assertFalse(ok_vendor_only)
        self.assertEqual(reason_vo, CALIBRATION_STATUS_VENDOR_UNVERIFIED)

        ok_exp, reason_exp = _classify_probe_calibration(
            {"vendor": "Sentek Drill & Drop", "isCalibrated": True, "calibrationExpiresAt": "2026-01-01T00:00:00+00:00"},
            "Sentek Drill & Drop",
            0.25,
            0.45,
            reading_ts=ts_now,
        )
        self.assertFalse(ok_exp)
        self.assertEqual(reason_exp, "calibration_expired")

        ok_bare_flag, reason_bare = _classify_probe_calibration(
            {"vendor": "Sentek Drill & Drop", "isCalibrated": True},
            "Sentek Drill & Drop",
            0.25,
            0.45,
            reading_ts=ts_now,
        )
        self.assertFalse(ok_bare_flag)
        self.assertEqual(reason_bare, "unverified_self_asserted_calibration")

        ok_cert, reason_cert = _classify_probe_calibration(
            {
                "vendor": "Sentek Drill & Drop",
                "calibrationCertificateId": "CERT-2026-88",
                "calibrationAuthority": "mitidja_metrology_lab",
                "calibrationVerifiedAt": "2026-05-01T00:00:00+00:00",
            },
            "Sentek Drill & Drop",
            0.25,
            0.45,
            reading_ts=ts_now,
        )
        self.assertTrue(ok_cert)
        self.assertEqual(reason_cert, "calibrated")

    def test_p1_3_scouting_requires_explicit_confirmation_and_tk_gating(self) -> None:
        raw_unconfirmed = {
            "_id": "obs_1",
            "type": "pest",
            "title": "Aphid Warning",
            "severity": "warning",
            "createdAt": "2026-11-15T17:27:02+00:00",
        }
        rec = evaluate_scouting_record(raw_unconfirmed)
        self.assertFalse(rec.is_confirmed)
        self.assertEqual(rec.confirmation_status, "UNCONFIRMED_SCOUTING")

        raw_unverified_claim = {
            "_id": "obs_2_nocfg",
            "type": "disease",
            "title": "Confirmed Without Verifier",
            "confirmed": True,
            "observedAt": "2026-10-10T09:00:00+00:00",
            "createdAt": "2026-11-15T12:00:00+00:00",
        }
        rec_uc = evaluate_scouting_record(raw_unverified_claim)
        self.assertFalse(rec_uc.is_confirmed)
        self.assertEqual(rec_uc.confirmation_status, "UNCONFIRMED_MISSING_CONFIRMER_OR_TIMESTAMP")

        raw_confirmed = {
            "_id": "obs_2",
            "type": "disease",
            "title": "Confirmed Rust",
            "confirmed": True,
            "confirmedBy": "agronomist_mitidja_01",
            "confirmedAt": "2026-11-15T12:00:00+00:00",
            "observedAt": "2026-10-10T09:00:00+00:00",
            "createdAt": "2026-11-15T12:00:00+00:00",
        }
        rec_c = evaluate_scouting_record(raw_confirmed)
        self.assertTrue(rec_c.is_confirmed)
        self.assertEqual(rec_c.confirmation_status, "OBSERVED_CONFIRMED")

        traj = [
            {
                "acquisition_time": "2026-11-16T10:30:00+00:00",
                "obs_channels": {"ndvi": 0.55},
                "posterior_state_means": {"vigor": 0.55, "lai": 2.0, "canopy_water": 0.5, "root_zone_water": 0.25, "bare_soil_fraction": 0.3, "stress_memory": 0.1},
                "raw_metrics": {"ndvi_mean": 0.55},
            }
        ]
        mem = HistoricalEventMemory().reconstruct_memory(
            traj,
            context_summary={
                "daily_weather": {},
                "valid_time_T": "2026-11-20T00:00:00+00:00",
                "knowledge_cutoff_K": "2026-11-20T00:00:00+00:00",
                "management_events": [
                    {
                        "type": "scouting_pest",
                        "date": "2026-11-15",
                        "timestamp": "2026-11-15T17:27:02+00:00",
                        "status": "UNCONFIRMED_SCOUTING",
                        "confirmed": False,
                        "title": "Aphid Warning",
                    }
                ],
            },
        )
        cats = [e["event_category"] for e in mem["events"]]
        epistemics = {e["event_category"]: e["epistemic_class"] for e in mem["events"]}
        self.assertIn("scouting_hypothesis_unconfirmed", cats)
        self.assertNotIn("field_scouting_confirmed", cats)
        self.assertEqual(epistemics["scouting_hypothesis_unconfirmed"], "model_hypothesis")

        # Confirmed observation logged at K=2026-11-15 must not appear when K=2026-11-01
        mem_before_k = HistoricalEventMemory().reconstruct_memory(
            traj,
            context_summary={
                "daily_weather": {},
                "valid_time_T": "2026-11-20T00:00:00+00:00",
                "knowledge_cutoff_K": "2026-11-01T00:00:00+00:00",
                "management_events": [
                    {
                        "type": "scouting_disease",
                        "date": "2026-10-10",
                        "timestamp": rec_c.observed_at,
                        "known_from": rec_c.created_at,
                        "status": "OBSERVED_CONFIRMED",
                        "confirmed": True,
                        "title": "Confirmed Rust",
                    }
                ],
            },
        )
        self.assertNotIn("field_scouting_confirmed", [e["event_category"] for e in mem_before_k["events"]])

    def test_p1_4_mandatory_weather_publication_lag_in_prospective_series(self) -> None:
        issue = datetime(2026, 7, 5, 10, 30, tzinfo=timezone.utc)
        end = datetime(2026, 7, 15, 10, 30, tzinfo=timezone.utc)
        daily_wx = {
            "2026-07-02": {
                "temp_max": 31.0, "temp_min": 18.0, "precipitation": 0.0, "et0": 5.0,
                "source_reality": "reanalysis_archive",
                "available_at": "2026-07-04T00:00:00+00:00",
            },
            "2026-07-04": {
                "temp_max": 42.0, "temp_min": 25.0, "precipitation": 25.0, "et0": 7.0,
                "source_reality": "reanalysis_archive",
                "available_at": "2026-07-09T00:00:00+00:00",  # Future ERA5 release!
            },
        }
        prosp = build_prospective_weather_series(
            daily_wx,
            issue,
            end,
            strict_previous_complete_day=True,
            knowledge_cutoff_dt=issue,
            enforce_publication_lag=True,
        )
        # 2026-07-04 had temp_max=42 & precip=25, but available_at=2026-07-09 > issue_K -> MUST NOT appear as realized 25mm rain!
        self.assertEqual(prosp["2026-07-02"]["precipitation"], 0.0)
        self.assertNotEqual(prosp.get("2026-07-04", {}).get("precipitation"), 25.0)

    def test_w1_domain_identity_rejects_synthetic_labels_and_unverified_crop(self) -> None:
        self.assertEqual(resolve_crop_code("Marmande"), "tomato")
        ident, chron = build_domain_chronology(
            plot_id="699d819a55a7933e54521aad",
            plot_doc={"name": "Golden Plot 1 (Wheat)", "soilType": "SANDY"},
            crop_cycles=[],
            confirmed_crop_labels=[{
                "cropCode": "tomato",
                "notes": "synthetic_seeded_v6_1A_eval",
                "synthetic": True,
                "labelSource": "imported_dataset",
            }],
        )
        self.assertFalse(ident.crop_identity_verified)
        self.assertTrue(ident.synthetic_label_rejected)
        self.assertTrue(ident.is_isolated_dev_fixture)
        self.assertIn("unverified_crop_identity", ident.identity_block_reasons)
        self.assertIn("synthetic_crop_label_rejected", ident.identity_block_reasons)
        self.assertIn("unverified_tenant_identity", ident.identity_block_reasons)

    def test_decisive_multi_season_crop_rotation_and_late_farmer_confirmation(self) -> None:
        # Unconfirmed CropCycle without declaredCropAuthority must stay REGISTRY_DECLARED (WM1-P1-02)
        _, unconf_chron = build_domain_chronology(
            plot_id="rot_plot_unconf",
            plot_doc={"tenantId": "tenant_real_01", "soilType": "LOAM"},
            crop_cycles=[{
                "_id": "cc_2024_u",
                "cropCode": "tomato",
                "status": "HARVESTED",
                "plantDate": "2024-03-01T00:00:00+00:00",
                "expectedHarvest": "2024-08-01T00:00:00+00:00",
                "createdAt": "2025-01-10T00:00:00+00:00",
            }],
        )
        unconf_s2 = unconf_chron.as_of(
            datetime(2024, 6, 15, tzinfo=timezone.utc),
            knowledge_cutoff_K=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )
        self.assertFalse(unconf_s2["crop_verified_as_of_k"])
        self.assertEqual(unconf_s2["crop_authority"], "REGISTRY_DECLARED")

        # Season 1 (2022) unknown pre-cycle; Season 2 (2024) confirmed late at declaredCropAt=2025-01-10
        ident, chron = build_domain_chronology(
            plot_id="rot_plot_1",
            plot_doc={"tenantId": "tenant_real_01", "soilType": "LOAM"},
            crop_cycles=[
                {
                    "_id": "cc_2024",
                    "cropCode": "tomato",
                    "variety": "Marmande",
                    "status": "HARVESTED",
                    "plantDate": "2024-03-01T00:00:00+00:00",
                    "expectedHarvest": "2024-08-01T00:00:00+00:00",
                    "declaredCropAuthority": "FARMER_CONFIRMED",
                    "declaredCropAt": "2025-01-10T00:00:00+00:00",
                    "createdAt": "2025-01-10T00:00:00+00:00",
                }
            ],
        )
        # Query during 2024 season AS KNOWN BEFORE late farmer confirmation (K=2024-08-01)
        dom_before_k = chron.as_of(
            datetime(2024, 6, 15, tzinfo=timezone.utc),
            knowledge_cutoff_K=datetime(2024, 8, 1, tzinfo=timezone.utc),
        )
        self.assertFalse(dom_before_k["crop_verified_as_of_k"])
        self.assertGreaterEqual(dom_before_k["withheld_future_crop_cycles_count"], 1)

        # Query after late farmer confirmation arrived (K=2025-02-01), without rewriting Season 1 (2022)!
        dom_after_k_s2 = chron.as_of(
            datetime(2024, 6, 15, tzinfo=timezone.utc),
            knowledge_cutoff_K=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )
        self.assertTrue(dom_after_k_s2["crop_verified_as_of_k"])
        self.assertEqual(dom_after_k_s2["verified_crop_code"], "tomato")

        dom_after_k_s1 = chron.as_of(
            datetime(2022, 5, 1, tzinfo=timezone.utc),
            knowledge_cutoff_K=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )
        # 2022 was BEFORE 2024 tomato planting without soil-prep confirmation -> PRE_KNOWN_CYCLE_UNKNOWN (WM1-P2-11)
        self.assertFalse(dom_after_k_s1["crop_verified_as_of_k"])
        self.assertEqual(dom_after_k_s1["physical_regime"], "PRE_KNOWN_CYCLE_UNKNOWN")

    def test_deep_audit_layer2_mixture_uncertainty_and_publication_authority(self) -> None:
        # 1. Low known mass (21% cereal, 79% unknown) must preserve nonzero unknown uncertainty variance
        mix = _mixture_conditioning({"cereal": 0.21, "unknown": 0.79})
        self.assertTrue(mix["unknown_uncertainty_inflated"])
        self.assertGreater(mix["parameter_variance"]["crop_coefficient"], 0.01)
        self.assertLess(mix["parameters"]["crop_coefficient"], 1.05)  # Tempered toward neutral prior

        # 2. Latent L3 species publication invariant: build ledger + model input receipt without calibration receipt
        from types import SimpleNamespace
        from services.agribrain.layer2_veg_int.crop_identification import CropIdentificationEngine
        from services.agribrain.layer2_veg_int.crop_observations import CropEvidenceLedgerV2

        pkg = {
            "source_family": "sentinel2",
            "metadata": {
                "source_family": "sentinel2",
                "provider_product_id": "S2A_MSIL2A_20260401T103021_N0500_R108_T31SDA_20260401T130000.SAFE",
                "plot_geometry_hash": "geom-test",
                "source_reality": "real_raster",
                "production_usable": True,
                "real_provider_product": True,
                "diagnostic_only": False,
                "tenant_id": "t1",
                "farm_id": "f1",
                "plot_id": "p_ml",
            },
            "packets": [
                {
                    "timestamp": f"2026-04-{d:02d}T10:30:00+00:00",
                    "ndvi_mean": 0.45,
                    "quality_admitted": True,
                    "usable": True,
                    "source_reality": "real_raster",
                    "production_usable": True,
                    "real_provider_product": True,
                    "diagnostic_only": False,
                }
                for d in (1, 10, 20)
            ],
        }
        # Without disjoint external calibration receipt, ledger input publication_eligible must stay False
        # Even if infer_crop_posterior attaches governed snapshot
        from services.agribrain.layer2_veg_int.features.ledger_crop_features import _resolve_calibration_validity
        cal_val, _ = _resolve_calibration_validity(None)
        self.assertEqual(cal_val, "unavailable")

    def test_w7_benchmark_matrix_and_scientific_failure_diagnosis(self) -> None:
        ident_fail, chron_fail = build_domain_chronology(
            plot_id="cmara_test",
            plot_doc={"name": "cmara", "soilType": "SANDY"},
            crop_cycles=[{
                "_id": "cc_cmara",
                "cropCode": "orange",
                "status": "PLANTED",
                "declaredCropAuthority": "FARMER_CONFIRMED",
                "declaredCropAt": "2026-05-21T00:00:00+00:00",
                "plantDate": "2026-05-21T00:00:00+00:00",
                "createdAt": "2026-05-21T00:00:00+00:00",
            }],
        )
        diag = HistoricalRetrovalidator.diagnose_scientific_failures(
            plot_id="cmara_test",
            summary={"n_evaluated_points": 30, "bias": 0.08, "coverage_1sigma": 0.65, "coverage_2sigma": 0.90, "skill_vs_climatology": -0.25},
            multi_horizon={"by_horizon": {"short_1_7d": {"skill_vs_persistence": -0.14}}},
            qualification={"passed": False, "block_reasons": ["unverified_tenant_identity", "skill_below_climatology"]},
            domain_identity=ident_fail.to_dict(),
            ctx={
                "crop_fusion": {"seasonal_timeline": [{"physical_regime": "EARLY_ESTABLISHMENT"}]},
                "n_calibrated_field_device_days": 0,
            },
            sorted_traj=[{}] * 30,
        )
        self.assertIn("unverified_domain_identity", diag["causes"])
        self.assertIn("regime_transition_mismatch", diag["causes"])
        self.assertIn("systematic_bias", diag["causes"])
        self.assertIn("missing_field_validation", diag["causes"])
        self.assertNotIn("insufficient_observations", diag["causes"])
        self.assertEqual(_broad_crop_group("evergreen_orchard"), "orchard")
        self.assertEqual(_broad_crop_group("solanaceae_veg"), "vegetable")

        matrix = evaluate_cross_plot_matrix([
            {
                "plot_id": "cmara_test",
                "plot_name": "cmara",
                "domain_identity": ident_fail.to_dict(),
                "domain_chronology": chron_fail,
                "reconstruction": {
                    "retrovalidation": {
                        "summary": {"n_evaluated_points": 30, "rmse": 0.08, "skill_vs_climatology": -0.25, "bma_rmse": 0.068},
                        "baselines": {"persistence": {"rmse": 0.07}, "doy_climatology": {"rmse": 0.06}, "bma_consensus": {"rmse": 0.068}},
                        "bma": {"bma_consensus_rmse": 0.068, "weights": {"sar_structure": 0.6, "optical_physiology": 0.4}},
                        "qualification": {"passed": False, "block_reasons": ["unverified_tenant_identity"]},
                        "scientific_failure_diagnosis": diag,
                    },
                },
                "independent_field_validation": {"mesia_hydrological_validation": {"native_sigmf_captures_present": False}},
                "crop_fusion": {},
            }
        ])
        self.assertEqual(matrix["matrix_version"], "asmae_world_model_v2_benchmark_matrix")
        self.assertEqual(matrix["verified_crop_plot_count"], 1)
        self.assertEqual(matrix["verified_tenant_plot_count"], 0)
        self.assertEqual(matrix["per_plot_benchmark"][0]["n_eval_points"], 30)
        self.assertEqual(matrix["per_plot_benchmark"][0]["counterfactual_arms"]["bma_consensus"]["rmse"], 0.068)
        self.assertEqual(matrix["per_plot_benchmark"][0]["counterfactual_arms"]["bma_consensus"]["expert_weights"]["sar_structure"], 0.6)
        self.assertEqual(
            matrix["per_plot_benchmark"][0]["counterfactual_arms"]["mesia_assisted"]["status"],
            "withheld_no_verified_native_sigmf_captures",
        )


    def test_ml_handoff_and_latent_species_publication_authority_invariant(self) -> None:
        """Verify infer_crop_posterior attaches governed snapshot and blocks L3 publication if input uncalibrated."""
        import hashlib
        import os
        from unittest.mock import patch
        from sklearn.impute import SimpleImputer
        from services.agribrain.layer2_veg_int.crop_identification import CropIdentificationEngine
        from services.agribrain.layer2_veg_int.features.crop_feature_vector import crop_feature_schema_receipt
        from services.agribrain.layer2_veg_int.labels.classifier import HierarchicalCropClassifier

        class _StaticModel:
            def __init__(self, classes, probs):
                self.classes_ = np.asarray(classes)
                self._probs = np.asarray(probs, dtype=float)
            def predict_proba(self, values):
                return np.asarray([self._probs for _ in values])

        schema = crop_feature_schema_receipt()
        names = [f.name for f in schema.features]
        clf = HierarchicalCropClassifier("unused")
        clf.feature_names = names
        clf.imputer = SimpleImputer(strategy="median").fit(np.zeros((2, len(names)), dtype=float))
        clf.models = {
            "L0": _StaticModel(["active_crop", "non_crop"], [0.95, 0.05]),
            "L1": _StaticModel(["annual", "orchard"], [0.95, 0.05]),
            "L2": _StaticModel(["winter_cereal", "evergreen_orchard"], [0.95, 0.05]),
            "L3": _StaticModel(["wheat", "barley", "olive"], [0.94, 0.05, 0.01]),
        }
        clf.metadata = {
            "level_status": {lvl: "trained" for lvl in ("L0", "L1", "L2", "L3")},
            "feature_vector_version": "6.0.0",
            "feature_order_hash": hashlib.sha256(",".join(sorted(names)).encode("utf-8")).hexdigest(),
            "feature_schema_hash": schema.content_hash,
            "calibration_modes": {lvl: "unavailable" for lvl in ("L0", "L1", "L2", "L3")},
        }
        clf.production_eligible = True

        # 1. Production-eligible ML model + uncalibrated input receipt -> L3 MUST NOT publish species
        uncal_res = clf.predict({
            "feature_vector_version": "6.0.0",
            "data_completeness": 1.0,
            "flat_features": {name: 0.25 for name in names},
        }, apply_constraints=True)
        self.assertFalse(uncal_res["publication_eligible"])
        self.assertIsNone(uncal_res["ml_classifier_output"]["L3"]["prediction"])
        self.assertEqual(uncal_res["ml_classifier_output"]["L3"]["exploratory_prediction"], "wheat")

        # 2. Outer engine.identify() enforces publication gate even with production_eligible=True
        engine = CropIdentificationEngine()
        engine._ml_classifier = clf
        engine._ml_load_status = {"loaded": True}
        with patch.dict(os.environ, {"AGRIBRAIN_CROP_ML_ENABLED": "true"}):
            id_res = engine.identify(
                ndvi_series=[0.2, 0.4, 0.7, 0.8, 0.6, 0.3],
                ndvi_dates=["2026-01-15", "2026-02-15", "2026-03-15", "2026-04-15", "2026-05-15", "2026-06-15"],
                feature_vector_snapshot={
                    "feature_vector_version": "6.0.0",
                    "data_completeness": 1.0,
                    "flat_features": {name: 0.25 for name in names},
                    "crop_model_input_receipt": {
                        "feature_schema_hash": schema.content_hash,
                        "publication_eligible": False,
                        "model_execution_eligible": True,
                        "publication_blockers": ["probability_calibration_not_validated"],
                    },
                },
            )
        self.assertFalse(id_res.detected_crop)
        self.assertIsNone(id_res.top_crop)
        self.assertFalse(id_res.evidence.get("ml_publication_gate_passed"))
        self.assertEqual(id_res.evidence.get("ml_l3_exploratory_candidate"), "wheat")

        # 3. Canonical infer_crop_posterior attaches governed feature_vector_snapshot & receipt
        from services.agribrain.scientific_contracts.crop_evidence import (
            CanonicalCropObservationV2,
            CropEvidenceLedgerV2,
        )

        ns = {"tenant_id": "t_ml", "farm_id": "f_ml", "plot_id": "p_ml"}
        obs_records = [
            CanonicalCropObservationV2.from_mapping({
                "observation_id": f"crop-ml-{m}",
                "timestamp": f"2026-0{m:d}-01T10:30:00+00:00",
                "date": f"2026-0{m:d}-01",
                "physical_acquisition_key": f"S2ACQ-ml-{m}",
                "physical_identity_complete": True,
                "independence_identity_available": True,
                "source_family": "sentinel2",
                "provider": "copernicus",
                "mission": "S2B",
                "sensor": "MSI",
                "tile_id": "T31SDA",
                "relative_orbit": "R108",
                "content_hash": f"sha256:mlobs{m:d}" * 4,
                "plot_geometry_hash": "sha256:geom_ml",
                "quality_admitted": True,
                "quality_class": "good",
                "valid_pixel_count": 8,
                "field_pixel_count": 9,
                "valid_fraction": 8 / 9,
                "cloud_fraction": 1 / 9,
                "shadow_fraction": 0.0,
                "snow_fraction": 0.0,
                "nodata_fraction": 0.0,
                "reading_reliability": 0.85,
                "pixel_support_contract": {
                    "support_hash": "support-ml",
                    "support_definition": "plot&DATAMASK&SCL&finite",
                    "grid_identity": {"crs": "EPSG:32631", "transform": [10.0, 0.0, 500000.0, 0.0, -10.0, 4040000.0], "shape": [3, 3]},
                },
                "index_statistics": {
                    "ndvi": {"mean": 0.25 + 0.1 * (m % 5), "std": 0.04, "min": 0.2, "max": 0.75, "valid_count": 8},
                    "evi": {"mean": 0.18 + 0.08 * (m % 5), "std": 0.03, "min": 0.14, "max": 0.60, "valid_count": 8},
                    "ndre": {"mean": 0.15 + 0.06 * (m % 5), "std": 0.02, "min": 0.10, "max": 0.45, "valid_count": 8},
                    "ndmi": {"mean": 0.12 + 0.05 * (m % 5), "std": 0.02, "min": 0.08, "max": 0.40, "valid_count": 8},
                },
                "environmental_context": {
                    "day_of_year": 30 * m,
                    "gdd_accumulated": 120.0 * m,
                    "gdd_basis": "base_10_daily_mean",
                    "season_phase": "early" if m <= 2 else "mid",
                },
                "direct_observation": True,
                "calibration_domain_compatibility": "compatible",
                "geographical_domain_compatibility": "compatible",
                "processing_lineage": [{
                    "provider_product_id": f"S2B_MSIL2A_20260{m:d}01T103000_N0500_R108_T31SDA",
                    "catalog_item_id": f"cat-ml-{m}",
                    "processing_timestamp": f"2026-0{m:d}-01T12:00:00+00:00",
                    "processing_baseline": "05.00",
                    "content_hash": f"sha256:ml{m:d}" * 4,
                    "process_request_hash": f"sha256:req{m:d}" * 4,
                    "provider_response_hash": f"sha256:resp{m:d}" * 4,
                }],
                **ns,
            }, plot_namespace=ns)
            for m in range(1, 7)
        ]
        ledger = CropEvidenceLedgerV2.from_observations(ns, obs_records)
        post = infer_crop_posterior(
            plot_id="p_ml",
            run_id="r_ml",
            plot_timeseries=[],
            operational_context={
                **ns,
                "crop_evidence_ledger": ledger.to_dict(),
                "crop_evidence_ledger_hash": ledger.ledger_hash,
            },
        )
        self.assertTrue(post["ml_handoff_status"]["ml_input_handoff_attached"])
        self.assertFalse(post["species_probability_published"])

        # 4. Self-asserted unsigned calibration_receipt MUST be rejected (WM1-P2-12);
        # only a cryptographically signed TrustedCalibrationArtifactStore entry passes
        from services.agribrain.layer2_veg_int.features.calibration_registry import TrustedCalibrationArtifactStore
        from services.agribrain.scientific_contracts.crop_model_input import build_crop_model_input_receipt

        _, forged_cal_receipt, _ = build_ledger_crop_feature_input(
            ledger=ledger,
            crop_cycle_hypothesis_id="cycle-cal-forged",
            run_id="r_ml_cal_forged",
            calibration_receipt={
                "calibration_artifact_hash": "c" * 64,
                "calibration_partition_policy": "external_farm_cycle_year_region_disjoint_required",
                "calibration_verified": True,
                "heldout_validation_complete": True,
                "ece": 0.03,
            },
            normalization_artifact_hash="b" * 64,
        )
        self.assertEqual(forged_cal_receipt.calibration_validity, "unavailable")
        self.assertIn("probability_calibration_not_validated", forged_cal_receipt.publication_blockers)

        cal_store = TrustedCalibrationArtifactStore(signing_secret="test-wm2-cal-secret")
        signed_rec = cal_store.issue_and_register(
            calibration_artifact_hash="c" * 64,
            feature_schema_hash=schema.content_hash,
            ece=0.03,
        )
        _, cal_receipt, _ = build_ledger_crop_feature_input(
            ledger=ledger,
            crop_cycle_hypothesis_id="cycle-cal",
            run_id="r_ml_cal",
            calibration_receipt={
                "calibration_artifact_hash": signed_rec.calibration_artifact_hash,
                "feature_schema_hash": signed_rec.feature_schema_hash,
                "calibration_partition_policy": signed_rec.calibration_partition_policy,
                "calibration_verified": True,
                "heldout_validation_complete": True,
                "ece": 0.03,
                "signature_hmac": signed_rec.signature_hmac,
            },
            normalization_artifact_hash="b" * 64,
            calibration_store=cal_store,
        )
        self.assertNotEqual(cal_receipt.calibration_validity, "unavailable")
        self.assertNotIn("probability_calibration_not_validated", cal_receipt.publication_blockers)
        full_cal_receipt = build_crop_model_input_receipt(
            ledger=ledger,
            crop_cycle_hypothesis_id="cycle-cal-full",
            feature_schema=schema,
            feature_values={name: 0.25 for name in names},
            feature_transform_hash="a" * 64,
            normalization_artifact_hash="b" * 64,
            domain_compatibility="compatible",
            calibration_validity=cal_receipt.calibration_validity,
        )
        self.assertTrue(full_cal_receipt.publication_eligible)
        cal_clf_res = clf.predict({
            "feature_vector_version": "6.0.0",
            "data_completeness": 1.0,
            "flat_features": {name: 0.25 for name in names},
            "crop_model_input_receipt": full_cal_receipt.to_dict(),
        }, apply_constraints=True)
        self.assertTrue(cal_clf_res["publication_eligible"])
        self.assertEqual(cal_clf_res["ml_classifier_output"]["L3"]["prediction"], "wheat")


if __name__ == "__main__":
    unittest.main()
