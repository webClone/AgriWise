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


from services.agribrain.layer1_fusion.schemas import EvidenceItem, Layer1InputBundle
from services.agribrain.layer1_fusion.evidence_validation import validate_evidence
from services.agribrain.layer1_fusion.adapters.observation_packet import observation_packet_to_evidence
from services.agribrain.layer1_fusion.truth_bridge import truth_for_observation_packet
from services.agribrain.layer2_veg_int.crop_observations import (
    _gdd_coordinates_until,
    build_sentinel2_crop_observation,
)
from services.agribrain.layer3_decision.runner import (
    _serialize_soil_observation,
    _deserialize_soil_observation,
)
from services.agribrain.layer05_asmae.training.exporter import export_weak_labels
from services.agribrain.layer1_fusion.adapters.asmae_adapter import ASMAEAdapter
from services.agribrain.asmae_learn.schemas import ValidationEvent
from services.agribrain.asmae_learn.dataset_builder import build_validated_training_view
from services.agribrain.mesia.contracts.observation import RadioObservationPacket
from services.agribrain.mesia.behaviour.feature_extraction import NativeFeatureExtractor
from services.agribrain.mesia.assimilation.asmae_operator import ASMAEInnovationProposal
from services.agribrain.mesia.assimilation.layer0_spine import (
    EvidenceAdmissionStatus,
    Layer0EvidenceSpine,
)
from services.agribrain.mesia.integration import MesiaAgriBrainBridge
from services.agribrain.mesia.ontology.evidence_roles import EvidenceRole
import numpy as np


class TestF01B01QuantitativeComponentQualification(unittest.TestCase):
    """F01-B01: Boolean/malformed quantitative components pass some Layer1 and crop consumers."""

    def test_layer1_validator_rejects_boolean_and_malformed_ndvi(self):
        # Boolean NDVI must be rejected with explicit violation
        item_bool = EvidenceItem(
            evidence_id="ev_bool",
            plot_id="plot_1",
            variable="ndvi",
            value=True,
            unit="index",
            data_status="observed",
            production_usable=True,
            state_update_allowed=True,
            source_family="sentinel2",
            source_id="pkt_1",
            observation_type="measurement",
            spatial_scope="plot",
            observed_at=CUTOFF,
            confidence=1.0,
            sigma=0.05,
            reliability=1.0,
            provenance_ref="ref_1",
        )
        violations_bool = validate_evidence(item_bool)
        self.assertTrue(any("BOOLEAN_VALUE_DISALLOWED" in v for v in violations_bool))

        # Malformed string NDVI must be rejected with explicit violation
        item_malformed = EvidenceItem(
            evidence_id="ev_str",
            plot_id="plot_1",
            variable="ndvi",
            value="not-a-number",
            unit="index",
            data_status="observed",
            production_usable=True,
            state_update_allowed=True,
            source_family="sentinel2",
            source_id="pkt_1",
            observation_type="measurement",
            spatial_scope="plot",
            observed_at=CUTOFF,
            confidence=1.0,
            sigma=0.05,
            reliability=1.0,
            provenance_ref="ref_1",
        )
        violations_str = validate_evidence(item_malformed)
        self.assertTrue(any("NON_FINITE_OR_MALFORMED_VALUE" in v for v in violations_str))

        # Valid zero sibling must have NO bounds/numeric violations
        item_zero = EvidenceItem(
            evidence_id="ev_zero",
            plot_id="plot_1",
            variable="evi",
            value=0.0,
            unit="index",
            data_status="observed",
            production_usable=True,
            state_update_allowed=True,
            source_family="sentinel2",
            source_id="pkt_1",
            observation_type="measurement",
            spatial_scope="plot",
            observed_at=CUTOFF,
            confidence=1.0,
            sigma=0.05,
            reliability=1.0,
            provenance_ref="ref_1",
        )
        violations_zero = validate_evidence(item_zero)
        self.assertEqual(violations_zero, [])

    def test_crop_observation_rejects_boolean_reflectance_arrays(self):
        shape = (3, 3)
        package = {
            "source_reality": "real_raster",
            "production_usable": True,
            "real_provider_product": True,
            "diagnostic_only": False,
            "tenant_id": "tenant-a",
            "farm_id": "farm-a",
            "plot_id": "plot_1",
            "band_arrays": {
                "B04": np.array([[True, True, True], [True, True, True], [True, True, True]], dtype=bool),
                "B08": np.full(shape, 0.20, dtype=float),
                "SCL": np.full(shape, 4, dtype=np.uint8),
            },
            "shape": [3, 3],
            "band_units": {"B04": "reflectance", "B08": "reflectance", "SCL": "classification"},
            "plot_geometry": {
                "type": "Polygon",
                "coordinates": [[[0.0, 0.0], [3.0, 0.0], [3.0, 3.0], [0.0, 3.0], [0.0, 0.0]]],
            },
            "transform": (0.0, 1.0, 0.0, 3.0, 0.0, -1.0),
            "crs": "EPSG:4326",
            "acquisition_datetime": "2026-10-20T10:00:00+00:00",
            "product_id": "S2A_MSIL2A_20261020T100000_N0500_R001_T31UDS_20261020T100000",
            "provider_product_id": "S2A_MSIL2A_20261020T100000_N0500_R001_T31UDS_20261020T100000",
        }
        obs = build_sentinel2_crop_observation(package, geometry_hash="geom-a")
        self.assertIsNotNone(obs)
        self.assertFalse(obs["quality_admitted"])
        self.assertTrue(any("malformed_reflectance_dtype:B04" in r for r in obs["quality_rejection_reasons"]))
        self.assertFalse(obs["state_update_allowed"])
        self.assertFalse(obs["direct_observation"])

    def test_thermal_coordinates_rejects_boolean_temperature(self):
        records = [
            {"date": "2026-10-15", "temp_mean": True},
            {"date": "2026-10-16", "temp_mean": 20.0},
        ]
        coords, primary = _gdd_coordinates_until(
            acquisition_day=datetime(2026, 10, 20).date(),
            weather_records=records,
            season_start=datetime(2026, 10, 1).date(),
        )
        # GDD0 should only accumulate the 20.0 C day (20.0), NOT the True day (which was 1.0)
        self.assertEqual(coords.get("GDD0"), 20.0)


class TestF01B02RestrictiveRoleMonotonePromotion(unittest.TestCase):
    """F01-B02: Adapter and truth paths promote restricted roles into observed evidence."""

    def test_conflicting_aliases_demote_monotonically(self):
        # role=OBSERVED but source_role=SIMULATED -> must demote to SIMULATED
        payload_sim = {
            "role": "OBSERVED",
            "source_role": "SIMULATED",
            "value": 0.45,
            "reading_reliability": 1.0,
        }
        status_sim = _infer_data_status(payload_sim, ObservationSource.WEATHER_STATION)
        self.assertEqual(status_sim, DataStatus.SIMULATED)

        # role=OBSERVED but data_role=UNAVAILABLE -> must demote to UNAVAILABLE
        payload_unavail = {
            "role": "OBSERVED",
            "data_role": "UNAVAILABLE",
            "value": 0.45,
            "reading_reliability": 1.0,
        }
        status_unavail = _infer_data_status(payload_unavail, ObservationSource.WEATHER_STATION)
        self.assertEqual(status_unavail, DataStatus.UNAVAILABLE)

    def test_truth_bridge_preserves_restrictive_packet_roles(self):
        # Daily plot statistic fast path must not promote SIMULATED packet to observed
        sim_pkt = ObservationPacket(
            plot_id="plot_1",
            timestamp=CUTOFF,
            source=ObservationSource.WEATHER_STATION,
            obs_type=ObservationType.POINT_TIMESERIES,
            data_status=DataStatus.SIMULATED,
            payload={
                "source_reality": "provider_daily_statistical_aggregate",
                "temporal_basis": "daily_plot_statistic",
                "ndvi": 0.45,
                "role": "SIMULATED",
            },
        )
        truth_sim = truth_for_observation_packet(sim_pkt)
        self.assertEqual(truth_sim.data_status, "simulated")
        self.assertTrue(truth_sim.diagnostic_only)
        self.assertFalse(truth_sim.state_update_allowed)

        # Adapter must also restrict state_update_allowed to False
        bundle = Layer1InputBundle(
            plot_id="plot_1",
            run_id="run_1",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
        )
        items = observation_packet_to_evidence(sim_pkt, bundle)
        self.assertTrue(len(items) > 0)
        for it in items:
            self.assertEqual(it.data_status, "simulated")
            self.assertTrue(it.diagnostic_only)
            self.assertFalse(it.state_update_allowed)


