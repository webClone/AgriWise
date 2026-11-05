"""Layer 0 C1/C2 pre-physical admission of management-event evidence.

This is a conservative *evidence router*, not an actuator or an L3 water
operator. It never asserts verified delivery from packet text alone and never
turns a declared amount into a net infiltrated water flux. The original
ObservationPackets stay attached to Layer0StatePackage for traceability.

Every state-bearing caller must keep these dispositions separate from
ProcessModel event forcing until a trusted, geometry/support-aware L3 receipt
and covariance contract is integrated (L0-02C3).
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Dict, Iterable, List, Optional, Set


def _utc_timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt.astimezone(timezone.utc)


def _finite_nonnegative(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and value >= 0.0
    )


def classify_management_event_evidence(
    events: Optional[Iterable[Dict[str, Any]]],
    *,
    day: str,
    plot_id: str,
    zone_id: str,
    geometry_hash: str = "",
    geometry_version: Optional[int] = None,
    tenant_id: str = "",
    cutoff: Optional[datetime] = None,
    seen_ids: Optional[Set[str]] = None,
    delivery_verifier: Optional[Any] = None,
    allow_historical_recompute: bool = False,
) -> List[Dict[str, Any]]:
    """Classify an event once per scoped run without granting physical force.

    Packet envelopes have the form {payload, packet_id, content_hash, source,
    plot_id, geometry_hash, timestamp}. Raw legacy event dictionaries remain
    representable but are unverified and generally unscoped.

    Statuses:
      REJECTED — malformed, foreign, incompatible or duplicated evidence
      DEFERRED — well-formed report/plan/claim awaiting physical qualification
      RETAINED — non-water management evidence or zero delivery declaration

    All results explicitly have state_update_allowed=False. A textual
    VERIFIED_DELIVERY role is an *unverified claim*, never a receipt.
    """
    if events is None:
        return []
    seen = seen_ids if seen_ids is not None else set()
    records: List[Dict[str, Any]] = []

    for index, raw in enumerate(events):
        envelope = raw if isinstance(raw, dict) else {}
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            payload = envelope
        event_type = payload.get("event_type")
        event_id = (
            payload.get("event_id")
            or envelope.get("event_id")
            or envelope.get("content_hash")
            or envelope.get("packet_id")
        )
        event_id = event_id if isinstance(event_id, str) and event_id else ""
        raw_role = payload.get("event_role") or payload.get("role")
        role = raw_role if isinstance(raw_role, str) and raw_role else "UNKNOWN"
        role = role.upper()
        source = str(envelope.get("source") or "")
        if raw_role is None and source == "user_event":
            # Only absent role on a user event implies reported evidence.
            # Explicit UNKNOWN never becomes an asserted report or delivery.
            role = "USER_REPORTED_EXPOSURE"

        decision = {
            "event_id": event_id or f"unidentified-index-{index}",
            "event_type": event_type if isinstance(event_type, str) else "",
            "claimed_role": role,
            "status": "DEFERRED",
            "reason": "unqualified_management_evidence",
            "state_update_allowed": False,
            "physical_delivery_verified": False,
            "target_zone": str(payload.get("zone_id") or "plot"),
        }

        expected_zone = decision["target_zone"]
        actual_plot = envelope.get("plot_id") or payload.get("plot_id")
        actual_geometry = envelope.get("geometry_hash") or payload.get("geometry_hash")
        occurred_at = (
            envelope.get("timestamp")
            or payload.get("occurred_at")
            or payload.get("timestamp")
        )
        event_time = _utc_timestamp(occurred_at)
        cutoff_utc = _utc_timestamp(cutoff) if cutoff is not None else None
        magnitude = payload.get("amount_mm")
        if magnitude is None:
            magnitude = payload.get("net_infiltrated_mm")

        if not isinstance(event_type, str) or not event_type:
            decision.update(status="REJECTED", reason="missing_event_type")
        elif not event_id:
            decision.update(status="REJECTED", reason="missing_event_identity")
        elif actual_plot != plot_id or not plot_id:
            decision.update(status="REJECTED", reason="unbound_or_foreign_plot")
        elif geometry_hash and actual_geometry != geometry_hash:
            decision.update(status="REJECTED", reason="unbound_or_foreign_geometry")
        elif expected_zone != zone_id:
            decision.update(status="REJECTED", reason="event_outside_zone")
        elif event_time is None or event_time.date().isoformat() != day:
            decision.update(status="REJECTED", reason="unqualified_event_time")
        elif cutoff is not None and (cutoff_utc is None or event_time > cutoff_utc):
            decision.update(status="REJECTED", reason="future_or_unavailable_event")
        elif event_id in seen:
            decision.update(status="REJECTED", reason="duplicate_event_identity")
        elif event_type != "irrigation":
            decision.update(status="RETAINED", reason="non_water_management_event")
        else:
            # Check for authentic L3 verified receipt
            receipt_data = payload.get("verified_receipt") or envelope.get("verified_receipt")
            if receipt_data is not None:
                if delivery_verifier is None:
                    decision.update(
                        status="DEFERRED",
                        reason="claimed_verification_requires_trusted_L3_receipt",
                    )
                else:
                    try:
                        admitted = delivery_verifier.verify_and_admit(
                            receipt_data,
                            expected_day=day,
                            expected_plot_id=plot_id,
                            expected_zone_id=zone_id,
                            expected_geometry_hash=geometry_hash,
                            expected_geometry_version=geometry_version,
                            expected_tenant_id=tenant_id,
                            cutoff=cutoff,
                            allow_historical_recompute=allow_historical_recompute,
                        )
                        decision.update(
                            status="ADMITTED",
                            reason="verified_l3_physical_delivery",
                            physical_delivery_verified=True,
                            state_update_allowed=True,
                            net_infiltrated_depth_mm=admitted.net_infiltrated_depth_mm,
                            depth_uncertainty_sigma_mm=admitted.depth_uncertainty_sigma_mm,
                            receipt_id=admitted.receipt_id,
                            replay_idempotency_key=admitted.replay_idempotency_key,
                            scientific_publication_authorized=False,
                            actuator_control_authorized=False,
                            admitted_token=admitted,
                        )
                    except Exception as exc:
                        decision.update(
                            status="REJECTED",
                            reason=str(exc),
                        )
            else:
                if not _finite_nonnegative(magnitude):
                    decision.update(status="REJECTED", reason="invalid_irrigation_amount")
                elif role in ("PLANNED_SCENARIO", "PLANNED", "RECOMMENDED"):
                    decision.update(status="DEFERRED", reason="planned_not_delivered")
                elif role in ("USER_REPORTED_EXPOSURE", "REPORTED"):
                    decision.update(status="DEFERRED", reason="reported_not_verified")
                elif role == "VERIFIED_DELIVERY":
                    decision.update(
                        status="DEFERRED",
                        reason="claimed_verification_requires_trusted_L3_receipt",
                    )
                else:
                    decision.update(status="DEFERRED", reason="unknown_delivery_role")

        # Track identity for accepted-scope evidence even when it is deferred:
        # duplicate reports should not silently masquerade as new delivery.
        if decision["status"] != "REJECTED" and event_id:
            seen.add(event_id)

        records.append(decision)

    return records
