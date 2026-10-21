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

try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real


def _qualify_drone_quality(package: Any) -> tuple[float, float, float, bool]:
    """Qualify native QA score and reliability weight using finite_real.

    Returns:
        (qa_score, rel_weight, effective_quality, is_valid)
    """
    if package is None:
        return (0.0, 0.0, 0.0, False)

    def _get(key: str, default=None):
        if isinstance(package, dict):
            return package.get(key, default)
        return getattr(package, key, default)

    raw_valid = _get("is_valid", True)
    is_valid = bool(raw_valid) if raw_valid is not None else False

    # qa_score qualification
    raw_qa = _get("qa_score")
    if raw_qa is None:
        if isinstance(package, dict) and "qa_score" not in package:
            qa_score = 0.8
        elif not isinstance(package, dict) and not hasattr(package, "qa_score"):
            qa_score = 1.0
        else:
            qa_score = 0.0
    else:
        fin_qa = finite_real(raw_qa)
        if fin_qa is None or fin_qa < 0.0:
            qa_score = 0.0
        else:
            qa_score = max(0.0, min(1.0, fin_qa))

    # reliability_weight qualification
    raw_rel = _get("reliability_weight")
    if raw_rel is None:
        if isinstance(package, dict) and "reliability_weight" not in package:
            rel_weight = 1.0
        elif not isinstance(package, dict) and not hasattr(package, "reliability_weight"):
            rel_weight = 1.0
        else:
            rel_weight = 0.0
    else:
        fin_rel = finite_real(raw_rel)
        if fin_rel is None or fin_rel < 0.0:
            rel_weight = 0.0
        else:
            rel_weight = max(0.0, min(1.0, fin_rel))

    if not is_valid:
        effective_quality = 0.0
    elif qa_score == 0.0 or rel_weight == 0.0:
        effective_quality = 0.0
    else:
        effective_quality = min(qa_score, rel_weight)

    return (qa_score, rel_weight, effective_quality, is_valid)


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

        qa_score, rel_weight, effective_quality, is_valid = _qualify_drone_quality(package)
        mission_id = _get("mission_id", "unknown")
        capture_ts = _get("capture_timestamp", None)

        if effective_quality == 0.0:
            base_confidence = 0.0
            base_reliability = 0.0
            state_update_ok = False
            diagnostic_only = True
        else:
            base_confidence = min(0.80, effective_quality * 0.85)
            base_reliability = effective_quality
            state_update_ok = effective_quality >= 0.6
            diagnostic_only = False

        idx = 0  # evidence counter

        def _add(variable: str, value: Any, unit: str,
                 obs_type: str = "derived_feature",
                 spatial_scope: str = "plot",
                 item_diagnostic_only: bool = False,
                 flags: list = None):
            nonlocal idx
            is_diag = diagnostic_only or item_diagnostic_only or (effective_quality == 0.0)
            item_flags = list(flags or [])
            if is_diag and "DIAGNOSTIC_ONLY" not in item_flags:
                item_flags.append("DIAGNOSTIC_ONLY")
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
                confidence=base_confidence if not is_diag else 0.0,
                reliability=base_reliability if not is_diag else 0.0,
                freshness_score=0.0,  # set by freshness engine later
                provenance_ref=f"drone_{mission_id}_{plot_id}",
                diagnostic_only=is_diag,
                state_update_allowed=state_update_ok and not is_diag,
                flags=item_flags,
            ))
            idx += 1

        # ---- Core structural metrics ----

        canopy = finite_real(_get("canopy_cover_fraction"))
        if canopy is not None:
            _add("canopy_cover_fraction", canopy, "fraction")

        bare_soil = finite_real(_get("bare_soil_fraction"))
        if bare_soil is not None:
            _add("bare_soil_fraction", bare_soil, "fraction")

        weed = finite_real(_get("weed_pressure_index"))
        if weed is not None:
            _add("weed_pressure_index", weed, "index")

        # ---- Row geometry metrics ----

        azimuth = finite_real(_get("row_azimuth_deg"))
        if azimuth is not None:
            _add("row_azimuth_deg", azimuth, "deg")

        spacing = finite_real(_get("row_spacing_cm"))
        if spacing is not None:
            _add("row_spacing_cm", spacing, "cm")

        row_count = _get("row_count")
        if row_count is not None and not isinstance(row_count, bool):
            try:
                rc_int = int(row_count)
                if rc_int > 0:
                    _add("row_count", rc_int, "count")
            except (ValueError, TypeError):
                pass

        # ---- Row continuity (aggregate to mean) ----
        continuity_scores = _get("row_continuity_scores", [])
        if continuity_scores and isinstance(continuity_scores, (list, tuple)):
            valid_scores = [finite_real(s) for s in continuity_scores if finite_real(s) is not None]
            if valid_scores:
                mean_cont = sum(valid_scores) / len(valid_scores)
                _add("row_continuity_mean", round(mean_cont, 4), "score")

        # ---- Row breaks (count only — individual breaks are diagnostic) ----
        row_breaks = _get("row_breaks", [])
        if row_breaks and isinstance(row_breaks, (list, tuple)):
            _add("row_break_count", len(row_breaks), "count",
                 item_diagnostic_only=True)

        # ---- Weed separation metrics ----
        in_row_weed = finite_real(_get("in_row_weed_fraction"))
        if in_row_weed is not None and in_row_weed > 0:
            _add("in_row_weed_fraction", in_row_weed, "fraction")

        inter_row_weed = finite_real(_get("inter_row_weed_fraction"))
        if inter_row_weed is not None and inter_row_weed > 0:
            _add("inter_row_weed_fraction", inter_row_weed, "fraction")

        # ---- Orchard mode metrics ----
        tree_count = _get("tree_count")
        if tree_count is not None and not isinstance(tree_count, bool):
            try:
                tc_int = int(tree_count)
                if tc_int > 0:
                    _add("tree_count", tc_int, "count")
            except (ValueError, TypeError):
                pass

        missing_trees = _get("missing_tree_count", 0)
        if missing_trees is not None and not isinstance(missing_trees, bool):
            try:
                mt_int = int(missing_trees)
                if mt_int > 0:
                    _add("missing_tree_count", mt_int, "count")
            except (ValueError, TypeError):
                pass

        uniformity = finite_real(_get("canopy_uniformity_cv"))
        if uniformity is not None:
            _add("canopy_uniformity_cv", uniformity, "ratio")

        from layer1_fusion.truth_bridge import normalize_evidence_truth
        for item in items:
            normalize_evidence_truth(item, source_context=package)
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

        def _get(key, default=None):
            if isinstance(package, dict):
                return package.get(key, default)
            return getattr(package, key, default)

        mission_id = _get("mission_id", "unknown")
        qa_score, rel_weight, effective_quality, is_valid = _qualify_drone_quality(package)

        if not is_valid or effective_quality == 0.0:
            return SourceEnvelope(
                source_id=f"drone_{mission_id}",
                source_family="drone_structural",
                source_name="Drone Structural Analysis",
                package_id=mission_id,
                package_version="drone_rgb_v1.5",
                trust_score=0.0,
                spatial_scope="plot",
                temporal_scope="instant",
                source_status="unusable",
            )

        return SourceEnvelope(
            source_id=f"drone_{mission_id}",
            source_family="drone_structural",
            source_name="Drone Structural Analysis",
            package_id=mission_id,
            package_version="drone_rgb_v1.5",
            trust_score=effective_quality,
            spatial_scope="plot",
            temporal_scope="instant",
            source_status="ok" if effective_quality >= 0.5 else "degraded",
        )
