"""Contract verification tests for NR01 through NR04 defect groups.

Verifies:
- NR01: Stopped-event recovery queries live actuator status rather than trusting
        stale/cached status, respects ownership of running controllers, and never
        stops or reopens an actuator executing a different live operation (NEW).
- NR02: Reopening a command after measured delivery preserves immutable commanded
        target (e.g. 8 mm) alongside qualified delivery/exposure (e.g. 12 mm),
        preventing target rewriting and permitting identical retry reconciliation.
- NR03: Concrete MQTT and Modbus drivers return failure when underlying transport
        responses fail, and dispatcher retains active ownership and safety watchdog
        monitoring without premature terminal stopped transitions.
- NR04: Reserving or replaying an already-settled event never hides completion
        receipts or creates phantom active reservations, preserving valid quota
        accounting for subsequent eligible irrigation.
"""

import asyncio
import copy
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.dispatcher import CommandDispatcher
from irrigation_runtime.drivers.mqtt_driver import MQTTActuator
from irrigation_runtime.drivers.modbus_driver import ModbusActuator
from irrigation_runtime.safety import (
    SafetyMonitor,
    SharedQuotaStore,
    WaterBudget,
)
from irrigation_runtime.schemas import (
    ActuatorCapabilities,
    ActuatorRegistration,
    ActuatorStatus,
    AutomationMode,
    CommandResult,
    CommandType,
    DriverProtocol,
    IrrigationCommand,
    IrrigationEvent,
    EventStatus,
    IrrigationSystemType,
    VendorId,
)


class MockHwAdapter(IrrigationActuator):
    """Adapter mimicking production hardware without public running flag."""
    def __init__(self, hardware, cached_status=ActuatorStatus.ONLINE):
        registration = ActuatorRegistration(
            "device",
            VendorId.CUSTOM,
            "offline",
            DriverProtocol.HTTP_REST,
            capabilities=ActuatorCapabilities(IrrigationSystemType.DRIP),
        )
        super().__init__(registration)
        self.hw = hardware
        self._status = cached_status
        self.queries = 0
        self.stops = 0
        self.starts = 0

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        pass

    async def get_status(self) -> ActuatorStatus:
        self.queries += 1
        self._status = ActuatorStatus.EXECUTING if self.hw.running else ActuatorStatus.ONLINE
        return self._status

    async def send_command(self, cmd: IrrigationCommand) -> CommandResult:
        if cmd.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            self.hw.running = True
            self.hw.event_id = cmd.source_event_id
            self.starts += 1
        else:
            self.hw.running = False
            self.stops += 1
        return CommandResult(cmd.command_id, self.device_id, True, datetime.now(timezone.utc).isoformat())

    async def emergency_stop(self) -> CommandResult:
        self.stops += 1
        self.hw.running = False
        return CommandResult("stop", self.device_id, True, datetime.now(timezone.utc).isoformat())


class ControllableClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now


def make_test_event(eid="E", dev="device", vol=8.0, dur=10.0, flow=8.0):
    return IrrigationEvent(
        event_id=eid,
        plot_id="plot",
        zone_id="zone",
        device_id=dev,
        system_type=IrrigationSystemType.DRIP,
        target_flow_rate_lpm=flow,
        target_volume_mm=vol,
        target_duration_minutes=dur,
        automation_mode=AutomationMode.FULL_AUTO,
        status=EventStatus.QUEUED,
        effective_area_ha=0.001,
    )


def make_test_dispatcher(driver: MockHwAdapter, clock: ControllableClock = None) -> CommandDispatcher:
    reg = SimpleNamespace(
        get_actuator=lambda _: driver,
        emergency_stop_all=lambda: asyncio.sleep(0),
    )
    return CommandDispatcher(reg, SafetyMonitor(clock), max_retries=1, retry_base_delay=0)


