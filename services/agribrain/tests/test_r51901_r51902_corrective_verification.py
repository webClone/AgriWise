"""
Corrective Verification Test Suite for Findings R51901 and R51902 (Candidate 51932bf review)

Covers:
- R51901 (P1): Full A/B/poll/stop/C lifecycle.
  Unsent contender B observing active operation A is refused pre-transport without transport,
  cleanly transitions to FAILED (not STOP_REQUESTED), releases all quota/store reservations,
  and polling B does not disrupt A. After A is positively stopped, fresh worker C submits,
  acquires the resource without false-intent obstruction, and executes normally.
- R51902 (P2): Non-finite (+Inf, NaN) root support domain validation.
  Validates that infinite or non-finite root depths are rejected as unsupported
  across EnvironmentalLossEngine (_leaching_burns, compute_all_losses),
  WaterState.to_layer4_boundary_receipt, and run_layer4_standalone,
  failing closed with UNAVAILABLE_UNSUPPORTED_ROOT, is_root_supported=False,
  zero excluded leaching debit in the N budget, blocked fertilizer prescriptions,
  and health/confidence <= 0.10.
"""

import asyncio
from datetime import datetime, timezone
import math
import unittest

from irrigation_runtime.dispatcher import CommandDispatcher
from irrigation_runtime.safety import SafetyMonitor, SharedQuotaStore
from irrigation_runtime.schemas import (
    ActuatorCapabilities, ActuatorRegistration, ActuatorStatus,
    AutomationMode, CommandResult, CommandType, DriverProtocol,
    EventStatus, IrrigationCommand, IrrigationEvent, IrrigationSystemType,
    VendorId
)
from irrigation_runtime.actuator import IrrigationActuator

import dataclasses
from layer3_water.contracts.water_state import (
    WaterState, RootZoneWaterState, WaterFluxState,
    PotentialWaterFlux, ActualWaterFlux,
)
from layer3_water.contracts.state_factory import WaterStateFactory
from layer4_nutrients.schema import Nutrient, SoilWaterBalanceOutput
from layer4_nutrients.runner import run_layer4_standalone
from layer4_nutrients.environmental_losses.engine import EnvironmentalLossEngine, LossPathway


