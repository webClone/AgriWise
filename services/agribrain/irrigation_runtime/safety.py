"""
Irrigation Runtime — Safety Monitor v1.0.0

Fail-safe interlock system that continuously evaluates sensor telemetry
against configured safety thresholds. Triggers emergency stops, alerts,
and audit records when violations are detected.

Interlock Categories:
  - PRESSURE_LOW:  Pipe burst detection (flow sensor + pressure drop)
  - PRESSURE_HIGH: Over-pressure protection
  - FLOW_ZERO:     Clog or stuck-closed valve detection
  - FLOW_EXCESSIVE: Leak or stuck-open valve detection
  - OVER_DELIVERY:  Volume exceeded target by >20%
  - DURATION_EXCEEDED: Max runtime watchdog
  - FROST_RISK:    Air temperature < 2°C → defer irrigation
  - WATER_QUOTA_EXCEEDED: Season/daily quota enforcement
  - SENSOR_OFFLINE: Critical sensor lost during irrigation
  - ELECTRICAL_FAULT: Actuator power anomaly

All violations are logged with full provenance for the L6 audit trail.
"""

from __future__ import annotations

import json
import logging
import math
import os
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from numbers import Real
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from irrigation_runtime.schemas import (
    ActuatorRegistration,
    CommandType,
    InterlockType,
    IrrigationCommand,
    IrrigationEvent,
    EventStatus,
    SafetyInterlock,
    SafetyViolation,
    WaterBudget,
)

try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    try:
        from services.agribrain.scientific_contracts.numeric import finite_real
    except ImportError:
        def finite_real(val: Any) -> Optional[float]:
            if isinstance(val, bool) or not isinstance(val, Real):
                return None
            try:
                res = float(val)
                return res if math.isfinite(res) else None
            except Exception:
                return None

logger = logging.getLogger(__name__)


class CorruptedQuotaStoreError(RuntimeError):
    """Raised when the persistent quota store is malformed, blank, or has invalid schema."""
    pass


