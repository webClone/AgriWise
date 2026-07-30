"""
Layer 1 Evidence Ledger.

The central queryable store for all evidence in a fusion run.
Supports queries by variable, source, scope, and time window.
Validates evidence integrity on insertion.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from common.time_utils import ensure_utc

from .schemas import EvidenceItem, SPATIAL_SCOPES, SOURCE_FAMILIES


class EvidenceLedger:
    """Append-only evidence store with query interface.

    All evidence must be added through add() which performs
    integrity checks before admission.
    """

    def __init__(self) -> None:
        self._items: List[EvidenceItem] = []
        self._ids: Set[str] = set()
        self._by_variable: Dict[str, List[EvidenceItem]] = {}
        self._by_source: Dict[str, List[EvidenceItem]] = {}
        self._by_scope: Dict[str, List[EvidenceItem]] = {}

    def add(self, item: EvidenceItem) -> List[str]:
        """Add evidence item. Returns list of integrity violations (empty = OK)."""
        violations = self._validate(item)
        if violations:
            return violations

        self._items.append(item)
        self._ids.add(item.evidence_id)

        self._by_variable.setdefault(item.variable, []).append(item)
        self._by_source.setdefault(item.source_family, []).append(item)
        self._by_scope.setdefault(item.spatial_scope, []).append(item)

        return []

    def add_batch(self, items: List[EvidenceItem]) -> Dict[str, List[str]]:
        """Add multiple items. Returns map of evidence_id → violations."""
        rejected: Dict[str, List[str]] = {}
        for item in items:
            violations = self.add(item)
            if violations:
                rejected[item.evidence_id] = violations
        return rejected

    def _validate(self, item: EvidenceItem) -> List[str]:
        violations: List[str] = []

        if not item.evidence_id:
            violations.append("evidence_id is empty")
        if item.evidence_id in self._ids:
            violations.append(f"duplicate evidence_id: {item.evidence_id}")
        if not item.plot_id:
            violations.append("plot_id is empty")
        if not item.variable:
            violations.append("variable is empty")
        if item.source_family not in SOURCE_FAMILIES:
            violations.append(f"invalid source_family: {item.source_family}")
        if item.spatial_scope not in SPATIAL_SCOPES:
            violations.append(f"invalid spatial_scope: {item.spatial_scope}")
        if not (0.0 <= item.confidence <= 1.0):
            violations.append(f"confidence {item.confidence} out of [0, 1]")
        if not (0.0 <= item.reliability <= 1.0):
            violations.append(f"reliability {item.reliability} out of [0, 1]")

        return violations

    # ── Query interface ──────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._items)

    @property
    def all_items(self) -> List[EvidenceItem]:
        return list(self._items)

    def by_variable(self, variable: str) -> List[EvidenceItem]:
        return list(self._by_variable.get(variable, []))

    def by_source(self, source_family: str) -> List[EvidenceItem]:
        return list(self._by_source.get(source_family, []))

    def by_scope(self, scope: str) -> List[EvidenceItem]:
        return list(self._by_scope.get(scope, []))

    def variables(self) -> List[str]:
        return list(self._by_variable.keys())

    def sources(self) -> List[str]:
        return list(self._by_source.keys())

    def latest(self, variable: str) -> Optional[EvidenceItem]:
        """Return the most recent evidence for a variable (by observed_at)."""
        items = self._by_variable.get(variable, [])
        if not items:
            return None
        dated = [e for e in items if e.observed_at is not None]
        if not dated:
            return items[-1]
        return max(dated, key=lambda e: ensure_utc(e.observed_at))


    def within(
        self, start: Optional[datetime] = None, end: Optional[datetime] = None
    ) -> List[EvidenceItem]:
        """Return evidence within a time window (observed_at)."""
        result = []
        start_utc = ensure_utc(start)
        end_utc = ensure_utc(end)
        for e in self._items:
            if e.observed_at is None:
                continue
            obs_utc = ensure_utc(e.observed_at)
            if start_utc and obs_utc < start_utc:
                continue
            if end_utc and obs_utc > end_utc:
                continue
            result.append(e)
        return result

    def state_updatable(self) -> List[EvidenceItem]:
        """Return only evidence that is allowed to update state."""
        return [e for e in self._items if e.state_update_allowed and not e.diagnostic_only]

    def diagnostic_only_items(self) -> List[EvidenceItem]:
        """Return only diagnostic evidence."""
        return [e for e in self._items if e.diagnostic_only]

    # ── Agronomic domain queries ─────────────────────────────────────────
    #
    # These methods provide crop-science-oriented access to evidence,
    # organized by the agronomic processes they inform.
    #
    # Variable sets imported from fusion_rules.py (single source of truth)
    # to prevent drift between query filters and fusion groupings.

    from .fusion_rules import (
        _WATER_VARIABLES as _WATER_VARS,
        _VEGETATION_VARIABLES as _VEG_VARS,
        _STRESS_VARIABLES as _STRESS_VARS,
    )

    def water_balance_evidence(self) -> List[EvidenceItem]:
        """All evidence relevant to the field water balance.

        Includes: soil moisture (VWC), SAR wetness proxy, precipitation,
        irrigation events, ET estimates, WHC, field capacity, wilting point.
        Used by Layer 2 for irrigation scheduling and drought detection.
        """
        return [e for e in self._items if any(w in e.variable for w in self._WATER_VARS)]

    def vegetation_vigor_evidence(self) -> List[EvidenceItem]:
        """All evidence relevant to crop canopy vigor and health.

        Includes: spectral vegetation indices (NDVI, NDMI, NDRE, EVI),
        LAI, canopy cover, chlorophyll proxies, SIF, bare soil fraction.
        Used by Layer 2 for growth monitoring and yield estimation.
        """
        return [e for e in self._items if any(v in e.variable for v in self._VEG_VARS)]

    def stress_indicators(self) -> List[EvidenceItem]:
        """All evidence that could indicate crop stress.

        Includes: stress indices, frost/drought/flood events, VPD anomalies,
        thermal stress, disease-weather risk indicators.
        Used by Layer 2 for early warning and stress classification.
        """
        return [e for e in self._items if any(s in e.variable for s in self._STRESS_VARS)]

    def by_spatial_resolution(self) -> Dict[str, List[EvidenceItem]]:
        """Group evidence by spatial scope for multi-scale analysis.

        Returns dict: scope -> [evidence items].
        Typical keys: 'plot', 'zone', 'point', 'edge', 'raster'.
        Used for understanding spatial coverage and scale mismatch.
        """
        result: Dict[str, List[EvidenceItem]] = {}
        for e in self._items:
            result.setdefault(e.spatial_scope, []).append(e)
        return result

    def by_freshness_tier(self) -> Dict[str, List[EvidenceItem]]:
        """Group evidence by freshness tier for temporal quality assessment.

        Returns dict with keys: 'fresh' (>0.7), 'aging' (0.3-0.7), 'stale' (<0.3).
        """
        tiers: Dict[str, List[EvidenceItem]] = {"fresh": [], "aging": [], "stale": []}
        for e in self._items:
            if e.freshness_score >= 0.7:
                tiers["fresh"].append(e)
            elif e.freshness_score >= 0.3:
                tiers["aging"].append(e)
            else:
                tiers["stale"].append(e)
        return tiers

