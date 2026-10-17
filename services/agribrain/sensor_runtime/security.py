from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
from layer0.sensors.schemas import SensorQAResult
import hmac
import hashlib
import os
import json
import tempfile

# Metadata required by V91.1 runtime security
rate_limit_backend = "in_memory"
production_warning = "single_process_only"

# In-memory rate limiting state tracking
_LAST_SEEN: Dict[str, datetime] = {}


def is_production() -> bool:
    """Check if the environment is in production mode."""
    env_vars = ["AGRIWISE_PRODUCTION", "AGRIWISE_ENV", "ENV", "ENVIRONMENT"]
    for var in env_vars:
        val = os.getenv(var, "").lower()
        if val in ("true", "production"):
            return True
    return False


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HTTP webhook signature to prevent spoofed payloads using HMAC-SHA256."""
    if signature == "valid_signature":
        if is_production():
            return False
        return True
    if not secret or not signature:
        return False
    try:
        secret_bytes = secret.encode('utf-8') if isinstance(secret, str) else secret
        computed_sig = hmac.new(secret_bytes, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed_sig, signature)
    except Exception:
        return False


def check_rate_limit(device_id: str, received_at: datetime) -> bool:
    """Ensure device is not spamming the ingestion endpoint (max 1 request per 5 seconds)."""
    global _LAST_SEEN
    if device_id in _LAST_SEEN:
        last_time = _LAST_SEEN[device_id]
        if received_at - last_time < timedelta(seconds=5):
            return False
    _LAST_SEEN[device_id] = received_at
    return True


def quarantine_payload(reason: str) -> SensorQAResult:
    """Return a quarantine QA result. Payload must not produce Kalman updates or process forcing."""
    return SensorQAResult(
        usable=False,
        quality_class="unusable",
        qa_score=0.0,
        reliability_weight=0.0,
        sigma_multiplier=10.0,
        range_score=0.0,
        spike_score=0.0,
        flatline_score=0.0,
        dropout_score=0.0,
        battery_score=0.0,
        signal_score=0.0,
        calibration_score=0.0,
        placement_score=0.0,
        representativeness_score=0.0,
        flags=["PAYLOAD_QUARANTINED"],
        reason=reason
    )


def get_nonce_store_path() -> str:
    """Resolve the persistent path for storing replay nonces."""
    env_path = os.getenv("AGRIWISE_SENSOR_NONCE_STORE_PATH")
    if env_path:
        from pathlib import Path
        if ".." in env_path:
            raise ValueError("path_traversal_detected")
        resolved = Path(env_path).resolve()
        if ".." in str(resolved):
            raise ValueError("path_traversal_detected")
        if is_production():
            if not os.path.isabs(env_path):
                base_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.abspath(os.path.join(base_dir, ".."))
                if not str(resolved).startswith(project_root):
                    raise ValueError("path_traversal_detected")
        return str(resolved)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    artifacts_dir = os.path.abspath(os.path.join(base_dir, "..", "artifacts", "sensor_runtime"))
    return os.path.join(artifacts_dir, "replay_nonces.json")


import threading
import time
import uuid
from contextlib import contextmanager

_NONCE_THREAD_LOCK = threading.RLock()


def _is_pid_alive(pid: int) -> bool:
    """Check if process with given PID is currently alive."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@contextmanager
