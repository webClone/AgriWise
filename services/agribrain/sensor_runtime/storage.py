from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sensor_runtime.schemas import RawSensorMessage, NormalizedSensorReading

logger = logging.getLogger(__name__)


class StorageCorruptedError(RuntimeError):
    """Raised when durable storage or normalized log contains corrupted or invalid data."""
    pass


def _lock_file_exclusive(fd: int, timeout: float = 10.0) -> None:
    start_t = time.monotonic()
    if sys.platform == "win32":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return
            except (BlockingIOError, OSError, PermissionError):
                if time.monotonic() - start_t > timeout:
                    raise TimeoutError(f"Timed out after {timeout}s waiting for file lock")
                time.sleep(0.01)
    else:
        import fcntl
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except (BlockingIOError, OSError):
                if time.monotonic() - start_t > timeout:
                    raise TimeoutError(f"Timed out after {timeout}s waiting for file lock")
                time.sleep(0.01)


def _unlock_file(fd: int) -> None:
    if sys.platform == "win32":
        import msvcrt
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
    else:
        import fcntl
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except Exception:
            pass

# Durable storage root configuration
def _get_storage_dir() -> Path:
    env_dir = os.getenv("AGRIWISE_SENSOR_STORAGE_DIR")
    if env_dir:
        p = Path(env_dir).resolve()
    else:
        p = (Path(__file__).resolve().parent / ".sensor_store").resolve()
    p.mkdir(parents=True, exist_ok=True)
    (p / "raw").mkdir(parents=True, exist_ok=True)
    (p / "normalized").mkdir(parents=True, exist_ok=True)
    return p


_STORAGE_LOCK = threading.RLock()
_RAW_STORAGE: Dict[str, RawSensorMessage] = {}
_NORMALIZED_STORAGE: List[NormalizedSensorReading] = []
_LAST_NORM_FILE_STAT: tuple[float, int] = (0.0, 0)
_INITIALIZED = False

_VALID_ID_RE = re.compile(r"^[a-zA-Z0-9_\-\.:]+$")


def _serialize_datetime(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _validate_and_encode_id(identifier: str) -> str:
    """Validate identifier characters and produce a strictly injective, collision-free filename key.
    
    Rejects path traversal and unsupported characters.
    Appends SHA-256 digest so two distinct identifiers (e.g. urn:dev:123 vs urn_COLON_dev_COLON_123)
    can never map to the same filename key.
    """
    if not identifier or not isinstance(identifier, str):
        raise ValueError("message_id must be a non-empty string")
    if ".." in identifier or "/" in identifier or "\\" in identifier or not _VALID_ID_RE.match(identifier):
        raise ValueError(f"invalid_message_id: '{identifier}' contains invalid characters or path traversal")
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    clean_prefix = re.sub(r"[^a-zA-Z0-9_\-]", "_", identifier)[:48]
    return f"{clean_prefix}_{digest}"


def _sanitize_id(identifier: str) -> str:
    return _validate_and_encode_id(identifier)


def _acquire_and_append(target_file: Path, lock_file: Path, data: bytes, timeout: float = 10.0) -> None:
    """Append data to target_file under OS-backed advisory lock.
    
    Uses msvcrt.locking on Windows and fcntl.flock on POSIX.
    The OS automatically releases the lock upon process termination or crash,
    preventing both lock-file leakage and stale-lock theft under stalled writers.
    """
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR, 0o666)
    try:
        if os.fstat(lock_fd).st_size == 0:
            try:
                os.write(lock_fd, b"L")
                os.fsync(lock_fd)
            except Exception:
                pass
        _lock_file_exclusive(lock_fd, timeout=timeout)
        try:
            with open(target_file, "ab") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
        finally:
            _unlock_file(lock_fd)
    finally:
        try:
            os.close(lock_fd)
        except Exception:
            pass