def _is_pid_alive(pid: int) -> bool:
    """Check if process with given PID is currently alive."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
        if handle:
            exit_code = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                STILL_ACTIVE = 259
                is_alive = (exit_code.value == STILL_ACTIVE)
                ctypes.windll.kernel32.CloseHandle(handle)
                return is_alive
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


class SharedQuotaStore:
    """Thread-safe and cross-process atomic shared quota reservation and settlement store.

    Backed by an atomic state file and cross-process file lock so that independent
    SafetyMonitor and CommandDispatcher instances across processes and threads share
    active reservations, unsettled delivery, and cumulative settled deliveries per plot scope.
    """
    _thread_lock = threading.RLock()

    @classmethod
    def _store_dir(cls) -> Path:
        env_dir = os.environ.get("AGRIBRAIN_QUOTA_DIR")
        if env_dir:
            p = Path(env_dir)
        else:
            p = Path(tempfile.gettempdir()) / "agribrain_runtime" / "quota"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def _store_file(cls) -> Path:
        return cls._store_dir() / "quota_store.json"

    @classmethod
    @contextmanager
    def _lock(cls):
        with cls._thread_lock:
            lock_path = cls._store_dir() / "quota.lock"
            descriptor = None
            owner_token = f"{os.getpid()}:{threading.get_ident()}:{uuid.uuid4().hex}"
            for _ in range(500):
                try:
                    descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    break
                except FileExistsError:
                    try:
                        if time.time() - lock_path.stat().st_mtime > 30.0:
                            # V02: Only displace lock if owner PID is confirmed dead!
                            lock_txt = ""
                            try:
                                lock_txt = lock_path.read_text(encoding="utf-8").strip()
                            except OSError:
                                pass
                            owner_pid = -1
                            if lock_txt:
                                try:
                                    owner_pid = int(lock_txt.split(":")[0])
                                except ValueError:
                                    owner_pid = -1
                            if owner_pid > 0 and _is_pid_alive(owner_pid):
                                # Owner is alive: do NOT steal lock
                                pass
                            else:
                                lock_path.unlink(missing_ok=True)
                                continue
                    except OSError:
                        pass
                    time.sleep(0.005)
            if descriptor is None:
                raise TimeoutError("Timeout acquiring cross-process quota lock")
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(owner_token)
                yield
            finally:
                # V02: Only release lock if it still belongs to our token
                try:
                    if lock_path.exists():
                        cur_token = lock_path.read_text(encoding="utf-8").strip()
                        if cur_token == owner_token:
                            lock_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @classmethod
    def _read_state(cls) -> Dict[str, Any]:
        p = cls._store_file()
        if not p.exists():
            return {
                "reservations": {},
                "settled_receipts": {},
                "settled_daily": {},
                "settled_season": {},
                "settled_plot_total": {},
                "stopped_receipts": {},
            }
        try:
            content = p.read_text(encoding="utf-8")
            if not content.strip():
                raise CorruptedQuotaStoreError(f"Quota store file {p} is empty or blank")
            data = json.loads(content)
            if not isinstance(data, dict):
                raise CorruptedQuotaStoreError(f"Quota store file {p} is not a JSON object: got {type(data).__name__}")
            required_keys = {"reservations", "settled_receipts", "settled_daily", "settled_season", "settled_plot_total"}
            if not required_keys.issubset(data.keys()) or not isinstance(data.get("reservations"), dict):
                raise CorruptedQuotaStoreError(f"Quota store file {p} has missing or invalid schema keys")
            return data
        except CorruptedQuotaStoreError:
            raise
        except Exception as exc:
            raise CorruptedQuotaStoreError(f"Quota store file {p} is malformed or unreadable: {exc}") from exc

    @classmethod
    def _write_state(cls, state: Dict[str, Any]) -> None:
        p = cls._store_file()
        tmp = p.with_suffix(f".{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp")
        try:
            with tmp.open("w", encoding="utf-8") as handle:
                json.dump(state, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, p)
        finally:
            tmp.unlink(missing_ok=True)

    @classmethod
    def reset(cls) -> None:
        with cls._lock():
            state = {
                "reservations": {},
                "settled_receipts": {},
                "settled_daily": {},
                "settled_season": {},
                "settled_plot_total": {},
                "stopped_receipts": {},
            }
            cls._write_state(state)

    @classmethod
    def atomic_check_and_reserve(
        cls,
        plot_id: str,
        requested_volume_mm: float,
        budget: WaterBudget,
        event_id: str,
        device_id: str = "",
        zone_id: str = "",
        duration_minutes: float = 0.0,
        owner_token: str = "",
    ) -> Optional[SafetyViolation]:
        """Atomically validate budget and reserve quota under a cross-process lock."""
        req_vol = finite_real(requested_volume_mm)
        if req_vol is None or req_vol < 0:
            return SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-QUOTA",
                interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                device_id=device_id,
                zone_id=zone_id,
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=float(requested_volume_mm) if isinstance(requested_volume_mm, (int, float)) and not math.isnan(requested_volume_mm) else 0.0,
                threshold_breached="max",
                threshold_value=0.0,
                action_taken="BLOCK",
                notes=f"Invalid requested volume {requested_volume_mm}: must be a non-negative finite real number",
            )

        s_rem = finite_real(budget.season_remaining_mm)
        d_rem = finite_real(budget.daily_remaining_mm)
        if s_rem is None or d_rem is None:
            return SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-QUOTA",
                interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                device_id=device_id,
                zone_id=zone_id,
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=req_vol,
                threshold_breached="max",
                threshold_value=0.0,
                action_taken="BLOCK",
                notes=f"Non-finite budget limits: season_remaining={budget.season_remaining_mm}, daily_remaining={budget.daily_remaining_mm}",
            )

        try:
            with cls._lock():
                state = cls._read_state()
                settled_receipts = state.get("settled_receipts", {})
                if event_id in settled_receipts:
                    rec = settled_receipts[event_id]
                    rec_vol = float(rec.get("volume_mm", 0.0))
                    rec_plot = rec.get("plot_id", "")
                    rec_dev = rec.get("device_id", "")
                    is_conflict = (abs(rec_vol - req_vol) > 1e-4) or (rec_plot and rec_plot != plot_id) or (device_id and rec_dev and rec_dev != device_id)
                    if is_conflict:
                        return SafetyViolation(
                            violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                            interlock_id="INT-QUOTA",
                            interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                            device_id=device_id,
                            zone_id=zone_id,
                            detected_at=datetime.now(timezone.utc).isoformat(),
                            sensor_value=req_vol,
                            threshold_breached="max",
                            threshold_value=rec_vol,
                            action_taken="BLOCK",
                            notes=f"Payload conflict with settled receipt: event {event_id} already settled with {rec_vol}mm vs requested {req_vol}mm",
                        )
                    return SafetyViolation(
                        violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                        interlock_id="INT-QUOTA",
                        interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                        device_id=device_id,
                        zone_id=zone_id,
                        detected_at=datetime.now(timezone.utc).isoformat(),
                        sensor_value=req_vol,
                        threshold_breached="max",
                        threshold_value=rec_vol,
                        action_taken="ALREADY_SETTLED",
                        notes=f"Event {event_id} already settled",
                    )

                reservations = state.get("reservations", {})
                if event_id in reservations:
                    res = reservations[event_id]
                    res_vol = float(res.get("volume_mm", 0.0))
                    res_plot = res.get("plot_id", "")
                    res_dev = res.get("device_id", "")
                    is_conflict = (abs(res_vol - req_vol) > 1e-4) or (res_plot and res_plot != plot_id) or (device_id and res_dev and res_dev != device_id)
                    if is_conflict:
                        return SafetyViolation(
                            violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                            interlock_id="INT-QUOTA",
                            interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                            device_id=device_id,
                            zone_id=zone_id,
                            detected_at=datetime.now(timezone.utc).isoformat(),
                            sensor_value=req_vol,
                            threshold_breached="max",
                            threshold_value=res_vol,
                            action_taken="BLOCK",
                            notes=f"Payload conflict with active reservation: event {event_id} already reserved with {res_vol}mm vs requested {req_vol}mm",
                        )
                    # V03: Concurrent identical operation already claimed
                    return SafetyViolation(
                        violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                        interlock_id="INT-QUOTA",
                        interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                        device_id=device_id,
                        zone_id=zone_id,
                        detected_at=datetime.now(timezone.utc).isoformat(),
                        sensor_value=req_vol,
                        threshold_breached="max",
                        threshold_value=res_vol,
                        action_taken="ALREADY_RESERVED",
                        notes=f"Event {event_id} already reserved by concurrent worker",
                    )

                already_reserved = 0.0
                for eid, res in reservations.items():
                    if eid != event_id and res.get("plot_id") == plot_id:
                        already_reserved += float(res.get("volume_mm", 0.0))

                today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                season_key = str(getattr(budget, "season", "default_season"))
                settled_today = float(state.get("settled_daily", {}).get(f"{plot_id}:{today_key}", 0.0))
                settled_season = float(state.get("settled_season", {}).get(f"{plot_id}:{season_key}", 0.0))

                daily_consumed = finite_real(budget.daily_consumed_mm) or 0.0
                season_consumed = finite_real(budget.season_consumed_mm) or 0.0

                untracked_daily = max(0.0, settled_today - daily_consumed)
                untracked_season = max(0.0, settled_season - season_consumed)

                eff_season = s_rem - already_reserved - untracked_season
                eff_daily = d_rem - already_reserved - untracked_daily

                if req_vol > eff_season:
                    reason = (
                        f"Season quota exceeded by concurrent reservations: need {req_vol:.1f}mm, "
                        f"remaining unreserved {eff_season:.1f}mm "
                        f"({already_reserved:.1f}mm reserved, {untracked_season:.1f}mm untracked settled)"
                    )
                    return SafetyViolation(
                        violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                        interlock_id="INT-QUOTA",
                        interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                        device_id=device_id,
                        zone_id=zone_id,
                        detected_at=datetime.now(timezone.utc).isoformat(),
                        sensor_value=req_vol,
                        threshold_breached="max",
                        threshold_value=eff_season,
                        action_taken="BLOCK",
                        notes=reason,
                    )

                if req_vol > eff_daily:
                    reason = (
                        f"Daily quota exceeded by concurrent reservations: need {req_vol:.1f}mm, "
                        f"remaining unreserved {eff_daily:.1f}mm "
                        f"({already_reserved:.1f}mm reserved, {untracked_daily:.1f}mm untracked settled)"
                    )
                    return SafetyViolation(
                        violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                        interlock_id="INT-QUOTA",
                        interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                        device_id=device_id,
                        zone_id=zone_id,
                        detected_at=datetime.now(timezone.utc).isoformat(),
                        sensor_value=req_vol,
                        threshold_breached="max",
                        threshold_value=eff_daily,
                        action_taken="BLOCK",
                        notes=reason,
                    )

                # Admitted! Reserve atomically with full payload binding and season retention (V03 + V04).
                if req_vol > 0:
                    reservations[event_id] = {
                        "plot_id": plot_id,
                        "device_id": device_id,
                        "zone_id": zone_id,
                        "volume_mm": req_vol,
                        "duration_minutes": duration_minutes,
                        "status": "RESERVED",
                        "date": today_key,
                        "season": season_key,
                        "owner_token": owner_token,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    state["reservations"] = reservations
                    cls._write_state(state)
                return None
        except CorruptedQuotaStoreError as c_err:
            # V01: Corrupt quota store must block new physical dispatches rather than resetting to zero
            return SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-QUOTA",
                interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                device_id=device_id,
                zone_id=zone_id,
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=req_vol,
                threshold_breached="max",
                threshold_value=0.0,
                action_taken="BLOCK",
                notes=f"Quota store corrupted or unreadable: {c_err}",
            )
        except OSError as os_err:
            return SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-QUOTA",
                interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                device_id=device_id,
                zone_id=zone_id,
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=req_vol,
                threshold_breached="max",
                threshold_value=0.0,
                action_taken="BLOCK",
                notes=f"Quota store I/O error: {os_err}",
            )

    @classmethod
    def reserve(
        cls,
        event_id: str,
        plot_id: str,
        volume_mm: float,
        season: Optional[str] = None,
        date: Optional[str] = None,
        device_id: str = "",
        zone_id: str = "",
        duration_minutes: float = 0.0,
    ) -> None:
        val = finite_real(volume_mm)
        if val is None or val <= 0:
            return
        with cls._lock():
            state = cls._read_state()
            today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            existing = state.setdefault("reservations", {}).get(event_id, {})
            # V04: Preserve season from existing atomic reservation if not supplied
            season_key = season or existing.get("season") or "default_season"
            date_key = date or existing.get("date") or today_key
            state["reservations"][event_id] = {
                "plot_id": plot_id,
                "device_id": device_id or existing.get("device_id", ""),
                "zone_id": zone_id or existing.get("zone_id", ""),
                "volume_mm": val,
                "duration_minutes": duration_minutes or existing.get("duration_minutes", 0.0),
                "status": "RESERVED",
                "date": date_key,
                "season": season_key,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            cls._write_state(state)

    @classmethod
    def mark_unsettled(cls, event_id: str) -> None:
        """Mark an active reservation as pending validation/settlement without releasing quota."""
        with cls._lock():
            state = cls._read_state()
            reservations = state.get("reservations", {})
            if event_id in reservations:
                reservations[event_id]["status"] = "UNSETTLED"
                cls._write_state(state)

    @classmethod
    def release(cls, event_id: str) -> None:
        with cls._lock():
            state = cls._read_state()
            reservations = state.get("reservations", {})
            if event_id in reservations:
                reservations.pop(event_id, None)
                cls._write_state(state)

    @classmethod
    def settle(
        cls,
        event_id: str,
        plot_id: str,
        volume_mm: float,
        date: Optional[str] = None,
        season: Optional[str] = None,
    ) -> None:
        with cls._lock():
            state = cls._read_state()
            existing_res = state.setdefault("reservations", {}).pop(event_id, {})
            settled_receipts = state.setdefault("settled_receipts", {})
            if event_id in settled_receipts:
                cls._write_state(state)
                return  # Idempotent!

            val = finite_real(volume_mm)
            if val is not None and val > 0:
                # V04: Retain season and date from existing reservation if omitted
                date_key = date or existing_res.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
                season_key = season or existing_res.get("season") or "default_season"
                device_id = existing_res.get("device_id", "")
                zone_id = existing_res.get("zone_id", "")
                settled_receipts[event_id] = {
                    "plot_id": plot_id,
                    "device_id": device_id,
                    "zone_id": zone_id,
                    "volume_mm": val,
                    "date": date_key,
                    "season": season_key,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                pk_daily = f"{plot_id}:{date_key}"
                pk_season = f"{plot_id}:{season_key}"
                state.setdefault("settled_daily", {})[pk_daily] = float(state.get("settled_daily", {}).get(pk_daily, 0.0)) + val
                state.setdefault("settled_season", {})[pk_season] = float(state.get("settled_season", {}).get(pk_season, 0.0)) + val
                state.setdefault("settled_plot_total", {})[plot_id] = float(state.get("settled_plot_total", {}).get(plot_id, 0.0)) + val

            cls._write_state(state)

    @classmethod
    def record_stopped_delivery(
        cls,
        event_id: str,
        plot_id: str,
        target_volume_mm: float,
        delivered_volume_mm: float = 0.0,
        season: Optional[str] = None,
        date: Optional[str] = None,
    ) -> None:
        """Record partial/stopped delivery so delivered or reserved exposure is not lost on cancellation (V04)."""
        with cls._lock():
            state = cls._read_state()
            existing_res = state.setdefault("reservations", {}).pop(event_id, {})
            del_val = finite_real(delivered_volume_mm) or 0.0
            date_key = date or existing_res.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            season_key = season or existing_res.get("season") or "default_season"
            device_id = existing_res.get("device_id", "")
            state.setdefault("stopped_receipts", {})[event_id] = {
                "plot_id": plot_id,
                "device_id": device_id,
                "target_volume_mm": target_volume_mm,
                "delivered_volume_mm": del_val,
                "date": date_key,
                "season": season_key,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if del_val > 0:
                pk_daily = f"{plot_id}:{date_key}"
                pk_season = f"{plot_id}:{season_key}"
                state.setdefault("settled_daily", {})[pk_daily] = float(state.get("settled_daily", {}).get(pk_daily, 0.0)) + del_val
                state.setdefault("settled_season", {})[pk_season] = float(state.get("settled_season", {}).get(pk_season, 0.0)) + del_val
                state.setdefault("settled_plot_total", {})[plot_id] = float(state.get("settled_plot_total", {}).get(plot_id, 0.0)) + del_val
            cls._write_state(state)

    @classmethod
    def get_reserved(cls, plot_id: str, exclude_event_id: Optional[str] = None) -> float:
        with cls._lock():
            state = cls._read_state()
            total = 0.0
            for eid, res in state.get("reservations", {}).items():
                if eid != exclude_event_id and res.get("plot_id") == plot_id:
                    total += float(res.get("volume_mm", 0.0))
            return total

    @classmethod
    def get_settled(cls, plot_id: str) -> float:
        with cls._lock():
            state = cls._read_state()
            return float(state.get("settled_plot_total", {}).get(plot_id, 0.0))

    @classmethod
    def is_settled(cls, event_id: str, plot_id: Optional[str] = None) -> bool:
        with cls._lock():
            state = cls._read_state()
            return event_id in state.get("settled_receipts", {})

    @classmethod
    def is_active(cls, event_id: str, plot_id: Optional[str] = None) -> bool:
        with cls._lock():
            state = cls._read_state()
            return event_id in state.get("reservations", {})

    @classmethod
    def get_active_record(cls, event_id: str) -> Optional[Dict[str, Any]]:
        with cls._lock():
            state = cls._read_state()
            return state.get("reservations", {}).get(event_id)

    @classmethod
    def get_settled_receipt(cls, event_id: str) -> Optional[Dict[str, Any]]:
        with cls._lock():
            state = cls._read_state()
            return state.get("settled_receipts", {}).get(event_id)


# ============================================================================
# Default Interlock Definitions
# ============================================================================

DEFAULT_INTERLOCKS: List[SafetyInterlock] = [
    SafetyInterlock(
        interlock_id="INT-PRESSURE-LOW",
        interlock_type=InterlockType.PRESSURE_LOW,
        description="Pipe burst detection: pressure drops below safe minimum during operation",
        sensor_variable="irrigation_pressure_bar",
        threshold_min=0.5,
        duration_seconds=15,
        action_on_trigger=CommandType.EMERGENCY_STOP,
        requires_manual_reset=True,
    ),
    SafetyInterlock(
        interlock_id="INT-PRESSURE-HIGH",
        interlock_type=InterlockType.PRESSURE_HIGH,
        description="Over-pressure protection: pressure exceeds system maximum",
        sensor_variable="irrigation_pressure_bar",
        threshold_max=8.0,
        duration_seconds=5,
        action_on_trigger=CommandType.EMERGENCY_STOP,
        requires_manual_reset=True,
    ),
    SafetyInterlock(
        interlock_id="INT-FLOW-ZERO",
        interlock_type=InterlockType.FLOW_ZERO,
        description="Clog detection: no flow detected while valve is commanded open",
        sensor_variable="irrigation_flow_l_min",
        threshold_min=0.1,
        duration_seconds=60,
        action_on_trigger=CommandType.STOP_ZONE,
        requires_manual_reset=False,
    ),
    SafetyInterlock(
        interlock_id="INT-FLOW-EXCESSIVE",
        interlock_type=InterlockType.FLOW_EXCESSIVE,
        description="Leak detection: flow exceeds 200% of commanded rate",
        sensor_variable="irrigation_flow_l_min",
        threshold_max=None,  # Set dynamically based on commanded flow
        duration_seconds=30,
        action_on_trigger=CommandType.EMERGENCY_STOP,
        requires_manual_reset=True,
    ),
    SafetyInterlock(
        interlock_id="INT-FROST",
        interlock_type=InterlockType.FROST_RISK,
        description="Frost protection: air temperature below 2°C",
        sensor_variable="air_temperature_c",
        threshold_min=2.0,
        duration_seconds=300,
        action_on_trigger=CommandType.STOP_ZONE,
        auto_reset=True,
        requires_manual_reset=False,
    ),
    SafetyInterlock(
        interlock_id="INT-DURATION",
        interlock_type=InterlockType.DURATION_EXCEEDED,
        description="Runtime watchdog: zone running beyond maximum allowed duration",
        sensor_variable="",  # Timer-based, not sensor-based
        duration_seconds=0,  # Checked against command duration
        action_on_trigger=CommandType.STOP_ZONE,
        requires_manual_reset=False,
    ),
]


class SafetyMonitor:
    """Continuous safety evaluation engine for irrigation operations.

    Monitors real-time sensor telemetry against configured interlocks
    and triggers appropriate protective actions when violations occur.

    Architecture:
      sensor_runtime telemetry → SafetyMonitor.evaluate()
        → check pressure, flow, temperature, duration
        → if violation: trigger emergency_stop + log violation
        → feed SafetyViolation to L6 ConflictRecord
    """

    def __init__(self, clock: Optional[Callable[[], float]] = None):
        self._interlocks: List[SafetyInterlock] = list(DEFAULT_INTERLOCKS)
        # Active violations indexed by stable key: f"{interlock_id}:{device_id}"
        self._active_violations: Dict[str, SafetyViolation] = {}
        self._violation_history: List[SafetyViolation] = []
        self._violation_callbacks: List[Callable] = []

        # Duration tracking: event_id → {start_time, start_monotonic, max_duration_minutes, device_id, plot_id, volume_mm}
        self._active_events: Dict[str, Dict[str, Any]] = {}
        # Quota reservation: event_id → {plot_id, volume_mm}
        self._reserved_quota: Dict[str, Dict[str, Any]] = {}

        # Debounce breach tracking: active_key -> {first_breach_monotonic, last_breach_monotonic, ...}
        self._breach_tracking: Dict[str, Dict[str, Any]] = {}

        # Monotonic clock source (injected for deterministic testing)
        self._clock: Callable[[], float] = clock if clock is not None else time.monotonic

    # ================================================================
    # Interlock Management
    # ================================================================

    def add_interlock(self, interlock: SafetyInterlock) -> None:
        """Register a custom safety interlock."""
        self._interlocks.append(interlock)
        logger.info("Added safety interlock: %s (%s)",
                     interlock.interlock_id, interlock.interlock_type.value)

    def remove_interlock(self, interlock_id: str) -> None:
        """Remove an interlock by ID."""
        self._interlocks = [i for i in self._interlocks
                            if i.interlock_id != interlock_id]

    def set_interlocks(self, interlocks: List[SafetyInterlock]) -> None:
        """Replace all interlocks with a new set."""
        self._interlocks = list(interlocks)

    def on_violation(self, callback: Callable) -> None:
        """Register a callback for safety violations.

        Callback signature: callback(violation: SafetyViolation) -> None
        """
        self._violation_callbacks.append(callback)

    # ================================================================
    # Event Tracking (for duration watchdog)
    # ================================================================

    def track_event_start(
        self,
        event_id: str,
        device_id: str,
        max_duration_minutes: float,
        plot_id: str = "",
        volume_mm: float = 0.0,
        elapsed_minutes: float = 0.0,
        season: Optional[str] = None,
        date: Optional[str] = None,
    ) -> None:
        """Register an active irrigation event for duration monitoring and quota reservation."""
        now_dt = datetime.now(timezone.utc)
        start_mono = self._clock() - (max(0.0, elapsed_minutes) * 60.0)
        self._active_events[event_id] = {
            "start_time": now_dt,
            "start_monotonic": start_mono,
            "max_duration_minutes": max_duration_minutes,
            "device_id": device_id,
            "plot_id": plot_id,
            "volume_mm": volume_mm,
            "season": season,
            "date": date,
        }
        if plot_id and volume_mm > 0:
            self.reserve_quota(
                event_id,
                plot_id,
                volume_mm,
                season=season,
                date=date,
                device_id=device_id,
                duration_minutes=max_duration_minutes,
            )
        logger.debug("Tracking event %s (max %.0f min, elapsed %.1f min, reserved %.1f mm)",
                     event_id, max_duration_minutes, elapsed_minutes, volume_mm)

    def track_event_end(self, event_id: str) -> None:
        """Remove an event from duration watchdog while preserving unsettled quota."""
        self._active_events.pop(event_id, None)
        SharedQuotaStore.mark_unsettled(event_id)

    def is_event_active(self, event_id: str) -> bool:
        """Check if an event is currently being tracked by the duration watchdog."""
        return event_id in self._active_events

    def reserve_quota(
        self,
        event_id: str,
        plot_id: str,
        volume_mm: float,
        season: Optional[str] = None,
        date: Optional[str] = None,
        device_id: str = "",
        zone_id: str = "",
        duration_minutes: float = 0.0,
    ) -> None:
        """Explicitly record a quota reservation in the shared store."""
        SharedQuotaStore.reserve(
            event_id,
            plot_id,
            volume_mm,
            season=season,
            date=date,
            device_id=device_id,
            zone_id=zone_id,
            duration_minutes=duration_minutes,
        )
        if volume_mm > 0:
            self._reserved_quota[event_id] = {
                "plot_id": plot_id,
                "volume_mm": volume_mm,
                "season": season,
                "date": date,
            }

    def release_quota(self, event_id: str) -> None:
        """Explicitly release a quota reservation in the shared store."""
        SharedQuotaStore.release(event_id)
        self._reserved_quota.pop(event_id, None)

    def settle_quota(
        self,
        event_id: str,
        plot_id: str,
        volume_mm: float,
        date: Optional[str] = None,
        season: Optional[str] = None,
    ) -> None:
        """Settle a delivered event: release reservation and debit cumulative budget."""
        SharedQuotaStore.settle(event_id, plot_id, volume_mm, date=date, season=season)
        self._reserved_quota.pop(event_id, None)

    def get_reserved_quota(self, plot_id: str, exclude_event_id: Optional[str] = None) -> float:
        """Calculate total reserved volume (mm) for a plot across all active uncommitted events."""
        shared_total = SharedQuotaStore.get_reserved(plot_id, exclude_event_id=exclude_event_id)
        local_total = 0.0
        for eid, res in self._reserved_quota.items():
            if eid != exclude_event_id and res.get("plot_id") == plot_id:
                local_total += res.get("volume_mm", 0.0)
        return max(shared_total, local_total)

    # ================================================================
    # Core Evaluation
    # ================================================================

    def evaluate(
        self,
        device_id: str,
        sensor_readings: Optional[Dict[str, float]] = None,
        active_command: Optional[IrrigationCommand] = None,
    ) -> List[SafetyViolation]:
        """Evaluate all interlocks against current sensor data.

        Monitors duration watchdog independently and evaluates sensor telemetry.
        Runs unconditionally whether sensor telemetry is present, empty, or None.

        Args:
            device_id: The actuator being monitored
            sensor_readings: Optional dict of CanonicalVariable → current value
            active_command: The currently executing command (for flow limits)

        Returns:
            List of newly detected SafetyViolation records
        """
        new_violations = []

        # 1. Independent duration watchdog check (runs on monotonic timer)
        duration_violations = self._check_duration_watchdog(device_id)
        new_violations.extend(duration_violations)

        # 2. Telemetry sensor interlocks
        readings = sensor_readings if sensor_readings is not None else {}
        for interlock in self._interlocks:
            if not interlock.enabled:
                continue

            # Skip if interlock is device-specific and doesn't apply
            if (interlock.applies_to_devices
                    and device_id not in interlock.applies_to_devices):
                continue

            violation = self._check_interlock(
                interlock, device_id, readings, active_command
            )
            if violation:
                new_violations.append(violation)
                active_key = f"{violation.interlock_id}:{device_id}"
                self._active_violations[active_key] = violation
                self._violation_history.append(violation)

                # Notify callbacks
                for cb in self._violation_callbacks:
                    try:
                        cb(violation)
                    except Exception as exc:
                        logger.error("Violation callback error: %s", exc)

        return new_violations

    def _check_interlock(
        self,
        interlock: SafetyInterlock,
        device_id: str,
        sensor_readings: Dict[str, float],
        active_command: Optional[IrrigationCommand],
    ) -> Optional[SafetyViolation]:
        """Check a single interlock against sensor data with debounce and recovery."""

        # Skip timer-based interlocks (handled by _check_duration_watchdog)
        if not interlock.sensor_variable:
            return None

        active_key = f"{interlock.interlock_id}:{device_id}"

        # If sensor reading is missing or non-finite:
        # "Missing or nonfinite readings cannot count as normal pressure."
        if interlock.sensor_variable not in sensor_readings:
            return None

        raw_val = sensor_readings[interlock.sensor_variable]
        if raw_val is None or isinstance(raw_val, bool) or not isinstance(raw_val, Real):
            return None

        val_float = float(raw_val)
        if math.isnan(val_float) or math.isinf(val_float):
            return None

        value = val_float

        # Dynamic threshold for flow excessive (based on commanded flow)
        threshold_max = interlock.threshold_max
        if (interlock.interlock_type == InterlockType.FLOW_EXCESSIVE
                and active_command
                and active_command.flow_rate_lpm > 0):
            threshold_max = active_command.flow_rate_lpm * 2.0  # 200% of commanded

        # Check thresholds
        breached = False
        threshold_type = ""
        threshold_val = 0.0

        if interlock.threshold_min is not None and value < interlock.threshold_min:
            breached = True
            threshold_type = "min"
            threshold_val = interlock.threshold_min

        if threshold_max is not None and value > threshold_max:
            breached = True
            threshold_type = "max"
            threshold_val = threshold_max

        now_mono = self._clock()

        if breached:
            # Check if this breach already triggered an active violation
            if active_key in self._active_violations:
                # Sustained breach emits only ONE active violation until qualifying reset
                return None

            # Debounce tracking
            if active_key not in self._breach_tracking:
                self._breach_tracking[active_key] = {
                    "first_breach_monotonic": now_mono,
                    "last_breach_monotonic": now_mono,
                    "last_breach_value": value,
                    "threshold_type": threshold_type,
                    "threshold_val": threshold_val,
                }
            else:
                self._breach_tracking[active_key]["last_breach_monotonic"] = now_mono
                self._breach_tracking[active_key]["last_breach_value"] = value

            elapsed = now_mono - self._breach_tracking[active_key]["first_breach_monotonic"]
            if elapsed < interlock.duration_seconds:
                # Debounce period has not elapsed yet
                return None

            # Debounce duration elapsed! Emit violation
            violation = SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id=interlock.interlock_id,
                interlock_type=interlock.interlock_type,
                device_id=device_id,
                zone_id=active_command.zone_id if active_command else "",
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=value,
                threshold_breached=threshold_type,
                threshold_value=threshold_val,
                action_taken=interlock.action_on_trigger.value,
                event_id_affected=(
                    active_command.source_event_id if active_command else ""
                ),
            )

            logger.warning(
                "🚨 SAFETY VIOLATION: %s on device %s — %s=%s "
                "(threshold %s=%s) → action: %s",
                interlock.interlock_type.value, device_id,
                interlock.sensor_variable, value,
                threshold_type, threshold_val,
                interlock.action_on_trigger.value,
            )

            return violation
        else:
            # Reading is valid, finite, and within nominal bounds
            # 1. Clear un-triggered debounce tracking
            self._breach_tracking.pop(active_key, None)

            # 2. Check for auto-reset qualifying condition
            if active_key in self._active_violations:
                if interlock.auto_reset and not interlock.requires_manual_reset:
                    violation = self._active_violations.pop(active_key)
                    violation.resolved_at = datetime.now(timezone.utc).isoformat()
                    violation.notes = "Auto-reset: telemetry returned to normal range"
                    logger.info(
                        "✅ Interlock %s on device %s auto-reset (value %.2f in normal range)",
                        interlock.interlock_id, device_id, value,
                    )
            return None

    def _check_duration_watchdog(self, device_id: str) -> List[SafetyViolation]:
        """Check if any active events on this device have exceeded max duration."""
        violations = []
        now_dt = datetime.now(timezone.utc)
        now_mono = self._clock()

        expired_events = []
        for event_id, info in list(self._active_events.items()):
            if info["device_id"] != device_id:
                continue

            if "start_monotonic" in info:
                elapsed = (now_mono - info["start_monotonic"]) / 60.0
            else:
                elapsed = (now_dt - info["start_time"]).total_seconds() / 60.0

            if elapsed > info["max_duration_minutes"]:
                active_key = f"INT-DURATION:{device_id}"
                if active_key in self._active_violations:
                    continue

                violation = SafetyViolation(
                    violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                    interlock_id="INT-DURATION",
                    interlock_type=InterlockType.DURATION_EXCEEDED,
                    device_id=device_id,
                    zone_id="",
                    detected_at=now_dt.isoformat(),
                    sensor_value=elapsed,
                    threshold_breached="max",
                    threshold_value=info["max_duration_minutes"],
                    action_taken=CommandType.STOP_ZONE.value,
                    event_id_affected=event_id,
                )
                violations.append(violation)
                self._active_violations[active_key] = violation
                self._violation_history.append(violation)
                expired_events.append(event_id)

                logger.warning(
                    "🚨 DURATION WATCHDOG: Event %s on device %s exceeded "
                    "max duration (%.1f > %.1f min)",
                    event_id, device_id, elapsed, info["max_duration_minutes"]
                )

                for cb in self._violation_callbacks:
                    try:
                        cb(violation)
                    except Exception as exc:
                        logger.error("Violation callback error: %s", exc)

        # R01: Do NOT remove expired events or release quota here before confirmed stop!
        # The dispatcher will attempt stop, and only on confirmed stop will quota/tracking be released.
        return violations

    # ================================================================
    # Water Quota Enforcement
    # ================================================================

    def check_water_quota(
        self,
        budget: WaterBudget,
        requested_volume_mm: float,
        event_id: Optional[str] = None,
    ) -> Optional[SafetyViolation]:
        """Check if an irrigation request would exceed water quota.

        Accounts for baseline budget limits as well as active concurrent reservations.
        """
        req_vol = finite_real(requested_volume_mm)
        if req_vol is None or req_vol < 0:
            reason = f"Invalid requested volume {requested_volume_mm}: must be a non-negative finite real number"
            violation = SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-QUOTA",
                interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                device_id="",
                zone_id="",
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=0.0,
                threshold_breached="max",
                threshold_value=0.0,
                action_taken="BLOCK",
                notes=reason,
            )
            self._violation_history.append(violation)
            return violation

        s_rem = finite_real(budget.season_remaining_mm)
        d_rem = finite_real(budget.daily_remaining_mm)
        if s_rem is None or d_rem is None:
            reason = f"Non-finite budget limits: season_remaining={budget.season_remaining_mm}, daily_remaining={budget.daily_remaining_mm}"
            violation = SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-QUOTA",
                interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                device_id="",
                zone_id="",
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=req_vol,
                threshold_breached="max",
                threshold_value=0.0,
                action_taken="BLOCK",
                notes=reason,
            )
            self._violation_history.append(violation)
            return violation

        can_irrigate, reason = budget.can_irrigate(req_vol)
        if not can_irrigate:
            violation = SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-QUOTA",
                interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                device_id="",
                zone_id="",
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=req_vol,
                threshold_breached="max",
                threshold_value=budget.season_remaining_mm if s_rem is not None else 0.0,
                action_taken="BLOCK",
                notes=reason,
            )
            logger.warning("🚨 WATER QUOTA VIOLATION: %s", reason)
            self._violation_history.append(violation)
            return violation

        # Account for concurrent uncommitted reservations and period-specific settled deliveries
        already_reserved = self.get_reserved_quota(budget.plot_id, exclude_event_id=event_id)
        today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        season_key = str(getattr(budget, "season", "default_season"))

        with SharedQuotaStore._lock():
            state = SharedQuotaStore._read_state()
            settled_today = float(state.get("settled_daily", {}).get(f"{budget.plot_id}:{today_key}", 0.0))
            settled_season = float(state.get("settled_season", {}).get(f"{budget.plot_id}:{season_key}", 0.0))

        daily_consumed = finite_real(budget.daily_consumed_mm) or 0.0
        season_consumed = finite_real(budget.season_consumed_mm) or 0.0

        untracked_daily = max(0.0, settled_today - daily_consumed)
        untracked_season = max(0.0, settled_season - season_consumed)

        effective_season_remaining = s_rem - already_reserved - untracked_season
        effective_daily_remaining = d_rem - already_reserved - untracked_daily

        if req_vol > effective_season_remaining:
            reason = (
                f"Season quota exceeded by concurrent reservations: need {req_vol:.1f}mm, "
                f"remaining unreserved {effective_season_remaining:.1f}mm "
                f"({already_reserved:.1f}mm reserved, {untracked_season:.1f}mm untracked settled)"
            )
            violation = SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-QUOTA",
                interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                device_id="",
                zone_id="",
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=req_vol,
                threshold_breached="max",
                threshold_value=effective_season_remaining,
                action_taken="BLOCK",
                notes=reason,
            )
            logger.warning("🚨 WATER QUOTA CONCURRENT VIOLATION: %s", reason)
            self._violation_history.append(violation)
            return violation

        if req_vol > effective_daily_remaining:
            reason = (
                f"Daily quota exceeded by concurrent reservations: need {req_vol:.1f}mm, "
                f"remaining unreserved {effective_daily_remaining:.1f}mm "
                f"({already_reserved:.1f}mm reserved, {untracked_daily:.1f}mm untracked settled)"
            )
            violation = SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-QUOTA",
                interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                device_id="",
                zone_id="",
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=req_vol,
                threshold_breached="max",
                threshold_value=effective_daily_remaining,
                action_taken="BLOCK",
                notes=reason,
            )
            logger.warning("🚨 WATER QUOTA CONCURRENT VIOLATION: %s", reason)
            self._violation_history.append(violation)
            return violation

        return None

    # ================================================================
    # Pre-flight Safety Assessment
    # ================================================================

    def pre_flight_check(
        self,
        command: IrrigationCommand,
        sensor_readings: Optional[Dict[str, float]] = None,
        budget: Optional[WaterBudget] = None,
    ) -> List[SafetyViolation]:
        """Comprehensive pre-dispatch safety assessment.

        Runs all checks before a command is sent to hardware:
          1. Sensor-based interlocks (frost, existing pressure issues)
          2. Water quota check (evaluated unconditionally whenever budget is provided)
          3. Environmental conditions

        Args:
            command: The command about to be dispatched
            sensor_readings: Optional latest sensor data for the zone
            budget: Optional water budget for quota enforcement

        Returns:
            List of blocking violations (empty = safe to proceed)
        """
        violations = []
        readings = sensor_readings if sensor_readings is not None else {}

        # Sensor interlocks (pre-existing conditions)
        sensor_violations = self.evaluate(
            command.device_id, readings, command
        )
        violations.extend(sensor_violations)

        # Water quota check - ALWAYS executed when budget is provided
        if budget is not None and command.volume_mm > 0:
            quota_violation = self.check_water_quota(
                budget, command.volume_mm, event_id=command.source_event_id
            )
            if quota_violation:
                violations.append(quota_violation)

        # Frost check
        air_temp = readings.get("air_temperature_c")
        if air_temp is not None and air_temp < 2.0:
            violation = SafetyViolation(
                violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                interlock_id="INT-FROST",
                interlock_type=InterlockType.FROST_RISK,
                device_id=command.device_id,
                zone_id=command.zone_id,
                detected_at=datetime.now(timezone.utc).isoformat(),
                sensor_value=air_temp,
                threshold_breached="min",
                threshold_value=2.0,
                action_taken="DEFER",
                notes=f"Air temperature {air_temp:.1f}°C — frost risk",
            )
            violations.append(violation)

        return violations

    # ================================================================
    # Resolution & Reporting
    # ================================================================

    def resolve_violation(
        self,
        identifier: str,
        acknowledged_by: str,
        notes: str = "",
    ) -> bool:
        """Mark a safety violation as resolved/acknowledged.

        Supports resolving either by violation_id (e.g. VIO-...) or active_key (e.g. INT-PRESSURE-HIGH:DEV-01).
        """
        matched_key = None
        violation = None

        if identifier in self._active_violations:
            matched_key = identifier
            violation = self._active_violations.pop(identifier)
        else:
            for k, v in self._active_violations.items():
                if v.violation_id == identifier:
                    matched_key = k
                    violation = self._active_violations.pop(k)
                    break

        if violation is None:
            return False

        if matched_key:
            self._breach_tracking.pop(matched_key, None)

        violation.resolved_at = datetime.now(timezone.utc).isoformat()
        violation.acknowledged_by = acknowledged_by
        violation.acknowledged_at = violation.resolved_at
        violation.notes = notes

        logger.info("Violation %s resolved by %s", violation.violation_id, acknowledged_by)
        return True

    def rehydrate_active_violations(
        self,
        violations: List[SafetyViolation],
    ) -> None:
        """Rehydrate active violations on process restart."""
        for v in violations:
            if not v.resolved_at:
                active_key = f"{v.interlock_id}:{v.device_id}"
                self._active_violations[active_key] = v
                if v not in self._violation_history:
                    self._violation_history.append(v)

    def get_active_violations(self) -> List[SafetyViolation]:
        """Get all unresolved safety violations."""
        return list(self._active_violations.values())

    def get_violation_history(
        self,
        device_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[SafetyViolation]:
        """Get historical violations, optionally filtered by device."""
        history = self._violation_history
        if device_id:
            history = [v for v in history if v.device_id == device_id]
        return history[-limit:]

    def get_safety_score(self) -> float:
        """Compute a 0-1 safety score for the irrigation system.

        1.0 = no violations, all systems nominal
        0.0 = critical violations present
        """
        active = len(self._active_violations)
        if active == 0:
            return 1.0

        critical_types = {
            InterlockType.PRESSURE_LOW,
            InterlockType.PRESSURE_HIGH,
            InterlockType.ELECTRICAL_FAULT,
        }
        critical_count = sum(
            1 for v in self._active_violations.values()
            if v.interlock_type in critical_types
        )

        if critical_count > 0:
            return 0.0

        # Degrade linearly for non-critical violations
        return max(0.0, 1.0 - (active * 0.2))


# Singleton
safety_monitor = SafetyMonitor()
