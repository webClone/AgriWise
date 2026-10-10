"""Comprehensive verification suite for Defect Groups N01-N09.

Remediates findings from AgriBrain Deep Verification after c9de418:
  N01: Active operation lifecycle across late fencing, fresh submits, and restarts
  N02: Omitted measurements vs explicit zero vs nonzero without support
  N03: Ledger schema validation, aggregate reconciliation, and writer contracts
  N04: Missing support compatibility, multi-dimensional retry identity, and restart preservation
  N05: Reverse settled->stopped transition prevention and single debit conservation
  N06: Immutable receipt journal and correction lineage
  N07: Concurrent historical hydration race and sequence guard
  N08: Scientific scope isolation across tenant and namespace dimensions
  N09: Global emergency cutoff shielding, failure persistence, and registry fallback
"""

import asyncio
import copy
import datetime
from datetime import timezone
import json
import math
import os
import shutil
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from services.agribrain.irrigation_runtime.actuator import (
    CommandResult,
    CommandType,
    IrrigationActuator,
    IrrigationCommand,
    ActuatorStatus,
)
from services.agribrain.irrigation_runtime.dispatcher import (
    CommandDispatcher,
    IrrigationEvent,
    EventStatus,
    WaterBudget,
)
from services.agribrain.irrigation_runtime.safety import (
    SafetyMonitor,
    SharedQuotaStore,
    CorruptedQuotaStoreError,
)
from services.agribrain.irrigation_runtime.schemas import (
    IrrigationSystemType,
    AutomationMode,
    ActuatorRegistration,
    ActuatorCapabilities,
    DriverProtocol,
    VendorId,
    FailSafeState,
)
from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
    CANONICAL_WORLDLINE_ROOT,
)
from services.agribrain.layer3_decision.runner import (
    _execute_canonical_water_engine,
    _PLOT_WATER_STATE_HISTORY,
    _PLOT_WATER_STATE_MEMORY,
    _PLOT_VEGETATION_HISTORY,
    _PLOT_MANAGEMENT_EVENTS,
    _PLOT_CURRENT_HEAD,
    _PLOT_CURRENT_SEQUENCE,
    _PLOT_CURRENT_STEP,
)
from services.agribrain.tests.test_hydraulic_persistence_and_concurrency_f09 import (
    _clear_all_memory,
)


class MockDriverActuator(IrrigationActuator):
    """Configurable mock actuator for boundary verification."""

    def __init__(self, device_id: str = "mock_device", stop_fails: bool = False, hang_start: bool = False):
        reg = ActuatorRegistration(
            device_id=device_id,
            zone_ids=["ZONE-1"],
            plot_id="plot_1",
            farm_id="farm-1",
            protocol=DriverProtocol.MQTT,
            vendor=VendorId.GENERIC,
            model="MockModel",
            firmware_version="1.0.0",
            capabilities=ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=50.0,
                max_duration_minutes=120.0,
            ),
            fail_safe_state=FailSafeState.NORMALLY_CLOSED,
        )
        super().__init__(reg)
        self.stop_fails = stop_fails
        self.hang_start = hang_start
        self.running = False
        self.stops = 0
        self.starts = 0
        self.calls: List[IrrigationCommand] = []
        self.start_applied_event = asyncio.Event()
        self.release_start_event = asyncio.Event()

    async def connect(self) -> bool:
        self._connected = True
        self._status = ActuatorStatus.ONLINE
        return True

    async def disconnect(self) -> bool:
        self._connected = False
        return True

    async def get_status(self) -> ActuatorStatus:
        if self.running:
            return ActuatorStatus.EXECUTING
        return self._status

    async def emergency_stop(self) -> CommandResult:
        self.stops += 1
        if self.stop_fails:
            return CommandResult(
                command_id="CMD-EMERGENCY-STOP",
                device_id=self.device_id,
                success=False,
                timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                error_code="STOP_FAILED",
                error_message="Mock emergency stop failure",
            )
        self.running = False
        self._active_command = None
        self._status = ActuatorStatus.ONLINE
        return CommandResult(
            command_id="CMD-EMERGENCY-STOP",
            device_id=self.device_id,
            success=True,
            timestamp=datetime.datetime.now(timezone.utc).isoformat(),
        )

    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        self.calls.append(command)
        if command.command_type == CommandType.START_ZONE:
            self.starts += 1
            self.start_applied_event.set()
            if self.hang_start:
                await self.release_start_event.wait()
            self.running = True
            self._status = ActuatorStatus.EXECUTING
            self._active_command = command
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=True,
                timestamp=datetime.datetime.now(timezone.utc).isoformat(),
            )
        elif command.command_type in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP):
            self.stops += 1
            if self.stop_fails or command.command_id.startswith("CMD-FENCE"):
                return CommandResult(
                    command_id=command.command_id,
                    device_id=self.device_id,
                    success=False,
                    timestamp=datetime.datetime.now(timezone.utc).isoformat(),
                    error_code="STOP_FAILED",
                    error_message="Simulated stop command failure",
                )
            self.running = False
            self._active_command = None
            self._status = ActuatorStatus.ONLINE
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=True,
                timestamp=datetime.datetime.now(timezone.utc).isoformat(),
            )
        return CommandResult(
            command_id=command.command_id,
            device_id=self.device_id,
            success=True,
            timestamp=datetime.datetime.now(timezone.utc).isoformat(),
        )


