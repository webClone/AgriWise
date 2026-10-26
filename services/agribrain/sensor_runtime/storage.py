from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sensor_runtime.schemas import RawSensorMessage, NormalizedSensorReading

logger = logging.getLogger(__name__)

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


def _acquire_and_append(target_file: Path, lock_file: Path, data: bytes, timeout: float = 5.0) -> None:
    start_time = time.monotonic()
    acquired = False
    lock_fd = None
    while time.monotonic() - start_time < timeout:
        try:
            lock_fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            acquired = True
            break
        except FileExistsError:
            time.sleep(0.01)

    if not acquired:
        try:
            if lock_file.exists() and (time.time() - lock_file.stat().st_mtime) > 10.0:
                lock_file.unlink(missing_ok=True)
        except Exception:
            pass
        lock_fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)

    try:
        with open(target_file, "ab") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    finally:
        if lock_fd is not None:
            try:
                os.close(lock_fd)
            except Exception:
                pass
        try:
            lock_file.unlink(missing_ok=True)
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
            try:
                st = norm_file.stat()
                _LAST_NORM_FILE_STAT = (st.st_mtime, st.st_size)
                with open(norm_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
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
            except Exception as exc:
                logger.warning("Failed to rehydrate normalized readings from %s: %s", norm_file, exc)

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

        # Crash-safe atomic publication:
        # Write to temporary file with fsync first to prevent partial records
        raw_dir = raw_file.parent
        tmp_file = raw_dir / f"tmp_{uuid.uuid4().hex}_{os.getpid()}.json"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(payload_data, f, default=_serialize_datetime, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # Exclusively create/claim raw_file (fails with FileExistsError if already exists)
            try:
                fd = os.open(str(raw_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                os.close(fd)
            except FileExistsError:
                raise ValueError("Raw message is immutable and cannot be overwritten.")

            # Atomically publish content to claimed file
            try:
                os.replace(str(tmp_file), str(raw_file))
            except Exception:
                raw_file.unlink(missing_ok=True)
                raise
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
    try:
        st = norm_file.stat()
        curr_stat = (st.st_mtime, st.st_size)
        if curr_stat != _LAST_NORM_FILE_STAT:
            readings = []
            with open(norm_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
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
            _NORMALIZED_STORAGE = readings
            _LAST_NORM_FILE_STAT = curr_stat
    except Exception as exc:
        logger.warning("Error rehydrating normalized readings from %s: %s", norm_file, exc)


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
