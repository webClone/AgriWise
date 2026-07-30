"""
User event source adapter.

Extracts management events: irrigation, fertilizer, spray, planting, harvest.

Rules:
- Events are operational context
- Events do NOT create crop diagnosis
- Irrigation events are process forcing context
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, List

from layer1_fusion.schemas import EvidenceItem, Layer1InputBundle, SourceEnvelope


class UserEventsAdapter:
    source_family = "user_event"

    def can_read(self, package: Any) -> bool:
        return package is not None and (
            isinstance(package, list) and len(package) > 0
        )

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if not package:
            return items

        plot_id = context.plot_id
        events = package if isinstance(package, list) else [package]

        for i, event in enumerate(events):
            if isinstance(event, dict):
                payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
                event_type = (
                    payload.get("type") or
                    event.get("type") or
                    event.get("event_type") or
                    event.get("source_type") or
                    "unknown"
                )
                timestamp = event.get("timestamp", event.get("date", None))
                value = payload.get("value", event.get("value", event.get("amount", payload or event)))
                unit = payload.get("unit", event.get("unit"))
                location_scope = event.get("location_scope", "plot")
                id_payload = {
                    "plot_id": plot_id,
                    "source_type": event.get("source_type"),
                    "timestamp": timestamp,
                    "location_scope": location_scope,
                    "payload": payload or event,
                }
            else:
                # Support dataclass / object events
                payload = getattr(event, "payload", {}) or {}
                if not isinstance(payload, dict):
                    payload = {}
                event_type = (
                    payload.get("type") or
                    getattr(event, "type", None) or
                    getattr(event, "event_type", None) or
                    getattr(event, "source_type", None) or
                    "unknown"
                )
                timestamp = getattr(event, "timestamp", getattr(event, "date", None))
                value = payload.get("value", getattr(event, "value", getattr(event, "event_value", None)))
                unit = payload.get("unit", getattr(event, "unit", None))
                location_scope = getattr(event, "location_scope", "plot")
                id_payload = {
                    "plot_id": plot_id,
                    "source_type": getattr(event, "source_type", None),
                    "timestamp": timestamp,
                    "location_scope": location_scope,
                    "payload": payload or str(event),
                }

            payload_hash = hashlib.sha256(
                json.dumps(id_payload, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()[:16]
            evidence_id = f"user_event_{event_type}_{payload_hash}"

            items.append(EvidenceItem(
                evidence_id=evidence_id,
                plot_id=plot_id,
                variable=f"user_{event_type}",
                value=value,
                unit=unit,
                source_family="user_event",
                source_id="user",
                observation_type="event",
                spatial_scope=location_scope or "plot",
                observed_at=timestamp,
                confidence=0.90,
                reliability=0.95,
                freshness_score=0.0,
                provenance_ref=evidence_id,
            ))

        from layer1_fusion.truth_bridge import normalize_evidence_truth
        for item in items:
            normalize_evidence_truth(item, source_context=package)
        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        events = package if isinstance(package, list) else []
        if not events:
            return SourceEnvelope(
                source_id="user_events_missing", source_family="user_event",
                source_name="User Events", package_id="", package_version="",
                source_status="missing",
            )
        return SourceEnvelope(
            source_id="user_events",
            source_family="user_event",
            source_name="User Management Events",
            package_id="user_events",
            package_version="v1",
            spatial_scope="plot",
            temporal_scope="instant",
            trust_score=0.90,
            source_status="ok",
            diagnostics={"event_count": len(events)},
        )
