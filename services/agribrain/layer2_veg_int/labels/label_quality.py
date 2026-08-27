"""
Crop Intelligence v6.0B — Label Quality Scoring.

Computes a multi-dimensional quality score for each crop label.
Used by TrainingDatasetBuilder to filter unreliable training samples.

Quality dimensions:
  temporal_coverage:    % of crop cycle covered by feature data
  feature_completeness: CropFeatureVector.data_completeness
  geometry_stability:   1.0 if geometry hash matches, 0.0 if changed
  source_trust:         Lookup from label_source (admin=1.0, farmer=0.8, etc.)
  freshness:            Exponential decay from created_at (half-life 365 days)

Composite formula:
  overall = 0.25 * temporal + 0.25 * features + 0.15 * geometry
          + 0.20 * trust    + 0.15 * freshness

Quality tiers:
  A: > 0.8  (excellent — suitable for model training)
  B: > 0.6  (good — suitable with caution)
  C: > 0.4  (fair — include only in large datasets)
  D: <= 0.4 (poor — exclude from training)
"""

import math
from datetime import datetime, timezone
from typing import Dict, Optional

from .label_schema import (
    CropLabel,
    LabelQualityScore,
    SOURCE_TRUST,
    TRAINING_ELIGIBLE_LABEL_SOURCES,
    FEATURE_VECTOR_VERSION,
)

# Half-life for freshness decay (days)
FRESHNESS_HALF_LIFE_DAYS = 365.0


def _compute_freshness(created_at: str) -> float:
    """Compute freshness as exponential decay from created_at.

    Half-life = 365 days. Returns 1.0 for today, 0.5 for 1 year ago, etc.
    """
    if not created_at:
        return 0.5

    try:
        if "T" not in created_at:
            created = datetime.strptime(created_at, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 0.5

    now = datetime.now(timezone.utc)
    age_days = max(0.0, (now - created).total_seconds() / 86400.0)


    # Exponential decay: f(t) = 2^(-t/half_life)
    return math.pow(2.0, -age_days / FRESHNESS_HALF_LIFE_DAYS)


def _compute_temporal_coverage(
    label: CropLabel,
    feature_vector: Optional[Dict] = None,
) -> float:
    """Estimate how much of the crop cycle is covered by feature data.

    If feature_vector_snapshot has data_completeness, use it.
    If planting and harvest dates exist but no features, return 0.0.
    If no dates, estimate from data_sources if available.
    """
    if feature_vector:
        # Use data_completeness from the feature vector
        return feature_vector.get("data_completeness", 0.0)

    fvs = label.feature_vector_snapshot
    if fvs:
        return fvs.get("data_completeness", 0.3)

    # No feature vector at all
    if label.planting_date and label.harvest_date:
        return 0.0  # We know the cycle but have no data

    return 0.0


def _compute_feature_completeness(
    feature_vector: Optional[Dict] = None,
    feature_snapshot: Optional[Dict] = None,
) -> float:
    """Compute feature completeness from CropFeatureVector.

    Count non-None values / total values in the flat dict.
    """
    fv = feature_vector or feature_snapshot
    if not fv:
        return 0.0

    # If the flat dict has explicit data_completeness, use it
    if "data_completeness" in fv:
        return fv["data_completeness"]

    total = 0
    present = 0
    for k, v in fv.items():
        if k.startswith("_") or k in ("data_sources", "extraction_warnings"):
            continue
        total += 1
        if v is not None:
            present += 1

    return present / total if total > 0 else 0.0


def _quality_tier(score: float) -> str:
    """Map overall quality score to tier."""
    if score > 0.8:
        return "A"
    elif score > 0.6:
        return "B"
    elif score > 0.4:
        return "C"
    else:
        return "D"


def compute_label_quality(
    label: CropLabel,
    current_geometry_hash: Optional[str] = None,
    feature_vector: Optional[Dict] = None,
) -> LabelQualityScore:
    """Compute quality score for a crop label.

    Args:
        label: The crop label to score
        current_geometry_hash: Current geometry hash of the plot (optional)
        feature_vector: CropFeatureVector.to_flat_dict() (optional)

    Returns:
        LabelQualityScore with all dimensions and composite score.
    """
    warnings = []

    # 1. Temporal coverage
    temporal = _compute_temporal_coverage(label, feature_vector)

    # 2. Feature completeness
    completeness = _compute_feature_completeness(
        feature_vector, label.feature_vector_snapshot
    )

    # 3. Geometry stability
    geo_stability = 1.0
    if current_geometry_hash:
        if label.geometry_hash == "NO_GEOMETRY":
            geo_stability = 0.5
            warnings.append("no_geometry")
        elif label.geometry_hash != current_geometry_hash:
            geo_stability = 0.0
            warnings.append("geometry_changed")

    # 4. Source trust
    trust = SOURCE_TRUST.get(label.label_source, 0.5)
    if label.label_source not in TRAINING_ELIGIBLE_LABEL_SOURCES:
        warnings.append("source_not_training_eligible")
    if not getattr(label, "authority_validated", False):
        warnings.append("label_authority_not_validated")

    # 5. Freshness
    freshness = _compute_freshness(label.created_at)

    # 6. Stale feature vector check
    if (
        label.feature_vector_snapshot
        and label.feature_vector_version != FEATURE_VECTOR_VERSION
    ):
        warnings.append("stale_feature_vector")
        # Penalize slightly
        completeness *= 0.8

    # 7. No feature vector at all
    if not label.feature_vector_snapshot and not feature_vector:
        warnings.append("no_feature_vector_attached")

    # Composite quality
    overall = (
        0.25 * temporal
        + 0.25 * completeness
        + 0.15 * geo_stability
        + 0.20 * trust
        + 0.15 * freshness
    )

    overall = round(max(0.0, min(1.0, overall)), 3)

    return LabelQualityScore(
        label_id=label.label_id,
        temporal_coverage=round(temporal, 3),
        feature_completeness=round(completeness, 3),
        geometry_stability=round(geo_stability, 3),
        source_trust=trust,
        freshness=round(freshness, 3),
        overall_quality=overall,
        quality_tier=_quality_tier(overall),
        quality_warnings=warnings,
    )
