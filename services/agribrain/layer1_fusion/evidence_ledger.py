"""
Layer 1 Evidence Ledger.

The central queryable store for all evidence in a fusion run.
Supports queries by variable, source, scope, and time window.
Validates evidence integrity on insertion.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from datetime import datetime

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
        return max(dated, key=lambda e: e.observed_at)

    def within(
        self, start: Optional[datetime] = None, end: Optional[datetime] = None
    ) -> List[EvidenceItem]:
        """Return evidence within a time window (observed_at)."""
        result = []
        for e in self._items:
            if e.observed_at is None:
                continue
            if start and e.observed_at < start:
                continue
            if end and e.observed_at > end:
                continue
            result.append(e)
        return result

    def state_updatable(self) -> List[EvidenceItem]:
        """Return only evidence that is allowed to update state."""
        return [e for e in self._items if e.state_update_allowed and not e.diagnostic_only]

    def diagnostic_only_items(self) -> List[EvidenceItem]:
        """Return only diagnostic evidence."""
        return [e for e in self._items if e.diagnostic_only]
