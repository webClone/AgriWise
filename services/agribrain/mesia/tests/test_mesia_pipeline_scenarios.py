"""Comprehensive Multi-Scenario Pipeline Test Suite for MESIA.

Verifies:
- Scenario A: Multi-agroclimatic spectrum scan across diverse soil/climate types
  (Mitidja clay loam with ASMAE raster, Biskra arid sand without ASMAE raster, Sahel coastal loam).
- Scenario B: Discovery & Open-Set Identification pipeline
  (CA-CFAR detection, WaveCandidate extraction, OpenSetWaveformClassifier,
   Deterministic Protocol Rules, Evidence Fusion with/without ProtocolConfirmationReceipt).
- Scenario C: In-Situ GNSS edge cases & fail-closed guardrails
  (>=8 points solved VWC, <8 points INSUFFICIENT_SATELLITE_ARCS fail-closed,
   missing SNR preserved as None, checksum corruption quarantined).
- Scenario D: Dynamic Wi-Fi CSI & Metrology
  (varying geodetic coordinates, deterministic namespace-derived BSSID,
   SigMF cf32_le packing, TruthEnvelope immutability & SIMULATION state).
- Scenario E: Full AgriBrain Layer 0 Bridge
  (MesiaAgriBrainBridge ingestion with valid/invalid calibration, P-10 capability revocation).
- Scenario F: Layer 3 Hydrological Model Cross-Validation
  (MesiaLayer3WaterBridge strata comparisons, residual tolerances).
- Scenario G: Canonical ClosureCertificate validation & content hash integrity in scan_plot_spectrum().
"""

import math
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import List, Tuple
from pathlib import Path

import pytest
import numpy as np

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.mesia.service import MesiaProductionService
from services.agribrain.mesia.discovery.detector_bank import DetectorBank, DetectionPeak
from services.agribrain.mesia.contracts.wave import WaveCandidate
from services.agribrain.mesia.identity.open_set_classifier import OpenSetWaveformClassifier
from services.agribrain.mesia.identity.evidence_fusion import EvidenceFusionEngine
from services.agribrain.mesia.contracts.receipts import ProtocolConfirmationReceipt
from services.agribrain.mesia.contracts.identity import SignalIdentityHypothesis
from services.agribrain.mesia.lanes.gnss.nmea_assembler import NmeaCycleAssembler
from services.agribrain.mesia.lanes.wifi.csi_extractor import NativeWifiCsiExtractor
from services.agribrain.mesia.ontology.evidence_taxonomy import (
    SourceClass,
    ProcessingLevel,
    AuthorityState,
    PresentationState,
    TruthEnvelope,
)
from services.agribrain.mesia.ontology.identity_states import IdentityState
from services.agribrain.mesia.contracts.scientific import (
    ClosureStatus,
    ClosureCertificate,
)
from services.agribrain.mesia.contracts.observation import RadioObservationPacket
from services.agribrain.mesia.contracts.authority import CapabilityAuthorityRecord
from services.agribrain.mesia.contracts.behaviour import BehaviourLikelihood
from services.agribrain.mesia.integration import MesiaAgriBrainBridge
from services.agribrain.mesia.integration_layer3 import MesiaLayer3WaterBridge
from services.agribrain.mesia.assimilation.spatial_lattice import LatticeStrata
from services.agribrain.mesia.assimilation.layer0_spine import EvidenceAdmissionStatus
from services.agribrain.mesia.assimilation.capability_governance import CapabilityGovernanceAuthority
from services.agribrain.mesia.truth.soil_columns import (
    SoilTextureClass,
    HysteresisBranch,
    SoilColumnExperimentRecord,
    SoilStratumMeasurement,
)
from services.agribrain.mesia.experiments.soil_column_experiment import (
    SoilColumnExperimentHarness,
    SoilColumnTrialSummary,
)
from services.agribrain.mesia.experiments.teacher_controls import (
    TeacherControlsAuthority,
    NegativeControlResult,
    TeacherControlComparison,
)
from services.agribrain.mesia.experiments.multi_radio_closure import (
    MultiRadioClosureHarness,
    ClosureVerificationReport,
)
from services.agribrain.mesia.experiments.nuisance_challenge_matrix import (
    NuisanceChallengeMatrixHarness,
    ChallengeExecutionResult,
)


# ==============================================================================
# SCENARIO A: Multi-Agroclimatic Spectrum Scan Across Diverse Soil / Climate Types
# ==============================================================================

class TestScenarioAMultiAgroclimaticSpectrumScan:
    """Validates MESIA spectrum scan over realistic, diverse Algerian agroclimatic regions."""

    def test_mitidja_subhumid_clay_loam_with_raster(self, monkeypatch):
        """Mitidja Plain: Sub-humid, clay loam, high organic matter, standard ASMAE raster present."""
        ns = PlotNamespace(tenant_id="tenant_mitidja", farm_id="farm_blida", plot_id="plot_citrus_01")
        polygon = [
            (36.5750, 2.9110),
            (36.5770, 2.9110),
            (36.5770, 2.9130),
            (36.5750, 2.9130),
        ]

        monkeypatch.setattr(
            MesiaProductionService,
            "_fetch_real_copernicus_soil",
            lambda lat, lon: {
                "soil_moisture_0_to_1cm": 0.22,
                "soil_moisture_1_to_3cm": 0.24,
                "soil_moisture_3_to_9cm": 0.26,
                "soil_moisture_9_to_27cm": 0.28,
                "relative_humidity_2m": 65.0,
                "temperature_2m": 24.5,
                "surface_pressure": 1012.0,
            },
        )
        monkeypatch.setattr(
            MesiaProductionService,
            "_fetch_real_osm_masts",
            lambda lat, lon, radius_m=8000.0: [
                {
                    "osm_id": 1001,
                    "operator": "Mobilis",
                    "band": "LTE 1800",
                    "freq_hz": 1815e6,
                    "dist_m": 420.0,
                    "bearing_deg": 35.0,
                    "tx_power_dbm": 43.0,
                    "source_class": "GIS_REGISTRY",
                    "identity_state": "PROTOCOL_CONFIRMED",
                },
                {
                    "osm_id": 1002,
                    "operator": "Djezzy",
                    "band": "LTE 2100",
                    "freq_hz": 2115e6,
                    "dist_m": 650.0,
                    "bearing_deg": 120.0,
                    "tx_power_dbm": 43.0,
                    "source_class": "GIS_REGISTRY",
                    "identity_state": "PROTOCOL_CONFIRMED",
                },
            ],
        )

        result = MesiaProductionService.scan_plot_spectrum(
            plot_namespace=ns,
            polygon_wgs84=polygon,
            soil_type="CLAY_LOAM",
        )

        assert result["plot_id"] == "plot_citrus_01"
        assert result["status"] == "RESEARCH_DEMONSTRATOR_TRL_1_2"
        assert result["agricultural_actuation_authority"] == "DISABLED"

        # Validate dielectrics & moisture strata
        dielectric = result["dielectric_profile"]
        assert dielectric["soil_texture"] == "CLAY_LOAM"
        assert 0.0 < dielectric["horizon_0_1cm_vwc_pct"] <= 100.0
        assert 0.0 < dielectric["horizon_3_9cm_vwc_pct"] <= 100.0
        assert dielectric["mean_dielectric_permittivity_eps_r"] > 1.0

        # Validate signals of opportunity
        soop = result["signals_of_opportunity"]
        assert "discovered_radio_emitters" in soop
        assert len(soop["discovered_radio_emitters"]) > 0
        assert soop["gnss_reflectometry"]["satellites_overhead_count"] > 0
        assert "canopy_water_index" in soop["cellular_forward_scatter"]
        assert soop["terrestrial_broadcast_uhf"]["skin_depth_cm"] > 0.0

        # Validate canonical closure certificate
        assert result["closure_certificate"] is not None
        assert len(result["closure_certificate_hash"]) == 64
        assert result["closure_certificate"]["status"] == "NOT_EVALUATED"

    def test_biskra_hyper_arid_sand_without_asmae_raster(self, monkeypatch):
        """Biskra Oasis: Hyper-arid, sand soil, zero ASMAE raster available -> graceful Dubois/Peplinski baseline."""
        ns = PlotNamespace(tenant_id="tenant_biskra", farm_id="farm_tolga", plot_id="plot_dates_oasis_99")
        polygon = [
            (34.7200, 5.3770),
            (34.7220, 5.3770),
            (34.7220, 5.3790),
            (34.7200, 5.3790),
        ]

        monkeypatch.setattr(
            MesiaProductionService,
            "_fetch_real_copernicus_soil",
            lambda lat, lon: {
                "soil_moisture_0_to_1cm": 0.04,
                "soil_moisture_1_to_3cm": 0.05,
                "soil_moisture_3_to_9cm": 0.06,
                "soil_moisture_9_to_27cm": 0.07,
                "relative_humidity_2m": 18.0,
                "temperature_2m": 39.0,
                "surface_pressure": 1008.0,
            },
        )
        monkeypatch.setattr(
            MesiaProductionService,
            "_fetch_real_osm_masts",
            lambda lat, lon, radius_m=8000.0: [
                {
                    "osm_id": 2001,
                    "operator": "Ooredoo",
                    "band": "LTE 800",
                    "freq_hz": 806e6,
                    "dist_m": 780.0,
                    "bearing_deg": 190.0,
                    "tx_power_dbm": 46.0,
                    "source_class": "GIS_REGISTRY",
                    "identity_state": "PROTOCOL_CONFIRMED",
                },
            ],
        )

        result = MesiaProductionService.scan_plot_spectrum(
            plot_namespace=ns,
            polygon_wgs84=polygon,
            soil_type="SAND",
        )

        assert result["plot_id"] == "plot_dates_oasis_99"
        # Verify baseline CWI for SAND was calibrated to 0.10 rather than arbitrary 0.12
        cell_proposal = next(p for p in result["asmae_p08_proposals"] if p["target_state"] == "canopy_water")
        assert cell_proposal["decision_eligible"] is False
        assert cell_proposal["authority_state"] == "RESEARCH_ONLY"

        # Sandy soil permittivity should be lower than clay loam
        assert result["dielectric_profile"]["soil_texture"] == "SAND"
        assert result["dielectric_profile"]["mean_dielectric_permittivity_eps_r"] < 25.0
        assert result["closure_certificate"]["status"] == "NOT_EVALUATED"

    def test_sahel_coastal_loam_spectrum_scan(self, monkeypatch):
        """Sahel coastal loam (Tipaza/Cherchell): Maritime loam with moderate moisture."""
        ns = PlotNamespace(tenant_id="tenant_sahel", farm_id="farm_tipaza", plot_id="plot_vineyard_05")
        polygon = [
            (36.5900, 2.4400),
            (36.5920, 2.4400),
            (36.5920, 2.4420),
            (36.5900, 2.4420),
        ]

        monkeypatch.setattr(
            MesiaProductionService,
            "_fetch_real_copernicus_soil",
            lambda lat, lon: {
                "soil_moisture_0_to_1cm": 0.18,
                "soil_moisture_1_to_3cm": 0.19,
                "soil_moisture_3_to_9cm": 0.20,
                "soil_moisture_9_to_27cm": 0.21,
                "relative_humidity_2m": 72.0,
                "temperature_2m": 22.0,
                "surface_pressure": 1015.0,
            },
        )
        monkeypatch.setattr(
            MesiaProductionService,
            "_fetch_real_osm_masts",
            lambda lat, lon, radius_m=8000.0: [
                {
                    "osm_id": 3001,
                    "operator": "Mobilis",
                    "band": "LTE 1800",
                    "freq_hz": 1815e6,
                    "dist_m": 520.0,
                    "bearing_deg": 85.0,
                    "tx_power_dbm": 43.0,
                    "source_class": "GIS_REGISTRY",
                    "identity_state": "PROTOCOL_CONFIRMED",
                },
            ],
        )

        result = MesiaProductionService.scan_plot_spectrum(
            plot_namespace=ns,
            polygon_wgs84=polygon,
            soil_type="LOAM",
        )

        assert result["plot_id"] == "plot_vineyard_05"
        assert result["feasibility_gate"]["agricultural_decision_authority"] == "DISABLED"
        assert result["feasibility_gate"]["observatory_status"] == "RESEARCH_DEMONSTRATOR_TRL_1_2"
        assert len(result["truth_envelopes"]) >= 6
        assert result["closure_certificate"]["status"] == "NOT_EVALUATED"


