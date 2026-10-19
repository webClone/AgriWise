"""
Corrective Verification Test Suite for Findings R47801-R47804 (Candidate 4788dac review)

Covers:
- R47801 (P1): Distinct phases for quota admission (ADMITTED), resource preparation (STARTING),
  and entered transport (DISPATCHING); unsent contender refused with quota cleanup and zero false stop intent;
  subsequent third caller C progresses normally.
- R47802 (P2): Idempotent same-event claim_resource preserves in-flight DISPATCHING phase, token,
  and non-expiring transport protection after 31s injected time.
- R47803 (P2): Unsupported root boundary marks water-dependent losses (leaching, denitrification) as UNAVAILABLE
  and prevents fictitious drainage debits into nitrogen budget.
- R47804 (P2): Standalone L4 with missing canonical water and missing weather fails closed with degraded health,
  missing driver flags, zero supported depth, and blocked prescriptions.
"""

import asyncio
from datetime import datetime, timezone
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from irrigation_runtime.dispatcher import CommandDispatcher
from irrigation_runtime.safety import SafetyMonitor, SharedQuotaStore
from irrigation_runtime.schemas import (
    ActuatorCapabilities, ActuatorRegistration, ActuatorStatus,
    AutomationMode, CommandResult, CommandType, DriverProtocol,
    EventStatus, IrrigationCommand, IrrigationEvent, IrrigationSystemType,
    VendorId
)
from irrigation_runtime.actuator import IrrigationActuator

from layer4_nutrients.schema import Nutrient
from layer4_nutrients.runner import run_layer4_standalone
from layer4_nutrients.environmental_losses.engine import EnvironmentalLossEngine


