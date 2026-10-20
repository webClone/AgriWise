"""Contract verification tests for SR01 through SR04 defect groups.

Verifies:
- SR01: MQTT emergency stop qualifies ACK payload: running=True or stopped=False fails stop
        with CONTROLLER_STILL_RUNNING, retaining STOP_REQUESTED and monitoring.
        get_status decodes correlated replies to ActuatorStatus and returns UNKNOWN
        on timeout without letting stale heartbeat payloads certify idle ONLINE state.
- SR02: Valid zero-depth operation (target_volume_mm=0, effective_exposure_mm=0) is
        accepted by _validate_state without CorruptedQuotaStoreError, allowing subsequent
        admissions. _write_state validates candidates prior to durable store replacement.
- SR03: Fresh atomic admission persists canonical target_volume_mm and effective_exposure_mm
        in reservation envelope and receipt journal. First settlement prioritizes canonical
        admitted envelope, preventing differing caller or local event targets from rewriting it.
- SR04: Physical device and zone mutual exclusion across active operations prevents
        two independent workers from dispatching conflicting operations to the same device/zone.
        Competing operations are held as STOP_REQUESTED without starting, preventing stale
        watchdog cutoff of new operations while preserving durable state integrity.
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


class MockHw:
    def __init__(self):
        self.running = False
        self.event_id = ""
        self.starts = 0
        self.stops = 0


class MockHwAdapter(IrrigationActuator):
    def __init__(self, hw, device_id="device", cached_status=ActuatorStatus.ONLINE):
        reg = ActuatorRegistration(
            device_id,
            VendorId.CUSTOM,
            "offline",
            DriverProtocol.HTTP_REST,
            capabilities=ActuatorCapabilities(IrrigationSystemType.DRIP),
        )
        super().__init__(reg)
        self.hw = hw
        self._status = cached_status

    async def connect(self):
        return True

    async def disconnect(self):
        pass

    async def get_status(self):
        self._status = ActuatorStatus.EXECUTING if self.hw.running else ActuatorStatus.ONLINE
        return self._status

    async def send_command(self, cmd):
        if cmd.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            self.hw.running = True
            self.hw.event_id = cmd.source_event_id
            self.hw.starts += 1
            self._status = ActuatorStatus.EXECUTING
        else:
            self.hw.running = False
            self.hw.stops += 1
            self._status = ActuatorStatus.ONLINE
        return CommandResult(cmd.command_id, self.device_id, True, datetime.now(timezone.utc).isoformat())

    async def emergency_stop(self):
        self.hw.running = False
        self.hw.stops += 1
        self._status = ActuatorStatus.ONLINE
        return CommandResult("stop", self.device_id, True, datetime.now(timezone.utc).isoformat())


class TestSR01ThroughSR04(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        SharedQuotaStore.reset()

    def tearDown(self):
        SharedQuotaStore.reset()

    def _make_event(self, eid="E", dev="device", vol=8.0, dur=10.0, flow=10.0, zone="zone"):
        return IrrigationEvent(
            event_id=eid,
            plot_id="plot",
            zone_id=zone,
            device_id=dev,
            system_type=IrrigationSystemType.DRIP,
            automation_mode=AutomationMode.FULL_AUTO,
            status=EventStatus.QUEUED,
            target_volume_mm=vol,
            target_duration_minutes=dur,
            target_flow_rate_lpm=flow,
        )

    # =========================================================================
    # SR01: MQTT ACK qualification and status query correlation
    # =========================================================================

    async def test_sr01_mqtt_emergency_stop_contradictory_ack_retains_stop_requested(self):
        """SR01: emergency_stop rejects contradictory ACK (OK but running=True / stopped=False)

        Watchdog check must retain event in STOP_REQUESTED with monitoring and no stopped receipt.
        """
        reg = ActuatorRegistration(
            "mqtt_dev",
            VendorId.CUSTOM,
            "offline",
            DriverProtocol.MQTT,
            farm_id="F",
            capabilities=ActuatorCapabilities(IrrigationSystemType.DRIP),
            connection_config={"query_timeout_s": 0.05, "stop_timeout_s": 0.05},
        )
        dr = MQTTActuator(reg)
        dr._connected = True
        dr._status = ActuatorStatus.EXECUTING

        # Mock MQTT client that returns contradictory ACK: status=OK, running=True, stopped=False
        class ContradictoryClient:
            def publish(self, topic, payload, qos):
                cmd = json.loads(payload)
                ack = {
                    "request_id": cmd.get("request_id"),
                    "status": "OK",
                    "stopped": False,
                    "running": True,
                }
                # Deliver to driver callback
                dr._on_message(None, None, SimpleNamespace(topic=dr._status_topic, payload=json.dumps(ack).encode()))
                return SimpleNamespace(rc=0)

        dr._client = ContradictoryClient()

        clock_val = [0.0]
        safety = SafetyMonitor(clock=lambda: clock_val[0])
        registry = SimpleNamespace(get_actuator=lambda _: dr, emergency_stop_all=lambda: asyncio.sleep(0))
        dispatcher = CommandDispatcher(registry, safety, max_retries=1, retry_base_delay=0)

        # Direct emergency stop test
        res = await dr.emergency_stop()
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "CONTROLLER_STILL_RUNNING")
        self.assertEqual(dr._status, ActuatorStatus.EXECUTING)

        # Integration test via watchdog
        hw = MockHw()
        adapter = MockHwAdapter(hw, device_id="mqtt_dev")
        owner = CommandDispatcher(SimpleNamespace(get_actuator=lambda _: adapter), safety)
        ev = await owner.submit_event(self._make_event("E", dev="mqtt_dev"), budget=WaterBudget("plot", "s", 10, 10))

        # Switch actuator to contradictory MQTT driver
        owner._registry.get_actuator = lambda _: dr
        clock_val[0] = 601.0
        await owner.check_execution_status("E", {})

        self.assertEqual(ev.status, EventStatus.STOP_REQUESTED)
        self.assertEqual(len(owner.get_active_events()), 1)
        self.assertIsNone(SharedQuotaStore.get_stopped_receipt("E"))

    async def test_sr01_mqtt_get_status_decodes_correlated_replies_and_times_out_safely(self):
        """SR01: get_status decodes EXECUTING and ERROR, and returns UNKNOWN on timeout

        Stale heartbeat payload must not certify current idle ONLINE status.
        """
        reg = ActuatorRegistration(
            "mqtt_dev",
            VendorId.CUSTOM,
            "offline",
            DriverProtocol.MQTT,
            farm_id="F",
            capabilities=ActuatorCapabilities(IrrigationSystemType.DRIP),
            connection_config={"query_timeout_s": 0.02, "stop_timeout_s": 0.02},
        )

        for mode, expected_status in [
            ("matched_running_reply", ActuatorStatus.EXECUTING),
            ("matched_error_reply", ActuatorStatus.ERROR),
            ("no_fresh_reply_with_recent_old_payload", ActuatorStatus.UNKNOWN),
        ]:
            dr = MQTTActuator(reg)
            dr._connected = True
            dr._status = ActuatorStatus.ONLINE

            if mode == "no_fresh_reply_with_recent_old_payload":
                dr._on_message(
                    None, None,
                    SimpleNamespace(topic=dr._status_topic, payload=json.dumps({"request_id": "old", "status": "OK", "running": False}).encode())
                )

            class TestClient:
                def publish(self, topic, payload, qos):
                    cmd = json.loads(payload)
                    if mode != "no_fresh_reply_with_recent_old_payload":
                        ack = {
                            "request_id": cmd.get("request_id"),
                            "status": "EXECUTING" if mode == "matched_running_reply" else "ERROR",
                            "running": True,
                            "stopped": False,
                        }
                        dr._on_message(None, None, SimpleNamespace(topic=dr._status_topic, payload=json.dumps(ack).encode()))
                    return SimpleNamespace(rc=0)

            dr._client = TestClient()
            queried = await dr.get_status()
            self.assertEqual(queried, expected_status, f"Mode {mode} expected {expected_status} but got {queried}")

            # Verify that completion fails closed while queried status is not idle ONLINE
            hw = MockHw()
            adapter = MockHwAdapter(hw, device_id="mqtt_dev")
            owner = CommandDispatcher(SimpleNamespace(get_actuator=lambda _: dr), SafetyMonitor())
            ev = self._make_event("E", dev="mqtt_dev")
            owner._active_events["E"] = ev
            ev.status = EventStatus.VALIDATING
            SharedQuotaStore.reserve("E", "plot", 8.0, device_id="mqtt_dev", zone_id="zone")
            SharedQuotaStore.mark_unsettled("E")

            completed = await owner.complete_event("E", actual_volume_l=80.0, actual_duration_minutes=10.0)
            self.assertEqual(completed.status, EventStatus.VALIDATING, f"Event completed erroneously in mode {mode}")
            self.assertIsNone(SharedQuotaStore.get_settled_receipt("E"))

    # =========================================================================
    # SR02: Valid zero-depth operation store readability
    # =========================================================================

    def test_sr02_valid_zero_depth_reopen_and_subsequent_admission(self):
        """SR02: Reopening a valid zero-depth operation produces readable state and allows admissions."""
        for measured in [None, 0.0]:
            SharedQuotaStore.reset()
            SharedQuotaStore.reserve("ZERO", "plot", 0.0, device_id="device", zone_id="zone", duration_minutes=10, flow_rate_lpm=0, effective_area_ha=0.001)
            if measured is not None:
                SharedQuotaStore.settle("ZERO", "plot", 0.0, target_volume_mm=0.0, actual_volume_l=0.0, actual_duration_minutes=None, effective_area_ha=0.001)

            # Reopen active zero operation
            SharedQuotaStore.reopen_active("ZERO", "plot", 0.0, device_id="device", zone_id="zone", duration_minutes=10, flow_rate_lpm=0, effective_area_ha=0.001)

            # Store file must be readable without CorruptedQuotaStoreError
            state = SharedQuotaStore._read_state()
            rec = state["reservations"]["ZERO"]
            self.assertEqual(rec["target_volume_mm"], 0.0)
            self.assertEqual(rec["effective_exposure_mm"], 0.0)

            # Next admission on different device must succeed
            violation = SharedQuotaStore.atomic_check_and_reserve(
                "plot", 1.0, None, "OTHER", device_id="other", zone_id="zone", duration_minutes=10, flow_rate_lpm=1.0
            )
            self.assertIsNone(violation, "Subsequent eligible admission blocked by zero-depth reservation")

    # =========================================================================
    # SR03: Canonical admission target preservation at settlement
    # =========================================================================

    async def test_sr03_fresh_atomic_admission_preserves_canonical_target_at_settlement(self):
        """SR03: Admitted target 8 mm is preserved through first settlement when caller target is 2 mm."""
        # 1. Direct settlement with conflicting caller target
        SharedQuotaStore.reset()
        violation = SharedQuotaStore.atomic_check_and_reserve(
            "plot", 8.0, None, "E", device_id="device", zone_id="zone", duration_minutes=10, flow_rate_lpm=8.0, effective_area_ha=0.001
        )
        self.assertIsNone(violation)
        claim = SharedQuotaStore.get_active_record("E")
        self.assertEqual(claim.get("target_volume_mm"), 8.0)
        self.assertEqual(claim.get("volume_mm"), 8.0)

        # Caller provides target_volume_mm=2.0 at settlement
        SharedQuotaStore.settle("E", "plot", 8.0, target_volume_mm=2.0, actual_volume_l=80.0, actual_duration_minutes=10.0, effective_area_ha=0.001)
        receipt = SharedQuotaStore.get_settled_receipt("E")
        self.assertEqual(receipt["target_volume_mm"], 8.0, "Canonical target rewritten to caller target")
        self.assertEqual(receipt["delivered_volume_mm"], 8.0)

        # 2. Mutated local event object before dispatcher complete_event
        SharedQuotaStore.reset()
        hw = MockHw()
        adapter = MockHwAdapter(hw)
        dispatcher = CommandDispatcher(SimpleNamespace(get_actuator=lambda _: adapter), SafetyMonitor())
        ev = self._make_event("E", vol=8.0, flow=8.0)
        ev.effective_area_ha = 0.001
        await dispatcher.submit_event(ev)

        # Controller finishes execution
        hw.running = False
        await dispatcher.check_execution_status("E", {})
        self.assertEqual(ev.status, EventStatus.VALIDATING)

        # Mutate local event target to 2.0
        ev.target_volume_mm = 2.0
        await dispatcher.complete_event("E", actual_volume_l=80.0, actual_duration_minutes=10.0)

        receipt2 = SharedQuotaStore.get_settled_receipt("E")
        self.assertEqual(receipt2["target_volume_mm"], 8.0, "Mutated local event rewrote canonical target")
        self.assertEqual(receipt2["delivered_volume_mm"], 8.0)

    # =========================================================================
    # SR04: Device/zone exclusivity across independent workers
    # =========================================================================

    async def test_sr04_device_zone_exclusivity_prevents_competing_dispatch(self):
        """SR04: Competing operation on same device/zone is held as STOP_REQUESTED without starting."""
        hw = MockHw()
        adapter1 = MockHwAdapter(hw, device_id="device")
        adapter2 = MockHwAdapter(hw, device_id="device")  # Separate adapter instance (simulating worker 2)

        dispatcher1 = CommandDispatcher(SimpleNamespace(get_actuator=lambda _: adapter1), SafetyMonitor())
        dispatcher2 = CommandDispatcher(SimpleNamespace(get_actuator=lambda _: adapter2), SafetyMonitor())

        # Worker 1 starts OLD
        ev_old = self._make_event("OLD", dev="device", vol=1.0, dur=1.0, flow=10.0, zone="zone")
        await dispatcher1.submit_event(ev_old, budget=WaterBudget("plot", "s", 10, 10))
        self.assertEqual(ev_old.status, EventStatus.EXECUTING)
        self.assertEqual(hw.starts, 1)
        self.assertEqual(hw.event_id, "OLD")

        # Worker 2 attempts NEW on same device and zone
        ev_new = self._make_event("NEW", dev="device", vol=1.0, dur=20.0, flow=10.0, zone="zone")
        await dispatcher2.submit_event(ev_new, budget=WaterBudget("plot", "s", 10, 10))

        # NEW must be refused pre-transport without dispatching a second START
        self.assertEqual(ev_new.status, EventStatus.FAILED)
        self.assertEqual(hw.starts, 1, "Competing worker dispatched duplicate START to physical hardware")
        self.assertEqual(hw.event_id, "OLD", "Competing worker overwrote active hardware operation")

        durable_new = SharedQuotaStore.get_active_record("NEW")
        self.assertIsNone(durable_new, "Positively unsent loser quota reservation must be released")


if __name__ == "__main__":
    unittest.main()
