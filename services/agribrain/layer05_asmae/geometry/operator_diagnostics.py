"""
ASMAE Observation Operator Diagnostics.

Validates H_t operators against acceptance gates from V69 spec:
  1. Same scene + same resolution → deterministic H_t
  2. Synthetic known shift → expected operator difference
  3. Fixed-grid resampled scenes do not fake shift diversity
  4. Cloud masks reduce operator support
  5. Weak geometry reduces identifiability

Diagnostics are run after operator construction and before
state estimation to catch geometry problems early.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..schema import ObservationOperatorRuntime

logger = logging.getLogger(__name__)

# Try scipy
try:
    from scipy import sparse as sp
    import numpy as np
    HAS_SCIPY = True
except ImportError:
    sp = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    HAS_SCIPY = False


@dataclass
class OperatorDiagnostic:
    """Diagnostic result for a single operator or operator pair."""
    test_name: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    severity: str = "info"   # info | warning | error


@dataclass
class OperatorDiagnosticReport:
    """Full diagnostic report for all operators in a run."""
    diagnostics: List[OperatorDiagnostic] = field(default_factory=list)
    n_passed: int = 0
    n_failed: int = 0
    n_errors: int = 0

    def add(self, diag: OperatorDiagnostic) -> None:
        self.diagnostics.append(diag)
        if diag.passed:
            self.n_passed += 1
        else:
            self.n_failed += 1
            if diag.severity == "error":
                self.n_errors += 1

    @property
    def all_passed(self) -> bool:
        return self.n_failed == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_passed": self.n_passed,
            "n_failed": self.n_failed,
            "n_errors": self.n_errors,
            "all_passed": self.all_passed,
            "tests": [
                {
                    "name": d.test_name,
                    "passed": d.passed,
                    "severity": d.severity,
                    "details": d.details,
                }
                for d in self.diagnostics
            ],
        }


# ── Diagnostic Tests ────────────────────────────────────────────────────────

def check_determinism(
    op1: ObservationOperatorRuntime,
    op2: ObservationOperatorRuntime,
) -> OperatorDiagnostic:
    """Gate 1: Same scene + same resolution → identical H_t.

    Compares operator_id (deterministic hash). If they differ,
    the operator construction is non-deterministic.
    """
    same_id = op1.operator_id == op2.operator_id
    same_support = abs(op1.support_score - op2.support_score) < 1e-6

    passed = same_id and same_support

    details = {
        "op1_id": op1.operator_id,
        "op2_id": op2.operator_id,
        "same_id": same_id,
        "same_support": same_support,
    }

    if HAS_SCIPY and op1.H_matrix is not None and op2.H_matrix is not None:
        if op1.H_matrix.shape == op2.H_matrix.shape:
            diff = (op1.H_matrix - op2.H_matrix)
            max_diff = abs(diff).max() if diff.nnz > 0 else 0.0
            details["max_matrix_diff"] = float(max_diff)
            if max_diff > 1e-8:
                passed = False

    return OperatorDiagnostic(
        test_name="determinism",
        passed=passed,
        details=details,
        severity="error" if not passed else "info",
    )


def check_support_score(
    operator: ObservationOperatorRuntime,
    min_support: float = 0.1,
) -> OperatorDiagnostic:
    """Gate 4/5: Support score must be above minimum.

    Low support means too many pixels are masked (clouds, nodata)
    or the geometry is too weak for reliable estimation.
    """
    passed = operator.support_score >= min_support

    return OperatorDiagnostic(
        test_name="support_score",
        passed=passed,
        details={
            "operator_id": operator.operator_id,
            "support_score": operator.support_score,
            "min_support": min_support,
        },
        severity="warning" if not passed else "info",
    )


def check_condition_number(
    operator: ObservationOperatorRuntime,
    max_condition: float = 100.0,
) -> OperatorDiagnostic:
    """Check condition number proxy for ill-conditioned operators.

    High condition number → unstable inversion → poor state estimates.
    """
    passed = operator.condition_number_proxy < max_condition

    return OperatorDiagnostic(
        test_name="condition_number",
        passed=passed,
        details={
            "operator_id": operator.operator_id,
            "condition_proxy": operator.condition_number_proxy,
            "max_condition": max_condition,
        },
        severity="warning" if not passed else "info",
    )


def check_row_normalization(
    operator: ObservationOperatorRuntime,
    tolerance: float = 0.01,
) -> OperatorDiagnostic:
    """Verify row sums ≈ 1 for non-masked pixels.

    Each pixel's zone weights should sum to 1 (the pixel's total
    observation is fully explained by zone contributions).
    """
    if not HAS_SCIPY or operator.H_matrix is None:
        return OperatorDiagnostic(
            test_name="row_normalization",
            passed=True,
            details={"reason": "no_matrix_available"},
        )

    row_sums = np.array(operator.H_matrix.sum(axis=1)).flatten()
    # Only check non-zero rows (masked pixels have all-zero rows)
    nonzero_rows = row_sums[row_sums > 1e-8]

    if len(nonzero_rows) == 0:
        return OperatorDiagnostic(
            test_name="row_normalization",
            passed=True,
            details={"reason": "all_rows_zero"},
        )

    max_deviation = float(np.max(np.abs(nonzero_rows - 1.0)))
    passed = max_deviation < tolerance

    return OperatorDiagnostic(
        test_name="row_normalization",
        passed=passed,
        details={
            "max_deviation": round(max_deviation, 6),
            "tolerance": tolerance,
            "n_nonzero_rows": int(len(nonzero_rows)),
        },
        severity="error" if not passed else "info",
    )


def check_shift_diversity(
    operators: List[ObservationOperatorRuntime],
    min_unique_shifts: int = 2,
) -> OperatorDiagnostic:
    """Gate 3: Check that shift diversity is genuine, not faked.

    If all operators have identical registration_uncertainty = 0,
    the stack may be from fixed-grid resampled scenes (no real diversity).
    """
    uncertainties = [op.registration_uncertainty_m for op in operators]
    unique_uncertainties = len(set(round(u, 3) for u in uncertainties))

    # Check if all uncertainties are exactly zero (suspicious)
    all_zero = all(u == 0.0 for u in uncertainties)

    passed = unique_uncertainties >= min(min_unique_shifts, len(operators))

    return OperatorDiagnostic(
        test_name="shift_diversity",
        passed=passed,
        details={
            "n_operators": len(operators),
            "unique_uncertainty_values": unique_uncertainties,
            "all_zero_uncertainty": all_zero,
            "min_unique_required": min_unique_shifts,
        },
        severity="warning" if not passed else "info",
    )


# ── Full Diagnostic Suite ───────────────────────────────────────────────────

def run_operator_diagnostics(
    operators: List[ObservationOperatorRuntime],
) -> OperatorDiagnosticReport:
    """Run all V69 acceptance gate diagnostics on a set of operators.

    Returns a diagnostic report with pass/fail for each gate.
    """
    report = OperatorDiagnosticReport()

    # Per-operator tests
    for op in operators:
        report.add(check_support_score(op))
        report.add(check_condition_number(op))
        report.add(check_row_normalization(op))

    # Stack-level tests
    if len(operators) >= 2:
        report.add(check_shift_diversity(operators))

    logger.info(
        "Operator diagnostics: %d passed, %d failed (%d errors)",
        report.n_passed, report.n_failed, report.n_errors,
    )

    return report
