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

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set


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


def extract_irrigation_receipt(envelope: Mapping[str, Any]) -> Any:
    """Shared B2B-08 extraction used by both L3 filter and HTTP journal.

    An event's role is not an authority claim. A signed physical receipt
    may be presented with REPORTED or another untrusted label.
    """
    payload = envelope.get("payload")
    if not isinstance(payload, Mapping):
        payload = envelope
    if payload.get("event_type") != "irrigation":
        return None
    return payload.get("verified_receipt") or envelope.get("verified_receipt")


def extract_receipt_id(envelope: Mapping[str, Any]) -> Optional[str]:
    """Extract receipt_id string if present in verified L3 delivery evidence."""
    rcpt = extract_irrigation_receipt(envelope)
    if rcpt is None:
        return None
    grant = (
        rcpt.get("grant") or rcpt
        if isinstance(rcpt, Mapping)
        else getattr(rcpt, "grant", rcpt)
    )
    if hasattr(grant, "receipt_id") and isinstance(grant.receipt_id, str) and grant.receipt_id:
        return grant.receipt_id
    if isinstance(grant, Mapping):
        rid = grant.get("receipt_id")
        if isinstance(rid, str) and rid:
            return rid
    return None


@dataclass(frozen=True)
class PlannedPhysicalEvent:
    """Authoritative, deterministic item in a physical-event execution plan."""
    index: int
    event_id: str
    receipt_id: Optional[str]
    event_type: str
    is_irrigation: bool
    is_admissible: bool
    rejection_reason: Optional[str] = None
    envelope: Mapping[str, Any] = field(default_factory=dict)


