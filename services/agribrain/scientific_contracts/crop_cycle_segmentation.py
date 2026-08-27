"""Ledger-bound, sensor-aware crop-cycle segmentation diagnostics.

The segmenter is deliberately not a production crop-cycle classifier. It
keeps every plausible current-cycle hypothesis in the signed receipt and
uses only the optical trajectory when proposing NDVI boundaries. Other
sensor observations are aligned to a hypothesis by acquisition time; they
never become neighbours in the optical NDVI adjacency graph.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.scientific_contracts.crop_evidence import CropEvidenceLedgerV2
from services.agribrain.scientific_contracts.crop_model_input import (
    CropModelObservationTokenV1,
    normalize_verified_crop_evidence_ledger,
    observation_tokens_from_ledger,
)


CROP_CYCLE_SEGMENTATION_VERSION = "crop-cycle-segmentation-v2"
_OPTICAL_FAMILIES = {"sentinel2", "s2", "optical", "landsat", "planet"}
_SAR_FAMILIES = {"sentinel1", "s1", "sar", "radar"}


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _family(value: Any) -> str:
    return str(value or "unknown").strip().lower().replace("-", "_")


def _ndvi(token: CropModelObservationTokenV1) -> Optional[float]:
    candidates = [
        (statistic, float(value))
        for name, statistic, value in token.feature_values
        if name.lower() in {"ndvi", "ndvi_clean"}
    ]
    if not candidates:
        return None
    priority = {"mean": 0, "p50": 1, "median": 2, "value": 3}
    return min(candidates, key=lambda row: priority.get(row[0].lower(), 99))[1]


def _phase(value: Mapping[str, Any]) -> Optional[str]:
    coverage = value.get("time_coverage")
    coverage = dict(coverage) if isinstance(coverage, Mapping) else {}
    phase = str(coverage.get("season_phase") or "").strip().lower()
    return phase if phase in {"early", "mid", "late"} else None


def _domain(values: Iterable[Any]) -> str:
    normalized = {
        str(value or "unverified").strip().lower() for value in values
    }
    if "incompatible" in normalized:
        return "incompatible"
    if normalized == {"compatible"}:
        return "compatible"
    return "unverified"


@dataclass(frozen=True)
class CropCycleBoundaryCandidateV1:
    candidate_id: str
    boundary_time: str
    sensor_family: str
    preceding_observation_id: str
    following_observation_id: str
    reasons: Tuple[str, ...]
    diagnostic_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "boundary_time": self.boundary_time,
            "sensor_family": self.sensor_family,
            "preceding_observation_id": self.preceding_observation_id,
            "following_observation_id": self.following_observation_id,
            "reasons": list(self.reasons),
            "diagnostic_score": self.diagnostic_score,
            "calibrated": False,
        }


@dataclass(frozen=True)
class CropCycleHypothesisV1:
    hypothesis_id: str
    start_time: str
    end_time: str
    observation_ids: Tuple[str, ...]
    physical_acquisition_keys: Tuple[str, ...]
    boundary_candidate_id: Optional[str]
    probability: float
    basis: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "observation_ids": list(self.observation_ids),
            "physical_acquisition_keys": list(self.physical_acquisition_keys),
            "boundary_candidate_id": self.boundary_candidate_id,
            "probability": self.probability,
            "basis": self.basis,
            "probability_calibrated": False,
        }


@dataclass(frozen=True)
class SegmentScopedCropEvidenceReadinessV1:
    hypothesis_id: str
    observation_ids: Tuple[str, ...]
    physical_acquisition_count: int
    sensor_counts: Tuple[Tuple[str, int], ...]
    feature_families: Tuple[str, ...]
    phase_coverage: Tuple[str, ...]
    temporal_start: Optional[str]
    temporal_end: Optional[str]
    temporal_span_days: Optional[float]
    gdd_spans: Tuple[Tuple[str, float, float, float, int], ...]
    calibration_domain_compatibility: str
    geographical_domain_compatibility: str
    red_edge_observation_count: int
    ndvi_observation_count: int
    readiness_status: str
    blockers: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        sensor_counts = dict(self.sensor_counts)
        return {
            "hypothesis_id": self.hypothesis_id,
            "observation_ids": list(self.observation_ids),
            "physical_acquisition_count": self.physical_acquisition_count,
            "sensor_counts": sensor_counts,
            "sensor_availability": {
                "optical": any(sensor_counts.get(name, 0) > 0 for name in _OPTICAL_FAMILIES),
                "sar": any(sensor_counts.get(name, 0) > 0 for name in _SAR_FAMILIES),
                "field": any(
                    name not in _OPTICAL_FAMILIES | _SAR_FAMILIES and count > 0
                    for name, count in sensor_counts.items()
                ),
            },
            "feature_families": list(self.feature_families),
            "phase_coverage": list(self.phase_coverage),
            "temporal_span": {
                "start": self.temporal_start,
                "end": self.temporal_end,
                "span_days": self.temporal_span_days,
            },
            "gdd_spans": {
                name: {"min": minimum, "max": maximum, "span": span, "count": count}
                for name, minimum, maximum, span, count in self.gdd_spans
            },
            "domain_compatibility": {
                "calibration": self.calibration_domain_compatibility,
                "geographical": self.geographical_domain_compatibility,
            },
            "red_edge_observation_count": self.red_edge_observation_count,
            "ndvi_observation_count": self.ndvi_observation_count,
            "readiness_status": self.readiness_status,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class CropCycleSegmentV1:
    """Compatibility partition; hypotheses below remain authoritative."""

    segment_id: str
    start_time: str
    end_time: str
    observation_ids: Tuple[str, ...]
    physical_acquisition_keys: Tuple[str, ...]
    boundary_reason: str
    current_cycle_probability: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "observation_ids": list(self.observation_ids),
            "physical_acquisition_keys": list(self.physical_acquisition_keys),
            "boundary_reason": self.boundary_reason,
            "current_cycle_probability": self.current_cycle_probability,
        }


@dataclass(frozen=True)
class CropCycleSegmentationReceiptV1:
    plot_namespace: PlotNamespace
    crop_evidence_ledger_hash: str
    segments: Tuple[CropCycleSegmentV1, ...]
    current_segment_id: str
    status: str
    method: str
    calibrated: bool
    boundary_candidates: Tuple[CropCycleBoundaryCandidateV1, ...] = ()
    current_cycle_hypotheses: Tuple[CropCycleHypothesisV1, ...] = ()
    primary_hypothesis_id: str = ""
    hypothesis_readiness: Tuple[SegmentScopedCropEvidenceReadinessV1, ...] = ()
    contract_version: str = CROP_CYCLE_SEGMENTATION_VERSION
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.plot_namespace.is_valid():
            raise ValueError("Crop-cycle segmentation requires a complete namespace")
        if not self.segments:
            raise ValueError("Crop-cycle segmentation requires at least one segment")
        if self.current_segment_id not in {segment.segment_id for segment in self.segments}:
            raise ValueError("Current crop-cycle segment is not present")
        if not self.current_cycle_hypotheses:
            raise ValueError("Crop-cycle segmentation requires a current-cycle hypothesis")
        hypothesis_ids = {item.hypothesis_id for item in self.current_cycle_hypotheses}
        if self.primary_hypothesis_id not in hypothesis_ids:
            raise ValueError("Primary crop-cycle hypothesis is not present")
        if not math.isclose(
            sum(item.probability for item in self.current_cycle_hypotheses),
            1.0,
            abs_tol=1e-6,
        ):
            raise ValueError("Crop-cycle hypothesis probabilities must sum to one")
        if {item.hypothesis_id for item in self.hypothesis_readiness} != hypothesis_ids:
            raise ValueError("Crop-cycle readiness must cover every hypothesis")
        expected = _hash(self._payload_without_hash())
        if self.content_hash and self.content_hash != expected:
            raise ValueError("Crop-cycle segmentation hash mismatch")
        object.__setattr__(self, "content_hash", expected)

    @property
    def receipt_id(self) -> str:
        return "CROP-CYCLE-SEG-" + self.content_hash[:24]

    @property
    def primary_hypothesis(self) -> CropCycleHypothesisV1:
        return next(
            item for item in self.current_cycle_hypotheses
            if item.hypothesis_id == self.primary_hypothesis_id
        )

    @property
    def current_observation_ids(self) -> Tuple[str, ...]:
        return self.primary_hypothesis.observation_ids

    @property
    def current_evidence_readiness(self) -> SegmentScopedCropEvidenceReadinessV1:
        return next(
            item for item in self.hypothesis_readiness
            if item.hypothesis_id == self.primary_hypothesis_id
        )

    def _payload_without_hash(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "plot_namespace": {
                "tenant_id": self.plot_namespace.tenant_id,
                "farm_id": self.plot_namespace.farm_id,
                "plot_id": self.plot_namespace.plot_id,
            },
            "crop_evidence_ledger_hash": self.crop_evidence_ledger_hash,
            "segments": [segment.to_dict() for segment in self.segments],
            "current_segment_id": self.current_segment_id,
            "boundary_candidates": [item.to_dict() for item in self.boundary_candidates],
            "current_cycle_hypotheses": [item.to_dict() for item in self.current_cycle_hypotheses],
            "primary_hypothesis_id": self.primary_hypothesis_id,
            "hypothesis_readiness": [item.to_dict() for item in self.hypothesis_readiness],
            "status": self.status,
            "method": self.method,
            "calibrated": self.calibrated,
        }

    def to_dict(self) -> Dict[str, Any]:
        payload = self._payload_without_hash()
        payload.update({"receipt_id": self.receipt_id, "content_hash": self.content_hash})
        return payload


def _selected_items(
    ledger: CropEvidenceLedgerV2,
    observation_ids: Sequence[str],
) -> Tuple[Mapping[str, Any], ...]:
    wanted = set(observation_ids)
    return tuple(
        item for item in ledger.evidence_items()
        if item.get("model_use_eligible") is True
        and str(item.get("observation_id")) in wanted
    )


def build_segment_scoped_evidence_readiness(
    ledger: CropEvidenceLedgerV2,
    hypothesis: CropCycleHypothesisV1,
    tokens: Sequence[CropModelObservationTokenV1],
) -> SegmentScopedCropEvidenceReadinessV1:
    wanted = set(hypothesis.observation_ids)
    scoped_tokens = tuple(token for token in tokens if token.observation_id in wanted)
    items = _selected_items(ledger, hypothesis.observation_ids)
    counts: Dict[str, int] = {}
    for token in scoped_tokens:
        family = _family(token.source_family)
        counts[family] = counts.get(family, 0) + 1
    feature_families = tuple(sorted({
        str(family)
        for item in items for family in item.get("feature_families", [])
    }))
    phases = tuple(sorted({
        phase for item in items if (phase := _phase(item)) is not None
    }))
    timestamps = sorted(_parse(token.sensing_time) for token in scoped_tokens)
    gdd: Dict[str, list[float]] = {}
    for token in scoped_tokens:
        for basis, value in token.gdd_coordinates:
            gdd.setdefault(str(basis), []).append(float(value))
    gdd_spans = tuple(
        (basis, min(values), max(values), max(values) - min(values), len(values))
        for basis, values in sorted(gdd.items())
    )
    red_edge_names = {"ndre", "reip", "cired", "red_edge"}
    red_edge_count = sum(any(
        name.lower() in red_edge_names for name, _, _ in token.feature_values
    ) for token in scoped_tokens)
    ndvi_count = sum(_ndvi(token) is not None for token in scoped_tokens)
    physical_count = len(scoped_tokens)
    blockers = []
    if physical_count < 4:
        blockers.append("physical_evidence_insufficient")
    if len(phases) < 2:
        blockers.append("phase_coverage_insufficient")
    calibration = _domain(
        item.get("calibration_domain_compatibility") for item in items
    )
    geography = _domain(
        item.get("geographical_domain_compatibility") for item in items
    )
    if calibration != "compatible":
        blockers.append("calibration_domain_unverified")
    if geography != "compatible":
        blockers.append("geographical_domain_unverified")
    if not timestamps:
        blockers.append("temporal_coverage_unavailable")
    status = "ready_for_diagnostic_execution" if not blockers else "insufficient"
    return SegmentScopedCropEvidenceReadinessV1(
        hypothesis_id=hypothesis.hypothesis_id,
        observation_ids=tuple(token.observation_id for token in scoped_tokens),
        physical_acquisition_count=physical_count,
        sensor_counts=tuple(sorted(counts.items())),
        feature_families=feature_families,
        phase_coverage=phases,
        temporal_start=timestamps[0].isoformat() if timestamps else None,
        temporal_end=timestamps[-1].isoformat() if timestamps else None,
        temporal_span_days=(
            (timestamps[-1] - timestamps[0]).total_seconds() / 86400.0
            if len(timestamps) >= 2 else 0.0 if timestamps else None
        ),
        gdd_spans=gdd_spans,
        calibration_domain_compatibility=calibration,
        geographical_domain_compatibility=geography,
        red_edge_observation_count=red_edge_count,
        ndvi_observation_count=ndvi_count,
        readiness_status=status,
        blockers=tuple(sorted(set(blockers))),
    )


def _candidate_boundaries(
    tokens: Sequence[CropModelObservationTokenV1],
    *,
    long_gap_days: float,
    harvest_drop: float,
) -> Tuple[CropCycleBoundaryCandidateV1, ...]:
    optical = [
        token for token in tokens
        if _family(token.source_family) in _OPTICAL_FAMILIES
        and _ndvi(token) is not None
    ]
    if len(optical) < 5:
        return ()
    candidates = []
    for previous, current in zip(optical, optical[1:]):
        gap = (_parse(current.sensing_time) - _parse(previous.sensing_time)).total_seconds() / 86400.0
        drop = float(_ndvi(previous)) - float(_ndvi(current))
        reasons = []
        score = 0.0
        if gap >= long_gap_days:
            reasons.append("long_optical_observation_gap")
            score = max(score, min(0.95, 0.65 + 0.20 * gap / long_gap_days))
        if drop >= harvest_drop:
            reasons.append("harvest_like_optical_ndvi_drop")
            score = max(score, min(0.90, 0.55 + 0.25 * drop / harvest_drop))
        if not reasons:
            continue
        payload = {
            "time": current.sensing_time,
            "previous": previous.observation_hash,
            "current": current.observation_hash,
            "reasons": reasons,
        }
        candidates.append(CropCycleBoundaryCandidateV1(
            candidate_id="CROP-BOUNDARY-" + _hash(payload)[:20],
            boundary_time=current.sensing_time,
            sensor_family=_family(current.source_family),
            preceding_observation_id=previous.observation_id,
            following_observation_id=current.observation_id,
            reasons=tuple(reasons),
            diagnostic_score=round(score, 8),
        ))
    return tuple(candidates)


def build_crop_cycle_segmentation_receipt(
    ledger: CropEvidenceLedgerV2 | Mapping[str, Any],
    *,
    crop_cycle_hypothesis_id: Optional[str] = None,
    long_gap_days: float = 45.0,
    harvest_drop: float = 0.25,
) -> CropCycleSegmentationReceiptV1:
    ledger = normalize_verified_crop_evidence_ledger(ledger)
    tokens = list(observation_tokens_from_ledger(ledger))
    if not tokens:
        raise ValueError("Crop-cycle segmentation requires admitted physical evidence")
    tokens.sort(key=lambda token: (_parse(token.sensing_time), token.observation_hash))
    candidates = _candidate_boundaries(
        tokens, long_gap_days=long_gap_days, harvest_drop=harvest_drop,
    )

    explicit_ids: set[str] = set()
    requested_cycle = str(crop_cycle_hypothesis_id or "").strip()
    if requested_cycle and requested_cycle not in {"unresolved-cycle", "unknown"}:
        selected_hashes = {token.observation_hash: token.observation_id for token in tokens}
        explicit_ids = {
            selected_hashes[observation.observation_hash]
            for observation in ledger.observations
            if observation.observation_hash in selected_hashes
            and str(observation.crop_cycle_id or "").strip() == requested_cycle
        }

    raw_hypotheses: list[
        tuple[
            Optional[CropCycleBoundaryCandidateV1],
            tuple[CropModelObservationTokenV1, ...],
            float,
            str,
        ]
    ] = []
    if explicit_ids:
        members = tuple(token for token in tokens if token.observation_id in explicit_ids)
        raw_hypotheses.append((None, members, 1.0, "ledger_crop_cycle_identity_match"))
    else:
        raw_hypotheses.append((None, tuple(tokens), 0.25, "continuing_cycle_from_ledger_window"))
        for candidate in candidates:
            boundary = _parse(candidate.boundary_time)
            members = tuple(token for token in tokens if _parse(token.sensing_time) >= boundary)
            if members:
                raw_hypotheses.append((candidate, members, candidate.diagnostic_score, "unvalidated_optical_boundary_candidate"))
    weight_sum = sum(weight for _, _, weight, _ in raw_hypotheses)
    hypotheses = []
    for candidate, members, weight, basis in raw_hypotheses:
        payload = {
            "ledger": ledger.ledger_hash,
            "observation_ids": [token.observation_id for token in members],
            "boundary": candidate.candidate_id if candidate else None,
            "basis": basis,
        }
        hypotheses.append(CropCycleHypothesisV1(
            hypothesis_id="CROP-CYCLE-HYP-" + _hash(payload)[:20],
            start_time=members[0].sensing_time,
            end_time=members[-1].sensing_time,
            observation_ids=tuple(token.observation_id for token in members),
            physical_acquisition_keys=tuple(token.physical_acquisition_key for token in members),
            boundary_candidate_id=candidate.candidate_id if candidate else None,
            probability=round(weight / weight_sum, 10),
            basis=basis,
        ))
    correction = 1.0 - sum(item.probability for item in hypotheses)
    if correction:
        hypotheses[-1] = replace(
            hypotheses[-1],
            probability=round(hypotheses[-1].probability + correction, 10),
        )
    primary = max(hypotheses, key=lambda item: (item.probability, item.start_time))

    boundary_by_time = {_parse(item.boundary_time): item for item in candidates}
    starts = [(_parse(tokens[0].sensing_time), "ledger_window_start")]
    starts.extend(
        (stamp, "+".join(candidate.reasons))
        for stamp, candidate in sorted(boundary_by_time.items())
    )
    segments = []
    for ordinal, (start, reason) in enumerate(starts):
        end = starts[ordinal + 1][0] if ordinal + 1 < len(starts) else None
        members = tuple(
            token for token in tokens
            if _parse(token.sensing_time) >= start
            and (end is None or _parse(token.sensing_time) < end)
        )
        if not members:
            continue
        payload = {"ledger": ledger.ledger_hash, "ids": [item.observation_id for item in members]}
        segment_id = "CROP-SEG-" + _hash(payload)[:20]
        member_ids = {item.observation_id for item in members}
        segments.append(CropCycleSegmentV1(
            segment_id=segment_id,
            start_time=members[0].sensing_time,
            end_time=members[-1].sensing_time,
            observation_ids=tuple(item.observation_id for item in members),
            physical_acquisition_keys=tuple(item.physical_acquisition_key for item in members),
            boundary_reason=reason,
            current_cycle_probability=round(sum(
                hypothesis.probability
                for hypothesis in hypotheses
                if member_ids.issubset(set(hypothesis.observation_ids))
            ), 10),
        ))

    readiness = tuple(
        build_segment_scoped_evidence_readiness(ledger, hypothesis, tokens)
        for hypothesis in hypotheses
    )
    usable_ndvi = sum(_ndvi(token) is not None for token in tokens)
    if explicit_ids:
        status = "ledger_cycle_identity_scoped"
    elif candidates:
        status = "unresolved_probabilistic_boundary_candidates"
    elif usable_ndvi < 5:
        status = "insufficient_for_boundary_inference"
    else:
        status = "single_cycle_candidate"
    return CropCycleSegmentationReceiptV1(
        plot_namespace=ledger.plot_namespace,
        crop_evidence_ledger_hash=ledger.ledger_hash,
        segments=tuple(segments),
        current_segment_id=segments[-1].segment_id,
        boundary_candidates=candidates,
        current_cycle_hypotheses=tuple(hypotheses),
        primary_hypothesis_id=primary.hypothesis_id,
        hypothesis_readiness=readiness,
        status=status,
        method="sensor_specific_optical_axis_probabilistic_candidates_v2",
        calibrated=False,
    )


__all__ = [
    "CROP_CYCLE_SEGMENTATION_VERSION",
    "CropCycleBoundaryCandidateV1",
    "CropCycleHypothesisV1",
    "SegmentScopedCropEvidenceReadinessV1",
    "CropCycleSegmentV1",
    "CropCycleSegmentationReceiptV1",
    "build_segment_scoped_evidence_readiness",
    "build_crop_cycle_segmentation_receipt",
]
