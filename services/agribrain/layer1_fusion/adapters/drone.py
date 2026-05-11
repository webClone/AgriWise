"""
Drone structural source adapter.

Extracts high-fidelity structural metrics from DroneRGBOutput into the
Layer 1 evidence ledger. This adapter processes the output of the
DroneRGBEngine (layer0.perception.drone_rgb) which produces structural
analysis of crop fields from drone orthomosaics.

Metrics ingested:
- canopy_cover_fraction → vegetation_context
- bare_soil_fraction → soil_site_context
- weed_pressure_index → stress_evidence_context
- row_azimuth_deg → operational_context
- row_spacing_cm → operational_context
- row_count → operational_context
- row_continuity (mean) → operational_context
- tree_count (orchard mode) → operational_context
- missing_tree_count (orchard mode) → operational_context
- canopy_uniformity_cv (orchard mode) → stress_evidence_context
- in_row_weed_fraction → stress_evidence_context
- inter_row_weed_fraction → stress_evidence_context

Rules:
- Drone structural data is derived_feature (not raw measurement)
- Spatial scope is always "plot" (field-level aggregates)
- QA score from DroneRGBOutput gates confidence
- Mission-rejected outputs are skipped entirely
- No state updates from drone structural alone (diagnostic_only=False,
  but state_update_allowed is modulated by qa_score)
"""

from __future__ import annotations

from typing import Any, List

from layer1_fusion.schemas import EvidenceItem, Layer1InputBundle, SourceEnvelope


class DroneStructuralAdapter:
    source_family = "drone_structural"

    def can_read(self, package: Any) -> bool:
        """Read if package is a DroneRGBOutput with valid data."""
        if package is None:
            return False
        # Accept both DroneRGBOutput dataclass instances and plain dicts
        is_valid = getattr(package, "is_valid", None)
        if is_valid is not None:
            return bool(is_valid)
        if isinstance(package, dict):
            return package.get("is_valid", True)
        return False

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if package is None:
            return items

        plot_id = context.plot_id

        # Normalize access — support both dataclass attrs and dict keys
        def _get(key: str, default=None):
            if isinstance(package, dict):
                return package.get(key, default)
            return getattr(package, key, default)

        mission_id = _get("mission_id", "unknown")
        qa_score = float(_get("qa_score", 0.8))
        capture_ts = _get("capture_timestamp", None)

        # Base confidence is bounded by the mission QA score
        base_confidence = min(0.80, qa_score * 0.85)
        base_reliability = qa_score

        # Allow state updates only for high-quality missions
        state_update_ok = qa_score >= 0.6

        idx = 0  # evidence counter

        def _add(variable: str, value: Any, unit: str,
                 obs_type: str = "derived_feature",
                 spatial_scope: str = "plot",
                 diagnostic_only: bool = False,
                 flags: list = None):
            nonlocal idx
            items.append(EvidenceItem(
                evidence_id=f"drone_{mission_id}_{variable}_{idx}",
                plot_id=plot_id,
                variable=variable,
                value=value,
                unit=unit,
                source_family="drone_structural",
                source_id=f"drone_{mission_id}",
                observation_type=obs_type,
                spatial_scope=spatial_scope,
                observed_at=capture_ts,
                confidence=base_confidence,
                reliability=base_reliability,
                freshness_score=0.0,  # set by freshness engine later
                provenance_ref=f"drone_{mission_id}_{plot_id}",
                diagnostic_only=diagnostic_only,
                state_update_allowed=state_update_ok,
                flags=flags or [],
            ))
            idx += 1

        # ---- Core structural metrics ----

        canopy = _get("canopy_cover_fraction")
        if canopy is not None:
            _add("canopy_cover_fraction", float(canopy), "fraction")

        bare_soil = _get("bare_soil_fraction")
        if bare_soil is not None:
            _add("bare_soil_fraction", float(bare_soil), "fraction")

        weed = _get("weed_pressure_index")
        if weed is not None:
            _add("weed_pressure_index", float(weed), "index")

        # ---- Row geometry metrics ----

        azimuth = _get("row_azimuth_deg")
        if azimuth is not None:
            _add("row_azimuth_deg", float(azimuth), "deg")

        spacing = _get("row_spacing_cm")
        if spacing is not None:
            _add("row_spacing_cm", float(spacing), "cm")

        row_count = _get("row_count")
        if row_count is not None and int(row_count) > 0:
            _add("row_count", int(row_count), "count")

        # ---- Row continuity (aggregate to mean) ----
        continuity_scores = _get("row_continuity_scores", [])
        if continuity_scores and len(continuity_scores) > 0:
            mean_cont = sum(continuity_scores) / len(continuity_scores)
            _add("row_continuity_mean", round(mean_cont, 4), "score")

        # ---- Row breaks (count only — individual breaks are diagnostic) ----
        row_breaks = _get("row_breaks", [])
        if row_breaks:
            _add("row_break_count", len(row_breaks), "count",
                 diagnostic_only=True)

        # ---- Weed separation metrics ----
        in_row_weed = _get("in_row_weed_fraction")
        if in_row_weed is not None and float(in_row_weed) > 0:
            _add("in_row_weed_fraction", float(in_row_weed), "fraction")

        inter_row_weed = _get("inter_row_weed_fraction")
        if inter_row_weed is not None and float(inter_row_weed) > 0:
            _add("inter_row_weed_fraction", float(inter_row_weed), "fraction")

        # ---- Orchard mode metrics ----
        tree_count = _get("tree_count")
        if tree_count is not None and int(tree_count) > 0:
            _add("tree_count", int(tree_count), "count")

            missing_trees = _get("missing_tree_count", 0)
            if int(missing_trees) > 0:
                _add("missing_tree_count", int(missing_trees), "count")

            uniformity = _get("canopy_uniformity_cv")
            if uniformity is not None:
                _add("canopy_uniformity_cv", float(uniformity), "ratio")

        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="drone_structural_missing",
                source_family="drone_structural",
                source_name="Drone Structural Analysis",
                package_id="",
                package_version="",
                source_status="missing",
            )

        # Normalize access
        def _get(key, default=None):
            if isinstance(package, dict):
                return package.get(key, default)
            return getattr(package, key, default)

        mission_id = _get("mission_id", "unknown")
        qa_score = float(_get("qa_score", 0.8))
        is_valid = _get("is_valid", True)

        if not is_valid:
            return SourceEnvelope(
                source_id=f"drone_{mission_id}",
                source_family="drone_structural",
                source_name="Drone Structural Analysis",
                package_id=mission_id,
                package_version="drone_rgb_v1.5",
                trust_score=0.0,
                source_status="unusable",
            )

        return SourceEnvelope(
            source_id=f"drone_{mission_id}",
            source_family="drone_structural",
            source_name="Drone Structural Analysis",
            package_id=mission_id,
            package_version="drone_rgb_v1.5",
            trust_score=qa_score,
            spatial_scope="plot",
            temporal_scope="instant",
            source_status="ok" if qa_score >= 0.5 else "degraded",
        )