def resolve_physical_event_plan(
    events: Optional[Iterable[Any]],
    *,
    day: Optional[str] = None,
    plot_id: Optional[str] = None,
    zone_id: Optional[str] = None,
    geometry_hash: Optional[str] = None,
    geometry_version: Optional[int] = None,
    tenant_id: Optional[str] = None,
    cutoff: Optional[datetime] = None,
    seen_event_ids: Optional[Set[str]] = None,
    seen_receipt_ids: Optional[Set[str]] = None,
) -> List[PlannedPhysicalEvent]:
    """Authoritative execution plan shared by hashing, admission, and journal.

    Enforces intra-batch distinctness of event_id and receipt_id while
    evaluating basic scope, geometry, timing, and cutoff bounds.
    """
    if events is None:
        return []
    seen_events = seen_event_ids if seen_event_ids is not None else set()
    seen_receipts = seen_receipt_ids if seen_receipt_ids is not None else set()
    planned: List[PlannedPhysicalEvent] = []

    for index, raw in enumerate(events):
        envelope = (
            raw if isinstance(raw, Mapping)
            else (raw.model_dump() if hasattr(raw, "model_dump") and callable(raw.model_dump)
                  else (asdict(raw) if is_dataclass(raw) and not isinstance(raw, type)
                        else getattr(raw, "__dict__", {})))
        )
        if not isinstance(envelope, Mapping):
            envelope = {}
        payload = envelope.get("payload")
        if not isinstance(payload, Mapping):
            if hasattr(payload, "model_dump") and callable(payload.model_dump):
                payload = payload.model_dump()
            elif is_dataclass(payload) and not isinstance(payload, type):
                payload = asdict(payload)
            elif hasattr(payload, "__dict__"):
                payload = getattr(payload, "__dict__")
            else:
                payload = envelope

        event_type = payload.get("event_type")
        event_type = event_type if isinstance(event_type, str) else ""

        event_id = (
            payload.get("event_id")
            or envelope.get("event_id")
            or envelope.get("content_hash")
            or envelope.get("packet_id")
        )
        event_id = str(event_id) if (event_id is not None and not isinstance(event_id, bool) and str(event_id)) else ""

        receipt_id = extract_receipt_id(envelope)
        is_irrigation = (event_type == "irrigation")

        expected_zone = str(payload.get("zone_id") or "plot")
        actual_plot = envelope.get("plot_id") or payload.get("plot_id")
        actual_geometry = envelope.get("geometry_hash") or payload.get("geometry_hash")
        occurred_at = (
            envelope.get("timestamp")
            or payload.get("occurred_at")
            or payload.get("timestamp")
        )
        event_time = _utc_timestamp(occurred_at)
        cutoff_utc = _utc_timestamp(cutoff) if cutoff is not None else None

        if receipt_id is not None:
            rcpt = extract_irrigation_receipt(envelope)
            grant = (
                rcpt.get("grant") or rcpt
                if isinstance(rcpt, Mapping)
                else getattr(rcpt, "grant", rcpt)
            )
            if not actual_plot:
                actual_plot = grant.get("plot_id") if isinstance(grant, Mapping) else getattr(grant, "plot_id", None)
            if not actual_geometry:
                actual_geometry = grant.get("geometry_hash") if isinstance(grant, Mapping) else getattr(grant, "geometry_hash", None)

        rejection_reason = None
        if not event_type:
            rejection_reason = "missing_event_type"
        elif not event_id:
            rejection_reason = "missing_event_identity"
        elif plot_id is not None and (actual_plot != plot_id or not plot_id):
            rejection_reason = "unbound_or_foreign_plot"
        elif geometry_hash and actual_geometry != geometry_hash:
            rejection_reason = "unbound_or_foreign_geometry"
        elif zone_id is not None and expected_zone != zone_id:
            rejection_reason = "event_outside_zone"
        elif day is not None and (event_time is None or event_time.date().isoformat() != day):
            rejection_reason = "unqualified_event_time"
        elif cutoff is not None and (cutoff_utc is None or event_time > cutoff_utc):
            rejection_reason = "future_or_unavailable_event"
        elif event_id in seen_events:
            rejection_reason = "duplicate_event_identity"
        elif receipt_id is not None and receipt_id in seen_receipts:
            rejection_reason = "duplicate_receipt_in_assessment"

        is_admissible = (rejection_reason is None)
        if is_admissible:
            seen_events.add(event_id)
            if receipt_id is not None:
                seen_receipts.add(receipt_id)

        planned.append(PlannedPhysicalEvent(
            index=index,
            event_id=event_id or f"unidentified-index-{index}",
            receipt_id=receipt_id,
            event_type=event_type,
            is_irrigation=is_irrigation,
            is_admissible=is_admissible,
            rejection_reason=rejection_reason,
            envelope=envelope,
        ))

    return planned


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

    plan = resolve_physical_event_plan(
        events,
        day=day,
        plot_id=plot_id,
        zone_id=zone_id,
        geometry_hash=geometry_hash,
        geometry_version=geometry_version,
        tenant_id=tenant_id,
        cutoff=cutoff,
        seen_event_ids=seen,
    )

    for item in plan:
        envelope = item.envelope
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            payload = envelope
        raw_role = payload.get("event_role") or payload.get("role")
        role = raw_role if isinstance(raw_role, str) and raw_role else "UNKNOWN"
        role = role.upper()
        source = str(envelope.get("source") or "")
        if raw_role is None and source == "user_event":
            role = "USER_REPORTED_EXPOSURE"

        decision = {
            "event_id": item.event_id,
            "event_type": item.event_type,
            "claimed_role": role,
            "status": "DEFERRED",
            "reason": "unqualified_management_evidence",
            "state_update_allowed": False,
            "physical_delivery_verified": False,
            "target_zone": str(payload.get("zone_id") or "plot"),
        }

        if not item.is_admissible:
            decision.update(status="REJECTED", reason=item.rejection_reason)
        elif item.event_type != "irrigation":
            decision.update(status="RETAINED", reason="non_water_management_event")
        else:
            receipt_data = extract_irrigation_receipt(envelope)
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
                magnitude = payload.get("amount_mm")
                if magnitude is None:
                    magnitude = payload.get("net_infiltrated_mm")
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

        records.append(decision)

    return records