def rehydrate_storage() -> None:
    """Rehydrate in-memory lookup indices from durable disk storage."""
    global _RAW_STORAGE, _NORMALIZED_STORAGE, _INITIALIZED
    with _STORAGE_LOCK:
        _RAW_STORAGE.clear()
        _NORMALIZED_STORAGE.clear()
        storage_dir = _get_storage_dir()
        raw_dir = storage_dir / "raw"
        for raw_file in raw_dir.glob("raw_*.json"):
            try:
                if raw_file.stat().st_size == 0:
                    try:
                        raw_file.unlink(missing_ok=True)
                    except Exception:
                        pass
                    continue
                with open(raw_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                r_at = datetime.fromisoformat(data["received_at"])
                msg = RawSensorMessage(
                    message_id=data["message_id"],
                    protocol=data["protocol"],
                    received_at=r_at,
                    device_id=data["device_id"],
                    payload=data["payload"],
                    gateway_id=data.get("gateway_id"),
                    rssi=data.get("rssi"),
                    snr=data.get("snr"),
                    raw_payload_ref=data.get("raw_payload_ref", ""),
                    provenance=data.get("provenance") or {},
                )
                _RAW_STORAGE[msg.message_id] = msg
            except Exception as exc:
                logger.warning("Failed to rehydrate raw sensor message %s: %s", raw_file, exc)

        norm_file = storage_dir / "normalized" / "normalized_readings.jsonl"
        if norm_file.exists():
            st = norm_file.stat()
            _LAST_NORM_FILE_STAT = (st.st_mtime, st.st_size)
            with open(norm_file, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r_data = json.loads(line)
                        reading = NormalizedSensorReading(
                            reading_id=r_data["reading_id"],
                            device_id=r_data["device_id"],
                            plot_id=r_data["plot_id"],
                            zone_id=r_data.get("zone_id"),
                            timestamp=datetime.fromisoformat(r_data["timestamp"]),
                            received_at=datetime.fromisoformat(r_data["received_at"]),
                            variable=r_data["variable"],
                            value=r_data["value"],
                            unit=r_data["unit"],
                            vendor=r_data["vendor"],
                            protocol=r_data["protocol"],
                            depth_cm=r_data.get("depth_cm"),
                            depth_interval_cm=tuple(r_data["depth_interval_cm"]) if r_data.get("depth_interval_cm") else None,
                            latitude=r_data.get("latitude"),
                            longitude=r_data.get("longitude"),
                            model=r_data.get("model"),
                            raw_payload_ref=r_data.get("raw_payload_ref", ""),
                            normalization_version=r_data.get("normalization_version", "1.0"),
                            original_unit=r_data.get("original_unit"),
                            original_value=r_data.get("original_value"),
                            rainfall_mode=r_data.get("rainfall_mode"),
                        )
                        _NORMALIZED_STORAGE.append(reading)
                    except Exception as parse_err:
                        raise StorageCorruptedError(
                            f"Corrupted record in normalized storage log {norm_file} at line {line_no}: {parse_err}"
                        ) from parse_err

        _INITIALIZED = True


def _ensure_initialized() -> None:
    global _INITIALIZED
    if not _INITIALIZED:
        rehydrate_storage()


def store_raw_message(msg: RawSensorMessage) -> None:
    """Store immutable raw payload with atomic cross-process durability and uniqueness."""
    _ensure_initialized()
    with _STORAGE_LOCK:
        if msg.message_id in _RAW_STORAGE:
            raise ValueError("Raw message is immutable and cannot be overwritten.")

        clean_id = _validate_and_encode_id(msg.message_id)
        storage_dir = _get_storage_dir()
        raw_file = storage_dir / "raw" / f"raw_{clean_id}.json"

        if raw_file.exists():
            raise ValueError("Raw message is immutable and cannot be overwritten.")

        stored = copy.deepcopy(msg)

        payload_data = {
            "message_id": stored.message_id,
            "protocol": stored.protocol,
            "received_at": stored.received_at.isoformat(),
            "device_id": stored.device_id,
            "payload": stored.payload,
            "gateway_id": stored.gateway_id,
            "rssi": stored.rssi,
            "snr": stored.snr,
            "raw_payload_ref": stored.raw_payload_ref,
            "provenance": stored.provenance or {},
        }

        # Crash-safe atomic publication with transactional advisory locking:
        # 1. Write full content to temporary file with fsync first
        raw_dir = raw_file.parent
        raw_lock_file = raw_dir / ".raw_publication.lock"
        tmp_file = raw_dir / f"tmp_{uuid.uuid4().hex}_{os.getpid()}.json"

        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(payload_data, f, default=_serialize_datetime, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # 2. Acquire publication lock for raw messages
            try:
                lock_fd = os.open(str(raw_lock_file), os.O_CREAT | os.O_RDWR, 0o666)
            except FileExistsError:
                raise ValueError("Raw message is immutable and cannot be overwritten.")
            try:
                if os.fstat(lock_fd).st_size == 0:
                    try:
                        os.write(lock_fd, b"L")
                        os.fsync(lock_fd)
                    except Exception:
                        pass
                _lock_file_exclusive(lock_fd, timeout=10.0)
                try:
                    # Under exclusive publication lock:
                    if raw_file.exists():
                        if raw_file.stat().st_size > 0:
                            raise ValueError("Raw message is immutable and cannot be overwritten.")
                        else:
                            # 0-byte orphan from a prior hard crash, remove it
                            raw_file.unlink(missing_ok=True)

                    # Atomically publish content to final destination file
                    os.replace(str(tmp_file), str(raw_file))
                finally:
                    _unlock_file(lock_fd)
            finally:
                try:
                    os.close(lock_fd)
                except Exception:
                    pass
        finally:
            tmp_file.unlink(missing_ok=True)

        _RAW_STORAGE[stored.message_id] = stored


def store_normalized_reading(reading: NormalizedSensorReading) -> None:
    """Store versioned normalized reading with cross-process append-only durability."""
    global _LAST_NORM_FILE_STAT
    _ensure_initialized()
    with _STORAGE_LOCK:
        stored = copy.deepcopy(reading)

        storage_dir = _get_storage_dir()
        norm_file = storage_dir / "normalized" / "normalized_readings.jsonl"
        lock_file = storage_dir / "normalized" / "normalized_readings.lock"

        reading_dict = {
            "reading_id": stored.reading_id,
            "device_id": stored.device_id,
            "plot_id": stored.plot_id,
            "zone_id": stored.zone_id,
            "timestamp": stored.timestamp.isoformat(),
            "received_at": stored.received_at.isoformat(),
            "variable": stored.variable,
            "value": stored.value,
            "unit": stored.unit,
            "vendor": stored.vendor,
            "protocol": stored.protocol,
            "depth_cm": stored.depth_cm,
            "depth_interval_cm": list(stored.depth_interval_cm) if stored.depth_interval_cm else None,
            "latitude": stored.latitude,
            "longitude": stored.longitude,
            "model": stored.model,
            "raw_payload_ref": stored.raw_payload_ref,
            "normalization_version": stored.normalization_version,
            "original_unit": stored.original_unit,
            "original_value": stored.original_value,
            "rainfall_mode": stored.rainfall_mode,
        }
        data_bytes = (json.dumps(reading_dict, default=_serialize_datetime) + "\n").encode("utf-8")
        # Persist to disk and fsync FIRST before in-memory append
        _acquire_and_append(norm_file, lock_file, data_bytes)
        try:
            st = norm_file.stat()
            _LAST_NORM_FILE_STAT = (st.st_mtime, st.st_size)
        except Exception:
            pass
        _NORMALIZED_STORAGE.append(stored)


def _rehydrate_normalized_from_disk_if_changed() -> None:
    global _NORMALIZED_STORAGE, _LAST_NORM_FILE_STAT
    storage_dir = _get_storage_dir()
    norm_file = storage_dir / "normalized" / "normalized_readings.jsonl"
    if not norm_file.exists():
        _NORMALIZED_STORAGE.clear()
        _LAST_NORM_FILE_STAT = (0.0, 0)
        return

    st = norm_file.stat()
    curr_stat = (st.st_mtime, st.st_size)
    if curr_stat != _LAST_NORM_FILE_STAT:
            readings = []
            with open(norm_file, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r_data = json.loads(line)
                        reading = NormalizedSensorReading(
                            reading_id=r_data["reading_id"],
                            device_id=r_data["device_id"],
                            plot_id=r_data["plot_id"],
                            zone_id=r_data.get("zone_id"),
                            timestamp=datetime.fromisoformat(r_data["timestamp"]),
                            received_at=datetime.fromisoformat(r_data["received_at"]),
                            variable=r_data["variable"],
                            value=r_data["value"],
                            unit=r_data["unit"],
                            vendor=r_data["vendor"],
                            protocol=r_data["protocol"],
                            depth_cm=r_data.get("depth_cm"),
                            depth_interval_cm=tuple(r_data["depth_interval_cm"]) if r_data.get("depth_interval_cm") else None,
                            latitude=r_data.get("latitude"),
                            longitude=r_data.get("longitude"),
                            model=r_data.get("model"),
                            raw_payload_ref=r_data.get("raw_payload_ref", ""),
                            normalization_version=r_data.get("normalization_version", "1.0"),
                            original_unit=r_data.get("original_unit"),
                            original_value=r_data.get("original_value"),
                            rainfall_mode=r_data.get("rainfall_mode"),
                        )
                        readings.append(reading)
                    except Exception as parse_err:
                        raise StorageCorruptedError(
                            f"Corrupted record in normalized storage log {norm_file} at line {line_no}: {parse_err}"
                        ) from parse_err
            _NORMALIZED_STORAGE = readings
            _LAST_NORM_FILE_STAT = curr_stat


def get_raw_message(message_id: str) -> RawSensorMessage | None:
    """Retrieve immutable raw message by ID."""
    _ensure_initialized()
    with _STORAGE_LOCK:
        res = _RAW_STORAGE.get(message_id)
        if res is not None:
            return copy.deepcopy(res)

        # Check disk directly if not in memory
        storage_dir = _get_storage_dir()
        clean_id = _sanitize_id(message_id)
        raw_file = storage_dir / "raw" / f"raw_{clean_id}.json"
        if raw_file.exists():
            try:
                with open(raw_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                r_at = datetime.fromisoformat(data["received_at"])
                msg = RawSensorMessage(
                    message_id=data["message_id"],
                    protocol=data["protocol"],
                    received_at=r_at,
                    device_id=data["device_id"],
                    payload=data["payload"],
                    gateway_id=data.get("gateway_id"),
                    rssi=data.get("rssi"),
                    snr=data.get("snr"),
                    raw_payload_ref=data.get("raw_payload_ref", ""),
                    provenance=data.get("provenance") or {},
                )
                _RAW_STORAGE[msg.message_id] = msg
                return copy.deepcopy(msg)
            except Exception as exc:
                logger.warning("Error reading raw sensor file %s: %s", raw_file, exc)

        return None


def get_normalized_readings(device_id: Optional[str] = None) -> List[NormalizedSensorReading]:
    """Retrieve stored normalized readings, optionally filtered by device_id."""
    _ensure_initialized()
    with _STORAGE_LOCK:
        _rehydrate_normalized_from_disk_if_changed()
        if device_id is None:
            return copy.deepcopy(_NORMALIZED_STORAGE)
        return [copy.deepcopy(r) for r in _NORMALIZED_STORAGE if r.device_id == device_id]


def clear_storage() -> None:
    """Clear storage for testing and isolated fixture execution."""
    global _RAW_STORAGE, _NORMALIZED_STORAGE, _LAST_NORM_FILE_STAT, _INITIALIZED
    with _STORAGE_LOCK:
        _RAW_STORAGE.clear()
        _NORMALIZED_STORAGE.clear()
        _LAST_NORM_FILE_STAT = (0.0, 0)
        storage_dir = _get_storage_dir()
        import shutil
        raw_dir = storage_dir / "raw"
        if raw_dir.exists():
            shutil.rmtree(raw_dir)
            raw_dir.mkdir(parents=True, exist_ok=True)
        norm_dir = storage_dir / "normalized"
        if norm_dir.exists():
            shutil.rmtree(norm_dir)
            norm_dir.mkdir(parents=True, exist_ok=True)
        _INITIALIZED = True
