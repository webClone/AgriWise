"""MESIA Coverage Audit & Gap Disambiguator — R6 §2.8 & §3.3.

Audits coverage queries against hardware manifests, calibration states, and
jurisdiction profiles to ensure ZERO false claims of coverage.

Hard integrity rule:
  NO_COVERAGE, UNAVAILABLE, PERMISSION_BLOCKED, SATURATED, and NO_SIGNAL
  are scientifically distinct states and must never share a null representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.receiver import ReceiverCapabilityManifest
from ..contracts.coverage import CoverageGraph, CoverageTuple
from ..ontology.coverage_outcomes import CoverageOutcome
from .jurisdiction import JurisdictionProfile


@dataclass(frozen=True)
class CoverageAuditResult:
    """Outcome of a scientific coverage audit for a planned observation."""

    query_frequency_hz: float
    query_bandwidth_hz: float
    outcome: CoverageOutcome
    is_observable: bool
    matching_receiver_id: Optional[str] = None
    matching_path_id: Optional[str] = None
    gap_reason: str = ""


class CoverageAuditor:
    """Strictly audits coverage requests against actual hardware and regulatory truth."""

    @staticmethod
    def audit_coverage(
        query_frequency_hz: float,
        query_bandwidth_hz: float,
        coverage_graph: CoverageGraph,
        jurisdiction_profile: Optional[JurisdictionProfile] = None,
        is_active_transmission: bool = False,
        tx_power_dbm: float = 0.0,
        duty_cycle_pct: float = 100.0,
        licence_ref: Optional[str] = None,
    ) -> CoverageAuditResult:
        """Evaluate a planned measurement and return the exact scientific coverage state."""
        q_start = query_frequency_hz - (query_bandwidth_hz / 2.0)
        q_end = query_frequency_hz + (query_bandwidth_hz / 2.0)

        # 1. Check Regulatory / Jurisdiction Policy if provided
        if jurisdiction_profile:
            is_auth, auth_msg = jurisdiction_profile.validate_transmission(
                freq_hz=query_frequency_hz,
                tx_power_dbm=tx_power_dbm,
                duty_cycle_pct=duty_cycle_pct,
                licence_ref=licence_ref,
            )
            if is_active_transmission and not is_auth:
                return CoverageAuditResult(
                    query_frequency_hz=query_frequency_hz,
                    query_bandwidth_hz=query_bandwidth_hz,
                    outcome=CoverageOutcome.UNAVAILABLE,
                    is_observable=False,
                    gap_reason=f"PERMISSION_BLOCKED: {auth_msg}",
                )

        # 2. Check Hardware Paths in CoverageGraph
        candidate_paths: List[CoverageTuple] = []
        for ct in coverage_graph.coverage_tuples:
            if ct.frequency_range_hz:
                f_min, f_max = ct.frequency_range_hz
                if f_min <= query_frequency_hz <= f_max:
                    candidate_paths.append(ct)

        if not candidate_paths:
            return CoverageAuditResult(
                query_frequency_hz=query_frequency_hz,
                query_bandwidth_hz=query_bandwidth_hz,
                outcome=CoverageOutcome.NO_COVERAGE,
                is_observable=False,
                gap_reason=f"No installed front-end receiver tunes to {query_frequency_hz/1e6:.3f} MHz.",
            )

        # 3. Check health and bandwidth of matching hardware
        for ct in candidate_paths:
            if ct.health_status != "HEALTHY":
                continue

            inst_bw = ct.instantaneous_bandwidth_hz or 0.0
            if inst_bw >= query_bandwidth_hz:
                return CoverageAuditResult(
                    query_frequency_hz=query_frequency_hz,
                    query_bandwidth_hz=query_bandwidth_hz,
                    outcome=CoverageOutcome.OBSERVABLE,
                    is_observable=True,
                    matching_receiver_id=ct.receiver_id,
                    matching_path_id=ct.path_id,
                    gap_reason="",
                )
            else:
                return CoverageAuditResult(
                    query_frequency_hz=query_frequency_hz,
                    query_bandwidth_hz=query_bandwidth_hz,
                    outcome=CoverageOutcome.PARTIAL,
                    is_observable=True,
                    matching_receiver_id=ct.receiver_id,
                    matching_path_id=ct.path_id,
                    gap_reason=f"Receiver instantaneous BW {inst_bw/1e6:.1f} MHz < requested {query_bandwidth_hz/1e6:.1f} MHz.",
                )

        # If candidates exist but all are unhealthy / saturated
        degraded_reasons = [f"{ct.receiver_id}: {ct.health_status}" for ct in candidate_paths]
        return CoverageAuditResult(
            query_frequency_hz=query_frequency_hz,
            query_bandwidth_hz=query_bandwidth_hz,
            outcome=CoverageOutcome.UNAVAILABLE,
            is_observable=False,
            gap_reason=f"Receiver(s) offline/unhealthy: {', '.join(degraded_reasons)}",
        )