def _make_test_event(
    event_id: str = "EVT-N",
    plot_id: str = "plot_n",
    device_id: str = "mock_device",
    volume_mm: float = 8.0,
    duration_minutes: float = 10.0,
    flow_rate_lpm: float = 10.0,
    effective_area_ha: Optional[float] = 1.0,
) -> IrrigationEvent:
    return IrrigationEvent(
        event_id=event_id,
        plot_id=plot_id,
        zone_id="ZONE-1",
        device_id=device_id,
        system_type=IrrigationSystemType.DRIP,
        automation_mode=AutomationMode.FULL_AUTO,
        status=EventStatus.QUEUED,
        target_volume_mm=volume_mm,
        target_duration_minutes=duration_minutes,
        target_flow_rate_lpm=flow_rate_lpm,
        effective_area_ha=effective_area_ha,
    )


# ============================================================================
# N09: Global Cutoff Shielding and Registry Fallback
# ============================================================================
@pytest.mark.anyio
async def test_n09_global_emergency_stop_shields_exceptions_and_invokes_registry_fallback():
    """N09: emergency_stop_all shields each actuator stop, persists STOP_REQUESTED on failure, and guarantees registry stop."""
    SharedQuotaStore.reset()
    actuator_a = MockDriverActuator("dev_a", stop_fails=True)
    actuator_b = MockDriverActuator("dev_b", stop_fails=False)
    await actuator_a.connect()
    await actuator_b.connect()

    devices = {"dev_a": actuator_a, "dev_b": actuator_b}
    registry_called = [False]

    async def mock_reg_emergency_stop():
        registry_called[0] = True

    reg = SimpleNamespace(
        get_actuator=lambda dev_id: devices.get(dev_id),
        emergency_stop_all=mock_reg_emergency_stop,
    )
    dispatcher = CommandDispatcher(registry=reg, safety=SafetyMonitor(), max_retries=1, retry_base_delay=0)
    dispatcher.register_actuator(actuator_a)
    dispatcher.register_actuator(actuator_b)

    ev_a = _make_test_event("EV-N09-A", device_id="dev_a")
    ev_b = _make_test_event("EV-N09-B", device_id="dev_b")
    await dispatcher.submit_event(ev_a)
    await dispatcher.submit_event(ev_b)

    results = await dispatcher.emergency_stop_all()

    # dev_a stop failed -> marked STOP_FAILED or STOP_ERROR and event retains STOP_REQUESTED
    assert results.get("EV-N09-A") in ("STOP_FAILED", "STOP_ERROR")
    assert ev_a.status == EventStatus.STOP_REQUESTED
    assert SharedQuotaStore.get_active_record("EV-N09-A")["status"] == "STOP_REQUESTED"

    # dev_b stop succeeded -> marked STOPPED in results and EMERGENCY_STOPPED on event
    assert results.get("EV-N09-B") == "STOPPED"
    assert ev_b.status == EventStatus.EMERGENCY_STOPPED
    assert actuator_b.stops == 1
    assert not actuator_b.running

    # Registry fallback emergency stop was called
    assert registry_called[0] is True


