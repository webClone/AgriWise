"""
Mission History.

In-memory store of completed mission records for temporal comparison
and recency-based suppression.

Each MissionRecord stores both:
  - Raw structural summary (canopy, weeds, row breaks, trees)
  - Decision context (source run_id, QA version, mode, trigger reason)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .schemas import MissionType, FlightMode


@dataclass
class MissionRecord:
    """A completed mission snapshot for temporal comparison and audit."""

    # Identity
    mission_id: str
    plot_id: str
    timestamp: datetime

    # --- Raw Structural Summary ---
    canopy_cover: float = 0.0
    weed_pressure: float = 0.0
    row_break_count: int = 0
    tree_count: int = 0
    missing_tree_count: int = 0
    in_row_weed_fraction: float = 0.0
    inter_row_weed_fraction: float = 0.0
    canopy_uniformity_cv: float = 0.0
    row_count: int = 0

    # --- QA / Execution Summary ---
    qa_score: float = 1.0
    coverage_completeness: float = 1.0

    # --- Decision Context ---
    mission_type: MissionType = MissionType.FULL_PLOT_MAP
    flight_mode: FlightMode = FlightMode.MAPPING_MODE
    source_run_id: str = ""              # The plan_id or intent_id that created this
    planner_version: str = "v1.5"        # Tracks which planner logic was active
    qa_version: str = "v1.5"             # Tracks which QA logic was active
    trigger_reason: str = ""             # "user_command", "anomaly_vegetation_drop", "refly_partial", etc.
    originating_anomaly_id: str = ""     # report_id of the anomaly that triggered this (if any)


class MissionHistory:
    """In-memory store of completed missions, keyed by plot_id.
    
    Thread-safety is NOT provided — this is a single-process V1.5 store.
    Production would use a database with proper concurrency.
    """

    def __init__(self):
        self._store: Dict[str, List[MissionRecord]] = {}

    def record(self, mission: MissionRecord):
        """Store a completed mission record."""
        if mission.plot_id not in self._store:
            self._store[mission.plot_id] = []
        self._store[mission.plot_id].append(mission)
        # Keep sorted by timestamp
        self._store[mission.plot_id].sort(key=lambda m: m.timestamp)

    def get_previous(self, plot_id: str, before: Optional[datetime] = None) -> Optional[MissionRecord]:
        """Return the most recent mission for a plot (optionally before a timestamp)."""
        records = self._store.get(plot_id, [])
        if not records:
            return None
        if before is None:
            return records[-1]
        candidates = [r for r in records if r.timestamp < before]
        return candidates[-1] if candidates else None

    def get_all(self, plot_id: str) -> List[MissionRecord]:
        """Return all missions for a plot, ordered by timestamp."""
        return list(self._store.get(plot_id, []))

    def get_recent_anomaly_timestamps(self, plot_id: str) -> Dict[str, datetime]:
        """Build a recency map for anomaly suppression.
        
        Returns: {anomaly_key: last_timestamp} for all missions on this plot
        that were triggered by anomalies.
        """
        result: Dict[str, datetime] = {}
        for rec in self._store.get(plot_id, []):
            if rec.trigger_reason.startswith("anomaly_"):
                # Extract anomaly type from trigger reason
                anomaly_type = rec.trigger_reason.replace("anomaly_", "", 1)
                key = f"{plot_id}:{anomaly_type}:"
                result[key] = rec.timestamp
        return result

    def count(self, plot_id: str) -> int:
        return len(self._store.get(plot_id, []))

    def clear(self, plot_id: Optional[str] = None):
        """Clear history. If plot_id given, only clear that plot."""
        if plot_id:
            self._store.pop(plot_id, None)
        else:
            self._store.clear()
