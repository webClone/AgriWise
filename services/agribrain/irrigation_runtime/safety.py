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

import copy
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


def _check_area_conflict(a1: Any, a2: Any) -> bool:
    v1 = finite_real(a1)
    v2 = finite_real(a2)
    if (v1 is None) != (v2 is None):
        return True
    if v1 is not None and v2 is not None:
        return abs(v1 - v2) > 1e-4
    return False


def _validate_writer_scalars(
    volume_mm: Any = 0.0,
    duration_minutes: Any = None,
    flow_rate_lpm: Any = None,
    effective_area_ha: Any = None,
) -> None:
    """RC07: Strictly validate input scalar parameters before mutating store state or writing candidate."""
    if volume_mm is not None:
        if isinstance(volume_mm, bool):
            raise ValueError(f"Invalid volume_mm {volume_mm}: booleans are not valid numeric volumes")
        v = finite_real(volume_mm)
        if v is None or v < 0:
            raise ValueError(f"Invalid volume_mm {volume_mm}: must be a non-negative finite real number")
    if duration_minutes is not None:
        if isinstance(duration_minutes, bool):
            raise ValueError(f"Invalid duration_minutes {duration_minutes}: booleans are not valid numeric durations")
        d = finite_real(duration_minutes)
        if d is None or d < 0:
            raise ValueError(f"Invalid duration_minutes {duration_minutes}: must be a non-negative finite real number")
    if flow_rate_lpm is not None:
        if isinstance(flow_rate_lpm, bool):
            raise ValueError(f"Invalid flow_rate_lpm {flow_rate_lpm}: booleans are not valid numeric flow rates")
        f = finite_real(flow_rate_lpm)
        if f is None or f < 0:
            raise ValueError(f"Invalid flow_rate_lpm {flow_rate_lpm}: must be a non-negative finite real number")
    if effective_area_ha is not None:
        if isinstance(effective_area_ha, (bool, str)):
            raise ValueError(f"Invalid effective_area_ha {effective_area_ha}: booleans and strings are not valid numeric areas")
        a = finite_real(effective_area_ha)
        if a is None or a <= 0:
            raise ValueError(f"Invalid effective_area_ha {effective_area_ha}: must be a positive finite real number")


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
    def _established_marker_file(cls) -> Path:
        return cls._store_file().with_name(".quota_store.established")

    @classmethod
    def _validate_state(cls, data: Dict[str, Any]) -> None:
        required_keys = {"reservations", "settled_receipts", "settled_daily", "settled_season", "settled_plot_total"}
        if not required_keys.issubset(data.keys()):
            raise CorruptedQuotaStoreError("Quota store missing required keys")
        for k in required_keys:
            if not isinstance(data[k], dict):
                raise CorruptedQuotaStoreError(f"Quota store key '{k}' must be a dictionary, got {type(data[k]).__name__}")
        if "stopped_receipts" in data and not isinstance(data["stopped_receipts"], dict):
            raise CorruptedQuotaStoreError("Quota store key 'stopped_receipts' must be a dictionary")

        # C03 + D04: Validate all nested records and scalar types (reject booleans, NaNs, infinities, and negatives)
        for eid, res in data["reservations"].items():
            if not isinstance(res, dict):
                raise CorruptedQuotaStoreError(f"Reservation '{eid}' must be a dictionary")
            vol = res.get("volume_mm")
            if isinstance(vol, bool) or not isinstance(vol, (int, float)) or not math.isfinite(vol) or vol < 0:
                raise CorruptedQuotaStoreError(f"Reservation '{eid}' has invalid volume_mm: {vol}")
            dur = res.get("duration_minutes")
            if dur is not None and (isinstance(dur, bool) or not isinstance(dur, (int, float)) or not math.isfinite(dur) or dur < 0):
                raise CorruptedQuotaStoreError(f"Reservation '{eid}' has invalid duration_minutes: {dur}")
            flow = res.get("flow_rate_lpm")
            if flow is not None and (isinstance(flow, bool) or not isinstance(flow, (int, float)) or not math.isfinite(flow) or flow < 0):
                raise CorruptedQuotaStoreError(f"Reservation '{eid}' has invalid flow_rate_lpm: {flow}")
            area = res.get("effective_area_ha")
            if area is not None and (isinstance(area, bool) or not isinstance(area, (int, float)) or not math.isfinite(area) or area <= 0):
                raise CorruptedQuotaStoreError(f"Reservation '{eid}' has invalid effective_area_ha: {area}")

            # XR05: Validate new target_volume_mm, delivered_volume_mm, and effective_exposure_mm
            tvol = res.get("target_volume_mm")
            if tvol is not None:
                if isinstance(tvol, bool) or not isinstance(tvol, (int, float)) or not math.isfinite(tvol) or tvol < 0:
                    raise CorruptedQuotaStoreError(f"Reservation '{eid}' has invalid target_volume_mm: {tvol}")
            dvol = res.get("delivered_volume_mm")
            if dvol is not None:
                if isinstance(dvol, bool) or not isinstance(dvol, (int, float)) or not math.isfinite(dvol) or dvol < 0:
                    raise CorruptedQuotaStoreError(f"Reservation '{eid}' has invalid delivered_volume_mm: {dvol}")
            exp = res.get("effective_exposure_mm")
            if exp is not None:
                if isinstance(exp, bool) or not isinstance(exp, (int, float)) or not math.isfinite(exp) or exp < 0:
                    raise CorruptedQuotaStoreError(f"Reservation '{eid}' has invalid effective_exposure_mm: {exp}")

            # Conservation lower bound: exposure and volume must be >= max(target_volume_mm, delivered_volume_mm)
            min_exp = max(float(tvol or 0.0), float(dvol or 0.0))
            if min_exp > 0:
                if exp is not None and exp < min_exp - 1e-4:
                    raise CorruptedQuotaStoreError(f"Reservation '{eid}' effective_exposure_mm={exp} violates lower bound {min_exp}")
                if vol is not None and vol < min_exp - 1e-4:
                    raise CorruptedQuotaStoreError(f"Reservation '{eid}' volume_mm={vol} violates lower bound {min_exp}")

        for eid, rec in data["settled_receipts"].items():
            if not isinstance(rec, dict):
                raise CorruptedQuotaStoreError(f"Settled receipt '{eid}' must be a dictionary")
            vol = rec.get("volume_mm")
            if isinstance(vol, bool) or not isinstance(vol, (int, float)) or not math.isfinite(vol) or vol < 0:
                raise CorruptedQuotaStoreError(f"Settled receipt '{eid}' has invalid volume_mm: {vol}")
            if "delivered_volume_mm" in rec:
                dvol = rec["delivered_volume_mm"]
                if isinstance(dvol, bool) or not isinstance(dvol, (int, float)) or not math.isfinite(dvol) or dvol < 0:
                    raise CorruptedQuotaStoreError(f"Settled receipt '{eid}' has invalid delivered_volume_mm: {dvol}")
                if abs(float(dvol) - float(vol)) > 1e-4:
                    raise CorruptedQuotaStoreError(f"Settled receipt '{eid}' delivered_volume_mm={dvol} contradicts volume_mm={vol}")
            if "target_volume_mm" in rec:
                tvol = rec["target_volume_mm"]
                if isinstance(tvol, bool) or not isinstance(tvol, (int, float)) or not math.isfinite(tvol) or tvol < 0:
                    raise CorruptedQuotaStoreError(f"Settled receipt '{eid}' has invalid target_volume_mm: {tvol}")
            if "actual_volume_l" in rec:
                avl = rec["actual_volume_l"]
                if avl is not None and (isinstance(avl, bool) or not isinstance(avl, (int, float)) or not math.isfinite(avl) or avl < 0):
                    raise CorruptedQuotaStoreError(f"Settled receipt '{eid}' has invalid actual_volume_l: {avl}")
            if "actual_duration_minutes" in rec:
                adur = rec["actual_duration_minutes"]
                if adur is not None and (isinstance(adur, bool) or not isinstance(adur, (int, float)) or not math.isfinite(adur) or adur < 0):
                    raise CorruptedQuotaStoreError(f"Settled receipt '{eid}' has invalid actual_duration_minutes: {adur}")
            dur = rec.get("duration_minutes")
            if dur is not None and (isinstance(dur, bool) or not isinstance(dur, (int, float)) or not math.isfinite(dur) or dur < 0):
                raise CorruptedQuotaStoreError(f"Settled receipt '{eid}' has invalid duration_minutes: {dur}")
            flow = rec.get("flow_rate_lpm")
            if flow is not None and (isinstance(flow, bool) or not isinstance(flow, (int, float)) or not math.isfinite(flow) or flow < 0):
                raise CorruptedQuotaStoreError(f"Settled receipt '{eid}' has invalid flow_rate_lpm: {flow}")
            area = rec.get("effective_area_ha")
            if area is not None and (isinstance(area, bool) or not isinstance(area, (int, float)) or not math.isfinite(area) or area <= 0):
                raise CorruptedQuotaStoreError(f"Settled receipt '{eid}' has invalid effective_area_ha: {area}")

        for eid, srec in data.get("stopped_receipts", {}).items():
            if not isinstance(srec, dict):
                raise CorruptedQuotaStoreError(f"Stopped receipt '{eid}' must be a dictionary")
            dvol = srec.get("delivered_volume_mm")
            if isinstance(dvol, bool) or not isinstance(dvol, (int, float)) or not math.isfinite(dvol) or dvol < 0:
                raise CorruptedQuotaStoreError(f"Stopped receipt '{eid}' has invalid delivered_volume_mm: {dvol}")
            tvol = srec.get("target_volume_mm")
            if tvol is not None and (isinstance(tvol, bool) or not isinstance(tvol, (int, float)) or not math.isfinite(tvol) or tvol < 0):
                raise CorruptedQuotaStoreError(f"Stopped receipt '{eid}' has invalid target_volume_mm: {tvol}")
            dur = srec.get("duration_minutes")
            if dur is not None and (isinstance(dur, bool) or not isinstance(dur, (int, float)) or not math.isfinite(dur) or dur < 0):
                raise CorruptedQuotaStoreError(f"Stopped receipt '{eid}' has invalid duration_minutes: {dur}")
            flow = srec.get("flow_rate_lpm")
            if flow is not None and (isinstance(flow, bool) or not isinstance(flow, (int, float)) or not math.isfinite(flow) or flow < 0):
                raise CorruptedQuotaStoreError(f"Stopped receipt '{eid}' has invalid flow_rate_lpm: {flow}")
            area = srec.get("effective_area_ha")
            if area is not None and (isinstance(area, bool) or not isinstance(area, (int, float)) or not math.isfinite(area) or area <= 0):
                raise CorruptedQuotaStoreError(f"Stopped receipt '{eid}' has invalid effective_area_ha: {area}")

        for agg_key in ("settled_daily", "settled_season", "settled_plot_total"):
            for k, v in data[agg_key].items():
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                    raise CorruptedQuotaStoreError(f"Aggregate '{agg_key}' key '{k}' has invalid amount: {v}")

        # D04 & N03: Two-way aggregate reconciliation over the union of keys
        expected_daily: Dict[str, float] = {}
        expected_season: Dict[str, float] = {}
        expected_plot: Dict[str, float] = {}

        for rec in data["settled_receipts"].values():
            p = rec.get("plot_id", "")
            d = rec.get("date", "")
            s = rec.get("season", "default_season")
            v = float(rec.get("volume_mm", 0.0))
            if v > 0:
                if p and d:
                    expected_daily[f"{p}:{d}"] = expected_daily.get(f"{p}:{d}", 0.0) + v
                if p and s:
                    expected_season[f"{p}:{s}"] = expected_season.get(f"{p}:{s}", 0.0) + v
                if p:
                    expected_plot[p] = expected_plot.get(p, 0.0) + v

        for srec in data.get("stopped_receipts", {}).values():
            p = srec.get("plot_id", "")
            d = srec.get("date", "")
            s = srec.get("season", "default_season")
            v = float(srec.get("delivered_volume_mm", 0.0))
            if v > 0:
                if p and d:
                    expected_daily[f"{p}:{d}"] = expected_daily.get(f"{p}:{d}", 0.0) + v
                if p and s:
                    expected_season[f"{p}:{s}"] = expected_season.get(f"{p}:{s}", 0.0) + v
                if p:
                    expected_plot[p] = expected_plot.get(p, 0.0) + v

        all_daily_keys = set(expected_daily.keys()) | set(data["settled_daily"].keys())
        for k in all_daily_keys:
            exp_val = expected_daily.get(k, 0.0)
            act_val = float(data["settled_daily"].get(k, 0.0))
            if abs(exp_val - act_val) > 1e-4:
                raise CorruptedQuotaStoreError(f"Aggregate settled_daily[{k}]={act_val} contradicts receipts sum {exp_val}")

        all_season_keys = set(expected_season.keys()) | set(data["settled_season"].keys())
        for k in all_season_keys:
            exp_val = expected_season.get(k, 0.0)
            act_val = float(data["settled_season"].get(k, 0.0))
            if abs(exp_val - act_val) > 1e-4:
                raise CorruptedQuotaStoreError(f"Aggregate settled_season[{k}]={act_val} contradicts receipts sum {exp_val}")

        all_plot_keys = set(expected_plot.keys()) | set(data["settled_plot_total"].keys())
        for p in all_plot_keys:
            exp_val = expected_plot.get(p, 0.0)
            act_val = float(data["settled_plot_total"].get(p, 0.0))
            if abs(exp_val - act_val) > 1e-4:
                raise CorruptedQuotaStoreError(f"Aggregate settled_plot_total[{p}]={act_val} contradicts receipts sum {exp_val}")

        if "receipt_journal" in data and not isinstance(data["receipt_journal"], list):
            raise CorruptedQuotaStoreError("Quota store key 'receipt_journal' must be a list")

    @classmethod
    def _read_state(cls) -> Dict[str, Any]:
        p = cls._store_file()
        marker = cls._established_marker_file()
        if not p.exists():
            # C03: If established marker exists but the file is gone, the store was deleted/lost!
            if marker.exists():
                raise CorruptedQuotaStoreError(f"Established quota store file {p} has disappeared/deleted while established marker exists")
            return {
                "reservations": {},
                "settled_receipts": {},
                "settled_daily": {},
                "settled_season": {},
                "settled_plot_total": {},
                "stopped_receipts": {},
                "receipt_journal": [],
            }

        def _reject_constant(c: str) -> None:
            raise ValueError(f"Non-finite JSON constant not allowed: {c}")

        try:
            content = p.read_text(encoding="utf-8")
            if not content.strip():
                raise CorruptedQuotaStoreError(f"Quota store file {p} is empty or blank")
            data = json.loads(content, parse_constant=_reject_constant)
            if not isinstance(data, dict):
                raise CorruptedQuotaStoreError(f"Quota store file {p} is not a JSON object: got {type(data).__name__}")
            cls._validate_state(data)
            data.setdefault("receipt_journal", [])
            return data
        except CorruptedQuotaStoreError:
            raise
        except Exception as exc:
            raise CorruptedQuotaStoreError(f"Quota store file {p} is malformed or unreadable: {exc}") from exc

    @classmethod
    def _write_state(cls, state: Dict[str, Any]) -> None:
        p = cls._store_file()
        marker = cls._established_marker_file()
        tmp = p.with_suffix(f".{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp")
        try:
            with tmp.open("w", encoding="utf-8") as handle:
                # RV06: Disallow non-finite JSON constants
                json.dump(state, handle, sort_keys=True, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            for attempt in range(5):
                try:
                    os.replace(tmp, p)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.02)
            # C03 + D04: Mark established so store disappearance cannot silently reset to zero.
            # Do NOT swallow exceptions on marker write!
            if not marker.exists():
                marker.write_text("established", encoding="utf-8")
        finally:
            tmp.unlink(missing_ok=True)

    @classmethod
    def reset(cls) -> None:
        with cls._lock():
            # Clean up established marker so fresh resets start clean
            try:
                cls._established_marker_file().unlink(missing_ok=True)
            except Exception:
                pass
            state = {
                "reservations": {},
                "settled_receipts": {},
                "settled_daily": {},
                "settled_season": {},
                "settled_plot_total": {},
                "stopped_receipts": {},
                "receipt_journal": [],
            }
            cls._write_state(state)

    @classmethod
    def atomic_check_and_reserve(
        cls,
        plot_id: str,
        requested_volume_mm: float,
        budget: Optional[WaterBudget] = None,
        event_id: str = "",
        device_id: str = "",
        zone_id: str = "",
        duration_minutes: float = 0.0,
        owner_token: str = "",
        flow_rate_lpm: float = 0.0,
        effective_area_ha: Optional[float] = None,
    ) -> Optional[SafetyViolation]:
        """Atomically validate budget and reserve quota under a cross-process lock (D05 + D06)."""
        # RC07: Strictly validate all scalar inputs before mutating state or checking budget
        _validate_writer_scalars(
            volume_mm=requested_volume_mm,
            duration_minutes=duration_minutes,
            flow_rate_lpm=flow_rate_lpm,
            effective_area_ha=effective_area_ha,
        )

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

        if budget is not None:
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
        else:
            s_rem = None
            d_rem = None

        e_dur = finite_real(duration_minutes)
        e_flow = finite_real(flow_rate_lpm)
        e_area = finite_real(effective_area_ha)

        try:
            with cls._lock():
                state = cls._read_state()

                # C05 + D06: Stopped receipts check
                stopped_receipts = state.get("stopped_receipts", {})
                if event_id in stopped_receipts:
                    srec = stopped_receipts[event_id]
                    s_target = finite_real(srec.get("target_volume_mm", 0.0))
                    s_plot = srec.get("plot_id", "")
                    s_dev = srec.get("device_id", "")
                    s_zone = srec.get("zone_id", "")
                    s_dur = finite_real(srec.get("duration_minutes"))
                    s_flow = finite_real(srec.get("flow_rate_lpm"))
                    s_area = finite_real(srec.get("effective_area_ha"))
                    is_conflict = (
                        (s_target is not None and abs(s_target - req_vol) > 1e-4)
                        or (bool(s_plot) and bool(plot_id) and s_plot != plot_id)
                        or (bool(device_id) and bool(s_dev) and s_dev != device_id)
                        or (bool(zone_id) and bool(s_zone) and s_zone != zone_id)
                        or (s_dur is not None and e_dur is not None and abs(s_dur - e_dur) > 1e-4)
                        or (s_flow is not None and e_flow is not None and abs(s_flow - e_flow) > 1e-4)
                        or _check_area_conflict(s_area, e_area)
                    )
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
                            threshold_value=s_target or 0.0,
                            action_taken="BLOCK",
                            notes=f"Payload conflict with stopped receipt: event {event_id}",
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
                        threshold_value=s_target or 0.0,
                        action_taken="ALREADY_STOPPED",
                        notes=f"Event {event_id} already stopped/cancelled",
                    )

                # C09 + D06: Settled receipts check (compare against commanded target, not delivered volume!)
                settled_receipts = state.get("settled_receipts", {})
                if event_id in settled_receipts:
                    rec = settled_receipts[event_id]
                    rec_target = finite_real(rec.get("target_volume_mm", rec.get("volume_mm", 0.0)))
                    rec_plot = rec.get("plot_id", "")
                    rec_dev = rec.get("device_id", "")
                    rec_zone = rec.get("zone_id", "")
                    rec_dur = finite_real(rec.get("duration_minutes"))
                    rec_flow = finite_real(rec.get("flow_rate_lpm"))
                    rec_area = finite_real(rec.get("effective_area_ha"))
                    is_conflict = (
                        (rec_target is not None and abs(rec_target - req_vol) > 1e-4)
                        or (bool(rec_plot) and bool(plot_id) and rec_plot != plot_id)
                        or (bool(device_id) and bool(rec_dev) and rec_dev != device_id)
                        or (bool(zone_id) and bool(rec_zone) and rec_zone != zone_id)
                        or (rec_dur is not None and e_dur is not None and abs(rec_dur - e_dur) > 1e-4)
                        or (rec_flow is not None and e_flow is not None and abs(rec_flow - e_flow) > 1e-4)
                        or _check_area_conflict(rec_area, e_area)
                    )
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
                            threshold_value=rec_target or 0.0,
                            action_taken="BLOCK",
                            notes=f"Payload conflict with settled receipt: event {event_id} already settled with target {rec_target}mm vs requested {req_vol}mm",
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
                        threshold_value=rec_target or 0.0,
                        action_taken="ALREADY_SETTLED",
                        notes=f"Event {event_id} already settled",
                    )

                # C06 + D06: Active reservation check with full payload binding (volume, duration, flow, zone, plot, device, area)
                reservations = state.get("reservations", {})
                if event_id in reservations:
                    res = reservations[event_id]
                    # NR02: Payload comparison binds to commanded target_volume_mm rather than effective exposure volume_mm
                    res_vol = finite_real(res.get("target_volume_mm", res.get("volume_mm", 0.0)))
                    res_plot = res.get("plot_id", "")
                    res_dev = res.get("device_id", "")
                    res_zone = res.get("zone_id", "")
                    res_dur = finite_real(res.get("duration_minutes"))
                    res_flow = finite_real(res.get("flow_rate_lpm"))
                    res_area = finite_real(res.get("effective_area_ha"))
                    is_conflict = (
                        (res_vol is not None and abs(res_vol - req_vol) > 1e-4)
                        or (bool(res_plot) and bool(plot_id) and res_plot != plot_id)
                        or (bool(device_id) and bool(res_dev) and res_dev != device_id)
                        or (bool(zone_id) and bool(res_zone) and res_zone != zone_id)
                        or (res_dur is not None and e_dur is not None and abs(res_dur - e_dur) > 1e-4)
                        or (res_flow is not None and e_flow is not None and abs(res_flow - e_flow) > 1e-4)
                        or _check_area_conflict(res_area, e_area)
                    )
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
                            threshold_value=res_vol or 0.0,
                            action_taken="BLOCK",
                            notes=f"Payload conflict with active reservation: event {event_id}",
                        )
                    # Concurrent identical operation already claimed
                    return SafetyViolation(
                        violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                        interlock_id="INT-QUOTA",
                        interlock_type=InterlockType.WATER_QUOTA_EXCEEDED,
                        device_id=device_id,
                        zone_id=zone_id,
                        detected_at=datetime.now(timezone.utc).isoformat(),
                        sensor_value=req_vol,
                        threshold_breached="max",
                        threshold_value=res_vol or 0.0,
                        action_taken="ALREADY_RESERVED",
                        notes=f"Event {event_id} already reserved by concurrent worker",
                    )



                today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                season_key = str(getattr(budget, "season", "default_season")) if budget else "default_season"

                # If budget is provided, enforce concurrent quota conservation
                if budget is not None and s_rem is not None and d_rem is not None:
                    already_reserved = 0.0
                    for eid, res in reservations.items():
                        if eid != event_id and res.get("plot_id") == plot_id:
                            already_reserved += float(res.get("effective_exposure_mm", res.get("volume_mm", 0.0)))

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

                # D05 + D06, RV08: Claim operation atomically EVEN IF req_vol == 0.0 OR budget is None!
                now_iso = datetime.now(timezone.utc).isoformat()
                reservations[event_id] = {
                    "plot_id": plot_id,
                    "device_id": device_id,
                    "zone_id": zone_id,
                    "volume_mm": req_vol,
                    "target_volume_mm": req_vol,
                    "effective_exposure_mm": req_vol,
                    "duration_minutes": e_dur if e_dur is not None else 0.0,
                    "flow_rate_lpm": e_flow if e_flow is not None else 0.0,
                    "effective_area_ha": e_area if (e_area is not None and e_area > 0) else None,
                    "status": "DISPATCHING",
                    "date": today_key,
                    "season": season_key,
                    "owner_token": owner_token,
                    "first_dispatched_at": now_iso,
                    "timestamp": now_iso,
                }
                # RV08: Append admission to receipt_journal for all operations (including req_vol == 0.0)
                state.setdefault("receipt_journal", []).append({
                    "entry_id": f"j_{event_id}_{len(state.get('receipt_journal', [])) + 1}",
                    "type": "RESERVATION",
                    "event_id": event_id,
                    "plot_id": plot_id,
                    "volume_mm": req_vol,
                    "target_volume_mm": req_vol,
                    "effective_exposure_mm": req_vol,
                    "device_id": device_id,
                    "zone_id": zone_id,
                    "duration_minutes": e_dur if e_dur is not None else 0.0,
                    "flow_rate_lpm": e_flow if e_flow is not None else 0.0,
                    "effective_area_ha": e_area if (e_area is not None and e_area > 0) else None,
                    "date": today_key,
                    "season": season_key,
                    "timestamp": now_iso,
                })
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
        flow_rate_lpm: float = 0.0,
        effective_area_ha: Optional[float] = None,
    ) -> None:
        # RC07: Strictly validate input scalar parameters before mutating store state
        _validate_writer_scalars(
            volume_mm=volume_mm,
            duration_minutes=duration_minutes,
            flow_rate_lpm=flow_rate_lpm,
            effective_area_ha=effective_area_ha,
        )
        val = finite_real(volume_mm)
        if val is None or val < 0:
            return
        with cls._lock():
            state = cls._read_state()
            today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            # NR04: Enforce terminal/reservation transition semantics at writer boundary
            settled_receipts = state.get("settled_receipts", {})
            if event_id in settled_receipts:
                s_rcpt = settled_receipts[event_id]
                s_plot = s_rcpt.get("plot_id", "")
                if s_plot and plot_id and s_plot != plot_id:
                    raise ValueError(f"Payload conflict: event {event_id} already settled on plot {s_plot}, cannot rebind to {plot_id}")
                s_target = finite_real(s_rcpt.get("target_volume_mm", s_rcpt.get("volume_mm")))
                if s_target is not None and val is not None and abs(s_target - val) > 1e-4:
                    raise ValueError(f"Payload conflict: event {event_id} already settled with target {s_target}mm vs requested {val}mm")
                # Compatible retry of already settled event: do not create phantom active reservation!
                return

            stopped_receipts = state.get("stopped_receipts", {})
            if event_id in stopped_receipts:
                st_rcpt = stopped_receipts[event_id]
                st_plot = st_rcpt.get("plot_id", "")
                if st_plot and plot_id and st_plot != plot_id:
                    raise ValueError(f"Payload conflict: event {event_id} already stopped on plot {st_plot}, cannot rebind to {plot_id}")
                st_target = finite_real(st_rcpt.get("target_volume_mm", st_rcpt.get("volume_mm")))
                if st_target is not None and val is not None and abs(st_target - val) > 1e-4:
                    raise ValueError(f"Payload conflict: event {event_id} already stopped with target {st_target}mm vs requested {val}mm")
                # Compatible retry of already stopped event: do not create phantom active reservation!
                return

            existing = state.setdefault("reservations", {}).get(event_id, {})
            # RC03, BV04: Prevent rebinding reservation to conflicting plot or mutating admitted envelope
            if existing.get("plot_id") and existing["plot_id"] != plot_id:
                raise ValueError(f"Payload conflict: event {event_id} already reserved on plot {existing['plot_id']}, cannot rebind to {plot_id}")
            if existing.get("volume_mm") is not None:
                val = float(existing["volume_mm"])
            season_key = existing.get("season") or season or "default_season"
            date_key = existing.get("date") or date or today_key
            dev_id = existing.get("device_id") or device_id or ""
            z_id = existing.get("zone_id") or zone_id or ""
            r_dur = existing.get("duration_minutes") if existing.get("duration_minutes") is not None else (finite_real(duration_minutes) or 0.0)
            r_flow = existing.get("flow_rate_lpm") if existing.get("flow_rate_lpm") is not None else (finite_real(flow_rate_lpm) or 0.0)
            r_area = existing.get("effective_area_ha") if "effective_area_ha" in existing else (finite_real(effective_area_ha) if (effective_area_ha is not None and not isinstance(effective_area_ha, (bool, str)) and finite_real(effective_area_ha) > 0) else None)
            now_iso = datetime.now(timezone.utc).isoformat()
            f_disp = existing.get("first_dispatched_at") or now_iso
            act_start = existing.get("actual_start")
            ex_target = existing.get("target_volume_mm")
            ex_del = existing.get("delivered_volume_mm")
            ex_exp = existing.get("effective_exposure_mm")
            res_entry = {
                "plot_id": plot_id,
                "device_id": dev_id,
                "zone_id": z_id,
                "volume_mm": val,
                "duration_minutes": r_dur if r_dur is not None else 0.0,
                "flow_rate_lpm": r_flow if r_flow is not None else 0.0,
                "effective_area_ha": r_area,
                "status": existing.get("status", "RESERVED"),
                "date": date_key,
                "season": season_key,
                "first_dispatched_at": f_disp,
                "timestamp": now_iso,
            }
            if ex_target is not None:
                res_entry["target_volume_mm"] = ex_target
            elif existing.get("volume_mm") is not None:
                res_entry["target_volume_mm"] = float(existing["volume_mm"])
            else:
                res_entry["target_volume_mm"] = val

            if ex_del is not None:
                res_entry["delivered_volume_mm"] = ex_del

            if ex_exp is not None:
                res_entry["effective_exposure_mm"] = ex_exp
                res_entry["volume_mm"] = ex_exp
            elif ex_del is not None and float(ex_del) > val:
                res_entry["effective_exposure_mm"] = float(ex_del)
                res_entry["volume_mm"] = float(ex_del)

            if act_start:
                res_entry["actual_start"] = act_start
            state["reservations"][event_id] = res_entry

            # RV08: Check if RESERVATION entry already exists in receipt_journal to avoid duplicate entries
            journal = state.setdefault("receipt_journal", [])
            has_res_journal = any(
                entry.get("event_id") == event_id and entry.get("type") == "RESERVATION"
                for entry in journal
            )
            if not has_res_journal:
                journal.append({
                    "entry_id": f"j_{event_id}_{len(journal) + 1}",
                    "type": "RESERVATION",
                    "event_id": event_id,
                    "plot_id": plot_id,
                    "volume_mm": val,
                    "device_id": device_id or existing.get("device_id", ""),
                    "zone_id": zone_id or existing.get("zone_id", ""),
                    "duration_minutes": r_dur if r_dur is not None else 0.0,
                    "flow_rate_lpm": r_flow if r_flow is not None else 0.0,
                    "effective_area_ha": r_area,
                    "date": date_key,
                    "season": season_key,
                    "timestamp": now_iso,
                })
            cls._write_state(state)

    @classmethod
    def set_actual_start(cls, event_id: str, actual_start: str) -> None:
        """RV03, RC04: Persist actual start timestamp for active reservation without permitting advancing established start."""
        with cls._lock():
            state = cls._read_state()
            if event_id in state.get("reservations", {}):
                cur = state["reservations"][event_id].get("actual_start")
                if cur:
                    try:
                        cur_dt = datetime.fromisoformat(cur)
                        new_dt = datetime.fromisoformat(actual_start)
                        if new_dt > cur_dt:
                            return  # Established start cannot advance
                    except Exception:
                        return
                state["reservations"][event_id]["actual_start"] = actual_start
                cls._write_state(state)

    @classmethod
    def update_status(cls, event_id: str, new_status: str, actual_start: Optional[str] = None) -> None:
        """C07, RV03, RC04: Update active operation phase and actual_start in shared store."""
        with cls._lock():
            state = cls._read_state()
            if event_id in state.get("reservations", {}):
                cur_status = state["reservations"][event_id].get("status")
                # RP01: If current status is STOP_REQUESTED, a late ACK promotion to EXECUTING must not erase stop intent
                if cur_status == "STOP_REQUESTED" and new_status == "EXECUTING":
                    return
                state["reservations"][event_id]["status"] = new_status
                if new_status in ("STOP_REQUESTED", "CANCELLED", "COMPLETED", "SETTLED", "FAILED"):
                    state["reservations"][event_id]["claimed"] = False
                elif new_status in ("STARTING", "EXECUTING"):
                    state["reservations"][event_id]["claimed"] = True
                if actual_start:
                    cur = state["reservations"][event_id].get("actual_start")
                    if cur:
                        try:
                            cur_dt = datetime.fromisoformat(cur)
                            new_dt = datetime.fromisoformat(actual_start)
                            if new_dt <= cur_dt:
                                state["reservations"][event_id]["actual_start"] = actual_start
                        except Exception:
                            pass
                    else:
                        state["reservations"][event_id]["actual_start"] = actual_start
                cls._write_state(state)

    @classmethod
    def mark_unsettled(cls, event_id: str) -> None:
        """Mark an active reservation as pending validation/settlement without releasing quota (D07)."""
        with cls._lock():
            state = cls._read_state()
            reservations = state.get("reservations", {})
            if event_id in reservations:
                reservations[event_id]["status"] = "VALIDATING"
                reservations[event_id]["accounting_status"] = "UNSETTLED"
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
        target_volume_mm: Optional[float] = None,
        actual_volume_l: Optional[float] = None,
        actual_duration_minutes: Optional[float] = None,
        date: Optional[str] = None,
        season: Optional[str] = None,
        device_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        duration_minutes: Optional[float] = None,
        flow_rate_lpm: Optional[float] = None,
        effective_area_ha: Optional[float] = None,
    ) -> None:
        # C08 & N03 & RV06: Strictly validate all scalar parameters BEFORE modifying any state
        val = finite_real(volume_mm)
        if val is None or val < 0:
            raise ValueError(f"Invalid settlement volume {volume_mm}: must be a non-negative finite real number")
        if actual_volume_l is not None:
            if isinstance(actual_volume_l, bool) or not isinstance(actual_volume_l, (int, float)) or not math.isfinite(actual_volume_l) or actual_volume_l < 0:
                raise ValueError(f"Invalid actual_volume_l {actual_volume_l}: must be a non-negative finite real number")
        if actual_duration_minutes is not None:
            if isinstance(actual_duration_minutes, bool) or not isinstance(actual_duration_minutes, (int, float)) or not math.isfinite(actual_duration_minutes) or actual_duration_minutes < 0:
                raise ValueError(f"Invalid actual_duration_minutes {actual_duration_minutes}: must be a non-negative finite real number")
        if target_volume_mm is not None:
            if isinstance(target_volume_mm, bool) or not isinstance(target_volume_mm, (int, float)) or not math.isfinite(target_volume_mm) or target_volume_mm < 0:
                raise ValueError(f"Invalid target_volume_mm {target_volume_mm}: must be a non-negative finite real number")
        if duration_minutes is not None:
            if isinstance(duration_minutes, bool) or not isinstance(duration_minutes, (int, float)) or not math.isfinite(duration_minutes) or duration_minutes < 0:
                raise ValueError(f"Invalid duration_minutes {duration_minutes}: must be a non-negative finite real number")
        if flow_rate_lpm is not None:
            if isinstance(flow_rate_lpm, bool) or not isinstance(flow_rate_lpm, (int, float)) or not math.isfinite(flow_rate_lpm) or flow_rate_lpm < 0:
                raise ValueError(f"Invalid flow_rate_lpm {flow_rate_lpm}: must be a non-negative finite real number")
        if effective_area_ha is not None:
            if isinstance(effective_area_ha, bool) or not isinstance(effective_area_ha, (int, float)) or not math.isfinite(effective_area_ha) or effective_area_ha <= 0:
                raise ValueError(f"Invalid effective_area_ha {effective_area_ha}: must be a positive finite real number")

        with cls._lock():
            state = cls._read_state()
            settled_receipts = state.setdefault("settled_receipts", {})
            if event_id in settled_receipts:
                # D08 Probe C & N04, PB06, RP04, ER05: Verify retry compatibility across all envelope and measurement dimensions!
                existing = settled_receipts[event_id]
                ex_target = float(existing.get("target_volume_mm", existing.get("volume_mm", 0.0)))
                ex_del = float(existing.get("delivered_volume_mm", existing.get("volume_mm", 0.0)))
                ex_plot = existing.get("plot_id", "")
                ex_dur = finite_real(existing.get("duration_minutes"))
                ex_flow = finite_real(existing.get("flow_rate_lpm"))
                ex_area = finite_real(existing.get("effective_area_ha"))
                ex_avl = finite_real(existing.get("actual_volume_l"))
                ex_adur = finite_real(existing.get("actual_duration_minutes"))
                ex_dev = existing.get("device_id", "")
                ex_zone = existing.get("zone_id", "")
                ex_date = existing.get("date", "")
                ex_season = existing.get("season", "")

                caller_input = existing.get("caller_input", {})

                # PB06, RP04: Canonical existing receipt area is authoritative for candidate depth normalization
                can_area = ex_area
                norm_val = val
                if actual_volume_l is not None:
                    if float(actual_volume_l) == 0.0:
                        norm_val = 0.0
                    elif can_area is not None and float(can_area) > 0:
                        norm_val = round(float(actual_volume_l) / (10000.0 * float(can_area)), 6)
                    elif effective_area_ha is not None and float(effective_area_ha) > 0:
                        norm_val = round(float(actual_volume_l) / (10000.0 * float(effective_area_ha)), 6)
                elif ex_avl is not None and ex_avl == 0.0:
                    norm_val = 0.0

                def _field_matches(c_val, ex_val, inp_val, is_num=False):
                    if c_val is None:
                        return True
                    if is_num:
                        cf = finite_real(c_val)
                        if cf is not None:
                            if ex_val is not None and abs(ex_val - cf) <= 1e-4:
                                return True
                            if inp_val is not None and abs(inp_val - cf) <= 1e-4:
                                return True
                            return False
                    else:
                        cs = str(c_val)
                        if ex_val is not None and str(ex_val) == cs:
                            return True
                        if inp_val is not None and str(inp_val) == cs:
                            return True
                        return False

                is_conflict = (
                    abs(ex_del - norm_val) > 1e-4
                    or (bool(plot_id) and bool(ex_plot) and ex_plot != plot_id)
                    or not _field_matches(target_volume_mm, ex_target, caller_input.get("target_volume_mm"), is_num=True)
                    or not _field_matches(duration_minutes, ex_dur, caller_input.get("duration_minutes"), is_num=True)
                    or not _field_matches(flow_rate_lpm, ex_flow, caller_input.get("flow_rate_lpm"), is_num=True)
                    or not _field_matches(effective_area_ha, ex_area, caller_input.get("effective_area_ha"), is_num=True)
                    or not _field_matches(actual_volume_l, ex_avl, caller_input.get("actual_volume_l"), is_num=True)
                    or not _field_matches(actual_duration_minutes, ex_adur, caller_input.get("actual_duration_minutes"), is_num=True)
                    or not _field_matches(device_id, ex_dev, caller_input.get("device_id"), is_num=False)
                    or not _field_matches(zone_id, ex_zone, caller_input.get("zone_id"), is_num=False)
                    or not _field_matches(date, ex_date, caller_input.get("date"), is_num=False)
                    or not _field_matches(season, ex_season, caller_input.get("season"), is_num=False)
                )
                if is_conflict:
                    raise ValueError(
                        f"Conflicting settlement retry for event {event_id}: existing vs requested parameters mismatch"
                    )
                return  # Identical retry: idempotent success

            existing_res = state.setdefault("reservations", {}).pop(event_id, {})
            # D08 Probe B: Reconcile prior stopped receipt if this event was previously stopped!
            stopped_receipts = state.setdefault("stopped_receipts", {})
            prior_stopped = stopped_receipts.pop(event_id, None)

            # BV04: Canonical admitted envelope from existing reservation or stopped receipt is authoritative
            canonical_plot = existing_res.get("plot_id") or (prior_stopped.get("plot_id") if prior_stopped else None) or plot_id
            target_plot = canonical_plot

            date_key = existing_res.get("date") or (prior_stopped.get("date") if prior_stopped else None) or date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            season_key = existing_res.get("season") or (prior_stopped.get("season") if prior_stopped else None) or season or "default_season"
            dev_id = existing_res.get("device_id") or (prior_stopped.get("device_id") if prior_stopped else "") or device_id or ""
            z_id = existing_res.get("zone_id") or (prior_stopped.get("zone_id") if prior_stopped else "") or zone_id or ""
            canonical_tgt = None
            if existing_res.get("target_volume_mm") is not None:
                canonical_tgt = existing_res["target_volume_mm"]
            elif prior_stopped and prior_stopped.get("target_volume_mm") is not None:
                canonical_tgt = prior_stopped["target_volume_mm"]
            elif existing_res.get("volume_mm") is not None:
                canonical_tgt = existing_res["volume_mm"]
            elif target_volume_mm is not None:
                canonical_tgt = target_volume_mm
            else:
                canonical_tgt = val
            t_vol = float(canonical_tgt)
            dur_m = existing_res.get("duration_minutes") if existing_res.get("duration_minutes") is not None else (prior_stopped.get("duration_minutes", duration_minutes if duration_minutes is not None else 0.0) if prior_stopped else (duration_minutes if duration_minutes is not None else 0.0))
            f_lpm = existing_res.get("flow_rate_lpm") if existing_res.get("flow_rate_lpm") is not None else (prior_stopped.get("flow_rate_lpm", flow_rate_lpm if flow_rate_lpm is not None else 0.0) if prior_stopped else (flow_rate_lpm if flow_rate_lpm is not None else 0.0))
            eff_area = existing_res.get("effective_area_ha") if "effective_area_ha" in existing_res else (prior_stopped.get("effective_area_ha") if prior_stopped and "effective_area_ha" in prior_stopped else effective_area_ha)

            # Deduct prior stopped delivery if present
            if prior_stopped is not None:
                p_del = float(prior_stopped.get("delivered_volume_mm", 0.0))
                p_date = prior_stopped.get("date", date_key)
                p_season = prior_stopped.get("season", season_key)
                if p_del > 0:
                    pk_daily_p = f"{target_plot}:{p_date}"
                    pk_season_p = f"{target_plot}:{p_season}"
                    state.setdefault("settled_daily", {})[pk_daily_p] = max(0.0, float(state.get("settled_daily", {}).get(pk_daily_p, 0.0)) - p_del)
                    state.setdefault("settled_season", {})[pk_season_p] = max(0.0, float(state.get("settled_season", {}).get(pk_season_p, 0.0)) - p_del)
                    state.setdefault("settled_plot_total", {})[target_plot] = max(0.0, float(state.get("settled_plot_total", {}).get(target_plot, 0.0)) - p_del)

            # ER05: Deduct prior settled delivery if coexisting settled receipt is being replaced
            prior_settled = settled_receipts.pop(event_id, None)
            if prior_settled is not None:
                ps_del = float(prior_settled.get("delivered_volume_mm", 0.0))
                ps_date = prior_settled.get("date", date_key)
                ps_season = prior_settled.get("season", season_key)
                if ps_del > 0:
                    pk_daily_ps = f"{target_plot}:{ps_date}"
                    pk_season_ps = f"{target_plot}:{ps_season}"
                    state.setdefault("settled_daily", {})[pk_daily_ps] = max(0.0, float(state.get("settled_daily", {}).get(pk_daily_ps, 0.0)) - ps_del)
                    state.setdefault("settled_season", {})[pk_season_ps] = max(0.0, float(state.get("settled_season", {}).get(pk_season_ps, 0.0)) - ps_del)
                    state.setdefault("settled_plot_total", {})[target_plot] = max(0.0, float(state.get("settled_plot_total", {}).get(target_plot, 0.0)) - ps_del)

            # C09 + D10, RV05, BV04, PB07: Preserve commanded target and actual delivery observations separately; enforce mathematical depth consistency
            act_vol_l = finite_real(actual_volume_l) if actual_volume_l is not None else None
            act_dur_m = finite_real(actual_duration_minutes) if actual_duration_minutes is not None else None
            if act_vol_l == 0.0:
                val = 0.0
            elif act_vol_l is not None and eff_area is not None and eff_area > 0:
                val = round(act_vol_l / (10000.0 * float(eff_area)), 6)
            settled_receipts[event_id] = {
                "plot_id": target_plot,
                "device_id": dev_id,
                "zone_id": z_id,
                "volume_mm": val,
                "delivered_volume_mm": val,
                "target_volume_mm": t_vol,
                "actual_volume_l": act_vol_l,
                "actual_duration_minutes": act_dur_m,
                "duration_minutes": dur_m,
                "flow_rate_lpm": f_lpm,
                "effective_area_ha": eff_area,
                "date": date_key,
                "season": season_key,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "caller_input": {
                    "target_volume_mm": target_volume_mm,
                    "actual_volume_l": actual_volume_l,
                    "actual_duration_minutes": actual_duration_minutes,
                    "duration_minutes": duration_minutes,
                    "flow_rate_lpm": flow_rate_lpm,
                    "effective_area_ha": effective_area_ha,
                    "device_id": device_id,
                    "zone_id": zone_id,
                    "date": date,
                    "season": season,
                },
            }
            if val > 0:
                pk_daily = f"{target_plot}:{date_key}"
                pk_season = f"{target_plot}:{season_key}"
                state.setdefault("settled_daily", {})[pk_daily] = float(state.get("settled_daily", {}).get(pk_daily, 0.0)) + val
                state.setdefault("settled_season", {})[pk_season] = float(state.get("settled_season", {}).get(pk_season, 0.0)) + val
                state.setdefault("settled_plot_total", {})[target_plot] = float(state.get("settled_plot_total", {}).get(target_plot, 0.0)) + val

            state.setdefault("receipt_journal", []).append({
                "entry_id": f"j_{event_id}_{len(state.get('receipt_journal', [])) + 1}",
                "type": "SETTLED",
                "event_id": event_id,
                "plot_id": target_plot,
                "volume_mm": val,
                "target_volume_mm": t_vol,
                "delivered_volume_mm": val,
                "actual_volume_l": act_vol_l,
                "actual_duration_minutes": act_dur_m,
                "duration_minutes": dur_m,
                "flow_rate_lpm": f_lpm,
                "effective_area_ha": eff_area,
                "device_id": dev_id,
                "zone_id": z_id,
                "date": date_key,
                "season": season_key,
                "supersedes_receipt": copy.deepcopy(prior_stopped) if prior_stopped else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            cls._write_state(state)

    @classmethod
    def record_stopped_delivery(
        cls,
        event_id: str,
        plot_id: str,
        target_volume_mm: float,
        delivered_volume_mm: Optional[float] = None,
        season: Optional[str] = None,
        date: Optional[str] = None,
        device_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        duration_minutes: Optional[float] = None,
        flow_rate_lpm: Optional[float] = None,
        effective_area_ha: Optional[float] = None,
    ) -> None:
        """Record partial/stopped delivery so delivered or reserved exposure is not lost on cancellation (V04 + C04 + C05 + D08)."""
        with cls._lock():
            state = cls._read_state()
            # N05: Settled state is definitive and terminal; do not create duplicate debit or overwrite settled outcome
            if event_id in state.get("settled_receipts", {}):
                return

            existing_receipt = state.get("stopped_receipts", {}).get(event_id)
            existing_res = state.setdefault("reservations", {}).pop(event_id, {})

            del_val = finite_real(delivered_volume_mm)
            if del_val is None:
                if existing_res.get("delivered_volume_mm") is not None:
                    del_val = float(existing_res["delivered_volume_mm"])
                else:
                    del_val = float(target_volume_mm)
            else:
                if existing_res.get("delivered_volume_mm") is not None:
                    del_val = max(del_val, float(existing_res["delivered_volume_mm"]))

            if existing_res.get("target_volume_mm") is not None:
                target_volume_mm = float(existing_res["target_volume_mm"])

            if existing_receipt is not None:
                # D08 Probe A: Preserve original receipt's date and season on corrections!
                orig_date = existing_receipt.get("date")
                orig_season = existing_receipt.get("season")
                date_key = date or orig_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
                season_key = season or orig_season or "default_season"
                dev_id = device_id or existing_receipt.get("device_id", "")
                z_id = zone_id or existing_receipt.get("zone_id", "")
                dur_m = duration_minutes if duration_minutes is not None else existing_receipt.get("duration_minutes", 0.0)
                f_lpm = flow_rate_lpm if flow_rate_lpm is not None else existing_receipt.get("flow_rate_lpm", 0.0)
                eff_area = effective_area_ha if effective_area_ha is not None else existing_receipt.get("effective_area_ha")

                old_del = float(existing_receipt.get("delivered_volume_mm", 0.0))
                if abs(old_del - del_val) < 1e-6:
                    return  # Identical retry
                diff = del_val - old_del

                # If correcting within the same period:
                if orig_date == date_key and orig_season == season_key:
                    if diff != 0.0:
                        pk_daily = f"{plot_id}:{date_key}"
                        pk_season = f"{plot_id}:{season_key}"
                        state.setdefault("settled_daily", {})[pk_daily] = float(state.get("settled_daily", {}).get(pk_daily, 0.0)) + diff
                        state.setdefault("settled_season", {})[pk_season] = float(state.get("settled_season", {}).get(pk_season, 0.0)) + diff
                        state.setdefault("settled_plot_total", {})[plot_id] = float(state.get("settled_plot_total", {}).get(plot_id, 0.0)) + diff
                else:
                    # Period changed: deduct old_del from original period and add del_val to new period
                    if old_del > 0:
                        pk_d_old = f"{plot_id}:{orig_date}"
                        pk_s_old = f"{plot_id}:{orig_season}"
                        state.setdefault("settled_daily", {})[pk_d_old] = max(0.0, float(state.get("settled_daily", {}).get(pk_d_old, 0.0)) - old_del)
                        state.setdefault("settled_season", {})[pk_s_old] = max(0.0, float(state.get("settled_season", {}).get(pk_s_old, 0.0)) - old_del)
                        state.setdefault("settled_plot_total", {})[plot_id] = max(0.0, float(state.get("settled_plot_total", {}).get(plot_id, 0.0)) - old_del)
                    if del_val > 0:
                        pk_d_new = f"{plot_id}:{date_key}"
                        pk_s_new = f"{plot_id}:{season_key}"
                        state.setdefault("settled_daily", {})[pk_d_new] = float(state.get("settled_daily", {}).get(pk_d_new, 0.0)) + del_val
                        state.setdefault("settled_season", {})[pk_s_new] = float(state.get("settled_season", {}).get(pk_s_new, 0.0)) + del_val
                        state.setdefault("settled_plot_total", {})[plot_id] = float(state.get("settled_plot_total", {}).get(plot_id, 0.0)) + del_val

                state.setdefault("receipt_journal", []).append({
                    "entry_id": f"j_{event_id}_{len(state.get('receipt_journal', [])) + 1}",
                    "type": "CORRECTION",
                    "event_id": event_id,
                    "plot_id": plot_id,
                    "target_volume_mm": target_volume_mm,
                    "delivered_volume_mm": del_val,
                    "previous_delivered_volume_mm": old_del,
                    "delta_volume_mm": diff,
                    "supersedes_receipt": copy.deepcopy(existing_receipt),
                    "device_id": dev_id,
                    "zone_id": z_id,
                    "date": date_key,
                    "season": season_key,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            else:
                date_key = date or existing_res.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
                season_key = season or existing_res.get("season") or "default_season"
                dev_id = device_id or existing_res.get("device_id", "")
                z_id = zone_id or existing_res.get("zone_id", "")
                dur_m = duration_minutes if duration_minutes is not None else existing_res.get("duration_minutes", 0.0)
                f_lpm = flow_rate_lpm if flow_rate_lpm is not None else existing_res.get("flow_rate_lpm", 0.0)
                eff_area = effective_area_ha if effective_area_ha is not None else existing_res.get("effective_area_ha")

                if del_val > 0:
                    pk_daily = f"{plot_id}:{date_key}"
                    pk_season = f"{plot_id}:{season_key}"
                    state.setdefault("settled_daily", {})[pk_daily] = float(state.get("settled_daily", {}).get(pk_daily, 0.0)) + del_val
                    state.setdefault("settled_season", {})[pk_season] = float(state.get("settled_season", {}).get(pk_season, 0.0)) + del_val
                    state.setdefault("settled_plot_total", {})[plot_id] = float(state.get("settled_plot_total", {}).get(plot_id, 0.0)) + del_val

                state.setdefault("receipt_journal", []).append({
                    "entry_id": f"j_{event_id}_{len(state.get('receipt_journal', [])) + 1}",
                    "type": "STOPPED",
                    "event_id": event_id,
                    "plot_id": plot_id,
                    "target_volume_mm": target_volume_mm,
                    "delivered_volume_mm": del_val,
                    "device_id": dev_id,
                    "zone_id": z_id,
                    "date": date_key,
                    "season": season_key,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            state.setdefault("stopped_receipts", {})[event_id] = {
                "plot_id": plot_id,
                "device_id": dev_id,
                "zone_id": z_id,
                "target_volume_mm": target_volume_mm,
                "delivered_volume_mm": del_val,
                "duration_minutes": dur_m,
                "flow_rate_lpm": f_lpm,
                "effective_area_ha": eff_area,
                "date": date_key,
                "season": season_key,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            cls._write_state(state)

    @classmethod
    def reopen_active(
        cls,
        event_id: str,
        plot_id: str,
        volume_mm: float,
        season: Optional[str] = None,
        date: Optional[str] = None,
        device_id: str = "",
        zone_id: str = "",
        duration_minutes: float = 0.0,
        flow_rate_lpm: float = 0.0,
        effective_area_ha: Optional[float] = None,
    ) -> None:
        """Reopen an active reservation after a failed stop/late-fence, superseding any premature stopped receipt (N01)."""
        # RC07: Strictly validate input scalar parameters before mutating store state
        _validate_writer_scalars(
            volume_mm=volume_mm,
            duration_minutes=duration_minutes,
            flow_rate_lpm=flow_rate_lpm,
            effective_area_ha=effective_area_ha,
        )
        val = finite_real(volume_mm) or 0.0
        dur_m = finite_real(duration_minutes) or 0.0
        f_lpm = finite_real(flow_rate_lpm) or 0.0
        eff_area = finite_real(effective_area_ha)

        with cls._lock():
            state = cls._read_state()
            existing_res = state.get("reservations", {}).get(event_id, {})
            stopped_receipts = state.setdefault("stopped_receipts", {})
            stopped = stopped_receipts.pop(event_id, None)
            settled_receipts = state.setdefault("settled_receipts", {})
            settled = settled_receipts.pop(event_id, None)

            prior_rcpt = settled or stopped

            # PB05, RP01: Canonical operation envelope is authoritative across active, settled, and stopped-only records
            canonical_plot = existing_res.get("plot_id") or (prior_rcpt.get("plot_id") if prior_rcpt else None) or plot_id
            if canonical_plot != plot_id:
                if stopped:
                    stopped_receipts[event_id] = stopped
                if settled:
                    settled_receipts[event_id] = settled
                raise ValueError(f"Payload conflict: event {event_id} already reserved on plot {canonical_plot}, cannot rebind to {plot_id}")

            cmd_target = val
            if existing_res.get("target_volume_mm") is not None:
                cmd_target = float(existing_res["target_volume_mm"])
            elif prior_rcpt and prior_rcpt.get("target_volume_mm") is not None:
                cmd_target = float(prior_rcpt["target_volume_mm"])
            elif prior_rcpt and prior_rcpt.get("volume_mm") is not None:
                cmd_target = float(prior_rcpt["volume_mm"])
            elif existing_res.get("volume_mm") is not None:
                cmd_target = float(existing_res["volume_mm"])

            if existing_res.get("duration_minutes") is not None:
                dur_m = float(existing_res["duration_minutes"])
            elif prior_rcpt and prior_rcpt.get("duration_minutes") is not None:
                dur_m = float(prior_rcpt["duration_minutes"])

            if existing_res.get("flow_rate_lpm") is not None:
                f_lpm = float(existing_res["flow_rate_lpm"])
            elif prior_rcpt and prior_rcpt.get("flow_rate_lpm") is not None:
                f_lpm = float(prior_rcpt["flow_rate_lpm"])

            if "effective_area_ha" in existing_res:
                eff_area = existing_res["effective_area_ha"]
            elif prior_rcpt and "effective_area_ha" in prior_rcpt:
                eff_area = prior_rcpt["effective_area_ha"]

            s_del = None
            if prior_rcpt:
                p_del = prior_rcpt.get("delivered_volume_mm")
                if p_del is not None:
                    s_del = float(p_del)
                # NR02: Maintain distinction between immutable commanded target, measured delivery, and effective exposure!
                eff_exposure = max(cmd_target, s_del if s_del is not None else 0.0)
                orig_plot = prior_rcpt.get("plot_id") or canonical_plot
                s_date = prior_rcpt.get("date") or existing_res.get("date") or date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
                s_season = prior_rcpt.get("season") or existing_res.get("season") or season or "default_season"
                if s_del is not None and s_del > 0:
                    pk_daily = f"{orig_plot}:{s_date}"
                    pk_season = f"{orig_plot}:{s_season}"
                    state.setdefault("settled_daily", {})[pk_daily] = max(0.0, float(state.get("settled_daily", {}).get(pk_daily, 0.0)) - s_del)
                    state.setdefault("settled_season", {})[pk_season] = max(0.0, float(state.get("settled_season", {}).get(pk_season, 0.0)) - s_del)
                    state.setdefault("settled_plot_total", {})[orig_plot] = max(0.0, float(state.get("settled_plot_total", {}).get(orig_plot, 0.0)) - s_del)
            else:
                ex_del = existing_res.get("delivered_volume_mm")
                if ex_del is not None:
                    s_del = float(ex_del)
                eff_exposure = max(cmd_target, s_del if s_del is not None else 0.0)

            # BV04, PB05, RP01: Preserve canonical admitted dimensions from existing_res, settled, or stopped
            date_key = existing_res.get("date") or (prior_rcpt.get("date") if prior_rcpt else None) or date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            season_key = existing_res.get("season") or (prior_rcpt.get("season") if prior_rcpt else None) or season or "default_season"
            dev_id = existing_res.get("device_id") or (prior_rcpt.get("device_id") if prior_rcpt else "") or device_id
            z_id = existing_res.get("zone_id") or (prior_rcpt.get("zone_id") if prior_rcpt else "") or zone_id
            f_disp = existing_res.get("first_dispatched_at") or (prior_rcpt.get("first_dispatched_at") if prior_rcpt else None)
            act_start = existing_res.get("actual_start") or (prior_rcpt.get("actual_start") if prior_rcpt else None)

            res_record = {
                "plot_id": canonical_plot,
                "volume_mm": eff_exposure,
                "target_volume_mm": cmd_target,
                "delivered_volume_mm": s_del,
                "effective_exposure_mm": eff_exposure,
                "status": "STOP_REQUESTED",
                "date": date_key,
                "season": season_key,
                "device_id": dev_id,
                "zone_id": z_id,
                "duration_minutes": dur_m,
                "flow_rate_lpm": f_lpm,
                "effective_area_ha": eff_area,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if f_disp:
                res_record["first_dispatched_at"] = f_disp
            if act_start:
                res_record["actual_start"] = act_start

            state.setdefault("reservations", {})[event_id] = res_record

            state.setdefault("receipt_journal", []).append({
                "entry_id": f"j_{event_id}_{len(state.get('receipt_journal', [])) + 1}",
                "type": "REOPEN_ACTIVE",
                "event_id": event_id,
                "plot_id": canonical_plot,
                "volume_mm": eff_exposure,
                "target_volume_mm": cmd_target,
                "delivered_volume_mm": s_del,
                "effective_exposure_mm": eff_exposure,
                "supersedes_receipt": copy.deepcopy(prior_rcpt) if prior_rcpt else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            cls._write_state(state)

    @classmethod
    def get_reserved(cls, plot_id: str, exclude_event_id: Optional[str] = None) -> float:
        with cls._lock():
            state = cls._read_state()
            total = 0.0
            for eid, res in state.get("reservations", {}).items():
                if eid != exclude_event_id and res.get("plot_id") == plot_id:
                    total += float(res.get("effective_exposure_mm", res.get("volume_mm", 0.0)))
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
    def is_stopped(cls, event_id: str, plot_id: Optional[str] = None) -> bool:
        """C05: Query whether event has a terminal stopped receipt."""
        with cls._lock():
            state = cls._read_state()
            return event_id in state.get("stopped_receipts", {})

    @classmethod
    def is_active(cls, event_id: str, plot_id: Optional[str] = None) -> bool:
        with cls._lock():
            state = cls._read_state()
            return event_id in state.get("reservations", {})

    @classmethod
    def get_active_record(cls, event_id: str) -> Optional[Dict[str, Any]]:
        with cls._lock():
            state = cls._read_state()
            rec = state.get("reservations", {}).get(event_id)
            if rec is not None:
                return rec
            receipt = state.get("settled_receipts", {}).get(event_id)
            if receipt is not None:
                return {"status": "COMPLETED", **receipt}
            stopped = state.get("stopped_receipts", {}).get(event_id)
            if stopped is not None:
                return {"status": "CANCELLED", **stopped}
            return None

    @classmethod
    def get_active_record_for_resource(cls, device_id: str, zone_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with cls._lock():
            state = cls._read_state()
            for eid, res in state.get("reservations", {}).items():
                if res.get("status") in ("STARTING", "DISPATCHING", "EXECUTING", "VALIDATING") or res.get("claimed") is True:
                    if res.get("device_id") == device_id:
                        if not zone_id or not res.get("zone_id") or res.get("zone_id") == zone_id:
                            return {"event_id": eid, **res}
            return None

    @classmethod
    def claim_resource(
        cls,
        device_id: str,
        zone_id: Optional[str],
        event_id: str,
        live_executing: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """Atomically claim exclusive execution rights on (device_id, zone_id) for event_id.

        Returns:
            (True, None) if claim succeeded (or event_id already holds the claim).
            (False, holding_event_id) if another active event holds the claim.
        """
        if not device_id:
            return True, None

        now_ts = time.time()
        with cls._lock():
            state = cls._read_state()
            reservations = state.get("reservations", {})

            for eid, res in reservations.items():
                if eid != event_id and res.get("device_id") == device_id:
                    r_zone = res.get("zone_id")
                    if not zone_id or not r_zone or zone_id == r_zone:
                        st = res.get("status")
                        # 1. In-flight dispatch: another worker is actively sending START right now
                        if st == "STARTING":
                            starting_ts = res.get("starting_ts", 0.0)
                            if now_ts - starting_ts < 30.0:
                                return False, eid
                        # 2. Hardware is currently executing another confirmed operation
                        if live_executing and st in ("EXECUTING", "DISPATCHING", "STARTING"):
                            return False, eid

            if event_id in reservations:
                reservations[event_id]["status"] = "STARTING"
                reservations[event_id]["starting_ts"] = now_ts
                reservations[event_id]["claimed_at"] = datetime.now(timezone.utc).isoformat()
                cls._write_state(state)

            return True, None

    @classmethod
    def release_resource_claim(
        cls,
        device_id: str,
        zone_id: Optional[str],
        event_id: str,
    ) -> None:
        """Release an exclusive resource claim for event_id."""
        with cls._lock():
            state = cls._read_state()
            reservations = state.get("reservations", {})
            if event_id in reservations and reservations[event_id].get("status") == "STARTING":
                reservations[event_id]["status"] = "DISPATCHING"
                reservations[event_id].pop("starting_ts", None)
                cls._write_state(state)

    @classmethod
    def get_settled_receipt(cls, event_id: str) -> Optional[Dict[str, Any]]:
        with cls._lock():
            state = cls._read_state()
            return state.get("settled_receipts", {}).get(event_id)

    @classmethod
    def get_stopped_receipt(cls, event_id: str) -> Optional[Dict[str, Any]]:
        """C05: Retrieve terminal stopped receipt."""
        with cls._lock():
            state = cls._read_state()
            return state.get("stopped_receipts", {}).get(event_id)


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

    def reset(self) -> None:
        """Reset in-memory state of the safety monitor (for testing/process reset)."""
        self._active_violations.clear()
        self._violation_history.clear()
        self._active_events.clear()
        self._reserved_quota.clear()
        self._breach_tracking.clear()

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
        zone_id: str = "",
        flow_rate_lpm: float = 0.0,
        effective_area_ha: Optional[float] = None,
    ) -> None:
        """Register an active irrigation event for duration monitoring and quota reservation."""
        now_dt = datetime.now(timezone.utc)
        start_mono = self._clock() - (max(0.0, elapsed_minutes) * 60.0)
        existing_claim = SharedQuotaStore.get_active_record(event_id) if SharedQuotaStore.is_active(event_id) else None
        eff_vol = float(existing_claim.get("effective_exposure_mm", existing_claim.get("volume_mm", volume_mm))) if existing_claim else volume_mm
        self._active_events[event_id] = {
            "start_time": now_dt,
            "start_monotonic": start_mono,
            "max_duration_minutes": max_duration_minutes,
            "device_id": device_id,
            "plot_id": plot_id,
            "volume_mm": eff_vol,
            "season": season,
            "date": date,
            "zone_id": zone_id,
            "flow_rate_lpm": flow_rate_lpm,
            "effective_area_ha": effective_area_ha,
        }
        if plot_id and volume_mm >= 0 and existing_claim is None:
            self.reserve_quota(
                event_id,
                plot_id,
                volume_mm,
                season=season,
                date=date,
                device_id=device_id,
                zone_id=zone_id,
                duration_minutes=max_duration_minutes,
                flow_rate_lpm=flow_rate_lpm,
                effective_area_ha=effective_area_ha,
            )
        logger.debug("Tracking event %s (max %.0f min, elapsed %.1f min, reserved %.1f mm)",
                     event_id, max_duration_minutes, elapsed_minutes, eff_vol)

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
        flow_rate_lpm: float = 0.0,
        effective_area_ha: Optional[float] = None,
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
            flow_rate_lpm=flow_rate_lpm,
            effective_area_ha=effective_area_ha,
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

    def reopen_active(
        self,
        event_id: str,
        plot_id: str,
        volume_mm: float,
        season: Optional[str] = None,
        date: Optional[str] = None,
        device_id: str = "",
        zone_id: str = "",
        duration_minutes: float = 0.0,
        flow_rate_lpm: float = 0.0,
        effective_area_ha: Optional[float] = None,
    ) -> None:
        """Reopen active tracking and quota in SharedQuotaStore after a failed stop/late-fence."""
        SharedQuotaStore.reopen_active(
            event_id,
            plot_id,
            volume_mm,
            season=season,
            date=date,
            device_id=device_id,
            zone_id=zone_id,
            duration_minutes=duration_minutes,
            flow_rate_lpm=flow_rate_lpm,
            effective_area_ha=effective_area_ha,
        )
        if volume_mm > 0:
            self._reserved_quota[event_id] = {
                "plot_id": plot_id,
                "volume_mm": volume_mm,
                "season": season,
                "date": date,
            }

    def settle_quota(
        self,
        event_id: str,
        plot_id: str,
        volume_mm: float,
        target_volume_mm: Optional[float] = None,
        actual_volume_l: Optional[float] = None,
        actual_duration_minutes: Optional[float] = None,
        date: Optional[str] = None,
        season: Optional[str] = None,
        device_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        duration_minutes: Optional[float] = None,
        flow_rate_lpm: Optional[float] = None,
        effective_area_ha: Optional[float] = None,
    ) -> None:
        """Settle a delivered event: release reservation and debit cumulative budget."""
        SharedQuotaStore.settle(
            event_id,
            plot_id,
            volume_mm,
            target_volume_mm=target_volume_mm,
            actual_volume_l=actual_volume_l,
            actual_duration_minutes=actual_duration_minutes,
            date=date,
            season=season,
            device_id=device_id,
            zone_id=zone_id,
            duration_minutes=duration_minutes,
            flow_rate_lpm=flow_rate_lpm,
            effective_area_ha=effective_area_ha,
        )
        self._reserved_quota.pop(event_id, None)

    def record_stopped_delivery(
        self,
        event_id: str,
        plot_id: str,
        target_volume_mm: float,
        delivered_volume_mm: Optional[float] = None,
        season: Optional[str] = None,
        date: Optional[str] = None,
        device_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        duration_minutes: Optional[float] = None,
        flow_rate_lpm: Optional[float] = None,
        effective_area_ha: Optional[float] = None,
    ) -> None:
        """Record stopped delivery in shared store and release uncommitted quota tracking (C04/C05)."""
        SharedQuotaStore.record_stopped_delivery(
            event_id=event_id,
            plot_id=plot_id,
            target_volume_mm=target_volume_mm,
            delivered_volume_mm=delivered_volume_mm,
            season=season,
            date=date,
            device_id=device_id,
            zone_id=zone_id,
            duration_minutes=duration_minutes,
            flow_rate_lpm=flow_rate_lpm,
            effective_area_ha=effective_area_ha,
        )
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
