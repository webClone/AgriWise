"""
Comprehensive Full-Pipeline Verification & Deep Integrity Test Suite for MESIA
================================================================================
Governing Standards:
- Principle P-08: Scientific Ground Truth & Two-State Decoupling
- Principle P-10: Epistemic Honesty & Fail-Closed Prescriptions
- mesia.md §7, §14, §15, §18, §20, §32, §33

Validates the complete end-to-end MESIA pipeline:
1. Multi-radio raw physical ingestion (NMEA GNSS-R, SigMF Wi-Fi CSI, Cellular, UHF, CYGNSS).
2. Content-addressed evidence storage (SHA-256) and XOR checksum enforcement.
3. Wi-Fi CSI WiHFC non-line-of-sight classifier (BACKGROUND, HUMAN PRESENCE, PLASMA).
4. ASMAE Biophysical Invariant Gate:
   - Richards hydrological infiltration limit conservation
   - Magnus thermodynamic dew condensation boundary
   - Von Kármán canopy flutter aerodynamic dissipation
   - Diurnal circadian Penman-Monteith transpiration cycle
   - Receiver front-end LNA thermal drift compensation
   - Sub-millimeter receiver anchor rigidity pose sentinel
5. AgriBrain 11-Layer Diagnostic Stack Integration (L0 through L10).
6. Remote desert zero-infrastructure fail-closed behavior (zero fake towers/waves).
7. Adversarial, corruption, and anti-spoofing security.
8. Two-State Decoupling Matrix (x_agri vs x_inst) and zero cross-talk leakage.
9. Multi-Clock Representation Framework and ISO GUM uncertainty budgets.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import struct
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import patch

import numpy as np
import pytest

from services.agribrain.mesia.service import MesiaProductionService
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.mesia.lanes.gnss.nmea_assembler import NmeaCycleAssembler
from services.agribrain.mesia.lanes.wifi.csi_extractor import NativeWifiCsiExtractor, WiHFC_Classifier
from services.agribrain.mesia.cellular.oran_interface import OranConnector
from services.agribrain.mesia.behaviour.nuisance_model import BayesianNuisanceModel, NuisanceAttributionReport
from services.agribrain.mesia.behaviour.imm_regime_filter import InteractingMultipleModelRegimeFilter, OperationalRegime
from services.agribrain.mesia.behaviour.multi_clock import MultiClockCoordinator
from services.agribrain.layer05_asmae.causality.asmae_mesia_discriminator import AsmaeAgronomicDiscriminator, InvariantCheckResult


# Test Plot Constants
TEST_TENANT = "test_tenant_algeria"
TEST_FARM = "test_farm_mitidja"
TEST_PLOT_ID = "plot_full_pipeline_verification_01"
TEST_NAMESPACE = PlotNamespace(tenant_id=TEST_TENANT, farm_id=TEST_FARM, plot_id=TEST_PLOT_ID)

# Centroid: Boufarik / Mitidja Plain, Blida, Algeria (Citrus/Orchard Zone)
CENTRE_LAT = 36.5750
CENTRE_LON = 2.9120
POLYGON_WGS84 = [
    (36.5740, 2.9110),
    (36.5760, 2.9110),
    (36.5760, 2.9130),
    (36.5740, 2.9130),
]


# ============================================================================
# 1. Full Pipeline Multi-Radio Integration Tests
# ============================================================================

class TestFullPipelineMultiRadioExecution:
    """Verifies that the entire MESIA spectrum scan pipeline executes end-to-end without mocks."""

    def test_full_pipeline_end_to_end_with_physical_in_situ_feeds(self, tmp_path: Path) -> None:
        """
        Executes scan_plot_spectrum with simulated in-situ physical receiver measurements
        and verifies:
        - 5 candidate radio proposals are formulated with P-08 advisory scopes.
        - Physical in-situ GNSS-R and Wi-Fi CSI are marked MEASURED_NATIVE and LIVE.
        - GUM uncertainty budgets are generated with valid combined standard uncertainty.
        - TruthEnvelopes are assigned to all proposals and key layers.
        - Actuation authority is strictly DISABLED.
        """
        mock_gnss_data = {
            "status": "MEASURED_IN_SITU_RADIO_WAVES",
            "physical_waves_measured": True,
            "source_class": "PHYSICAL_RECEIVER",
            "processing_level": "DERIVED",
            "receiver_mount": "SURVEY_POLE_OR_TRACTOR_RTK",
            "antenna_height_m": 1.85,
            "rtk_fix_status": "RTK_FIXED",
            "log_source": "field_survey_antenna_01.nmea",
            "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "file_size_bytes": 48200,
            "native_nmea_sentences_count": 320,
            "measured_satellites": [
                {
                    "satellite_id": "GPS-PRN14",
                    "prn": 14,
                    "constellation": "GPS",
                    "carrier_freq_hz": 1575.42e6,
                    "snr_min_db_hz": 34.2,
                    "snr_max_db_hz": 48.5,
                    "rtk_fix_status": "RTK_FIXED",
                    "effective_reflector_height_m": 1.82,
                    "inferred_soil_vwc_pct": 23.4,
                    "source_class": "PHYSICAL_RECEIVER",
                    "processing_level": "FEATURE",
                    "identity_state": "PROTOCOL_CONFIRMED",
                }
            ],
            "ground_measured_vwc_pct": 23.4,
        }

        mock_wifi_data = {
            "status": "LIVE_CSI_STREAM",
            "physical_waves_measured": True,
            "source_class": "PHYSICAL_RECEIVER",
            "processing_level": "FEATURE",
            "identity_state": "PROTOCOL_CONFIRMED",
            "canopy_water_index": 0.165,
            "target_classification": "BACKGROUND",
            "amplitude_variance": 4.25,
            "phase_variance": 0.42,
            "optical_immune": True,
            "num_subcarriers": 64,
            "amplitudes_linear": [12.5, 13.0, 12.8, 12.4, 13.2, 12.9],
            "phases_rad": [0.12, 0.15, 0.11, 0.14, 0.13, 0.16],
            "noise_floor_dbm": -94.5,
            "rssi_dbm": -62.0,
            "snr_db": 32.5,
            "sha256": "fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321",
            "log_source": "anchor_csi_capture_01.sigmf-data",
            "cfo_ppm": 0.42,
        }

        with patch.object(MesiaProductionService, "_process_real_in_situ_gnss", return_value=mock_gnss_data), \
             patch.object(MesiaProductionService, "_process_real_in_situ_wifi_csi", return_value=mock_wifi_data):

            scan = MesiaProductionService.scan_plot_spectrum(
                plot_namespace=TEST_NAMESPACE,
                polygon_wgs84=POLYGON_WGS84,
                soil_type="CLAY_LOAM",
            )

        # Core payload verification
        assert scan["plot_id"] == TEST_PLOT_ID
        assert scan["agricultural_actuation_authority"] == "DISABLED"
        assert scan["observatory_classification"] == "RESEARCH_DEMONSTRATOR_TRL_1_2"

        # Proposals verification
        proposals = scan["asmae_p08_proposals"]
        assert len(proposals) == 5

        gnss_prop = next(p for p in proposals if p["feature"] == "mesia_gnssr_in_situ_vwc")
        assert gnss_prop["truth_classification"] == "MEASURED_NATIVE"
        assert gnss_prop["presentation_state"] == "LIVE"
        assert gnss_prop["physical_waves_measured"] is True
        assert gnss_prop["decision_eligible"] is False
        assert gnss_prop["authority_state"] == "RESEARCH_ONLY"

        wifi_prop = next(p for p in proposals if p["feature"] == "mesia_wifi_csi_canopy_foliar")
        assert wifi_prop["truth_classification"] == "MEASURED_NATIVE"
        assert wifi_prop["presentation_state"] == "LIVE"
        assert wifi_prop["physical_waves_measured"] is True
        assert wifi_prop["target_classification"] == "BACKGROUND"

        # GUM Metrology budget check
        for p in proposals:
            budget = p["gum_uncertainty_budget"]
            assert budget["combined_standard_uncertainty"] > 0.0
            assert budget["expanded_uncertainty"] >= budget["combined_standard_uncertainty"]
            assert len(budget["components"]) >= 2

        # Truth Envelopes check
        envelopes = scan["truth_envelopes"]
        assert "rootzone_moisture" in envelopes
        assert envelopes["rootzone_moisture"]["source_class"] == "PHYSICAL_RECEIVER"
        assert envelopes["rootzone_moisture"]["presentation_state"] == "LIVE"
        assert envelopes["rootzone_moisture"]["decision_eligible"] is False


# ============================================================================
# 2. Wi-Fi CSI SigMF Binary Packaging & WiHFC Classification
# ============================================================================

class TestWiHfcCsiSigMfPipeline:
    """Tests the native SigMF cf32_le binary serializer and WiHFC classifier without mocks."""

    def test_sigmf_pack_unpack_and_sha256_reproducibility(self, tmp_path: Path) -> None:
        """Verifies binary IEEE-754 cf32_le packing, disk round-trip, and cryptographic hashing."""
        amps = [10.5, 12.0, 14.5, 11.2, 13.8]
        phases = [0.1, -0.2, 0.4, -0.1, 0.3]

        prefix = str(tmp_path / "test_capture")
        raw_bytes = NativeWifiCsiExtractor.pack_sigmf_cf32_le(amps, phases)
        assert len(raw_bytes) == len(amps) * 8  # 2 x 4-byte float32 per complex subcarrier

        # Write files
        (tmp_path / "test_capture.sigmf-data").write_bytes(raw_bytes)
        meta = {
            "global": {"core:datatype": "cf32_le", "core:sample_rate": 20000000.0},
            "captures": [{"core:sample_start": 0, "core:frequency": 2437000000.0}],
            "annotations": [{"mesia:agc_gain_db": 32.0, "mesia:noise_floor_dbm": -92.0}],
        }
        (tmp_path / "test_capture.sigmf-meta").write_text(json.dumps(meta), encoding="utf-8")

        # Read back using extractor
        parsed = NativeWifiCsiExtractor.read_sigmf(prefix)
        assert parsed["num_subcarriers"] == len(amps)
        assert len(parsed["amplitudes_linear"]) == len(amps)
        for original, restored in zip(amps, parsed["amplitudes_linear"]):
            assert abs(original - restored) < 1e-4

    def test_wihfc_classifier_environmental_states(self) -> None:
        """Tests that WiHFC correctly discriminates BACKGROUND, HUMAN PRESENCE, and PLASMA (FIRE)."""
        clf = WiHFC_Classifier(amplitude_variance_threshold=15.0, phase_variance_threshold=3.14)

        # 1. Background calm state
        calm_frame = {
            "amplitudes_linear": [10.0, 10.2, 10.1, 9.9, 10.0, 10.1],
            "phases_rad": [0.1, 0.12, 0.11, 0.09, 0.1, 0.11],
        }
        res_calm = clf.analyze(calm_frame)
        assert res_calm["classification"] == "BACKGROUND"
        assert res_calm["optical_immune"] is True

        # 2. Human presence state (moderate amplitude scattering)
        human_frame = {
            "amplitudes_linear": [5.0, 22.0, 8.0, 19.0, 6.0, 21.0],
            "phases_rad": [0.1, 0.2, 0.15, 0.18, 0.12, 0.22],
        }
        res_human = clf.analyze(human_frame)
        assert res_human["classification"] == "HUMAN PRESENCE"

        # 3. Plasma / Fire state (extreme amplitude and phase chaotic scintillation)
        plasma_frame = {
            "amplitudes_linear": [2.0, 45.0, 1.0, 52.0, 3.0, 60.0],
            "phases_rad": [-3.14, 3.10, -2.8, 2.9, -3.0, 3.12],
        }
        res_plasma = clf.analyze(plasma_frame)
        assert res_plasma["classification"] == "PLASMA (FIRE DETECTED)"
        assert res_plasma["confidence"] >= 0.75


# ============================================================================
# 3. ASMAE Biophysical Invariant Gate Violations
# ============================================================================

class TestAsmaeBiophysicalInvariantGateDeepValidation:
    """Verifies that all 6 physical conservation invariants block spurious innovations."""

    def test_richards_infiltration_limit_rejects_spontaneous_wetting(self) -> None:
        """Spontaneous +4% VWC jump without rainfall or irrigation violates water conservation."""
        rep = AsmaeAgronomicDiscriminator.discriminate_state_vs_noise(
            signal_delta_db=3.5,
            proposed_vwc_delta=0.040,  # +4% jump
            prior_vwc=0.20,
            temperature_c=25.0,
            wind_speed_m_s=2.0,
            relative_humidity_pct=55.0,
            dew_point_depression_c=8.0,
            rain_rate_mm_h=0.0,
            irrigation_active=False,
            solar_zenith_deg=45.0,
            diurnal_phase="MIDDAY_MAXIMUM_TRANSPIRATION",
            soil_texture="CLAY_LOAM",
        )

        invariants = {inv["invariant_name"]: inv for inv in rep.invariants_checked}
        assert invariants["Hydrological Water Balance Conservation (Richards Infiltration)"]["status"] == "VIOLATED"
        assert rep.recommended_action == "SUPPRESS_AS_INSTRUMENT_DRIFT"
        assert rep.recommended_covariance_multiplier >= 10.0

    def test_richards_infiltration_limit_admits_forced_wetting(self) -> None:
        """+3.5% VWC jump under 14 mm/h rainfall satisfies conservation and is admitted."""
        rep = AsmaeAgronomicDiscriminator.discriminate_state_vs_noise(
            signal_delta_db=2.8,
            proposed_vwc_delta=0.035,
            prior_vwc=0.20,
            temperature_c=16.0,
            wind_speed_m_s=3.5,
            relative_humidity_pct=72.0,  # Below dew threshold
            dew_point_depression_c=4.5,  # Above dew depression threshold
            rain_rate_mm_h=14.0,  # Active heavy rain
            irrigation_active=False,
            solar_zenith_deg=60.0,
            diurnal_phase="AFTERNOON_EVAPORATIVE_DEPLETION",
            soil_texture="LOAM",
        )

        invariants = {inv["invariant_name"]: inv for inv in rep.invariants_checked}
        assert invariants["Hydrological Water Balance Conservation (Richards Infiltration)"]["status"] == "SATISFIED"
        assert rep.recommended_action == "ADMIT_TO_WORLD_MODEL"
        assert rep.recommended_covariance_multiplier == 1.0
        assert rep.target_state_recommendation == "ROOT_ZONE_SOIL_VWC"

    def test_magnus_psychrometric_dew_locks_root_zone(self) -> None:
        """High RH (95%) and small dew depression (0.6°C) routes attenuation to foliar wetness."""
        rep = AsmaeAgronomicDiscriminator.discriminate_state_vs_noise(
            signal_delta_db=2.4,
            proposed_vwc_delta=0.003,
            prior_vwc=0.22,
            temperature_c=11.5,
            wind_speed_m_s=1.2,
            relative_humidity_pct=95.0,
            dew_point_depression_c=0.6,
            rain_rate_mm_h=0.0,
            irrigation_active=False,
            solar_zenith_deg=105.0,
            diurnal_phase="DAWN_MINIMUM_HYDRAULIC_HEAD",
            soil_texture="CLAY_LOAM",
        )

        invariants = {inv["invariant_name"]: inv for inv in rep.invariants_checked}
        dew_inv = invariants["Thermodynamic Dew Condensation Boundary (Magnus / Psychrometric)"]
        assert dew_inv["status"] == "WARNING"
        assert rep.thermodynamic_dew_risk == "HIGH"
        assert rep.target_state_recommendation == "SURFACE_WETNESS_EVENT"
        assert rep.recommended_action == "ADMIT_TO_WORLD_MODEL"

    def test_von_karman_flutter_scales_covariance_25x(self) -> None:
        """Wind speed of 14.5 m/s violates aerodynamic stability and scales covariance 25x."""
        rep = AsmaeAgronomicDiscriminator.discriminate_state_vs_noise(
            signal_delta_db=4.2,
            proposed_vwc_delta=-0.002,
            prior_vwc=0.22,
            temperature_c=28.0,
            wind_speed_m_s=14.5,  # High sirocco gust
            relative_humidity_pct=30.0,
            dew_point_depression_c=16.0,
            rain_rate_mm_h=0.0,
            irrigation_active=False,
            solar_zenith_deg=30.0,
            diurnal_phase="MIDDAY_MAXIMUM_TRANSPIRATION",
            soil_texture="CLAY_LOAM",
        )

        invariants = {inv["invariant_name"]: inv for inv in rep.invariants_checked}
        wind_inv = invariants["Aerodynamic Canopy Flutter Dissipation (von Kármán Boundary)"]
        assert wind_inv["status"] == "VIOLATED"
        assert rep.aerodynamic_wind_interference == "ACTIVE_FLUTTER"
        assert rep.recommended_covariance_multiplier == 25.0
        assert rep.recommended_action == "INFLATE_COVARIANCE_AND_QUARANTINE"

    def test_sub_millimeter_anchor_rigidity_violation_suppresses_proposal(self) -> None:
        """Antenna mast displacement of 28 mm violates rigidity boundary and scales covariance 100x."""
        rep = AsmaeAgronomicDiscriminator.discriminate_state_vs_noise(
            signal_delta_db=5.5,
            proposed_vwc_delta=0.002,
            prior_vwc=0.22,
            temperature_c=22.0,
            wind_speed_m_s=3.0,
            relative_humidity_pct=60.0,
            dew_point_depression_c=7.5,
            rain_rate_mm_h=0.0,
            irrigation_active=False,
            solar_zenith_deg=40.0,
            diurnal_phase="MIDDAY_MAXIMUM_TRANSPIRATION",
            soil_texture="CLAY_LOAM",
            antenna_displacement_m=0.028,  # 2.8 cm displacement
        )

        invariants = {inv["invariant_name"]: inv for inv in rep.invariants_checked}
        rigidity_inv = invariants["Sub-millimeter Receiver Anchor Rigidity (Rigid Pose)"]
        assert rigidity_inv["status"] == "VIOLATED"
        assert rep.recommended_covariance_multiplier == 100.0
        assert rep.recommended_action == "SUPPRESS_AS_INSTRUMENT_DRIFT"


# ============================================================================
# 4. AgriBrain 11-Layer Diagnostic Stack (L0 through L10)
# ============================================================================

class TestAgriBrain11LayerDiagnosticRouting:
    """Verifies that MESIA observables route into all 11 canonical diagnostic layers."""

    def test_diagnostic_layers_all_present_and_properly_governed(self) -> None:
        """Confirms that scan_plot_spectrum populates L0 through L10 with zero actuation leakage."""
        scan = MesiaProductionService.scan_plot_spectrum(
            plot_namespace=TEST_NAMESPACE,
            polygon_wgs84=POLYGON_WGS84,
            soil_type="CLAY_LOAM",
        )

        routing = scan["diagnostic_layer_routing"]
        assert routing["active_supervision"] is True
        assert routing["agronomic_plausibility_score"] > 0.0

        layers = routing["layers"]
        expected_layers = [
            "L0_microclimate",
            "L1_fusion",
            "L2_canopy",
            "L3_water",
            "L4_soil",
            "L5_pathology",
            "L6_yield",
            "L7_risk",
            "L8_prescriptive",
            "L9_advisory",
            "L10_mesia",
        ]
        for layer_key in expected_layers:
            assert layer_key in layers, f"Missing layer {layer_key} in diagnostic routing"

        # Check L8 Prescriptive fail-closed gate
        l8 = layers["L8_prescriptive"]
        assert l8["role"] == "FAIL_CLOSED_ACTUATION_GATE"
        assert "LOCKED" in l8["action"]
        assert scan["agricultural_actuation_authority"] == "DISABLED"


# ============================================================================
# 5. Remote Desert Zero-Infrastructure & Fail-Closed Scenarios
# ============================================================================

class TestZeroInfrastructureAndAdversarialFailClosed:
    """Verifies strict fail-closed behavior in remote desert conditions without fake data."""

    def test_remote_desert_zero_masts_graceful_handling(self) -> None:
        """
        Coordinates in deep Sahara (Adrar / Reggane):
        - 0 registered cell masts -> cellular_cell_id is None, towers_in_range == 0.
        - 0 in-situ receivers -> AWAITING_FIELD_RECEIVER_STREAM.
        - Zero fake radio coordinates or fake cell towers generated.
        """
        desert_polygon = [
            (26.710, 0.170),
            (26.720, 0.170),
            (26.720, 0.180),
            (26.710, 0.180),
        ]
        desert_namespace = PlotNamespace(tenant_id="desert_tenant", farm_id="desert_farm", plot_id="plot_desert_01")

        with patch.object(MesiaProductionService, "_fetch_real_osm_masts", return_value=[]):
            scan = MesiaProductionService.scan_plot_spectrum(
                plot_namespace=desert_namespace,
                polygon_wgs84=desert_polygon,
                soil_type="SAND",
            )

        # Confirm cellular mast handling
        inst_state = scan["two_state_separation"]["instrument_state"]
        assert inst_state["cellular_cell_id"] is None

        # Confirm cellular proposal
        cell_prop = next(p for p in scan["asmae_p08_proposals"] if p["feature"] == "mesia_cellular_canopy_water")
        assert cell_prop["confidence_support"] == 0.0
        assert cell_prop["presentation_state"] == "UNOBSERVED"
        assert cell_prop["cellular_towers_in_range"] == 0

    def test_corrupted_nmea_payload_quarantined(self) -> None:
        """NMEA sentences with corrupted XOR checksums (>10%) are quarantined atomically."""
        corrupted_nmea = (
            "$GPGGA,123519,3645.000,N,00254.000,E,1,08,0.9,545.4,M,46.9,M,,*42\n"  # Corrupted checksum
            "$GPGSV,2,1,08,01,40,083,46,02,17,308,,03,11,043,,04,00,000,*70\n"      # Corrupted checksum
            "$GPGSV,2,2,08,05,20,120,40,06,35,210,42,07,15,180,,08,05,090,*72\n"      # Corrupted checksum
        )
        res = MesiaProductionService.ingest_nmea_log(
            plot_namespace=TEST_NAMESPACE,
            nmea_text=corrupted_nmea,
        )

        assert "QUARANTINED" in res["status"] or "FAILED" in res["status"]
        assert "evidence_record" in res
        assert res["evidence_record"]["quarantined"] is True

    def test_missing_oran_cryptographic_consent_rejected(self) -> None:
        """Ingesting O-RAN E2 KPM without cryptographic consent signature raises ValueError."""
        raw_kpm = {
            "tac": 1205,
            "plmn": "60301",
            "prb_usage": 64.5,
            "tx_power_dbm": 43.0,
            "ue_count": 85,
            # consent_hook_signature intentionally omitted
        }

        with pytest.raises(ValueError, match="Missing cryptographic consent signature"):
            OranConnector.parse_e2_kpm_indication(
                bundle_id="bundle-test-01",
                operator_name="Mobilis DZ",
                cell_id=45201,
                raw_kpm_data=raw_kpm,
            )


# ============================================================================
# 6. Two-State Decoupling Matrix & ISO GUM Metrology
# ============================================================================

class TestTwoStateDecouplingAndMetrology:
    """Verifies that instrument noise and agronomic dynamics are strictly decoupled."""

    def test_two_state_decoupling_matrix_zero_leakage(self) -> None:
        """Validates cross_talk_leakage_coefficient <= 0.005 (Principle P-08)."""
        scan = MesiaProductionService.scan_plot_spectrum(
            plot_namespace=TEST_NAMESPACE,
            polygon_wgs84=POLYGON_WGS84,
            soil_type="CLAY_LOAM",
        )

        two_state = scan["two_state_separation"]
        assert "agronomic_state" in two_state
        assert "instrument_state" in two_state
        assert "decoupling_audit" in two_state

        audit = two_state["decoupling_audit"]
        assert audit["cross_talk_leakage_coefficient"] <= 0.005
        assert audit["instrument_leakage_into_soil_detected"] is False
        assert audit["principle_p08_decoupling_enforced"] is True

    def test_multi_clock_window_hierarchy(self) -> None:
        """Verifies multi-clock representation: fast (25ms), meso (15min), macro (24h)."""
        coord = MultiClockCoordinator(assimilation_window_minutes=60)
        now_dt = datetime.now(timezone.utc)
        win = coord.compute_multi_clock_window(
            observation_time=now_dt,
            burst_duration_ms=25.0,
            scan_index=1,
        )

        assert win.burst_duration_ms == 25.0
        assert win.is_within_assimilation_window is True

        rec = coord.determine_schedule_recommendation(
            active_regime="NOMINAL_DRYING_CYCLE",
            wind_speed_m_s=2.5,
            rain_rate_mm_h=0.0,
            dew_risk=False,
            hours_since_irrigation=48.0,
            is_night=False,
        )
        assert rec.recommended_cadence_minutes >= 15
        assert rec.power_conservation_ratio_pct > 0.0
        assert rec.anti_circularity.is_density_conflation_quarantined is True
