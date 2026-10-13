"""Contract verification tests for XR01 through XR05 defect groups.

Verifies:
- XR01: MQTT publication acceptance without controller acknowledgement returns
        unconfirmed failure, keeping event in STOP_REQUESTED with active ownership
        and duration watchdog monitoring retained.
- XR02: Modbus emergency cutoff traverses configured zone coils from zone_coil_map,
        isolates transport exceptions per output coil to continue subsequent outputs,
        and reports ActuatorStatus.ERROR on failed status register reads, preventing
        false completions while the actuator is not confirmed idle.
- XR03: Restart recovery binds canonical device before querying actuator, preserves
        recovery obligation on OFFLINE/UNKNOWN or failed queries, treats STOP_REQUESTED
        as active owner, and does not misattribute post-execution VALIDATING as physical owner.
- XR04: Normal lifecycle writers (reserve, settle, reopen_active, watchdog registration)
        preserve immutable commanded target, qualified measured delivery, and effective
        exposure bounds. Known 12 mm delivery is debited as 12 mm, blocking a competing
        10 mm event under a 20 mm budget (12 + 10 = 22 > 20).
- XR05: Quota ledger validation rejects invalid scalars (bool, negative) for
        target_volume_mm, delivered_volume_mm, effective_exposure_mm, and enforces
        exposure >= max(target_volume_mm, delivered_volume_mm), failing closed.
"""

