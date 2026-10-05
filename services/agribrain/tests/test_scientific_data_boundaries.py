"""Regressions for provenance, prospective timing and physical input integrity.

Run with PYTHONPATH=services/agribrain python -m unittest discover
    -s services/agribrain/tests -p test_scientific_data_boundaries.py -v
"""

import json
import unittest
from dataclasses import asdict
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np

from layer0.observation_packet import DataStatus, ObservationPacket, ObservationSource
from layer0.wrappers import _infer_data_status, aggregate_data_status, ensure_observation_packet
from layer05_asmae.resilient_posterior import (
    _is_proven_before_cutoff, _prior_state_estimates, _records_as_of,
    _strip_dynamic_recursive, _extract_signal, estimate_resilient_plot_posterior,
)
from layer3_water.assimilation.water_state_assimilator import WaterStateAssimilator
from layer3_water.contracts.assimilation_state import SoilObservationVector
from layer3_water.contracts.state_factory import WaterStateFactory
from layer3_water.runner import WaterIntelligenceEngine
from layer3_water.contracts.authority import WaterPhysicsAuthority
from services.agribrain.scientific_contracts.exceptions import ContractViolation
from scientific_contracts.numeric import finite_real
from scientific_contracts.observation import ASMAEObservationPayload


CUTOFF = datetime(2026, 1, 2, tzinfo=timezone.utc)
EARLY = "2026-01-01T12:00:00Z"
LATE = "2026-01-03T12:00:00Z"


def qualified(**values):
    return {"timestamp": EARLY, "available_at": EARLY, **values}


class ProvenanceBoundaryTests(unittest.TestCase):
    def test_unknown_status_never_becomes_observed(self):
        for raw in (None, "", "unknown", "obseved", [], {}, False):
            with self.subTest(raw=raw):
                self.assertEqual(DataStatus.from_value(raw), DataStatus.UNAVAILABLE)
                self.assertEqual(
                    _infer_data_status({"data_status": raw}, ObservationSource.SENSOR_IOT),
                    DataStatus.UNAVAILABLE,
                )

    def test_known_statuses_preserve_their_role(self):
        for status in DataStatus:
            with self.subTest(status=status):
                self.assertEqual(DataStatus.from_value(status.value), status)
                self.assertEqual(DataStatus.from_value(status), status)

    def test_observed_declaration_cannot_override_synthetic_or_forecast_source(self):
        self.assertEqual(_infer_data_status(
            {"data_status": "observed", "simulated": True}, ObservationSource.SENSOR_IOT,
        ), DataStatus.SIMULATED)
        self.assertEqual(_infer_data_status(
            {"data_status": "observed"}, ObservationSource.WEATHER_FORECAST,
        ), DataStatus.ESTIMATED)
        self.assertEqual(_infer_data_status(
            {"data_status": "observed", "packet_type": "calibration_failed"}, ObservationSource.SENSOR_IOT,
        ), DataStatus.UNAVAILABLE)

    def test_packet_normalizes_status_before_hash_and_serialization(self):
        packet = ObservationPacket(data_status="obseved", payload={"data_status": "obseved"}, content_hash="old-hash")
        self.assertEqual(packet.to_dict()["data_status"], "unavailable")
        self.assertEqual(packet.payload["data_status"], "obseved")
        self.assertNotEqual(packet.content_hash, "old-hash")
        self.assertEqual(packet.to_dict()["unrecognized_data_status"], "'obseved'")
        self.assertEqual(packet.effective_weight(), 0.0)

    def test_wrapper_cannot_promote_an_unavailable_packet(self):
        for source, payload in (
            (ObservationSource.SENSOR_IOT, {}),
            (ObservationSource.SENTINEL2, {}),
            (ObservationSource.SENTINEL2, {"crs": "EPSG:32631", "transform": [0, 10, 0, 0, 0, -10]}),
        ):
            with self.subTest(source=source, payload=payload):
                packet = ObservationPacket(source=source, data_status="unknown", payload=payload)
                wrapped = ensure_observation_packet(packet, source, "plot", "geometry", 1)
                self.assertEqual(wrapped.data_status, DataStatus.UNAVAILABLE)
                self.assertEqual(wrapped.effective_weight(), 0.0)

    def test_wrapper_preserves_non_observed_role_without_payload_metadata(self):
        for status in (DataStatus.ESTIMATED, DataStatus.ASSIMILATED, DataStatus.SIMULATED):
            packet = ObservationPacket(source=ObservationSource.SENSOR_IOT, data_status=status)
            wrapped = ensure_observation_packet(packet, packet.source, "plot", "geometry", 1)
            self.assertEqual(wrapped.data_status, status)

    def test_aggregation_does_not_promote_unavailable_or_assimilated(self):
        def packets(*statuses):
            return [ObservationPacket(data_status=s) for s in statuses]
        self.assertEqual(aggregate_data_status(packets(DataStatus.UNAVAILABLE), True), DataStatus.UNAVAILABLE)
        self.assertEqual(aggregate_data_status(packets(DataStatus.ASSIMILATED), True), DataStatus.ASSIMILATED)
        self.assertNotEqual(
            aggregate_data_status(packets(DataStatus.OBSERVED, DataStatus.UNAVAILABLE), True),
            DataStatus.OBSERVED,
        )
        self.assertEqual(aggregate_data_status(packets(DataStatus.OBSERVED), True), DataStatus.OBSERVED)


