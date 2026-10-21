"""Authoritative verification suite for Package F02:
Enforce observation time and availability at issuance (AB-DAT-004, AB-DAT-014, AB-ML-008).

Verifies the 4 implementation tasks:
  1. ST01-F02-01: Explicit cutoff and observation/availability provenance for measurements,
     including causality enforcement (availability cannot precede observation).
  2. ST01-F02-02: Typed timing for measurements, priors, forecasts and management scenarios
     (TimingRole, TemporalTiming, admission ledger audit, excluded revision logging).
  3. ST01-F02-03: Decision cutoff propagation through layers (historical extractor, L3 weather adapter,
     checkpoint scan, assimilation state filter).
  4. ST01-F02-04: Recorded excluded revisions and archived knowledge view integrity during replay.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, List

import numpy as np

from services.agribrain.layer0.temporal_evidence import (
    TimingRole,
    TemporalTiming,
    extract_temporal_timing,
    is_admitted_temporal_record,
    build_temporal_admission_ledger,
)
from services.agribrain.layer05_asmae.resilient_posterior import (
    ARCHIVE_POSTERIOR_CONTRACT_VERSION,
    _is_proven_before_cutoff,
    _records_as_of,
    _strip_dynamic_recursive,
    _prior_state_estimates,
    estimate_resilient_plot_posterior,
)
from services.agribrain.world_model.historical_extractor import (
    BitemporalWorldlineExtractor,
    TrainingTrajectoryWindow,
    _is_prospective_scenario_event,
)
from unittest.mock import MagicMock
from services.agribrain.layer3_decision.runner import (
    _is_weather_available_at_issuance,
    _execute_canonical_water_engine,
)
from services.agribrain.layer3_water.contracts.assimilation_state import SoilObservationVector
from services.agribrain.layer3_water.contracts.state_factory import WaterStateFactory
from services.agribrain.layer3_water.assimilation.water_state_assimilator import WaterStateAssimilator


CUTOFF = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
EARLY = "2026-01-01T12:00:00Z"
AT_CUTOFF = "2026-01-02T12:00:00Z"
LATE = "2026-01-03T12:00:00Z"
LATER_REVISION = "2026-01-10T12:00:00Z"


def make_record(
    *,
    obs_time: str = EARLY,
    avail_time: str = EARLY,
    role: str = "OBSERVED",
    is_forecast: bool = False,
    reality: str = "provider_daily_statistical_aggregate",
    usable: bool = True,
    qa_admitted: bool = True,
    ndvi: float = 0.65,
    **extra: Any,
) -> Dict[str, Any]:
    return {
        "source_reality": reality,
        "provider_product_id": "prod-s2-20260101-001",
        "content_hash": "sha256-abcdef1234567890",
        "geometry_hash": "geom-plot-42",
        "valid_pixel_count": 100,
        "quality_class": "good",
        "usable": usable,
        "production_usable": True,
        "quality_admitted": qa_admitted,
        "diagnostic_only": False,
        "ndvi": ndvi,
        "observation_time": obs_time,
        "available_at": avail_time,
        "role": role,
        "is_forecast": is_forecast,
        **extra,
    }


class TestF02ST01ProspectiveMeasurementProvenance(unittest.TestCase):
    """ST01-F02-01: Require both observation and availability provenance for measurements."""

    def test_both_observation_and_availability_timestamps_required(self):
        # Missing availability
        rec1 = {"timestamp": EARLY}
        self.assertFalse(_is_proven_before_cutoff(rec1, CUTOFF))

        # Missing observation
        rec2 = {"available_at": EARLY}
        self.assertFalse(_is_proven_before_cutoff(rec2, CUTOFF))

        # Both present and before cutoff
        rec3 = {"timestamp": EARLY, "available_at": EARLY}
        self.assertTrue(_is_proven_before_cutoff(rec3, CUTOFF))

    def test_physical_causality_enforced(self):
        # An observation cannot be known/available before it occurs physically!
        causality_violation = {
            "timestamp": "2026-01-02T10:00:00Z",
            "available_at": "2026-01-02T08:00:00Z",
        }
        self.assertFalse(_is_proven_before_cutoff(causality_violation, CUTOFF))

        # Legitimate ordering: available_at >= timestamp
        legitimate = {
            "timestamp": "2026-01-02T10:00:00Z",
            "available_at": "2026-01-02T10:30:00Z",
        }
        self.assertTrue(_is_proven_before_cutoff(legitimate, CUTOFF))

    def test_measurement_postdating_cutoff_rejected(self):
        # Observation past cutoff
        late_obs = {"timestamp": LATE, "available_at": LATE}
        self.assertFalse(_is_proven_before_cutoff(late_obs, CUTOFF))

        # Observation before cutoff, but availability revision arrived past cutoff
        late_avail = {"timestamp": EARLY, "available_at": LATE}
        self.assertFalse(_is_proven_before_cutoff(late_avail, CUTOFF))

    def test_dynamic_soil_stripped_recursively_when_unproven(self):
        soil_context = {
            "clay_pct": 28.5,
            "sand_pct": 45.0,
            "soil_moisture": {"value": 0.32, "timestamp": LATE, "available_at": LATE},
            "root_zone_water": 0.28,  # missing timestamps
        }
        filtered = _strip_dynamic_recursive(soil_context, CUTOFF, is_proven=False)
        self.assertNotIn("soil_moisture", filtered)
        self.assertNotIn("root_zone_water", filtered)
        self.assertEqual(filtered["clay_pct"], 28.5)
        self.assertEqual(filtered["sand_pct"], 45.0)


class TestF02ST02TypedTimingContract(unittest.TestCase):
    """ST01-F02-02: Define typed timing for measurements, priors, forecasts and scenarios."""

    def test_timing_role_enumeration(self):
        self.assertEqual(TimingRole.from_value("forecast"), TimingRole.FORECAST)
        self.assertEqual(TimingRole.from_value("weather_forecast"), TimingRole.FORECAST)
        self.assertEqual(TimingRole.from_value("prior"), TimingRole.PRIOR)
        self.assertEqual(TimingRole.from_value("management_scenario"), TimingRole.MANAGEMENT_SCENARIO)
        self.assertEqual(TimingRole.from_value("plan"), TimingRole.MANAGEMENT_SCENARIO)
        self.assertEqual(TimingRole.from_value("observed"), TimingRole.MEASUREMENT)

    def test_temporal_timing_measurement_rules(self):
        t_valid = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        t_avail = datetime(2026, 1, 1, 10, 15, 0, tzinfo=timezone.utc)
        timing = TemporalTiming(role=TimingRole.MEASUREMENT, valid_time=t_valid, available_at=t_avail)

        ok, reason = timing.validate_cutoff(CUTOFF)
        self.assertTrue(ok)
        self.assertIsNone(reason)

        # Causality check: available before valid
        bad_timing = TemporalTiming(role=TimingRole.MEASUREMENT, valid_time=t_avail, available_at=t_valid)
        ok, reason = bad_timing.validate_cutoff(CUTOFF)
        self.assertFalse(ok)
        self.assertEqual(reason, "causality_violation_availability_precedes_observation")

        # Future measurement
        future_timing = TemporalTiming(
            role=TimingRole.MEASUREMENT,
            valid_time=datetime(2026, 1, 5, tzinfo=timezone.utc),
            available_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )
        ok, reason = future_timing.validate_cutoff(CUTOFF)
        self.assertFalse(ok)
        self.assertEqual(reason, "observation_time_postdates_cutoff")

    def test_earlier_issued_forecast_scenario_eligibility(self):
        """Earlier-issued future forecasts remain eligible as scenarios."""
        # Forecast issued on Jan 1 for target date Jan 5
        issued = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        target = datetime(2026, 1, 5, 0, 0, 0, tzinfo=timezone.utc)
        forecast_timing = TemporalTiming(
            role=TimingRole.FORECAST,
            valid_time=target,
            available_at=issued,
            issued_at=issued,
            is_forecast=True,
        )
        # Evaluated as of Jan 2: issued before cutoff, target is future -> ELIGIBLE SCENARIO
        ok, reason = forecast_timing.validate_cutoff(CUTOFF)
        self.assertTrue(ok)
        self.assertIsNone(reason)

        # Forecast issued after cutoff: Jan 3 issuance -> INELIGIBLE (future knowledge leakage)
        late_issued = datetime(2026, 1, 3, 6, 0, 0, tzinfo=timezone.utc)
        late_forecast = TemporalTiming(
            role=TimingRole.FORECAST,
            valid_time=target,
            available_at=late_issued,
            issued_at=late_issued,
            is_forecast=True,
        )
        ok, reason = late_forecast.validate_cutoff(CUTOFF)
        self.assertFalse(ok)
        self.assertEqual(reason, "forecast_issued_after_cutoff")

    def test_admission_ledger_categorizes_and_audits_cutoffs(self):
        records = [
            # Admitted measurement
            make_record(obs_time=EARLY, avail_time=EARLY, role="OBSERVED"),
            # Excluded: observation postdates cutoff
            make_record(obs_time=LATE, avail_time=LATE, role="OBSERVED", provider_product_id="prod-late-obs"),
            # Excluded: late revision of earlier observation
            make_record(obs_time=EARLY, avail_time=LATER_REVISION, role="OBSERVED", provider_product_id="prod-late-rev"),
            # Excluded: causality violation (avail before obs)
            make_record(obs_time="2026-01-02T10:00:00Z", avail_time="2026-01-01T10:00:00Z", provider_product_id="prod-causality"),
            # Admitted prospective forecast (issued before cutoff for future target)
            make_record(
                obs_time=LATE,
                avail_time=EARLY,
                issued_at=EARLY,
                role="FORECAST",
                is_forecast=True,
                provider_product_id="prod-forecast-ok",
            ),
        ]
        ledger = build_temporal_admission_ledger(records, cutoff=CUTOFF)

        self.assertEqual(ledger["input_count"], 5)
        self.assertEqual(ledger["quality_admitted_count"], 2)
        self.assertEqual(ledger["rejected_count"], 3)
        self.assertEqual(ledger["admitted_measurements_count"], 1)
        self.assertEqual(ledger["admitted_scenarios_count"], 1)
        self.assertEqual(ledger["quarantined_future_leakage_count"], 2)  # late obs + late rev
        self.assertEqual(ledger["quarantined_causality_violations_count"], 1)  # causality
        self.assertEqual(len(ledger["excluded_revisions"]), 3)


class TestF02ST03DecisionCutoffPropagation(unittest.TestCase):
    """ST01-F02-03: Propagate decision cutoff and reject unresolved eligibility across layers."""

    def test_historical_extractor_allows_earlier_issued_forecasts_as_scenarios(self):
        events = [
            # 1. Observation event: Jan 1 event, Jan 1 commit
            {
                "event_id": "ev-01",
                "plot_id": "plot_f02_extractor_test",
                "tenant_id": "tenant_f02",
                "namespace": "ns_f02",
                "event_type": "OBSERVATION",
                "observation_or_valid_time": "2026-01-01T12:00:00Z",
                "committed_at": "2026-01-01T12:30:00Z",
                "payload": {"ndvi": 0.65},
            },
            # 2. Prospective weather forecast: issued Jan 1 (kt) for target Jan 5 (et)
            {
                "event_id": "ev-02",
                "plot_id": "plot_f02_extractor_test",
                "tenant_id": "tenant_f02",
                "namespace": "ns_f02",
                "event_type": "WEATHER_FORECAST",
                "observation_or_valid_time": "2026-01-05T00:00:00Z",
                "committed_at": "2026-01-01T06:00:00Z",
                "payload": {"temp_max": 24.5, "is_forecast": True, "role": "FORECAST"},
            },
            # 3. Future measurement: Jan 10 event, Jan 10 commit
            {
                "event_id": "ev-03",
                "plot_id": "plot_f02_extractor_test",
                "tenant_id": "tenant_f02",
                "namespace": "ns_f02",
                "event_type": "OBSERVATION",
                "observation_or_valid_time": "2026-01-10T12:00:00Z",
                "committed_at": "2026-01-10T12:30:00Z",
                "payload": {"ndvi": 0.70},
            },
        ]
        service = MagicMock()
        service.load_all_events.return_value = events
        plot_id = "plot_f02_extractor_test"
        tenant_id = "tenant_f02"
        namespace = "ns_f02"

        extractor = BitemporalWorldlineExtractor(service)
        # Extraction query as of Jan 2:
        window = extractor.extract_training_window(
            plot_id=plot_id,
            start_event_time="2026-01-01T00:00:00Z",
            end_event_time="2026-01-07T00:00:00Z",
            as_of_knowledge_time="2026-01-02T00:00:00Z",
            tenant_id=tenant_id,
            namespace=namespace,
        )

        # Observations include Jan 1, but NOT Jan 10
        obs = window.get_observations()
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["observation_or_valid_time"], "2026-01-01T12:00:00Z")

        # Forecasts include the Jan 1 issued forecast for Jan 5!
        forecasts = window.get_forecasts()
        self.assertEqual(len(forecasts), 1)
        self.assertEqual(forecasts[0]["event_type"], "WEATHER_FORECAST")
        self.assertEqual(forecasts[0]["observation_or_valid_time"], "2026-01-05T00:00:00Z")

        # Zero future knowledge leakage
        self.assertFalse(window.has_future_leakage(datetime(2026, 1, 2, tzinfo=timezone.utc)))

    def test_layer3_weather_issuance_cutoff_filtering(self):
        """Weather revision available after issuance cutoff is rejected."""
        ts_cutoff = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

        # Valid weather available before issuance
        valid_w = {
            "date": "2026-01-02",
            "temp_max": 22.0,
            "temp_min": 12.0,
            "precipitation": 0.0,
            "available_at": "2026-01-02T06:00:00Z",
        }
        self.assertTrue(_is_weather_available_at_issuance(valid_w, ts_cutoff))

        # Weather revision that arrived on Jan 10 for Jan 2 date
        revised_w = {
            "date": "2026-01-02",
            "temp_max": 25.0,
            "temp_min": 14.0,
            "precipitation": 5.0,
            "available_at": "2026-01-10T12:00:00Z",
        }
        self.assertFalse(_is_weather_available_at_issuance(revised_w, ts_cutoff))

    def test_layer3_water_state_assimilator_cutoff_and_causality(self):
        """WaterStateAssimilator rejects observations with postdated availability or causality violation."""
        soil_prior = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=[10.0, 30.0, 60.0, 100.0],
            theta_profile=[0.25, 0.25, 0.25, 0.25],
            field_capacity_profile=[0.30, 0.30, 0.30, 0.30],
            wilting_point_profile=[0.15, 0.15, 0.15, 0.15],
            saturation_profile=[0.45, 0.45, 0.45, 0.45],
            residual_profile=[0.05, 0.05, 0.05, 0.05],
        )

        # Causality violation: available before timestamp
        bad_obs = SoilObservationVector(
            timestamp=datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            available_at=datetime(2026, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
            soil_probe_moisture_profile=[0.25, 0.25, 0.25, 0.25],
            observation_uncertainties={"soil_probe": 0.02},
        )
        post_soil, diag = WaterStateAssimilator.assimilate(soil_prior, bad_obs, cutoff=CUTOFF)
        self.assertEqual(diag.observations_assimilated_count, 0)
        self.assertEqual(diag.variance_reduction_fraction, 0.0)

        # Postdated observation
        late_obs = SoilObservationVector(
            timestamp=datetime(2026, 1, 5, tzinfo=timezone.utc),
            available_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            soil_probe_moisture_profile=[0.25, 0.25, 0.25, 0.25],
            observation_uncertainties={"soil_probe": 0.02},
        )
        post_soil, diag = WaterStateAssimilator.assimilate(soil_prior, late_obs, cutoff=CUTOFF)
        self.assertEqual(diag.observations_assimilated_count, 0)
        self.assertEqual(diag.variance_reduction_fraction, 0.0)


class TestF02ST04RecordingExcludedRevisionsAndArchiveIntegrity(unittest.TestCase):
    """ST01-F02-04: Record every excluded revision and force historical replays to use archived view."""

    def test_records_as_of_records_detailed_excluded_reasons(self):
        sink: List[Dict[str, Any]] = []
        records = [
            {"timestamp": EARLY, "available_at": EARLY, "ndvi": 0.5},
            {"timestamp": LATE, "available_at": LATE, "ndvi": 0.7},
            {"timestamp": EARLY, "available_at": LATER_REVISION, "ndvi": 0.6},
            {"timestamp": "2026-01-02T10:00:00Z", "available_at": "2026-01-01T10:00:00Z", "ndvi": 0.55},
            {"simulated": True, "ndvi": 0.8},
        ]
        kept = _records_as_of(records, CUTOFF, excluded_sink=sink)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(sink), 4)

        reasons = [item["reason"] for item in sink]
        self.assertIn("observation_postdates_cutoff", reasons)
        self.assertIn("availability_postdates_cutoff", reasons)
        self.assertIn("causality_violation_availability_precedes_observation", reasons)
        self.assertIn("rejected_dynamic_record_or_forecast", reasons)

    def test_estimate_resilient_plot_posterior_returns_f02_metadata(self):
        inp = SimpleNamespace(
            plot_timeseries=[
                {"timestamp": EARLY, "available_at": EARLY, "signal_type": "ndvi", "value": 0.6},
                {"timestamp": LATE, "available_at": LATE, "signal_type": "ndvi", "value": 0.8},
            ],
            weather_daily_series={
                "2026-01-01": {"timestamp": EARLY, "available_at": EARLY, "temp_max": 20.0},
                "2026-01-05": {"timestamp": LATE, "available_at": LATE, "temp_max": 25.0},
            },
            soil_context={"clay_pct": 25.0},
            crop_context={"crop_type": "wheat"},
            archive_posterior=None,
        )
        posterior = estimate_resilient_plot_posterior(inp, as_of=CUTOFF)

        self.assertIn("excluded_revisions", posterior)
        self.assertIn("excluded_revision_count", posterior)
        self.assertIn("decision_cutoff", posterior)
        self.assertIn("archived_knowledge_view_used", posterior)
        self.assertEqual(posterior["decision_cutoff"], CUTOFF.isoformat())
        self.assertGreaterEqual(posterior["excluded_revision_count"], 1)

    def test_postdated_archive_rejected_with_specific_reason(self):
        postdated_archive = {
            "contract_version": ARCHIVE_POSTERIOR_CONTRACT_VERSION,
            "last_update_date": "2026-01-10",
            "geometry_hash": "geom-42",
            "crop_context": {"crop_type": "wheat"},
            "historical_validation_status": "validated",
            "content_distinct_scene_ids": ["s1", "s2"],
            "state_means": {"root_zone_water": 0.30},
            "state_covariance": {"root_zone_water": 0.001},
            "state_support_ledger": {"root_zone_water": ["archive_seed"]},
            "archive_hash": "hash-20260110",
        }
        inp = SimpleNamespace(
            archive_posterior=postdated_archive,
            geometry_hash="geom-42",
            crop_context={"crop_type": "wheat"},
            soil_context={},
            plot_timeseries=[],
            weather_daily_series={},
        )
        posterior = estimate_resilient_plot_posterior(inp, as_of=CUTOFF)
        self.assertFalse(posterior["archive_contract_valid"])
        self.assertIn("archive_postdates_as_of_cutoff", posterior["archive_rejection_reasons"])
        self.assertFalse(posterior["archived_knowledge_view_used"])


class TestF02EndToEndAcceptance(unittest.TestCase):
    """ST01-F02-FA: Package F02 End-to-End Acceptance Sign-off."""

    def test_criteria_1_late_measurements_and_revisions_excluded(self):
        records = [
            make_record(obs_time=EARLY, avail_time=EARLY),
            make_record(obs_time=LATE, avail_time=LATE),
            make_record(obs_time=EARLY, avail_time=LATER_REVISION),
        ]
        ledger = build_temporal_admission_ledger(records, cutoff=CUTOFF)
        self.assertEqual(ledger["quality_admitted_count"], 1)
        self.assertEqual(ledger["rejected_count"], 2)

    def test_criteria_2_earlier_issued_forecasts_eligible_as_scenarios(self):
        forecast_rec = make_record(
            obs_time="2026-01-05T00:00:00Z",
            avail_time="2026-01-01T06:00:00Z",
            issued_at="2026-01-01T06:00:00Z",
            role="FORECAST",
            is_forecast=True,
        )
        self.assertTrue(is_admitted_temporal_record(forecast_rec, cutoff=CUTOFF))

    def test_criteria_3_replay_identifies_exact_available_versions(self):
        inp = SimpleNamespace(
            plot_timeseries=[
                make_record(obs_time=EARLY, avail_time=EARLY, signal_type="ndvi", value=0.62),
                make_record(obs_time=EARLY, avail_time=LATER_REVISION, signal_type="ndvi", value=0.75),
            ],
            weather_daily_series={},
            soil_context={},
            crop_context={},
            archive_posterior=None,
        )
        res = estimate_resilient_plot_posterior(inp, as_of=CUTOFF)
        # Replay at CUTOFF only consumed the EARLY version; LATER_REVISION is identified in excluded_revisions
        self.assertEqual(res["decision_cutoff"], CUTOFF.isoformat())
        excluded_reasons = [e["reason"] for e in res["excluded_revisions"]]
        self.assertIn("availability_postdates_cutoff", excluded_reasons)


if __name__ == "__main__":
    unittest.main()