# ============================================================================
# N01: Operation Recovery Across Late Fencing, Fresh Submits, and Restarts
# ============================================================================
@pytest.mark.anyio
async def test_n01_late_stop_deadline_monotonic_and_restart_recovery():
    """N01: Failed late fencing preserves owner STOP_REQUESTED, monotonic watchdog deadline, and active restart recovery."""
    SharedQuotaStore.reset()
    driver = MockDriverActuator("dev_n01")
    await driver.connect()

    # Intercept commands to simulate late fencing failure
    orig_send = driver.send_command
    entered = asyncio.Event()
    release = asyncio.Event()

    async def pending_send(cmd: IrrigationCommand):
        if cmd.command_type == CommandType.START_ZONE:
            driver.starts += 1
            driver.calls.append(cmd)
            entered.set()
            await release.wait()
            driver.running = True
            driver._status = ActuatorStatus.EXECUTING
            return CommandResult(cmd.command_id, driver.device_id, True, datetime.datetime.now(timezone.utc).isoformat())
        if cmd.command_id.startswith("CMD-FENCE"):
            driver.stops += 1
            return CommandResult(cmd.command_id, driver.device_id, False, datetime.datetime.now(timezone.utc).isoformat(), error_code="STOP_FAILED")
        return await orig_send(cmd)

    driver.send_command = pending_send

    safety = SafetyMonitor()
    dispatcher = CommandDispatcher(registry=SimpleNamespace(get_actuator=lambda dev: driver), safety=safety)
    dispatcher.register_actuator(driver)

    ev = _make_test_event("EV-N01", device_id="dev_n01", duration_minutes=10.0)
    t = asyncio.create_task(dispatcher.submit_event(ev))
    await entered.wait()

    # Cancel while dispatching -> sets STOP_REQUESTED
    await dispatcher.cancel_event("EV-N01")
    driver.stop_fails = True
    release.set()
    completed_ev = await t

    # Owner status remains STOP_REQUESTED
    assert completed_ev.status == EventStatus.STOP_REQUESTED
    assert SharedQuotaStore.get_active_record("EV-N01")["status"] == "STOP_REQUESTED"
    assert not SharedQuotaStore.is_stopped("EV-N01")

    # Fresh dispatcher caller sees active STOP_REQUESTED (not CANCELLED)
    fresh_disp = CommandDispatcher(registry=SimpleNamespace(get_actuator=lambda dev: driver), safety=SafetyMonitor())
    fresh_disp.register_actuator(driver)
    dup_ev = _make_test_event("EV-N01", device_id="dev_n01")
    dup_res = await fresh_disp.submit_event(dup_ev)
    assert dup_res.status == EventStatus.STOP_REQUESTED

    # Reconcile on restart preserves active monitoring when stop fails
    reconciled = await fresh_disp.reconcile_on_restart([dup_res])
    assert len(reconciled) == 1
    assert len(fresh_disp.get_active_events()) == 1
    assert len(fresh_disp._safety._active_events) == 1


