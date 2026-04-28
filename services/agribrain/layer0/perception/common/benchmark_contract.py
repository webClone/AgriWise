"""
Benchmark Gate Contract — single source of truth.

Every engine benchmark runner MUST return a BenchmarkGateResult.
The printed scorecard, saved JSON, and exit code are ALL derived from it.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MetricVerdict:
    """Result for a single aggregate metric."""
    name: str
    value: float
    threshold: float
    higher_is_better: bool
    passed: bool


@dataclass
class CaseVerdict:
    """Result for a single benchmark case."""
    case_id: str
    passed: bool
    is_critical: bool
    is_soft_fail: bool
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkGateResult:
    """Canonical benchmark result. One object rules all output."""
    engine: str
    aggregate_failures: int = 0
    critical_failures: int = 0
    soft_failures: int = 0
    gate_passed: bool = False
    failing_metrics: List[str] = field(default_factory=list)
    failing_cases: List[str] = field(default_factory=list)
    scorecard: Dict[str, Any] = field(default_factory=dict)
    case_results: List[Dict[str, Any]] = field(default_factory=list)


def compute_gate_pass(result: BenchmarkGateResult) -> bool:
    """Compute gate_passed strictly from failure counts."""
    return result.aggregate_failures == 0 and result.critical_failures == 0


def finalize(result: BenchmarkGateResult) -> BenchmarkGateResult:
    """Recompute gate_passed to ensure consistency."""
    result.gate_passed = compute_gate_pass(result)
    return result


def result_to_dict(result: BenchmarkGateResult) -> dict:
    """Convert to JSON-serializable dict."""
    return {
        "engine": result.engine,
        "aggregate_failures": result.aggregate_failures,
        "critical_failures": result.critical_failures,
        "soft_failures": result.soft_failures,
        "gate_passed": result.gate_passed,
        "failing_metrics": result.failing_metrics,
        "failing_cases": result.failing_cases,
        "scorecard": result.scorecard,
        "case_results": result.case_results,
    }


REQUIRED_KEYS = [
    "engine", "aggregate_failures", "critical_failures",
    "soft_failures", "gate_passed", "failing_metrics", "failing_cases",
]


def validate_schema(data: dict) -> List[str]:
    """Validate that a gate result dict has all required fields.
    Returns list of errors (empty if valid)."""
    errors = []
    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"Missing required field: {key}")
    if "gate_passed" in data:
        agg = data.get("aggregate_failures", 0)
        crit = data.get("critical_failures", 0)
        expected = (agg == 0 and crit == 0)
        if data["gate_passed"] != expected:
            errors.append(
                f"gate_passed={data['gate_passed']} contradicts "
                f"aggregate_failures={agg}, critical_failures={crit}"
            )
    # Validate case categories: critical + soft_fail is forbidden
    for case in data.get("case_results", []):
        if case.get("critical") and case.get("soft_fail"):
            errors.append(
                f"Case '{case.get('case_id', '?')}' is both critical=True "
                f"and soft_fail=True — this combination is forbidden"
            )
    return errors


def validate_case_metadata(case_id: str, critical: bool, soft_fail: bool) -> None:
    """Enforce that a case cannot be both critical and soft-fail.

    Call this at benchmark case registration or runner startup.
    Raises ValueError if the combination is invalid.
    """
    if critical and soft_fail:
        raise ValueError(
            f"Case '{case_id}' is marked critical_case=True AND "
            f"allowed_soft_fail=True. A case cannot be both. "
            f"Choose: hard-critical (blocks gate) OR soft-informational (visible but non-blocking)."
        )


def exit_code_from_result(result: BenchmarkGateResult) -> int:
    """Return 0 if gate passed, 1 otherwise."""
    return 0 if result.gate_passed else 1


def summarize_failures(result: BenchmarkGateResult) -> str:
    """Human-readable failure summary."""
    if result.gate_passed:
        return f"[+] GATE PASSED: {result.engine} -- all metrics and cases green."
    parts = []
    if result.aggregate_failures > 0:
        parts.append(f"{result.aggregate_failures} aggregate metric failure(s): {result.failing_metrics}")
    if result.critical_failures > 0:
        parts.append(f"{result.critical_failures} critical case failure(s): {result.failing_cases}")
    if result.soft_failures > 0:
        parts.append(f"{result.soft_failures} soft failure(s) (non-blocking)")
    return f"[!] GATE FAILED: {result.engine} -- " + "; ".join(parts)
