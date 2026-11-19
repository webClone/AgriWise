"""IR-04 Batch A: defensive state × cell × valid-time × knowledge-time support.

This is a contract-only, exploratory evidence-support evaluator. It does NOT
refine the EnKF graph, create rasters, validate source signatures, or authorize
certified 1 m claims. Production integration must supply identity-verified
observation operators/metadata and holdout qualification upstream.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import re
from typing import Literal, Optional, Sequence, Tuple

STATE_NAMES = (
    "vigor", "lai", "chlorophyll", "canopy_water", "root_zone_water",
    "surface_wetness_event", "structure", "bare_soil_fraction",
    "salinity_stress", "thermal_stress", "biotic_confounder_risk",
    "phenology_progress", "stress_memory",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SpatialSupportViolation(ValueError):
    """Rejects wrong-scope or structurally invalid spatial evidence."""


def _utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise SpatialSupportViolation("timestamps must be ISO-8601 UTC strings")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SpatialSupportViolation("invalid ISO-8601 timestamp") from exc
    if instant.tzinfo is None or instant.utcoffset() != timedelta(0):
        raise SpatialSupportViolation("timestamp must explicitly declare UTC")
    return instant.astimezone(timezone.utc)


def _hash(value: str, field: str) -> None:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise SpatialSupportViolation(f"{field} must be a lowercase SHA-256 digest")


def _positive(value: float, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
        raise SpatialSupportViolation(f"{field} must be finite and positive")


def _canonical_digest(data: object) -> str:
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class GridSpec:
    """A projected metric reference grid; rotated cells require real geometry support."""

    crs: str
    transform: Tuple[float, float, float, float, float, float]
    width: int
    height: int
    unit: str = "metre"

    def __post_init__(self) -> None:
        if not self.crs or self.crs.upper() in ("EPSG:4326", "OGC:CRS84") or self.unit != "metre":
            raise SpatialSupportViolation("reference grid requires a projected metric CRS")
        if len(self.transform) != 6 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in self.transform):
            raise SpatialSupportViolation("affine transform must contain six finite numbers")
        if any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in (self.width, self.height)):
            raise SpatialSupportViolation("grid dimensions must be positive integers")
        a, b, c, d, e, f = self.transform
        # A row/column-to-pixel-bounds approximation is not valid for rotation/shear.
        if abs(c) > 1e-12 or abs(e) > 1e-12 or abs(b) < 1e-12 or abs(f) < 1e-12:
            raise SpatialSupportViolation("unsupported rotated/sheared/degenerate reference grid")

    def cell_bbox(self, row: int, col: int) -> Tuple[float, float, float, float]:
        if row < 0 or col < 0 or row >= self.height or col >= self.width:
            raise SpatialSupportViolation("cell outside reference grid")
        x0, xstep, _, y0, _, ystep = self.transform
        xa, xb = x0 + xstep * col, x0 + xstep * (col + 1)
        ya, yb = y0 + ystep * row, y0 + ystep * (row + 1)
        return min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb)

    def minimum_scientific_cell_scale_m(self) -> float:
        """Output cell size bounds what detail this grid can actually represent."""
        return max(abs(float(self.transform[1])), abs(float(self.transform[5])))

    def digest(self) -> str:
        return _canonical_digest({"crs": self.crs, "transform": self.transform,
                                  "width": self.width, "height": self.height, "unit": self.unit})


@dataclass(frozen=True)
class EvidenceFootprint:
    """Untrusted until independently admitted upstream: never a certification token."""

    observation_id: str
    source_sha256: str
    operator_sha256: str
    tenant_id: str
    farm_id: str
    plot_id: str
    geometry_sha256: str
    observation_valid_time: str
    committed_at: str
    supported_states: Tuple[str, ...]
    bbox: Tuple[float, float, float, float]
    crs: str
    native_resolution_m: float
    psf_fwhm_m: float
    observability: float
    calibrated_operator_sha256: Optional[str] = None
    classification: Literal["physical", "forecast", "synthetic", "scenario"] = "physical"
    nodata: bool = False
    independent_holdout_sha256: Optional[str] = None
    valid_cell_indices: Optional[Tuple[int, ...]] = None
    valid_support_hash: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.observation_id or not all((self.tenant_id, self.farm_id, self.plot_id, self.crs)):
            raise SpatialSupportViolation("missing observation identity or namespace")
        for name in ("source_sha256", "operator_sha256", "geometry_sha256"):
            _hash(getattr(self, name), name)
        if self.calibrated_operator_sha256 is not None:
            _hash(self.calibrated_operator_sha256, "calibrated_operator_sha256")
        if self.independent_holdout_sha256 is not None:
            _hash(self.independent_holdout_sha256, "independent_holdout_sha256")
        if self.valid_support_hash is not None:
            _hash(self.valid_support_hash, "valid_support_hash")
        if self.valid_cell_indices is not None:
            if not all(isinstance(i, int) and i >= 0 for i in self.valid_cell_indices):
                raise SpatialSupportViolation("valid_cell_indices must contain non-negative integers")
        _utc(self.observation_valid_time)
        _utc(self.committed_at)
        if not self.supported_states or any(s not in STATE_NAMES for s in self.supported_states):
            raise SpatialSupportViolation("supported_states must be known latent state names")
        _positive(self.native_resolution_m, "native_resolution_m")
        _positive(self.psf_fwhm_m, "psf_fwhm_m")
        if not isinstance(self.observability, (int, float)) or not math.isfinite(self.observability) or not 0 <= self.observability <= 1:
            raise SpatialSupportViolation("observability must be in [0,1]")
        if len(self.bbox) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in self.bbox):
            raise SpatialSupportViolation("invalid footprint bounding box")
        x0, y0, x1, y1 = self.bbox
        if x0 >= x1 or y0 >= y1:
            raise SpatialSupportViolation("non-positive footprint area")

    def content_identity(self) -> str:
        # Canonical fingerprint for bookkeeping, not an authenticated signature.
        return _canonical_digest(self.__dict__)


@dataclass(frozen=True)
class StateCellSupport:
    contract_version: str
    state: str
    row: int
    col: int
    valid_time: str
    knowledge_cutoff: str
    grid_sha256: str
    estimate_kind: Literal["posterior", "prior_only", "unavailable"]
    spatial_support: Literal["local_operator", "modeled_coupling", "none"]
    authority_status: Literal["exploratory", "denied"]
    estimated_value: Optional[float]
    sigma: Optional[float]
    effective_resolution_m: Optional[float]
    admitted_observation_ids: Tuple[str, ...]
    admitted_source_hashes: Tuple[str, ...]
    propagated_source_hashes: Tuple[str, ...]
    holdout_references: Tuple[str, ...]
    demotion_reasons: Tuple[str, ...]
    certified_1m: bool = False
    admitted_operator_hashes: Tuple[str, ...] = ()
    admitted_calibration_hashes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.certified_1m:
            raise SpatialSupportViolation("1 m certification cannot originate in the exploratory contract")
        if self.authority_status not in ("exploratory", "denied"):
            raise SpatialSupportViolation("unsupported authority status")
        if self.state not in STATE_NAMES:
            raise SpatialSupportViolation("unsupported latent state")

    def to_dict(self) -> dict:
        return {key: list(value) if isinstance(value, tuple) else value
                for key, value in self.__dict__.items()}

    def digest(self) -> str:
        return _canonical_digest(self.to_dict())


def _overlap_fraction(a: Tuple[float, ...], b: Tuple[float, ...]) -> float:
    x = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    y = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return x * y / ((a[2] - a[0]) * (a[3] - a[1]))


def evaluate_state_cell_support(
    *, state: str, row: int, col: int, grid: GridSpec,
    tenant_id: str, farm_id: str, plot_id: str, geometry_sha256: str,
    valid_time: str, knowledge_cutoff: str,
    estimated_value: Optional[float], sigma: Optional[float],
    evidences: Sequence[EvidenceFootprint],
    propagation_source_hashes: Sequence[str] = (),
    display_resolution_m: Optional[float] = None,
    scene_wide_1m_approval: bool = False,
    retrovalidation_score: float = 1.0,
    bma_agreement: float = 1.0,
) -> StateCellSupport:
    """Conservative metadata, never an independently certified spatial claim.

    The unused scene-wide, retrovalidation and BMA arguments are intentionally
    retained as hostile-control inputs: none can upgrade spatial support.
    """
    if state not in STATE_NAMES:
        raise SpatialSupportViolation("unknown latent state")
    _hash(geometry_sha256, "geometry_sha256")
    t, k = _utc(valid_time), _utc(knowledge_cutoff)
    bbox = grid.cell_bbox(row, col)
    if estimated_value is not None and (not isinstance(estimated_value, (int, float)) or
                                        not math.isfinite(estimated_value)):
        raise SpatialSupportViolation("non-finite state estimate")
    if sigma is not None and (not isinstance(sigma, (int, float)) or
                              not math.isfinite(sigma) or sigma < 0):
        raise SpatialSupportViolation("invalid state uncertainty")
    if display_resolution_m is not None:
        _positive(display_resolution_m, "display_resolution_m")
    for hash_value in propagation_source_hashes:
        _hash(hash_value, "propagation_source_hash")

    reasons = []
    usable = []
    for ev in evidences:
        # Fail closed on a wrong-scoped record, rather than silently accepting it.
        if (ev.tenant_id, ev.farm_id, ev.plot_id, ev.geometry_sha256) != (tenant_id, farm_id, plot_id, geometry_sha256):
            raise SpatialSupportViolation("evidence namespace or geometry mismatch")
        if _utc(ev.observation_valid_time) > t or _utc(ev.committed_at) > k:
            reasons.append("excluded_by_valid_or_knowledge_cutoff")
            continue
        if ev.classification != "physical":
            reasons.append("non_observation_excluded")
            continue
        if state not in ev.supported_states:
            continue
        if ev.crs != grid.crs:
            reasons.append("crs_mismatch_requires_qualified_reprojection")
            continue
        if ev.nodata:
            reasons.append("source_nodata")
            continue
        coverage = _overlap_fraction(bbox, ev.bbox)
        if coverage < 0.95:
            reasons.append("insufficient_local_footprint_overlap")
            continue
        if ev.valid_cell_indices is not None:
            cell_idx = row * grid.width + col
            if cell_idx not in ev.valid_cell_indices:
                reasons.append("masked_by_scene_valid_support")
                continue
        if ev.observability < 0.7:
            reasons.append("weak_state_specific_observability")
            continue
        if not ev.calibrated_operator_sha256:
            reasons.append("uncalibrated_observation_operator")
            continue
        usable.append(ev)

    best = min(usable, key=lambda ev: (max(ev.native_resolution_m, ev.psf_fwhm_m), ev.observation_id), default=None)
    estimate_kind = "posterior" if estimated_value is not None else "unavailable"
    if estimate_kind == "unavailable":
        spatial_support, resolution_m = "none", None
        reasons.append("no_posterior_estimate")
    elif best is not None:
        spatial_support = "local_operator"
        instrument_scale_m = max(float(best.native_resolution_m), float(best.psf_fwhm_m))
        resolution_m = max(instrument_scale_m, grid.minimum_scientific_cell_scale_m())
        if instrument_scale_m < grid.minimum_scientific_cell_scale_m():
            reasons.append("fine_evidence_requires_finer_scientific_state_grid")
    elif propagation_source_hashes:
        spatial_support, resolution_m = "modeled_coupling", None
    else:
        spatial_support, resolution_m = "none", None
        estimate_kind = "prior_only"
        reasons.append("no_qualified_local_operator")

    if not usable:
        reasons.append("no_independently_qualified_local_fine_evidence")
    if resolution_m is not None and resolution_m <= 1.0:
        reasons.append("one_meter_certification_on_hold")
    # A display-resolution change never enters effective_resolution_m.
    # No signatures or independent authority service is verified here.
    return StateCellSupport(
        contract_version="akaloris/asmae-state-cell-support/v1",
        state=state, row=row, col=col, valid_time=t.isoformat(), knowledge_cutoff=k.isoformat(),
        grid_sha256=grid.digest(), estimate_kind=estimate_kind,
        spatial_support=spatial_support,
        authority_status="exploratory" if estimated_value is not None else "denied",
        estimated_value=estimated_value, sigma=sigma, effective_resolution_m=resolution_m,
        admitted_observation_ids=tuple(sorted(ev.observation_id for ev in usable)),
        admitted_source_hashes=tuple(sorted(ev.source_sha256 for ev in usable)),
        admitted_operator_hashes=tuple(sorted(ev.operator_sha256 for ev in usable)),
        admitted_calibration_hashes=tuple(sorted(ev.calibrated_operator_sha256 for ev in usable if ev.calibrated_operator_sha256)),
        propagated_source_hashes=tuple(sorted(set(propagation_source_hashes))),
        holdout_references=tuple(sorted(ev.independent_holdout_sha256 for ev in usable if ev.independent_holdout_sha256)),
        demotion_reasons=tuple(sorted(set(reasons))), certified_1m=False,
    )


def statewise_support_tensor(records: Sequence[StateCellSupport]) -> dict:
    """Stable 13-state selector data, not 13 invented spatial rasters."""
    if not records:
        return {state: {} for state in STATE_NAMES}
    grid_ids = {r.grid_sha256 for r in records}
    tk = {(r.valid_time, r.knowledge_cutoff) for r in records}
    if len(grid_ids) != 1 or len(tk) != 1:
        raise SpatialSupportViolation("mixed reference grids or bitemporal cutoffs")
    tensor = {state: {} for state in STATE_NAMES}
    for record in records:
        cell_id = f"{record.row}:{record.col}"
        if cell_id in tensor[record.state]:
            raise SpatialSupportViolation("duplicate state-cell support record")
        tensor[record.state][cell_id] = record.to_dict()
    return tensor


def describe_display_resampling(record: StateCellSupport, display_resolution_m: float) -> dict:
    _positive(display_resolution_m, "display_resolution_m")
    return {
        "state": record.state, "cell": f"{record.row}:{record.col}",
        "source_support_digest": record.digest(),
        "source_effective_resolution_m": record.effective_resolution_m,
        "display_resolution_m": float(display_resolution_m),
        "is_resampled_display": bool(record.effective_resolution_m is None or
                                     display_resolution_m < record.effective_resolution_m),
        "authority_status": "display_only_not_certified",
    }
