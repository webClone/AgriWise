"""Test Suite for Package F01: Qualify provenance and numeric evidence at every admission boundary.

Requirements: AB-DAT-005, AB-DAT-006, AB-ARC-005, AB-ARC-006.

Verifies:
1. Temporal admission rejects non-finite scalars (inf, nan) and booleans.
2. Legitimate zero reliability (reading_reliability=0.0) is preserved and not replaced by 1.0.
3. Dictionary role qualifiers (SIMULATED, ESTIMATED, FALLBACK, UNAVAILABLE) are obeyed.
4. Soil assimilation qualifies probe provenance: simulated/synthetic probes do not confer OBSERVED authority.
5. Component admission records explicit rejection reasons for invalid numeric or excluded roles.
"""

from datetime import datetime, timezone
import math
import unittest

from services.agribrain.scientific_contracts.numeric import finite_real
from services.agribrain.scientific_contracts.observation import ASMAEObservationPayload
from services.agribrain.layer0.observation_packet import (
    DataStatus,
    ObservationPacket,
    ObservationSource,
    ObservationType,
    QAFlag,
    QAMetadata,
)
from services.agribrain.layer0.temporal_evidence import (
    _has_numeric,
    is_admitted_temporal_record,
    build_temporal_admission_ledger,
)
from services.agribrain.layer0.wrappers import (
    _infer_data_status,
    ensure_observation_packet,
)
from services.agribrain.layer3_water.contracts.assimilation_state import SoilObservationVector
from services.agribrain.layer3_water.contracts.authority import WaterPhysicsAuthority
from services.agribrain.layer3_water.contracts.state_factory import WaterStateFactory
from services.agribrain.layer3_water.assimilation.water_state_assimilator import WaterStateAssimilator
from services.agribrain.layer3_water.runner import WaterIntelligenceEngine


CUTOFF = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


class TestF01TemporalEvidenceAdmission(unittest.TestCase):
    """AB-DAT-005 / AB-ARC-005: Temporal admission numeric qualification."""

    def test_has_numeric_rejects_non_finite_and_booleans(self):
        self.assertFalse(_has_numeric({"ndvi": float("inf")}, ("ndvi",)))
        self.assertFalse(_has_numeric({"ndvi": float("-inf")}, ("ndvi",)))
        self.assertFalse(_has_numeric({"ndvi": float("nan")}, ("ndvi",)))
        self.assertFalse(_has_numeric({"ndvi": True}, ("ndvi",)))
        self.assertFalse(_has_numeric({"ndvi": False}, ("ndvi",)))
        self.assertFalse(_has_numeric({"ndvi": "0.45"}, ("ndvi",)))
        self.assertFalse(_has_numeric({"ndvi": None}, ("ndvi",)))
        self.assertFalse(_has_numeric({}, ("ndvi",)))

    def test_has_numeric_accepts_finite_real_and_valid_zero(self):
        self.assertTrue(_has_numeric({"ndvi": 0.0}, ("ndvi",)))
        self.assertTrue(_has_numeric({"ndvi": 0}, ("ndvi",)))
        self.assertTrue(_has_numeric({"ndvi": 0.65}, ("ndvi",)))
        self.assertTrue(_has_numeric({"other": "foo", "ndvi": -0.1}, ("ndvi",)))

    def test_is_admitted_temporal_record_fails_closed_on_non_finite_payload(self):
        valid_envelope = {
            "source_reality": "provider_daily_statistical_aggregate",
            "provider_product_id": "MODIS_DAILY_001",
            "content_hash": "a1b2c3d4e5f60718",
            "usable": True,
            "quality_class": "good",
            "production_usable": True,
            "diagnostic_only": False,
            "quality_admitted": True,
            "geometry_hash": "geom_hash_123",
            "valid_pixel_count": 100,
        }

        # Inf and NaN must fail admission despite complete surrounding envelope
        inf_record = {**valid_envelope, "ndvi": float("inf")}
        self.assertFalse(is_admitted_temporal_record(inf_record))

        nan_record = {**valid_envelope, "ndvi": float("nan")}
        self.assertFalse(is_admitted_temporal_record(nan_record))

        bool_record = {**valid_envelope, "ndvi": True}
        self.assertFalse(is_admitted_temporal_record(bool_record))

        # Legitimate finite zero or positive scalar must be admitted
        zero_record = {**valid_envelope, "ndvi": 0.0}
        self.assertTrue(is_admitted_temporal_record(zero_record))

        finite_record = {**valid_envelope, "ndvi": 0.52}
        self.assertTrue(is_admitted_temporal_record(finite_record))

    def test_build_temporal_admission_ledger_rejection_accounting(self):
        records = [
            {
                "source_reality": "provider_daily_statistical_aggregate",
                "provider_product_id": "P1",
                "content_hash": "hash1",
                "usable": True,
                "quality_class": "good",
                "production_usable": True,
                "diagnostic_only": False,
                "quality_admitted": True,
                "geometry_hash": "g1",
                "valid_pixel_count": 50,
                "ndvi": 0.42,
            },
            {
                "source_reality": "provider_daily_statistical_aggregate",
                "provider_product_id": "P2",
                "content_hash": "hash2",
                "usable": True,
                "quality_class": "good",
                "production_usable": True,
                "diagnostic_only": False,
                "quality_admitted": True,
                "geometry_hash": "g2",
                "valid_pixel_count": 50,
                "ndvi": float("nan"),
            },
        ]
        ledger = build_temporal_admission_ledger(records, value_keys=("ndvi",))
        self.assertEqual(ledger["input_count"], 2)
        self.assertEqual(ledger["quality_admitted_count"], 1)
        self.assertEqual(ledger["rejected_count"], 1)
        self.assertEqual(len(ledger["admitted_records"]), 1)


