"""
Test suite verifying 2E01-2E04 corrective verifications from the October 2026 review.

- 2E01: Query failure and transport race do not allow duplicate START effects.
- 2E02: Legacy pre-receipt-map head backfills known publication generations on subsequent publication.
- 2E03: Complete quantile grammar: p1/1% = 0.01, p0.5/0.5% = 0.005, no false median.
- 2E04: Gust-only duplicate merge canonicalizes units to km/h idempotently regardless of row order.
"""

import asyncio
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.dispatcher import CommandDispatcher
from irrigation_runtime.safety import SafetyMonitor, SharedQuotaStore
from irrigation_runtime.schemas import (
    ActuatorCapabilities,
    ActuatorRegistration,
    ActuatorStatus,
    AutomationMode,
    CommandResult,
    CommandType,
    DriverProtocol,
    EventStatus,
    IrrigationCommand,
    IrrigationEvent,
    IrrigationSystemType,
    VendorId,
)
from layer8_prescriptive.scheduler import ConstraintScheduler
from layer8_prescriptive.schema import (
    ActionCard,
    ActionType,
    ConfidenceLevel,
    PrescriptiveEvidence,
    PriorityBreakdown,
    RateRange,
    ScheduleStatus,
)
from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService
from services.agribrain.world_model.forecast_archive import (
    ContractViolation,
    ForecastRecord,
    ImmutableForecastArchive,
    parse_quantile_level,
)