class NumericBoundaryTests(unittest.TestCase):
    def test_numeric_qualification_rejects_coercion_and_non_finite_values(self):
        for raw in (None, True, False, "0.2", float("nan"), float("inf"), -float("inf"), 10**1000):
            with self.subTest(raw=repr(raw)):
                self.assertIsNone(finite_real(raw))
        for raw in (0, 0.0, np.float32(0.2), np.float64(0.2)):
            with self.subTest(valid=raw):
                self.assertIsNotNone(finite_real(raw))

    def test_payload_rejects_invalid_value_variance_and_units(self):
        valid = dict(
            observation_id="obs-1", target_state_variable="canopy_water", microzone_id="mz-1",
            depth_stratum="canopy", observation_value=0.2, observation_units="mm",
            observation_variance=0.01, forward_operator_id="canopy-native",
            calibration_certificate_id="", truth_class="MEASURED_NATIVE", knowledge_cutoff=CUTOFF,
        )
        for key, bads in (
            ("observation_value", [True, "0.2", float("nan"), float("inf")]),
            ("observation_variance", [True, "0.1", 0, -1, float("nan"), float("inf")]),
            ("observation_units", [None, "", "   "]),
        ):
            for raw in bads:
                with self.subTest(key=key, raw=raw):
                    with self.assertRaises(ValueError):
                        ASMAEObservationPayload(**{**valid, key: raw})
        native = ASMAEObservationPayload(**{**valid, "observation_value": np.float32(0.2)})
        json.dumps(native.to_dict(), allow_nan=False)
        zero = ASMAEObservationPayload(**{
            **valid, "target_state_variable": "root_zone_water", "observation_value": 0.0,
            "observation_units": "volumetric fraction [0,1]",
        })
        self.assertEqual(zero.observation_value, 0.0)


