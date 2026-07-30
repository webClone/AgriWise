"""
ASMAE Scene Stack Builder.

Central orchestrator that assembles a complete multi-sensor scene stack
from Layer 0 source packages. This is the first step in the ASMAE pipeline.

Design:
  - Each scene keeps its native CRS and transform
  - No premature grid forcing
  - Scene quality is computed and low-quality scenes are excluded
  - The stack is sorted chronologically
  - Minimum scene counts are enforced for mode selection

Acceptance gates (V68):
  - At least N valid S2 scenes for adaptive optical mode
  - At least M valid S1 scenes for SAR-assisted mode
  - Per-scene transform/CRS available
  - Bad cloud/shadow scenes downweighted or excluded
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..config import (
    MIN_S1_SCENES_SAR_ASSISTED,
    MIN_S2_SCENES_OPTICAL_MODE,
    SCENE_QUALITY_THRESHOLD,
)
from ..schema import ASMAEInput, ASMAESceneRuntime
from .s1_scene_loader import load_s1_scenes
from .s2_scene_loader import load_s2_scenes
from .s5p_scene_loader import load_s5p_scenes
from .external_scene_loader import load_external_scenes
from .scene_quality import SceneQualityResult

logger = logging.getLogger(__name__)


class SceneStack:
    """Multi-sensor chronological scene stack for ASMAE.

    Contains all loaded scenes, quality assessments, and mode decisions.
    """

    def __init__(self) -> None:
        self.scenes: List[Dict[str, Any]] = []
        self.excluded_scenes: List[Dict[str, Any]] = []
        self.sensor_counts: Dict[str, int] = {}
        self.mode: str = "optical"  # optical | sar_assisted | degraded
        self.diagnostics: Dict[str, Any] = {}

    @property
    def s2_scenes(self) -> List[Dict[str, Any]]:
        return [s for s in self.scenes if s["runtime"].sensor == "S2"]

    @property
    def s1_scenes(self) -> List[Dict[str, Any]]:
        return [s for s in self.scenes if s["runtime"].sensor == "S1"]

    @property
    def s5p_scenes(self) -> List[Dict[str, Any]]:
        return [s for s in self.scenes if s["runtime"].sensor == "S5P"]

    @property
    def external_scenes(self) -> List[Dict[str, Any]]:
        return [s for s in self.scenes if s["runtime"].sensor == "EXTERNAL"]

    @property
    def runtimes(self) -> List[ASMAESceneRuntime]:
        return [s["runtime"] for s in self.scenes]

    @property
    def quality_scores(self) -> List[SceneQualityResult]:
        return [s["quality"] for s in self.scenes]

    def total_included(self) -> int:
        return len(self.scenes)

    def total_excluded(self) -> int:
        return len(self.excluded_scenes)

    def mean_quality(self) -> float:
        scores = [s["quality"].overall for s in self.scenes]
        return sum(scores) / len(scores) if scores else 0.0

    def date_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        times = [s["runtime"].acquisition_time for s in self.scenes]
        if not times:
            return (None, None)
        return (min(times), max(times))

    def to_dict(self) -> Dict[str, Any]:
        start, end = self.date_range()
        return {
            "total_included": self.total_included(),
            "total_excluded": self.total_excluded(),
            "sensor_counts": self.sensor_counts,
            "mode": self.mode,
            "mean_quality": round(self.mean_quality(), 4),
            "date_range": {
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
            },
            "scenes": [
                {
                    "scene_id": s["runtime"].scene_id,
                    "sensor": s["runtime"].sensor,
                    "acquisition_time": s["runtime"].acquisition_time.isoformat(),
                    "qa_score": s["quality"].overall,
                    "included": True,
                }
                for s in self.scenes
            ],
            "excluded": [
                {
                    "scene_id": s["runtime"].scene_id,
                    "sensor": s["runtime"].sensor,
                    "reason": s["quality"].exclusion_reason,
                }
                for s in self.excluded_scenes
            ],
            "diagnostics": self.diagnostics,
        }


def build_real_asmae_scene_stack(inp: ASMAEInput) -> SceneStack:
    """Build a stack consisting strictly of real provider Sentinel scenes."""
    stack = SceneStack()
    l0 = inp.layer0_source_packages or {}
    from .layer0_package_adapter import adapt_layer0_package_to_scene_candidate
    raster_composites = inp.raster_composites or {}

    # S2 packages: strictly real
    s2_pkgs = _extract_packages(l0, "asmae_sentinel2_real")
    try:
        from ..history.historical_scene_adapter import HistoricalSceneAdapter
        adapter = HistoricalSceneAdapter()
        s2_pkgs = [adapter.adapt(p) if hasattr(p, "quality_status") else p for p in s2_pkgs]
    except Exception:
        pass
    s2_candidates_raw = [adapt_layer0_package_to_scene_candidate(p, "sentinel2", raster_composites) for p in s2_pkgs]
    # Filter to real rasters only
    s2_candidates_raw = [c for c in s2_candidates_raw if c.reality == "real_raster"]
    s2_candidates = _select_best_candidates(s2_candidates_raw)
    s2_scenes = load_s2_scenes(s2_candidates)
    logger.info("Real S2 scenes loaded: %d", len(s2_scenes))

    # S1 packages: strictly real
    s1_pkgs = _extract_packages(l0, "asmae_sentinel1_real")
    try:
        from ..history.historical_scene_adapter import HistoricalSceneAdapter
        adapter = HistoricalSceneAdapter()
        s1_pkgs = [adapter.adapt(p) if hasattr(p, "quality_status") else p for p in s1_pkgs]
    except Exception:
        pass
    s1_candidates_raw = [adapt_layer0_package_to_scene_candidate(p, "sentinel1", raster_composites) for p in s1_pkgs]
    # Filter to real rasters only
    s1_candidates_raw = [c for c in s1_candidates_raw if c.reality == "real_raster"]
    s1_candidates = _select_best_candidates(s1_candidates_raw)
    
    s2_times = [
        s["runtime"].acquisition_time for s in s2_scenes
        if s["quality"].included
    ]
    s1_scenes = load_s1_scenes(s1_candidates, previous_acquisition_times=s2_times)
    logger.info("Real S1 scenes loaded: %d", len(s1_scenes))

    loadable_s2_count = sum(1 for c in s2_candidates if c.reality == "real_raster")
    loadable_s1_count = sum(1 for c in s1_candidates if c.reality == "real_raster")

    # S5P atmospheric context
    s5p_data = l0.get("s5p") or l0.get("sentinel5p")
    s5p_scenes = load_s5p_scenes(s5p_data)

    # External imagery
    ext_data = l0.get("external") or l0.get("external_imagery")
    if isinstance(ext_data, dict):
        ext_data = [ext_data]
    ext_scenes = load_external_scenes(ext_data)

    # Merge all scenes
    all_scenes = s2_scenes + s1_scenes + s5p_scenes + ext_scenes

    # Quality filter
    included = []
    excluded = []
    for scene in all_scenes:
        if scene["quality"].included:
            included.append(scene)
        else:
            excluded.append(scene)

    included.sort(key=lambda s: s["runtime"].acquisition_time)
    excluded.sort(key=lambda s: s["runtime"].acquisition_time)

    stack.scenes = included
    stack.excluded_scenes = excluded

    # Sensor counts
    sensor_counter = Counter(s["runtime"].sensor for s in included)
    stack.sensor_counts = dict(sensor_counter)

    # Determine mode
    n_s2 = loadable_s2_count
    n_s1 = loadable_s1_count

    if n_s2 + n_s1 > 0:
        if n_s2 >= MIN_S2_SCENES_OPTICAL_MODE and n_s1 >= MIN_S1_SCENES_SAR_ASSISTED:
            stack.mode = "sar_assisted"
        elif n_s2 >= MIN_S2_SCENES_OPTICAL_MODE:
            stack.mode = "optical"
        elif n_s1 >= MIN_S1_SCENES_SAR_ASSISTED:
            stack.mode = "sar_only"
        else:
            stack.mode = "degraded"
    else:
        stack.mode = "unavailable"

    stack.diagnostics = {
        "s2_loaded": len(s2_scenes),
        "s1_loaded": len(s1_scenes),
        "s5p_loaded": len(s5p_scenes),
        "external_loaded": len(ext_scenes),
        "total_loaded": len(all_scenes),
        "total_included": len(included),
        "total_excluded": len(excluded),
        "mode": stack.mode,
        "quality_threshold": SCENE_QUALITY_THRESHOLD,
        "min_s2_optical": MIN_S2_SCENES_OPTICAL_MODE,
        "min_s1_sar": MIN_S1_SCENES_SAR_ASSISTED,
        "s2_quality_mean": _safe_mean([s["quality"].overall for s in included if s["runtime"].sensor == "S2"]),
        "s1_quality_mean": _safe_mean([s["quality"].overall for s in included if s["runtime"].sensor == "S1"]),
    }
    return stack


def build_experimental_proxy_stack(inp: ASMAEInput) -> SceneStack:
    """Build a stack consisting strictly of experimental composite proxies."""
    stack = SceneStack()
    l0 = inp.layer0_source_packages or {}
    from .layer0_package_adapter import adapt_layer0_package_to_scene_candidate
    raster_composites = inp.raster_composites or {}

    # S2 packages: strictly experimental proxy
    s2_pkgs = _extract_packages(l0, "experimental_s2_proxy")
    try:
        from ..history.historical_scene_adapter import HistoricalSceneAdapter
        adapter = HistoricalSceneAdapter()
        s2_pkgs = [adapter.adapt(p) if hasattr(p, "quality_status") else p for p in s2_pkgs]
    except Exception:
        pass
    s2_candidates_raw = [adapt_layer0_package_to_scene_candidate(p, "sentinel2", raster_composites) for p in s2_pkgs]
    s2_candidates = _select_best_candidates(s2_candidates_raw)
    s2_scenes = load_s2_scenes(s2_candidates)
    logger.info("Proxy S2 scenes loaded: %d", len(s2_scenes))

    # S1 packages: strictly experimental proxy
    s1_pkgs = _extract_packages(l0, "experimental_s1_proxy")
    try:
        from ..history.historical_scene_adapter import HistoricalSceneAdapter
        adapter = HistoricalSceneAdapter()
        s1_pkgs = [adapter.adapt(p) if hasattr(p, "quality_status") else p for p in s1_pkgs]
    except Exception:
        pass
    s1_candidates_raw = [adapt_layer0_package_to_scene_candidate(p, "sentinel1", raster_composites) for p in s1_pkgs]
    s1_candidates = _select_best_candidates(s1_candidates_raw)
    
    s2_times = [
        s["runtime"].acquisition_time for s in s2_scenes
        if s["quality"].included
    ]
    s1_scenes = load_s1_scenes(s1_candidates, previous_acquisition_times=s2_times)
    logger.info("Proxy S1 scenes loaded: %d", len(s1_scenes))

    # For proxies, they are all forced to raster_composite_proxy
    scenes = s2_scenes + s1_scenes
    from layer05_asmae.truth_contract import normalize_asmae_runtime
    for s in scenes:
        s["runtime"].source_reality = "raster_composite_proxy"
        s["runtime"] = normalize_asmae_runtime(s["runtime"])

    stack.scenes = scenes
    stack.excluded_scenes = []
    
    # Sensor counts
    sensor_counter = Counter(s["runtime"].sensor for s in scenes)
    stack.sensor_counts = dict(sensor_counter)

    stack.mode = "raster_composite_proxy"
    stack.diagnostics = {
        "s2_loaded": len(s2_scenes),
        "s1_loaded": len(s1_scenes),
        "total_loaded": len(scenes),
        "total_included": len(scenes),
        "total_excluded": 0,
        "mode": stack.mode,
        "temporal_basis": "aggregate",
        "independent_observation_count": int(bool(s2_scenes)) + int(bool(s1_scenes)),
    }
    return stack


def build_scene_stack(inp: ASMAEInput) -> SceneStack:
    """Build a complete multi-sensor scene stack from ASMAEInput, dispatching to real or proxy stack."""
    policy = getattr(inp, "source_policy", None)
    if policy == "experimental":
        logger.info("Building experimental proxy stack")
        return build_experimental_proxy_stack(inp)
    elif policy == "historical":
        logger.info("Building historical archive scene stack")
        return build_historical_scene_stack(inp)
    elif policy == "hybrid":
        logger.info("Building hybrid scene stack")
        return build_hybrid_scene_stack(inp)
    else:
        logger.info("Building real ASMAE scene stack")
        return build_real_asmae_scene_stack(inp)


class HybridSceneStack(SceneStack):
    """BC.10.17: Partitioned stack representing real, proxy, and archive layers.
    Maintains compatibility with all down-stream consumers by behaving like a standard stack
    externally, while keeping partitions separate internally for proof metadata."""
    def __init__(self) -> None:
        super().__init__()
        self.real_scenes: List[Dict[str, Any]] = []
        self.proxy_scenes: List[Dict[str, Any]] = []
        self.archive_scenes: List[Dict[str, Any]] = []


def build_hybrid_scene_stack(inp: ASMAEInput) -> HybridSceneStack:
    """Build a hybrid stack consisting of both real Sentinel scenes and experimental proxies.

    Real Sentinel scenes are tagged with authority = "real".
    Experimental proxies are tagged with authority = "proxy".
    All scenes are merged and sorted chronologically.
    """
    stack = HybridSceneStack()

    # 1. Build real stack
    real_stack = build_real_asmae_scene_stack(inp)
    for s in real_stack.scenes:
        s["runtime"].authority = "real"
    for s in real_stack.excluded_scenes:
        s["runtime"].authority = "real"
    stack.real_scenes = real_stack.scenes

    # 2. Build experimental proxy stack
    proxy_stack = build_experimental_proxy_stack(inp)
    for s in proxy_stack.scenes:
        s["runtime"].authority = "proxy"
    for s in proxy_stack.excluded_scenes:
        s["runtime"].authority = "proxy"
    stack.proxy_scenes = proxy_stack.scenes

    # 3. Merge scenes
    all_included = real_stack.scenes + proxy_stack.scenes
    all_excluded = real_stack.excluded_scenes + proxy_stack.excluded_scenes

    # 4. Sort chronologically
    all_included.sort(key=lambda s: s["runtime"].acquisition_time)
    all_excluded.sort(key=lambda s: s["runtime"].acquisition_time)

    stack.scenes = all_included
    stack.excluded_scenes = all_excluded

    # 5. Sensor counts
    sensor_counter = Counter(s["runtime"].sensor for s in all_included)
    stack.sensor_counts = dict(sensor_counter)

    # 6. Mode: hybrid
    stack.mode = "hybrid"

    # 7. Diagnostics
    stack.diagnostics = {
        "real_diagnostics": real_stack.diagnostics,
        "proxy_diagnostics": proxy_stack.diagnostics,
        "total_included": len(all_included),
        "total_excluded": len(all_excluded),
        "mode": stack.mode,
        "scenes_real_count": len(stack.real_scenes),
        "scenes_proxy_count": len(stack.proxy_scenes),
        "scenes_archive_count": len(stack.archive_scenes),
        "authority_partition": {
            "approval": [s["runtime"].scene_id for s in stack.real_scenes],
            "advisory": [s["runtime"].scene_id for s in stack.real_scenes + stack.proxy_scenes],
            "prior": [s["runtime"].scene_id for s in stack.archive_scenes]
        }
    }
    return stack


def build_historical_scene_stack(inp: ASMAEInput) -> SceneStack:
    """Build a stack from historical archive records, accepting mean_only candidates.

    Unlike build_real_asmae_scene_stack (which filters to real_raster only),
    this path also admits mean_only candidates so that scenes with only scalar
    index means (no physical raster cache) are included in the archive stack.
    """
    stack = SceneStack()
    l0 = inp.layer0_source_packages or {}
    from .layer0_package_adapter import adapt_layer0_package_to_scene_candidate
    raster_composites = inp.raster_composites or {}

    # S2 packages — adapt HistoricalSceneRecord objects then classify
    s2_pkgs = _extract_packages(l0, "asmae_sentinel2_real")
    try:
        from ..history.historical_scene_adapter import HistoricalSceneAdapter
        adapter = HistoricalSceneAdapter()
        s2_pkgs = [adapter.adapt(p) if hasattr(p, "quality_status") else p for p in s2_pkgs]
    except Exception:
        pass
    s2_candidates_raw = [adapt_layer0_package_to_scene_candidate(p, "sentinel2", raster_composites) for p in s2_pkgs]
    # Historical path: admit real_raster AND mean_only candidates (no physical raster cache may exist).
    s2_candidates_raw = [c for c in s2_candidates_raw if c.reality in ("real_raster", "mean_only")]
    s2_candidates = _select_best_candidates(s2_candidates_raw)
    s2_scenes = load_s2_scenes(s2_candidates)
    logger.info("Historical S2 scenes loaded: %d", len(s2_scenes))

    # S1 packages — same relaxed filter
    s1_pkgs = _extract_packages(l0, "asmae_sentinel1_real")
    try:
        from ..history.historical_scene_adapter import HistoricalSceneAdapter
        adapter = HistoricalSceneAdapter()
        s1_pkgs = [adapter.adapt(p) if hasattr(p, "quality_status") else p for p in s1_pkgs]
    except Exception:
        pass
    s1_candidates_raw = [adapt_layer0_package_to_scene_candidate(p, "sentinel1", raster_composites) for p in s1_pkgs]
    s1_candidates_raw = [c for c in s1_candidates_raw if c.reality in ("real_raster", "mean_only")]
    s1_candidates = _select_best_candidates(s1_candidates_raw)

    s2_times = [
        s["runtime"].acquisition_time for s in s2_scenes
        if s["quality"].included
    ]
    s1_scenes = load_s1_scenes(s1_candidates, previous_acquisition_times=s2_times)
    logger.info("Historical S1 scenes loaded: %d", len(s1_scenes))

    all_scenes = s2_scenes + s1_scenes

    # Quality filter
    included = []
    excluded = []
    for scene in all_scenes:
        if scene["quality"].included:
            included.append(scene)
        else:
            excluded.append(scene)

    included.sort(key=lambda s: s["runtime"].acquisition_time)
    excluded.sort(key=lambda s: s["runtime"].acquisition_time)

    stack.scenes = included
    stack.excluded_scenes = excluded

    sensor_counter = Counter(s["runtime"].sensor for s in included)
    stack.sensor_counts = dict(sensor_counter)

    n_s2 = sum(1 for c in s2_candidates if c.reality in ("real_raster", "mean_only"))
    n_s1 = sum(1 for c in s1_candidates if c.reality in ("real_raster", "mean_only"))
    if n_s2 + n_s1 > 0:
        if n_s2 >= MIN_S2_SCENES_OPTICAL_MODE and n_s1 >= MIN_S1_SCENES_SAR_ASSISTED:
            stack.mode = "sar_assisted"
        elif n_s2 >= MIN_S2_SCENES_OPTICAL_MODE:
            stack.mode = "optical"
        elif n_s1 >= MIN_S1_SCENES_SAR_ASSISTED:
            stack.mode = "sar_only"
        else:
            stack.mode = "degraded"
    else:
        stack.mode = "unavailable"

    stack.diagnostics = {
        "s2_loaded": len(s2_scenes),
        "s1_loaded": len(s1_scenes),
        "total_loaded": len(all_scenes),
        "total_included": len(included),
        "total_excluded": len(excluded),
        "mode": stack.mode,
        "quality_threshold": SCENE_QUALITY_THRESHOLD,
        "min_s2_optical": MIN_S2_SCENES_OPTICAL_MODE,
        "min_s1_sar": MIN_S1_SCENES_SAR_ASSISTED,
    }
    return stack



# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_packages(
    l0: Dict[str, Any],
    sensor_key: str,
) -> List[Any]:
    """Extract source packages for a sensor type from Layer 0 dict.

    Handles multiple naming conventions:
      - l0["sentinel2"] — list of packages
      - l0["s2_packages"] — list of packages
      - l0[sensor_key] — single package or list
    """
    keys_to_try = [
        f"asmae_{sensor_key}_real",
        f"asmae_{sensor_key}_raw",
        sensor_key,
        sensor_key.replace("sentinel", "s"),
        f"{sensor_key}_packages",
        f"s{sensor_key[-1]}_packages" if sensor_key.startswith("sentinel") else None,
    ]

    all_pkgs = []
    for key in keys_to_try:
        if key is None:
            continue
        data = l0.get(key)
        if data is not None:
            if isinstance(data, list):
                all_pkgs.extend(data)
            else:
                all_pkgs.append(data)
    return all_pkgs


def _safe_mean(values: List[float]) -> float:
    """Compute mean, returning 0.0 for empty lists."""
    return round(sum(values) / len(values), 4) if values else 0.0

def _select_best_candidates(candidates: List[Any]) -> List[Any]:
    """Deduplicate candidates by scene_id or date, preferring highest reality score."""
    scores = {"real_raster": 3, "mean_only": 2, "raster_composite_proxy": 1, "unavailable": 0}
    best = {}
    for c in candidates:
        key = c.scene_id or c.acquisition_datetime
        if not key:
            continue
        if key not in best or scores.get(c.reality, 0) > scores.get(best[key].reality, 0):
            best[key] = c
    return list(best.values())