class MockSimpleActuator(IrrigationActuator):
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

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> bool:
        self._connected = False
        return True

    async def get_status(self) -> ActuatorStatus:
        return self._status

    async def emergency_stop(self) -> CommandResult:
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
            self._status = ActuatorStatus.EXECUTING
        elif command.command_type in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP):
            self._status = ActuatorStatus.ONLINE
        return CommandResult(
            command_id=f"CMD-{command.source_event_id}",
            device_id=command.device_id,
            success=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


class TestR47801AdmissionLifecycle(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    def test_r47801_quota_reservation_creates_admitted_not_dispatching(self):
        """Quota admission records status=ADMITTED, not DISPATCHING."""
        vio = SharedQuotaStore.atomic_check_and_reserve(
            plot_id="plot_1",
            requested_volume_mm=10.0,
            event_id="EV-ADM-01",
            device_id="DEV-01",
            zone_id="ZONE-1",
            duration_minutes=10.0,
        )
        self.assertIsNone(vio)

        rec = SharedQuotaStore.get_active_record("EV-ADM-01")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["status"], "ADMITTED")
        self.assertFalse(rec.get("claimed", False))
        self.assertIsNone(rec.get("first_dispatched_at"))

    async def test_r47801_concurrent_submissions_one_executes_one_refused_no_false_stop_intent(self):
        """Two submissions to same device: one progresses to EXECUTING, loser is refused without false STOP_REQUESTED, and caller C succeeds."""
        actuator = MockSimpleActuator("DEV-01")
        safety_a = SafetyMonitor()
        disp_a = CommandDispatcher(safety=safety_a)
        disp_a.register_actuator(actuator)

        safety_b = SafetyMonitor()
        disp_b = CommandDispatcher(safety=safety_b)
        disp_b.register_actuator(actuator)

        ev_a = IrrigationEvent(
            event_id="EV-A",
            device_id="DEV-01",
            plot_id="plot_1",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.SEMI_AUTO,
            status=EventStatus.QUEUED,
            target_duration_minutes=15.0,
            target_volume_mm=10.0,
            target_flow_rate_lpm=5.0,
            effective_area_ha=1.0,
            zone_id="ZONE-1",
            scheduled_start=datetime.now(timezone.utc).isoformat(),
        )

        ev_b = IrrigationEvent(
            event_id="EV-B",
            device_id="DEV-01",
            plot_id="plot_1",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.SEMI_AUTO,
            status=EventStatus.QUEUED,
            target_duration_minutes=15.0,
            target_volume_mm=10.0,
            target_flow_rate_lpm=5.0,
            effective_area_ha=1.0,
            zone_id="ZONE-1",
            scheduled_start=datetime.now(timezone.utc).isoformat(),
        )

        # Worker A acquires resource claim while device is ONLINE
        claimed_a, token_a = SharedQuotaStore.claim_resource("DEV-01", "ZONE-1", "EV-A")
        self.assertTrue(claimed_a)

        # Worker B submits to the same idle device (actuator is ONLINE):
        # Truthfully observes ONLINE, but is refused pre-transport by claim_resource
        res_b = await disp_b.submit_event(ev_b)
        # B must be cleanly refused with FAILED, NOT STOP_REQUESTED!
        self.assertEqual(res_b.status, EventStatus.FAILED)
        self.assertIn("pre-transport refused without transport", res_b.error_message)

        # Check store: B must NOT have left STOP_REQUESTED intent in store
        rec_b = SharedQuotaStore.get_active_record("EV-B")
        self.assertIsNone(rec_b, "B's quota reservation must be released upon pre-transport refusal")

        # A completes normally and releases claim
        actuator._status = ActuatorStatus.ONLINE
        SharedQuotaStore.update_status("EV-A", "COMPLETED")
        SharedQuotaStore.release_resource_claim("DEV-01", "ZONE-1", "EV-A")

        # Third worker C submits ordinarily
        safety_c = SafetyMonitor()
        disp_c = CommandDispatcher(safety=safety_c)
        disp_c.register_actuator(actuator)

        ev_c = IrrigationEvent(
            event_id="EV-C",
            device_id="DEV-01",
            plot_id="plot_1",
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.SEMI_AUTO,
            status=EventStatus.QUEUED,
            target_duration_minutes=15.0,
            target_volume_mm=10.0,
            target_flow_rate_lpm=5.0,
            effective_area_ha=1.0,
            zone_id="ZONE-1",
            scheduled_start=datetime.now(timezone.utc).isoformat(),
        )
        res_c = await disp_c.submit_event(ev_c)
        # C must succeed and NOT stall!
        self.assertEqual(res_c.status, EventStatus.EXECUTING)


class TestR47802IdempotentSameEventClaim(unittest.TestCase):
    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    def test_r47802_same_event_claim_preserves_dispatching_and_token(self):
        """Calling claim_resource again for an event already in DISPATCHING preserves phase and in-flight protection."""
        # 1. Admit and claim for EV-A
        claimed, token_1 = SharedQuotaStore.claim_resource(
            device_id="DEV-01",
            zone_id="ZONE-1",
            event_id="EV-A",
        )
        self.assertTrue(claimed)

        # 2. Transition EV-A to DISPATCHING
        ok = SharedQuotaStore.transition_to_dispatching("EV-A", token_1, "DEV-01", "ZONE-1")
        self.assertTrue(ok)
        rec_before = SharedQuotaStore.get_active_record("EV-A")
        self.assertEqual(rec_before["status"], "DISPATCHING")

        # 3. Call claim_resource AGAIN for same event EV-A
        claimed_again, token_2 = SharedQuotaStore.claim_resource(
            device_id="DEV-01",
            zone_id="ZONE-1",
            event_id="EV-A",
        )
        self.assertTrue(claimed_again)
        self.assertEqual(token_1, token_2, "Token must be preserved idempotently")

        rec_after = SharedQuotaStore.get_active_record("EV-A")
        self.assertEqual(rec_after["status"], "DISPATCHING", "Status must NOT be demoted to STARTING")

        # 4. Simulate 31 seconds elapsed
        # Worker B attempts claim_resource
        with SharedQuotaStore._lock():
            st = SharedQuotaStore._read_state()
            # If it were demoted to STARTING, starting_ts would expire after 30s
            st["reservations"]["EV-A"]["starting_ts"] = time.time() - 31.0
            SharedQuotaStore._write_state(st)

        b_claimed, holding_id = SharedQuotaStore.claim_resource(
            device_id="DEV-01",
            zone_id="ZONE-1",
            event_id="EV-B",
        )
        # Because EV-A is in DISPATCHING, B must be refused!
        self.assertFalse(b_claimed)
        self.assertEqual(holding_id, "EV-A")


class TestR47803UnsupportedRootDomainLosses(unittest.TestCase):
    def test_r47803_environmental_losses_unavailable_when_root_depth_zero(self):
        """When root depth is 0.0, leaching and denitrification are marked UNAVAILABLE with 0.0 loss."""
        engine = EnvironmentalLossEngine()
        res = engine.compute_all_losses(
            n_applied_kg_ha=180.0,
            root_depth_cm=0.0,
            total_drainage_mm=20.0,  # Explicit drainage declared on unsupported domain
            soil_moisture_vwc=0.0,
        )

        self.assertEqual(res.leaching.loss_kg_ha, 0.0)
        self.assertEqual(res.leaching.risk_class, "UNAVAILABLE")
        self.assertEqual(res.leaching.availability, "UNAVAILABLE_UNSUPPORTED_ROOT")

        self.assertEqual(res.denitrification.loss_kg_ha, 0.0)
        self.assertEqual(res.denitrification.risk_class, "UNAVAILABLE")
        self.assertEqual(res.denitrification.availability, "UNAVAILABLE_UNSUPPORTED_ROOT")

        self.assertEqual(res.availability, "UNAVAILABLE_UNSUPPORTED_ROOT")
        self.assertFalse(res.is_root_supported)
        self.assertIn("Root boundary is unsupported", res.notes)

    def test_r47803_full_l4_nitrogen_budget_excludes_unsupported_drainage_loss(self):
        """Full L4 does not debit fictitious 104.4 kg/ha leaching loss into N budget on unsupported root boundary."""
        from layer3_water.contracts.assimilation_state import Layer3ToLayer4BoundaryReceipt
        from layer3_water.contracts.state_factory import WaterStateFactory
        from layer3_water.contracts.water_state import WaterFluxState, PotentialWaterFlux, ActualWaterFlux

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
            layer_depths_cm=[10.0, 30.0, 60.0],
            theta_profile=[0.25, 0.25, 0.25],
            field_capacity_profile=[0.30, 0.30, 0.30],
            wilting_point_profile=[0.15, 0.15, 0.15],
        )
        water_state = WaterStateFactory.create_water_state(
            plot_id="plot_1",
            timestamp=datetime.now(timezone.utc),
            soil_water=soil_state,
            fluxes=WaterFluxState(
                potential=PotentialWaterFlux(et0_mm=4.0, kcb=1.0, ke=0.2),
                actual=ActualWaterFlux(ks=1.0, precipitation_mm=0.0, irrigation_mm=0.0, deep_drainage_mm=20.0, runoff_mm=0.0),
            ),
            root_zone=root_zone,
            data_health_score=0.8,
        )

        zero_receipt = Layer3ToLayer4BoundaryReceipt(
            plot_id="plot_1",
            timestamp=datetime.now(timezone.utc),
            stress_factor_ks=1.0,
            transpiration_deficit_mm=0.0,
            transpiration_deficit_sigma_mm=0.0,
            total_available_water_mm=0.0,
            readily_available_water_mm=0.0,
            root_zone_depletion_mm=0.0,
            water_availability_ratio=0.0,
            supported_root_depth_cm=0.0,
            root_zone_storage_mm=0.0,
            theta_fc_root=0.30,
            theta_wp_root=0.15,
            theta_sat_root=0.45,
            deep_drainage_mm=20.0,
            mass_conserved=True,
            water_closure_error_mm=0.0,
            is_degraded=True,
            requested_root_depth_cm=60.0,
            root_support_coverage_fraction=0.0,
        )

        class MockCanonicalWater:
            def __init__(self, real_ws, receipt):
                self._real = real_ws
                self.root_zone = real_ws.root_zone
                self.soil_water = real_ws.soil_water
                self.fluxes = real_ws.fluxes
                self._receipt = receipt
            def to_layer4_boundary_receipt(self):
                return self._receipt
            def __getattr__(self, item):
                return getattr(self._real, item)

        class MockL3Decision:
            canonical_water_state = MockCanonicalWater(water_state, zero_receipt)

        weather = [{"date": "2026-08-20", "temp_avg_c": 22.0, "rain_mm": 0.0, "et0": 4.0, "t_max": 25.0, "t_min": 15.0}]
        l4_out = run_layer4_standalone(
            l3_decision=MockL3Decision(),
            crop_type="maize",
            stages=["V6"],
            soil_props={"nitrogen_ppm": 2.0, "phosphorus_ppm": 2.0, "potassium_ppm": 10.0},
            daily_weather=weather,
            ndvi=0.6,
        )

        n_budget = l4_out.nutrient_budgets[Nutrient.N]
        # In the presence of supported_root_depth_cm=0.0, leaching loss in budget must be 0.0, not 104.4!
        self.assertEqual(n_budget.leaching_loss, 0.0)
        self.assertEqual(n_budget.denitrification_loss, 0.0)


