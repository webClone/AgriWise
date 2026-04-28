"""
Sentinel-2 Scene Selector — Ranks candidate scenes by usability for a plot.

Works on pre-computed QA results (no live API calls).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from layer0.sentinel2.schemas import SceneQualityClass, Sentinel2QAResult


@dataclass
class SceneCandidate:
    """A candidate scene with its QA result."""
    scene_id: str = ""
    age_days: int = 0
    qa: Sentinel2QAResult = field(default_factory=Sentinel2QAResult)


@dataclass
class SceneRejection:
    """Why a scene was rejected."""
    scene_id: str = ""
    reason: str = ""
    cloud_fraction: float = 0.0
    valid_fraction: float = 0.0
    score: float = 0.0


@dataclass
class SceneSelectionResult:
    """Output of scene selection."""
    selected_scene_id: Optional[str] = None
    selected_reason: str = ""
    selected_score: float = 0.0
    selected_qa: Optional[Sentinel2QAResult] = None
    rejected_scenes: List[SceneRejection] = field(default_factory=list)


def compute_scene_score(candidate: SceneCandidate) -> float:
    """
    Score a scene for usability.

    score = 0.35 * valid_plot_fraction
          + 0.25 * freshness_score
          + 0.20 * low_cloud_score
          + 0.10 * low_shadow_score
          + 0.10 * geometry_score
    """
    qa = candidate.qa

    if not qa.usable:
        return 0.0

    valid_score = qa.valid_fraction
    freshness = max(0.0, 1.0 - candidate.age_days / 30.0)
    low_cloud = max(0.0, 1.0 - qa.cloud_fraction * 2.0)
    low_shadow = max(0.0, 1.0 - qa.shadow_fraction * 2.0)
    geometry = 1.0 - qa.boundary_contamination_score

    score = (
        0.35 * valid_score
        + 0.25 * freshness
        + 0.20 * low_cloud
        + 0.10 * low_shadow
        + 0.10 * geometry
    )
    return round(max(0.0, min(1.0, score)), 4)


def select_best_scene(candidates: List[SceneCandidate]) -> SceneSelectionResult:
    """
    Select the best scene from candidates.
    Rejects unusable scenes and ranks the rest by score.
    """
    if not candidates:
        return SceneSelectionResult(
            selected_reason="no_candidates_available",
        )

    scored = []
    rejections = []

    for cand in candidates:
        score = compute_scene_score(cand)
        if not cand.qa.usable:
            rejections.append(SceneRejection(
                scene_id=cand.scene_id,
                reason=cand.qa.reason,
                cloud_fraction=cand.qa.cloud_fraction,
                valid_fraction=cand.qa.valid_fraction,
                score=score,
            ))
        else:
            scored.append((score, cand))

    if not scored:
        return SceneSelectionResult(
            selected_reason="all_candidates_unusable",
            rejected_scenes=rejections,
        )

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_cand = scored[0]

    # Add non-selected usable scenes to rejections
    for score, cand in scored[1:]:
        rejections.append(SceneRejection(
            scene_id=cand.scene_id,
            reason=f"lower_score_{score:.3f}_vs_{best_score:.3f}",
            cloud_fraction=cand.qa.cloud_fraction,
            valid_fraction=cand.qa.valid_fraction,
            score=score,
        ))

    return SceneSelectionResult(
        selected_scene_id=best_cand.scene_id,
        selected_reason="best_valid_recent_scene",
        selected_score=best_score,
        selected_qa=best_cand.qa,
        rejected_scenes=rejections,
    )
