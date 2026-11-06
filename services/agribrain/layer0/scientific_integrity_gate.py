"""L0-C1: Fail-closed state-export integrity boundary.

The canonical Layer0StateEngine calls this gate before returning a scientific
state package. An invariant failure raises instead of permitting Layer 1 to
consume a plausible but invalid posterior. This checks exported numerical
and timeline integrity; it is not independent field calibration or a PSD
proof for the complete Kalman covariance matrix.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Mapping, Sequence

from services.agribrain.layer0.production_admission import (
    Layer0AdmissionRequiredError,
)


class Layer0ScientificIntegrityError(Layer0AdmissionRequiredError):
    """A state estimate failed a mandatory integrity check.

    The public exception code is stable; failure details are retained for
    server-side logging, not as an authorization or publication receipt.
    """

    def __init__(self, code: str, details: Sequence[str] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.details = tuple(details)


def _valid_numeric_export(
    records: Mapping[str, Any],
    *,
    nonnegative: bool,
    name: str,
) -> None:
    if not isinstance(records, Mapping) or not records:
        raise Layer0ScientificIntegrityError("layer0_empty_" + name)
    for zone, entries in records.items():
        if not isinstance(zone, str) or not zone:
            raise Layer0ScientificIntegrityError("layer0_invalid_zone")
        if not isinstance(entries, list) or not entries:
            raise Layer0ScientificIntegrityError("layer0_empty_" + name)
        for entry in entries:
            if not isinstance(entry, Mapping) or not isinstance(entry.get("day"), str):
                raise Layer0ScientificIntegrityError("layer0_invalid_" + name + "_day")
            for field, value in entry.items():
                if field == "day":
                    continue
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise Layer0ScientificIntegrityError("layer0_nonnumeric_" + name)
                if not math.isfinite(value):
                    raise Layer0ScientificIntegrityError("layer0_nonfinite_" + name)
                if nonnegative and value < 0:
                    raise Layer0ScientificIntegrityError("layer0_negative_uncertainty")


def assert_layer0_scientific_integrity(
    *,
    daily_state: Mapping[str, Any],
    state_uncertainty: Mapping[str, Any],
    provenance_log: Sequence[Mapping[str, Any]],
    source_reliability: Mapping[str, float],
    enforce_invariants: Callable[..., Any],
) -> list[dict[str, Any]]:
    """Run the native enforcer without auto-clamping or repairing evidence."""
    _valid_numeric_export(daily_state, nonnegative=False, name="state")
    _valid_numeric_export(
        state_uncertainty, nonnegative=True, name="uncertainty",
    )
    if set(daily_state) != set(state_uncertainty):
        raise Layer0ScientificIntegrityError("layer0_zone_uncertainty_mismatch")
    for zone in daily_state:
        sdays = [record["day"] for record in daily_state[zone]]
        udays = [record["day"] for record in state_uncertainty[zone]]
        if sdays != udays:
            raise Layer0ScientificIntegrityError("layer0_uncertainty_day_mismatch")
    if not isinstance(provenance_log, (list, tuple)) or not provenance_log:
        raise Layer0ScientificIntegrityError("layer0_missing_daily_provenance")
    time_index = []
    for record in provenance_log:
        if not isinstance(record, Mapping) or not isinstance(record.get("day"), str):
            raise Layer0ScientificIntegrityError("layer0_invalid_provenance_time")
        time_index.append(record["day"])
    if len(time_index) != len(set(time_index)):
        raise Layer0ScientificIntegrityError("layer0_duplicate_provenance_day")
    if not callable(enforce_invariants):
        raise Layer0ScientificIntegrityError("layer0_invariant_checker_missing")

    try:
        violations = enforce_invariants(
            daily_state, state_uncertainty,
            provenance_log, time_index, source_reliability,
            auto_fix=False,
        )
    except Layer0ScientificIntegrityError:
        raise
    except Exception as exc:
        raise Layer0ScientificIntegrityError("layer0_invariant_checker_failed") from exc

    if not isinstance(violations, list):
        raise Layer0ScientificIntegrityError("layer0_invariant_result_invalid")
    decisions = []
    for violation in violations:
        if not hasattr(violation, "to_dict") or not callable(violation.to_dict):
            raise Layer0ScientificIntegrityError("layer0_invariant_result_invalid")
        decision = violation.to_dict()
        if not isinstance(decision, dict) or decision.get("severity") not in (
            "error", "warning", "fixed",
        ):
            raise Layer0ScientificIntegrityError("layer0_invariant_result_invalid")
        decisions.append(decision)
    blocked = [
        f'{v.get("invariant")}:{v.get("location")}'
        for v in decisions
        if v.get("severity") in ("error", "fixed")
        or v.get("invariant") == "date_alignment"
    ]
    if blocked:
        raise Layer0ScientificIntegrityError(
            "layer0_scientific_invariant_violation", blocked,
        )
    return decisions


def assert_structural_audit_passed(report: Any) -> None:
    """Refuse a missing/failed structural audit before state handoff.

    Trust-report grades and nonstructural warnings remain diagnostic rather
    than being treated as physical calibration or as hard aborts.
    """
    if not isinstance(report, dict):
        raise Layer0ScientificIntegrityError("layer0_structural_audit_missing")
    structural = report.get("structural_audit")
    if not isinstance(structural, dict):
        raise Layer0ScientificIntegrityError("layer0_structural_audit_missing")
    if (
        structural.get("status") != "PASS"
        or type(structural.get("checks_failed")) is not int
        or structural["checks_failed"] != 0
        or type(structural.get("checks_run")) is not int
        or structural["checks_run"] == 0
    ):
        raise Layer0ScientificIntegrityError(
            "layer0_structural_audit_failed",
        )