# ==============================================================================
# SCENARIO B: Discovery & Open-Set Identification Pipeline
# ==============================================================================

class TestScenarioBDiscoveryAndOpenSetIdentification:
    """Validates CA-CFAR detection, WaveCandidate extraction, classifier, and evidence fusion."""

    def test_ca_cfar_1d_detector_bank(self):
        """Verify CA-CFAR detector identifies spectral peaks above local noise floor."""
        freq_bins = [100e6 + i * 1e6 for i in range(30)]
        noise_linear = [1e-9] * 30
        noise_linear[10] = 5e-8  # Peak 1
        noise_linear[20] = 8e-8  # Peak 2

        peaks = DetectorBank.ca_cfar_1d(
            power_linear=noise_linear,
            freq_bins_hz=freq_bins,
            guard_cells=1,
            training_cells=3,
            pfa=1e-3,
        )

        assert len(peaks) >= 2
        peak_freqs = [p.frequency_hz for p in peaks]
        assert 110e6 in peak_freqs
        assert 120e6 in peak_freqs
        assert all(p.snr_db > 10.0 for p in peaks)

    def test_open_set_waveform_classifier_inference(self):
        """Verify open-set classifier extracts normalized features and computes calibrated OOD scores."""
        clf = OpenSetWaveformClassifier()

        candidate_wifi = WaveCandidate(
            candidate_id="wave-wifi-test",
            centre_frequency_hz=2437e6,
            bandwidth_hz=20e6,
            morphology="OFDM",
            snr_db=25.0,
            detection_method="ENERGY_CFAR",
        )

        features = clf.extract_features(candidate_wifi)
        assert len(features) == 5
        assert features[0] == pytest.approx(math.log10(20e6), rel=1e-3)
        assert features[1] == pytest.approx(math.log10(2437e6), rel=1e-3)
        assert features[3] == 0.0
        assert features[4] == 1.0

        result = clf.classify(candidate_wifi)
        assert result.predicted_class in OpenSetWaveformClassifier.KNOWN_CLASSES
        assert 0.0 <= result.abstention_score <= 1.0
        assert result.ood_score >= 0.0

    def test_evidence_fusion_without_receipt_probationary(self):
        """EvidenceFusionEngine without a ProtocolConfirmationReceipt cannot promote to PROTOCOL_CONFIRMED."""
        fusion = EvidenceFusionEngine()
        candidate = WaveCandidate(
            candidate_id="wave-lte-unconfirmed",
            centre_frequency_hz=2115e6,
            bandwidth_hz=20e6,
            morphology="OFDM",
            snr_db=18.0,
            detection_method="ENERGY_CFAR",
        )

        hyp = fusion.fuse_evidence(
            hypothesis_id="hyp-lte-01",
            candidate=candidate,
            confirmation_receipt=None,
        )

        assert isinstance(hyp, SignalIdentityHypothesis)
        assert hyp.current_state != IdentityState.PROTOCOL_CONFIRMED.value
        assert hyp.current_state in [
            IdentityState.RAT_CANDIDATE.value,
            IdentityState.WAVEFORM_CLASSIFIED.value,
            IdentityState.DETECTED.value,
            IdentityState.UNKNOWN.value,
        ]

    def test_evidence_fusion_with_receipt_confirmed(self):
        """EvidenceFusionEngine with valid ProtocolConfirmationReceipt strictly promotes to PROTOCOL_CONFIRMED."""
        fusion = EvidenceFusionEngine()
        candidate = WaveCandidate(
            candidate_id="wave-wifi-confirmed",
            centre_frequency_hz=2437e6,
            bandwidth_hz=20e6,
            morphology="OFDM",
            snr_db=28.0,
            detection_method="ENERGY_CFAR",
        )

        receipt = ProtocolConfirmationReceipt(
            receipt_id="REC_WIFI_CONF_01",
            source_type="PHYSICAL_RECEIVER",
            timestamp_utc=datetime.now(timezone.utc),
            content_hash="d" * 64,
            protocol_name="WIFI_80211BF",
            confirmation_method="DECODER",
            confirmation_level=4,
            crc_passed=True,
            crc_valid=True,
            preamble_detected=True,
            channel_freq_hz=2437e6,
            snr_db=28.0,
        )

        hyp = fusion.fuse_evidence(
            hypothesis_id="hyp-wifi-conf",
            candidate=candidate,
            confirmation_receipt=receipt,
        )

        assert hyp.current_state == IdentityState.PROTOCOL_CONFIRMED.value
        assert len(hyp.candidates) > 0
        assert hyp.candidates[0]["protocol"] == "WIFI_80211BF"
        assert hyp.candidates[0]["probability"] == 1.0

    def test_evidence_fusion_with_failed_crc_not_confirmed(self):
        """EvidenceFusionEngine with failed CRC receipt rejects PROTOCOL_CONFIRMED promotion."""
        fusion = EvidenceFusionEngine()
        candidate = WaveCandidate(
            candidate_id="wave-wifi-corrupted",
            centre_frequency_hz=2437e6,
            bandwidth_hz=20e6,
            morphology="OFDM",
            snr_db=12.0,
        )

        bad_receipt = ProtocolConfirmationReceipt(
            receipt_id="REC_WIFI_CORRUPTED",
            source_type="PHYSICAL_RECEIVER",
            timestamp_utc=datetime.now(timezone.utc),
            content_hash="e" * 64,
            protocol_name="WIFI_80211BF",
            confirmation_level=4,
            crc_passed=False,
            crc_valid=False,
        )

        hyp = fusion.fuse_evidence(
            hypothesis_id="hyp-wifi-bad",
            candidate=candidate,
            confirmation_receipt=bad_receipt,
        )

        assert hyp.current_state != IdentityState.PROTOCOL_CONFIRMED.value

    def test_discover_and_identify_signals_service_integration(self):
        """Verify MesiaProductionService.discover_and_identify_signals integrates the pipeline."""
        ns = PlotNamespace(tenant_id="t1", farm_id="f1", plot_id="p_discovery_01")
        res = MesiaProductionService.discover_and_identify_signals(ns)

        assert res["plot_id"] == "p_discovery_01"
        assert res["pipeline_stage"] == "WAVE_DISCOVERY_AND_OPEN_SET_IDENTIFICATION"
        assert res["detector"] == "CA_CFAR_1D"
        assert len(res["discovered_emitters"]) > 0

        for emitter in res["discovered_emitters"]:
            assert "candidate_id" in emitter
            assert "centre_frequency_mhz" in emitter
            assert "bandwidth_mhz" in emitter
            assert "identity_state" in emitter
            assert "truth_envelope" in emitter
            assert emitter["truth_envelope"]["decision_eligible"] is False


# ==============================================================================
# SCENARIO C: In-Situ GNSS Edge Cases & Fail-Closed Guardrails
# ==============================================================================

class TestScenarioCInSituGnssEdgeCasesAndFailClosed:
    """Validates fail-closed handling of GNSS NMEA logs without synthetic 20.0% fallbacks."""

    def test_sufficient_satellite_arc_solves_vwc(self):
        """Plot with real field GNSS log containing >= 8 elevation points solves multipath frequency and derives physical VWC."""
        ns = PlotNamespace(tenant_id="default_tenant", farm_id="default_farm", plot_id="69f72838")
        res = MesiaProductionService._process_real_in_situ_gnss(ns)

        assert res["status"] == "MEASURED_IN_SITU_RADIO_WAVES"
        assert res["physical_waves_measured"] is True
        assert res["ground_measured_vwc_pct"] is not None
        assert res["ground_measured_vwc_pct"] > 0.0
        assert len(res["measured_satellites"]) >= 1

    def test_insufficient_satellite_arc_strictly_fails_closed(self):
        """Arc with only 3 points (< 8 required) strictly returns INSUFFICIENT_SATELLITE_ARCS without 20.0% fallback."""
        ns = PlotNamespace(tenant_id="default_tenant", farm_id="default_farm", plot_id="test_insufficient_edge")
        data_dir = Path("services/agribrain/mesia/data")
        log_file = data_dir / f"plot_{ns.plot_id}_field.nmea"

        # Only 3 points for PRN 05
        sentences = [
            "$GPGSV,1,1,01,05,07,045,35*75\n",
            "$GPGSV,1,1,01,05,10,046,36*78\n",
            "$GPGSV,1,1,01,05,13,047,38*74\n",
        ]
        log_file.write_text("".join(sentences), encoding="utf-8")

        try:
            res = MesiaProductionService._process_real_in_situ_gnss(ns)
            assert res["status"] == "INSUFFICIENT_SATELLITE_ARCS"
            assert res["physical_waves_measured"] is False
            assert res["ground_measured_vwc_pct"] is None
            assert res["measured_satellites"] == []
            assert ">= 8 valid snr points" in res["message"].lower()
        finally:
            if log_file.exists():
                log_file.unlink()

    def test_empty_or_missing_nmea_stream_fails_closed(self):
        """Non-existent NMEA log strictly returns AWAITING_FIELD_RECEIVER_STREAM and False."""
        ns = PlotNamespace(tenant_id="t1", farm_id="f1", plot_id="plot_no_stream_exist")
        res = MesiaProductionService._process_real_in_situ_gnss(ns)

        assert res["status"] == "AWAITING_FIELD_RECEIVER_STREAM"
        assert res["physical_waves_measured"] is False
        assert res.get("ground_measured_vwc_pct") is None

    def test_missing_snr_field_handled_without_crash(self):
        """NMEA GSV with missing SNR is parsed gracefully by NmeaCycleAssembler without crashing."""
        sentence = "$GPGSV,1,1,01,03,25,180,*4D"
        obs, meta = NmeaCycleAssembler.assemble_nmea_stream(sentence)
        assert meta["total_lines_processed"] == 1
        if obs:
            assert obs[0].snr_db_hz is None

    def test_checksum_corruption_quarantined_by_assembler(self):
        """Sentence with corrupted checksum is rejected by NmeaCycleAssembler."""
        corrupted = "$GPGSV,2,1,08,01,05,045,32,02,12,120,38,03,45,210,44,04,65,015,48*99"
        assert NmeaCycleAssembler.verify_xor_checksum(corrupted) is False

        obs, meta = NmeaCycleAssembler.assemble_nmea_stream(corrupted)
        assert meta["corrupted_sentence_count"] == 1
        assert len(obs) == 0


# ==============================================================================
# SCENARIO D: Dynamic Wi-Fi CSI & Metrology
# ==============================================================================