class ProspectiveTimingTests(unittest.TestCase):
    def test_both_observation_and_availability_proof_are_required(self):
        for row in ({}, {"timestamp": EARLY}, {"available_at": EARLY}, qualified(timestamp=None)):
            with self.subTest(row=row):
                self.assertFalse(_is_proven_before_cutoff(row, CUTOFF))
        self.assertTrue(_is_proven_before_cutoff(qualified(), CUTOFF))

    def test_timestamps_cannot_qualify_unknown_or_synthetic_provenance(self):
        for status in (None, "unknown", "unavailable", "simulated", "fallback"):
            with self.subTest(status=status):
                row = qualified(data_status=status, soil_moisture=0.6)
                self.assertFalse(_is_proven_before_cutoff(row, CUTOFF))
                self.assertEqual(_records_as_of([row], CUTOFF), [])

    def test_inherited_timing_cannot_qualify_rejected_nested_provenance(self):
        for flags in ({"data_status": "unknown"}, {"simulated": True}, {"fallback": True}):
            soil = qualified(soil_moisture={"value": 0.6, **flags})
            self.assertNotIn("soil_moisture", _strip_dynamic_recursive(soil, CUTOFF, is_proven=True))
            row = qualified(payload={"ndvi": {"mean": 0.7, **flags}})
            self.assertNotIn("ndvi", _records_as_of([row], CUTOFF)[0]["payload"])

    def test_late_or_invalid_alias_cannot_hide_behind_an_early_alias(self):
        for key in ("recorded_at", "known_at", "created_at", "observed_at", "date", "valid_time"):
            for stamp in (LATE, "2026-01-01Tnot-a-time", None):
                with self.subTest(key=key, stamp=stamp):
                    self.assertFalse(_is_proven_before_cutoff(qualified(**{key: stamp}), CUTOFF))

    def test_exact_cutoff_and_timezone_normalization(self):
        self.assertTrue(_is_proven_before_cutoff(
            qualified(timestamp="2026-01-02T01:00:00+01:00", available_at=CUTOFF), CUTOFF,
        ))
        self.assertFalse(_is_proven_before_cutoff(
            qualified(timestamp="2026-01-02T01:00:01+01:00"), CUTOFF,
        ))

    def test_rejected_nested_measurement_is_removed_whole(self):
        for value in ({"value": 0.6}, {"mean": 0.6}, {"estimate": 0.6}, {"median": 0.6}):
            soil = qualified(clay_pct=20.0, soil_moisture=qualified(**value, timestamp=LATE))
            filtered = _strip_dynamic_recursive(soil, CUTOFF, is_proven=True)
            self.assertNotIn("soil_moisture", filtered)
            self.assertEqual(filtered["clay_pct"], 20.0)
            self.assertNotIn("root_zone_water", _prior_state_estimates(
                SimpleNamespace(soil_context=soil, coarse_layer_outputs={}), as_of=CUTOFF,
            ))

    def test_lists_cannot_hide_future_dynamic_measurements(self):
        soil = {"clay_pct": 20.0, "measurements": [qualified(soil_moisture=0.0), qualified(soil_moisture=0.6, timestamp=LATE)]}
        filtered = _strip_dynamic_recursive(soil, CUTOFF)
        self.assertEqual(filtered["measurements"][0]["soil_moisture"], 0.0)
        self.assertNotIn("soil_moisture", filtered["measurements"][1])

    def test_eligible_nested_prior_preserves_zero(self):
        states = _prior_state_estimates(SimpleNamespace(
            soil_context={"soil_moisture": qualified(value=0.0)}, coarse_layer_outputs={},
        ), as_of=CUTOFF)
        self.assertEqual(states["root_zone_water"]["mean"], 0.0)

    def test_zero_temperature_is_supported_weather(self):
        states = _prior_state_estimates(SimpleNamespace(
            soil_context={}, coarse_layer_outputs={}, weather_daily_series=[qualified(temp_max=0.0)],
        ), as_of=CUTOFF)
        self.assertEqual(states["thermal_stress"]["mean"], 0.0)
        self.assertEqual(states["thermal_stress"]["observation_count"], 1)

    def test_forecast_is_not_an_observed_initial_state(self):
        row = qualified(data_status="forecast", valid_time=LATE, soil_moisture=0.6)
        original = dict(row)
        self.assertEqual(_records_as_of([row], CUTOFF), [])
        self.assertNotIn("soil_moisture", _strip_dynamic_recursive(row, CUTOFF))
        self.assertEqual(row, original)  # issuance inputs remain available to their scenario path

    def test_weather_and_signal_rows_require_available_native_evidence(self):
        early = qualified(precipitation=0.0)
        unproven = {"date": EARLY, "precipitation": 0.0}
        late = qualified(recorded_at=LATE, precipitation=5.0)
        nested = qualified(payload=qualified(ndvi=0.7, timestamp=LATE))
        filtered = _records_as_of([early, unproven, late, nested], CUTOFF)
        self.assertEqual(filtered[0], early)
        self.assertEqual(len(filtered), 2)
        self.assertNotIn("payload", filtered[1])
        self.assertIsNone(_extract_signal(filtered[1], "ndvi"))
        self.assertEqual(_records_as_of([early], "invalid-cutoff"), [])

    def test_nested_signal_removal_preserves_independent_valid_components(self):
        row = qualified(payload={"ndvi": qualified(mean=0.7, timestamp=LATE), "ndmi": qualified(value=0.2)})
        filtered = _records_as_of([row], CUTOFF)[0]
        self.assertNotIn("ndvi", filtered["payload"])
        self.assertEqual(filtered["payload"]["ndmi"]["value"], 0.2)
        self.assertIn("ndvi", row["payload"])

    def test_invalid_requested_cutoff_cannot_disable_filtering(self):
        inp = SimpleNamespace(soil_context={"soil_moisture": 0.6}, coarse_layer_outputs={})
        self.assertEqual(_prior_state_estimates(inp, as_of="invalid"), {})
        with self.assertRaises(ValueError):
            estimate_resilient_plot_posterior(inp, as_of="invalid")


class SoilAssimilationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.prior = WaterStateFactory.create_soil_water_state(
            [10.0, 30.0], [0.2, 0.2], [0.3, 0.3], [0.1, 0.1], [0.45, 0.45], [0.04, 0.04],
        )

    def test_invalid_probe_values_cannot_saturate_the_state(self):
        for raw in (None, True, "0.2", float("nan"), float("inf"), -float("inf"), -0.1, 0.9):
            with self.subTest(raw=raw):
                post, diag = WaterStateAssimilator.assimilate_observations(
                    self.prior, SoilObservationVector(CUTOFF, soil_probe_moisture_profile=[raw]),
                )
                self.assertIs(post, self.prior)
                self.assertEqual(diag.observations_assimilated_count, 0)
                self.assertEqual(diag.assimilated_sensor_sources, [])
                self.assertEqual(len(diag.rejected_observations), 1)
                json.dumps(asdict(diag), allow_nan=False)

    def test_invalid_covariance_is_rejected_without_a_fake_fallback(self):
        for sigma in (0, -1, True, "0.1", float("nan"), float("inf"), 1e-300, 1e308):
            with self.subTest(sigma=sigma):
                post, diag = WaterStateAssimilator.assimilate_observations(self.prior, SoilObservationVector(
                    CUTOFF, soil_probe_moisture_profile=[0.3], observation_uncertainties={"soil_probe": sigma},
                ))
                self.assertIs(post, self.prior)
                self.assertEqual(diag.rejected_observations[0]["reason"], "invalid_observation_uncertainty")

    def test_invalid_background_covariance_fails_closed(self):
        for sigma in (0, -1, True, float("nan"), float("inf"), 1e-300, 1e154, 1e308):
            with self.subTest(sigma=sigma), self.assertRaises(ValueError):
                WaterStateAssimilator.assimilate_observations(self.prior, background_uncertainty_sigma=sigma)

    def test_partial_source_acceptance_preserves_rejection_and_valid_update(self):
        post, diag = WaterStateAssimilator.assimilate_observations(self.prior, SoilObservationVector(
            CUTOFF, soil_probe_moisture_profile=[float("inf"), 0.3], satellite_surface_moisture_m3_m3=0.25,
        ))
        self.assertEqual(diag.observations_assimilated_count, 2)
        self.assertEqual(len(diag.rejected_observations), 1)
        self.assertEqual(set(diag.assimilated_sensor_sources), {"IN_SITU_PROBE_TDR", "SATELLITE_SMAP_SENTINEL1"})
        self.assertGreater(post.theta_profile[1], self.prior.theta_profile[1])
        self.assertTrue(all(np.isfinite(post.theta_profile)))

    def test_missing_or_invalid_satellite_and_thermal_values(self):
        for kwargs in (
            {"satellite_surface_moisture_m3_m3": float("inf")},
            {"canopy_cooling_differential_c": float("inf")},
        ):
            post, diag = WaterStateAssimilator.assimilate_observations(self.prior, SoilObservationVector(CUTOFF, **kwargs))
            self.assertIs(post, self.prior)
            self.assertEqual(len(diag.rejected_observations), 1)
        post, diag = WaterStateAssimilator.assimilate_observations(self.prior, SoilObservationVector(CUTOFF))
        self.assertIs(post, self.prior)
        self.assertEqual(diag.rejected_observations, [])

    def test_real_zero_measurement_is_not_missing(self):
        _, diag = WaterStateAssimilator.assimilate_observations(
            self.prior, SoilObservationVector(CUTOFF, satellite_surface_moisture_m3_m3=0.0),
        )
        self.assertEqual(diag.observations_assimilated_count, 1)
        self.assertEqual(diag.rejected_observations, [])


class WaterPipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.weather = {
            "t_max_c": 25.0, "t_min_c": 15.0, "precipitation_mm": 0.0,
            "wind_speed_2m_m_s": 2.0, "rh_min_pct": 30.0, "rh_max_pct": 60.0,
            "net_radiation_mj_m2": 10.0,
        }

    def run_pipeline(self, **overrides):
        return WaterIntelligenceEngine.execute_pipeline(
            plot_id="plot-1", timestamp=CUTOFF,
            **{"weather_observations": self.weather, **overrides},
        )

    def test_rejected_probe_cannot_upgrade_published_state_to_observed(self):
        state, receipt = self.run_pipeline(soil_observations=SoilObservationVector(
            CUTOFF, soil_probe_moisture_profile=[float("inf")],
        ))
        self.assertEqual(state.physics_authority, WaterPhysicsAuthority.MODELLED)
        self.assertEqual(state.assimilation_diagnostic.observations_assimilated_count, 0)
        self.assertEqual(len(state.assimilation_diagnostic.rejected_observations), 1)
        self.assertTrue(np.isfinite(receipt.transpiration_constraint_factor))
        json.dumps(asdict(state), default=str, allow_nan=False)

    def test_valid_probe_still_produces_supported_assimilation(self):
        state, _ = self.run_pipeline(soil_observations=SoilObservationVector(
            CUTOFF, soil_probe_moisture_profile=[0.2],
        ))
        self.assertEqual(state.physics_authority, WaterPhysicsAuthority.OBSERVED)
        self.assertEqual(state.assimilation_diagnostic.observations_assimilated_count, 1)

    def test_weather_and_applied_water_are_qualified_before_model_execution(self):
        for key, bads in (
            ("t_max_c", [float("nan"), float("inf"), True, "25"]),
            ("precipitation_mm", [-1, float("inf")]),
            ("wind_speed_2m_m_s", [-1, float("nan")]),
            ("rh_min_pct", [-1, 101, 80]),
            ("weather_sigma_override", [-1, float("inf")]),
            ("t_min_c", [30]),
        ):
            for raw in bads:
                with self.subTest(key=key, raw=raw), self.assertRaises(ContractViolation):
                    self.run_pipeline(weather_observations={**self.weather, key: raw})
        for raw in (True, "10", -1, float("inf")):
            with self.subTest(irrigation=raw), self.assertRaises(ContractViolation):
                self.run_pipeline(irrigation_applied_mm=raw)

    def test_zero_weather_values_are_preserved_without_mutating_input(self):
        weather = {**self.weather, "t_min_c": 0.0, "t_max_c": 0.0, "precipitation_mm": 0.0}
        before = dict(weather)
        state, _ = self.run_pipeline(weather_observations=weather)
        self.assertEqual(weather, before)
        self.assertEqual(state.fluxes.actual.precipitation_mm, 0.0)


if __name__ == "__main__":
    unittest.main()