class MockFlakyActuator(IrrigationActuator):
    def __init__(self, device_id: str = "DEV-FLAKY-01", forced_status: ActuatorStatus = ActuatorStatus.ONLINE, fail_query: bool = False):
        reg = ActuatorRegistration(
            device_id=device_id,
            zone_ids=["ZONE-1"],
            plot_id="PLOT-1",
            farm_id="farm-1",
            protocol=DriverProtocol.MQTT,
            vendor=VendorId.GENERIC,
            model="SimValve",
            firmware_version="1.0.0",
            capabilities=ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=100.0,
                min_flow_rate_lpm=1.0,
                max_duration_minutes=120.0,
            ),
        )
        super().__init__(reg)
        self.forced_status = forced_status
        self.fail_query = fail_query
        self.commands_sent = []

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> bool:
        self._connected = False
        return True

    async def get_status(self) -> ActuatorStatus:
        if self.fail_query:
            raise RuntimeError("Controlled network/transport timeout")
        self._status = self.forced_status
        return self.forced_status

    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        self.commands_sent.append(command)
        if command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            self.forced_status = ActuatorStatus.EXECUTING
            self._status = ActuatorStatus.EXECUTING
        return CommandResult(
            command_id=f"CMD-{command.source_event_id}",
            device_id=command.device_id,
            success=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def emergency_stop(self) -> CommandResult:
        return CommandResult(
            command_id=f"ESTOP-{self.device_id}",
            device_id=self.device_id,
            success=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


class Test2E01ResourceHandoffAndQueryFailure(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    async def test_2e01_failed_query_with_existing_execution_refuses_second_start(self):
        """Companion 2E01 case: An unsuccessful status query cannot serve as positive idle evidence."""
        actuator_a = MockFlakyActuator("DEV-01", forced_status=ActuatorStatus.ONLINE)
        safety_a = SafetyMonitor()
        disp_a = CommandDispatcher(safety=safety_a)
        disp_a.register_actuator(actuator_a)

        ev_a = IrrigationEvent(
            event_id="EV-A",
            device_id="DEV-01",
            plot_id="PLOT-1",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.SEMI_AUTO,
            status=EventStatus.QUEUED,
            target_duration_minutes=10.0,
            target_volume_mm=10.0,
            target_flow_rate_lpm=5.0,
            effective_area_ha=1.0,
            zone_id="ZONE-1",
            scheduled_start=datetime.now(timezone.utc).isoformat(),
        )
        res_a = await disp_a.submit_event(ev_a)
        self.assertEqual(res_a.status, EventStatus.EXECUTING)
        self.assertEqual(len(actuator_a.commands_sent), 1)

        # Worker B starts with forced query exception
        actuator_b = MockFlakyActuator("DEV-01", forced_status=ActuatorStatus.UNKNOWN, fail_query=True)
        safety_b = SafetyMonitor()
        disp_b = CommandDispatcher(safety=safety_b)
        disp_b.register_actuator(actuator_b)

        ev_b = IrrigationEvent(
            event_id="EV-B",
            device_id="DEV-01",
            plot_id="PLOT-1",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.SEMI_AUTO,
            status=EventStatus.QUEUED,
            target_duration_minutes=10.0,
            target_volume_mm=10.0,
            target_flow_rate_lpm=5.0,
            effective_area_ha=1.0,
            zone_id="ZONE-1",
            scheduled_start=datetime.now(timezone.utc).isoformat(),
        )
        res_b = await disp_b.submit_event(ev_b)

        # B must be rejected, not admitted, and must send zero START commands
        self.assertIn(res_b.status, (EventStatus.STOP_REQUESTED, EventStatus.FAILED))
        self.assertEqual(len(actuator_b.commands_sent), 0)

        # Check SharedQuotaStore state: A remains active, B did not overwrite A
        rec_a = SharedQuotaStore.get_active_record("EV-A")
        self.assertIsNotNone(rec_a)
        self.assertEqual(rec_a["status"], "EXECUTING")

    def test_2e01_interleaved_query_before_executing_rejected_by_timestamp(self):
        """Primary 2E01 case: A query timestamp older than or equal to executing_ts cannot claim resource."""
        # 1. A claims resource at t=100.0
        now_ts = 100.0
        claimed, token_a = SharedQuotaStore.claim_resource(
            device_id="DEV-01",
            zone_id="ZONE-1",
            event_id="EV-A",
            live_executing=False,
            query_ts=now_ts,
        )
        self.assertTrue(claimed)

        # 2. B queries idle at t=100.5
        b_query_ts = 100.5

        # 3. A's transport completes send and transitions to EXECUTING at t=101.0
        SharedQuotaStore.update_status("EV-A", "EXECUTING")
        rec_a = SharedQuotaStore.get_active_record("EV-A")
        self.assertIn("executing_ts", rec_a)
        # Ensure executing_ts is newer than B's query_ts
        with SharedQuotaStore._lock():
            st = SharedQuotaStore._read_state()
            st["reservations"]["EV-A"]["executing_ts"] = 101.0
            SharedQuotaStore._write_state(st)

        # 4. B now attempts to claim using its query timestamp from t=100.5
        b_claimed, holding_id = SharedQuotaStore.claim_resource(
            device_id="DEV-01",
            zone_id="ZONE-1",
            event_id="EV-B",
            live_executing=False,
            query_ts=b_query_ts,
        )
        self.assertFalse(b_claimed)
        self.assertEqual(holding_id, "EV-A")


class Test2E02LegacyReceiptBackfill(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.service = CanonicalWorldlineService(root=Path(self.tmp_dir.name))

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_2e02_legacy_head_retains_publication_generation_after_independent_publish(self):
        """2E02: Pre-receipt-map legacy head backfills generation 5 for A2 when B publishes generation 6."""
        # Setup initial checkpoints
        self.service.save_hydraulic_checkpoint(plot_id="p1", checkpoint_id="A1", checkpoint_payload={"water_balance": 10.0}, tenant_id="t1", namespace="ns1", cycle_id="A")
        self.service.save_hydraulic_checkpoint(plot_id="p1", checkpoint_id="A2", checkpoint_payload={"water_balance": 15.0}, expected_predecessor_head="A1", tenant_id="t1", namespace="ns1", cycle_id="A")
        self.service.save_hydraulic_checkpoint(plot_id="p1", checkpoint_id="B1", checkpoint_payload={"water_balance": 20.0}, tenant_id="t1", namespace="ns1", cycle_id="B")
        self.service.save_hydraulic_checkpoint(plot_id="p1", checkpoint_id="B2", checkpoint_payload={"water_balance": 22.0}, expected_predecessor_head="B1", tenant_id="t1", namespace="ns1", cycle_id="B")
        b3 = self.service.save_hydraulic_checkpoint(plot_id="p1", checkpoint_id="B3", checkpoint_payload={"water_balance": 25.0}, expected_predecessor_head="B2", tenant_id="t1", namespace="ns1", cycle_id="B")

        # Now simulate legacy pre-receipt-map head shape:
        # Latest head is A2 (generation 5), but scoped_sequences and checkpoint_sequences fields are omitted
        head_path = self.service._hydraulic_head_path("p1", "t1", "ns1")
        modern_head = self.service._read(head_path)
        legacy_head = {k: v for k, v in modern_head.items() if k not in ("scoped_sequences", "checkpoint_sequences")}
        legacy_head["latest_checkpoint_id"] = "A2"
        legacy_head["head_hash"] = "A2"
        legacy_head["sequence"] = 5
        legacy_head["scoped_heads"] = {"A::default_geom": "A2", "B::default_geom": "B3"}
        self.service._atomic(head_path, legacy_head)

        # Verify A2 reads generation 5 via fallback
        a_before = self.service.load_latest_hydraulic_checkpoint("p1", cycle_id="A", tenant_id="t1", namespace="ns1")
        self.assertEqual(a_before["publication_generation"], 5)

        # Now independent B publishes B4 (sequence 6)
        b4 = self.service.save_hydraulic_checkpoint(plot_id="p1", checkpoint_id="B4", checkpoint_payload={"water_balance": 30.0}, expected_predecessor_head="B3", tenant_id="t1", namespace="ns1", cycle_id="B")
        self.assertEqual(b4["publication_generation"], 6)

        # A2 must still expose publication_generation = 5
        a_after = self.service.load_latest_hydraulic_checkpoint("p1", cycle_id="A", tenant_id="t1", namespace="ns1")
        self.assertEqual(a_after["publication_generation"], 5)
        self.assertEqual(a_after["sequence"], 5)

        # Fresh instance also reads 5
        restart_svc = CanonicalWorldlineService(root=Path(self.tmp_dir.name))
        a_restart = restart_svc.load_latest_hydraulic_checkpoint("p1", cycle_id="A", tenant_id="t1", namespace="ns1")
        self.assertEqual(a_restart["publication_generation"], 5)


class Test2E03QuantileGrammar(unittest.TestCase):
    def test_parse_quantile_level_semantics(self):
        """2E03: Uniform parsing: p1/1% = 0.01, p0.5/0.5% = 0.005, p50/50% = 0.5."""
        self.assertAlmostEqual(parse_quantile_level("p1"), 0.01)
        self.assertAlmostEqual(parse_quantile_level("1%"), 0.01)
        self.assertAlmostEqual(parse_quantile_level("p0.5"), 0.005)
        self.assertAlmostEqual(parse_quantile_level("0.5%"), 0.005)
        self.assertAlmostEqual(parse_quantile_level("p50"), 0.5)
        self.assertAlmostEqual(parse_quantile_level("50%"), 0.5)
        self.assertAlmostEqual(parse_quantile_level("0.5"), 0.5)
        self.assertAlmostEqual(parse_quantile_level("p100"), 1.0)
        self.assertAlmostEqual(parse_quantile_level("100%"), 1.0)
        self.assertAlmostEqual(parse_quantile_level("1.0"), 1.0)
        self.assertAlmostEqual(parse_quantile_level("p10"), 0.1)
        self.assertAlmostEqual(parse_quantile_level("p90"), 0.9)

    def test_p05_not_treated_as_median(self):
        """2E03: p0.5 must not be falsely picked as median (p50) when evaluating forecast RMSE."""
        tmp = tempfile.TemporaryDirectory()
        try:
            store = ImmutableForecastArchive(root=Path(tmp.name))
            now = datetime.now(timezone.utc)
            target = now + timedelta(days=1)
            record = ForecastRecord(
                forecast_id="FC-01",
                plot_id="PLOT-1",
                target_variable="soil_moisture_surface",
                issued_at_knowledge_time=now,
                target_epoch=target,
                horizon_days=1,
                predicted_quantiles={"p0.5": 0.05, "p10": 0.1, "p90": 0.9},
                predicted_mean=None,
                predicted_std=None,
                model_id="test-model",
                model_version="1.0.0",
                calibration_version="1.0.0",
            )
            store.store_forecast(record)
            eval_res = store.evaluate_forecast("FC-01", observed_value=0.5, verifying_evidence_ids=["ev-test-1"], evaluated_at=target + timedelta(hours=1))
            # Since p50 is missing and predicted_mean is None, rmse must be None, NOT computed against p0.5
            self.assertIsNone(eval_res.rmse)
            self.assertIsNotNone(eval_res.crps)
        finally:
            tmp.cleanup()


class Test2E04GustUnitIdempotence(unittest.TestCase):
    def test_gust_only_duplicate_merge_order_invariant(self):
        """2E04: Equivalent gust-only 2 m/s and 7.2 km/h duplicates must merge to km/h in either order."""
        scheduler = ConstraintScheduler()

        # m/s first
        forecast_mps_first = [
            {"date": "2026-10-20", "wind_gust": 2.0, "unit": "m/s", "temp_max": 25.0, "temp_min": 15.0, "precip_mm": 0.0},
            {"date": "2026-10-20", "wind_gust": 7.2, "unit": "km/h", "temp_max": 25.0, "temp_min": 15.0, "precip_mm": 0.0},
        ]
        # km/h first
        forecast_kmh_first = [
            {"date": "2026-10-20", "wind_gust": 7.2, "unit": "km/h", "temp_max": 25.0, "temp_min": 15.0, "precip_mm": 0.0},
            {"date": "2026-10-20", "wind_gust": 2.0, "unit": "m/s", "temp_max": 25.0, "temp_min": 15.0, "precip_mm": 0.0},
        ]

        card = ActionCard(
            action_id="CARD_SPRAY_TEST",
            action_type=ActionType.SPRAY,
            priority_score=0.8,
            priority_breakdown=PriorityBreakdown(0.8, 0.7, 0.2, 0.3, 0.9),
            zone_targets=["zone_1"],
            zone_allocation={"zone_1": 1.0},
            rate=RateRange(recommended=2.0, min_safe=1.0, max_safe=5.0, unit="L/ha"),
            evidence=[PrescriptiveEvidence("L5", "threat", "REF_PEST", 0.8, "Pest", source_type="sensor")],
            confidence=ConfidenceLevel.HIGH,
            explain="Spray action",
        )

        base_date = datetime(2026, 10, 19, tzinfo=timezone.utc)
        sched_mps = scheduler.schedule_actions([card], forecast_mps_first, base_date)
        sched_kmh = scheduler.schedule_actions([card], forecast_kmh_first, base_date)

        # Both schedules must yield identical feasibility (both confirmed/feasible at 7.2 km/h <= 15.0 km/h)
        self.assertEqual(len(sched_mps), len(sched_kmh))
        self.assertEqual(sched_mps[0].status, ScheduleStatus.CONFIRMED)
        self.assertEqual(sched_kmh[0].status, ScheduleStatus.CONFIRMED)


if __name__ == "__main__":
    unittest.main()