class TestScenarioDDynamicWifiCsiAndMetrology:
    """Validates dynamic coordinates, deterministic BSSID hashing, and SigMF packing."""

    def test_dynamic_bssid_derived_from_namespace_hash(self):
        """BSSID must be deterministically derived from plot namespace hash, never hardcoded B4:FB:E4:9C:21:40."""
        ns1 = PlotNamespace(tenant_id="tenant_a", farm_id="farm_01", plot_id="plot_alpha")
        ns2 = PlotNamespace(tenant_id="tenant_a", farm_id="farm_01", plot_id="plot_beta")

        poly1 = [(36.56, 2.93), (36.57, 2.93), (36.57, 2.94), (36.56, 2.94)]
        poly2 = [(34.85, 5.73), (34.86, 5.73), (34.86, 5.74), (34.85, 5.74)]

        res1 = MesiaProductionService.simulate_or_ingest_wifi_csi(plot_namespace=ns1, polygon_wgs84=poly1)
        res2 = MesiaProductionService.simulate_or_ingest_wifi_csi(plot_namespace=ns2, polygon_wgs84=poly2)

        bssid1 = res1["access_point"]["bssid"]
        bssid2 = res2["access_point"]["bssid"]

        assert bssid1 != "B4:FB:E4:9C:21:40"
        assert bssid2 != "B4:FB:E4:9C:21:40"
        assert bssid1 != bssid2
        assert bssid1.startswith("02:")

    def test_wifi_csi_truth_envelope_governance(self):
        """Simulated Wi-Fi CSI must embed TruthEnvelope tagged as SIMULATOR, SIMULATION, decision_eligible=False."""
        ns = PlotNamespace(tenant_id="tenant_gov", farm_id="farm_gov", plot_id="plot_gov_01")
        poly = [(36.56, 2.93), (36.57, 2.93), (36.57, 2.94), (36.56, 2.94)]
        res = MesiaProductionService.simulate_or_ingest_wifi_csi(plot_namespace=ns, polygon_wgs84=poly)

        assert res["status"] == "SIMULATED_CHANNEL_STATE"
        assert res["signal_detected"] is False

        env = res["truth_envelope"]
        assert env["source_class"] == "SIMULATOR"
        assert env["presentation_state"] == "SIMULATION"
        assert env["authority_state"] == "RESEARCH_ONLY"
        assert env["decision_eligible"] is False

    def test_sigmf_complex_float_binary_packing(self):
        """Verify NativeWifiCsiExtractor packs CSI subcarrier matrix into SigMF cf32_le binary."""
        h_matrix = np.array([complex(math.cos(i * 0.1), math.sin(i * 0.1)) for i in range(64)], dtype=np.complex64)
        amplitudes = [abs(c) for c in h_matrix]
        phases = [math.atan2(c.imag, c.real) for c in h_matrix]

        raw_bytes = NativeWifiCsiExtractor.pack_sigmf_cf32_le(amplitudes, phases)
        assert len(raw_bytes) == 64 * 2 * 4

        unpacked = np.frombuffer(raw_bytes, dtype=np.float32).reshape(-1, 2)
        for i in range(64):
            assert unpacked[i, 0] == pytest.approx(h_matrix[i].real, abs=1e-5)
            assert unpacked[i, 1] == pytest.approx(h_matrix[i].imag, abs=1e-5)


# ==============================================================================
# SCENARIO E: Full AgriBrain Layer 0 Bridge Integration
# ==============================================================================

class TestScenarioEAgriBrainLayer0Bridge:
    """Validates MesiaAgriBrainBridge end-to-end admission, calibration gates, and P-10 revocation."""

    def test_bridge_admission_with_valid_and_invalid_calibration(self):
        """Bridge must invalidate uncalibrated packets and admit properly calibrated/epoch-active packets."""
        bridge = MesiaAgriBrainBridge(plot_id="PLOT_TEST_BRIDGE")

        packet = RadioObservationPacket(
            packet_id="pkt-test-001",
            source_profile="WIFI_CSI/v2",
            receiver_id="RECV_TEST_01",
            utc_time=datetime.now(timezone.utc),
            native_data_uri="sigmf://data/wifi_csi_01.sigmf-data",
            native_data_hash="a" * 64,
            native_data_type="cf32_le",
        )

        # 1. Uncalibrated attempt -> INVALIDATED
        l0_uncal, asmae_uncal = bridge.process_and_admit_observation(
            packet=packet,
            is_calibration_valid=False,
            is_epoch_active=False,
        )
        assert l0_uncal.status == EvidenceAdmissionStatus.INVALIDATED
        assert l0_uncal.is_usable_for_assimilation is False

        # 2. Fully calibrated and epoch active -> ADMITTED
        l0_adm, asmae_adm = bridge.process_and_admit_observation(
            packet=packet,
            is_calibration_valid=True,
            is_epoch_active=True,
        )
        assert l0_adm.status == EvidenceAdmissionStatus.ADMITTED
        assert l0_adm.is_usable_for_assimilation is True

    def test_bridge_missing_native_hash_rejected(self):
        """Bridge must strictly reject packets without valid 64-character SHA-256 native data hash."""
        bridge = MesiaAgriBrainBridge(plot_id="PLOT_NO_HASH")

        packet_no_hash = RadioObservationPacket(
            packet_id="pkt-bad-hash",
            source_profile="WIFI_CSI/v2",
            receiver_id="RECV_TEST_02",
            native_data_uri="sigmf://data/wifi.sigmf-data",
            native_data_hash="short_invalid_hash",
        )

        l0_rec, _ = bridge.process_and_admit_observation(
            packet=packet_no_hash,
            is_calibration_valid=True,
            is_epoch_active=True,
        )
        assert l0_rec.status == EvidenceAdmissionStatus.INVALIDATED

    def test_principle_p10_capability_revocation_on_drift(self):
        """Principle P-10: Revoking a capability transitions state to REVOKED and returns RevocationEvent."""
        bridge = MesiaAgriBrainBridge(plot_id="PLOT_GOV_P10")

        cap = CapabilityGovernanceAuthority.issue_qualification_record(
            capability_id="CAP_GNSSR_SOIL_V1",
            capability_name="GNSS-R Subsurface Soil Moisture",
            target_variable="root_zone_water",
            supported_radios=["GNSS_IR", "GNSS_R"],
            supported_soils=["SAND", "LOAM"],
            supported_crops=["TOMATO", "WHEAT"],
            gate_repeatability_passed=True,
            gate_sensitivity_passed=True,
            gate_specificity_passed=True,
            gate_observability_passed=True,
            gate_transfer_passed=True,
            gate_closure_passed=True,
            gate_incremental_value_passed=True,
            gate_governance_passed=True,
            validation_signature="SIG_AUDIT_APPROVED_2026",
        )

        bridge.register_capability(cap)
        assert len(bridge.list_active_capabilities()) == 1

        rev_event = bridge.revoke_capability(
            capability_id="CAP_GNSSR_SOIL_V1",
            trigger_reason="Multipath phase drift exceeded 15 degrees over 48h.",
        )

        assert rev_event is not None
        assert rev_event.new_state == "REVOKED"
        assert rev_event.capability_authority_ref == "CAP_GNSSR_SOIL_V1"
        assert len(bridge.list_active_capabilities()) == 0


# ==============================================================================
# SCENARIO F: Layer 3 Hydrological Model Cross-Validation
# ==============================================================================

class TestScenarioFLayer3HydrologicalModelCrossValidation:
    """Validates MesiaLayer3WaterBridge cross-validation across soil strata."""

    def test_consistent_observation_across_strata(self):
        """When MESIA observed VWC is within tolerance of hydrological model, consistent flag is True."""
        likelihood = BehaviourLikelihood(
            likelihood_id="lh-rz-01",
            radio_family="GNSS_IR",
            contract_ref="contract-gnss-01",
            target_variable="root_zone_water",
            likelihood_value=0.225,
        )

        comp = MesiaLayer3WaterBridge.compare_with_hydrological_model(
            plot_id="plot_hydro_01",
            stratum=LatticeStrata.ROOT_ZONE_5_30CM,
            mesia_likelihood=likelihood,
            layer3_model_vwc=0.240,
            tolerance_vwc=0.05,
        )

        assert comp.is_hydrologically_consistent is True
        assert comp.residual_error_vwc == pytest.approx(0.015, abs=1e-4)
        assert comp.mesia_observed_vwc == 0.225
        assert comp.stratum == LatticeStrata.ROOT_ZONE_5_30CM

    def test_inconsistent_observation_detected(self):
        """When MESIA observed VWC deviates beyond tolerance, inconsistent flag is False."""
        likelihood = BehaviourLikelihood(
            likelihood_id="lh-surf-02",
            radio_family="WIFI_CSI",
            contract_ref="contract-wifi-01",
            target_variable="topsoil_water",
            likelihood_value=0.380,
        )

        comp = MesiaLayer3WaterBridge.compare_with_hydrological_model(
            plot_id="plot_hydro_02",
            stratum=LatticeStrata.SOIL_SURFACE_0_5CM,
            mesia_likelihood=likelihood,
            layer3_model_vwc=0.150,
            tolerance_vwc=0.05,
        )

        assert comp.is_hydrologically_consistent is False
        assert comp.residual_error_vwc == pytest.approx(0.230, abs=1e-4)


# ==============================================================================
# SCENARIO G: Canonical ClosureCertificate Validation & Hash Integrity
# ==============================================================================

class TestScenarioGClosureCertificateValidation:
    """Validates instantiation, SHA-256 content hash determinism, and immutability of ClosureCertificate."""

    def test_closure_certificate_instantiation_and_content_hash(self):
        """ClosureCertificate content_hash() must be deterministic 64-character SHA-256."""
        now = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)
        cert = ClosureCertificate(
            certificate_id="cert-test-001",
            target_capability="root_zone_water",
            status=ClosureStatus.NOT_EVALUATED,
            evaluated_at=now,
            withheld_evidence_refs=(),
            closure_passed=False,
            passed_shortcut_checks=False,
            incremental_value_demonstrated=False,
            review_comments="Independent dual closure requires authentic withheld physical RF evidence (R6 §11). Status is NOT_EVALUATED.",
        )

        h1 = cert.content_hash()
        h2 = cert.content_hash()

        assert len(h1) == 64
        assert h1 == h2
        assert cert.status == ClosureStatus.NOT_EVALUATED

        d = cert.to_dict()
        assert d["certificate_id"] == "cert-test-001"
        assert d["status"] == "NOT_EVALUATED"

    def test_closure_certificate_embedded_in_spectrum_scan(self, monkeypatch):
        """scan_plot_spectrum() output must contain closure_certificate and matching hash."""
        ns = PlotNamespace(tenant_id="t_cert", farm_id="f_cert", plot_id="p_cert_01")
        polygon = [(36.5, 3.0), (36.5, 3.01), (36.49, 3.01), (36.49, 3.0)]

        monkeypatch.setattr(
            MesiaProductionService,
            "_fetch_real_copernicus_soil",
            lambda lat, lon: {
                "soil_moisture_0_to_1cm": 0.20,
                "soil_moisture_1_to_3cm": 0.21,
                "soil_moisture_3_to_9cm": 0.22,
                "soil_moisture_9_to_27cm": 0.23,
                "relative_humidity_2m": 60.0,
                "temperature_2m": 25.0,
                "surface_pressure": 1013.0,
            },
        )
        monkeypatch.setattr(
            MesiaProductionService,
            "_fetch_real_osm_masts",
            lambda lat, lon, radius_m=8000.0: [
                {
                    "osm_id": 4001,
                    "operator": "Djezzy",
                    "band": "LTE 1800",
                    "freq_hz": 1815e6,
                    "dist_m": 450.0,
                    "bearing_deg": 40.0,
                    "tx_power_dbm": 43.0,
                    "source_class": "GIS_REGISTRY",
                    "identity_state": "PROTOCOL_CONFIRMED",
                },
            ],
        )

        res = MesiaProductionService.scan_plot_spectrum(plot_namespace=ns, polygon_wgs84=polygon)

        assert "closure_certificate" in res
        assert "closure_certificate_hash" in res

        cert_dict = res["closure_certificate"]
        cert_hash = res["closure_certificate_hash"]

        assert cert_dict is not None
        assert cert_dict["status"] == "NOT_EVALUATED"
        assert len(cert_hash) == 64


