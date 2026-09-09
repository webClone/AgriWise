"""MESIA Coverage Outcomes — R6 §3.3.

Five scientifically distinct coverage states.  They must NEVER share a
null value.

  OBSERVABLE  — Planned measurement is inside capability/calibration/
                antenna/time/policy limits.
  PARTIAL     — Only part of bandwidth/time/geometry/beams/metadata is
                observable; missing support is explicit.
  NO_COVERAGE — No current front end can observe the signal with the
                required conditions.
  UNAVAILABLE — A normally supported path is offline, permission-blocked,
                saturated, or not exposed.
  NO_SIGNAL   — Calibrated coverage existed and no emission was detected
                above the declared limit.

Hard integrity rule:
  NO_COVERAGE, UNAVAILABLE, and NO_SIGNAL are scientifically different
  states and must never share a null value.
"""

from __future__ import annotations

from enum import Enum


class CoverageOutcome(str, Enum):
    """Coverage outcome for a receiver path — R6 §3.3."""

    OBSERVABLE = "OBSERVABLE"
    PARTIAL = "PARTIAL"
    NO_COVERAGE = "NO_COVERAGE"
    UNAVAILABLE = "UNAVAILABLE"
    NO_SIGNAL = "NO_SIGNAL"


# Hard integrity: all five are distinct non-null string values.
_values = {m.value for m in CoverageOutcome}
assert len(_values) == 5, "Coverage outcomes must be 5 distinct values"
assert "" not in _values, "Coverage outcomes must not contain empty strings"
assert None not in _values, "Coverage outcomes must not contain None"  # type: ignore[comparison-overlap]


# Semantic groups for programmatic use
OBSERVATION_POSSIBLE = frozenset({
    CoverageOutcome.OBSERVABLE,
    CoverageOutcome.PARTIAL,
})

NO_OBSERVATION_POSSIBLE = frozenset({
    CoverageOutcome.NO_COVERAGE,
    CoverageOutcome.UNAVAILABLE,
})

# NO_SIGNAL is intentionally in neither group — it means coverage existed
# but nothing was detected.  It is a valid scientific measurement result,
# distinct from "we cannot observe."
CALIBRATED_ABSENCE = frozenset({
    CoverageOutcome.NO_SIGNAL,
})