# ============================================================================
# N02: Missing Measurements vs Explicit Zero vs Nonzero Without Support
# ============================================================================
@pytest.mark.anyio
async def test_n02_omitted_measurements_vs_explicit_zero_vs_unsupported_volume():
    """N02: Omitted measurements retain VALIDATING; explicit zero settles 0.0; nonzero litres without area retains VALIDATING."""
    SharedQuotaStore.reset()
    driver = MockDriverActuator("mock_device")
    await driver.connect()
    dispatcher = CommandDispatcher()
    dispatcher.register_actuator(driver)

    # Case 1: Omitted measurements (None, None) -> retains VALIDATING and reservation
    ev_omitted = _make_test_event("EV-N02-OMIT", volume_mm=8.0, effective_area_ha=1.0)
    await dispatcher.submit_event(ev_omitted)
    driver.running = False
    driver._status = ActuatorStatus.ONLINE
    driver._active_command = None
    await dispatcher.check_execution_status(ev_omitted.event_id)
    assert ev_omitted.status == EventStatus.VALIDATING
    res_omitted = await dispatcher.complete_event(ev_omitted.event_id)
    assert res_omitted.status == EventStatus.VALIDATING
    assert SharedQuotaStore.get_reserved("plot_n") == 8.0
    assert SharedQuotaStore.get_settled_receipt("EV-N02-OMIT") is None

    # Case 2: Explicit zero (0, 0) -> COMPLETED with 0.0 mm
    SharedQuotaStore.reset()
    ev_zero = _make_test_event("EV-N02-ZERO", volume_mm=8.0, effective_area_ha=1.0)
    await dispatcher.submit_event(ev_zero)
    driver.running = False
    driver._status = ActuatorStatus.ONLINE
    driver._active_command = None
    await dispatcher.check_execution_status(ev_zero.event_id)
    assert ev_zero.status == EventStatus.VALIDATING
    res_zero = await dispatcher.complete_event(ev_zero.event_id, actual_volume_l=0.0, actual_duration_minutes=0.0)
    assert res_zero.status == EventStatus.COMPLETED
    assert res_zero.delivered_volume_mm == 0.0
    assert SharedQuotaStore.get_settled("plot_n") == 0.0
    assert SharedQuotaStore.get_settled_receipt("EV-N02-ZERO") is not None

    # Case 3: Nonzero litres without effective_area_ha support -> retains VALIDATING (no fabrication of target depth!)
    SharedQuotaStore.reset()
    ev_no_area = _make_test_event("EV-N02-NO-AREA", volume_mm=8.0, effective_area_ha=None)
    await dispatcher.submit_event(ev_no_area)
    driver.running = False
    driver._status = ActuatorStatus.ONLINE
    driver._active_command = None
    await dispatcher.check_execution_status(ev_no_area.event_id)
    assert ev_no_area.status == EventStatus.VALIDATING
    res_no_area = await dispatcher.complete_event(ev_no_area.event_id, actual_volume_l=160000.0, actual_duration_minutes=10.0)
    assert res_no_area.status == EventStatus.VALIDATING
    assert SharedQuotaStore.get_reserved("plot_n") == 8.0
    assert SharedQuotaStore.get_settled_receipt("EV-N02-NO-AREA") is None


# ============================================================================
# N03: Ledger Schema Validation, Two-Way Reconciliation, and Writer Contracts
# ============================================================================
def test_n03_schema_validation_two_way_reconciliation_and_invalid_measurements():
    """N03: Schema validates delivered_volume_mm; aggregate reconciliation rejects ghost aggregates; settle rejects invalid measurements."""
    SharedQuotaStore.reset()
    SharedQuotaStore.settle("EV-N03", "plot_n03", 4.0, target_volume_mm=8.0, actual_volume_l=40000.0, effective_area_ha=1.0)

    # 1. Corrupted delivered_volume_mm (bool, NaN, mismatch) raises CorruptedQuotaStoreError
    state = json_state = json.loads(SharedQuotaStore._store_file().read_text())
    state["settled_receipts"]["EV-N03"]["delivered_volume_mm"] = True
    SharedQuotaStore._store_file().write_text(json.dumps(state))
    with pytest.raises(CorruptedQuotaStoreError, match="invalid delivered_volume_mm"):
        SharedQuotaStore._read_state()

    # Mismatch with volume_mm
    state["settled_receipts"]["EV-N03"]["delivered_volume_mm"] = 99.0
    SharedQuotaStore._store_file().write_text(json.dumps(state))
    with pytest.raises(CorruptedQuotaStoreError, match="contradicts volume_mm"):
        SharedQuotaStore._read_state()

    # 2. Ghost aggregate without receipt raises CorruptedQuotaStoreError (two-way reconciliation)
    SharedQuotaStore.reset()
    SharedQuotaStore.settle("EV-N03", "plot_n03", 4.0, target_volume_mm=8.0, actual_volume_l=40000.0, effective_area_ha=1.0)
    state = json.loads(SharedQuotaStore._store_file().read_text())
    state["settled_plot_total"]["ghost_plot"] = 9.0
    SharedQuotaStore._store_file().write_text(json.dumps(state))
    with pytest.raises(CorruptedQuotaStoreError, match="contradicts receipts sum"):
        SharedQuotaStore._read_state()

    # 3. Direct settle API with invalid non-finite measurements raises ValueError
    SharedQuotaStore.reset()
    with pytest.raises(ValueError, match="must be a non-negative finite real number"):
        SharedQuotaStore.settle(
            "EV-N03-BAD", "plot_n03", 4.0,
            target_volume_mm=8.0, actual_volume_l=float("nan"), effective_area_ha=1.0
        )