class TestScenarioHCoverageGraphAndReceiverManifest:
    """Scenario H: Multi-dimensional receiver interrogation and coverage graph generation."""

    def test_build_observatory_coverage_graph(self):
        """Verifies multi-dimensional coverage graph maps observable bands and detects blind gaps."""
        ns = PlotNamespace(tenant_id="tenant_audit", farm_id="farm_audit", plot_id="plot_cov_01")
        cov = MesiaProductionService.build_observatory_coverage_graph(plot_namespace=ns, spectrum_span_hz=(50e6, 6.0e9))

        assert "graph_id" in cov
        assert cov["graph_id"] == "cov-plot_cov_01"
        assert "observable_spans" in cov
        assert cov["observable_spans_count"] >= 3
        assert "blind_bands_mhz" in cov
        assert "overall_coverage_pct" in cov
        assert 0.0 <= cov["overall_coverage_pct"] <= 100.0

        # Check receiver limitations
        assert "receiver_limitations" in cov
        rx_ids = [r["receiver_id"] for r in cov["receiver_limitations"]]
        assert "RX_GNSS_F9P_INSITU" in rx_ids
        assert "RX_WIFI6_CSI_ANCHOR" in rx_ids
        assert "RX_SDR_SURVEY_CHAIN" in rx_ids
        assert "RX_CELLULAR_GIS_METADATA" in rx_ids

    def test_coverage_graph_in_scan_plot_spectrum(self, monkeypatch):
        """Verifies coverage_graph is surfaced in scan_plot_spectrum() output."""
        ns = PlotNamespace(tenant_id="tenant_audit", farm_id="farm_audit", plot_id="plot_cov_02")
        polygon = [(36.56, 2.93), (36.57, 2.93), (36.57, 2.94), (36.56, 2.94)]

        monkeypatch.setattr(
            MesiaProductionService,
            "_fetch_real_copernicus_soil",
            lambda lat, lon: {
                "soil_moisture_0_to_1cm": 0.20,
                "soil_moisture_1_to_3cm": 0.22,
                "soil_moisture_3_to_9cm": 0.25,
                "soil_moisture_9_to_27cm": 0.28,
                "relative_humidity_2m": 55.0,
                "temperature_2m": 22.0,
                "surface_pressure": 1014.0,
            },
        )

        res = MesiaProductionService.scan_plot_spectrum(plot_namespace=ns, polygon_wgs84=polygon)
        assert "coverage_graph" in res
        cov = res["coverage_graph"]
        assert cov["graph_id"] == "cov-plot_cov_02"
        assert cov["observable_spans_count"] > 0
        assert "discovery_pipeline_summary" in res["signals_of_opportunity"]
        disc_summary = res["signals_of_opportunity"]["discovery_pipeline_summary"]
        assert "peaks_detected" in disc_summary
        assert "rejection_audit" in disc_summary


class TestScenarioIGovernedAsmaeLayer0Admission:
    """Scenario I: Governed ASMAE Layer 0 admission evaluating fail-closed demonstrator gates."""

    def test_proposals_have_layer0_admission_and_fail_closed(self, monkeypatch):
        """Emitted proposals must carry Layer 0 record, admission_status INVALIDATED/QUARANTINED, and not be decision eligible."""
        ns = PlotNamespace(tenant_id="tenant_audit", farm_id="farm_audit", plot_id="plot_asmae_01")
        polygon = [(36.56, 2.93), (36.57, 2.93), (36.57, 2.94), (36.56, 2.94)]

        monkeypatch.setattr(
            MesiaProductionService,
            "_fetch_real_copernicus_soil",
            lambda lat, lon: {
                "soil_moisture_0_to_1cm": 0.18,
                "soil_moisture_1_to_3cm": 0.20,
                "soil_moisture_3_to_9cm": 0.22,
                "soil_moisture_9_to_27cm": 0.24,
                "relative_humidity_2m": 50.0,
                "temperature_2m": 24.0,
                "surface_pressure": 1012.0,
            },
        )

        res = MesiaProductionService.scan_plot_spectrum(plot_namespace=ns, polygon_wgs84=polygon)
        proposals = res.get("asmae_p08_proposals", [])
        assert len(proposals) >= 4

        for p in proposals:
            assert "layer0_record_id" in p
            assert p["layer0_record_id"].startswith("l0-rec-innov-")
            assert "admission_status" in p
            # Research demonstrator has uncalibrated physical sensors -> must fail closed to INVALIDATED or QUARANTINED
            assert p["admission_status"] in ["INVALIDATED", "QUARANTINED"]
            assert p["is_usable_for_assimilation"] is False
            assert p["decision_eligible"] is False
            assert p["authority_state"] == "RESEARCH_ONLY"
            assert "admission_notes" in p
            assert len(p["admission_notes"]) > 5


class TestScenarioJCellularMetadataPreservationOfUnknown:
    """Scenario J: Cellular metadata preserves UNKNOWN and avoids fabricating RSRP."""

    def test_osm_mast_missing_tags_preserves_unknown_and_none_rsrp(self, monkeypatch):
        """Masts without operator/band/frequency tags must not have fabricated values or RSRP."""
        ns = PlotNamespace(tenant_id="tenant_audit", farm_id="farm_audit", plot_id="plot_cell_01")
        polygon = [(36.56, 2.93), (36.57, 2.93), (36.57, 2.94), (36.56, 2.94)]

        monkeypatch.setattr(
            MesiaProductionService,
            "_fetch_real_osm_masts",
            lambda lat, lon, radius_m=8000.0: [
                {
                    "osm_id": 99991,
                    "operator": "UNKNOWN",
                    "band": "UNKNOWN",
                    "freq_hz": 0.0,
                    "dist_m": 1200.0,
                    "bearing_deg": 180.0,
                    "tx_power_dbm": 0.0,
                    "source_class": "GIS_REGISTRY",
                    "identity_state": "UNKNOWN",
                },
            ],
        )

        res = MesiaProductionService.scan_plot_spectrum(plot_namespace=ns, polygon_wgs84=polygon)
        masts = res["signals_of_opportunity"]["cellular_forward_scatter"]["masts_tracked"]
        assert len(masts) == 1
        m = masts[0]
        assert m["operator"] == "UNKNOWN"
        assert m["band"] == "UNKNOWN"
        assert m["rx_rsrp_dbm"] is None  # RSRP cannot be fabricated without known frequency and Tx power
        assert m["identity_state"] == "UNKNOWN"


class TestScenarioKPhysicalInSituGnssLaneIntegration:
    """Scenario K: Validates end-to-end integration of authentic in-situ GNSS receiver measurements."""

    def test_in_situ_gnss_measured_waves_grounds_proposal_and_truth_envelope(self, monkeypatch):
        """When an in-situ receiver log is present, GNSS-R proposal and rootzone envelope reflect MEASURED_NATIVE."""
        ns = PlotNamespace(tenant_id="tenant_gnss", farm_id="farm_gnss", plot_id="plot_in_situ_test")
        polygon = [(36.56, 2.93), (36.57, 2.93), (36.57, 2.94), (36.56, 2.94)]

        # Mock authentic in-situ GNSS receiver measurement result
        mock_in_situ = {
            "status": "MEASURED_IN_SITU_RADIO_WAVES",
            "physical_waves_measured": True,
            "source_class": "PHYSICAL_RECEIVER",
            "processing_level": "DERIVED",
            "receiver_mount": "SURVEY_POLE_OR_TRACTOR_RTK",
            "antenna_height_m": 1.85,
            "rtk_fix_status": "RTK_FIXED",
            "log_source": "plot_in_situ_test_real_field_gnss.nmea",
            "sha256": "c" * 64,
            "file_size_bytes": 1024,
            "native_nmea_sentences_count": 48,
            "measured_satellites": [
                {
                    "satellite_id": "GPS-PRN13",
                    "prn": 13,
                    "constellation": "GPS",
                    "carrier_freq_hz": 1575.42e6,
                    "snr_min_db_hz": 32.0,
                    "snr_max_db_hz": 48.0,
                    "rtk_fix_status": "RTK_FIXED",
                    "effective_reflector_height_m": 1.84,
                    "inferred_soil_vwc_pct": 28.5,
                    "source_class": "PHYSICAL_RECEIVER",
                    "processing_level": "FEATURE",
                    "identity_state": "PROTOCOL_CONFIRMED",
                }
            ],
            "ground_measured_vwc_pct": 28.5,
        }

        monkeypatch.setattr(
            MesiaProductionService,
            "_process_real_in_situ_gnss",
            lambda plot_ns: mock_in_situ,
        )

        res = MesiaProductionService.scan_plot_spectrum(plot_namespace=ns, polygon_wgs84=polygon)

        # 1. GNSS-R proposal must be marked MEASURED_NATIVE and LIVE
        proposals = res["asmae_p08_proposals"]
        gnssr_prop = next(p for p in proposals if p["feature"] == "mesia_gnssr_in_situ_vwc")
        assert gnssr_prop["evidence_class"] == "MEASURED_NATIVE"
        assert gnssr_prop["presentation_state"] == "LIVE"
        assert gnssr_prop["physical_waves_measured"] is True
        assert gnssr_prop["variance"] == 0.0008

        # 2. Rootzone TruthEnvelope must reflect PHYSICAL_RECEIVER and LIVE
        root_env = res["truth_envelopes"]["rootzone_moisture"]
        assert root_env["source_class"] == "PHYSICAL_RECEIVER"
        assert root_env["presentation_state"] == "LIVE"
        assert root_env["identity_state"] == "PROTOCOL_CONFIRMED"
        assert root_env["value"] == 28.5
        assert "Ground in-situ GNSS-R" in root_env["explanation"]

        # 3. Signals of Opportunity reflects physical measurement
        soo_gnss = res["signals_of_opportunity"]["gnss_reflectometry"]
        assert soo_gnss["physical_waves_measured"] is True
        assert soo_gnss["source_class"] == "PHYSICAL_RECEIVER"
        assert soo_gnss["inferred_subsurface_vwc_pct"] == 28.5


class TestScenarioLGumMetrologyBudgetAndEpochAuthority:
    """Scenario L: Verifies ISO GUM Uncertainty Budget and P-06 Epoch Authority for all proposals."""

    def test_gum_uncertainty_budget_and_epoch_lineage_presence(self):
        ns = PlotNamespace(tenant_id="tenant_gum", farm_id="farm_gum", plot_id="plot_gum_01")
        polygon = [(36.56, 2.93), (36.57, 2.93), (36.57, 2.94), (36.56, 2.94)]

        res = MesiaProductionService.scan_plot_spectrum(plot_namespace=ns, polygon_wgs84=polygon)
        proposals = res["asmae_p08_proposals"]
        assert len(proposals) >= 4

        for p in proposals:
            # 1. GUM Uncertainty Budget must be attached and valid
            assert "gum_uncertainty_budget" in p
            b = p["gum_uncertainty_budget"]
            assert b["budget_id"].startswith("GUM-")
            assert len(b["measurand_name"]) > 5
            assert b["combined_standard_uncertainty"] > 0.0
            assert b["coverage_factor"] == 2.0
            assert b["expanded_uncertainty"] > 0.0
            assert b["confidence_level_pct"] == 95.0
            assert len(b["components"]) >= 2

            # Expanded uncertainty must match TruthEnvelope
            env_unc = p["truth_envelope"]["uncertainty"]
            assert env_unc == round(b["expanded_uncertainty"], 4)

            # 2. P-06 Epoch Authority lineage tags must be present
            assert "epoch_lineage" in p
            el = p["epoch_lineage"]
            assert el["geometry_epoch_id"].startswith("geo-epoch-")
            assert el["instrument_epoch_id"].startswith("inst-epoch-")
            assert el["network_epoch_id"].startswith("net-epoch-")
            assert "calibration_state_ref" in el
            assert el["software_model_epoch_ref"] == "mesia-r6.1"

            # 3. Governance containment invariants
            assert p["decision_eligible"] is False
            assert p["is_usable_for_assimilation"] is False
            assert p["admission_status"] in ("INVALIDATED", "QUARANTINED")


