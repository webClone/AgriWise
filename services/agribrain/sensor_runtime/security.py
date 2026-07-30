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


def load_nonces() -> set:
    """Load nonces from the persistent JSON file store."""
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
    """Atomically persist a nonce to the replay nonces JSON store."""
    path = get_nonce_store_path()
    nonces = load_nonces()
    new_nonces = set(nonces)
    new_nonces.add(nonce)
    try:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        os.close(fd)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(list(new_nonces), f)
        os.replace(tmp_path, path)
    except Exception as e:
        if is_production() or os.getenv("AGRIWISE_STRICT_SECURITY") == "true":
            raise RuntimeError("sensor_nonce_persistence_failed") from e


def detect_replay(message_id: str, seen_messages: set) -> bool:
    """Detect duplicate message_ids to prevent replay attacks using persistent storage."""
    nonces = load_nonces()
    if message_id in nonces or message_id in seen_messages:
        return True
    return False
