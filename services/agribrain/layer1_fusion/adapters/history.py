"""
History source adapter.

Carries forward historical Layer 1 context packages as evidence
with explicit stale flags and decayed confidence.

Rules:
- All historical evidence gets stale flag
- Confidence is decayed based on age
- Observation_type = "state_estimate"
"""

from __future__ import annotations

from typing import Any, List

from layer1_fusion.schemas import EvidenceItem, Layer1InputBundle, SourceEnvelope


class HistoryAdapter:
    source_family = "history"

    def can_read(self, package: Any) -> bool:
        return package is not None

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if package is None:
            return items

        plot_id = context.plot_id

        # If the previous Layer1ContextPackage has fused features, carry them forward
        fused = getattr(package, "fused_features", None)
        if fused is None:
            return items

        prev_run_id = getattr(package, "run_id", "unknown_prev")

        for group_name in [
            "water_context", "vegetation_context", "phenology_context",
            "stress_evidence_context", "soil_site_context",
            "operational_context", "data_quality_context",
        ]:
            group = getattr(fused, group_name, [])
            for i, ff in enumerate(group):
                items.append(EvidenceItem(
                    evidence_id=f"hist_{prev_run_id}_{group_name}_{i}",
                    plot_id=plot_id,
                    variable=getattr(ff, "name", f"{group_name}_{i}"),
                    value=getattr(ff, "value", None),
                    unit=getattr(ff, "unit", None),
                    source_family="history",
                    source_id=prev_run_id,
                    observation_type="state_estimate",
                    spatial_scope=getattr(ff, "spatial_scope", "plot"),
                    scope_id=getattr(ff, "scope_id", None),
                    confidence=max(0.0, getattr(ff, "confidence", 0.5) * 0.7),
                    reliability=max(0.0, getattr(ff, "confidence", 0.5) * 0.6),
                    freshness_score=0.1,  # always stale
                    provenance_ref=f"hist_{prev_run_id}",
                    flags=["HISTORICAL", "STALE", "CARRY_FORWARD"],
                ))

        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="history_missing", source_family="history",
                source_name="Historical Context", package_id="", package_version="",
                source_status="missing",
            )
        return SourceEnvelope(
            source_id=f"hist_{getattr(package, 'run_id', 'unknown')}",
            source_family="history",
            source_name="Historical Layer 1 Context",
            package_id=f"hist_{getattr(package, 'run_id', '')}",
            package_version="v1",
            spatial_scope="plot",
            temporal_scope="daily",
            trust_score=0.30,
            source_status="stale",
        )