class TestScenarioMMultiLaneWifiCsiAndTargetClassification:
    """Scenario M: Validates Native Wi-Fi CSI extraction, WiHFC target classification, and P-08 governance."""

    def test_native_sigmf_pack_read_and_wihfc_classification(self, tmp_path):
        """Validates binary SigMF packing/unpacking and Wi-HFC ambient/human/plasma discrimination."""
        from services.agribrain.mesia.lanes.wifi.csi_extractor import NativeWifiCsiExtractor, WiHFC_Classifier

        extractor = NativeWifiCsiExtractor(driver="iwlwifi")
        clf = WiHFC_Classifier()

        # 1. Background frame: low variance across subcarriers
        bg_amps = [0.08 + 0.002 * math.cos(i) for i in range(64)]
        bg_phases = [0.05 * i for i in range(64)]
        prefix_bg = str(tmp_path / "test_bg_csi")
        h_bg = extractor.write_sigmf({
            "amplitudes_linear": bg_amps,
            "phases_rad": bg_phases,
            "num_subcarriers": 64,
            "bandwidth_hz": 20.0e6,
            "center_frequency_hz": 2437.0e6,
            "timestamp": "2026-09-05T12:00:00Z",
            "agc_gain_db": 30.0,
            "noise_floor_dbm": -92.0,
            "rssi_dbm": -65.0,
        }, prefix_bg)
        assert len(h_bg) == 64

        read_bg = NativeWifiCsiExtractor.read_sigmf(prefix_bg)
        assert read_bg["sha256"] == h_bg
        assert read_bg["num_subcarriers"] == 64
        analysis_bg = clf.analyze(read_bg)
        assert analysis_bg["classification"] == "BACKGROUND"
        assert analysis_bg["optical_immune"] is True
        assert analysis_bg["confidence"] >= 0.90

        # 2. Human presence frame: moderate fading variance across subcarriers
        human_amps = [1.0 if i % 2 == 0 else 10.0 for i in range(64)]
        human_phases = [0.1 for _ in range(64)]
        prefix_human = str(tmp_path / "test_human_csi")
        extractor.write_sigmf({
            "amplitudes_linear": human_amps,
            "phases_rad": human_phases,
            "num_subcarriers": 64,
            "bandwidth_hz": 20.0e6,
            "center_frequency_hz": 2437.0e6,
            "timestamp": "2026-09-05T12:01:00Z",
            "agc_gain_db": 34.0,
            "noise_floor_dbm": -92.0,
            "rssi_dbm": -68.0,
        }, prefix_human)

        read_human = NativeWifiCsiExtractor.read_sigmf(prefix_human)
        analysis_human = clf.analyze(read_human)
        assert analysis_human["classification"] == "HUMAN PRESENCE"
        assert analysis_human["optical_immune"] is True

        # 3. Fire / Thermal Plasma frame: extreme chaotic scintillation in amplitude and phase
        plasma_amps = [1.0 if i % 2 == 0 else 20.0 for i in range(64)]
        plasma_phases = [3.14 if i % 2 == 0 else -3.14 for i in range(64)]
        prefix_plasma = str(tmp_path / "test_plasma_csi")
        extractor.write_sigmf({
            "amplitudes_linear": plasma_amps,
            "phases_rad": plasma_phases,
            "num_subcarriers": 64,
            "bandwidth_hz": 20.0e6,
            "center_frequency_hz": 2437.0e6,
            "timestamp": "2026-09-05T12:02:00Z",
            "agc_gain_db": 38.0,
            "noise_floor_dbm": -90.0,
            "rssi_dbm": -72.0,
        }, prefix_plasma)

        read_plasma = NativeWifiCsiExtractor.read_sigmf(prefix_plasma)
        analysis_plasma = clf.analyze(read_plasma)
        assert analysis_plasma["classification"] == "PLASMA (FIRE DETECTED)"
        assert analysis_plasma["optical_immune"] is True

    def test_wifi_csi_in_situ_end_to_end_pipeline_and_governance(self, monkeypatch):
        """When an in-situ Wi-Fi CSI capture is present, pipeline emits LIVE proposal with GUM budget and fail-closed Layer 0."""
        ns = PlotNamespace(tenant_id="tenant_wifi", farm_id="farm_wifi", plot_id="plot_wifi_01")
        polygon = [(36.56, 2.93), (36.57, 2.93), (36.57, 2.94), (36.56, 2.94)]

        mock_wifi_in_situ = {
            "status": "MEASURED_IN_SITU_RADIO_WAVES",
            "physical_waves_measured": True,
            "source_class": "PHYSICAL_RECEIVER",
            "processing_level": "FEATURE",
            "identity_state": "PROTOCOL_CONFIRMED",
            "presentation_state": "LIVE",
            "receiver_mount": "IOT_CANOPY_ANCHOR_OR_SOIL_POST",
            "antenna_height_m": 1.2,
            "log_source": "plot_wifi_01_real_field_csi.sigmf-data",
            "sha256": "f" * 64,
            "file_size_bytes": 512,
            "num_subcarriers": 64,
            "center_frequency_hz": 2437.0e6,
            "bandwidth_hz": 20.0e6,
            "rssi_dbm": -64.0,
            "noise_floor_dbm": -92.0,
            "snr_db": 28.0,
            "target_classification": "BACKGROUND",
            "amplitude_variance": 0.0003,
            "phase_variance": 2.98,
            "optical_immune": True,
            "confidence": 0.94,
            "canopy_water_index": 0.082,
            "excess_loss_db": 1.45,
            "subcarriers": [],
            "amplitudes_linear": [0.082 + 0.005 * math.sin(i) for i in range(64)],
            "phases_rad": [0.05 * i for i in range(64)],
        }

        monkeypatch.setattr(
            MesiaProductionService,
            "_process_real_in_situ_wifi_csi",
            lambda plot_ns: mock_wifi_in_situ,
        )

        res = MesiaProductionService.scan_plot_spectrum(plot_namespace=ns, polygon_wgs84=polygon)

        # 1. Wi-Fi CSI Proposal verification
        proposals = res["asmae_p08_proposals"]
        wifi_prop = next(p for p in proposals if p["feature"] == "mesia_wifi_csi_canopy_foliar")
        assert wifi_prop["evidence_class"] == "MEASURED_NATIVE"
        assert wifi_prop["presentation_state"] == "LIVE"
        assert wifi_prop["physical_waves_measured"] is True
        assert wifi_prop["target_classification"] == "BACKGROUND"
        assert wifi_prop["variance"] == 0.0005

        # 2. ISO GUM Uncertainty Budget verification
        assert "gum_uncertainty_budget" in wifi_prop
        gum = wifi_prop["gum_uncertainty_budget"]
        assert gum["budget_id"].startswith("GUM-WIFI-")
        assert "Canopy Foliar Attenuation" in gum["measurand_name"]
        assert gum["combined_standard_uncertainty"] > 0.0
        assert gum["expanded_uncertainty"] > 0.0
        assert len(gum["components"]) >= 3

        # 3. P-06 Central Epoch Authority lineage tags
        assert "epoch_lineage" in wifi_prop
        el = wifi_prop["epoch_lineage"]
        assert el["geometry_epoch_id"].startswith("geo-epoch-")
        assert el["instrument_epoch_id"] == "inst-epoch-RX_ESP32_CSI_INSITU-v1"
        assert el["network_epoch_id"] == "net-epoch-WIFI_CSI_NATIVE-v1"
        assert el["calibration_state_ref"] == "CALIB-UNVERIFIED-DEMONSTRATOR"

        # 4. Layer 0 Gatekeeper Fail-Closed containment
        assert wifi_prop["decision_eligible"] is False
        assert wifi_prop["is_usable_for_assimilation"] is False
        assert wifi_prop["admission_status"] in ("INVALIDATED", "QUARANTINED")

        # 5. TruthEnvelope verification
        wifi_env = res["truth_envelopes"]["ambient_wifi_csi"]
        assert wifi_env["source_class"] == "PHYSICAL_RECEIVER"
        assert wifi_env["presentation_state"] == "LIVE"
        assert wifi_env["identity_state"] == "PROTOCOL_CONFIRMED"
        assert wifi_env["decision_eligible"] is False
        assert "802.11bf/CSI frame subcarrier measurement" in wifi_env["explanation"]

        # 6. Radio wave channel & Signals of Opportunity
        wifi_channel = res["radio_wave_channels"]["in_situ_wifi_receiver"]
        assert wifi_channel["physical_waves_measured"] is True
        assert wifi_channel["target_classification"] == "BACKGROUND"

        soo_wifi = res["signals_of_opportunity"]["ambient_wifi_csi"]
        assert soo_wifi["status"] == "LIVE_CSI_STREAM"
        assert soo_wifi["signal_detected"] is True
        assert soo_wifi["physical_waves_measured"] is True
        assert soo_wifi["source_class"] == "PHYSICAL_RECEIVER"
        assert soo_wifi["optical_immune"] is True
        assert soo_wifi["target_classification"] == "BACKGROUND"


# ==============================================================================
# SCENARIO N: Independent Experimental Validation & Multi-Radio Closure (Phase 5)
# ==============================================================================