class TestR47804MissingCanonicalWaterAndWeather(unittest.TestCase):
    def test_r47804_missing_canonical_water_and_weather_fails_closed(self):
        """Standalone L4 with l3_decision=None and daily_weather=[] fails closed with degraded health and blocked prescriptions."""
        l4_out = run_layer4_standalone(
            l3_decision=None,
            daily_weather=[],
            crop_type="maize",
            stages=["V6"],
            soil_props={"nitrogen_ppm": 2.0, "phosphorus_ppm": 2.0, "potassium_ppm": 10.0},
            ndvi=0.6,
        )

        # 1. Must NOT report healthy 0.75 health
        self.assertLessEqual(l4_out.data_health.overall, 0.10)
        self.assertEqual(l4_out.data_health.status, "degraded")

        # 2. Must declare missing drivers
        self.assertIn("UNSUPPORTED_ROOT_BOUNDARY", l4_out.quality_metrics.missing_drivers)
        self.assertIn("MISSING_HYDROLOGY_AND_WEATHER", l4_out.quality_metrics.missing_drivers)

        # 3. All prescriptions must be blocked
        self.assertTrue(len(l4_out.prescriptions) > 0)
        for rx in l4_out.prescriptions:
            self.assertFalse(rx.is_allowed)
            self.assertIn("unsupported_root_boundary", rx.blocked_reason)
