"""
Perception source adapter.

Extracts evidence from photo observations, drone RGB, and IP camera bundles.

Rules:
- Photo symptom observations are diagnostic only
- Drone RGB observations are local scope
- IP camera observations are diagnostic only
- None may claim plot-wide crop state
"""

from __future__ import annotations

from typing import Any, List

from layer1_fusion.schemas import EvidenceItem, Layer1InputBundle, SourceEnvelope


class PerceptionAdapter:
    source_family = "perception"

    def can_read(self, package: Any) -> bool:
        return package is not None

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if package is None:
            return items

        plot_id = context.plot_id

        # Extract observations from perception bundle
        observations = []
        if isinstance(package, dict):
            observations = package.get("observations", [])
        elif isinstance(package, list):
            observations = package
        else:
            observations = getattr(package, "observations", [])

        for i, obs in enumerate(observations):
            obs_dict = obs if isinstance(obs, dict) else {}
            variable = obs_dict.get("variable", "photo_observation")
            value = obs_dict.get("value", obs_dict.get("description", ""))
            source_type = obs_dict.get("source_type", "photo")
            confidence = obs_dict.get("confidence", 0.50)

            items.append(EvidenceItem(
                evidence_id=f"perception_{source_type}_{i}",
                plot_id=plot_id,
                variable=variable,
                value=value,
                unit=None,
                source_family="perception",
                source_id=f"perception_{source_type}",
                observation_type="diagnostic",
                spatial_scope="point",
                observed_at=None,
                confidence=min(0.60, confidence),
                reliability=confidence,
                freshness_score=0.0,
                provenance_ref=f"perception_{plot_id}_{i}",
                diagnostic_only=True,
                state_update_allowed=False,
            ))

        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="perception_missing", source_family="perception",
                source_name="Perception", package_id="", package_version="",
                source_status="missing",
            )
        return SourceEnvelope(
            source_id="perception",
            source_family="perception",
            source_name="Perception Bundle",
            package_id="perception",
            package_version="perception_v1",
            spatial_scope="point",
            temporal_scope="instant",
            trust_score=0.50,
            source_status="ok",
        )