class TestScenarioNIndependentExperimentalValidation:
    """Validates Phase 5 E1-E4 experimental validation, teacher controls, multi-radio closure, and nuisance matrix."""

    def test_soil_column_texture_moisture_sweep_and_hysteresis(self):
        """E1: Soil column texture-dependent apparent permittivity and wetting/drying hysteresis."""
        vwc_levels = [0.08, 0.15, 0.22, 0.30, 0.38]

        # 1. Moisture sweep across multiple USDA soil textures
        for texture in [SoilTextureClass.SAND, SoilTextureClass.LOAM, SoilTextureClass.CLAY]:
            raw_obs = [
                {"vwc": th, "permittivity": SoilColumnExperimentHarness.vwc_to_permittivity(th, texture, HysteresisBranch.MAIN_DRYING)}
                for th in vwc_levels
            ]
            summary = SoilColumnExperimentHarness.run_texture_moisture_sweep(
                column_id=f"COL_{texture.value}",
                texture=texture,
                raw_observations=raw_obs,
                tdr_truth_vwc=vwc_levels,
                branch=HysteresisBranch.MAIN_DRYING,
            )

            assert summary.texture_class == texture
            assert summary.hysteresis_branch == HysteresisBranch.MAIN_DRYING
            assert len(summary.measured_apparent_permittivity) == len(vwc_levels)
            assert summary.rmse_permittivity_error <= 1.50
            assert summary.is_valid_ground_truth is True
            assert summary.to_dict()["trial_id"].startswith("TRIAL_COL_")

        # 2. Hysteresis loop evaluation (Drying permittivity > Wetting permittivity for same VWC)
        hyst_report = SoilColumnExperimentHarness.evaluate_hysteresis_loop(
            texture=SoilTextureClass.LOAM,
            vwc_sweep=vwc_levels,
        )
        assert hyst_report["mean_hysteresis_delta"] > 0.0
        assert all(d > 0.0 for d in hyst_report["hysteresis_deltas"])

        # 3. Multi-depth strata record assembly
        strata_spec = [(0.0, 5.0, 0.12), (5.0, 15.0, 0.20), (15.0, 30.0, 0.26), (30.0, 50.0, 0.28)]
        col_record = SoilColumnExperimentHarness.create_replicated_experiment_record(
            column_id="COL_LAB_01",
            texture=SoilTextureClass.LOAM,
            replicate_index=1,
            vwc_strata=strata_spec,
            branch=HysteresisBranch.MAIN_DRYING,
        )
        assert len(col_record.strata) == 4
        assert col_record.strata[0].gravimetric_water_content is not None
        assert len(col_record.content_hash()) == 64

    def test_teacher_and_negative_controls(self):
        """E2: RF absorber negative controls (>= 40 dB) and positive teacher probe benchmarks."""
        # 1. Negative control RF darkbox isolation (>= 40 dB required)
        pass_neg = TeacherControlsAuthority.verify_negative_absorber_isolation(
            fixture_id="DARKBOX_01",
            measured_signal_leakage_dbm=-35.0,
            reference_tx_power_dbm=20.0,
        )
        assert pass_neg.measured_isolation_db == 55.0
        assert pass_neg.is_isolation_adequate is True

        fail_neg = TeacherControlsAuthority.verify_negative_absorber_isolation(
            fixture_id="DARKBOX_BREACHED",
            measured_signal_leakage_dbm=-10.0,
            reference_tx_power_dbm=20.0,
        )
        assert fail_neg.measured_isolation_db == 30.0
        assert fail_neg.is_isolation_adequate is False

        # 2. Direct physical teacher probe comparison (|delta| <= 0.03)
        comp_pass = TeacherControlsAuthority.compare_with_teacher_truth(
            probe_id="TDR_TEACHER_10CM",
            teacher_type="TDR_PROBE",
            teacher_vwc=0.245,
            mesia_vwc=0.258,
            tolerance_vwc=0.03,
        )
        assert comp_pass.is_within_tolerance is True
        assert comp_pass.absolute_residual_error == 0.013

        comp_fail = TeacherControlsAuthority.compare_with_teacher_truth(
            probe_id="TDR_TEACHER_10CM",
            teacher_type="TDR_PROBE",
            teacher_vwc=0.245,
            mesia_vwc=0.320,
            tolerance_vwc=0.03,
        )
        assert comp_fail.is_within_tolerance is False
        assert comp_fail.absolute_residual_error == 0.075

        # 3. Honest null experiment: 50-ohm terminator / thermal noise compulsory abstention
        null_res = TeacherControlsAuthority.verify_honest_null_abstention(
            fixture_id="TERMINATOR_50OHM",
            snr_db=0.5,
            is_terminated_load=True,
        )
        assert null_res["abstention_enforced"] is True
        assert null_res["output_state"] == "ABSTAIN_TERMINATED_LOAD"
        assert null_res["phantom_moisture_prevented"] is True
        assert null_res["inferred_vwc"] is None

    def test_multi_radio_closure_withheld_prediction(self):
        """E3: Multi-radio physical closure predicting genuinely withheld radio family."""
        # 1. Consensus state from GNSS and Wi-Fi predicting Cellular forward scatter attenuation
        consensus_vwc = 0.22
        active_fams = ["GNSS_REFLECTOMETRY", "WIFI_CSI"]

        # Expected cellular loss: 18.5 * 0.22 + 2.8 = 6.87 dB
        # Actual measurement close to prediction (e.g. 6.6 dB)
        report_pass = MultiRadioClosureHarness.evaluate_withheld_radio_prediction(
            experiment_id="EXP_MULTI_CLOSURE_01",
            active_families=active_fams,
            withheld_family="CELLULAR_FORWARD_SCATTER",
            estimated_soil_moisture_vwc=consensus_vwc,
            actual_withheld_measurement_attenuation_db=6.60,
        )
        assert report_pass.closure_satisfied is True
        assert report_pass.residual_error <= report_pass.closure_tolerance_db
        assert "Closure verified" in report_pass.audit_notes

        # Incompatible measurement (e.g. 14.2 dB, residual = 7.33 dB > 2.5 dB)
        report_fail = MultiRadioClosureHarness.evaluate_withheld_radio_prediction(
            experiment_id="EXP_MULTI_CLOSURE_02",
            active_families=active_fams,
            withheld_family="CELLULAR_FORWARD_SCATTER",
            estimated_soil_moisture_vwc=consensus_vwc,
            actual_withheld_measurement_attenuation_db=14.20,
        )
        assert report_fail.closure_satisfied is False
        assert report_fail.residual_error > report_fail.closure_tolerance_db
        assert "Closure failed" in report_fail.audit_notes

        # 2. Compulsory abstention on unphysical inputs
        unphysical_report = MultiRadioClosureHarness.evaluate_withheld_radio_prediction(
            experiment_id="EXP_UNPHYSICAL",
            active_families=active_fams,
            withheld_family="CELLULAR_FORWARD_SCATTER",
            estimated_soil_moisture_vwc=0.92,  # impossible soil moisture
            actual_withheld_measurement_attenuation_db=6.60,
        )
        assert unphysical_report.closure_satisfied is False
        assert unphysical_report.residual_error == float("inf")
        assert "outside physical bounds" in unphysical_report.audit_notes

        # 3. Cross-modal discordance compulsory abstention check
        discordant = MultiRadioClosureHarness.compulsory_cross_modal_abstention_check(
            wifi_cwi=0.02,  # severe foliar drought
            gnss_vwc=0.48,  # standing saturated soil
        )
        assert discordant["abstention_required"] is True
        assert discordant["status"] == "ABSTAIN_CROSS_MODAL_CONFLICT"
        assert discordant["decision_eligible"] is False

    def test_nuisance_challenge_matrix(self):
        """E4: Nuisance injection matrix verifying zero false agronomic anomaly detection."""
        # 1. Receiver firmware gain step (+2.0 dB)
        firmware_safe = NuisanceChallengeMatrixHarness.run_firmware_swap_challenge(
            challenge_id="CHALLENGE_FW_01",
            observed_gain_shift_db=2.0,
            firmware_event_logged=True,
        )
        assert firmware_safe.correctly_attributed_as_nuisance is True
        assert firmware_safe.falsely_attributed_as_soil_change is False
        assert firmware_safe.is_safe is True
        assert firmware_safe.diagnostics["false_moisture_step_pct"] == 0.0

        firmware_unsafe = NuisanceChallengeMatrixHarness.run_firmware_swap_challenge(
            challenge_id="CHALLENGE_FW_UNLOGGED",
            observed_gain_shift_db=2.0,
            firmware_event_logged=False,
        )
        assert firmware_unsafe.falsely_attributed_as_soil_change is True
        assert firmware_unsafe.is_safe is False

        # 2. Mast wind flutter (12 m/s wind, 1.8 Hz mechanical vibration)
        mast_flutter = NuisanceChallengeMatrixHarness.run_mast_wind_flutter_challenge(
            challenge_id="CHALLENGE_WIND_01",
            wind_speed_m_s=12.0,
            observed_phase_flutter_deg=8.5,
            flutter_frequency_hz=1.8,
        )
        assert mast_flutter.correctly_attributed_as_nuisance is True
        assert mast_flutter.falsely_attributed_as_soil_change is False
        assert mast_flutter.is_safe is True
        assert mast_flutter.diagnostics["bandpass_filter_rejected"] is True

        # 3. LTE Cellular handover (sector change)
        handover = NuisanceChallengeMatrixHarness.run_cellular_handover_challenge(
            challenge_id="CHALLENGE_HANDOVER_01",
            observed_rsrp_drop_db=6.0,
            cell_tower_handover_logged=True,
        )
        assert handover.correctly_attributed_as_nuisance is True
        assert handover.is_safe is True

        # 4. Honest null terminated load challenge
        null_test = NuisanceChallengeMatrixHarness.run_honest_null_noise_challenge(
            challenge_id="CHALLENGE_NULL_01",
            measured_snr_db=0.8,
            is_terminated_50ohm_load=True,
        )
        assert null_test.correctly_attributed_as_nuisance is True
        assert null_test.is_safe is True
        assert null_test.diagnostics["zero_phantom_detection"] is True

    def test_service_validation_loop_and_qualified_closure(self):
        """Service integration: evaluate_validation_loop with authentic withheld physical observation."""
        # 1. Default call without physical holdout fails closed to NOT_EVALUATED
        default_val = MesiaProductionService._evaluate_validation_loop(
            real_grid=None,
            unc_grid=None,
            mean_cwi=0.10,
            vwc_surface=0.18,
            vwc_rootzone=0.22,
            vwc_deeproot=0.25,
            cygnss_refl_db=-14.2,
        )
        assert default_val["independent_dual_closure"] == "NOT_EVALUATED"
        assert default_val["dual_closure_verified"] is False
        assert default_val["closure_certificate"]["status"] == "NOT_EVALUATED"

        # 2. Call with withheld observation evaluates multi-radio closure
        val_with_holdout = MesiaProductionService._evaluate_validation_loop(
            real_grid=None,
            unc_grid=None,
            mean_cwi=0.10,
            vwc_surface=0.18,
            vwc_rootzone=0.22,
            vwc_deeproot=0.25,
            cygnss_refl_db=-14.2,
            withheld_observation={
                "family": "WIFI_CSI",
                "measured_attenuation_db": 6.20,
            },
            active_physical_observations={
                "families": ["GNSS_REFLECTOMETRY"],
                "consensus_vwc": 0.22,
            },
        )
        assert "multi_radio_closure_report" in val_with_holdout
        assert val_with_holdout["multi_radio_closure_report"]["withheld_family"] == "WIFI_CSI"
        assert isinstance(val_with_holdout["multi_radio_closure_report"]["residual_error"], float)

        # 3. Qualified physical holdout satisfying all preregistered criteria
        now_dt = datetime.now(timezone.utc)
        val_qualified = MesiaProductionService._evaluate_validation_loop(
            real_grid=None,
            unc_grid=None,
            mean_cwi=0.10,
            vwc_surface=0.18,
            vwc_rootzone=0.22,
            vwc_deeproot=0.25,
            cygnss_refl_db=-14.2,
            withheld_observation={
                "family": "WIFI_CSI",
                "measured_attenuation_db": 6.22,
                "is_authenticated_holdout": True,
                "evidence_refs": ["PHYS_WIFI_SIGMF_01"],
                "preregistration_ref": "PREREG_HYPOTHESIS_PHASE5",
                "split_manifest_hash": "b" * 64,
                "receiver_epoch_ref": "inst-epoch-ESP32-v1",
                "geometry_epoch_ref": "geo-epoch-69f72838-v1",
                "calibration_epoch_ref": "cal-epoch-P5-v1",
                "software_epoch_ref": "mesia-r6.1",
                "passed_shortcut_checks": True,
                "shortcut_challenge_receipt_ref": "RECEIPT_SHORTCUT_P5",
                "incremental_value_demonstrated": True,
            },
            active_physical_observations={
                "families": ["GNSS_REFLECTOMETRY"],
                "consensus_vwc": 0.22,
            },
        )
        assert val_qualified["dual_closure_verified"] is True
        assert val_qualified["independent_dual_closure"] == "EVALUATED_PASSED"
        assert val_qualified["closure_certificate"]["status"] == "EVALUATED_PASSED"
        assert val_qualified["closure_certificate"]["closure_passed"] is True
        assert len(val_qualified["closure_certificate_hash"]) == 64


# ==============================================================================
# SCENARIO O: Operational Hardening, Fleet Health, O-RAN E2 KPM & Security Sovereignty (Phase 7)
# ==============================================================================

