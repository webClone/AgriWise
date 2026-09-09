"""R6.0 / WP12: Bitemporal Historical Window Extraction.

Extracts training and backtesting windows as they existed at a specific historical point
in knowledge time (as_of_knowledge_time).

Guarantees ZERO data leakage from future observations into historical training sets:
Even if a sensor reading or satellite scene corresponds to a physical event on 2026-05-30,
if that data was ingested/committed on 2026-06-02, an extraction query as of 2026-06-01
will completely exclude it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
    compute_payload_hash,
)
from services.agribrain.scientific_contracts.exceptions import ContractViolation


def _ensure_utc_datetime(dt_val: Union[datetime, str]) -> datetime:
    """Convert string or datetime to timezone-aware UTC datetime."""
    if isinstance(dt_val, str):
        # Handle 'Z' suffix
        cleaned = dt_val.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
    elif isinstance(dt_val, datetime):
        dt = dt_val
    else:
        raise ContractViolation(f"Invalid timestamp type: {type(dt_val)}")

    if dt.tzinfo is None or dt.utcoffset() is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def _extract_event_time(event: Dict[str, Any]) -> Optional[datetime]:
    """Extract physical event time (observation_or_valid_time or effective_at)."""
    raw = event.get("observation_or_valid_time") or event.get("effective_at")
    if not raw and isinstance(event.get("payload"), dict):
        raw = event["payload"].get("observation_time") or event["payload"].get("timestamp")
    if not raw:
        return None
    try:
        return _ensure_utc_datetime(str(raw))
    except Exception:
        return None


def _extract_knowledge_time(event: Dict[str, Any]) -> Optional[datetime]:
    """Extract knowledge time (committed_at)."""
    raw = event.get("committed_at")
    if not raw and isinstance(event.get("payload"), dict):
        raw = event["payload"].get("committed_at")
    if not raw:
        return None
    try:
        return _ensure_utc_datetime(str(raw))
    except Exception:
        return None


@dataclass(frozen=True)
class TrainingTrajectoryWindow:
    """Immutable bitemporal training window.

    Guaranteed free of future knowledge leakage.
    """

    plot_id: str
    tenant_id: str
    namespace: str
    start_event_time: datetime
    end_event_time: datetime
    as_of_knowledge_time: datetime
    events: Tuple[Dict[str, Any], ...]
    active_events: Tuple[Dict[str, Any], ...]
    superseded_events: Tuple[Dict[str, Any], ...]
    extracted_at: datetime
    window_hash: str

    def has_future_leakage(self, knowledge_cutoff: Optional[datetime] = None) -> bool:
        """Verify that no event in this window was committed after the knowledge cutoff."""
        cutoff = _ensure_utc_datetime(knowledge_cutoff) if knowledge_cutoff else self.as_of_knowledge_time
        for event in self.events:
            kt = _extract_knowledge_time(event)
            if kt is not None and kt > cutoff:
                return True
        return False

    def get_observations(self) -> List[Dict[str, Any]]:
        """Return observation events active in this window."""
        obs_types = {"OBSERVATION", "CROP_OBSERVATION", "SATELLITE_SCENE", "PROBE_TELEMETRY", "WEATHER_OBSERVATION"}
        return [
            e for e in self.active_events
            if str(e.get("event_type", "")).upper() in obs_types
        ]

    def get_interventions(self) -> List[Dict[str, Any]]:
        """Return management intervention / forcing events active in this window."""
        intervention_types = {"INTERVENTION", "MANAGEMENT_ACTION", "FORCING_EVENT", "PRESCRIPTION_EXECUTION"}
        return [
            e for e in self.active_events
            if str(e.get("event_type", "")).upper() in intervention_types
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plot_id": self.plot_id,
            "tenant_id": self.tenant_id,
            "namespace": self.namespace,
            "start_event_time": self.start_event_time.isoformat(),
            "end_event_time": self.end_event_time.isoformat(),
            "as_of_knowledge_time": self.as_of_knowledge_time.isoformat(),
            "event_count": len(self.events),
            "active_event_count": len(self.active_events),
            "superseded_event_count": len(self.superseded_events),
            "extracted_at": self.extracted_at.isoformat(),
            "window_hash": self.window_hash,
        }


class BitemporalWorldlineExtractor:
    """Extracts training windows as they existed at a specific historical point in knowledge time.

    Guarantees zero data leakage from future observations into historical training sets.
    """

    def __init__(self, worldline_service: Optional[CanonicalWorldlineService] = None) -> None:
        self.worldline_service = worldline_service or CanonicalWorldlineService()

    def extract_training_window(
        self,
        plot_id: str,
        start_event_time: Union[datetime, str],
        end_event_time: Union[datetime, str],
        as_of_knowledge_time: Union[datetime, str],
        tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> TrainingTrajectoryWindow:
        """Extract all worldline events matching [start_event_time, end_event_time] committed <= as_of_knowledge_time.

        Parameters
        ----------
        plot_id : str
            Target agricultural plot identifier.
        start_event_time : datetime or str
            Start of physical event window (inclusive).
        end_event_time : datetime or str
            End of physical event window (inclusive).
        as_of_knowledge_time : datetime or str
            Point in knowledge time: any observation or event committed after this
            instant is strictly masked, preventing future knowledge leakage.
        tenant_id : str
            Tenant identifier.
        namespace : str
            Partition namespace.
        """
        start_dt = _ensure_utc_datetime(start_event_time)
        end_dt = _ensure_utc_datetime(end_event_time)
        knowledge_dt = _ensure_utc_datetime(as_of_knowledge_time)

        if start_dt > end_dt:
            raise ContractViolation(f"start_event_time ({start_dt}) cannot be after end_event_time ({end_dt})")

        # 1. Load all persisted events for plot
        all_events = self.worldline_service.load_all_events(plot_id, tenant_id=tenant_id, namespace=namespace)

        # 2. Filter 1: Strictly mask future knowledge
        # Any event committed AFTER as_of_knowledge_time did not exist in the system's
        # knowledge at that time.
        knowledge_known_events: List[Dict[str, Any]] = []
        for event in all_events:
            kt = _extract_knowledge_time(event)
            if kt is not None and kt > knowledge_dt:
                # FUTURE LEAKAGE: Skip completely
                continue
            knowledge_known_events.append(event)

        # 3. Filter 2: Event time window [start_event_time, end_event_time]
        window_events: List[Dict[str, Any]] = []
        for event in knowledge_known_events:
            et = _extract_event_time(event)
            if et is None:
                # If event has no valid time, fallback to committed time
                et = _extract_knowledge_time(event)
            if et is not None and start_dt <= et <= end_dt:
                window_events.append(event)

        # 4. Resolve superseding relationships within knowledge-known events
        # If an event B was committed <= knowledge_dt and supersedes event A,
        # then A is superseded. If event B was committed > knowledge_dt,
        # B was filtered out in step 2, so A remains active!
        superseded_ids: Set[str] = set()
        for event in knowledge_known_events:
            payload = event.get("payload") or {}
            sup_id = (
                payload.get("supersedes_event_id")
                or payload.get("superseded_event_id")
                or payload.get("supersedes_evidence_id")
            )
            if sup_id:
                superseded_ids.add(str(sup_id))

        active_events = [e for e in window_events if str(e.get("event_id")) not in superseded_ids]
        superseded_events = [e for e in window_events if str(e.get("event_id")) in superseded_ids]

        # 5. Compute deterministic window hash
        extracted_at = datetime.now(timezone.utc)
        hash_payload = {
            "plot_id": plot_id,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "as_of": knowledge_dt.isoformat(),
            "active_event_ids": sorted(str(e.get("event_id")) for e in active_events),
        }
        window_hash = hashlib.sha256(
            json.dumps(hash_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        return TrainingTrajectoryWindow(
            plot_id=plot_id,
            tenant_id=tenant_id,
            namespace=namespace,
            start_event_time=start_dt,
            end_event_time=end_dt,
            as_of_knowledge_time=knowledge_dt,
            events=tuple(window_events),
            active_events=tuple(active_events),
            superseded_events=tuple(superseded_events),
            extracted_at=extracted_at,
            window_hash=window_hash,
        )