class TestF01WrapperAndProvenanceQualification(unittest.TestCase):
    """AB-DAT-005 / AB-DAT-006: Provenance qualification and explicit zero preservation."""

    def test_reading_reliability_zero_preserved_without_fallback_to_one(self):
        payload = {
            "packet_type": "WEATHER_OBSERVATION",
            "reading_reliability": 0.0,
            "timestamp": "2026-10-20T12:00:00Z",
            "temperature_2m": 24.5,
        }
        packet = ensure_observation_packet(
            payload,
            source=ObservationSource.WEATHER_STATION,
            plot_id="plot-1",
            geometry_hash="geom_hash_1",
            geometry_version=1,
        )
        self.assertEqual(packet.qa.scene_score, 0.0)
        self.assertEqual(packet.reliability_weight, 0.0)
        self.assertEqual(packet.effective_weight(), 0.0)

    def test_infer_data_status_from_explicit_roles(self):
        # Simulated / synthetic roles
        self.assertEqual(
            _infer_data_status({"role": "SIMULATED"}, ObservationSource.SENSOR_IOT),
            DataStatus.SIMULATED,
        )
        self.assertEqual(
            _infer_data_status({"source_role": "SYNTHETIC"}, ObservationSource.SENSOR_IOT),
            DataStatus.SIMULATED,
        )
        self.assertEqual(
            _infer_data_status({"data_role": "SCENARIO"}, ObservationSource.SENSOR_IOT),
            DataStatus.SIMULATED,
        )

        # Estimated / forecast / prior roles
        self.assertEqual(
            _infer_data_status({"role": "FORECAST"}, ObservationSource.WEATHER_STATION),
            DataStatus.ESTIMATED,
        )
        self.assertEqual(
            _infer_data_status({"role": "PRIOR"}, ObservationSource.WEATHER_STATION),
            DataStatus.ESTIMATED,
        )
        self.assertEqual(
            _infer_data_status({"role": "MODELLED"}, ObservationSource.WEATHER_STATION),
            DataStatus.ESTIMATED,
        )

        # Fallback / proxy roles
        self.assertEqual(
            _infer_data_status({"role": "FALLBACK"}, ObservationSource.WEATHER_STATION),
            DataStatus.FALLBACK,
        )
        self.assertEqual(
            _infer_data_status({"role": "PROXY"}, ObservationSource.WEATHER_STATION),
            DataStatus.FALLBACK,
        )

        # Unavailable / rejected / excluded roles
        self.assertEqual(
            _infer_data_status({"role": "UNAVAILABLE"}, ObservationSource.WEATHER_STATION),
            DataStatus.UNAVAILABLE,
        )
        self.assertEqual(
            _infer_data_status({"role": "REJECTED"}, ObservationSource.WEATHER_STATION),
            DataStatus.UNAVAILABLE,
        )
        self.assertEqual(
            _infer_data_status({"role": "EXCLUDED"}, ObservationSource.WEATHER_STATION),
            DataStatus.UNAVAILABLE,
        )

    def test_uncertainty_model_qualification(self):
        # Strictly positive finite uncertainty is admitted
        payload_valid = {"uncertainty": 0.05, "reading_reliability": 0.8}
        pkt_valid = ensure_observation_packet(
            payload_valid,
            ObservationSource.SENSOR_IOT,
            plot_id="plot-1",
            geometry_hash="geom_hash_1",
            geometry_version=1,
        )
        self.assertEqual(pkt_valid.uncertainty.get_sigma("observation"), 0.05)

        # Zero or negative uncertainty falls back to default empty model
        payload_zero = {"uncertainty": 0.0}
        pkt_zero = ensure_observation_packet(
            payload_zero,
            ObservationSource.SENSOR_IOT,
            plot_id="plot-1",
            geometry_hash="geom_hash_1",
            geometry_version=1,
        )
        self.assertNotIn("observation", pkt_zero.uncertainty.sigmas)

        payload_inf = {"uncertainty": float("inf")}
        pkt_inf = ensure_observation_packet(
            payload_inf,
            ObservationSource.SENSOR_IOT,
            plot_id="plot-1",
            geometry_hash="geom_hash_1",
            geometry_version=1,
        )
        self.assertNotIn("observation", pkt_inf.uncertainty.sigmas)


