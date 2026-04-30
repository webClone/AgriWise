"""
Layer 2 Intelligence — Context Invariants.

10 runtime checks on Layer2Output, mirroring the L1 pattern.
Auto-fixes safe cases (clamp bounds, inflate uncertainty on degraded data).
Error-level checks block the output from being considered production-safe.

Checks:
  1. stress_confidence_floor — clamp to 0.05
  2. stress_severity_bounds — clamp [0, 1]
  3. no_conflicting_attribution_without_explanation
  4. phenology_gdd_consistency
  5. zone_coverage_integrity
  6. uncertainty_inflation_on_degraded
  7. no_prescription_vocabulary
  8. diagnostic_only_no_strong_conclusion
  9. run_id_present
 10. provenance_complete
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .schemas import (
    FORBIDDEN_L2_VOCABULARY,
    Layer2Output,
)


@dataclass
class InvariantViolation:
    """A single invariant check result."""
    check_name: str
    severity: str          # warning | error
    description: str
    auto_fixed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "severity": self.severity,
            "description": self.description,
            "auto_fixed": self.auto_fixed,
        }


def enforce_layer2_invariants(pkg: Layer2Output) -> List[InvariantViolation]:
    """Run all 10 invariant checks. Auto-fixes safe cases in-place."""
    violations: List[InvariantViolation] = []

    violations.extend(_check_stress_confidence_floor(pkg))
    violations.extend(_check_stress_severity_bounds(pkg))
    violations.extend(_check_conflicting_attribution(pkg))
    violations.extend(_check_phenology_gdd_consistency(pkg))
    violations.extend(_check_zone_coverage_integrity(pkg))
    violations.extend(_check_uncertainty_inflation(pkg))
    violations.extend(_check_prescription_vocabulary(pkg))
    violations.extend(_check_diagnostic_only_severity(pkg))
    violations.extend(_check_run_id(pkg))
    violations.extend(_check_provenance_complete(pkg))

    return violations


# ── 1. Stress confidence floor ──────────────────────────────────────────────

def _check_stress_confidence_floor(pkg: Layer2Output) -> List[InvariantViolation]:
    violations = []
    for s in pkg.stress_context:
        if s.confidence < 0.05:
            old = s.confidence
            s.confidence = 0.05
            violations.append(InvariantViolation(
                "stress_confidence_floor", "warning",
                f"Stress {s.stress_id} confidence {old:.3f} → clamped to 0.05",
                auto_fixed=True,
            ))
    return violations


# ── 2. Stress severity bounds ───────────────────────────────────────────────

def _check_stress_severity_bounds(pkg: Layer2Output) -> List[InvariantViolation]:
    violations = []
    for s in pkg.stress_context:
        if s.severity < 0.0:
            old = s.severity
            s.severity = 0.0
            violations.append(InvariantViolation(
                "stress_severity_bounds", "warning",
                f"Stress {s.stress_id} severity {old:.3f} → clamped to 0.0",
                auto_fixed=True,
            ))
        elif s.severity > 1.0:
            old = s.severity
            s.severity = 1.0
            violations.append(InvariantViolation(
                "stress_severity_bounds", "warning",
                f"Stress {s.stress_id} severity {old:.3f} → clamped to 1.0",
                auto_fixed=True,
            ))
    return violations


# ── 3. No conflicting attribution without explanation ───────────────────────

def _check_conflicting_attribution(pkg: Layer2Output) -> List[InvariantViolation]:
    """If two stress items for the same zone have conflicting types,
    at least one must have an explanation_basis entry about the conflict."""
    violations = []
    zone_stresses: Dict[str, List] = {}
    for s in pkg.stress_context:
        key = s.scope_id or "plot"
        zone_stresses.setdefault(key, []).append(s)

    for zone_id, items in zone_stresses.items():
        types = set(s.stress_type for s in items)
        if len(types) > 1:
            has_conflict_explanation = any(
                any("conflict" in e.lower() for e in s.explanation_basis)
                for s in items
            )
            if not has_conflict_explanation:
                # Auto-fix: add conflict flag
                for s in items:
                    s.flags.append("multi_stress_type_in_zone")
                violations.append(InvariantViolation(
                    "conflicting_attribution_explanation", "warning",
                    f"Zone {zone_id}: multiple stress types {types} without conflict explanation — flagged",
                    auto_fixed=True,
                ))
    return violations


# ── 4. Phenology GDD consistency ───────────────────────────────────────────

def _check_phenology_gdd_consistency(pkg: Layer2Output) -> List[InvariantViolation]:
    """GDD=0 but stage not bare_soil/unknown is suspicious."""
    violations = []
    for p in pkg.phenology_adjusted_indices:
        if p.gdd_accumulated == 0.0 and p.crop_stage not in ("bare_soil", "unknown", "BARE_SOIL", "UNKNOWN", ""):
            violations.append(InvariantViolation(
                "phenology_gdd_consistency", "warning",
                f"Phenology '{p.name}': GDD=0 but stage='{p.crop_stage}' — may indicate missing GDD data",
            ))
    return violations


# ── 5. Zone coverage integrity ──────────────────────────────────────────────

def _check_zone_coverage_integrity(pkg: Layer2Output) -> List[InvariantViolation]:
    """zone_stress_map zones must exist in spatial_index_ref."""
    violations = []
    if pkg.spatial_index_ref and pkg.zone_stress_map:
        valid_zone_ids = {z.zone_id for z in pkg.spatial_index_ref.zones}
        for zone_id in pkg.zone_stress_map:
            if zone_id not in valid_zone_ids and zone_id != "plot":
                violations.append(InvariantViolation(
                    "zone_coverage_integrity", "warning",
                    f"Zone '{zone_id}' in zone_stress_map but not in spatial_index",
                ))
    return violations


# ── 6. Uncertainty inflation on degraded data ──────────────────────────────

def _check_uncertainty_inflation(pkg: Layer2Output) -> List[InvariantViolation]:
    """If L1 data_health.overall < 0.4, inflate all stress uncertainties ×1.5."""
    violations = []
    if pkg.data_health.overall < 0.4:
        for s in pkg.stress_context:
            if s.uncertainty < 0.15:
                old = s.uncertainty
                s.uncertainty = round(s.uncertainty * 1.5, 4)
                violations.append(InvariantViolation(
                    "uncertainty_inflation_degraded", "warning",
                    f"Stress {s.stress_id} uncertainty {old:.4f} → {s.uncertainty:.4f} "
                    f"(inflated ×1.5, data_health={pkg.data_health.overall:.3f})",
                    auto_fixed=True,
                ))
    return violations


# ── 7. No prescription vocabulary ──────────────────────────────────────────

def _check_prescription_vocabulary(pkg: Layer2Output) -> List[InvariantViolation]:
    """Scan all explanation_basis and flags for forbidden terms."""
    violations = []
    for s in pkg.stress_context:
        for text in s.explanation_basis:
            text_lower = text.lower()
            for term in FORBIDDEN_L2_VOCABULARY:
                if term in text_lower:
                    violations.append(InvariantViolation(
                        "no_prescription_vocabulary", "error",
                        f"Stress {s.stress_id} explanation contains forbidden term '{term}': \"{text}\"",
                    ))
    return violations


# ── 8. Diagnostic-only no strong conclusion ─────────────────────────────────

def _check_diagnostic_only_severity(pkg: Layer2Output) -> List[InvariantViolation]:
    """Diagnostic-only stress must not have severity > 0.5."""
    violations = []
    for s in pkg.stress_context:
        if s.diagnostic_only and s.severity > 0.5:
            old = s.severity
            s.severity = 0.5
            violations.append(InvariantViolation(
                "diagnostic_only_severity_cap", "warning",
                f"Stress {s.stress_id} diagnostic_only but severity {old:.3f} → capped to 0.5",
                auto_fixed=True,
            ))
    return violations


# ── 9. Run ID present ──────────────────────────────────────────────────────

def _check_run_id(pkg: Layer2Output) -> List[InvariantViolation]:
    violations = []
    if not pkg.run_id:
        violations.append(InvariantViolation(
            "run_id_present", "error", "Missing run_id",
        ))
    if not pkg.layer1_run_id:
        violations.append(InvariantViolation(
            "layer1_run_id_present", "warning", "Missing layer1_run_id",
        ))
    return violations


# ── 10. Provenance complete ────────────────────────────────────────────────

def _check_provenance_complete(pkg: Layer2Output) -> List[InvariantViolation]:
    violations = []
    prov = pkg.provenance
    if not prov.run_id:
        violations.append(InvariantViolation(
            "provenance_run_id", "warning", "Provenance missing run_id",
        ))
    if not prov.layer1_run_id:
        violations.append(InvariantViolation(
            "provenance_layer1_ref", "warning", "Provenance missing layer1_run_id",
        ))
    if prov.generated_at is None:
        violations.append(InvariantViolation(
            "provenance_timestamp", "warning", "Provenance missing generated_at",
        ))
    return violations
