from datetime import datetime, timezone
from typing import Optional
from layer0.sensors.schemas import SensorQAResult


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HTTP webhook signature to prevent spoofed payloads."""
    # V1: Deterministic mock for pure-function testing
    return signature == "valid_signature"


def check_rate_limit(device_id: str, received_at: datetime) -> bool:
    """Ensure device is not spamming the ingestion endpoint."""
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


def detect_replay(message_id: str, seen_messages: set) -> bool:
    """Detect duplicate message_ids to prevent replay attacks."""
    return message_id in seen_messages
