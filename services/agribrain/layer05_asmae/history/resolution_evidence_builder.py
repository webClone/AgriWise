# -*- coding: utf-8 -*-
"""
Resolution Evidence Builder — BC.10.17 P2.1
Compiles local microzone/pixel maps to prove resolution capabilities.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np

@dataclass
class ASMAEResolutionEvidence:
    sentinel_archive_real_scene_count: int = 0
    sentinel_archive_proxy_scene_count: int = 0
    weather_archive_status: str = "unavailable"
    retro_score_by_resolution: Dict[int, float] = field(default_factory=dict)
    local_retro_support_by_resolution: Dict[int, Any] = field(default_factory=dict)
    local_archive_support_map: Optional[np.ndarray] = None  # MANDATORY for 1m approval
    local_bma_disagreement_map: Optional[np.ndarray] = None
    local_weather_support_map: Optional[np.ndarray] = None
    local_uncertainty_support_map: Optional[np.ndarray] = None
    local_provider_scene_depth_map: Optional[np.ndarray] = None
    local_gap_risk_map: Optional[np.ndarray] = None
    evidence_status: str = "unavailable"
    missing_reasons: List[str] = field(default_factory=list)
    evidence_lineage: Dict[str, Any] = field(default_factory=dict)


def build_resolution_evidence(
    inp: Any,
    scene_stack: Any,
    retro_scores: Optional[Dict[int, float]] = None,
    local_retro_support: Optional[Dict[int, Any]] = None,
    local_archive_map: Optional[np.ndarray] = None,
    local_bma_map: Optional[np.ndarray] = None,
    local_weather_map: Optional[np.ndarray] = None,
    local_uncertainty_map: Optional[np.ndarray] = None,
    local_scene_depth_map: Optional[np.ndarray] = None,
    local_gap_risk_map: Optional[np.ndarray] = None,
    evidence_lineage: Optional[Dict[str, Any]] = None,
) -> ASMAEResolutionEvidence:
    """Builds a structured resolution evidence block validating 1m approval conditions (BC.10.17 P2.1)."""
    evidence = ASMAEResolutionEvidence()

    # 1. Archive scene counts
    real_count = 0
    proxy_count = 0
    if scene_stack:
        for s in getattr(scene_stack, "scenes", []):
            authority = getattr(s.get("runtime"), "authority", "")
            reality = getattr(s.get("runtime"), "source_reality", "")
            if authority == "real" and reality != "test_fixture_raster":
                real_count += 1
            elif authority == "proxy" or reality == "raster_composite_proxy":
                proxy_count += 1
    
    evidence.sentinel_archive_real_scene_count = real_count
    evidence.sentinel_archive_proxy_scene_count = proxy_count

    # 2. Weather status
    evidence.weather_archive_status = getattr(inp, "weather_archive_status", "unavailable")

    # 3. Retrovalidation scores
    evidence.retro_score_by_resolution = retro_scores or {}
    evidence.local_retro_support_by_resolution = local_retro_support or {}

    # 4. Local maps
    evidence.local_archive_support_map = local_archive_map
    evidence.local_bma_disagreement_map = local_bma_map
    evidence.local_weather_support_map = local_weather_map
    evidence.local_uncertainty_support_map = local_uncertainty_map
    evidence.local_provider_scene_depth_map = local_scene_depth_map
    evidence.local_gap_risk_map = local_gap_risk_map
    evidence.evidence_lineage = dict(evidence_lineage or {})

    # 5. Check if we have evidence for 1m
    missing = []
    if local_retro_support is None or local_retro_support.get(1) is None:
        missing.append("local_retro_support_by_resolution[1]")
    if local_archive_map is None:
        missing.append("local_archive_support_map")
    if local_uncertainty_map is None:
        missing.append("local_uncertainty_support_map")
    if local_scene_depth_map is None:
        missing.append("local_provider_scene_depth_map")
    if local_gap_risk_map is None:
        missing.append("local_gap_risk_map")

    # Local approval evidence must be an independently persisted historical
    # product. Current-run posterior, uncertainty, retrovalidation, global
    # scene counts, or broadcast weather values cannot prove local resolution.
    lineage = evidence.evidence_lineage
    if not lineage.get("independent_historical_product"):
        missing.append("independent_historical_resolution_evidence")
    if not lineage.get("excludes_current_run"):
        missing.append("current_run_exclusion_proof")
    if not lineage.get("source_hash"):
        missing.append("resolution_evidence_source_hash")

    def _is_spatially_informative(value: Optional[np.ndarray]) -> bool:
        if value is None:
            return False
        arr = np.asarray(value, dtype=float)
        finite = arr[np.isfinite(arr)]
        return bool(finite.size > 1 and float(np.ptp(finite)) > 0.0)

    if not _is_spatially_informative(local_scene_depth_map):
        missing.append("local_provider_scene_depth_is_broadcast_or_empty")
    if not _is_spatially_informative(local_gap_risk_map):
        missing.append("local_gap_risk_is_constant_or_empty")
    if local_weather_map is not None and not _is_spatially_informative(local_weather_map):
        missing.append("local_weather_support_is_broadcast_or_empty")

    evidence.missing_reasons = list(dict.fromkeys(missing))

    if not missing:
        evidence.evidence_status = "available"
    else:
        evidence.evidence_status = "unavailable"

    return evidence