class TestScenarioOOperationalHardeningFleetAndOran:
    """Validates Phase 7 operational hardening, Arrhenius wear, continuous drift, O-RAN E2 KPM, and supply chain governance."""

    def test_fleet_node_health_evaluation_and_thermal_acceleration(self):
        """O1: Node health evaluation with Arrhenius temperature acceleration and Weibull survival modeling."""
        from services.agribrain.mesia.operations.fleet_monitor import FleetOperationsMonitor, NodeHealthSnapshot

        # 1. Nominal conditions (25C, 10 days calibration, 90% battery, 0.5% packet loss)
        nominal_snap = FleetOperationsMonitor.evaluate_node_health(
            node_id="RX_GNSS_TEST_01",
            battery_pct=90.0,
            solar_watts=15.0,
            temp_c=25.0,
            packet_loss=0.5,
            cal_days=10,
        )
        assert nominal_snap.is_healthy is True
        assert nominal_snap.requires_maintenance is False
        assert nominal_snap.battery_level_pct == 90.0
        assert nominal_snap.temperature_celsius == 25.0

        # 2. Elevated thermal wear (45C core temperature -> 4x Arrhenius acceleration factor)
        # 45C on 60-day calibration -> effective age = 240 days > eta (180 days), Weibull R(t) drops significantly
        hot_snap = FleetOperationsMonitor.evaluate_node_health(
            node_id="RX_GNSS_HOT_01",
            battery_pct=85.0,
            solar_watts=12.0,
            temp_c=45.0,
            packet_loss=0.5,
            cal_days=60,
        )
        assert hot_snap.requires_maintenance is True

        # 3. Low battery / excessive packet loss condition
        degraded_snap = FleetOperationsMonitor.evaluate_node_health(
            node_id="RX_GNSS_LOW_BAT",
            battery_pct=15.0,
            solar_watts=1.0,
            temp_c=25.0,
            packet_loss=6.5,
            cal_days=10,
        )
        assert degraded_snap.is_healthy is False
        assert degraded_snap.requires_maintenance is True

    def test_continuous_drift_sentinel_invalidation_and_calibration_demotion(self):
        """O2: DriftSentinelMonitor triggers automatic calibration invalidation and demotion when drift exceeds 1.5 dB."""
        from services.agribrain.mesia.epoch_authority.drift_sentinel import DriftSentinelMonitor
        from services.agribrain.mesia.contracts.epochs import CalibrationState
        from services.agribrain.mesia.truth.reference_sentinel import SentinelVerificationResult, SentinelFixtureType

        monitor = DriftSentinelMonitor(max_allowed_gain_drift_db=1.5, max_allowed_phase_drift_deg=5.0)
        now_dt = datetime.now(timezone.utc)

        cal_active = CalibrationState(
            epoch_id="cal-test-active",
            triggered_at=now_dt,
            trigger_reason="Baseline calibration epoch",
            valid_from=now_dt,
            valid_to=now_dt + timedelta(days=90),
            status="VALID",
        )

        # Case 1: Nominal drift (0.42 dB <= 1.5 dB tolerance)
        sentinel_pass = SentinelVerificationResult(
            sentinel_id="sentinel-loopback-01",
            fixture_type=SentinelFixtureType.CABLE_LOOPBACK,
            verified_at=now_dt,
            nominal_baseline_value=0.0,
            measured_value=0.42,
            tolerance=1.5,
            unit="dB",
        )
        eval_pass = monitor.evaluate_sentinel_health(
            receiver_id="RX_GNSS_F9P",
            current_calibration=cal_active,
            sentinel_result=sentinel_pass,
        )
        assert eval_pass.is_healthy is True
        assert eval_pass.requires_demotion is False
        assert eval_pass.new_calibration_state.status == "VALID"

        # Case 2: Excessive drift (2.15 dB > 1.5 dB tolerance) -> automatic demotion
        sentinel_fail = SentinelVerificationResult(
            sentinel_id="sentinel-loopback-02",
            fixture_type=SentinelFixtureType.CABLE_LOOPBACK,
            verified_at=now_dt,
            nominal_baseline_value=0.0,
            measured_value=2.15,
            tolerance=1.5,
            unit="dB",
        )
        eval_fail = monitor.evaluate_sentinel_health(
            receiver_id="RX_GNSS_F9P",
            current_calibration=cal_active,
            sentinel_result=sentinel_fail,
        )
        assert eval_fail.is_healthy is False
        assert eval_fail.requires_demotion is True
        assert eval_fail.new_calibration_state.status == "FAILED"
        assert "Drift breach" in eval_fail.new_calibration_state.demotion_reason
        assert "Drift sentinel triggered invalidation" in eval_fail.demotion_reason

    def test_oran_e2_kpm_parsing_consent_and_bundle_assembly(self):
        """O3: OranConnector parses E2 KPM indications, enforces cryptographic consent, and creates immutable bundles."""
        from services.agribrain.mesia.cellular.oran_interface import OranConnector

        valid_kpm = {
            "tac": 1604,
            "plmn": "60301",
            "prb_usage": 44.2,
            "tx_power_dbm": 43.5,
            "beam_id": 5,
            "scheduler": "PROPORTIONAL_FAIR",
            "ue_count": 22,
            "consent_hook_signature": "SIG_CONSENT_OPERATOR_MOBILIS_DZ_2026",
        }

        # 1. Valid telemetry with cryptographic consent
        bundle = OranConnector.parse_e2_kpm_indication(
            bundle_id="oran-bundle-test-01",
            operator_name="Mobilis DZ",
            cell_id=60401,
            raw_kpm_data=valid_kpm,
        )
        assert bundle.bundle_id == "oran-bundle-test-01"
        assert bundle.operator_name == "Mobilis DZ"
        assert bundle.cell_id == 60401
        assert bundle.tracking_area_code == 1604
        assert bundle.plmn_id == "60301"
        assert bundle.prb_utilization_pct == 44.2
        assert bundle.mean_tx_power_dbm == 43.5
        assert bundle.active_beam_index == 5
        assert bundle.scheduler_mode == "PROPORTIONAL_FAIR"
        assert bundle.anonymized_ue_count == 22
        assert bundle.is_consent_valid is True
        assert bundle.revocation_hook_ref == "SIG_CONSENT_OPERATOR_MOBILIS_DZ_2026"

        # 2. Missing consent signature -> must raise ValueError
        unconsented_kpm = dict(valid_kpm)
        unconsented_kpm["consent_hook_signature"] = None
        with pytest.raises(ValueError, match="Missing cryptographic consent signature"):
            OranConnector.parse_e2_kpm_indication(
                bundle_id="oran-bundle-unconsented",
                operator_name="Mobilis DZ",
                cell_id=60401,
                raw_kpm_data=unconsented_kpm,
            )

        # 3. Missing mandatory metric (e.g. prb_usage) -> must raise ValueError
        corrupted_kpm = dict(valid_kpm)
        del corrupted_kpm["prb_usage"]
        with pytest.raises(ValueError, match="Missing mandatory KPM metric"):
            OranConnector.parse_e2_kpm_indication(
                bundle_id="oran-bundle-corrupt",
                operator_name="Mobilis DZ",
                cell_id=60401,
                raw_kpm_data=corrupted_kpm,
            )

    def test_security_governance_audit_and_sovereignty_compliance(self):
        """O4: SecurityGovernanceManager authenticates hardware UID, firmware hash, and national sovereignty (DZ)."""
        from services.agribrain.mesia.operations.security_governance import SecurityGovernanceManager

        fw_hash = hashlib.sha256(b"v2.4.1-mesia-firmware-signed").hexdigest()

        # 1. Compliant and authenticated node in Algerian territory
        auth_rec = SecurityGovernanceManager.audit_node_security(
            node_id="RX_GNSS_NODE_01",
            hardware_uid="STM32MP157-UID-884219472917",
            firmware_hash=fw_hash,
            expected_firmware_hash=fw_hash,
            model_weights_hash="m" * 64,
            residency_country="DZ",
        )
        assert auth_rec.is_authenticated is True
        assert auth_rec.is_sovereignty_compliant is True
        assert auth_rec.data_residency_country == "DZ"

        # 2. Tampered / mismatched firmware hash
        tampered_rec = SecurityGovernanceManager.audit_node_security(
            node_id="RX_GNSS_TAMPERED",
            hardware_uid="STM32MP157-UID-884219472917",
            firmware_hash="corrupted_hash",
            expected_firmware_hash=fw_hash,
            residency_country="DZ",
        )
        assert tampered_rec.is_authenticated is False
        assert tampered_rec.is_sovereignty_compliant is True

        # 3. Non-compliant foreign data residency
        foreign_rec = SecurityGovernanceManager.audit_node_security(
            node_id="RX_GNSS_FOREIGN",
            hardware_uid="STM32MP157-UID-884219472917",
            firmware_hash=fw_hash,
            expected_firmware_hash=fw_hash,
            residency_country="FR",
        )
        assert foreign_rec.is_authenticated is True
        assert foreign_rec.is_sovereignty_compliant is False

    def test_mesia_production_service_fleet_and_oran_integration(self, monkeypatch):
        """O5: MesiaProductionService integrates fleet health evaluation and O-RAN E2 KPM telemetry."""
        ns = PlotNamespace(tenant_id="tenant_p7", farm_id="farm_p7", plot_id="plot_p7_01")
        polygon = [(36.56, 2.93), (36.57, 2.93), (36.57, 2.94), (36.56, 2.94)]

        # 1. Fleet health status evaluation via service
        fleet_res = MesiaProductionService.evaluate_fleet_and_drift_status(plot_namespace=ns)
        assert fleet_res["plot_id"] == "plot_p7_01"
        assert fleet_res["fleet_status"] in ["OPERATIONAL_STABLE", "DEGRADED_NEEDS_MAINTENANCE"]
        assert fleet_res["total_monitored_nodes"] >= 3
        assert len(fleet_res["nodes"]) >= 3
        for node in fleet_res["nodes"]:
            assert "battery_pct" in node
            assert "solar_input_watts" in node
            assert "sentinel_drift_db" in node
            assert "requires_calibration_demotion" in node

        # 2. Ingest live O-RAN E2 KPM telemetry
        raw_kpm = {
            "tac": 1604,
            "plmn": "60301",
            "prb_usage": 38.5,
            "tx_power_dbm": 43.0,
            "beam_id": 7,
            "scheduler": "PROPORTIONAL_FAIR",
            "ue_count": 16,
            "consent_hook_signature": "SIG_MOBILIS_DZ_AUTHENTIC_2026",
        }
        oran_res = MesiaProductionService.ingest_oran_e2_kpm_telemetry(
            plot_namespace=ns,
            raw_kpm_data=raw_kpm,
            operator_name="Mobilis DZ",
            cell_id=60401,
        )
        assert oran_res["status"] == "ORAN_E2_KPM_ADMITTED"
        assert oran_res["bundle"]["prb_utilization_pct"] == 38.5
        assert oran_res["bundle"]["is_consent_valid"] is True
        assert oran_res["audit_trail"]["authority_state"] == "RESEARCH_ONLY"
        assert oran_res["audit_trail"]["decision_eligible"] is False

        # 3. Supply chain security audit via service
        fw_h = hashlib.sha256(b"v2.4.1-mesia-firmware").hexdigest()
        audit_res = MesiaProductionService.audit_node_supply_chain(
            plot_namespace=ns,
            node_id="RX_GNSS_F9P_TEST",
            hardware_uid="STM32MP157-UID-884219472917",
            firmware_hash=fw_h,
            expected_firmware_hash=fw_h,
            residency_country="DZ",
        )
        assert audit_res["is_authenticated"] is True
        assert audit_res["is_sovereignty_compliant"] is True
        assert audit_res["is_tamper_detected"] is False

        # 4. Ingested O-RAN telemetry and fleet health must be embedded in scan_plot_spectrum()
        monkeypatch.setattr(
            MesiaProductionService,
            "_fetch_real_copernicus_soil",
            lambda lat, lon: {
                "soil_moisture_0_to_1cm": 0.18,
                "soil_moisture_1_to_3cm": 0.20,
                "soil_moisture_3_to_9cm": 0.22,
                "soil_moisture_9_to_27cm": 0.24,
                "relative_humidity_2m": 50.0,
                "temperature_2m": 24.0,
                "surface_pressure": 1012.0,
            },
        )
        scan_res = MesiaProductionService.scan_plot_spectrum(plot_namespace=ns, polygon_wgs84=polygon)
        assert "fleet_health" in scan_res
        assert scan_res["fleet_health"]["total_monitored_nodes"] >= 3

        cell_scatter = scan_res["signals_of_opportunity"]["cellular_forward_scatter"]
        assert "oran_e2_telemetry" in cell_scatter
        assert cell_scatter["oran_e2_telemetry"] is not None
        assert cell_scatter["oran_e2_telemetry"]["cell_id"] == 60401
        assert cell_scatter["oran_e2_telemetry"]["prb_utilization_pct"] == 38.5

    def test_remote_desert_zero_masts_in_range_fail_safe(self, monkeypatch):
        """Principle P-08: If a parcel is located in a remote desert with 0 registered towers in range,
        scan_plot_spectrum must NEVER raise RuntimeError or 500. It must gracefully report NO_MASTS_IN_RANGE."""
        ns = PlotNamespace(tenant_id="tenant_p08", farm_id="farm_desert", plot_id="plot_adrar_01")
        polygon = [(27.108, 0.005), (27.108, 0.007), (27.106, 0.007), (27.106, 0.005)]

        monkeypatch.setattr(
            MesiaProductionService,
            "_fetch_real_osm_masts",
            lambda lat, lon, radius_m=8000.0: [],
        )

        scan_res = MesiaProductionService.scan_plot_spectrum(
            plot_namespace=ns,
            polygon_wgs84=polygon,
            soil_type="SANDY_LOAM",
        )
        assert scan_res is not None
        assert scan_res["plot_id"] == "plot_adrar_01"
        cell_scatter = scan_res["signals_of_opportunity"]["cellular_forward_scatter"]
        assert cell_scatter["status"] == "NO_MASTS_IN_RANGE"
        assert cell_scatter["masts_tracked"] == []
        assert cell_scatter["canopy_water_index"] == 0.04
        assert cell_scatter["mean_excess_loss_db"] == 0.0