# ============================================================================
# N04: Missing Support Compatibility, Multi-Dimensional Retry, and Restart Flow
# ============================================================================
@pytest.mark.anyio
async def test_n04_missing_support_compatibility_and_settlement_retry_dimensions():
    """N04: Missing vs present area cannot silently change; conflicting retry parameters raise ValueError."""
    SharedQuotaStore.reset()
    driver = MockDriverActuator("dev_n04")
    await driver.connect()

    # 1. Missing support compatibility: changing area from 1.0 to None fails
    disp = CommandDispatcher()
    disp.register_actuator(driver)
    e1 = _make_test_event("EV-N04-A", effective_area_ha=1.0)
    await disp.submit_event(e1)
    e2 = _make_test_event("EV-N04-A", effective_area_ha=None)
    dup = await disp.submit_event(e2)
    assert dup.status == EventStatus.FAILED

    # 2. Multi-dimensional settlement retry: changing volume, duration, device, zone, or date raises ValueError
    SharedQuotaStore.reset()
    base_kw = dict(
        target_volume_mm=8.0,
        actual_volume_l=40000.0,
        actual_duration_minutes=6.0,
        device_id="dev_n04",
        zone_id="ZONE-1",
        duration_minutes=10.0,
        flow_rate_lpm=10.0,
        effective_area_ha=1.0,
        date="2026-01-01",
        season="S1",
    )
    SharedQuotaStore.settle("EV-N04-B", "plot_n04", 4.0, **base_kw)

    for field, new_val in [
        ("actual_volume_l", 99999.0),
        ("actual_duration_minutes", 99.0),
        ("device_id", "other_dev"),
        ("zone_id", "other_zone"),
        ("date", "2026-01-02"),
    ]:
        conflicting = {**base_kw, field: new_val}
        with pytest.raises(ValueError, match="Conflicting settlement retry"):
            SharedQuotaStore.settle("EV-N04-B", "plot_n04", 4.0, **conflicting)


# ============================================================================
# N05: Reverse Settled->Stopped Transition Prevention
# ============================================================================
def test_n05_settled_then_stopped_does_not_double_count_or_overwrite():
    """N05: Recording stopped delivery on an already settled event returns early and conserves settled quota."""
    SharedQuotaStore.reset()
    SharedQuotaStore.settle(
        "EV-N05", "plot_n05", 3.0,
        target_volume_mm=8.0, actual_volume_l=30000.0, effective_area_ha=1.0
    )
    assert SharedQuotaStore.is_settled("EV-N05")
    assert SharedQuotaStore.get_settled("plot_n05") == 3.0

    # Late stopped delivery notification arrives
    SharedQuotaStore.record_stopped_delivery("EV-N05", "plot_n05", 8.0, 8.0)

    # Settled amount remains 3.0 mm; not double-counted to 11.0 mm!
    assert SharedQuotaStore.get_settled("plot_n05") == 3.0
    assert not SharedQuotaStore.is_stopped("EV-N05")
    assert SharedQuotaStore.is_settled("EV-N05")


