"""
Layer 1 Context Invariants — Runtime Safety Checks on Layer1ContextPackage.

Enforces non-negotiable invariants at runtime to prevent silent corruption.
Modeled on Layer 0's enforce_all_invariants() pattern.

These run on EVERY pipeline execution, after fusion but before return.

Invariants:
  1. No NaN/Inf in numeric evidence values
  2. Value bounds (NDVI ∈ [-1,1], moisture ∈ [0,1], precip ≥ 0, temp ∈ [-50,60])
  3. Confidence/reliability floor (≥ 0.01 / ≥ 0.05 — prevents division by zero)
  4. Fused feature provenance (every feature has ≥1 source_evidence_ids)
  5. Source weights sum ~1.0 for numeric features
  6. Temporal coherence (no evidence observed_at > run_timestamp + 1h)
  7. Resolution mismatch flagging (SoilGrids 250m vs S2 10m)
  8. Provenance completeness (run_id, engine_version, contract_version non-empty)
  9. Spatial index integrity (zone area fractions sum ~1.0)
  10. Data health bounds (overall ∈ [0,1], status canonical)

Usage:
    from layer1_fusion.context_invariants import enforce_context_invariants
    violations = enforce_context_invariants(pkg)
    if violations:
        pkg.provenance.invariant_violations = [v.to_dict() for v in violations]
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .schemas import (
    EvidenceItem,
    FusedFeature,
    FusedFeatureSet,
    Layer1ContextPackage,
)


# ============================================================================
# Violation dataclass
# ============================================================================

class ContextInvariantViolation:
    """Single invariant violation on a Layer1ContextPackage."""
    __slots__ = ("invariant", "severity", "location", "detail", "auto_fixed")

    def __init__(self, invariant: str, severity: str, location: str,
                 detail: str, auto_fixed: bool = False):
        self.invariant = invariant
        self.severity = severity  # "error", "warning", "fixed"
        self.location = location
        self.detail = detail
        self.auto_fixed = auto_fixed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invariant": self.invariant,
            "severity": self.severity,
            "location": self.location,
            "detail": self.detail,
            "auto_fixed": self.auto_fixed,
        }


# ============================================================================
# Constants (matching Layer 0 patterns)
# ============================================================================

CONFIDENCE_MIN = 0.01
RELIABILITY_MIN = 0.05

VALUE_BOUNDS = {
    "ndvi":             (-1.0, 1.0),
    "ndmi":             (-1.0, 1.0),
    "ndre":             (-1.0, 1.0),
    "evi":              (-1.0, 1.0),
    "bsi":              (-1.0, 1.0),
    "vegetation_fraction": (0.0, 1.0),
    "bare_soil_fraction":  (0.0, 1.0),
    "soil_moisture_vwc":   (0.0, 1.0),
    "canopy_cover":        (0.0, 1.0),
    "surface_wetness_proxy_mean": (0.0, 1.0),
}

PRECIP_VARS = {"forecast_precip", "precipitation", "rain_mm"}
TEMP_VARS = {"forecast_temp_max", "forecast_temp_min", "temperature",
             "temp_max", "temp_min"}
TEMP_BOUNDS = (-50.0, 60.0)

RESOLUTION_COARSE_THRESHOLD = 100.0  # meters — SoilGrids is ~250m


# ============================================================================
# Individual checks
# ============================================================================

def check_no_nan_inf(
    evidence: List[EvidenceItem],
    auto_fix: bool = True,
) -> List[ContextInvariantViolation]:
    """Invariant 1: No NaN/Inf in numeric evidence values."""
    violations = []
    for e in evidence:
        if not isinstance(e.value, (int, float)):
            continue
        if math.isnan(e.value) or math.isinf(e.value):
            if auto_fix:
                e.value = None
                violations.append(ContextInvariantViolation(
                    "no_nan_inf", "fixed",
                    f"evidence={e.evidence_id}",
                    f"Value was {e.value}, reset to None",
                    auto_fixed=True,
                ))
            else:
                violations.append(ContextInvariantViolation(
                    "no_nan_inf", "error",
                    f"evidence={e.evidence_id}",
                    f"Value is NaN/Inf",
                ))
    return violations


def check_value_bounds(
    evidence: List[EvidenceItem],
    auto_clamp: bool = True,
) -> List[ContextInvariantViolation]:
    """Invariant 2: Evidence values within physical bounds."""
    violations = []
    for e in evidence:
        if not isinstance(e.value, (int, float)):
            continue

        # Index bounds
        if e.variable in VALUE_BOUNDS:
            lo, hi = VALUE_BOUNDS[e.variable]
            if e.value < lo or e.value > hi:
                if auto_clamp:
                    clamped = max(lo, min(hi, e.value))
                    violations.append(ContextInvariantViolation(
                        "value_bounds", "fixed",
                        f"evidence={e.evidence_id}/{e.variable}",
                        f"Clamped {e.value:.4f} → [{lo}, {hi}]",
                        auto_fixed=True,
                    ))
                    e.value = clamped
                else:
                    violations.append(ContextInvariantViolation(
                        "value_bounds", "error",
                        f"evidence={e.evidence_id}/{e.variable}",
                        f"Value {e.value:.4f} out of [{lo}, {hi}]",
                    ))

        # Precipitation non-negative
        if e.variable in PRECIP_VARS and e.value < 0:
            if auto_clamp:
                violations.append(ContextInvariantViolation(
                    "value_bounds", "fixed",
                    f"evidence={e.evidence_id}/{e.variable}",
                    f"Precipitation {e.value:.2f} clamped to 0",
                    auto_fixed=True,
                ))
                e.value = 0.0
            else:
                violations.append(ContextInvariantViolation(
                    "value_bounds", "error",
                    f"evidence={e.evidence_id}/{e.variable}",
                    f"Negative precipitation: {e.value:.2f}",
                ))

        # Temperature bounds
        if e.variable in TEMP_VARS:
            lo, hi = TEMP_BOUNDS
            if e.value < lo or e.value > hi:
                violations.append(ContextInvariantViolation(
                    "value_bounds", "warning",
                    f"evidence={e.evidence_id}/{e.variable}",
                    f"Temperature {e.value:.1f}°C outside [{lo}, {hi}]",
                ))

    return violations


def check_confidence_floor(
    evidence: List[EvidenceItem],
    auto_clamp: bool = True,
) -> List[ContextInvariantViolation]:
    """Invariant 3: Confidence ≥ 0.01, reliability ≥ 0.05.

    Layer 0 enforces reliability ≥ 0.05 to prevent R_effective = σ²/w
    division by zero in the Kalman engine. We mirror this.
    """
    violations = []
    for e in evidence:
        if e.confidence < CONFIDENCE_MIN:
            if auto_clamp:
                violations.append(ContextInvariantViolation(
                    "confidence_floor", "fixed",
                    f"evidence={e.evidence_id}",
                    f"Confidence {e.confidence:.4f} clamped to {CONFIDENCE_MIN}",
                    auto_fixed=True,
                ))
                e.confidence = CONFIDENCE_MIN
            else:
                violations.append(ContextInvariantViolation(
                    "confidence_floor", "error",
                    f"evidence={e.evidence_id}",
                    f"Confidence {e.confidence:.4f} < {CONFIDENCE_MIN}",
                ))

        if e.reliability < RELIABILITY_MIN:
            if auto_clamp:
                violations.append(ContextInvariantViolation(
                    "reliability_floor", "fixed",
                    f"evidence={e.evidence_id}",
                    f"Reliability {e.reliability:.4f} clamped to {RELIABILITY_MIN}",
                    auto_fixed=True,
                ))
                e.reliability = RELIABILITY_MIN
            else:
                violations.append(ContextInvariantViolation(
                    "reliability_floor", "error",
                    f"evidence={e.evidence_id}",
                    f"Reliability {e.reliability:.4f} < {RELIABILITY_MIN}",
                ))

    return violations


def check_fused_provenance(
    fused: FusedFeatureSet,
) -> List[ContextInvariantViolation]:
    """Invariant 4: Every fused feature has ≥1 source_evidence_ids."""
    violations = []
    for group_name, group in [
        ("water", fused.water_context),
        ("vegetation", fused.vegetation_context),
        ("phenology", fused.phenology_context),
        ("stress", fused.stress_evidence_context),
        ("soil_site", fused.soil_site_context),
        ("operational", fused.operational_context),
        ("data_quality", fused.data_quality_context),
    ]:
        for f in group:
            if not f.source_evidence_ids:
                violations.append(ContextInvariantViolation(
                    "fused_provenance", "error",
                    f"fused/{group_name}/{f.name}",
                    "Fused feature has no source_evidence_ids",
                ))
    return violations


def check_source_weight_sum(
    fused: FusedFeatureSet,
    auto_normalize: bool = True,
) -> List[ContextInvariantViolation]:
    """Invariant 5: Source weights sum to ~1.0 for numeric features."""
    violations = []
    for group in [fused.water_context, fused.vegetation_context,
                  fused.stress_evidence_context]:
        for f in group:
            if not f.source_weights or not isinstance(f.value, (int, float)):
                continue
            total = sum(f.source_weights.values())
            if abs(total - 1.0) > 0.05:
                if auto_normalize and total > 0:
                    for k in f.source_weights:
                        f.source_weights[k] /= total
                    violations.append(ContextInvariantViolation(
                        "source_weight_sum", "fixed",
                        f"fused/{f.name}",
                        f"Weights summed to {total:.4f}, normalized",
                        auto_fixed=True,
                    ))
                else:
                    violations.append(ContextInvariantViolation(
                        "source_weight_sum", "warning",
                        f"fused/{f.name}",
                        f"Weights sum to {total:.4f}, expected ~1.0",
                    ))
    return violations


def check_temporal_coherence(
    evidence: List[EvidenceItem],
    run_timestamp: datetime,
) -> List[ContextInvariantViolation]:
    """Invariant 6: No evidence observed_at > run_timestamp + 1h."""
    violations = []
    cutoff = run_timestamp + timedelta(hours=1)
    for e in evidence:
        if e.observed_at is not None and e.observed_at > cutoff:
            violations.append(ContextInvariantViolation(
                "temporal_coherence", "warning",
                f"evidence={e.evidence_id}",
                f"observed_at {e.observed_at.isoformat()} is in the future "
                f"(run_timestamp={run_timestamp.isoformat()})",
            ))
    return violations


def check_resolution_mismatch(
    pkg: Layer1ContextPackage,
) -> List[ContextInvariantViolation]:
    """Invariant 7: Flag coarse resolution sources (> 100m)."""
    violations = []
    coarse_rasters = [
        r for r in pkg.spatial_index.raster_refs
        if r.resolution_m > RESOLUTION_COARSE_THRESHOLD
    ]
    if coarse_rasters:
        for r in coarse_rasters:
            violations.append(ContextInvariantViolation(
                "resolution_mismatch", "warning",
                f"raster={r.raster_id}",
                f"Resolution {r.resolution_m}m > {RESOLUTION_COARSE_THRESHOLD}m threshold "
                f"(variable={r.variable})",
            ))
    return violations


def check_provenance_completeness(
    pkg: Layer1ContextPackage,
) -> List[ContextInvariantViolation]:
    """Invariant 8: run_id, engine_version, contract_version non-empty."""
    violations = []
    prov = pkg.provenance
    if not prov.run_id:
        violations.append(ContextInvariantViolation(
            "provenance_completeness", "error", "provenance.run_id",
            "run_id is empty",
        ))
    if not prov.engine_version:
        violations.append(ContextInvariantViolation(
            "provenance_completeness", "error", "provenance.engine_version",
            "engine_version is empty",
        ))
    if not prov.contract_version:
        violations.append(ContextInvariantViolation(
            "provenance_completeness", "error", "provenance.contract_version",
            "contract_version is empty",
        ))
    return violations


def check_zone_area_fractions(
    pkg: Layer1ContextPackage,
) -> List[ContextInvariantViolation]:
    """Invariant 9: Zone area fractions sum to ~1.0 (if zones present)."""
    violations = []
    zones = pkg.spatial_index.zones
    if not zones:
        return violations

    fractions = [z.area_fraction for z in zones if z.area_fraction > 0]
    if fractions:
        total = sum(fractions)
        if abs(total - 1.0) > 0.10:
            violations.append(ContextInvariantViolation(
                "zone_area_fraction_sum", "warning",
                "spatial_index.zones",
                f"Zone area fractions sum to {total:.3f}, expected ~1.0",
            ))
    return violations


def check_data_health(
    pkg: Layer1ContextPackage,
) -> List[ContextInvariantViolation]:
    """Invariant 10: Data health bounds and canonical status."""
    violations = []
    dh = pkg.diagnostics.data_health

    if not (0.0 <= dh.overall <= 1.0):
        violations.append(ContextInvariantViolation(
            "data_health_bounds", "error", "data_health.overall",
            f"Overall {dh.overall} not in [0, 1]",
        ))

    if dh.status not in ("ok", "degraded", "unusable"):
        violations.append(ContextInvariantViolation(
            "data_health_status", "error", "data_health.status",
            f"Status '{dh.status}' is not canonical",
        ))

    return violations


# ============================================================================
# Combined enforcer
# ============================================================================

def enforce_context_invariants(
    pkg: Layer1ContextPackage,
    auto_fix: bool = True,
) -> List[ContextInvariantViolation]:
    """Run ALL runtime invariants on a Layer1ContextPackage.

    If auto_fix=True (default for production), values are clamped/reset
    in-place and violations are marked as "fixed".

    Returns list of all violations found. Production code should store
    these in provenance for audit trail.
    """
    violations: List[ContextInvariantViolation] = []

    # Evidence-level checks
    evidence = pkg.evidence_items
    violations.extend(check_no_nan_inf(evidence, auto_fix=auto_fix))
    violations.extend(check_value_bounds(evidence, auto_clamp=auto_fix))
    violations.extend(check_confidence_floor(evidence, auto_clamp=auto_fix))

    # Temporal coherence
    if pkg.generated_at:
        violations.extend(check_temporal_coherence(evidence, pkg.generated_at))

    # Fused feature checks
    violations.extend(check_fused_provenance(pkg.fused_features))
    violations.extend(check_source_weight_sum(
        pkg.fused_features, auto_normalize=auto_fix))

    # Package-level checks
    violations.extend(check_resolution_mismatch(pkg))
    violations.extend(check_provenance_completeness(pkg))
    violations.extend(check_zone_area_fractions(pkg))
    violations.extend(check_data_health(pkg))

    return violations


# ============================================================================
# Computed health scores (replacing hardcoded 1.0)
# ============================================================================

def compute_spatial_fidelity(pkg: Layer1ContextPackage) -> float:
    """Compute real spatial fidelity from resolution mix, zone coverage, and
    edge contamination.

    Scoring:
    - Base: 1.0 if rasters present, 0.5 if none
    - Resolution mix penalty: -0.10 if both fine (<100m) and coarse (≥100m)
      rasters are present (mismatch between S2 10m and SoilGrids 250m)
    - Coarse-only penalty: -0.15 per coarse raster (max -0.5)
    - Zone coverage bonus: +0.10 if zones present with area fractions ~1.0
    - Edge contamination penalty: -0.05 per edge with score ≥ 0.5 (max -0.15)
    """
    rasters = pkg.spatial_index.raster_refs
    zones = pkg.spatial_index.zones
    edges = pkg.spatial_index.edge_regions

    if not rasters:
        return 0.5

    # Base = 1.0
    score = 1.0

    # Resolution mix analysis
    fine = [r for r in rasters if r.resolution_m < RESOLUTION_COARSE_THRESHOLD]
    coarse = [r for r in rasters if r.resolution_m >= RESOLUTION_COARSE_THRESHOLD]

    if fine and coarse:
        # Mix penalty: fine + coarse sources present (resolution mismatch)
        score -= 0.10
    elif coarse and not fine:
        # All coarse: heavier penalty
        penalty = min(0.5, len(coarse) * 0.15)
        score -= penalty

    # Zone coverage bonus
    if zones:
        fractions = [z.area_fraction for z in zones if z.area_fraction > 0]
        if fractions and abs(sum(fractions) - 1.0) < 0.10:
            score += 0.10

    # Edge contamination penalty
    if edges:
        high_contam = sum(1 for e in edges if e.contamination_score >= 0.5)
        score -= min(0.15, high_contam * 0.05)

    return round(max(0.0, min(1.0, score)), 3)


def compute_provenance_completeness(pkg: Layer1ContextPackage) -> float:
    """Compute real provenance completeness from coverage.

    Checks:
    - run_id present (0.2)
    - engine_version present (0.2)
    - contract_version present (0.2)
    - input_package_ids non-empty (0.2)
    - evidence_count > 0 (0.2)
    """
    score = 0.0
    prov = pkg.provenance
    if prov.run_id:
        score += 0.2
    if prov.engine_version:
        score += 0.2
    if prov.contract_version:
        score += 0.2
    if prov.input_package_ids:
        score += 0.2
    if prov.evidence_count > 0:
        score += 0.2
    return round(score, 3)