import asyncio
import copy
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.dispatcher import CommandDispatcher
from irrigation_runtime.drivers.mqtt_driver import MQTTActuator
from irrigation_runtime.drivers.modbus_driver import ModbusActuator
from irrigation_runtime.safety import (
    CorruptedQuotaStoreError,
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

    def __init__(self, hardware, cached_status=ActuatorStatus.ONLINE, device_id="device"):
        registration = ActuatorRegistration(
            device_id,
            VendorId.CUSTOM,
            "offline",
            DriverProtocol.HTTP_REST,
            farm_id="farm",
            plot_id="plot",
            zone_ids=["zone"],
            capabilities=ActuatorCapabilities(IrrigationSystemType.DRIP, max_flow_rate_lpm=50.0),
        )
        super().__init__(registration)
        self.device_id = device_id
        self.hw = hardware
        self._status = cached_status
        self.starts = 0
        self.stops = 0
        self.queries = 0

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        pass

    async def send_command(self, cmd: IrrigationCommand) -> CommandResult:
        if cmd.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            self.hw.running = True
            self.hw.event_id = cmd.source_event_id
            self.starts += 1
            self._status = ActuatorStatus.EXECUTING
        else:
            self.hw.running = False
            self.stops += 1
            self._status = ActuatorStatus.ONLINE
        return CommandResult(cmd.command_id, self.device_id, True, datetime.now(timezone.utc).isoformat())

    async def start_irrigation(self, command: IrrigationCommand) -> CommandResult:
        self.starts += 1
        self.hw.running = True
        self.hw.event_id = command.event_id
        self._status = ActuatorStatus.EXECUTING
        return CommandResult(command.command_id, self.device_id, True, datetime.now(timezone.utc).isoformat())

    async def emergency_stop(self) -> CommandResult:
        self.stops += 1
        self.hw.running = False
        self._status = ActuatorStatus.ONLINE
        return CommandResult("stop", self.device_id, True, datetime.now(timezone.utc).isoformat())

    async def get_status(self) -> ActuatorStatus:
        self.queries += 1
        if hasattr(self, "hw") and getattr(self.hw, "running", False):
            self._status = ActuatorStatus.EXECUTING
        return self._status


class FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now


def make_test_event(event_id="E", dev="device", vol=8.0, dur=10.0, flow=8.0, area=0.001):
    ev = IrrigationEvent(
        event_id=event_id,
        plot_id="plot",
        zone_id="zone",
        device_id=dev,
        system_type=IrrigationSystemType.DRIP,
        target_volume_mm=vol,
        target_duration_minutes=dur,
        target_flow_rate_lpm=flow,
        automation_mode=AutomationMode.FULL_AUTO,
        status=EventStatus.QUEUED,
        effective_area_ha=area,
    )
    return ev


def make_test_dispatcher(driver, clock=None):
    reg = SimpleNamespace(
        get_actuator=lambda dev: driver if dev in (getattr(driver, "device_id", "device"), "device") else None,
        emergency_stop_all=lambda: asyncio.sleep(0),
    )
    return CommandDispatcher(reg, SafetyMonitor(clock=clock), max_retries=1, retry_base_delay=0)


class TestXR01ThroughXR05(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    async def test_xr01_mqtt_unconfirmed_stop_retains_monitoring_and_ownership(self):
        """XR01: MQTT queue acceptance without controller ACK does not finalize STOP."""
        hw = SimpleNamespace(running=True, event_id="E")
        initial = MockHwAdapter(hw)
        clock = FakeClock(0.0)
        disp = make_test_dispatcher(initial, clock)
        budget = WaterBudget(daily_remaining_mm=20.0, season_remaining_mm=100.0, plot_id="plot", season="season")

        ev = await disp.submit_event(make_test_event("E"), budget=budget)
        self.assertEqual(ev.status, EventStatus.EXECUTING)

        # Substitute MQTT actuator with publish mock that returns rc=0 but receives no ACK
        reg = copy.deepcopy(initial.registration)
        reg.protocol = DriverProtocol.MQTT
        reg.farm_id = "F"
        reg.zone_ids = ["zone"]
        mqtt_dr = MQTTActuator(reg)
        mqtt_dr._connected = True
        mqtt_dr._status = ActuatorStatus.EXECUTING
        mqtt_dr.set_active_command(copy.deepcopy(initial.active_command))

        published_cmds = []

        class ClientMock:
            def publish(self, topic, payload, qos):
                cmd_data = json.loads(payload)
                published_cmds.append({"qos": qos, "cmd": cmd_data["cmd"]})
                return SimpleNamespace(rc=0)

        mqtt_dr._client = ClientMock()
        disp._registry.get_actuator = lambda _: mqtt_dr

        # Advance clock to trigger duration watchdog expiration (10 min = 600 s)
        clock.now = 601.0
        await disp.check_execution_status("E", {})

        # Verify event remains in STOP_REQUESTED, not premature EMERGENCY_STOPPED
        self.assertEqual(ev.status, EventStatus.STOP_REQUESTED)
        self.assertEqual(len(disp.get_active_events()), 1)
        self.assertEqual(len(disp._safety._active_events), 1)
        self.assertIsNone(SharedQuotaStore.get_stopped_receipt("E"))

    async def test_xr02_modbus_zone_cutoff_and_exception_isolation_and_status(self):
        """XR02: Modbus emergency cutoff covers zone_coil_map, isolates errors, and fails on bad read."""
        hw = SimpleNamespace(running=True, event_id="E")
        initial = MockHwAdapter(hw)
        clock = FakeClock(0.0)
        disp = make_test_dispatcher(initial, clock)
        budget = WaterBudget(daily_remaining_mm=20.0, season_remaining_mm=100.0, plot_id="plot", season="season")

        ev = await disp.submit_event(make_test_event("E"), budget=budget)

        # 1. Zone coil map only
        reg = copy.deepcopy(initial.registration)
        reg.protocol = DriverProtocol.MODBUS_TCP
        reg.connection_config = {"coil_map": {}, "zone_coil_map": {"zone": 77}}
        mb_dr = ModbusActuator(reg)
        mb_dr._connected = True
        writes = []

        class ClientZoneOnly:
            async def write_coil(self, address, value, slave):
                writes.append({"address": address, "value": value})
                raise OSError("transport failure")

        mb_dr._client = ClientZoneOnly()
        disp._registry.get_actuator = lambda _: mb_dr

        clock.now = 601.0
        await disp.check_execution_status("E", {})
        # Verify address 77 was targeted
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]["address"], 77)
        self.assertEqual(ev.status, EventStatus.STOP_REQUESTED)

        # 2. Per-output exception isolation
        writes_all = []

        class ClientFirstFails:
            async def write_coil(self, address, value, slave):
                writes_all.append({"address": address, "value": value})
                raise OSError("transport failure")

        reg_full = copy.deepcopy(initial.registration)
        reg_full.protocol = DriverProtocol.MODBUS_TCP
        reg_full.connection_config = {}  # uses default coils: emergency_stop(9), valves(0,1,2,3), pump(8)
        mb_dr_full = ModbusActuator(reg_full)
        mb_dr_full._connected = True
        mb_dr_full._client = ClientFirstFails()
        disp._registry.get_actuator = lambda _: mb_dr_full

        clock.now = 602.0
        await disp.check_execution_status("E", {})
        # All configured coils were attempted despite the first raising
        attempted_addrs = [w["address"] for w in writes_all]
        self.assertIn(9, attempted_addrs)
        self.assertIn(0, attempted_addrs)
        self.assertIn(8, attempted_addrs)

        # 3. Failed status read does not become ONLINE
        reg_read = copy.deepcopy(initial.registration)
        reg_read.protocol = DriverProtocol.MODBUS_TCP
        mb_read = ModbusActuator(reg_read)
        mb_read._connected = True

        class ReadClientError:
            async def read_input_registers(self, address, count, slave):
                return SimpleNamespace(isError=lambda: True, registers=[])

        mb_read._client = ReadClientError()
        st = await mb_read.get_status()
        self.assertEqual(st, ActuatorStatus.ERROR)

        # Complete event in VALIDATING rejected when status is ERROR
        disp_complete = make_test_dispatcher(initial)
        ev_comp = make_test_event("E_COMP", flow=8.0, area=0.001)
        await disp_complete.submit_event(ev_comp)
        SharedQuotaStore.mark_unsettled("E_COMP")
        ev_comp.status = EventStatus.VALIDATING
        disp_complete._registry.get_actuator = lambda _: mb_read

        await disp_complete.complete_event("E_COMP", actual_volume_l=80.0, actual_duration_minutes=10.0)
        self.assertEqual(ev_comp.status, EventStatus.VALIDATING)
        self.assertIsNone(SharedQuotaStore.get_settled_receipt("E_COMP"))

    async def test_xr03_restart_recovery_scope_and_uncertainty(self):
        """XR03: Canonical device queried first; OFFLINE/UNKNOWN preserves recovery."""
        hw = SimpleNamespace(running=True, event_id="OLD")
        initial = MockHwAdapter(hw)
        disp = make_test_dispatcher(initial)
        old_ev = await disp.submit_event(make_test_event("OLD", vol=1.0, dur=20.0))
        await disp.cancel_event("OLD")
        self.assertEqual(old_ev.status, EventStatus.CANCELLED)

        # 1. Live status UNKNOWN preserves reconciliation
        hw.running = True
        hw.event_id = "OLD"
        fresh_hw = MockHwAdapter(hw, ActuatorStatus.ONLINE)

        async def query_unknown():
            fresh_hw.queries += 1
            return ActuatorStatus.UNKNOWN

        fresh_hw.get_status = query_unknown
        fresh_disp = make_test_dispatcher(fresh_hw)
        snapshot = copy.deepcopy(old_ev)
        await fresh_disp.reconcile_on_restart([snapshot])

        self.assertEqual(fresh_hw.queries, 1)
        self.assertEqual(fresh_hw.stops, 1)  # Stopped because UNKNOWN is treated as unconfirmed running

        # 2. Wrong snapshot device queries canonical device
        hw.running = True
        hw.event_id = "OLD"
        canonical_hw = MockHwAdapter(hw, ActuatorStatus.ONLINE)
        wrong_driver = MockHwAdapter(hw, ActuatorStatus.ONLINE)
        wrong_driver.device_id = "wrong-device"
        reg_map = {"device": canonical_hw, "wrong-device": wrong_driver}
        restart_reg = SimpleNamespace(
            get_actuator=lambda dev: reg_map.get(dev),
            emergency_stop_all=lambda: asyncio.sleep(0),
        )
        restart_disp = CommandDispatcher(restart_reg, SafetyMonitor())

        snapshot_wrong = copy.deepcopy(old_ev)
        snapshot_wrong.device_id = "wrong-device"
        await restart_disp.reconcile_on_restart([snapshot_wrong])
        self.assertEqual(canonical_hw.queries, 1)
        self.assertEqual(canonical_hw.stops, 1)

    async def test_xr04_lifecycle_preserves_target_delivery_and_blocks_excess_admission(self):
        """XR04: reserve/settle/reopen/watchdog preserve target 8 / delivery 12, blocking 10 under 20."""
        kw = dict(
            season="S1",
            device_id="device",
            zone_id="zone",
            duration_minutes=10.0,
            flow_rate_lpm=8.0,
            effective_area_ha=0.001,
        )
        SharedQuotaStore.reserve("E", "plot", 8.0, **kw)
        SharedQuotaStore.settle("E", "plot", 12.0, target_volume_mm=8.0, actual_volume_l=120.0, actual_duration_minutes=10.0, **kw)
        SharedQuotaStore.reopen_active("E", "plot", 8.0, **kw)

        # 1. reserve retry preserves target 8 and delivery 12
        before = copy.deepcopy(SharedQuotaStore.get_active_record("E"))
        SharedQuotaStore.reserve("E", "plot", 8.0, **kw)
        after = copy.deepcopy(SharedQuotaStore.get_active_record("E"))
        self.assertEqual(after.get("target_volume_mm"), 8.0)
        self.assertEqual(after.get("delivered_volume_mm"), 12.0)
        self.assertEqual(after.get("effective_exposure_mm"), 12.0)

        # 2. settle preserves commanded target 8
        SharedQuotaStore.settle("E", "plot", 12.0, target_volume_mm=8.0, actual_volume_l=120.0, actual_duration_minutes=10.0, **kw)
        rcpt = SharedQuotaStore.get_settled_receipt("E")
        self.assertEqual(rcpt["target_volume_mm"], 8.0)
        self.assertEqual(rcpt["delivered_volume_mm"], 12.0)

        # 3. Repeated reopen without measurement is idempotent and does not raise TypeError
        SharedQuotaStore.reset()
        SharedQuotaStore.reserve("E", "plot", 8.0, **kw)
        SharedQuotaStore.reopen_active("E", "plot", 8.0, **kw)
        SharedQuotaStore.reopen_active("E", "plot", 8.0, **kw)
        rec = SharedQuotaStore.get_active_record("E")
        self.assertIsNone(rec.get("delivered_volume_mm"))
        self.assertEqual(rec.get("target_volume_mm"), 8.0)

        # 4. Failed-STOP restart recovery retains 12 mm lower bound; blocks competing 10 mm under 20 mm budget
        SharedQuotaStore.reset()
        SharedQuotaStore.reserve("E", "plot", 8.0, **kw)
        SharedQuotaStore.settle("E", "plot", 12.0, target_volume_mm=8.0, actual_volume_l=120.0, actual_duration_minutes=10.0, **kw)
        SharedQuotaStore.reopen_active("E", "plot", 8.0, **kw)
        SharedQuotaStore.set_actual_start("E", datetime.now(timezone.utc).isoformat())

        hw = SimpleNamespace(running=True, event_id="E")
        dr = MockHwAdapter(hw)

        async def failed_stop():
            dr.stops += 1
            return CommandResult("stop", "device", False, datetime.now(timezone.utc).isoformat(), error_code="FAILED")

        dr.emergency_stop = failed_stop
        disp = make_test_dispatcher(dr)
        ev = make_test_event("E", vol=8.0, flow=8.0, area=0.001)
        ev.status = EventStatus.STOP_REQUESTED

        await disp.reconcile_on_restart([ev])

        rec_after_stop = SharedQuotaStore.get_active_record("E")
        self.assertEqual(rec_after_stop.get("target_volume_mm"), 8.0)
        self.assertEqual(rec_after_stop.get("delivered_volume_mm"), 12.0)
        self.assertEqual(rec_after_stop.get("effective_exposure_mm"), 12.0)

        # Now successful stop
        async def success_stop():
            dr.stops += 1
            hw.running = False
            return CommandResult("stop", "device", True, datetime.now(timezone.utc).isoformat())

        dr.emergency_stop = success_stop
        await disp.check_execution_status("E", {})

        stopped_rcpt = SharedQuotaStore.get_stopped_receipt("E")
        self.assertEqual(stopped_rcpt["delivered_volume_mm"], 12.0)
        self.assertEqual(stopped_rcpt["target_volume_mm"], 8.0)

        # Competing 10 mm operation under budget 20: 12 + 10 = 22 > 20 -> BLOCKED!
        budget = WaterBudget(daily_remaining_mm=20.0, season_remaining_mm=20.0, plot_id="plot", season="S1")
        new_ev = make_test_event("SECOND", dev="second-device", vol=10.0, dur=10.0, flow=10.0, area=0.001)
        new_dr = MockHwAdapter(SimpleNamespace(running=False, event_id=""), ActuatorStatus.ONLINE)
        new_dr.device_id = "second-device"
        new_disp = make_test_dispatcher(new_dr)

        res_ev = await new_disp.submit_event(new_ev, budget=budget)
        self.assertEqual(res_ev.status, EventStatus.FAILED)
        self.assertEqual(new_dr.starts, 0)

    def test_xr05_ledger_corruption_rejection(self):
        """XR05: Schema validates new reservation fields and enforces exposure bounds."""
        kw = dict(
            season="S1",
            device_id="device",
            zone_id="zone",
            duration_minutes=10.0,
            flow_rate_lpm=8.0,
            effective_area_ha=0.001,
        )
        for field, invalid_val in [
            ("target_volume_mm", True),
            ("delivered_volume_mm", -5),
            ("effective_exposure_mm", -1),
            ("effective_exposure_mm", 0),
        ]:
            SharedQuotaStore.reset()
            SharedQuotaStore.reserve("E", "plot", 8.0, **kw)
            raw = SharedQuotaStore._read_state()
            raw["reservations"]["E"][field] = invalid_val
            SharedQuotaStore._store_file().write_text(json.dumps(raw))

            with self.assertRaises(CorruptedQuotaStoreError):
                SharedQuotaStore._read_state()

        # Lower bound violation: delivered_volume_mm is 12, but effective_exposure_mm is set to 8
        SharedQuotaStore.reset()
        SharedQuotaStore.reserve("E", "plot", 8.0, **kw)
        raw = SharedQuotaStore._read_state()
        raw["reservations"]["E"]["delivered_volume_mm"] = 12.0
        raw["reservations"]["E"]["effective_exposure_mm"] = 8.0
        SharedQuotaStore._store_file().write_text(json.dumps(raw))

        with self.assertRaises(CorruptedQuotaStoreError):
            SharedQuotaStore._read_state()


if __name__ == "__main__":
    unittest.main()