class TestNR01NR04ContractVerification(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        SharedQuotaStore.reset()

    async def asyncTearDown(self):
        SharedQuotaStore.reset()

    async def test_nr01_stopped_old_recovery_does_not_stop_or_reopen_different_new(self):
        """NR01: Recovering an OLD stopped event queries live controller and does not stop NEW."""
        for has_identity in [True, False]:
            SharedQuotaStore.reset()
            hw = SimpleNamespace(running=False, event_id="")
            initial = MockHwAdapter(hw)
            old_owner = make_test_dispatcher(initial)

            old = await old_owner.submit_event(make_test_event("OLD", vol=1.0, dur=20.0))
            await old_owner.cancel_event("OLD")

            new = await make_test_dispatcher(initial).submit_event(make_test_event("NEW", vol=1.0, dur=20.0))
            self.assertTrue(hw.running)
            self.assertEqual(hw.event_id, "NEW")

            recovery_driver = MockHwAdapter(hw, ActuatorStatus.EXECUTING)
            if has_identity:
                recovery_driver.set_active_command(copy.deepcopy(initial.active_command))

            fresh = make_test_dispatcher(recovery_driver)
            snapshot = copy.deepcopy(old)
            await fresh.reconcile_on_restart([snapshot])

            self.assertEqual(recovery_driver.stops, 0, f"Expected 0 STOPs, got {recovery_driver.stops}")
            self.assertTrue(hw.running, "Physical hardware should still be running for NEW")
            self.assertEqual(new.status, EventStatus.EXECUTING)
            self.assertEqual(SharedQuotaStore.get_active_record("NEW")["status"], "EXECUTING")
            self.assertEqual(snapshot.status, EventStatus.CANCELLED)
            self.assertFalse(SharedQuotaStore.is_active("OLD"))
            self.assertEqual(len(fresh.get_active_events()), 0)

    async def test_nr02_reopened_exposure_preserves_command_target(self):
        """NR02: Reopening an 8 mm event after 12 mm delivery preserves commanded target 8 mm."""
        SharedQuotaStore.reserve(
            "E", "plot", 8.0,
            date="2026-10-12", season="S1", device_id="device", zone_id="zone",
            duration_minutes=10.0, flow_rate_lpm=8.0, effective_area_ha=0.001,
        )
        SharedQuotaStore.settle(
            "E", "plot", 12.0,
            target_volume_mm=8.0, actual_volume_l=120.0, actual_duration_minutes=10.0,
            date="2026-10-12", season="S1", device_id="device", zone_id="zone",
            duration_minutes=10.0, flow_rate_lpm=8.0, effective_area_ha=0.001,
        )

        prior = SharedQuotaStore.get_settled_receipt("E")
        self.assertEqual(prior["target_volume_mm"], 8.0)
        self.assertEqual(prior["delivered_volume_mm"], 12.0)

        SharedQuotaStore.reopen_active(
            "E", "plot", 8.0,
            duration_minutes=10.0, flow_rate_lpm=8.0, effective_area_ha=0.001,
        )
        reopened = SharedQuotaStore.get_active_record("E")
        self.assertEqual(reopened["target_volume_mm"], 8.0)
        self.assertEqual(reopened["volume_mm"], 12.0)
        self.assertEqual(reopened["effective_exposure_mm"], 12.0)

        retry = make_test_event("E", vol=8.0, dur=10.0, flow=8.0)
        hw = SimpleNamespace(running=False, event_id="E")
        driver = MockHwAdapter(hw)
        dispatcher = make_test_dispatcher(driver)

        returned = await dispatcher.submit_event(retry)
        self.assertEqual(returned.status, EventStatus.STOP_REQUESTED)
        self.assertEqual(returned.failure_reason, "")
        self.assertEqual(driver.starts, 0)
        self.assertEqual(returned.target_volume_mm, 8.0)

        # Cold restart snapshot reconciliation preserves 8 mm target
        cold_driver = MockHwAdapter(hw)
        cold_disp = make_test_dispatcher(cold_driver)
        snapshot = make_test_event("E", vol=8.0, dur=10.0, flow=8.0)
        snapshot.status = EventStatus.STOP_REQUESTED
        await cold_disp.reconcile_on_restart([snapshot])

        self.assertEqual(snapshot.target_volume_mm, 8.0)
        self.assertEqual(snapshot.status, EventStatus.CANCELLED)

        receipt = SharedQuotaStore.get_stopped_receipt("E")
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["target_volume_mm"], 8.0)
        self.assertEqual(receipt["delivered_volume_mm"], 12.0)

    async def test_nr03_mqtt_and_modbus_failed_stop_transport(self):
        """NR03: Concrete MQTT and Modbus drivers report failure on failed STOP transport."""
        for proto in ["MQTT", "MODBUS"]:
            SharedQuotaStore.reset()
            hw = SimpleNamespace(running=False, event_id="")
            initial = MockHwAdapter(hw)
            clock = ControllableClock(0.0)
            owner = make_test_dispatcher(initial, clock)
            budget = WaterBudget(daily_remaining_mm=20.0, season_remaining_mm=100.0, plot_id="plot", season="S1")
            event = await owner.submit_event(make_test_event("E", vol=8.0), budget=budget)

            reg = copy.deepcopy(initial.registration)
            reg.farm_id = "F"
            reg.zone_ids = ["zone"]

            calls = []
            if proto == "MQTT":
                reg.protocol = DriverProtocol.MQTT
                driver = MQTTActuator(reg)
                driver._connected = True

                class FailingMqttClient:
                    def publish(self, topic, payload, qos):
                        calls.append({"qos": qos, "return_code": 4})
                        return SimpleNamespace(rc=4)

                driver._client = FailingMqttClient()
            else:
                reg.protocol = DriverProtocol.MODBUS_TCP
                driver = ModbusActuator(reg)
                driver._connected = True

                class FailingModbusClient:
                    async def write_coil(self, address, value, slave=1):
                        calls.append({"address": address, "value": value, "isError": True})
                        return SimpleNamespace(isError=lambda: True)

                driver._client = FailingModbusClient()

            driver._status = ActuatorStatus.EXECUTING
            driver.set_active_command(copy.deepcopy(initial.active_command))
            owner._registry.get_actuator = lambda _: driver

            # Advance clock past timeout (10 min duration = 600s)
            clock.now = 601.0
            await owner.check_execution_status("E", {})

            self.assertTrue(len(calls) > 0)
            self.assertEqual(event.status, EventStatus.STOP_REQUESTED)
            self.assertEqual(len(owner.get_active_events()), 1)
            self.assertEqual(len(owner._safety._active_events), 1)
            self.assertEqual(SharedQuotaStore.get_active_record("E")["status"], "STOP_REQUESTED")
            self.assertIsNone(SharedQuotaStore.get_stopped_receipt("E"))

    async def test_nr04_terminal_reserve_retains_receipt_and_prevents_phantom_quota(self):
        """NR04: Re-reserving a settled event preserves completed receipt and avoids phantom quota."""
        SharedQuotaStore.reserve(
            "E", "plot", 8.0,
            season="S1", device_id="device", zone_id="zone",
            duration_minutes=10.0, flow_rate_lpm=8.0, effective_area_ha=0.001,
        )
        kwargs = dict(
            target_volume_mm=8.0, actual_volume_l=40.0, actual_duration_minutes=5.0,
            season="S1", device_id="device", zone_id="zone",
            duration_minutes=10.0, flow_rate_lpm=8.0, effective_area_ha=0.001,
        )
        SharedQuotaStore.settle("E", "plot", 4.0, **kwargs)
        original = SharedQuotaStore.get_settled_receipt("E")
        self.assertIsNotNone(original)
        self.assertEqual(original["delivered_volume_mm"], 4.0)

        # Re-reserving already-settled event
        SharedQuotaStore.reserve(
            "E", "plot", 8.0,
            season="S1", device_id="device", zone_id="zone",
            duration_minutes=10.0, flow_rate_lpm=8.0, effective_area_ha=0.001,
        )

        # Verify receipt is still present and valid
        self.assertTrue(SharedQuotaStore.is_settled("E"))
        receipt_after = SharedQuotaStore.get_settled_receipt("E")
        self.assertEqual(receipt_after["delivered_volume_mm"], 4.0)
        self.assertEqual(receipt_after["target_volume_mm"], 8.0)

        # Resubmitting identical duplicate event returns COMPLETED without duplicate START
        duplicate = make_test_event("E", vol=8.0, dur=10.0, flow=8.0)
        hw = SimpleNamespace(running=False, event_id="")
        driver = MockHwAdapter(hw)
        dispatcher = make_test_dispatcher(driver)

        returned = await dispatcher.submit_event(duplicate)
        self.assertEqual(returned.status, EventStatus.COMPLETED)
        self.assertEqual(driver.starts, 0)

        # Quota verification: settled is 4 mm, reserved is 4 mm (from active completed record)
        self.assertEqual(SharedQuotaStore.get_settled("plot"), 4.0)

        # Second event for 4 mm should be admitted under 10 mm budget
        second_hw = SimpleNamespace(running=False, event_id="")
        second_driver = MockHwAdapter(second_hw)
        second_disp = make_test_dispatcher(second_driver)

        second = make_test_event("SECOND", dev="second_device", vol=4.0, dur=5.0, flow=8.0)
        budget = WaterBudget(daily_remaining_mm=10.0, season_remaining_mm=100.0, plot_id="plot", season="S1")
        await second_disp.submit_event(second, budget=budget)

        self.assertEqual(second.status, EventStatus.EXECUTING)
        self.assertEqual(second_driver.starts, 1)


if __name__ == "__main__":
    unittest.main()