class TestF01B03InvalidExplicitReliability(unittest.TestCase):
    """F01-B03: Invalid explicit reliability can default to full reliability."""

    def test_nan_inf_bool_string_reliability_yields_zero_and_low_confidence(self):
        base_dict = {
            "plot_id": "plot_1",
            "timestamp": CUTOFF,
            "source": "sensor_soil",
            "type": "moisture",
            "value": 0.25,
        }

        # NaN reliability
        pkt_nan = ensure_observation_packet({**base_dict, "reading_reliability": float("nan")}, ObservationSource.SENSOR_IOT, "plot_1", "hash_1", 1)
        self.assertEqual(pkt_nan.reliability_weight, 0.0)
        self.assertIn(QAFlag.LOW_CONFIDENCE, pkt_nan.qa.flags)

        # Inf reliability
        pkt_inf = ensure_observation_packet({**base_dict, "reading_reliability": float("inf")}, ObservationSource.SENSOR_IOT, "plot_1", "hash_1", 1)
        self.assertEqual(pkt_inf.reliability_weight, 0.0)
        self.assertIn(QAFlag.LOW_CONFIDENCE, pkt_inf.qa.flags)

        # Boolean True reliability (not a finite real scalar in [0,1])
        pkt_bool = ensure_observation_packet({**base_dict, "reading_reliability": True}, ObservationSource.SENSOR_IOT, "plot_1", "hash_1", 1)
        self.assertEqual(pkt_bool.reliability_weight, 0.0)
        self.assertIn(QAFlag.LOW_CONFIDENCE, pkt_bool.qa.flags)

        # Malformed string reliability
        pkt_str = ensure_observation_packet({**base_dict, "reading_reliability": "bad"}, ObservationSource.SENSOR_IOT, "plot_1", "hash_1", 1)
        self.assertEqual(pkt_str.reliability_weight, 0.0)
        self.assertIn(QAFlag.LOW_CONFIDENCE, pkt_str.qa.flags)

        # Legitimate 0.0 reliability preserved without replacing by 1.0
        pkt_zero = ensure_observation_packet({**base_dict, "reading_reliability": 0.0}, ObservationSource.SENSOR_IOT, "plot_1", "hash_1", 1)
        self.assertEqual(pkt_zero.reliability_weight, 0.0)

        # Absent reliability defaults to 1.0
        pkt_absent = ensure_observation_packet(base_dict, ObservationSource.SENSOR_IOT, "plot_1", "hash_1", 1)
        self.assertEqual(pkt_absent.reliability_weight, 1.0)