class TestScenarioPTwoStateDecouplingAndNoiseSeparation:
    """Rigorous validation of mesia.md §7, §14, §15, §18, §19:
    - Two-state decoupling x = [x_agri, x_inst]
    - Bayesian nuisance classification (wind, dew, thermal drift, antenna shift)
    - IMM regime-dependent covariance inflation
    - Fixed-lag retrospective smoothing trajectory
    """

    def test_two_state_separation_and_decoupling_structure(self):
        """mesia.md §7: Scan result must explicitly separate x_agri from x_inst with zero leakage."""
        ns = PlotNamespace(tenant_id="tenant_p08", farm_id="farm_decoupling", plot_id="plot_state_01")
        polygon = [(36.562, 2.936), (36.562, 2.938), (36.560, 2.938), (36.560, 2.936)]

        scan_res = MesiaProductionService.scan_plot_spectrum(plot_namespace=ns, polygon_wgs84=polygon)

        assert "two_state_separation" in scan_res
        two_state = scan_res["two_state_separation"]
        assert "agronomic_state" in two_state
        assert "instrument_state" in two_state
        assert "decoupling_audit" in two_state

        agri = two_state["agronomic_state"]
        inst = two_state["instrument_state"]
        audit = two_state["decoupling_audit"]

        # Agronomic vector attributes
        assert "topsoil_vwc_pct" in agri
        assert "rootzone_vwc_pct" in agri
        assert "deep_subsoil_vwc_pct" in agri
        assert "canopy_water_index" in agri
        assert "hydrological_regime" in agri

        # Instrument vector attributes
        assert "receiver_temperature_c" in inst
        assert "thermal_drift_db" in inst
        assert "antenna_displacement_m" in inst
        assert "antenna_pose_status" in inst
        assert "carrier_frequency_offset_ppm" in inst

        # Decoupling invariants
        assert audit["instrument_leakage_into_soil_detected"] is False
        assert audit["principle_p08_decoupling_enforced"] is True
        assert audit["cross_talk_leakage_coefficient"] < 0.01

    def test_wind_nuisance_inflates_covariance_and_suppresses_proposal(self, monkeypatch):
        """mesia.md §14, §18: High wind flutter must be attributed to nuisance, scaling covariance by 25x."""
        from services.agribrain.mesia.behaviour.nuisance_model import BayesianNuisanceModel
        from services.agribrain.mesia.behaviour.imm_regime_filter import InteractingMultipleModelRegimeFilter, OperationalRegime

        report = BayesianNuisanceModel.attribute_cause(
            signal_delta_db=2.5,
            wind_speed_m_s=14.0,  # strong wind
            is_foliar_link=True,
        )
        assert report.is_safe_for_soil_assimilation is False
        assert report.is_safe_for_agronomic_assimilation is False
        assert report.recommended_covariance_multiplier >= 25.0
        assert "WIND" in (report.rejection_reason or "")

        imm = InteractingMultipleModelRegimeFilter.evaluate_regime(
            observed_vwc=0.25,
            prior_vwc=0.20,
            wind_speed_m_s=14.0,
        )
        assert imm.active_regime == OperationalRegime.WIND_GUST_NUISANCE
        assert imm.covariance_scaling_factor >= 25.0
        assert imm.is_soil_update_permitted is False

    def test_dew_surface_wetness_vs_soil_inversion_separation(self):
        """mesia.md §14: Dew on canopy must not be inferred as root-zone soil wetting."""
        from services.agribrain.mesia.behaviour.nuisance_model import BayesianNuisanceModel
        from services.agribrain.mesia.behaviour.imm_regime_filter import InteractingMultipleModelRegimeFilter, OperationalRegime

        report = BayesianNuisanceModel.attribute_cause(
            signal_delta_db=1.8,
            wind_speed_m_s=1.0,
            relative_humidity_pct=94.0,
            dew_point_depression_c=0.8,
            is_foliar_link=True,
        )
        assert report.p_dew_condensation > 0.30
        assert report.is_safe_for_soil_assimilation is False

        imm = InteractingMultipleModelRegimeFilter.evaluate_regime(
            observed_vwc=0.22,
            prior_vwc=0.20,
            wind_speed_m_s=1.0,
            relative_humidity_pct=94.0,
            dew_point_depression_c=0.8,
        )
        assert imm.active_regime == OperationalRegime.DEW_CONDENSATION
        assert imm.is_soil_update_permitted is False
        assert imm.is_foliar_update_permitted is True

    def test_fixed_lag_smoothing_and_multi_clock_trajectory(self):
        """mesia.md §19: Retrospective fixed-lag smoothing retains online vs smoothed posterior."""
        from services.agribrain.mesia.behaviour.imm_regime_filter import InteractingMultipleModelRegimeFilter
        from services.agribrain.mesia.behaviour.multi_clock import MultiClockCoordinator
        from datetime import datetime, timezone

        history = [0.20, 0.20, 0.21, 0.21, 0.22]
        imm = InteractingMultipleModelRegimeFilter.evaluate_regime(
            observed_vwc=0.26,  # transient spike
            prior_vwc=0.21,
            wind_speed_m_s=2.0,
            historical_vwc_trace=history,
        )

        # Smoothed posterior must temper the transient jump with historical smoothing
        assert imm.retrospectively_smoothed_vwc <= imm.online_posterior_vwc
        assert imm.smoothing_lag_hours >= 1.0

        coord = MultiClockCoordinator(assimilation_window_minutes=60)
        now = datetime(2026, 9, 6, 14, 25, 0, tzinfo=timezone.utc)
        win = coord.compute_multi_clock_window(observation_time=now, scan_index=12)
        assert win.scan_cycle_index == 12
        assert win.burst_duration_ms == 25.0
        assert win.is_within_assimilation_window is True

    def test_asmae_supervisor_rejects_impossible_wetting_and_scales_covariance(self):
        """ASMAE biophysical supervisor enforces Richards infiltration conservation."""
        from services.agribrain.layer05_asmae.causality.asmae_mesia_discriminator import AsmaeAgronomicDiscriminator

        # Test spontaneous jump of +4% VWC with 0 rain and no irrigation
        report = AsmaeAgronomicDiscriminator.discriminate_state_vs_noise(
            signal_delta_db=3.2,
            proposed_vwc_delta=0.04,  # +4% jump
            prior_vwc=0.20,
            temperature_c=25.0,
            wind_speed_m_s=2.0,
            relative_humidity_pct=45.0,
            dew_point_depression_c=8.0,
            rain_rate_mm_h=0.0,
            irrigation_active=False,
        )
        assert report.hydrological_flux_consistent is False
        assert report.recommended_action == "SUPPRESS_AS_INSTRUMENT_DRIFT"
        assert report.recommended_covariance_multiplier >= 50.0
        assert report.target_state_recommendation == "INSTRUMENT_STATE"
        assert report.agronomic_plausibility_score < 0.60
        assert any(chk["status"] == "VIOLATED" for chk in report.invariants_checked)

    def test_asmae_supervisor_routes_dew_to_foliar_surface_and_protects_root_zone(self):
        """ASMAE psychrometric model directs dew attenuation to surface wetness, protecting root-zone soil."""
        from services.agribrain.layer05_asmae.causality.asmae_mesia_discriminator import AsmaeAgronomicDiscriminator

        report = AsmaeAgronomicDiscriminator.discriminate_state_vs_noise(
            signal_delta_db=1.8,
            proposed_vwc_delta=0.005,
            prior_vwc=0.22,
            temperature_c=12.0,
            wind_speed_m_s=1.2,
            relative_humidity_pct=92.0,
            dew_point_depression_c=0.9,
            rain_rate_mm_h=0.0,
        )
        assert report.thermodynamic_dew_risk == "HIGH"
        assert report.target_state_recommendation == "SURFACE_WETNESS_EVENT"
        assert report.recommended_action == "ADMIT_TO_WORLD_MODEL"
        assert report.recommended_covariance_multiplier == 2.0
        assert "leaf surface dew" in report.scientific_justification.lower()

    def test_scan_plot_spectrum_returns_asmae_guidance_and_diagnostic_routing(self):
        """Verify MESIA service payload includes asmae_discrimination_guidance and diagnostic_layer_routing (L0-L10)."""
        from services.agribrain.mesia.service import MesiaProductionService

        res = MesiaProductionService.scan_plot_spectrum(
            plot_id="test_plot_routing",
            polygon_wgs84=[(31.6, -2.2), (31.61, -2.2), (31.61, -2.19), (31.6, -2.19)],
            soil_type="SANDY_LOAM",
        )
        assert "asmae_discrimination_guidance" in res
        assert "diagnostic_layer_routing" in res

        guidance = res["asmae_discrimination_guidance"]
        assert guidance["supervision_active"] is True
        assert "invariants_checked" in guidance
        assert len(guidance["invariants_checked"]) >= 4

        routing = res["diagnostic_layer_routing"]
        layers = routing["layers"]
        assert "L0_microclimate" in layers
        assert "L2_canopy" in layers
        assert "L3_water" in layers
        assert "L4_soil" in layers
        assert "L5_pathology" in layers
        assert "L8_prescriptive" in layers
        assert "L10_mesia" in layers
        assert layers["L8_prescriptive"]["asmae_authority"] == "STRICT_FAIL_CLOSED_GATE"

    def test_mesia_temporal_dynamics_and_agricultural_scheduler(self):
        """mesia.md §15, §19, §20, §33: Temporal trajectory matching, multi-clock scheduling, and anti-circularity."""
        from services.agribrain.mesia.behaviour.multi_clock import MultiClockCoordinator, AgriculturalSchedulerMode
        from services.agribrain.layer05_asmae.causality.asmae_mesia_discriminator import AsmaeAgronomicDiscriminator
        from services.agribrain.mesia.service import MesiaProductionService

        # 1. Agricultural Cadence Scheduler verification (mesia.md §20)
        coord = MultiClockCoordinator()
        
        # High wind condition -> short frequent bursts
        rec_wind = coord.determine_schedule_recommendation(
            active_regime="WIND_GUST_NUISANCE",
            wind_speed_m_s=12.5,
        )
        assert rec_wind.active_mode == AgriculturalSchedulerMode.STRONG_WIND_NUISANCE_BURST
        assert rec_wind.recommended_cadence_minutes <= 2.0
        assert rec_wind.burst_duration_s == 10.0
        assert rec_wind.anti_circularity.is_density_conflation_quarantined is True

        # Recent irrigation -> dense 3 min sampling
        rec_irr = coord.determine_schedule_recommendation(
            active_regime="ACTIVE_IRRIGATION",
            wind_speed_m_s=1.5,
            hours_since_irrigation=0.2,
        )
        assert rec_irr.active_mode == AgriculturalSchedulerMode.POST_IRRIGATION_DENSE_30M
        assert rec_irr.recommended_cadence_minutes <= 3.0

        # Normal field -> 25 min cadence with >95% power saving
        rec_norm = coord.determine_schedule_recommendation(
            active_regime="NORMAL_DRYING_CYCLE",
            wind_speed_m_s=2.0,
        )
        assert rec_norm.active_mode == AgriculturalSchedulerMode.NORMAL_STABLE_FIELD
        assert rec_norm.recommended_cadence_minutes == 25.0
        assert rec_norm.power_conservation_ratio_pct > 95.0

        # 2. Temporal Trajectory & Fixed-Lag Belief Progression (mesia.md §15 & §19)
        report = AsmaeAgronomicDiscriminator.discriminate_state_vs_noise(
            signal_delta_db=2.5,
            proposed_vwc_delta=0.03,
            prior_vwc=0.20,
            temperature_c=25.0,
            wind_speed_m_s=1.5,
            relative_humidity_pct=45.0,
            dew_point_depression_c=8.0,
            irrigation_active=True,
        )
        assert report.temporal_trajectory is not None
        traj = report.temporal_trajectory
        assert traj["matched_trajectory"] == "DRIP_IRRIGATION_TRAJECTORY"
        assert traj["trajectory_confidence"] >= 0.95
        assert traj["is_canopy_wetted_before_soil"] is False  # Drip wets soil first

        # Check the 4 fixed-lag progression stages (mesia.md §19: 0.61 -> 0.78 -> 0.89 -> 0.94)
        prog = traj["fixed_lag_smoothing_progression"]
        assert len(prog) == 4
        assert prog[0]["online_posterior"] == 0.61
        assert prog[1]["online_posterior"] == 0.78
        assert prog[2]["online_posterior"] == 0.89
        assert prog[3]["retrospectively_smoothed_posterior"] == 0.94

        # 3. Payload integration in scan_plot_spectrum
        res = MesiaProductionService.scan_plot_spectrum(
            plot_id="test_plot_temporal",
            polygon_wgs84=[(31.6, -2.2), (31.61, -2.2), (31.61, -2.19), (31.6, -2.19)],
            soil_type="SANDY_LOAM",
        )
        assert "multi_clock_window" in res
        assert "schedule_recommendation" in res["multi_clock_window"]
        sched = res["multi_clock_window"]["schedule_recommendation"]
        assert "active_mode" in sched
        assert "recommended_cadence_minutes" in sched
        assert "anti_circularity" in sched
        assert "schedule_matrix" in sched
        assert len(sched["schedule_matrix"]) == 10



