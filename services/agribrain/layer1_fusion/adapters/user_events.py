"""
User event source adapter.

Extracts management events: irrigation, fertilizer, spray, planting, harvest.

Rules:
- Events are operational context
- Events do NOT create crop diagnosis
- Irrigation events are process forcing context
"""

from __future__ import annotations

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
                event_type = event.get("type", event.get("event_type", "unknown"))
                timestamp = event.get("timestamp", event.get("date", None))
                value = event.get("value", event.get("amount", event))
                unit = event.get("unit")
            else:
                # Support dataclass / object events
                event_type = getattr(event, "type", getattr(event, "event_type", "unknown"))
                timestamp = getattr(event, "timestamp", getattr(event, "date", None))
                value = getattr(event, "value", getattr(event, "event_value", None))
                unit = getattr(event, "unit", None)

            items.append(EvidenceItem(
                evidence_id=f"user_event_{event_type}_{i}",
                plot_id=plot_id,
                variable=f"user_{event_type}",
                value=value,
                unit=unit,
                source_family="user_event",
                source_id="user",
                observation_type="event",
                spatial_scope="plot",
                observed_at=None,
                confidence=0.90,
                reliability=0.95,
                freshness_score=0.0,
                provenance_ref=f"user_event_{plot_id}_{i}",
            ))

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