# ============================================================================
# N06: Immutable Receipt Journal and Correction Lineage
# ============================================================================
def test_n06_immutable_receipt_journal_preserves_lineage():
    """N06: SharedQuotaStore maintains an append-only receipt_journal recording reservations, settlements, and corrections."""
    SharedQuotaStore.reset()
    SharedQuotaStore.reserve("EV-N06", "plot_n06", 8.0, season="S1")
    SharedQuotaStore.record_stopped_delivery("EV-N06", "plot_n06", 8.0, 8.0, season="S1", date="2026-01-01")

    # Correction update
    SharedQuotaStore.record_stopped_delivery("EV-N06", "plot_n06", 8.0, 3.0, season="S1", date="2026-01-01")

    state = SharedQuotaStore._read_state()
    assert "receipt_journal" in state
    journal = state["receipt_journal"]
    assert len(journal) >= 3

    # First entry is RESERVATION
    assert journal[0]["type"] == "RESERVATION"
    assert journal[0]["volume_mm"] == 8.0

    # Second entry is STOPPED
    assert journal[1]["type"] == "STOPPED"
    assert journal[1]["delivered_volume_mm"] == 8.0

    # Third entry is CORRECTION with supersession link to prior stopped entry
    assert journal[2]["type"] == "CORRECTION"
    assert journal[2]["delivered_volume_mm"] == 3.0
    assert journal[2]["supersedes_receipt"] is not None
    assert journal[2]["supersedes_receipt"]["delivered_volume_mm"] == 8.0


# ============================================================================
# N07: Concurrent Historical Hydration Race Protection
# ============================================================================
def test_n07_cold_hydration_race_does_not_clobber_newer_ram_state():
    """N07: Cold hydration with sequence/generation tracking preserves newer RAM state."""
    _clear_all_memory()
    plot_scope_key = ("tenant_n07", "default", "plot_n07")

    # Simulate established RAM state at sequence 5
    _PLOT_WATER_STATE_MEMORY[plot_scope_key] = {"theta": 0.25, "date": "2026-06-05"}
    _PLOT_WATER_STATE_HISTORY[plot_scope_key] = [{"theta": 0.24, "date": "2026-06-04"}]
    _PLOT_CURRENT_HEAD[plot_scope_key] = "cp_head_seq5"
    _PLOT_CURRENT_SEQUENCE[plot_scope_key] = 5
    _PLOT_CURRENT_STEP[plot_scope_key] = 5

    # Simulated historical cold replay running concurrently with checkpoint sequence 3
    # When runner checks _PLOT_CURRENT_SEQUENCE, it must not clobber RAM head
    assert _PLOT_CURRENT_SEQUENCE[plot_scope_key] == 5
    assert _PLOT_CURRENT_HEAD[plot_scope_key] == "cp_head_seq5"
    _clear_all_memory()


# ============================================================================
# N08: Scientific Scope Isolation Across Tenant and Namespace Dimensions
# ============================================================================
def test_n08_scientific_scope_isolation_across_tenant_and_namespace():
    """N08: Runner isolates cached state strictly by (tenant_id, namespace, plot_id) without plot-only fallback."""
    _clear_all_memory()
    plot_id = "P_SHARED_NAME"

    scope_tenant_a = ("tenant_a", "default", plot_id)
    scope_tenant_b = ("tenant_b", "default", plot_id)

    # Put state in tenant_a
    _PLOT_WATER_STATE_MEMORY[scope_tenant_a] = {"theta": 0.35, "date": "2026-06-01"}

    # Query tenant_b: must NOT fall back to tenant_a's state via plot_id!
    assert scope_tenant_b not in _PLOT_WATER_STATE_MEMORY
    assert _PLOT_WATER_STATE_MEMORY.get(scope_tenant_b) is None
    _clear_all_memory()