class TestF01B04WaterProvenanceAndHistoryQualification(unittest.TestCase):
    """F01-B04: Water provenance/history loses restrictions."""

    def setUp(self):
        self.prior = WaterStateFactory.create_soil_water_state(
            [10.0, 20.0, 30.0],
            [0.20, 0.20, 0.20],
            [0.30, 0.30, 0.30],
            [0.15, 0.15, 0.15],
            [0.45, 0.45, 0.45],
            [0.04, 0.04, 0.04],
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

    def test_forecast_probe_cannot_confer_observed_authority(self):
        obs = SoilObservationVector(
            timestamp=CUTOFF,
            soil_probe_moisture_profile=[0.35, 0.35, 0.35],
            provenance_sources=["IN_SITU_PROBE_TDR", "FORECAST"],
        )
        state, _ = WaterIntelligenceEngine.execute_pipeline(
            plot_id="plot_1",
            timestamp=CUTOFF,
            weather_observations=self.weather,
            soil_observations=obs,
        )
        self.assertNotEqual(state.physics_authority, WaterPhysicsAuthority.OBSERVED)
        self.assertEqual(state.physics_authority, WaterPhysicsAuthority.ASSIMILATED)

    def test_excluded_satellite_input_rejected_without_state_increment(self):
        obs = SoilObservationVector(
            timestamp=CUTOFF,
            satellite_surface_moisture_m3_m3=0.35,
            observation_uncertainties={"satellite_smap": 0.04},
            provenance_sources=["EXCLUDED_SATELLITE_SMAP_SENTINEL1"],
        )
        post, diag = WaterStateAssimilator.assimilate_observations(self.prior, obs)
        self.assertEqual(diag.observations_assimilated_count, 0)
        self.assertEqual(len(diag.rejected_observations), 1)
        self.assertEqual(diag.rejected_observations[0]["reason"], "explicitly_excluded_role")

        # Full water engine must not update state from excluded satellite
        state, _ = WaterIntelligenceEngine.execute_pipeline(
            plot_id="plot_1",
            timestamp=CUTOFF,
            weather_observations=self.weather,
            soil_observations=obs,
        )
        self.assertEqual(state.physics_authority, WaterPhysicsAuthority.MODELLED)

    def test_history_serialization_preserves_role_and_zero_reliability(self):
        hist_dict = {
            "timestamp": CUTOFF.isoformat(),
            "soil_probe_moisture_profile": [0.35, 0.35, 0.35],
            "role": "SIMULATED",
            "reading_reliability": 0.0,
            "reliability_weight": 0.0,
            "source": "IN_SITU_PROBE_TDR",
        }
        so_deser = _deserialize_soil_observation(hist_dict)
        self.assertIsNotNone(so_deser)
        self.assertEqual(so_deser.role, "SIMULATED")
        self.assertEqual(so_deser.reading_reliability, 0.0)
        self.assertEqual(so_deser.reliability_weight, 0.0)

        # Zero reliability rejects observation components
        post, diag = WaterStateAssimilator.assimilate_observations(self.prior, so_deser)
        self.assertEqual(diag.observations_assimilated_count, 0)
        self.assertTrue(all(r["reason"] == "zero_reliability" for r in diag.rejected_observations))


class TestF01B05WeakLabelExportMalformedTargets(unittest.TestCase):
    """F01-B05: NaN/Inf/boolean weak-label targets receive positive training weight."""

    def _call_export(self, val):
        return export_weak_labels(
            state_result={"raster_maps": {"mz_1": [val]}, "uncertainty_maps": {"mz_1": [0.1]}},
            retro_result={"aggregate": {"retro_score": 0.9}, "status": "success_with_holdouts"},
            bma_result={"per_microzone_disagreement": {"mz_1": 0.01}, "status": "success"},
            consistency_result={"overall_pass": True},
            scene_stack_mode="real_raster",
            resolution_m=10,
            plot_id="plot_1",
            run_id="run_1",
            production_usable=True,
            n_scenes_processed=3,
            certification_level="certified",
            mode="training_export",
        )

    def test_exporter_assigns_zero_weight_to_nan_inf_bool(self):
        # NaN estimate
        labels_nan = self._call_export(float("nan"))
        self.assertEqual(len(labels_nan), 1)
        self.assertEqual(labels_nan[0]["training_weight"], 0.0)
        self.assertTrue(any("invalid_state_estimate" in r for r in labels_nan[0]["zero_weight_reasons"]))

        # Boolean True estimate
        labels_bool = self._call_export(True)
        self.assertEqual(len(labels_bool), 1)
        self.assertEqual(labels_bool[0]["training_weight"], 0.0)
        self.assertTrue(any("invalid_state_estimate" in r for r in labels_bool[0]["zero_weight_reasons"]))

        # Valid finite estimate (0.50) receives positive training weight
        labels_valid = self._call_export(0.50)
        self.assertEqual(len(labels_valid), 1)
        self.assertGreater(labels_valid[0]["training_weight"], 0.0)
        self.assertEqual(labels_valid[0]["zero_weight_reasons"], [])

class TestF01B06ValidatedSupervisedTrainingViews(unittest.TestCase):
    """F01-B06: The actual validation pipeline approves malformed continuous targets for training views."""

    def test_validation_event_rejects_bool_and_nonfinite_confidence(self):
        with self.assertRaises(ValueError):
            ValidationEvent(
                event_id="ev_1",
                plot_id="plot_1",
                geometry_hash="g_123",
                event_time="2026-10-20T10:00:00Z",
                source_type="soil_lab",
                target_variable="vigor",
                observed_value=0.5,
                spatial_scope="plot",
                temporal_scope="daily",
                confidence=True, # Boolean confidence disallowed
                validator_role="lab",
                evidence_hash="ev_hash",
            )

        with self.assertRaises(ValueError):
            ValidationEvent(
                event_id="ev_2",
                plot_id="plot_1",
                geometry_hash="g_123",
                event_time="2026-10-20T10:00:00Z",
                source_type="soil_lab",
                target_variable="vigor",
                observed_value=0.5,
                spatial_scope="plot",
                temporal_scope="daily",
                confidence=float("nan"), # NaN confidence disallowed
                validator_role="lab",
                evidence_hash="ev_hash",
            )

    def test_validation_event_rejects_malformed_continuous_target(self):
        # NaN continuous target disallowed
        with self.assertRaises(ValueError):
            ValidationEvent(
                event_id="ev_3",
                plot_id="plot_1",
                geometry_hash="g_123",
                event_time="2026-10-20T10:00:00Z",
                source_type="soil_lab",
                target_variable="vigor",
                observed_value=float("nan"),
                spatial_scope="plot",
                temporal_scope="daily",
                confidence=1.0,
                validator_role="lab",
                evidence_hash="ev_hash",
            )

        # Boolean continuous target disallowed
        with self.assertRaises(ValueError):
            ValidationEvent(
                event_id="ev_4",
                plot_id="plot_1",
                geometry_hash="g_123",
                event_time="2026-10-20T10:00:00Z",
                source_type="soil_lab",
                target_variable="vigor",
                observed_value=True,
                spatial_scope="plot",
                temporal_scope="daily",
                confidence=1.0,
                validator_role="lab",
                evidence_hash="ev_hash",
            )

        # Malformed string continuous target disallowed
        with self.assertRaises(ValueError):
            ValidationEvent(
                event_id="ev_5",
                plot_id="plot_1",
                geometry_hash="g_123",
                event_time="2026-10-20T10:00:00Z",
                source_type="soil_lab",
                target_variable="vigor",
                observed_value="not-a-number",
                spatial_scope="plot",
                temporal_scope="daily",
                confidence=1.0,
                validator_role="lab",
                evidence_hash="ev_hash",
            )

        # Valid finite continuous target (0.0 or 0.65) allowed
        ev_valid = ValidationEvent(
            event_id="ev_6",
            plot_id="plot_1",
            geometry_hash="g_123",
            event_time="2026-10-20T10:00:00Z",
            source_type="soil_lab",
            target_variable="vigor",
            observed_value=0.0,
            spatial_scope="plot",
            temporal_scope="daily",
            confidence=1.0,
            validator_role="lab",
            evidence_hash="ev_hash",
        )
        self.assertEqual(ev_valid.observed_value, 0.0)


class TestF01B07RFInternalAdmission(unittest.TestCase):
    """F01-B07: Internal RF admission lacks complete scalar/role qualification."""

    def test_feature_extractor_rejects_bool_and_nonfinite_snr(self):
        pkt_nan = RadioObservationPacket(
            packet_id="pkt_nan",
            receiver_id="dev_1",
            utc_time=CUTOFF,
            source_profile="WIFI_CSI/802.11ac",
            snr_db=float("nan"),
            calibration_state_id="cal_1",
        )
        feat_nan = NativeFeatureExtractor.extract_features(pkt_nan)
        self.assertIsNone(feat_nan.features["snr_db"])

        pkt_bool = RadioObservationPacket(
            packet_id="pkt_bool",
            receiver_id="dev_1",
            utc_time=CUTOFF,
            source_profile="WIFI_CSI/802.11ac",
            snr_db=True,
            calibration_state_id="cal_1",
        )
        feat_bool = NativeFeatureExtractor.extract_features(pkt_bool)
        self.assertIsNone(feat_bool.features["snr_db"])

    def test_layer0_spine_rejects_nan_support_or_variance(self):
        prop_nan_cov = ASMAEInnovationProposal(
            proposal_id="p_nan_cov",
            target_state_variable="soil_moisture",
            microzone_id="mz_1",
            depth_stratum="ROOT_ZONE_5_30CM",
            innovation_value=1.5,
            observation_variance=float("nan"),
            confidence_support=1.0,
            authority_scope="evidence_proposal",
            native_lineage_hash="hash_1",
            likelihood_ref="lik_1",
            created_at=CUTOFF,
        )
        rec = Layer0EvidenceSpine.evaluate_admission(prop_nan_cov, is_calibration_valid=True, is_epoch_active=True)
        self.assertEqual(rec.status, EvidenceAdmissionStatus.ABSENT)
        self.assertFalse(rec.is_usable_for_assimilation)

    def test_non_sensing_roles_cannot_gain_state_update_authority(self):
        bridge = MesiaAgriBrainBridge("plot_1")
        pkt_context = RadioObservationPacket(
            packet_id="pkt_ctx",
            receiver_id="dev_1",
            utc_time=CUTOFF,
            source_profile="BLE_BEACON/mesh",
            snr_db=15.0,
            calibration_state_id="cal_1",
            native_data_uri="memory://capture_1",
            native_data_hash="a" * 64,
            evidence_role=EvidenceRole.CONTEXT.value,
        )
        rec, asmae_ev = bridge.process_and_admit_observation(
            pkt_context,
            is_calibration_valid=True,
            is_epoch_active=True,
        )
        # CONTEXT role must not be usable for state assimilation
        self.assertFalse(rec.is_usable_for_assimilation)
        self.assertIsNone(asmae_ev)


class TestR415ConsolidatedResiduals(unittest.TestCase):
    """Explicit verification for R415-01 through R415-07 residual findings."""

    def test_r415_01_asmae_adapter_weak_label_finite_real(self):
        """R415-01: finite_real import prevents NameError on weak-label processing with valid scalars and zeros."""
        from services.agribrain.layer1_fusion.adapters.asmae_adapter import ASMAEAdapter
        from services.agribrain.layer1_fusion.schemas import Layer1InputBundle

        bundle = Layer1InputBundle(
            plot_id="plot_415",
            run_id="run_weak_001",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
        )
        package = {
            "run_id": "run_weak_001",
            "plot_id": "plot_415",
            "generated_at": CUTOFF.isoformat(),
            "status": "success",
            "production_usable": True,
            "weak_label_export_allowed": True,
            "provenance": {"mode": "training_export"},
            "diagnostics": {"mode": "training_export"},
            "weak_labels": [
                {"estimate": 0.0, "training_weight": 0.85, "zero_weight_reasons": []},
                {"estimate": 0.42, "training_weight": 0.90, "zero_weight_reasons": []},
            ],
        }
        items = ASMAEAdapter().extract_evidence(package, bundle)
        w_item = next((item for item in items if item.variable == "ASMAE_TRAINING_WEIGHT"), None)
        self.assertIsNotNone(w_item)
        self.assertAlmostEqual(w_item.value, 0.875)

    def test_r415_02_reconstruction_role_and_monotonic_weather_exclusion(self):
        """R415-02: Later normalization restores restricted roles; unavailable weather re-enters crop features."""
        from services.agribrain.layer0.observation_packet import DataStatus
        from services.agribrain.layer0.wrappers import _canonical_weather_records
        from services.agribrain.layer2_veg_int.crop_observations import _gdd_coordinates_until
        from services.agribrain.layer1_fusion.truth_bridge import normalize_evidence_truth
        from services.agribrain.layer1_fusion.schemas import EvidenceItem, DATA_STATUSES, DATA_STATUS_CEILING

        # 1. DataStatus has RECONSTRUCTION
        self.assertIn("reconstruction", [s.value for s in DataStatus])
        self.assertIn("reconstruction", DATA_STATUSES)
        self.assertEqual(DATA_STATUS_CEILING["reconstruction"], 0.50)

        # 2. _canonical_weather_records checks data_status and declared roles monotonically
        records = [
            {"date": "2026-10-15", "temp_mean_c": 20.0, "data_status": "reconstruction"},
            {"date": "2026-10-16", "temp_mean_c": 21.0, "role": "fallback"},
            {"date": "2026-10-17", "temp_mean_c": 22.0, "source_role": "simulated"},
            {"date": "2026-10-18", "temp_mean_c": 23.0, "data_role": "unavailable"},
            {"date": "2026-10-19", "temp_mean_c": 24.0, "status_role": "estimated"},
            {"date": "2026-10-20", "temp_mean_c": 25.0, "data_status": "observed", "role": "observed"},
        ]
        env_package = {"weather_consensus": records}
        canonical = _canonical_weather_records(env_package, [])
        self.assertEqual(len(canonical), 6)
        self.assertEqual(canonical[0]["data_status"], "estimated")
        self.assertEqual(canonical[1]["data_status"], "fallback")
        self.assertEqual(canonical[2]["data_status"], "simulated")
        self.assertEqual(canonical[3]["data_status"], "unavailable")
        self.assertEqual(canonical[4]["data_status"], "estimated")
        self.assertEqual(canonical[5]["data_status"], "observed")

        # 3. _gdd_coordinates_until excludes restricted weather records
        crop_records = [
            {"date": "2026-10-18", "temp_mean": 23.0, "data_role": "unavailable"},
            {"date": "2026-10-19", "temp_mean": 24.0, "status_role": "excluded"},
            {"date": "2026-10-20", "temp_mean": 25.0, "data_status": "observed", "role": "observed"},
        ]
        coords, primary = _gdd_coordinates_until(
            acquisition_day=datetime(2026, 10, 20).date(),
            weather_records=crop_records,
            season_start=datetime(2026, 10, 1).date(),
        )
        self.assertEqual(coords.get("GDD0"), 25.0)

        # 4. normalize_evidence_truth does not promote restricted status to observed
        item = EvidenceItem(
            evidence_id="ev_rec_1",
            plot_id="plot_1",
            variable="DRONE_NDVI",
            value=0.55,
            unit="unitless",
            source_family="drone",
            source_id="d_1",
            observation_type="direct",
            spatial_scope="plot",
            observed_at=CUTOFF,
            confidence=0.9,
            reliability=0.9,
            provenance_ref="drone_reconstructed",
            data_status="reconstruction",
            diagnostic_only=True,
            state_update_allowed=False,
        )
        norm = normalize_evidence_truth(item)
        self.assertEqual(norm.data_status, "reconstruction")
        self.assertTrue(norm.diagnostic_only)
        self.assertFalse(norm.state_update_allowed)
        self.assertLessEqual(norm.confidence, 0.50)

    def test_r415_03_water_component_roles_and_probe_reliability(self):
        """R415-03: Water component roles/quality govern influence and authority (+89.70 mm reproduction fails closed)."""
        # 1. Simulated probe vector does NOT confer OBSERVED authority
        comp_role = WaterStateAssimilator._resolve_role("OBSERVED", "SIMULATED")
        self.assertEqual(comp_role, "SIMULATED")

        # 2. Zero reliability reading (0.0) must not default to 1.0 or gain update authority
        prior_soil = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=[10.0, 20.0, 30.0],
            theta_profile=[0.20, 0.22, 0.24],
            field_capacity_profile=[0.30, 0.30, 0.30],
            wilting_point_profile=[0.12, 0.12, 0.12],
            saturation_profile=[0.45, 0.45, 0.45],
            residual_profile=[0.05, 0.05, 0.05],
        )
        vec_zero = SoilObservationVector(
            timestamp=CUTOFF,
            soil_probe_moisture_profile=[0.25, 0.27, 0.29],
            provenance_sources=["probe_tdr_hardware"],
            reading_reliability=0.0,
        )
        _, diag_zero = WaterStateAssimilator.assimilate_observations(prior_soil, vec_zero)
        self.assertTrue(any(r["reason"] == "zero_reliability" for r in diag_zero.rejected_observations))

        # 3. Non-finite or boolean reliability rejected
        vec_nan = SoilObservationVector(
            timestamp=CUTOFF,
            soil_probe_moisture_profile=[0.25, 0.27, 0.29],
            provenance_sources=["probe_tdr_hardware"],
            reading_reliability=float("nan"),
        )
        _, diag_nan = WaterStateAssimilator.assimilate_observations(prior_soil, vec_nan)
        self.assertTrue(any(r["reason"] == "invalid_observation_reliability" for r in diag_nan.rejected_observations))

        vec_bool = SoilObservationVector(
            timestamp=CUTOFF,
            soil_probe_moisture_profile=[0.25, 0.27, 0.29],
            provenance_sources=["probe_tdr_hardware"],
            reading_reliability=True,
        )
        _, diag_bool = WaterStateAssimilator.assimilate_observations(prior_soil, vec_bool)
        self.assertTrue(any(r["reason"] == "invalid_observation_reliability" for r in diag_bool.rejected_observations))

    def test_r415_04_producer_reliability_qualification(self):
        """R415-04: Supported typed producers qualify reliability without bumping zero to 0.05 or accepting boolean."""
        from services.agribrain.layer0.perception.common.packet_adapter import to_observation_packets
        from services.agribrain.layer0.perception.common.contracts import (
            PerceptionEngineOutput,
            PerceptionEngineFamily,
            PerceptionVariable,
        )
        from services.agribrain.layer1_fusion.adapters.sensors import SensorAdapter
        from services.agribrain.layer1_fusion.schemas import Layer1InputBundle

        # 1. Native perception adapter preserves 0.0 and rejects non-finite/bool
        out_zero = PerceptionEngineOutput(
            engine_family=PerceptionEngineFamily.SATELLITE_RGB,
            plot_id="plot_1",
            reliability_weight=0.0,
            variables=[PerceptionVariable(name="vegetation_fraction", value=0.45, sigma=0.05, confidence=0.0)],
        )
        pkts_zero = to_observation_packets(out_zero)
        self.assertEqual(len(pkts_zero), 1)
        self.assertEqual(pkts_zero[0].reliability_weight, 0.0)

        # Invalid reliability fails closed to 0.0
        out_nan = PerceptionEngineOutput(
            engine_family=PerceptionEngineFamily.SATELLITE_RGB,
            plot_id="plot_1",
            reliability_weight=float("nan"),
            variables=[PerceptionVariable(name="vegetation_fraction", value=0.45, sigma=0.05, confidence=1.0)],
        )
        pkts_nan = to_observation_packets(out_nan)
        self.assertEqual(len(pkts_nan), 1)
        self.assertEqual(pkts_nan[0].reliability_weight, 0.0)

        # 2. Sensor QA rejects boolean reliability
        bundle = Layer1InputBundle(
            plot_id="plot_1",
            run_id="run_1",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
        )

        class DummyQA:
            usable = True
            reading_reliability = True  # boolean!
            update_allowed = True

        class DummyReading:
            device_id = "sensor_01"
            variable = "soil_moisture"
            value = 0.22
            unit = "fraction"
            timestamp = CUTOFF

        class DummyPackage:
            plot_id = "plot_1"
            readings = [DummyReading()]
            qa_results = [DummyQA()]

        items = SensorAdapter().extract_evidence(DummyPackage(), bundle)
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0].state_update_allowed)
        self.assertTrue(items[0].diagnostic_only)
        self.assertEqual(items[0].reliability, 0.0)

    def test_r415_05_quantitative_soil_strings_rejected(self):
        """R415-05: Registered quantitative soil strings reach nondiagnostic fused features rejected as NON_FINITE_OR_MALFORMED_VALUE."""
        from services.agribrain.layer1_fusion.evidence_validation import validate_evidence
        from services.agribrain.layer1_fusion.schemas import EvidenceItem

        item_str = EvidenceItem(
            evidence_id="soil_str_1",
            plot_id="plot_1",
            variable="SOIL_CLAY_PCT",
            value="35.5",
            unit="percent",
            source_family="soil_survey",
            source_id="ss_1",
            observation_type="direct",
            spatial_scope="plot",
            observed_at=CUTOFF,
            confidence=0.8,
            reliability=0.8,
            provenance_ref="survey_lab_doc",
        )
        violations_str = validate_evidence(item_str)
        self.assertTrue(any(v.startswith("NON_FINITE_OR_MALFORMED_VALUE") for v in violations_str))

        # Legitimate numeric float is admitted
        item_float = EvidenceItem(
            evidence_id="soil_flt_1",
            plot_id="plot_1",
            variable="SOIL_CLAY_PCT",
            value=35.5,
            unit="percent",
            source_family="soil_survey",
            source_id="ss_1",
            observation_type="direct",
            spatial_scope="plot",
            observed_at=CUTOFF,
            confidence=0.8,
            reliability=0.8,
            provenance_ref="survey_lab_doc",
        )
        violations_flt = validate_evidence(item_float)
        self.assertFalse(any(v.startswith("NON_FINITE_OR_MALFORMED_VALUE") for v in violations_flt))

    def test_r415_06_asmae_learn_non_finite_diagnostics_and_nan_comparator(self):
        """R415-06: Invalid training diagnostics/comparators generate approved training-view samples."""
        from services.agribrain.asmae_learn.candidate_builder import build_learning_candidate
        from services.agribrain.asmae_learn.disagreement import check_disagreement
        from services.agribrain.asmae_learn.schemas import ValidationEvent

        # 1. Candidate builder rejects NaN uncertainty, retro_score, resolution
        ev_dict = {
            "event_id": "ev_01",
            "plot_id": "plot_1",
            "geometry_hash": "a" * 64,
            "event_time": CUTOFF.isoformat(),
            "source_type": "farmer_observation",
            "target_variable": "canopy_water",
            "observed_value": 0.45,
            "spatial_scope": "plot",
            "temporal_scope": "instant",
            "confidence": 0.8,
            "validator_role": "farmer",
            "trust_weight": 0.8,
            "evidence_hash": "e" * 64,
        }
        run_record_base = {
            "plot_id": "plot_1",
            "run_id": "run_test_01",
            "geometry_hash": "a" * 64,
            "layer0_output_hash": "b" * 64,
            "asmae_content_hash": "c" * 64,
            "asmae_artifact_instance_hash": "d" * 64,
            "target_variable": "canopy_water",
            "validation_events": [ev_dict],
            "diagnostics": {
                "bma_status": "success",
                "retro_status": "success_with_holdouts",
                "uncertainty": float("nan"),
                "retro_mean_score": 0.85,
                "resolution_selected_m": 10.0,
            },
        }
        cand = build_learning_candidate(run_record_base)
        self.assertFalse(cand["eligible"])
        self.assertIn("invalid_or_unqualified_uncertainty", cand["blocked_reasons"])

        # 2. check_disagreement treats NaN model comparator as critical contradiction
        ev = ValidationEvent(
            event_id="ev_02",
            plot_id="plot_1",
            geometry_hash="a" * 64,
            event_time=CUTOFF.isoformat(),
            source_type="farmer_observation",
            target_variable="vigor",
            observed_value=0.65,
            spatial_scope="plot",
            temporal_scope="instant",
            confidence=0.85,
            validator_role="farmer",
            trust_weight=0.85,
            evidence_hash="e" * 64,
        )
        asmae_output_nan = {
            "timestamp": CUTOFF.isoformat(),
            "raster_maps": {"vigor": [[float("nan"), float("nan")]]},
        }
        diag_report = check_disagreement(asmae_output_nan, [ev])
        self.assertEqual(diag_report["candidate_status"], "rejected")
        self.assertTrue(any(c["type"] == "unqualified_model_comparator" for c in diag_report["contradictions"]))

    def test_r415_07_invalid_rf_covariance_fails_closed(self):
        """R415-07: Invalid RF covariance fails closed as None and is marked ABSENT by layer0 spine."""
        from services.agribrain.mesia.contracts.behaviour import BehaviourLikelihood
        from services.agribrain.mesia.assimilation.asmae_operator import ASMAEObservationOperator
        from services.agribrain.mesia.assimilation.layer0_spine import Layer0EvidenceSpine, EvidenceAdmissionStatus

        # 1. Invalid covariance (NaN) produces variance=None
        lik_nan = BehaviourLikelihood(
            likelihood_id="lik_nan_01",
            radio_family="wifi_csi",
            contract_ref="contract_wifi_01",
            target_variable="soil_moisture",
            innovation=0.05,
            covariance=float("nan"),
            support=0.8,
            authority_scope="evidence_proposal",
            native_observation_ref="hash_ref_01",
        )
        proposal_nan = ASMAEObservationOperator.create_innovation(lik_nan, 0.25, "mz_1", "ROOT_ZONE")
        self.assertIsNone(proposal_nan.observation_variance)

        # Layer 0 spine marks it ABSENT
        rec_nan = Layer0EvidenceSpine.evaluate_admission(proposal_nan, is_calibration_valid=True, is_epoch_active=True)
        self.assertEqual(rec_nan.status, EvidenceAdmissionStatus.ABSENT)
        self.assertFalse(rec_nan.is_usable_for_assimilation)

        # 2. Truly absent covariance (None) receives default 0.25 and is admitted
        lik_none = BehaviourLikelihood(
            likelihood_id="lik_none_02",
            radio_family="wifi_csi",
            contract_ref="contract_wifi_01",
            target_variable="soil_moisture",
            innovation=0.05,
            covariance=None,
            support=0.8,
            authority_scope="evidence_proposal",
            native_observation_ref="hash_ref_02",
        )
        proposal_none = ASMAEObservationOperator.create_innovation(lik_none, 0.25, "mz_1", "ROOT_ZONE")
        self.assertEqual(proposal_none.observation_variance, 0.25)

        rec_none = Layer0EvidenceSpine.evaluate_admission(proposal_none, is_calibration_valid=True, is_epoch_active=True)
        self.assertEqual(rec_none.status, EvidenceAdmissionStatus.ADMITTED)
        self.assertTrue(rec_none.is_usable_for_assimilation)