class TestF01WaterAssimilationProvenanceAndAuthority(unittest.TestCase):
    """AB-ARC-005 / AB-ARC-006: Provenance qualification in Layer 3 assimilation & authority."""

    def setUp(self):
        self.prior = WaterStateFactory.create_soil_water_state(
            [10.0, 30.0],
            [0.2, 0.2],
            [0.3, 0.3],
            [0.1, 0.1],
            [0.45, 0.45],
            [0.04, 0.04],
        )
        self.weather = {
            "t_max_c": 25.0,
            "t_min_c": 15.0,
            "precipitation_mm": 0.0,
            "wind_speed_2m_m_s": 2.0,
            "rh_min_pct": 30.0,
            "rh_max_pct": 60.0,
            "net_radiation_mj_m2": 10.0,
        }

    def test_simulated_probe_cannot_confer_observed_authority(self):
        """A probe tagged as SIMULATED in provenance must not upgrade authority to OBSERVED."""
        obs = SoilObservationVector(
            timestamp=CUTOFF,
            soil_probe_moisture_profile=[0.25],
            provenance_sources=["SIMULATED_TDR_PROBE"],
        )
        post, diag = WaterStateAssimilator.assimilate_observations(self.prior, obs)
        self.assertEqual(diag.observations_assimilated_count, 1)
        self.assertIn("SIMULATED_TDR_PROBE", diag.assimilated_sensor_sources)

        state, _ = WaterIntelligenceEngine.execute_pipeline(
            plot_id="plot-1",
            timestamp=CUTOFF,
            weather_observations=self.weather,
            soil_observations=obs,
        )
        # Authority must be ASSIMILATED, never OBSERVED
        self.assertEqual(state.physics_authority, WaterPhysicsAuthority.ASSIMILATED)

    def test_observed_real_probe_confers_observed_authority(self):
        """A clean real in-situ probe confers OBSERVED authority."""
        obs = SoilObservationVector(
            timestamp=CUTOFF,
            soil_probe_moisture_profile=[0.25],
            provenance_sources=["IN_SITU_PROBE_TDR"],
        )
        state, _ = WaterIntelligenceEngine.execute_pipeline(
            plot_id="plot-1",
            timestamp=CUTOFF,
            weather_observations=self.weather,
            soil_observations=obs,
        )
        self.assertEqual(state.physics_authority, WaterPhysicsAuthority.OBSERVED)

    def test_excluded_role_is_explicitly_rejected_in_diagnostic(self):
        """A probe with EXCLUDED provenance tag is rejected before assimilation."""
        obs = SoilObservationVector(
            timestamp=CUTOFF,
            soil_probe_moisture_profile=[0.25],
            provenance_sources=["EXCLUDED_PROBE_SENSOR"],
        )
        post, diag = WaterStateAssimilator.assimilate_observations(self.prior, obs)
        self.assertEqual(diag.observations_assimilated_count, 0)
        self.assertEqual(len(diag.rejected_observations), 1)
        self.assertEqual(diag.rejected_observations[0]["reason"], "explicitly_excluded_role")
        self.assertEqual(diag.rejected_observations[0]["role"], "EXCLUDED")

    def test_asmae_observation_payload_validation(self):
        """ASMAEObservationPayload enforces finite numeric and positive variance."""
        valid_payload = ASMAEObservationPayload(
            observation_id="obs_001",
            target_state_variable="root_zone_water",
            microzone_id="mz_1",
            depth_stratum="ROOT_ZONE_5_30CM",
            observation_value=0.28,
            observation_units="volumetric fraction [0,1]",
            observation_variance=0.0004,
            forward_operator_id="identity_fwd",
            calibration_certificate_id="cert_2026",
            truth_class="MEASURED_NATIVE",
            knowledge_cutoff=CUTOFF,
        )
        self.assertEqual(valid_payload.observation_value, 0.28)
        self.assertEqual(valid_payload.observation_variance, 0.0004)

        # Non-finite value must raise ValueError
        with self.assertRaises(ValueError):
            ASMAEObservationPayload(
                observation_id="obs_bad_val",
                target_state_variable="root_zone_water",
                microzone_id="mz_1",
                depth_stratum="ROOT_ZONE_5_30CM",
                observation_value=float("inf"),
                observation_units="volumetric fraction [0,1]",
                observation_variance=0.0004,
                forward_operator_id="identity_fwd",
                calibration_certificate_id="cert_2026",
                truth_class="MEASURED_NATIVE",
                knowledge_cutoff=CUTOFF,
            )

        # Zero or negative variance must raise ValueError
        with self.assertRaises(ValueError):
            ASMAEObservationPayload(
                observation_id="obs_bad_var",
                target_state_variable="root_zone_water",
                microzone_id="mz_1",
                depth_stratum="ROOT_ZONE_5_30CM",
                observation_value=0.28,
                observation_units="volumetric fraction [0,1]",
                observation_variance=0.0,
                forward_operator_id="identity_fwd",
                calibration_certificate_id="cert_2026",
                truth_class="MEASURED_NATIVE",
                knowledge_cutoff=CUTOFF,
            )


if __name__ == "__main__":
    unittest.main()
