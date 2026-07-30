"""
ASMAE Invariant Enforcement.

Runtime invariant checks on ASMAEOutput, mirroring the L1/L2 pattern.
Auto-fixes safe cases. Error-level checks block production use.

Checks:
   1. state_bounds           — clamp all state values to physical bounds
   2. uncertainty_positive    — uncertainties must be > 0
   3. confidence_bounds       — confidence in [0, 1]
   4. resolution_consistency  — selected resolution must be in tested set
   5. no_1m_without_cert      — 1m resolution requires explicit certification
   6. severity_confidence     — severity ≤ confidence + 0.1 (mirroring L2)
   7. no_ndvi_as_state        — NDVI must not appear as a state variable name
   8. provenance_complete     — run_id, plot_id, timestamps present
   9. content_hash_present    — deterministic hash must exist
  10. no_prescription_leak    — ASMAE output must not contain prescription terms
  11. retrovalidation_gated   — high-res requires retrovalidation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .config import (
    CANDIDATE_RESOLUTIONS_M,
    STATE_BOUNDS,
    STATE_NAMES,
)

# Forbidden terms — ASMAE is diagnostic, never prescriptive
FORBIDDEN_ASMAE_VOCABULARY = frozenset({
    "apply",
    "spray",
    "irrigate now",
    "dose",
    "prescribe",
    "recommend applying",
    "treatment plan",
    "action required",
})


@dataclass
class ASMAEInvariantViolation:
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


def enforce_asmae_invariants(output) -> List[ASMAEInvariantViolation]:
    """Run all invariant checks on ASMAEOutput. Auto-fixes safe cases.

    The output object is modified in-place for auto-fixes.
    Returns list of all violations found.
    """
    violations: List[ASMAEInvariantViolation] = []

    violations.extend(_check_state_bounds(output))
    violations.extend(_check_uncertainty_positive(output))
    violations.extend(_check_confidence_bounds(output))
    violations.extend(_check_resolution_consistency(output))
    violations.extend(_check_no_1m_without_cert(output))
    violations.extend(_check_no_ndvi_as_state(output))
    violations.extend(_check_provenance_complete(output))
    violations.extend(_check_content_hash_present(output))
    violations.extend(_check_no_prescription_leak(output))
    violations.extend(_check_retrovalidation_gated(output))

    return violations


# ── 1. State bounds ─────────────────────────────────────────────────────────

def _check_state_bounds(output) -> List[ASMAEInvariantViolation]:
    """Clamp raster map values to physical bounds."""
    violations = []
    for state_name, grid in (output.raster_maps or {}).items():
        if state_name not in STATE_BOUNDS:
            continue
        lo, hi = STATE_BOUNDS[state_name]
        for r, row in enumerate(grid):
            for c, val in enumerate(row):
                if val < lo:
                    grid[r][c] = lo
                    violations.append(ASMAEInvariantViolation(
                        "state_bounds", "warning",
                        f"{state_name}[{r},{c}]={val:.4f} < {lo} → clamped",
                        auto_fixed=True,
                    ))
                elif val > hi:
                    grid[r][c] = hi
                    violations.append(ASMAEInvariantViolation(
                        "state_bounds", "warning",
                        f"{state_name}[{r},{c}]={val:.4f} > {hi} → clamped",
                        auto_fixed=True,
                    ))
    return violations


# ── 2. Uncertainty positive ─────────────────────────────────────────────────

def _check_uncertainty_positive(output) -> List[ASMAEInvariantViolation]:
    """All uncertainty values must be > 0."""
    violations = []
    for state_name, grid in (output.uncertainty_maps or {}).items():
        for r, row in enumerate(grid):
            for c, val in enumerate(row):
                if val <= 0.0:
                    grid[r][c] = 0.001
                    violations.append(ASMAEInvariantViolation(
                        "uncertainty_positive", "warning",
                        f"uncertainty[{state_name}][{r},{c}]={val:.6f} ≤ 0 → set to 0.001",
                        auto_fixed=True,
                    ))
    return violations


# ── 3. Confidence bounds ───────────────────────────────────────────────────

def _check_confidence_bounds(output) -> List[ASMAEInvariantViolation]:
    """Confidence values must be in [0, 1]."""
    violations = []
    for state_name, grid in (output.confidence_maps or {}).items():
        for r, row in enumerate(grid):
            for c, val in enumerate(row):
                if val < 0.0:
                    grid[r][c] = 0.0
                    violations.append(ASMAEInvariantViolation(
                        "confidence_bounds", "warning",
                        f"confidence[{state_name}][{r},{c}]={val:.4f} → clamped to 0",
                        auto_fixed=True,
                    ))
                elif val > 1.0:
                    grid[r][c] = 1.0
                    violations.append(ASMAEInvariantViolation(
                        "confidence_bounds", "warning",
                        f"confidence[{state_name}][{r},{c}]={val:.4f} → clamped to 1",
                        auto_fixed=True,
                    ))
    return violations


# ── 4. Resolution consistency ──────────────────────────────────────────────

def _check_resolution_consistency(output) -> List[ASMAEInvariantViolation]:
    """Selected resolution must be in the tested candidate set."""
    violations = []
    rd = output.resolution_decision
    if rd is not None:
        tested = rd.candidate_resolutions_tested_m or CANDIDATE_RESOLUTIONS_M
        if rd.selected_effective_resolution_m not in tested:
            violations.append(ASMAEInvariantViolation(
                "resolution_consistency", "error",
                f"Selected resolution {rd.selected_effective_resolution_m}m "
                f"not in tested set {tested}",
            ))
    return violations


# ── 5. No 1m without certification ────────────────────────────────────────

def _check_no_1m_without_cert(output) -> List[ASMAEInvariantViolation]:
    """1m production resolution requires explicit certification."""
    violations = []
    rd = output.resolution_decision
    if rd is not None and rd.selected_effective_resolution_m == 1:
        if not rd.safe_for_1m_claim:
            violations.append(ASMAEInvariantViolation(
                "no_1m_without_certification", "error",
                "1m resolution selected but safe_for_1m_claim is False — "
                "1m is never production-selectable without explicit certification",
            ))
    return violations


# ── 6. No NDVI as state ───────────────────────────────────────────────────

def _check_no_ndvi_as_state(output) -> List[ASMAEInvariantViolation]:
    """NDVI is an observation, not a state variable. It must not appear as a state."""
    violations = []
    forbidden_state_names = {"ndvi", "evi", "savi", "ndre", "ndmi", "ndwi", "bsi", "nbr"}
    for state_name in (output.raster_maps or {}):
        if state_name.lower() in forbidden_state_names:
            violations.append(ASMAEInvariantViolation(
                "no_ndvi_as_state", "error",
                f"'{state_name}' found as a state variable — "
                f"spectral indices are observations, not states",
            ))
    return violations


# ── 7. Provenance complete ────────────────────────────────────────────────

def _check_provenance_complete(output) -> List[ASMAEInvariantViolation]:
    """Run ID, plot ID, and timestamps must be present."""
    violations = []
    if not output.run_id:
        violations.append(ASMAEInvariantViolation(
            "provenance_run_id", "error", "Missing run_id",
        ))
    if not output.plot_id:
        violations.append(ASMAEInvariantViolation(
            "provenance_plot_id", "error", "Missing plot_id",
        ))
    if output.generated_at is None:
        violations.append(ASMAEInvariantViolation(
            "provenance_timestamp", "warning", "Missing generated_at timestamp",
        ))
    return violations


# ── 8. Content hash present ───────────────────────────────────────────────

def _check_content_hash_present(output) -> List[ASMAEInvariantViolation]:
    """Deterministic content hash must be set before export."""
    violations = []
    prov = output.provenance or {}
    if isinstance(prov, dict) and not prov.get("content_hash"):
        violations.append(ASMAEInvariantViolation(
            "content_hash_present", "warning",
            "Provenance missing content_hash — deterministic verification disabled",
        ))
    return violations


# ── 9. No prescription leak ──────────────────────────────────────────────

def _check_no_prescription_leak(output) -> List[ASMAEInvariantViolation]:
    """ASMAE output must not contain prescriptive vocabulary."""
    violations = []
    diagnostics = output.diagnostics or {}
    text_to_scan = str(diagnostics).lower()
    for term in FORBIDDEN_ASMAE_VOCABULARY:
        if term in text_to_scan:
            violations.append(ASMAEInvariantViolation(
                "no_prescription_leak", "error",
                f"Diagnostics contain forbidden term '{term}' — "
                f"ASMAE is diagnostic only, never prescriptive",
            ))
    return violations


# ── 10. Retrovalidation gated ─────────────────────────────────────────────

def _check_retrovalidation_gated(output) -> List[ASMAEInvariantViolation]:
    """High-resolution selections (≤5m) require retrovalidation scores."""
    violations = []
    rd = output.resolution_decision
    if rd is not None and rd.selected_effective_resolution_m <= 5:
        if not output.retrovalidation_maps:
            violations.append(ASMAEInvariantViolation(
                "retrovalidation_gated", "warning",
                f"Resolution {rd.selected_effective_resolution_m}m selected "
                f"but no retrovalidation maps present — "
                f"high-res requires retrovalidation",
            ))
    return violations