class TestR39FollowUpVerification(unittest.TestCase):
    """R39-01, R39-02, R39-03: Precise follow-ups on legacy water exclusion, resolution fallback, and target parity."""

    def setUp(self):
        self.prior = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=[10.0, 30.0, 60.0],
            theta_profile=[0.20, 0.20, 0.20],
            field_capacity_profile=[0.35, 0.35, 0.35],
            wilting_point_profile=[0.12, 0.12, 0.12],
            saturation_profile=[0.45, 0.45, 0.45],
            residual_profile=[0.05, 0.05, 0.05],
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

    def _write_ledger(self, ledger_path, run_id, target_var, observed_val, observed_unit, res_selected_m=None, resolution_m=10.0):
        import json
        diag = {}
        if res_selected_m is not None:
            diag["resolution_selected_m"] = res_selected_m
        run_record = {
            "record_type": "asmae_run",
            "run_id": run_id,
            "plot_id": "plot_1",
            "geometry_hash": "a" * 64,
            "layer0_output_hash": "b" * 64,
            "asmae_content_hash": "c" * 64,
            "asmae_artifact_instance_hash": "d" * 64,
            "resolution_m": resolution_m,
            "diagnostics": diag,
        }
        val_event = {
            "record_type": "validation_event",
            "run_id": run_id,
            "event_id": f"ev_{run_id}",
            "source_type": "agronomist_observation",
            "target_variable": target_var,
            "observed_value": observed_val,
            "observed_unit": observed_unit,
            "confidence": 0.85,
        }
        cand_update = {
            "record_type": "candidate_update",
            "run_id": run_id,
            "learning_candidate_status": "approved",
            "eligible_for_asmae_learn": True,
            "candidate": {
                "candidate_id": f"cand_{run_id}",
                "candidate_type": "standard_learning",
                "disagreement_report_hash": "h" * 64,
                "target_variable": target_var,
            },
        }
        with open(ledger_path, "w") as f:
            f.write(json.dumps(run_record) + "\n")
            f.write(json.dumps(val_event) + "\n")
            f.write(json.dumps(cand_update) + "\n")

    def test_r39_01_legacy_exclusion_marker_preservation_with_tdr_identity(self):
        """R39-01: ['IN_SITU_PROBE_TDR', 'EXCLUDED'] must reject observations and yield 0 mm analysis increment."""
        # 1. Order 1: ['IN_SITU_PROBE_TDR', 'EXCLUDED']
        obs1 = SoilObservationVector(
            timestamp=CUTOFF,
            soil_probe_moisture_profile=[0.35, 0.35, 0.35],
            observation_uncertainties={"soil_probe": 0.015, "satellite_smap": 0.04},
            provenance_sources=["IN_SITU_PROBE_TDR", "EXCLUDED"],
        )
        post1, diag1 = WaterStateAssimilator.assimilate_observations(self.prior, obs1)
        self.assertEqual(diag1.observations_assimilated_count, 0)
        self.assertEqual(len(diag1.rejected_observations), 3)
        for r in diag1.rejected_observations:
            self.assertEqual(r["reason"], "explicitly_excluded_role")
            self.assertEqual(r["role"], "EXCLUDED")

        state1, receipt1 = WaterIntelligenceEngine.execute_pipeline(
            plot_id="plot-1",
            timestamp=CUTOFF,
            weather_observations=self.weather,
            soil_observations=obs1,
            soil_profile_state=self.prior,
        )
        self.assertEqual(state1.physics_authority, WaterPhysicsAuthority.MODELLED)
        self.assertEqual(state1.analysis_receipt.storage_increment_mm, 0.0)

        # 2. Order 2: ['EXCLUDED', 'IN_SITU_PROBE_TDR']
        obs2 = SoilObservationVector(
            timestamp=CUTOFF,
            soil_probe_moisture_profile=[0.35, 0.35, 0.35],
            observation_uncertainties={"soil_probe": 0.015, "satellite_smap": 0.04},
            provenance_sources=["EXCLUDED", "IN_SITU_PROBE_TDR"],
        )
        post2, diag2 = WaterStateAssimilator.assimilate_observations(self.prior, obs2)
        self.assertEqual(diag2.observations_assimilated_count, 0)
        self.assertEqual(len(diag2.rejected_observations), 3)

        state2, receipt2 = WaterIntelligenceEngine.execute_pipeline(
            plot_id="plot-1",
            timestamp=CUTOFF,
            weather_observations=self.weather,
            soil_observations=obs2,
            soil_profile_state=self.prior,
        )
        self.assertEqual(state2.physics_authority, WaterPhysicsAuthority.MODELLED)
        self.assertEqual(state2.analysis_receipt.storage_increment_mm, 0.0)

        # 3. Scoped satellite exclusion preserves independent valid TDR probe
        obs_scoped = SoilObservationVector(
            timestamp=CUTOFF,
            soil_probe_moisture_profile=[0.35, 0.35, 0.35],
            observation_uncertainties={"soil_probe": 0.015, "satellite_smap": 0.04},
            provenance_sources=["IN_SITU_PROBE_TDR", "EXCLUDED_SATELLITE_SMAP"],
        )
        post_scoped, diag_scoped = WaterStateAssimilator.assimilate_observations(self.prior, obs_scoped)
        self.assertEqual(diag_scoped.observations_assimilated_count, 3)
        state_scoped, receipt_scoped = WaterIntelligenceEngine.execute_pipeline(
            plot_id="plot-1",
            timestamp=CUTOFF,
            weather_observations=self.weather,
            soil_observations=obs_scoped,
            soil_profile_state=self.prior,
        )
        self.assertEqual(state_scoped.physics_authority, WaterPhysicsAuthority.OBSERVED)
        self.assertGreater(state_scoped.analysis_receipt.storage_increment_mm, 0.0)

    def test_r39_02_resolution_fallback_distinguishes_absence_from_invalid_zero_and_false(self):
        """R39-02: Explicit selected resolution 0.0 or False must reject candidate and not use fallback 10.0."""
        from services.agribrain.asmae_learn.candidate_builder import build_learning_candidate
        import tempfile
        from pathlib import Path
        from services.agribrain.asmae_learn.dataset_builder import build_validated_training_view

        base_event = {
            "event_id": "ev_res_01",
            "plot_id": "plot_1",
            "geometry_hash": "a" * 64,
            "event_time": CUTOFF.isoformat(),
            "source_type": "agronomist_observation",
            "target_variable": "canopy_water",
            "observed_value": 0.45,
            "spatial_scope": "plot",
            "temporal_scope": "instant",
            "confidence": 0.85,
            "validator_role": "agronomist",
            "evidence_hash": "e" * 64,
        }

        # 1. Candidate builder rejects explicit 0.0
        rec_zero = {
            "plot_id": "plot_1",
            "run_id": "run_res_0",
            "geometry_hash": "a" * 64,
            "layer0_output_hash": "b" * 64,
            "asmae_content_hash": "c" * 64,
            "asmae_artifact_instance_hash": "d" * 64,
            "target_variable": "canopy_water",
            "resolution_m": 10.0,
            "validation_events": [base_event],
            "diagnostics": {
                "bma_status": "success",
                "retro_status": "success_with_holdouts",
                "uncertainty": 0.15,
                "retro_mean_score": 0.85,
                "resolution_selected_m": 0.0,
            },
        }
        cand_zero = build_learning_candidate(rec_zero)
        self.assertFalse(cand_zero["eligible"])
        self.assertIn("invalid_resolution", cand_zero["blocked_reasons"])

        # 2. Candidate builder rejects explicit False
        rec_false = dict(rec_zero)
        rec_false["diagnostics"] = dict(rec_zero["diagnostics"])
        rec_false["diagnostics"]["resolution_selected_m"] = False
        cand_false = build_learning_candidate(rec_false)
        self.assertFalse(cand_false["eligible"])
        self.assertIn("invalid_resolution", cand_false["blocked_reasons"])

        # 3. Candidate builder accepts truly absent resolution_selected_m using valid fallback
        rec_absent = dict(rec_zero)
        rec_absent["diagnostics"] = dict(rec_zero["diagnostics"])
        del rec_absent["diagnostics"]["resolution_selected_m"]
        cand_absent = build_learning_candidate(rec_absent)
        self.assertTrue(cand_absent["eligible"])
        self.assertNotIn("invalid_resolution", cand_absent["blocked_reasons"])

        # 4. Replay in dataset builder excludes explicit 0.0 and False, admits absent with 10.0
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "validation_ledger.jsonl"
            
            # Write run with resolution_selected_m = 0.0
            self._write_ledger(ledger_path, "run_res_0", "canopy_water", 0.45, "fraction", res_selected_m=0.0)
            samples_zero = build_validated_training_view(ledger_path)
            self.assertEqual(len(samples_zero), 0)

            # Write run with resolution_selected_m = False
            self._write_ledger(ledger_path, "run_res_f", "canopy_water", 0.45, "fraction", res_selected_m=False)
            samples_false = build_validated_training_view(ledger_path)
            self.assertEqual(len(samples_false), 0)

            # Write run with absent resolution_selected_m and fallback 10.0
            self._write_ledger(ledger_path, "run_res_abs", "canopy_water", 0.45, "fraction", res_selected_m=None)
            samples_absent = build_validated_training_view(ledger_path)
            self.assertEqual(len(samples_absent), 1)
            self.assertEqual(samples_absent[0]["target_value"], 0.45)

    def test_r39_03_shared_continuous_target_qualifier_at_write_and_replay(self):
        """R39-03: Shared target/form/unit qualification rejects string and boolean fractional biotic targets."""
        import tempfile
        from pathlib import Path
        from services.agribrain.asmae_learn.schemas import ValidationEvent, is_continuous_target
        from services.agribrain.asmae_learn.dataset_builder import build_validated_training_view

        # Helper function
        self.assertTrue(is_continuous_target("biotic_confounder", "fraction", 0.5))
        self.assertTrue(is_continuous_target("biotic_confounder", "fraction", "0.5"))
        self.assertTrue(is_continuous_target("biotic_confounder", "fraction", "not-a-number"))
        self.assertFalse(is_continuous_target("biotic_confounder", "fraction", "low"))
        self.assertFalse(is_continuous_target("biotic_confounder", "category", "aphids"))

        # 1. ValidationEvent writer rejects string or boolean values for fractional biotic_confounder
        with self.assertRaises(ValueError):
            ValidationEvent(
                event_id="ev_b_01",
                plot_id="plot_1",
                geometry_hash="a" * 64,
                event_time=CUTOFF.isoformat(),
                source_type="agronomist_observation",
                target_variable="biotic_confounder",
                observed_value="0.5",
                observed_unit="fraction",
                spatial_scope="plot",
                temporal_scope="instant",
                confidence=0.85,
                validator_role="agronomist",
            )

        with self.assertRaises(ValueError):
            ValidationEvent(
                event_id="ev_b_02",
                plot_id="plot_1",
                geometry_hash="a" * 64,
                event_time=CUTOFF.isoformat(),
                source_type="agronomist_observation",
                target_variable="biotic_confounder",
                observed_value="not-a-number",
                observed_unit="fraction",
                spatial_scope="plot",
                temporal_scope="instant",
                confidence=0.85,
                validator_role="agronomist",
            )

        with self.assertRaises(ValueError):
            ValidationEvent(
                event_id="ev_b_03",
                plot_id="plot_1",
                geometry_hash="a" * 64,
                event_time=CUTOFF.isoformat(),
                source_type="agronomist_observation",
                target_variable="biotic_confounder",
                observed_value=False,
                observed_unit="fraction",
                spatial_scope="plot",
                temporal_scope="instant",
                confidence=0.85,
                validator_role="agronomist",
            )

        # Valid numeric float succeeds
        ev_valid = ValidationEvent(
            event_id="ev_b_04",
            plot_id="plot_1",
            geometry_hash="a" * 64,
            event_time=CUTOFF.isoformat(),
            source_type="agronomist_observation",
            target_variable="biotic_confounder",
            observed_value=0.5,
            observed_unit="fraction",
            spatial_scope="plot",
            temporal_scope="instant",
            confidence=0.85,
            validator_role="agronomist",
        )
        self.assertEqual(ev_valid.observed_value, 0.5)

        # 2. Reader in dataset_builder excludes legacy approved ledger with fractional strings
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / "validation_ledger.jsonl"

            # Legacy ledger with string observed_value = "0.5"
            self._write_ledger(ledger_path, "run_leg_1", "biotic_confounder", "0.5", "fraction")
            samples = build_validated_training_view(ledger_path)
            self.assertEqual(len(samples), 0, "String fractional biotic target must be excluded by reader")

            # Legacy ledger with string observed_value = "not-a-number"
            self._write_ledger(ledger_path, "run_leg_2", "biotic_confounder", "not-a-number", "fraction")
            samples_nan = build_validated_training_view(ledger_path)
            self.assertEqual(len(samples_nan), 0, "Non-numeric fractional biotic string must be excluded by reader")

            # Legacy ledger with boolean observed_value = False
            self._write_ledger(ledger_path, "run_leg_3", "biotic_confounder", False, "fraction")
            samples_bool = build_validated_training_view(ledger_path)
            self.assertEqual(len(samples_bool), 0, "Boolean fractional biotic must be excluded by reader")

            # Legacy ledger with valid float 0.5 is admitted
            self._write_ledger(ledger_path, "run_leg_valid", "biotic_confounder", 0.5, "fraction")
            samples_valid = build_validated_training_view(ledger_path)
            self.assertEqual(len(samples_valid), 1)
            self.assertEqual(samples_valid[0]["target_value"], 0.5)

            # Categorical biotic is retained as categorical
            self._write_ledger(ledger_path, "run_leg_cat", "biotic_confounder", "low", "category")
            samples_cat = build_validated_training_view(ledger_path)
            self.assertEqual(len(samples_cat), 1)
            self.assertEqual(samples_cat[0]["target_value"], "low")