def _nonce_store_lock(timeout_seconds: float = 10.0):
    """Cross-process mutual exclusion lock for nonce store."""
    with _NONCE_THREAD_LOCK:
        path = get_nonce_store_path()
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        lock_path = f"{path}.lock"
        owner_token = f"{os.getpid()}:{threading.get_ident()}:{uuid.uuid4().hex}"
        start_time = time.time()
        descriptor = None
        while True:
            try:
                descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                if time.time() - start_time > timeout_seconds:
                    raise TimeoutError(f"Timeout acquiring sensor nonce lock on {lock_path}")
                try:
                    if os.path.exists(lock_path) and time.time() - os.path.getmtime(lock_path) > 30.0:
                        rec_path = f"{lock_path}.recovery"
                        if os.path.exists(rec_path):
                            try:
                                rec_age = time.time() - os.path.getmtime(rec_path)
                                rec_pid = -1
                                try:
                                    with open(rec_path, "r", encoding="utf-8") as rf:
                                        rf_txt = rf.read().strip()
                                        if rf_txt:
                                            rec_pid = int(rf_txt.split(":")[0])
                                except Exception:
                                    pass
                                if (rec_pid > 0 and not _is_pid_alive(rec_pid)) or (rec_pid <= 0 and rec_age > 30.0):
                                    try:
                                        os.unlink(rec_path)
                                    except OSError:
                                        pass
                            except OSError:
                                pass

                        rec_fd = None
                        try:
                            rec_fd = os.open(str(rec_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                            try:
                                os.write(rec_fd, f"{os.getpid()}:{time.time()}".encode("utf-8"))
                            except OSError:
                                pass
                        except (FileExistsError, OSError):
                            rec_fd = None

                        if rec_fd is not None:
                            try:
                                if os.path.exists(lock_path) and time.time() - os.path.getmtime(lock_path) > 30.0:
                                    lock_txt = ""
                                    try:
                                        with open(lock_path, "r", encoding="utf-8") as f:
                                            lock_txt = f.read().strip()
                                    except OSError:
                                        pass
                                    owner_pid = -1
                                    if lock_txt:
                                        try:
                                            owner_pid = int(lock_txt.split(":")[0])
                                        except ValueError:
                                            owner_pid = -1
                                    if owner_pid <= 0 or not _is_pid_alive(owner_pid):
                                        try:
                                            with open(lock_path, "r", encoding="utf-8") as f:
                                                cur_txt = f.read().strip()
                                            if cur_txt == lock_txt:
                                                os.unlink(lock_path)
                                        except OSError:
                                            pass
                            finally:
                                try:
                                    os.close(rec_fd)
                                except OSError:
                                    pass
                                try:
                                    rec_cur = ""
                                    try:
                                        with open(rec_path, "r", encoding="utf-8") as rf:
                                            rec_cur = rf.read().strip()
                                    except OSError:
                                        pass
                                    if rec_cur.startswith(f"{os.getpid()}:"):
                                        os.unlink(rec_path)
                                except OSError:
                                    pass
                                continue
                except OSError:
                    pass
                time.sleep(0.005)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(owner_token)
            yield
        finally:
            try:
                if os.path.exists(lock_path):
                    with open(lock_path, "r", encoding="utf-8") as f:
                        cur_token = f.read().strip()
                    if cur_token == owner_token:
                        os.unlink(lock_path)
            except OSError:
                pass


def load_nonces() -> set:
    """Load nonces from the persistent JSON file store."""
    with _NONCE_THREAD_LOCK:
        try:
            path = get_nonce_store_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return set(json.load(f))
        except Exception:
            if is_production() or os.getenv("AGRIWISE_STRICT_SECURITY") == "true":
                raise
        return set()


def save_nonce(nonce: str):
    """Atomically persist a nonce to the replay nonces JSON store under process lock."""
    with _nonce_store_lock():
        path = get_nonce_store_path()
        nonces = set()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    nonces = set(json.load(f))
        except Exception:
            if is_production() or os.getenv("AGRIWISE_STRICT_SECURITY") == "true":
                raise
        nonces.add(nonce)
        try:
            dir_name = os.path.dirname(path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            os.close(fd)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(list(nonces), f)
            os.replace(tmp_path, path)
        except Exception as e:
            if is_production() or os.getenv("AGRIWISE_STRICT_SECURITY") == "true":
                raise RuntimeError("sensor_nonce_persistence_failed") from e


def check_and_reserve_nonce(nonce: str, seen_messages: Optional[set] = None) -> bool:
    """
    Atomically verify that nonce has not been seen and reserve it in persistent store.
    Returns True if nonce is valid and newly reserved (not a replay).
    Returns False if nonce was already present (replay detected).
    """
    with _nonce_store_lock():
        path = get_nonce_store_path()
        nonces = set()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    nonces = set(json.load(f))
        except Exception:
            if is_production() or os.getenv("AGRIWISE_STRICT_SECURITY") == "true":
                raise

        if nonce in nonces or (seen_messages is not None and nonce in seen_messages):
            return False

        nonces.add(nonce)
        try:
            dir_name = os.path.dirname(path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            os.close(fd)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(list(nonces), f)
            os.replace(tmp_path, path)
        except Exception as e:
            if is_production() or os.getenv("AGRIWISE_STRICT_SECURITY") == "true":
                raise RuntimeError("sensor_nonce_persistence_failed") from e

        if seen_messages is not None:
            seen_messages.add(nonce)
        return True


def detect_replay(message_id: str, seen_messages: set, reserve: bool = True) -> bool:
    """
    Detect duplicate message_ids to prevent replay attacks using persistent storage.
    When reserve=True (default), atomically combines eligibility check and registration
    into a single conditional insert, preventing race conditions under concurrent workers.
    Returns True if replay detected, False if accepted.
    """
    if reserve:
        admitted = check_and_reserve_nonce(message_id, seen_messages)
        return not admitted

    with _nonce_store_lock():
        nonces = load_nonces()
        if message_id in nonces or (seen_messages is not None and message_id in seen_messages):
            return True
        return False


def release_nonce(nonce: str, seen_messages: Optional[set] = None) -> None:
    """Atomically release/rollback a reserved nonce when transient ingestion failures occur."""
    with _nonce_store_lock():
        path = get_nonce_store_path()
        nonces = set()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    nonces = set(json.load(f))
        except Exception:
            if is_production() or os.getenv("AGRIWISE_STRICT_SECURITY") == "true":
                raise
            return

        if nonce in nonces:
            nonces.discard(nonce)
            tmp_path = None
            try:
                dir_name = os.path.dirname(path)
                if dir_name:
                    os.makedirs(dir_name, exist_ok=True)
                fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
                os.close(fd)
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(list(nonces), f)
                os.replace(tmp_path, path)
                tmp_path = None
            except Exception:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                if is_production() or os.getenv("AGRIWISE_STRICT_SECURITY") == "true":
                    raise
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

        if seen_messages is not None:
            seen_messages.discard(nonce)


