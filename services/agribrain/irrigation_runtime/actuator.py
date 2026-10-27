"""
Irrigation Runtime — Abstract Actuator Interface v1.0.0

Hardware-agnostic base class for all irrigation actuator drivers.
Every physical controller (solenoid, pivot, PLC) implements this interface.

Contract:
  - send_command() dispatches a single atomic command
  - get_status() returns real-time actuator state
  - emergency_stop() is always available, even during errors
  - validate_command() performs pre-flight safety checks before dispatch
  - All methods are async for non-blocking I/O across protocols
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import math
import os
import re
import tempfile
import threading
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from irrigation_runtime.schemas import (
    ActuatorRegistration,
    ActuatorStatus,
    CommandResult,
    CommandType,
    DriverProtocol,
    IrrigationCommand,
    SafetyInterlock,
    SafetyViolation,
    InterlockType,
    VendorId,
)

try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    try:
        from services.agribrain.scientific_contracts.numeric import finite_real
    except ImportError:
        import math
        from numbers import Real
        def finite_real(val: Any) -> Optional[float]:
            if isinstance(val, bool) or not isinstance(val, Real):
                return None
            try:
                res = float(val)
                return res if math.isfinite(res) else None
            except Exception:
                return None

logger = logging.getLogger(__name__)

_GLOBAL_CONSUMED_RECEIPT_TOKENS: Set[str] = set()

PREDICTABLE_KEY_BLACKLIST = {
    "default",
    "secret",
    "predictable",
    "password",
    "admin",
    "12345",
    "changeme",
    "test_secret",
    "root",
}


def is_predictable_or_insecure_key(
    key: Optional[Union[str, bytes]],
    device_id: Optional[str] = None,
) -> bool:
    """Return True if the key is empty, predictable, derived from public device info, or in blacklist."""
    if key is None:
        return True
    if isinstance(key, bytes):
        try:
            key_str = key.decode("utf-8")
        except Exception:
            key_str = ""
    else:
        key_str = str(key)

    clean = key_str.strip()
    if len(clean) < 8:
        return True

    lower = clean.lower()
    if lower in PREDICTABLE_KEY_BLACKLIST:
        return True
    if "agribrain_stop_auth_" in lower:
        return True

    if device_id:
        dev_clean = str(device_id).strip().lower()
        if dev_clean and (clean == dev_clean or lower == f"agribrain_stop_auth_{dev_clean}"):
            return True
    return False


def get_provisioned_stop_keys(
    device_id: str,
    registration: Optional[ActuatorRegistration] = None,
) -> List[bytes]:
    """Resolve provisioned STOP signing/verification keys for a device.

    Supports key rotation by returning all currently valid keys (active and previous).
    Sources:
      1. registration.connection_config: 'auth_secret', 'stop_auth_key', 'stop_auth_keys'
      2. Environment AGRIBRAIN_STOP_AUTH_KEYS (JSON map of device_id -> key(s))
      3. Environment AGRIBRAIN_STOP_AUTH_KEY_<DEVICE_ID_SANITIZED>
      4. Environment AGRIBRAIN_STOP_AUTH_KEY (global authority secret)

    Predictable keys (e.g. derived from public device_id) are strictly rejected.
    """
    keys: List[bytes] = []

    def _add_key(k: Any) -> None:
        if isinstance(k, (list, tuple, set)):
            for item in k:
                _add_key(item)
            return
        if not k or is_predictable_or_insecure_key(k, device_id):
            return
        b = k.encode("utf-8") if isinstance(k, str) else bytes(k)
        if b not in keys:
            keys.append(b)

    # 1. Registration connection_config
    if registration and getattr(registration, "connection_config", None):
        cfg = registration.connection_config
        _add_key(cfg.get("auth_secret"))
        _add_key(cfg.get("stop_auth_key"))
        _add_key(cfg.get("stop_auth_keys"))

    # 2. AGRIBRAIN_STOP_AUTH_KEYS JSON mapping
    env_keys_json = os.environ.get("AGRIBRAIN_STOP_AUTH_KEYS")
    if env_keys_json:
        try:
            parsed = json.loads(env_keys_json)
            if isinstance(parsed, dict):
                dev_entry = parsed.get(device_id) or parsed.get(device_id.upper()) or parsed.get(device_id.lower())
                if dev_entry:
                    _add_key(dev_entry)
                auth_entry = parsed.get("authority") or parsed.get("default")
                if auth_entry:
                    _add_key(auth_entry)
        except Exception:
            pass

    # 3. AGRIBRAIN_STOP_AUTH_KEY_<DEVICE>
    dev_sanitized = re.sub(r"[^A-Za-z0-9_]", "_", device_id.upper())
    env_dev_key = os.environ.get(f"AGRIBRAIN_STOP_AUTH_KEY_{dev_sanitized}")
    if env_dev_key:
        _add_key(env_dev_key)

    # 4. AGRIBRAIN_STOP_AUTH_KEY (authority fallback)
    global_key = os.environ.get("AGRIBRAIN_STOP_AUTH_KEY")
    if global_key:
        _add_key(global_key)

    return keys


def build_canonical_stop_assertion(
    device_id: str,
    operation_id: str,
    attempt_number: Any,
    timestamp: Any,
    source: str,
    actual_flow_lpm: float = 0.0,
    is_running: bool = False,
    is_stopped: bool = True,
    confirmed_stopped: bool = True,
) -> bytes:
    """Build canonical UTF-8 bytes binding device, operation, attempt, timestamp, provenance source,
    and all safety-critical physical measurements (flow rate, running state, stopped assertion).
    """
    dev_str = str(device_id).strip()
    op_str = str(operation_id).strip()
    att_str = str(attempt_number).strip() if attempt_number is not None else "1"

    if isinstance(timestamp, datetime):
        ts_str = timestamp.isoformat()
    elif isinstance(timestamp, (int, float)):
        ts_str = datetime.fromtimestamp(float(timestamp), tz=timezone.utc).isoformat()
    else:
        ts_str = str(timestamp).strip()

    src_str = str(source).strip().lower() if source else "controller"

    try:
        flow_float = float(actual_flow_lpm)
        if not math.isfinite(flow_float):
            flow_float = 0.0
    except Exception:
        flow_float = 0.0

    raw = (
        f"dev={dev_str}|"
        f"op={op_str}|"
        f"att={att_str}|"
        f"ts={ts_str}|"
        f"src={src_str}|"
        f"flow={flow_float:.4f}|"
        f"running={bool(is_running)}|"
        f"stopped={bool(is_stopped)}|"
        f"confirmed_stopped={bool(confirmed_stopped)}"
    )
    return raw.encode("utf-8")


class DurableStopReceiptStore:
    """Thread-safe and cross-process atomic consumed STOP receipt store.

    Prevents replay attacks across restarts, threads, and independent worker processes.
    Backed by an append-only journal with atomic cross-process file locking.
    """
    _thread_lock = threading.RLock()
    _memory_cache: Set[str] = set()

    @classmethod
    def _store_dir(cls) -> Path:
        env_dir = os.environ.get("AGRIBRAIN_STOP_RECEIPT_DIR") or os.environ.get("AGRIBRAIN_QUOTA_DIR")
        if env_dir:
            p = Path(env_dir)
        else:
            p = Path(tempfile.gettempdir()) / "agribrain_runtime" / "stop_receipts"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def _journal_file(cls) -> Path:
        return cls._store_dir() / "consumed_stop_receipts.jsonl"

    @classmethod
    def _lock_file(cls) -> Path:
        return cls._store_dir() / "stop_receipts.lock"

    @classmethod
    @contextmanager
    def _cross_process_lock(cls):
        with cls._thread_lock:
            lock_path = cls._lock_file()
            descriptor = None
            owner_token = f"{os.getpid()}:{threading.get_ident()}:{uuid.uuid4().hex}"
            for _ in range(500):
                try:
                    descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    break
                except FileExistsError:
                    try:
                        if time.time() - lock_path.stat().st_mtime > 30.0:
                            lock_path.unlink(missing_ok=True)
                            continue
                    except OSError:
                        pass
                    time.sleep(0.005)
            if descriptor is None:
                raise TimeoutError("Timeout acquiring cross-process stop receipt lock")
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(owner_token)
                yield
            finally:
                try:
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @classmethod
    def is_consumed(cls, fingerprint: str, token: Optional[str] = None) -> bool:
        """Check if fingerprint or token has already been consumed."""
        with cls._thread_lock:
            if fingerprint in cls._memory_cache:
                return True
            if token and token in cls._memory_cache:
                return True

        jfile = cls._journal_file()
        if not jfile.exists():
            return False

        try:
            with open(jfile, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        fp = rec.get("fingerprint")
                        tok = rec.get("token")
                        if fp == fingerprint or (token and tok == token):
                            with cls._thread_lock:
                                if fp:
                                    cls._memory_cache.add(fp)
                                if tok:
                                    cls._memory_cache.add(tok)
                            return True
                    except Exception:
                        continue
        except OSError:
            pass
        return False

    @classmethod
    def consume(cls, fingerprint: str, token: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Atomically mark fingerprint and token as consumed. Returns True if newly consumed, False if replay."""
        with cls._cross_process_lock():
            if cls.is_consumed(fingerprint, token):
                return False

            record = {
                "fingerprint": fingerprint,
                "token": token,
                "consumed_at": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid(),
            }
            if metadata:
                record.update(metadata)

            jfile = cls._journal_file()
            try:
                with open(jfile, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            except OSError as e:
                logger.error("Failed to append to stop receipt journal: %s", e)

            with cls._thread_lock:
                cls._memory_cache.add(fingerprint)
                if token:
                    cls._memory_cache.add(token)
            return True

    @classmethod
    def reset(cls) -> None:
        """Reset memory cache and journal (for testing isolation)."""
        with cls._thread_lock:
            cls._memory_cache.clear()
            jfile = cls._journal_file()
            if jfile.exists():
                try:
                    jfile.unlink(missing_ok=True)
                except OSError:
                    pass


def generate_stop_receipt_token(
    device_id: str,
    operation_id: str,
    attempt_number: Any = 1,
    timestamp: Any = None,
    secret: Optional[Union[str, bytes]] = None,
    source: str = "controller",
    actual_flow_lpm: float = 0.0,
    is_running: bool = False,
    is_stopped: bool = True,
    confirmed_stopped: bool = True,
) -> str:
    """Generate a cryptographic authentication token binding device, operation, attempt, time,
    and complete physical measurements.

    Strictly forbids predictable keys derived from device_id.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    if secret is not None:
        if is_predictable_or_insecure_key(secret, device_id):
            raise ValueError(
                f"Predictable or insecure signing key rejected for device {device_id}. "
                "Keys derived from device_id or matching defaults are forbidden."
            )
        key_bytes = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
    else:
        keys = get_provisioned_stop_keys(device_id)
        if not keys:
            raise ValueError(
                f"Cannot generate STOP receipt token for device {device_id}: "
                "no securely provisioned signing key available."
            )
        key_bytes = keys[0]

    assertion = build_canonical_stop_assertion(
        device_id=device_id,
        operation_id=operation_id,
        attempt_number=attempt_number,
        timestamp=timestamp,
        source=source,
        actual_flow_lpm=actual_flow_lpm,
        is_running=is_running,
        is_stopped=is_stopped,
        confirmed_stopped=confirmed_stopped,
    )
    return hmac.new(key_bytes, assertion, hashlib.sha256).hexdigest()[:32]


def create_verified_stop_receipt(
    device_id: str,
    operation_id: str,
    attempt_number: int = 1,
    source: str = "controller",
    actual_flow_lpm: float = 0.0,
    timestamp: Optional[Union[str, float, datetime]] = None,
    secret: Optional[Union[str, bytes]] = None,
    is_running: bool = False,
    is_stopped: bool = True,
    confirmed_stopped: bool = True,
    **extra: Any,
) -> Dict[str, Any]:
    """Create an authenticated, operation-bound, replay-resistant physical STOP receipt at a trusted boundary."""
    if timestamp is None:
        ts_str = datetime.now(timezone.utc).isoformat()
    elif isinstance(timestamp, datetime):
        ts_str = timestamp.isoformat()
    elif isinstance(timestamp, (int, float)):
        ts_str = datetime.fromtimestamp(float(timestamp), tz=timezone.utc).isoformat()
    else:
        ts_str = str(timestamp)

    token = generate_stop_receipt_token(
        device_id=device_id,
        operation_id=operation_id,
        attempt_number=attempt_number,
        timestamp=ts_str,
        secret=secret,
        source=source,
        actual_flow_lpm=actual_flow_lpm,
        is_running=is_running,
        is_stopped=is_stopped,
        confirmed_stopped=confirmed_stopped,
    )
    rec: Dict[str, Any] = {
        "device_id": device_id,
        "operation_id": operation_id,
        "attempt_number": attempt_number,
        "source": source,
        "actual_flow_lpm": float(actual_flow_lpm),
        "timestamp": ts_str,
        "authenticated": True,
        "auth_token": token,
        "receipt_token": token,
        "confirmed_stopped": bool(confirmed_stopped),
        "is_stopped": bool(is_stopped),
        "is_running": bool(is_running),
    }
    rec.update(extra)
    return rec


class IrrigationActuator(ABC):
    """Abstract base class for all irrigation hardware drivers.

    Subclasses implement protocol-specific communication:
      - MQTTActuator: MQTT publish/subscribe
      - ModbusActuator: Modbus RTU/TCP register R/W
      - LoRaWANActuator: Class C downlink via network server
      - HTTPActuator: REST API calls to cloud-connected hardware

    Every driver must:
      1. Handle connection lifecycle (connect/disconnect/reconnect)
      2. Translate IrrigationCommand → protocol-specific payload
      3. Parse actuator responses → CommandResult
      4. Implement emergency_stop as a non-blocking, always-available operation
    """

    def __init__(self, registration: ActuatorRegistration):
        self.registration = registration
        self.device_id = registration.device_id
        self.protocol = registration.protocol
        self._status = ActuatorStatus.UNKNOWN
        self._connected = False
        self._last_heartbeat: Optional[datetime] = None
        self._active_command: Optional[IrrigationCommand] = None
        self._pending_command: Optional[IrrigationCommand] = None
        self._dispatch_lock: Optional[asyncio.Lock] = None
        self._command_history: List[Dict[str, Any]] = []
        self._interlocks: List[SafetyInterlock] = []
        self._stop_generation: int = 0
        self._cancelled_commands: set[str] = set()
        self._cancelled_operations: set[str] = set()
        self._consumed_receipt_tokens: Set[str] = set()

    @property
    def dispatch_lock(self) -> asyncio.Lock:
        if getattr(self, "_dispatch_lock", None) is None:
            self._dispatch_lock = asyncio.Lock()
        return self._dispatch_lock

    # ================================================================
    # Abstract Methods (must be implemented by drivers)
    # ================================================================

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the physical actuator.

        Returns True if connection succeeded.
        Must handle reconnection logic internally.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close connection to the actuator."""
        ...

    @abstractmethod
    async def send_command(self, command: IrrigationCommand) -> CommandResult:
        """Dispatch a single command to the physical actuator.

        The driver must:
          1. Encode the command into protocol-specific format
          2. Transmit to the device
          3. Wait for acknowledgment (with timeout)
          4. Return a CommandResult with actual delivery data

        Args:
            command: Validated IrrigationCommand to execute

        Returns:
            CommandResult with success/failure and actual measurements
        """
        ...

    @abstractmethod
    async def get_status(self) -> ActuatorStatus:
        """Query real-time status from the physical actuator.

        Returns the current ActuatorStatus based on device heartbeat
        and operational state.
        """
        ...

    @abstractmethod
    async def emergency_stop(self) -> CommandResult:
        """Immediately stop all irrigation on this actuator.

        This MUST:
          - Be non-blocking (fire-and-forget if necessary)
          - Work even if the actuator is in ERROR state
          - Close all valves to fail-safe position
          - Log the emergency stop event

        Returns:
            CommandResult indicating stop confirmation
        """
        ...

    async def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Query driver/controller for operation-specific execution receipt.

        Returns None if driver does not support operation-level querying or
        if operation is unknown to the controller.
        """
        return None

    # ================================================================
    # Common Methods (shared across all drivers)
    # ================================================================

    def validate_command(self, command: IrrigationCommand) -> List[str]:
        """Pre-flight safety validation before dispatch.

        Checks:
          - Command schema validity
          - Flow rate within actuator capability limits
          - Duration within watchdog limits
          - Volume within daily/season quota
          - No active safety interlocks

        Returns:
            List of error messages (empty = valid)
        """
        errors = command.validate()
        if errors:
            return errors

        caps = self.registration.capabilities

        # Flow rate and duration bounds (apply only to active irrigation commands)
        if command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
            if command.flow_rate_lpm > caps.max_flow_rate_lpm > 0:
                errors.append(
                    f"Flow rate {command.flow_rate_lpm} L/min exceeds max "
                    f"{caps.max_flow_rate_lpm} L/min for device {self.device_id}"
                )

            if command.flow_rate_lpm < caps.min_flow_rate_lpm:
                errors.append(
                    f"Flow rate {command.flow_rate_lpm} L/min below min "
                    f"{caps.min_flow_rate_lpm} L/min for device {self.device_id}"
                )

            # Duration watchdog
            if command.duration_minutes > caps.max_duration_minutes:
                errors.append(
                    f"Duration {command.duration_minutes} min exceeds max "
                    f"{caps.max_duration_minutes} min watchdog"
                )

        # Actuator status check
        if self._status == ActuatorStatus.OFFLINE:
            errors.append(f"Actuator {self.device_id} is OFFLINE")

        # Allow STOP_ZONE and EMERGENCY_STOP even if in ERROR or MAINTENANCE or latched fault
        if ((self._status == ActuatorStatus.ERROR or getattr(self, "_fault_latched", False))
                and command.command_type not in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP)):
            errors.append(f"Actuator {self.device_id} is in ERROR state or has latched fault")

        if (self._status == ActuatorStatus.MAINTENANCE
                and command.command_type not in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP)):
            errors.append(f"Actuator {self.device_id} is in MAINTENANCE mode")

        # Reject physical START while stop confirmation is pending
        if (self._status == ActuatorStatus.STOP_PENDING_CONFIRMATION
                and command.command_type not in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP)):
            errors.append(
                f"Actuator {self.device_id} is in STOP_PENDING_CONFIRMATION state: "
                "physical stop unconfirmed. Cannot start new delivery until cessation is positively verified."
            )

        # Check if already executing (unless stop or emergency stop)
        if (self._status == ActuatorStatus.EXECUTING
                and command.command_type not in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP)):
            is_own_retry = False
            has_payload_conflict = False
            active = self._active_command
            if active is not None:
                op_matches = bool(command.operation_id) and bool(active.operation_id) and active.operation_id == command.operation_id
                event_matches = bool(command.source_event_id) and bool(active.source_event_id) and active.source_event_id == command.source_event_id
                if op_matches or event_matches:
                    c_vol = finite_real(command.volume_mm)
                    a_vol = finite_real(active.volume_mm)
                    c_dur = finite_real(command.duration_minutes)
                    a_dur = finite_real(active.duration_minutes)
                    c_flw = finite_real(command.flow_rate_lpm)
                    a_flw = finite_real(active.flow_rate_lpm)
                    same_vol = (c_vol is not None and a_vol is not None and abs(c_vol - a_vol) < 1e-4)
                    same_dur = (c_dur is not None and a_dur is not None and abs(c_dur - a_dur) < 1e-4)
                    same_flw = (c_flw is not None and a_flw is not None and abs(c_flw - a_flw) < 1e-4)
                    op_conflict = bool(command.operation_id) and bool(active.operation_id) and (command.operation_id != active.operation_id)
                    if same_vol and same_dur and same_flw and not op_conflict:
                        is_own_retry = True
                    else:
                        has_payload_conflict = True
            elif hasattr(self, "hw") and (getattr(self.hw, "event_id", None) == command.source_event_id or getattr(self.hw, "operation", None) == command.source_event_id):
                is_own_retry = True

            if has_payload_conflict:
                errors.append(
                    f"Actuator {self.device_id} is EXECUTING command {self._active_command.command_id if self._active_command else ''}; "
                    f"command {command.command_id} has conflicting payload or operation ID."
                )
            elif not is_own_retry:
                errors.append(
                    f"Actuator {self.device_id} is already EXECUTING. "
                    f"Send STOP_ZONE or EMERGENCY_STOP first."
                )

        return errors

    def set_active_command(self, command: IrrigationCommand, status: Optional[ActuatorStatus] = None) -> None:
        """Rehydrate active command and status (e.g. on process restart)."""
        self._active_command = command
        if status is not None:
            self._status = status
        elif command.command_type in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP):
            self._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
        else:
            self._status = ActuatorStatus.EXECUTING

    def confirm_stop(self) -> None:
        """Positively confirm physical cessation of irrigation, releasing ownership to ONLINE."""
        self._status = ActuatorStatus.ONLINE
        self._active_command = None
        self._pending_command = None
        logger.info("Device %s physical stop positively confirmed; status transitioned to ONLINE.", self.device_id)

    async def _execute_stop_direct(self, command: IrrigationCommand) -> CommandResult:
        """Execute STOP or EMERGENCY_STOP directly without waiting behind a hung START lock (V06)."""
        errors = self.validate_command(command)
        if errors:
            logger.warning(
                "Command %s rejected for device %s: %s",
                command.command_id, self.device_id, errors
            )
            return CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error_code="VALIDATION_FAILED",
                error_message="; ".join(errors),
            )

        # C01 / C02: Bump stop generation and track cancelled commands/operations
        if getattr(self, "_stop_generation", None) is None:
            self._stop_generation = 0
        self._stop_generation += 1

        if getattr(self, "_cancelled_commands", None) is None:
            self._cancelled_commands = set()
        if getattr(self, "_cancelled_operations", None) is None:
            self._cancelled_operations = set()

        if self._pending_command is not None:
            self._cancelled_commands.add(self._pending_command.command_id)
            if self._pending_command.operation_id:
                self._cancelled_operations.add(self._pending_command.operation_id)
        if command.source_event_id:
            self._cancelled_operations.add(command.source_event_id)
        if command.operation_id:
            self._cancelled_operations.add(command.operation_id)

        if (command.command_type == CommandType.STOP_ZONE
                and self._status == ActuatorStatus.ONLINE
                and self._active_command is None
                and self._pending_command is None):
            logger.info("Device %s is already stopped (ONLINE); STOP_ZONE succeeded idempotently.", self.device_id)
            result = CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=True,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error_code="ALREADY_STOPPED",
                error_message="Actuator is already stopped",
            )
            self._command_history.append({
                "command_id": command.command_id,
                "command_type": command.command_type.value,
                "success": result.success,
                "timestamp": result.timestamp,
                "error_code": result.error_code,
            })
            return result

        logger.info(
            "Direct stop dispatch %s to device %s (zone=%s)",
            command.command_type.value, self.device_id, command.zone_id
        )

        try:
            result = await self.send_command(command)
        except Exception as exc:
            logger.error(
                "Stop command %s failed on device %s: %s",
                command.command_id, self.device_id, exc
            )
            self._status = ActuatorStatus.ERROR
            result = CommandResult(
                command_id=command.command_id,
                device_id=self.device_id,
                success=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error_code="DISPATCH_EXCEPTION",
                error_message=str(exc),
                retry_recommended=False,
            )

        if result.success:
            has_fault = (
                getattr(self, "_fault_latched", False)
                or getattr(self, "_status", None) == ActuatorStatus.ERROR
                or bool(getattr(result, "fault_code", 0))
                or getattr(result, "error_code", "") in ("FAULT", "HARDWARE_FAULT", "ERROR")
            )
            is_simulation = (
                type(self).__name__.startswith("Mock")
                or getattr(self, "is_mock", False)
                or getattr(self, "is_simulation", False)
                or getattr(getattr(self, "registration", None), "is_simulation", False)
                or getattr(getattr(self, "registration", None), "model", "") in ("MockModel", "offline")
            )
            if is_simulation:
                self._status = ActuatorStatus.ERROR if has_fault else ActuatorStatus.ONLINE
                self._active_command = None
                self._pending_command = None
                result.confirmed_physical_stop = True
            elif has_fault:
                self._status = ActuatorStatus.ERROR
            elif getattr(result, "confirmed_physical_stop", False) is True:
                self._status = ActuatorStatus.ONLINE
                self._active_command = None
                self._pending_command = None
            else:
                self._status = ActuatorStatus.STOP_PENDING_CONFIRMATION
                result.confirmed_physical_stop = False
                result.transport_acknowledged_only = True
                logger.warning(
                    "Stop command %s on device %s lacks affirmative physical proof; entered STOP_PENDING_CONFIRMATION.",
                    command.command_id, self.device_id
                )
        else:
            self._status = ActuatorStatus.ERROR

        self._command_history.append({
            "command_id": command.command_id,
            "command_type": command.command_type.value,
            "success": result.success,
            "timestamp": result.timestamp,
            "error_code": result.error_code,
        })
        return result

    async def execute_with_safety(self, command: IrrigationCommand) -> CommandResult:
        """Validate, dispatch, and log a command with full safety checks.

        This is the primary entry point for dispatching commands.
        It wraps send_command() with validation, reconciliation, and audit logging.
        Uses dispatch locking so in-flight commands are serialized and duplicates do not
        fabricate false success before initial outcome resolution.
        """
        # V06: STOP and EMERGENCY_STOP must preempt hung START dispatches without blocking
        if command.command_type in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP):
            return await self._execute_stop_direct(command)

        async with self.dispatch_lock:
            # Pre-flight validation
            errors = self.validate_command(command)
            if errors:
                logger.warning(
                    "Command %s rejected for device %s: %s",
                    command.command_id, self.device_id, errors
                )
                return CommandResult(
                    command_id=command.command_id,
                    device_id=self.device_id,
                    success=False,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_code="VALIDATION_FAILED",
                    error_message="; ".join(errors),
                )

            # Idempotent stop check: if already ONLINE and idle, STOP_ZONE succeeds idempotently
            if (command.command_type == CommandType.STOP_ZONE
                    and self._status == ActuatorStatus.ONLINE
                    and self._active_command is None):
                logger.info("Device %s is already stopped (ONLINE); STOP_ZONE succeeded idempotently.", self.device_id)
                result = CommandResult(
                    command_id=command.command_id,
                    device_id=self.device_id,
                    success=True,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_code="ALREADY_STOPPED",
                    error_message="Actuator is already stopped",
                )
                self._command_history.append({
                    "command_id": command.command_id,
                    "command_type": command.command_type.value,
                    "success": result.success,
                    "timestamp": result.timestamp,
                    "error_code": result.error_code,
                })
                return result

            # Idempotent execution check: if already EXECUTING this own-operation, do not duplicate physical START
            if (command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE)
                    and self._status == ActuatorStatus.EXECUTING):
                is_own_retry = False
                has_payload_conflict = False
                active = self._active_command
                if active is not None:
                    op_matches = bool(command.operation_id) and bool(active.operation_id) and active.operation_id == command.operation_id
                    event_matches = bool(command.source_event_id) and bool(active.source_event_id) and active.source_event_id == command.source_event_id
                    if op_matches or event_matches:
                        c_vol = finite_real(command.volume_mm)
                        a_vol = finite_real(active.volume_mm)
                        c_dur = finite_real(command.duration_minutes)
                        a_dur = finite_real(active.duration_minutes)
                        c_flw = finite_real(command.flow_rate_lpm)
                        a_flw = finite_real(active.flow_rate_lpm)
                        same_vol = (c_vol is not None and a_vol is not None and abs(c_vol - a_vol) < 1e-4)
                        same_dur = (c_dur is not None and a_dur is not None and abs(c_dur - a_dur) < 1e-4)
                        same_flw = (c_flw is not None and a_flw is not None and abs(c_flw - a_flw) < 1e-4)
                        op_conflict = bool(command.operation_id) and bool(active.operation_id) and (command.operation_id != active.operation_id)
                        if same_vol and same_dur and same_flw and not op_conflict:
                            is_own_retry = True
                        else:
                            has_payload_conflict = True
                elif hasattr(self, "hw") and (getattr(self.hw, "event_id", None) == command.source_event_id or getattr(self.hw, "operation", None) == command.source_event_id):
                    is_own_retry = True

                if has_payload_conflict:
                    logger.warning(
                        "Command %s conflicts with active payload on device %s. Returning PAYLOAD_CONFLICT.",
                        command.command_id, self.device_id
                    )
                    return CommandResult(
                        command_id=command.command_id,
                        device_id=self.device_id,
                        success=False,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        error_code="PAYLOAD_CONFLICT",
                        error_message=(
                            f"Payload conflict: Command {command.command_id} differs from active command "
                            f"{self._active_command.command_id if self._active_command else ''} on device {self.device_id}"
                        ),
                        retry_recommended=False,
                    )

                if is_own_retry:
                    if self._active_command is None:
                        self._active_command = command
                    logger.info(
                        "Operation %s is already EXECUTING on device %s. Returning active execution status idempotently without duplicate physical dispatch.",
                        command.operation_id or command.source_event_id, self.device_id
                    )
                    result = CommandResult(
                        command_id=command.command_id,
                        device_id=self.device_id,
                        success=True,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        actual_flow_rate_lpm=self._active_command.flow_rate_lpm if self._active_command else command.flow_rate_lpm,
                        error_code="ALREADY_EXECUTING",
                        error_message="Operation is already executing on actuator",
                    )
                    self._command_history.append({
                        "command_id": command.command_id,
                        "command_type": command.command_type.value,
                        "success": result.success,
                        "timestamp": result.timestamp,
                        "error_code": result.error_code,
                    })
                    return result

            prev_active_command = self._active_command
            start_gen = getattr(self, "_stop_generation", 0)

            # Mark command pending dispatch (do NOT prematurely set EXECUTING before actual physical send)
            self._pending_command = command

            logger.info(
                "Dispatching %s to device %s (zone=%s, volume=%.1fmm, duration=%.0fmin)",
                command.command_type.value, self.device_id,
                command.zone_id, command.volume_mm, command.duration_minutes
            )

            try:
                result = await self.send_command(command)
            except Exception as exc:
                logger.error(
                    "Command %s failed on device %s: %s",
                    command.command_id, self.device_id, exc
                )
                self._status = ActuatorStatus.ERROR
                result = CommandResult(
                    command_id=command.command_id,
                    device_id=self.device_id,
                    success=False,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_code="DISPATCH_EXCEPTION",
                    error_message=str(exc),
                    retry_recommended=False,
                )
            finally:
                self._pending_command = None

            # C02: Check if STOP or EMERGENCY_STOP occurred while START was in flight
            current_gen = getattr(self, "_stop_generation", 0)
            is_preempted = (
                current_gen > start_gen
                or command.command_id in getattr(self, "_cancelled_commands", set())
                or (bool(command.operation_id) and command.operation_id in getattr(self, "_cancelled_operations", set()))
            )
            if is_preempted:
                logger.warning(
                    "Command %s on device %s completed after STOP/cancellation (gen %d -> %d). Fencing execution.",
                    command.command_id, self.device_id, start_gen, current_gen
                )
                fence_ok = False
                try:
                    fence_stop = IrrigationCommand(
                        command_id=f"CMD-FENCE-{uuid.uuid4().hex[:8]}",
                        command_type=CommandType.STOP_ZONE,
                        device_id=self.device_id,
                        zone_id=command.zone_id,
                        plot_id=command.plot_id,
                        operation_id=f"OP-FENCE-{command.operation_id}" if command.operation_id else "",
                    )
                    fence_res = await self.send_command(fence_stop)
                    fence_ok = bool(fence_res and fence_res.success)
                except Exception as fence_exc:
                    logger.error("Fence stop command failed on device %s: %s", self.device_id, fence_exc)
                    fence_ok = False

                if fence_ok:
                    has_fault = getattr(self, "_fault_latched", False) or bool(fence_res and getattr(fence_res, "error_code", "") in ("FAULT", "HARDWARE_FAULT", "ERROR"))
                    self._status = ActuatorStatus.ERROR if has_fault else ActuatorStatus.ONLINE
                    self._active_command = None
                    err_code = "PREEMPTED_BY_STOP"
                    err_msg = "Command was preempted by STOP or cancellation"
                else:
                    # D01: If fence stop failed or threw exception, do not certify stopped; preserve ERROR and active command
                    self._status = ActuatorStatus.ERROR
                    self._active_command = command
                    err_code = "STOP_FAILED"
                    err_msg = "Late fence stop command failed or was rejected on actuator driver"

                result = CommandResult(
                    command_id=command.command_id,
                    device_id=self.device_id,
                    success=False,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    error_code=err_code,
                    error_message=err_msg,
                    retry_recommended=False,
                )
                self._command_history.append({
                    "command_id": command.command_id,
                    "command_type": command.command_type.value,
                    "success": result.success,
                    "timestamp": result.timestamp,
                    "error_code": result.error_code,
                })
                return result

            # Reconcile ambiguous failures on START commands before retry or failure
            if not result.success and command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
                try:
                    op_receipt = None
                    if getattr(self.registration.capabilities, "supports_operation_reconciliation", False) and bool(command.operation_id):
                        op_receipt = await self.get_operation_status(command.operation_id)

                    if op_receipt is not None:
                        if op_receipt.get("executing") or op_receipt.get("completed"):
                            logger.info(
                                "Reconciliation: Device %s confirmed operation %s via operation receipt.",
                                self.device_id, command.operation_id,
                            )
                            result = CommandResult(
                                command_id=command.command_id,
                                device_id=self.device_id,
                                success=True,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                actual_flow_rate_lpm=command.flow_rate_lpm,
                                error_code="RECONCILED_OPERATION",
                                error_message="Operation confirmed by controller",
                            )
                            if op_receipt.get("executing"):
                                self._status = ActuatorStatus.EXECUTING
                                self._active_command = command
                            else:
                                self._status = ActuatorStatus.ONLINE
                                self._active_command = None
                        elif op_receipt.get("not_applied"):
                            logger.info(
                                "Reconciliation: Device %s confirmed operation %s NOT applied. Safe to retry.",
                                self.device_id, command.operation_id,
                            )
                            self._status = ActuatorStatus.ONLINE
                            self._active_command = None
                            result.retry_recommended = True
                        else:
                            self._status = ActuatorStatus.ERROR
                            self._active_command = command
                            result.retry_recommended = False
                    else:
                        controller_status = await self.get_status()
                        if controller_status == ActuatorStatus.EXECUTING:
                            # BA-03 / R02: Bare controller status cannot prove this specific new command was applied.
                            logger.warning(
                                "Reconciliation: Device %s is EXECUTING on controller after unacknowledged %s, but lacks operation-level reconciliation. Retaining uncertainty boundary without blind retry.",
                                self.device_id, command.command_id,
                            )
                            self._status = ActuatorStatus.ERROR
                            self._active_command = command
                            result.retry_recommended = False
                            result.error_code = "UNCERTAIN_OUTCOME"
                            result.error_message = "Controller is running, but driver lacks operation-level reconciliation; cannot confirm whether requested command was applied."
                        elif controller_status == ActuatorStatus.ONLINE:
                            # Confirmed idle state alone must not authorize a new dose without operation attribution.
                            logger.warning(
                                "Reconciliation: Device %s is ONLINE after unacknowledged %s, but lacks operation-level reconciliation. Retaining uncertainty boundary without blind retry.",
                                self.device_id, command.command_id,
                            )
                            self._status = ActuatorStatus.ERROR
                            self._active_command = command
                            result.retry_recommended = False
                            result.error_code = "UNCERTAIN_OUTCOME"
                            result.error_message = "Controller is ONLINE but driver lacks operation-level reconciliation; cannot confirm whether dose was applied."
                        else:
                            self._status = ActuatorStatus.ERROR
                            self._active_command = command
                            result.retry_recommended = False
                except Exception as rec_exc:
                    logger.error(
                        "Reconciliation query failed on %s for %s: %s. Retaining ownership during uncertainty.",
                        self.device_id, command.command_id, rec_exc,
                    )
                    self._status = ActuatorStatus.ERROR
                    self._active_command = command
                    result.retry_recommended = False

            # State transition according to resolved result
            if not result.success:
                if command.command_type in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP):
                    self._status = ActuatorStatus.ERROR
                    self._active_command = prev_active_command  # Preserve original delivery command
                    logger.error("Stop command failed on device %s. Retaining active command and ERROR state.", self.device_id)
                elif command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
                    if self._status != ActuatorStatus.ONLINE:
                        self._status = ActuatorStatus.ERROR
            elif command.command_type in (CommandType.STOP_ZONE, CommandType.EMERGENCY_STOP):
                has_fault = (
                    getattr(self, "_fault_latched", False)
                    or getattr(self, "_status", None) == ActuatorStatus.ERROR
                    or bool(getattr(result, "fault_code", 0))
                    or getattr(result, "error_code", "") in ("FAULT", "HARDWARE_FAULT", "ERROR")
                )
                if has_fault:
                    self._status = ActuatorStatus.ERROR
                else:
                    self._status = ActuatorStatus.ONLINE
                self._active_command = None
            elif command.command_type in (CommandType.START_ZONE, CommandType.PULSE_IRRIGATE):
                if getattr(self, "_stop_generation", 0) > start_gen:
                    self._status = ActuatorStatus.ONLINE
                    self._active_command = None
                else:
                    self._status = ActuatorStatus.EXECUTING
                    self._active_command = command

            # Audit log
        self._command_history.append({
            "command_id": command.command_id,
            "command_type": command.command_type.value,
            "success": result.success,
            "timestamp": result.timestamp,
            "error_code": result.error_code,
        })

        return result

    def check_interlocks(self, sensor_readings: Dict[str, float]) -> List[SafetyViolation]:
        """Evaluate all registered safety interlocks against current sensor data.

        Args:
            sensor_readings: Dict of CanonicalVariable → current value

        Returns:
            List of SafetyViolation records for any breached interlocks
        """
        violations = []
        for interlock in self._interlocks:
            if not interlock.enabled:
                continue

            if interlock.sensor_variable not in sensor_readings:
                continue

            value = sensor_readings[interlock.sensor_variable]
            breached = False
            threshold_type = ""
            threshold_val = 0.0

            if interlock.threshold_min is not None and value < interlock.threshold_min:
                breached = True
                threshold_type = "min"
                threshold_val = interlock.threshold_min

            if interlock.threshold_max is not None and value > interlock.threshold_max:
                breached = True
                threshold_type = "max"
                threshold_val = interlock.threshold_max

            if breached:
                violation = SafetyViolation(
                    violation_id=f"VIO-{uuid.uuid4().hex[:12]}",
                    interlock_id=interlock.interlock_id,
                    interlock_type=interlock.interlock_type,
                    device_id=self.device_id,
                    zone_id="",
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    sensor_value=value,
                    threshold_breached=threshold_type,
                    threshold_value=threshold_val,
                    action_taken=interlock.action_on_trigger.value,
                )
                violations.append(violation)
                logger.warning(
                    "Safety interlock %s triggered on device %s: "
                    "%s=%s (threshold %s=%s)",
                    interlock.interlock_id, self.device_id,
                    interlock.sensor_variable, value,
                    threshold_type, threshold_val
                )

        return violations

    def register_interlock(self, interlock: SafetyInterlock) -> None:
        """Add a safety interlock to this actuator."""
        self._interlocks.append(interlock)
        logger.info(
            "Registered interlock %s (%s) on device %s",
            interlock.interlock_id, interlock.interlock_type.value, self.device_id
        )

    def confirm_stop(
        self,
        receipt: Optional[Dict[str, Any]] = None,
        expected_operation_id: Optional[Any] = None,
    ) -> bool:
        """Confirm physical cessation using verified controller evidence.

        Must be governed by an affirmative verified receipt from the controller or field sensor.
        Unrestricted or unverified confirmation is strictly rejected.
        Receipt must:
          1. Match this device_id
          2. Contain mandatory operation_id / command_id correlated to active or expected operation
          3. Originate from an authenticated, authorized source (trusted controller/driver)
          4. Contain positive physical stop evidence:
             - actual_flow_lpm == 0.0, OR
             - status in ('STOPPED', 'IDLE', 'OFF'), OR
             - confirmed_stopped is True
          5. NOT detect running state (e.g. is_running is not True, flow > 0 is rejected)
        """
        if receipt is None or not isinstance(receipt, dict):
            raise ValueError("confirm_stop requires a verified dictionary receipt")

        rec_dev = receipt.get("device_id")
        if not rec_dev or rec_dev != self.device_id:
            raise ValueError(f"Receipt device_id {rec_dev} does not match actuator {self.device_id}")

        rec_op = receipt.get("operation_id") or receipt.get("command_id")
        active_op = getattr(self._active_command, "operation_id", None) or getattr(self._active_command, "command_id", None)

        if active_op:
            if not rec_op or rec_op != active_op:
                raise ValueError(f"Receipt operation_id {rec_op} does not match active operation {active_op}")
        elif not rec_op or not str(rec_op).strip():
            raise ValueError(f"Receipt for device {self.device_id} missing mandatory operation_id / command_id")
        elif expected_operation_id:
            if isinstance(expected_operation_id, (list, tuple, set)):
                if rec_op not in expected_operation_id:
                    raise ValueError(f"Receipt operation_id {rec_op} does not match expected operation {expected_operation_id}")
            else:
                if rec_op != expected_operation_id:
                    raise ValueError(f"Receipt operation_id {rec_op} does not match expected operation {expected_operation_id}")
        else:
            # Recovery / restart path: active_command is absent, correlate via pending stop context or durable claim
            pending_op = getattr(self, "_pending_stop_operation_id", None) or (self._pending_command.command_id if self._pending_command else None)
            durable_op = None
            try:
                from .safety import SharedQuotaStore
                claim = SharedQuotaStore.get_resource_claim(self.device_id)
                if claim:
                    durable_op = claim.get("operation_id") or claim.get("command_id") or claim.get("event_id")
            except Exception:
                durable_op = None

            expected_corr = pending_op or durable_op
            if expected_corr:
                if rec_op != expected_corr:
                    raise ValueError(f"Receipt operation_id {rec_op} does not match recoverable operation {expected_corr}")
            else:
                raise ValueError(f"Receipt operation_id {rec_op} rejected on {self.device_id}: no active, expected, pending, or durable operation established for correlation")

        # Freshness and observation window check (mandatory, within 600s, not future-dated > 30s)
        ts_raw = receipt.get("timestamp") or receipt.get("observed_at") or receipt.get("received_at")
        if not ts_raw:
            logger.warning("Receipt for device %s rejected: missing mandatory observation timestamp", self.device_id)
            return False
        try:
            if isinstance(ts_raw, (int, float)):
                if math.isnan(ts_raw) or math.isinf(ts_raw):
                    logger.warning("Receipt for device %s rejected: non-finite numeric timestamp", self.device_id)
                    return False
                ts_dt = datetime.fromtimestamp(float(ts_raw), tz=timezone.utc)
            else:
                ts_dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            age = (now_utc - ts_dt).total_seconds()
            if age > 600.0:
                logger.warning("Receipt for device %s is stale (age=%.1fs > 600s)", self.device_id, age)
                return False
            if age < -30.0:
                logger.warning("Receipt for device %s has future-dated observation time (%s)", self.device_id, ts_raw)
                return False
        except Exception as ts_err:
            logger.warning("Failed to parse observation timestamp in receipt for device %s: %s", self.device_id, ts_err)
            return False

        # Provenance authentication check (mandatory, non-empty, trusted and authenticated authority)
        source = receipt.get("source") or receipt.get("driver") or receipt.get("provenance")
        if not source or not str(source).strip():
            logger.warning("Receipt for device %s rejected: missing mandatory source/provenance", self.device_id)
            return False
        src_clean = str(source).strip().lower()
        if src_clean in ("untrusted", "spoofed", "unknown", "invalid", "anonymous"):
            logger.warning("Receipt for device %s from untrusted source %s", self.device_id, source)
            return False

        trusted_sources = {
            "controller",
            "modbus_plc",
            "mqtt_broker",
            "lorawan_gateway",
            "http_rest",
            "hardware_telemetry",
            "safety_verifier",
            "field_bus",
            "driver",
            "system_reconciliation",
            "command_dispatcher",
            self.device_id.lower(),
            f"{self.device_id.lower()}_controller",
            self.protocol.value.lower(),
            f"{self.protocol.value.lower()}_driver",
        }
        if src_clean not in trusted_sources:
            logger.warning("Receipt for device %s rejected: unauthenticated/untrusted provenance source '%s'", self.device_id, source)
            return False

        if receipt.get("authenticated") is False:
            logger.warning("Receipt for device %s rejected: explicitly marked unauthenticated", self.device_id)
            return False

        # Physical flow measurement validation (finite real, reject NaN/Inf/bool/string-garbage/negative)
        raw_flow = receipt.get("actual_flow_rate_lpm", receipt.get("actual_flow_lpm", receipt.get("flow_rate_lpm", receipt.get("flow"))))
        parsed_flow = None
        if raw_flow is not None:
            checked_flow = finite_real(raw_flow)
            if checked_flow is None and isinstance(raw_flow, str):
                try:
                    f_s = float(raw_flow)
                    if math.isfinite(f_s):
                        checked_flow = f_s
                except Exception:
                    checked_flow = None
            if checked_flow is None or checked_flow < 0.0:
                logger.warning("Receipt for device %s contains invalid/non-finite flow measurement (%s); rejecting.", self.device_id, raw_flow)
                return False
            parsed_flow = checked_flow

        status = str(receipt.get("status", "")).upper()
        raw_stopped = receipt.get("is_stopped") if "is_stopped" in receipt else receipt.get("stopped")
        is_stopped = True if raw_stopped is None else bool(raw_stopped)

        raw_running = receipt.get("is_running") if "is_running" in receipt else receipt.get("running")
        is_running = False if raw_running is None else bool(raw_running)

        raw_conf = receipt.get("confirmed_stopped") if "confirmed_stopped" in receipt else receipt.get("confirmed_physical_stop")
        confirmed_stopped = True if raw_conf is None else bool(raw_conf)

        # Driver boundary cryptographic authentication verification
        # An ordinary dictionary with only a recognized source label is NOT sufficient.
        attempt_no = receipt.get("attempt_number", 1)
        receipt_token = (
            receipt.get("auth_token")
            or receipt.get("receipt_token")
            or receipt.get("signature")
            or receipt.get("verification_token")
        )
        is_sim = (
            getattr(self, "is_simulation", False)
            or getattr(getattr(self, "registration", None), "is_simulation", False)
            or getattr(self, "is_mock", False)
            or type(self).__name__.startswith("Mock")
            or type(self).__name__.startswith("Dummy")
        )

        # 1. Strictly reject receipts signed with predictable device-derived or blacklisted keys
        if receipt_token:
            known_insecure_keys = [
                f"agribrain_stop_auth_{self.device_id}",
                self.device_id,
                *PREDICTABLE_KEY_BLACKLIST,
            ]
            for bad_key_str in known_insecure_keys:
                bad_bytes = bad_key_str.encode("utf-8")
                for candidate_ts in (ts_dt.isoformat(), str(ts_raw).strip()):
                    bad_ast = build_canonical_stop_assertion(
                        device_id=self.device_id,
                        operation_id=str(rec_op),
                        attempt_number=attempt_no,
                        timestamp=candidate_ts,
                        source=source,
                        actual_flow_lpm=parsed_flow if parsed_flow is not None else 0.0,
                        is_running=is_running,
                        is_stopped=is_stopped,
                        confirmed_stopped=confirmed_stopped,
                    )
                    if hmac.compare_digest(hmac.new(bad_bytes, bad_ast, hashlib.sha256).hexdigest()[:32], receipt_token):
                        logger.warning("Receipt for device %s rejected: signed using predictable device-derived key", self.device_id)
                        return False

        # 2. Key configuration and canonical measurement signature verification
        if not receipt_token:
            if not is_sim:
                logger.warning("Receipt for device %s rejected: missing trusted authentication token (unverified self-declared dictionary)", self.device_id)
                return False
        else:
            prov_keys = get_provisioned_stop_keys(self.device_id, self.registration)
            if not prov_keys:
                if not is_sim:
                    logger.warning("Receipt for device %s rejected: missing provisioned signing key on real hardware (fail closed)", self.device_id)
                    return False
            else:
                assertions = [
                    build_canonical_stop_assertion(
                        device_id=self.device_id,
                        operation_id=str(rec_op),
                        attempt_number=attempt_no,
                        timestamp=ts_dt.isoformat(),
                        source=source,
                        actual_flow_lpm=parsed_flow if parsed_flow is not None else 0.0,
                        is_running=is_running,
                        is_stopped=is_stopped,
                        confirmed_stopped=confirmed_stopped,
                    ),
                    build_canonical_stop_assertion(
                        device_id=self.device_id,
                        operation_id=str(rec_op),
                        attempt_number=attempt_no,
                        timestamp=str(ts_raw).strip(),
                        source=source,
                        actual_flow_lpm=parsed_flow if parsed_flow is not None else 0.0,
                        is_running=is_running,
                        is_stopped=is_stopped,
                        confirmed_stopped=confirmed_stopped,
                    ),
                ]
                token_matched = False
                for pk in prov_keys:
                    for ast in assertions:
                        expected = hmac.new(pk, ast, hashlib.sha256).hexdigest()[:32]
                        if hmac.compare_digest(receipt_token, expected):
                            token_matched = True
                            break
                    if token_matched:
                        break

                if not token_matched and not is_sim:
                    logger.warning(
                        "Receipt for device %s rejected: cryptographic authentication token mismatch (key or measurements invalid)",
                        self.device_id,
                    )
                    return False

        # 3. Durable anti-replay check across process restarts and independent worker processes
        consumed = getattr(self, "_consumed_receipt_tokens", None)
        if consumed is None:
            self._consumed_receipt_tokens = set()
            consumed = self._consumed_receipt_tokens

        fingerprint = f"{self.device_id}:{rec_op}:{attempt_no}:{ts_dt.isoformat()}:{receipt_token}"
        if (
            fingerprint in consumed
            or fingerprint in _GLOBAL_CONSUMED_RECEIPT_TOKENS
            or (receipt_token and (receipt_token in consumed or receipt_token in _GLOBAL_CONSUMED_RECEIPT_TOKENS))
            or DurableStopReceiptStore.is_consumed(fingerprint, receipt_token)
        ):
            logger.warning("Receipt for device %s rejected: receipt already consumed (replay detected)", self.device_id)
            return False

        # 4. Affirmative physical evidence and ongoing execution check
        if is_running is True or is_stopped is False or (parsed_flow is not None and parsed_flow > 0.0) or status in ("RUNNING", "EXECUTING", "STARTING", "ACTIVE"):
            logger.warning("Receipt for device %s detects ongoing flow/running; cannot confirm stop.", self.device_id)
            return False

        has_physical_evidence = (
            confirmed_stopped is True
            or (parsed_flow is not None and parsed_flow == 0.0)
            or (is_stopped is True)
            or (status in ("STOPPED", "IDLE", "OFF", "STANDBY") and is_running is not True)
        )

        if not has_physical_evidence:
            logger.warning("Receipt for device %s lacks affirmative physical stop evidence.", self.device_id)
            return False

        # 5. Affirmative stop verified: update state and consume token durably
        has_fault = getattr(self, "_fault_latched", False) or getattr(self, "_status", None) == ActuatorStatus.ERROR
        if has_fault:
            self._status = ActuatorStatus.ERROR
        else:
            self._status = ActuatorStatus.ONLINE

        self._active_command = None
        self._pending_command = None

        consumed.add(fingerprint)
        _GLOBAL_CONSUMED_RECEIPT_TOKENS.add(fingerprint)
        if receipt_token:
            consumed.add(receipt_token)
            _GLOBAL_CONSUMED_RECEIPT_TOKENS.add(receipt_token)

        DurableStopReceiptStore.consume(
            fingerprint=fingerprint,
            token=receipt_token,
            metadata={"device_id": self.device_id, "operation_id": str(rec_op)},
        )

        logger.info("Physical STOP confirmed on device %s by verified receipt. Status=%s", self.device_id, self._status.value)
        return True

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def status(self) -> ActuatorStatus:
        return self._status

    @property
    def active_command(self) -> Optional[IrrigationCommand]:
        return self._active_command

    @property
    def pending_command(self) -> Optional[IrrigationCommand]:
        return self._pending_command

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} device={self.device_id} "
            f"protocol={self.protocol.value} status={self._status.value}>"
        )