class TestF01DownstreamPerceptionZeroInfluenceIntegration(unittest.TestCase):
    """Integration evidence verifying downstream zero-influence of zero-confidence perception inputs."""

    def test_zero_confidence_perception_fails_closed_in_packet_and_evidence(self):
        """Zero-confidence perception produces zero reliability_weight, zero qa scene_score, and diagnostic-only evidence."""
        from services.agribrain.layer0.perception.common.contracts import (
            PerceptionEngineFamily,
            PerceptionEngineOutput,
            PerceptionVariable,
        )
        from services.agribrain.layer0.perception.common.packet_adapter import to_observation_packets
        from services.agribrain.layer1_fusion.adapters.observation_packet import observation_packet_to_evidence
        from services.agribrain.layer1_fusion.schemas import Layer1InputBundle

        # 1. Perception output with 0.0 variable confidence
        out_zero_conf = PerceptionEngineOutput(
            engine_family=PerceptionEngineFamily.DRONE,
            plot_id="plot_test_1",
            qa_score=0.9,
            reliability_weight=0.8,
            variables=[
                PerceptionVariable(name="vegetation_fraction", value=0.45, sigma=0.03, confidence=0.0),
            ],
        )
        pkts = to_observation_packets(out_zero_conf)
        self.assertEqual(len(pkts), 1)
        pkt = pkts[0]
        self.assertEqual(pkt.reliability_weight, 0.0)
        self.assertEqual(pkt.qa.scene_score, 0.0)
        self.assertEqual(pkt.effective_weight(), 0.0)

        # 2. Bridge to Layer 1 EvidenceItem
        bundle = Layer1InputBundle(
            plot_id="plot_test_1",
            run_id="run_test_1",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
        )
        items = observation_packet_to_evidence(pkt, bundle)
        self.assertEqual(len(items), 1)
        ev = items[0]
        self.assertEqual(ev.confidence, 0.0)
        self.assertEqual(ev.reliability, 0.0)
        self.assertTrue(ev.diagnostic_only)
        self.assertFalse(ev.state_update_allowed)

        # 3. Positive control: valid perception item retains positive confidence and state update permission
        out_valid = PerceptionEngineOutput(
            engine_family=PerceptionEngineFamily.DRONE,
            plot_id="plot_test_1",
            qa_score=0.9,
            reliability_weight=0.85,
            variables=[
                PerceptionVariable(name="vegetation_fraction", value=0.45, sigma=0.03, confidence=0.8),
            ],
        )
        pkts_valid = to_observation_packets(out_valid)
        self.assertEqual(pkts_valid[0].reliability_weight, 0.8)
        self.assertGreater(pkts_valid[0].qa.scene_score, 0.0)
        items_valid = observation_packet_to_evidence(pkts_valid[0], bundle)
        self.assertGreater(items_valid[0].confidence, 0.0)
        self.assertGreater(items_valid[0].reliability, 0.0)
        self.assertTrue(items_valid[0].state_update_allowed)
        self.assertFalse(items_valid[0].diagnostic_only)

    def test_evidence_validator_rejects_zero_confidence_with_state_update(self):
        """validate_evidence catches any zero confidence or zero reliability item claiming state update permission."""
        from services.agribrain.layer1_fusion.evidence_validation import validate_evidence
        from services.agribrain.layer1_fusion.schemas import EvidenceItem

        # Item with zero confidence but state_update_allowed=True must be rejected
        item_bad_conf = EvidenceItem(
            evidence_id="ev_zero_conf",
            plot_id="plot_1",
            variable="vegetation_fraction",
            value=0.35,
            unit="fraction",
            source_family="perception",
            source_id="drone_01",
            observation_type="derived_feature",
            spatial_scope="plot",
            observed_at=CUTOFF,
            confidence=0.0,
            reliability=0.8,
            provenance_ref="ref_zero_conf",
            data_status="observed",
            production_usable=True,
            state_update_allowed=True,
            diagnostic_only=False,
        )
        violations = validate_evidence(item_bad_conf)
        self.assertTrue(any("ZERO_CONFIDENCE_OR_RELIABILITY_CANNOT_UPDATE_STATE" in v for v in violations))

        # Item with zero reliability but state_update_allowed=True must be rejected
        item_bad_rel = EvidenceItem(
            evidence_id="ev_zero_rel",
            plot_id="plot_1",
            variable="vegetation_fraction",
            value=0.35,
            unit="fraction",
            source_family="perception",
            source_id="drone_01",
            observation_type="derived_feature",
            spatial_scope="plot",
            observed_at=CUTOFF,
            confidence=0.8,
            reliability=0.0,
            provenance_ref="ref_zero_rel",
            data_status="observed",
            production_usable=True,
            state_update_allowed=True,
            diagnostic_only=False,
        )
        violations_rel = validate_evidence(item_bad_rel)
        self.assertTrue(any("ZERO_CONFIDENCE_OR_RELIABILITY_CANNOT_UPDATE_STATE" in v for v in violations_rel))

        # Conforming diagnostic item passes cleanly
        item_diagnostic = EvidenceItem(
            evidence_id="ev_diag_ok",
            plot_id="plot_1",
            variable="vegetation_fraction",
            value=0.35,
            unit="fraction",
            source_family="perception",
            source_id="drone_01",
            observation_type="derived_feature",
            spatial_scope="plot",
            observed_at=CUTOFF,
            confidence=0.0,
            reliability=0.0,
            provenance_ref="ref_diag_ok",
            data_status="observed",
            production_usable=True,
            state_update_allowed=False,
            diagnostic_only=True,
        )
        self.assertEqual(validate_evidence(item_diagnostic), [])

    def test_fusion_engine_zero_confidence_perception_has_zero_downstream_state_influence(self):
        """Zero-confidence perception packets processed by Layer 1 FusionEngine cannot alter state or fabricate confidence."""
        from services.agribrain.layer0.perception.common.contracts import (
            PerceptionEngineFamily,
            PerceptionEngineOutput,
            PerceptionVariable,
        )
        from services.agribrain.layer0.perception.common.packet_adapter import to_observation_packets
        from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
        from services.agribrain.layer1_fusion.schemas import Layer1InputBundle

        from services.agribrain.layer0.source_package import Layer0SourcePackage

        out_zero = PerceptionEngineOutput(
            engine_family=PerceptionEngineFamily.DRONE,
            plot_id="plot_pilot",
            timestamp=CUTOFF,
            qa_score=0.9,
            reliability_weight=0.0,  # Zero quality/reliability
            variables=[
                PerceptionVariable(name="vegetation_fraction", value=0.62, sigma=0.02, confidence=0.0),
            ],
        )
        pkts_zero = to_observation_packets(out_zero)
        src_pkg = Layer0SourcePackage(
            source_family="perception",
            plot_id="plot_pilot",
            packets=pkts_zero,
        )

        bundle = Layer1InputBundle(
            plot_id="plot_pilot",
            run_id="run_zero_inf_test",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
            perception_packages=[src_pkg],
        )

        engine = Layer1FusionEngine()
        context_pkg = engine.fuse(bundle)

        # 1. Ledger admission records item as diagnostic without state update
        ledger_items = context_pkg.evidence_items
        self.assertEqual(len(ledger_items), 1)
        self.assertFalse(ledger_items[0].state_update_allowed)
        self.assertTrue(ledger_items[0].diagnostic_only)
        self.assertEqual(ledger_items[0].confidence, 0.0)

        # 2. Fused feature set contains NO state feature with positive confidence for vegetation_fraction
        veg_features = context_pkg.fused_features.vegetation_context
        for feat in veg_features:
            if feat.name == "vegetation_fraction":
                self.assertEqual(feat.confidence, 0.0, "Zero-weight evidence cannot produce positive confidence")
                self.assertTrue(feat.diagnostic_only)

        # 3. Downstream L2/L3 adapter does not extract active drone structural signals
        from services.agribrain.layer2_intelligence.outputs.layer3_adapter import _extract_drone_structural_signals
        from services.agribrain.layer2_intelligence.schemas import Layer2Output

        fake_l2_output = Layer2Output(
            plot_id="plot_pilot",
            run_id="run_zero_inf_test",
            generated_at=CUTOFF,
            vegetation_intelligence=veg_features,
            stress_context=[],
        )
        signals = {}
        _extract_drone_structural_signals(fake_l2_output, signals)
        self.assertFalse(signals.get("has_drone_structural", False))
        self.assertNotIn("canopy_cover_fraction", signals)
        self.assertNotIn("bare_soil_fraction", signals)

    def test_a263_02_native_structural_adapter_quality_qualification_and_sibling_isolation(self):
        """P1 A263-02: Native structural adapter qualifies qa_score and reliability_weight; zero/NaN reliability does not contaminate siblings."""
        from services.agribrain.layer0.perception.drone_rgb.schemas import DroneRGBOutput
        from services.agribrain.layer1_fusion.adapters.drone import DroneStructuralAdapter
        from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
        from services.agribrain.layer1_fusion.schemas import Layer1InputBundle
        from services.agribrain.layer1_fusion.outputs.layer2_adapter import build_layer2_context
        from services.agribrain.layer2_intelligence.engine import Layer2IntelligenceEngine
        from services.agribrain.layer2_intelligence.outputs.layer3_adapter import _extract_drone_structural_signals

        adapter = DroneStructuralAdapter()
        context_bundle = Layer1InputBundle(
            plot_id="plot_pilot",
            run_id="run_test_a263_02",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
        )

        # 1. Direct adapter checks for zero and NaN reliability_weight
        d_bad_zero = DroneRGBOutput(
            plot_id="plot_pilot",
            mission_id="m_bad_zero",
            qa_score=1.0,
            reliability_weight=0.0,
            weed_pressure_index=0.60,
            canopy_cover_fraction=0.70,
            timestamp=CUTOFF,
        )
        items_zero = adapter.extract_evidence(d_bad_zero, context_bundle)
        self.assertTrue(len(items_zero) >= 2)
        for item in items_zero:
            self.assertEqual(item.confidence, 0.0)
            self.assertEqual(item.reliability, 0.0)
            self.assertTrue(item.diagnostic_only)
            self.assertFalse(item.state_update_allowed)
        health_zero = adapter.source_health(d_bad_zero)
        self.assertEqual(health_zero.trust_score, 0.0)
        self.assertEqual(health_zero.source_status, "unusable")

        d_bad_nan = DroneRGBOutput(
            plot_id="plot_pilot",
            mission_id="m_bad_nan",
            qa_score=1.0,
            reliability_weight=float("nan"),
            weed_pressure_index=0.60,
            canopy_cover_fraction=0.70,
            timestamp=CUTOFF,
        )
        items_nan = adapter.extract_evidence(d_bad_nan, context_bundle)
        for item in items_nan:
            self.assertEqual(item.confidence, 0.0)
            self.assertEqual(item.reliability, 0.0)
            self.assertTrue(item.diagnostic_only)
            self.assertFalse(item.state_update_allowed)
        health_nan = adapter.source_health(d_bad_nan)
        self.assertEqual(health_nan.trust_score, 0.0)
        self.assertEqual(health_nan.source_status, "unusable")

        # Positive control: valid finite reliability
        d_qual = DroneRGBOutput(
            plot_id="plot_pilot",
            mission_id="m_qual",
            qa_score=1.0,
            reliability_weight=0.85,
            weed_pressure_index=0.60,
            canopy_cover_fraction=0.70,
            timestamp=CUTOFF,
        )
        items_qual = adapter.extract_evidence(d_qual, context_bundle)
        for item in items_qual:
            self.assertGreater(item.confidence, 0.0)
            self.assertEqual(item.reliability, 0.85)
            self.assertFalse(item.diagnostic_only)
            self.assertTrue(item.state_update_allowed)
        health_qual = adapter.source_health(d_qual)
        self.assertEqual(health_qual.trust_score, 0.85)
        self.assertEqual(health_qual.source_status, "ok")

        # Legitimate numeric zero values with positive quality survive
        d_zero_val = DroneRGBOutput(
            plot_id="plot_pilot",
            mission_id="m_zero_val",
            qa_score=1.0,
            reliability_weight=1.0,
            canopy_cover_fraction=0.0,
            bare_soil_fraction=0.0,
            timestamp=CUTOFF,
        )
        items_zero_val = adapter.extract_evidence(d_zero_val, context_bundle)
        canopy_item = next(it for it in items_zero_val if it.variable == "canopy_cover_fraction")
        self.assertEqual(canopy_item.value, 0.0)
        self.assertEqual(canopy_item.reliability, 1.0)
        self.assertFalse(canopy_item.diagnostic_only)
        self.assertTrue(canopy_item.state_update_allowed)

        # 2. Mixed valid sibling numerical fusion and downstream L3 isolation
        # Baseline: qualified sibling alone with weed=0.30
        d_valid = DroneRGBOutput(
            plot_id="plot_pilot",
            mission_id="m_valid",
            qa_score=1.0,
            reliability_weight=1.0,
            weed_pressure_index=0.30,
            timestamp=CUTOFF,
        )
        bundle_baseline = Layer1InputBundle(
            plot_id="plot_pilot",
            run_id="run_base",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
            drone_structural_packages=[d_valid],
        )
        pkg_baseline = Layer1FusionEngine().fuse(bundle_baseline)
        weed_baseline = next(f for f in pkg_baseline.fused_features.vegetation_context if f.name == "weed_pressure_index")
        self.assertAlmostEqual(weed_baseline.value, 0.30, places=2)
        l2_baseline = Layer2IntelligenceEngine().analyze(build_layer2_context(pkg_baseline))
        sig_baseline = {}
        _extract_drone_structural_signals(l2_baseline, sig_baseline)
        self.assertAlmostEqual(sig_baseline["weed_pressure_severity"], 0.24, places=2)

        # Add invalid sibling with weed=0.60, reliability=0.0: MUST NOT contaminate to 0.45 / 0.36
        bundle_mixed_zero = Layer1InputBundle(
            plot_id="plot_pilot",
            run_id="run_mixed_zero",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
            drone_structural_packages=[d_valid, d_bad_zero],
        )
        pkg_mixed_zero = Layer1FusionEngine().fuse(bundle_mixed_zero)
        weed_mixed_zero = next(f for f in pkg_mixed_zero.fused_features.vegetation_context if f.name == "weed_pressure_index")
        self.assertAlmostEqual(weed_mixed_zero.value, 0.30, places=2, msg="Fused weed contaminated by zero-reliability sibling")
        l2_mixed_zero = Layer2IntelligenceEngine().analyze(build_layer2_context(pkg_mixed_zero))
        sig_mixed_zero = {}
        _extract_drone_structural_signals(l2_mixed_zero, sig_mixed_zero)
        self.assertAlmostEqual(sig_mixed_zero["weed_pressure_severity"], 0.24, places=2, msg="L3 weed severity contaminated by zero-reliability sibling")

        # Add invalid sibling with weed=0.60, reliability=NaN: MUST NOT contaminate
        bundle_mixed_nan = Layer1InputBundle(
            plot_id="plot_pilot",
            run_id="run_mixed_nan",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
            drone_structural_packages=[d_valid, d_bad_nan],
        )
        pkg_mixed_nan = Layer1FusionEngine().fuse(bundle_mixed_nan)
        weed_mixed_nan = next(f for f in pkg_mixed_nan.fused_features.vegetation_context if f.name == "weed_pressure_index")
        self.assertAlmostEqual(weed_mixed_nan.value, 0.30, places=2, msg="Fused weed contaminated by NaN-reliability sibling")
        l2_mixed_nan = Layer2IntelligenceEngine().analyze(build_layer2_context(pkg_mixed_nan))
        sig_mixed_nan = {}
        _extract_drone_structural_signals(l2_mixed_nan, sig_mixed_nan)
        self.assertAlmostEqual(sig_mixed_nan["weed_pressure_severity"], 0.24, places=2, msg="L3 weed severity contaminated by NaN-reliability sibling")

        # Standalone bad drone: produces no updatable state feature and no active L3 weed severity
        bundle_bad_alone = Layer1InputBundle(
            plot_id="plot_pilot",
            run_id="run_bad_alone",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
            drone_structural_packages=[d_bad_zero],
        )
        pkg_bad_alone = Layer1FusionEngine().fuse(bundle_bad_alone)
        updatable_weeds = [f for f in pkg_bad_alone.fused_features.vegetation_context if f.name == "weed_pressure_index" and not f.diagnostic_only]
        self.assertEqual(len(updatable_weeds), 0)
        l2_bad_alone = Layer2IntelligenceEngine().analyze(build_layer2_context(pkg_bad_alone))
        sig_bad_alone = {}
        _extract_drone_structural_signals(l2_bad_alone, sig_bad_alone)
        self.assertFalse(sig_bad_alone.get("has_drone_structural", False))
        self.assertEqual(sig_bad_alone.get("weed_pressure_severity", 0.0), 0.0)

    def test_a263_01_zero_quality_diagnostic_conflict_does_not_penalize_qualified_source(self):
        """P2 A263-01: Zero-quality diagnostic conflicts do not penalize qualified source confidence, while retaining diagnostic conflict lineage."""
        from services.agribrain.layer0.observation_packet import (
            ObservationPacket,
            ObservationSource,
            ObservationType,
            QAMetadata,
            UncertaintyModel,
            DataStatus,
        )
        from services.agribrain.layer0.perception.common.contracts import (
            PerceptionEngineFamily,
            PerceptionEngineOutput,
            PerceptionVariable,
        )
        from services.agribrain.layer0.perception.common.packet_adapter import to_observation_packets
        from services.agribrain.layer0.source_package import Layer0SourcePackage
        from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
        from services.agribrain.layer1_fusion.schemas import Layer1InputBundle

        from services.agribrain.sensor_runtime.registry import SensorDeviceRegistration, register_device
        register_device(SensorDeviceRegistration(
            device_id="pkt_sensor_1",
            vendor="acme",
            model="probe-x",
            protocol="lora",
            farm_id="farm_pilot",
            plot_id="plot_pilot",
            latitude=35.0,
            longitude=10.0,
            variables=["vegetation_fraction"],
            installation_datetime=CUTOFF,
            status="active",
            calibration_profile_id="cal_v1",
        ))

        # 1. Baseline: Valid point sensor vegetation_fraction=0.20 alone
        pkt_sensor = ObservationPacket(
            packet_id="pkt_sensor_1",
            source=ObservationSource.SENSOR_IOT,
            obs_type=ObservationType.POINT_TIMESERIES,
            data_status=DataStatus.OBSERVED,
            timestamp=CUTOFF,
            spatial_scope="point",
            point=(35.0, 10.0),
            qa=QAMetadata(scene_score=1.0, sensor_health=1.0),
            uncertainty=UncertaintyModel(error_model="gaussian", sigmas={"vegetation_fraction": 0.02}),
            payload={"variable": "vegetation_fraction", "value": 0.20, "unit": "fraction", "instrument_id": "pkt_sensor_1", "calibration_version": "cal_v1"},
            reliability_weight=1.0,
        )
        sensor_src = Layer0SourcePackage(source_family="sensor", plot_id="plot_pilot", packets=[pkt_sensor])

        bundle_sensor_only = Layer1InputBundle(
            plot_id="plot_pilot",
            run_id="run_sensor_only",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
            sensor_context_package=sensor_src,
        )
        pkg_sensor_only = Layer1FusionEngine().fuse(bundle_sensor_only)
        ev_s_base = next(e for e in pkg_sensor_only.evidence_items if e.source_family == "sensor")
        fused_s_base = next(f for f in pkg_sensor_only.fused_features.vegetation_context if f.name == "vegetation_fraction" and not f.diagnostic_only)
        self.assertAlmostEqual(ev_s_base.confidence, 0.95, places=2)
        self.assertAlmostEqual(fused_s_base.confidence, 0.95, places=2)
        self.assertAlmostEqual(fused_s_base.value, 0.20, places=2)

        # 2. Add disagreeing plot drone with reliability_weight=0.0
        drone_out_zero = PerceptionEngineOutput(
            engine_family=PerceptionEngineFamily.DRONE,
            plot_id="plot_pilot",
            timestamp=CUTOFF,
            qa_score=1.0,
            reliability_weight=0.0,
            variables=[PerceptionVariable(name="vegetation_fraction", value=0.95, sigma=0.02, confidence=0.0)],
        )
        drone_src_zero = Layer0SourcePackage(
            source_family="perception",
            plot_id="plot_pilot",
            packets=to_observation_packets(drone_out_zero),
        )

        bundle_disagree_zero = Layer1InputBundle(
            plot_id="plot_pilot",
            run_id="run_disagree_zero",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
            sensor_context_package=sensor_src,
            perception_packages=[drone_src_zero],
        )
        pkg_disagree_zero = Layer1FusionEngine().fuse(bundle_disagree_zero)
        ev_s_zero = next(e for e in pkg_disagree_zero.evidence_items if e.source_family == "sensor")
        fused_s_zero = next(f for f in pkg_disagree_zero.fused_features.vegetation_context if f.name == "vegetation_fraction" and not f.diagnostic_only)

        # Diagnostic lineage is preserved: conflict is detected and reported
        scope_conflicts_zero = [c for c in pkg_disagree_zero.conflicts if c.conflict_type == "SCOPE_MISMATCH"]
        self.assertGreater(len(scope_conflicts_zero), 0, "Diagnostic SCOPE_MISMATCH conflict must be retained")

        # But valid sensor evidence and fused confidence must NOT be penalized
        self.assertAlmostEqual(ev_s_zero.confidence, 0.95, places=2, msg="Valid sensor confidence penalized by zero-weight drone conflict")
        self.assertAlmostEqual(fused_s_zero.confidence, 0.95, places=2, msg="Valid sensor fused confidence penalized by zero-weight drone conflict")
        self.assertAlmostEqual(fused_s_zero.value, 0.20, places=2)

        # 3. Add disagreeing plot drone with reliability_weight=NaN
        drone_out_nan = PerceptionEngineOutput(
            engine_family=PerceptionEngineFamily.DRONE,
            plot_id="plot_pilot",
            timestamp=CUTOFF,
            qa_score=1.0,
            reliability_weight=float("nan"),
            variables=[PerceptionVariable(name="vegetation_fraction", value=0.95, sigma=0.02, confidence=0.0)],
        )
        drone_src_nan = Layer0SourcePackage(
            source_family="perception",
            plot_id="plot_pilot",
            packets=to_observation_packets(drone_out_nan),
        )

        bundle_disagree_nan = Layer1InputBundle(
            plot_id="plot_pilot",
            run_id="run_disagree_nan",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
            sensor_context_package=sensor_src,
            perception_packages=[drone_src_nan],
        )
        pkg_disagree_nan = Layer1FusionEngine().fuse(bundle_disagree_nan)
        ev_s_nan = next(e for e in pkg_disagree_nan.evidence_items if e.source_family == "sensor")
        fused_s_nan = next(f for f in pkg_disagree_nan.fused_features.vegetation_context if f.name == "vegetation_fraction" and not f.diagnostic_only)
        self.assertAlmostEqual(ev_s_nan.confidence, 0.95, places=2)
        self.assertAlmostEqual(fused_s_nan.confidence, 0.95, places=2)
        self.assertAlmostEqual(fused_s_nan.value, 0.20, places=2)

        # 4. Agreeing control: zero-quality drone with agreeing value 0.20 preserves 0.95 confidence
        drone_out_agree = PerceptionEngineOutput(
            engine_family=PerceptionEngineFamily.DRONE,
            plot_id="plot_pilot",
            timestamp=CUTOFF,
            qa_score=1.0,
            reliability_weight=0.0,
            variables=[PerceptionVariable(name="vegetation_fraction", value=0.20, sigma=0.02, confidence=0.0)],
        )
        drone_src_agree = Layer0SourcePackage(
            source_family="perception",
            plot_id="plot_pilot",
            packets=to_observation_packets(drone_out_agree),
        )
        bundle_agree = Layer1InputBundle(
            plot_id="plot_pilot",
            run_id="run_agree",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
            sensor_context_package=sensor_src,
            perception_packages=[drone_src_agree],
        )
        pkg_agree = Layer1FusionEngine().fuse(bundle_agree)
        ev_s_agree = next(e for e in pkg_agree.evidence_items if e.source_family == "sensor")
        self.assertAlmostEqual(ev_s_agree.confidence, 0.95, places=2)

        # 5. Positive control: Qualified disagreeing drone with reliability_weight=0.85 DOES penalize sensor confidence
        drone_out_qual = PerceptionEngineOutput(
            engine_family=PerceptionEngineFamily.DRONE,
            plot_id="plot_pilot",
            timestamp=CUTOFF,
            qa_score=1.0,
            reliability_weight=0.85,
            variables=[PerceptionVariable(name="vegetation_fraction", value=0.95, sigma=0.02, confidence=0.85)],
        )
        drone_src_qual = Layer0SourcePackage(
            source_family="perception",
            plot_id="plot_pilot",
            packets=to_observation_packets(drone_out_qual),
        )
        bundle_qual = Layer1InputBundle(
            plot_id="plot_pilot",
            run_id="run_qual",
            run_timestamp=CUTOFF,
            window_start=CUTOFF,
            window_end=CUTOFF,
            sensor_context_package=sensor_src,
            perception_packages=[drone_src_qual],
        )
        pkg_qual = Layer1FusionEngine().fuse(bundle_qual)
        ev_s_qual = next(e for e in pkg_qual.evidence_items if e.source_family == "sensor")
        fused_s_qual = next(f for f in pkg_qual.fused_features.vegetation_context if f.name == "vegetation_fraction" and not f.diagnostic_only)
        self.assertAlmostEqual(ev_s_qual.confidence, 0.85, places=2, msg="Qualified disagreement failed to apply expected conflict penalty")
        self.assertAlmostEqual(fused_s_qual.confidence, 0.85, places=2)


if __name__ == "__main__":
    unittest.main()