class MockTrackingActuator(IrrigationActuator):
    """Mock actuator tracking START/STOP invocations and simulated execution state."""
    def __init__(self, device_id: str = "DEV-01"):
        reg = ActuatorRegistration(
            device_id=device_id,
            zone_ids=["ZONE-1"],
            plot_id="plot_1",
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
        self.commands_sent = []
        self._status = ActuatorStatus.ONLINE
        self.starts = 0
        self.stops = 0

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> bool:
        self._connected = False
        return True

    async def get_status(self) -> ActuatorStatus:
        return self._status

    async def emergency_stop(self) -> CommandResult:
        self.stops += 1
        self._status = ActuatorStatus.ONLINE
        return CommandResult(
            command_id=f"cmd-estop-{len(self.commands_sent)}",
            device_id=self.device_id,
            success=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        self.commands_sent.append(command)
        if command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            self.starts += 1
            self._status = ActuatorStatus.EXECUTING
        elif command.command_type in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP):
            self.stops += 1
            self._status = ActuatorStatus.ONLINE
        return CommandResult(
            command_id=f"CMD-{command.source_event_id}",
            device_id=command.device_id,
            success=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


class TestR51901UnsentContenderRefusalLifecycle(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    def _make_event(self, event_id: str, device_id: str = "DEV-01", zone_id: str = "ZONE-1") -> IrrigationEvent:
        return IrrigationEvent(
            event_id=event_id,
            device_id=device_id,
            plot_id="plot_1",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.SEMI_AUTO,
            status=EventStatus.QUEUED,
            target_duration_minutes=15.0,
            target_volume_mm=8.0,
            target_flow_rate_lpm=5.0,
            effective_area_ha=1.0,
            zone_id=zone_id,
            scheduled_start=datetime.now(timezone.utc).isoformat(),
        )

    async def test_r51901_a_start_b_refused_b_poll_a_stop_c_executes_lifecycle(self):
        """Replay exact lifecycle:
        1. A submits normally -> A EXECUTING, 1 START(A), active owner and reservation.
        2. Fresh B submits while A runs -> preflight identifies foreign live owner A.
           B is refused pre-transport, transitions to FAILED (NOT STOP_REQUESTED),
           quota/store reservation released. Hardware starts remain 1.
        3. B polls execution status while A is still live -> A remains EXECUTING; no STOP.
        4. A's owner cancels A -> Positive STOP(A), A CANCELLED and tracking cleared.
        5. Fresh C submits after A stopped -> C is NOT blocked by B's phantom reservation;
           C acquires claim and transitions to EXECUTING (1 START to hardware, total 2).
        """
        actuator = MockTrackingActuator("DEV-01")

        disp_a = CommandDispatcher(safety=SafetyMonitor())
        disp_a.register_actuator(actuator)

        disp_b = CommandDispatcher(safety=SafetyMonitor())
        disp_b.register_actuator(actuator)

        disp_c = CommandDispatcher(safety=SafetyMonitor())
        disp_c.register_actuator(actuator)

        # 1. Worker A submits normally
        ev_a = self._make_event("EV-A")
        res_a = await disp_a.submit_event(ev_a)
        self.assertEqual(res_a.status, EventStatus.EXECUTING)
        self.assertEqual(actuator.starts, 1)
        self.assertEqual(actuator.stops, 0)
        self.assertEqual(await actuator.get_status(), ActuatorStatus.EXECUTING)

        rec_a = SharedQuotaStore.get_active_record("EV-A")
        self.assertIsNotNone(rec_a)
        self.assertEqual(rec_a["status"], "EXECUTING")

        # 2. Fresh Worker B submits while A is EXECUTING
        ev_b = self._make_event("EV-B")
        res_b = await disp_b.submit_event(ev_b)

        # B must transition to FAILED, NOT STOP_REQUESTED!
        self.assertEqual(res_b.status, EventStatus.FAILED)
        self.assertIn("pre-transport refused without transport", res_b.error_message)

        # No duplicate START sent to hardware
        self.assertEqual(actuator.starts, 1)
        self.assertEqual(actuator.stops, 0)

        # B's quota and store reservation must be released (no retained 8 mm exposure)
        rec_b = SharedQuotaStore.get_active_record("EV-B")
        self.assertIsNone(rec_b, "B's quota reservation must be released upon pre-transport refusal")

        # Local dispatcher active events must not retain B
        self.assertNotIn("EV-B", disp_b.get_active_events())

        # 3. B polls while A is still live: A must remain EXECUTING; no foreign-owner STOP
        poll_b = await disp_b.check_execution_status(ev_b.event_id)
        self.assertEqual(poll_b.status, EventStatus.FAILED)
        self.assertEqual(actuator.starts, 1)
        self.assertEqual(actuator.stops, 0)
        self.assertEqual(await actuator.get_status(), ActuatorStatus.EXECUTING)

        # 4. A is cancelled (positive stop)
        cancel_res = await disp_a.cancel_event("EV-A", reason="Manual operator stop")
        self.assertTrue(cancel_res)
        self.assertEqual(ev_a.status, EventStatus.CANCELLED)
        self.assertEqual(actuator.stops, 1)
        self.assertEqual(await actuator.get_status(), ActuatorStatus.ONLINE)

        # 5. Fresh Worker C submits after A has positively stopped
        ev_c = self._make_event("EV-C")
        res_c = await disp_c.submit_event(ev_c)

        # C must NOT be blocked by B's phantom reservation; C acquires and EXECUTING
        self.assertEqual(res_c.status, EventStatus.EXECUTING)
        self.assertEqual(actuator.starts, 2, "Caller C must have dispatched exactly one START to hardware")
        self.assertEqual(actuator.stops, 1, "No extraneous STOPs should have occurred")

        rec_c = SharedQuotaStore.get_active_record("EV-C")
        self.assertIsNotNone(rec_c)
        self.assertEqual(rec_c["status"], "EXECUTING")

        # Clean shutdown of C
        await disp_c.cancel_event("EV-C", reason="Test teardown")


class TestR51902FiniteRootSupportValidation(unittest.TestCase):
    """Tests for non-finite root depth rejection in environmental losses and L4 boundaries."""

    def setUp(self):
        self.loss_engine = EnvironmentalLossEngine()

    def test_r51902_environmental_losses_rejects_infinite_root_depth(self):
        """EnvironmentalLossEngine._leaching_burns and compute_all_losses reject float('inf')."""
        # Direct _leaching_burns with infinite root depth
        leach_inf = self.loss_engine._leaching_burns(
            n_applied=100.0,
            drainage_mm=20.0,
            theta_fc=0.30,
            root_depth_cm=float("inf"),
            clay_pct=20.0,
        )
        self.assertEqual(leach_inf.availability, "UNAVAILABLE_UNSUPPORTED_ROOT")
        self.assertFalse(leach_inf.is_supported)
        self.assertEqual(leach_inf.risk_class, "UNAVAILABLE")
        self.assertEqual(leach_inf.loss_kg_ha, 0.0)

        # compute_all_losses with infinite root depth
        res_inf = self.loss_engine.compute_all_losses(
            n_applied_kg_ha=100.0,
            soil_ph=6.5,
            clay_pct=20.0,
            organic_matter_pct=2.0,
            temperature_c=22.0,
            total_drainage_mm=20.0,
            soil_moisture_vwc=0.25,
            theta_fc=0.30,
            theta_sat=0.45,
            root_depth_cm=float("inf"),
            slope_pct=2.0,
            crop_cover_fraction=0.8,
        )
        self.assertEqual(res_inf.availability, "UNAVAILABLE_UNSUPPORTED_ROOT")
        self.assertFalse(res_inf.is_root_supported)
        self.assertEqual(res_inf.leaching.availability, "UNAVAILABLE_UNSUPPORTED_ROOT")
        self.assertFalse(res_inf.leaching.is_supported)
        self.assertEqual(res_inf.denitrification.availability, "UNAVAILABLE_UNSUPPORTED_ROOT")
        self.assertFalse(res_inf.denitrification.is_supported)
        self.assertIn("Root boundary is unsupported", res_inf.notes)

    def test_r51902_environmental_losses_rejects_nan_and_boolean_root_depth(self):
        """EnvironmentalLossEngine rejects NaN, None, and boolean values."""
        for malformed in (float("nan"), -10.0, 0.0, True, False, None):
            res = self.loss_engine.compute_all_losses(
                n_applied_kg_ha=50.0,
                soil_ph=6.5,
                clay_pct=20.0,
                organic_matter_pct=2.0,
                temperature_c=20.0,
                total_drainage_mm=15.0,
                soil_moisture_vwc=0.25,
                theta_fc=0.30,
                theta_sat=0.45,
                root_depth_cm=malformed,
            )
            self.assertEqual(res.availability, "UNAVAILABLE_UNSUPPORTED_ROOT", f"Failed for {malformed}")
            self.assertFalse(res.is_root_supported)

    def test_r51902_water_state_boundary_receipt_rejects_infinite_root_depth(self):
        """WaterState.to_layer4_boundary_receipt treats infinite root depth as degraded with 0 depth."""
        soil_state = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=[10.0, 30.0, 60.0],
            theta_profile=[0.25, 0.25, 0.25],
            field_capacity_profile=[0.30, 0.30, 0.30],
            wilting_point_profile=[0.15, 0.15, 0.15],
            saturation_profile=[0.45, 0.45, 0.45],
            residual_profile=[0.04, 0.04, 0.04],
        )
        root_zone = WaterStateFactory.create_root_zone_water_state(
            root_depth_m=0.6,
            layer_depths_cm=soil_state.layer_depths_cm,
            theta_profile=soil_state.theta_profile,
            field_capacity_profile=soil_state.field_capacity_profile,
            wilting_point_profile=soil_state.wilting_point_profile,
            saturation_profile=soil_state.saturation_profile,
        )
        # Inject non-finite root support
        root_zone = dataclasses.replace(root_zone, supported_root_depth_cm=float("inf"))

        ws = WaterStateFactory.create_water_state(
            plot_id="plot_1",
            timestamp=datetime.now(timezone.utc),
            soil_water=soil_state,
            fluxes=WaterFluxState(
                potential=PotentialWaterFlux(et0_mm=4.0, kcb=1.0, ke=0.2),
                actual=ActualWaterFlux(ks=1.0, precipitation_mm=0.0, irrigation_mm=0.0, deep_drainage_mm=20.0, runoff_mm=0.0),
            ),
            root_zone=root_zone,
            data_health_score=1.0,
        )

        receipt = ws.to_layer4_boundary_receipt()
        self.assertTrue(receipt.is_degraded)
        self.assertEqual(receipt.supported_root_depth_cm, 0.0)
        self.assertEqual(receipt.root_support_coverage_fraction, 0.0)

    def test_r51902_standalone_layer4_with_infinite_root_depth_fails_closed(self):
        """Standalone L4 with infinite root depth fails closed with zero loss debit and blocked prescriptions."""
        soil_state = WaterStateFactory.create_soil_water_state(
            layer_depths_cm=[10.0, 30.0, 60.0],
            theta_profile=[0.25, 0.25, 0.25],
            field_capacity_profile=[0.30, 0.30, 0.30],
            wilting_point_profile=[0.15, 0.15, 0.15],
            saturation_profile=[0.45, 0.45, 0.45],
            residual_profile=[0.04, 0.04, 0.04],
        )
        root_zone = WaterStateFactory.create_root_zone_water_state(
            root_depth_m=0.6,
            layer_depths_cm=soil_state.layer_depths_cm,
            theta_profile=soil_state.theta_profile,
            field_capacity_profile=soil_state.field_capacity_profile,
            wilting_point_profile=soil_state.wilting_point_profile,
            saturation_profile=soil_state.saturation_profile,
        )
        # Injected non-finite root support
        root_zone = dataclasses.replace(root_zone, supported_root_depth_cm=float("inf"))

        ws = WaterStateFactory.create_water_state(
            plot_id="plot_1",
            timestamp=datetime.now(timezone.utc),
            soil_water=soil_state,
            fluxes=WaterFluxState(
                potential=PotentialWaterFlux(et0_mm=4.0, kcb=1.0, ke=0.2),
                actual=ActualWaterFlux(ks=1.0, precipitation_mm=0.0, irrigation_mm=0.0, deep_drainage_mm=20.0, runoff_mm=0.0),
            ),
            root_zone=root_zone,
            data_health_score=1.0,
        )

        class MockL3Decision:
            canonical_water_state = ws

        weather = [{"date": "2026-08-20", "temp_avg_c": 22.0, "rain_mm": 0.0, "et0": 4.0, "t_max": 25.0, "t_min": 15.0}]
        out = run_layer4_standalone(
            l3_decision=MockL3Decision(),
            crop_type="maize",
            stages=["V6"],
            soil_props={"ph": 6.8, "clay_pct": 22.0, "organic_matter_pct": 2.5, "nitrogen_ppm": 2.0, "phosphorus_ppm": 2.0, "potassium_ppm": 10.0},
            daily_weather=weather,
            ndvi=0.6,
        )

        # 1. Environmental losses must be UNAVAILABLE_UNSUPPORTED_ROOT
        self.assertEqual(out.environmental_losses.availability, "UNAVAILABLE_UNSUPPORTED_ROOT")
        self.assertFalse(out.environmental_losses.is_root_supported)
        self.assertEqual(out.environmental_losses.leaching.availability, "UNAVAILABLE_UNSUPPORTED_ROOT")
        self.assertFalse(out.environmental_losses.leaching.is_supported)

        # 2. Nitrogen budget must exclude unsupported leaching debit
        budget_n = out.nutrient_budgets.get(Nutrient.N)
        self.assertIsNotNone(budget_n)
        self.assertEqual(budget_n.leaching_loss, 0.0)
        self.assertEqual(budget_n.denitrification_loss, 0.0)

        # 3. Prescriptions must be blocked due to unsupported root boundary
        self.assertTrue(len(out.prescriptions) > 0)
        for rx in out.prescriptions:
            self.assertFalse(rx.is_allowed, f"Prescription for {rx.nutrient} should be blocked")
            self.assertIn("unsupported_root_boundary", rx.blocked_reason)

        # 4. Confidence / decision reliability must be penalized <= 0.10
        self.assertLessEqual(out.quality_metrics.decision_reliability, 0.10)
        self.assertLessEqual(out.nutrient_states[Nutrient.N].confidence, 0.10)


if __name__ == "__main__":
    unittest.main()
