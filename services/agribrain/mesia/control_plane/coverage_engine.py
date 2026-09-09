"""MESIA Multi-Dimensional Coverage Engine — R6 §3.2 & §2.4.

Computes multi-dimensional coverage across frequency, instantaneous bandwidth,
spatial position, polarisation, and decoders.  Detects blind bands and gaps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.receiver import ReceiverCapabilityManifest, AntennaPathManifest
from ..contracts.coverage import CoverageTuple, CoverageGraph
from ..ontology.coverage_outcomes import CoverageOutcome


class CoverageEngine:
    """Evaluates coverage capabilities across receiver and antenna paths."""

    @staticmethod
    def resolve_coverage_tuple(
        receiver: ReceiverCapabilityManifest,
        antenna: AntennaPathManifest,
        jurisdiction_policy_ref: str = "",
    ) -> CoverageTuple:
        """Resolve a specific receiver + antenna path into a CoverageTuple."""
        outcome = CoverageOutcome.OBSERVABLE.value if receiver.health_status == "HEALTHY" else CoverageOutcome.UNAVAILABLE.value
        gap_reason = "" if outcome == CoverageOutcome.OBSERVABLE.value else f"Receiver health={receiver.health_status}"

        return CoverageTuple(
            path_id=antenna.path_id,
            receiver_id=receiver.receiver_id,
            frequency_range_hz=receiver.tuning_range_hz,
            instantaneous_bandwidth_hz=receiver.instantaneous_bandwidth_hz,
            scan_dwell_duty_cycle_pct=receiver.scan_duty_cycle_pct,
            sensitivity_dbm=receiver.sensitivity_dbm,
            dynamic_range_db=receiver.dynamic_range_db,
            antenna_polarisation=antenna.polarisation,
            antenna_beam_description=f"Antenna: {antenna.antenna_model}, loss={antenna.insertion_loss_db}dB",
            supported_sample_formats=[receiver.sample_format],
            tx_rx_constraints=receiver.duplex_mode,
            legal_permissions=jurisdiction_policy_ref,
            health_status=receiver.health_status,
            waveform_operations=list(receiver.supported_decoders),
            coverage_outcome=outcome,
            gap_reason=gap_reason,
        )

    @classmethod
    def build_coverage_graph(
        cls,
        graph_id: str,
        receivers: List[ReceiverCapabilityManifest],
        antennas_by_id: Dict[str, AntennaPathManifest],
        spectrum_span_hz: Tuple[float, float],
    ) -> CoverageGraph:
        """Build an aggregated CoverageGraph and identify blind frequency bands within spectrum_span_hz."""
        coverage_tuples: List[CoverageTuple] = []

        for rx in receivers:
            for ant_ref in rx.antenna_path_refs:
                ant = antennas_by_id.get(ant_ref)
                if ant:
                    ct = cls.resolve_coverage_tuple(rx, ant)
                    coverage_tuples.append(ct)

        # Detect blind bands within requested span [f_min, f_max]
        f_min, f_max = spectrum_span_hz
        covered_intervals: List[Tuple[float, float]] = []

        for ct in coverage_tuples:
            if ct.coverage_outcome == CoverageOutcome.OBSERVABLE.value and ct.frequency_range_hz:
                c_start = max(f_min, ct.frequency_range_hz[0])
                c_end = min(f_max, ct.frequency_range_hz[1])
                if c_start < c_end:
                    covered_intervals.append((c_start, c_end))

        # Merge covered intervals
        covered_intervals.sort(key=lambda x: x[0])
        merged: List[Tuple[float, float]] = []
        for interval in covered_intervals:
            if not merged:
                merged.append(interval)
            else:
                prev_start, prev_end = merged[-1]
                if interval[0] <= prev_end:
                    merged[-1] = (prev_start, max(prev_end, interval[1]))
                else:
                    merged.append(interval)

        # Find blind bands (gaps in coverage between f_min and f_max)
        blind_bands: List[Tuple[float, float]] = []
        curr = f_min
        for start, end in merged:
            if start > curr:
                blind_bands.append((curr, start))
            curr = max(curr, end)
        if curr < f_max:
            blind_bands.append((curr, f_max))

        gap_summary = (
            f"{len(blind_bands)} blind band(s) detected across {f_min/1e6:.1f}–{f_max/1e6:.1f} MHz span."
            if blind_bands else "Continuous observable coverage across span."
        )

        now = datetime.now(timezone.utc)
        return CoverageGraph(
            graph_id=graph_id,
            created_at=now,
            coverage_tuples=coverage_tuples,
            blind_bands=blind_bands,
            gap_summary=gap_summary,
        )
