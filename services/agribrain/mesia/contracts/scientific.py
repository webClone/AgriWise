"""MESIA Scientific Qualification Contracts — R6 §11, Appendix A.

ObservabilityCertificate — Supported zones/strata, rank/conditioning,
  resolution/depth limits and dropout robustness.
ClosureCertificate — Held-out radio/link/node/band/time/intervention
  prediction performance and shortcut checks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ObservabilityCertificate:
    """Supported zones, depth strata, rank and conditioning — R6 Appendix A.

    Produced from geometry, sensitivity kernels, and Fisher information
    analysis over the shared ASMAE microzone lattice.
    """

    certificate_id: str
    target_capability: str
    """e.g., 'root_zone_water', 'canopy_water', 'salinity_stress'."""

    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Supported spatial/strata boundaries
    supported_microzones: List[str] = field(default_factory=list)
    supported_strata: List[str] = field(default_factory=list)
    """e.g., ['surface_0_5cm', 'root_zone_5_30cm', 'deep_30_60cm']."""

    unobservable_zones: List[str] = field(default_factory=list)
    unobservable_strata: List[str] = field(default_factory=list)

    # Matrix conditioning and information metrics
    effective_rank: Optional[float] = None
    condition_number: Optional[float] = None
    fisher_information_score: Optional[float] = None
    collinearity_index: Optional[float] = None
    posterior_contraction_ratio: Optional[float] = None

    # Geometry & link sensitivity
    participating_links: List[str] = field(default_factory=list)
    critical_links: List[str] = field(default_factory=list)
    """Links whose removal would drop observability below threshold."""

    dropout_robustness_score: Optional[float] = None
    geometry_epoch_refs: List[str] = field(default_factory=list)

    # Resolution limits
    effective_spatial_resolution_m: Optional[float] = None
    effective_temporal_resolution_s: Optional[float] = None
    depth_limit_m: Optional[float] = None

    # Status
    is_observable: bool = True
    abstention_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for f in self.__dataclass_fields__:
            val = getattr(self, f)
            if isinstance(val, datetime):
                val = val.isoformat()
            elif isinstance(val, (list, tuple)):
                val = list(val)
            d[f] = val
        return d

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


from enum import Enum


class ClosureStatus(str, Enum):
    """Explicit state machine for independent physical and statistical closure."""

    NOT_EVALUATED = "NOT_EVALUATED"
    """Initial default state: no withheld physical evidence or evaluation has been performed."""

    EVALUATION_INVALID = "EVALUATION_INVALID"
    """Missing pre-registration, contaminated holdout, or broken manifest."""

    EVALUATED_FAILED = "EVALUATED_FAILED"
    """Holdout prediction error or shortcut check exceeded permitted threshold."""

    EVALUATED_PASSED = "EVALUATED_PASSED"
    """Strictly verified against pre-registered predictions on authentic physically withheld observations."""

    REVOKED = "REVOKED"
    """Authority explicitly withdrawn due to downstream drift or invalidated calibration."""


@dataclass(frozen=True)
class ClosureCertificate:
    """Held-out radio/link/node/band/time prediction performance — R6 Appendix A.

    Validates that the multi-radio model satisfies physical and statistical
    closure without shortcuts. Fails closed by default (status=NOT_EVALUATED).
    """

    certificate_id: str
    target_capability: str
    status: ClosureStatus = ClosureStatus.NOT_EVALUATED
    evaluated_at: Optional[datetime] = None

    # Authentic Withheld Physical Observation References
    withheld_evidence_refs: Tuple[str, ...] = field(default_factory=tuple)

    # Closure Test Types and Scores
    leave_link_out_r2: Optional[float] = None
    leave_node_out_r2: Optional[float] = None
    leave_band_out_r2: Optional[float] = None
    leave_rat_out_r2: Optional[float] = None
    future_time_prediction_rmse: Optional[float] = None
    intervention_holdout_rmse: Optional[float] = None

    # Residuals & Coverage
    closure_residual_mean: Optional[float] = None
    closure_residual_variance: Optional[float] = None
    closure_coverage_pct: Optional[float] = None

    # Shortcut & Confounder Challenges (Default False: never presumed passed)
    passed_shortcut_checks: bool = False
    shortcut_challenge_receipt_ref: str = ""
    shortcut_vulnerability_notes: List[str] = field(default_factory=list)

    # Incremental Value Comparison (Default False: never presumed demonstrated)
    strongest_single_radio_metric: Optional[float] = None
    multi_radio_metric: Optional[float] = None
    non_radio_baseline_metric: Optional[float] = None
    incremental_value_demonstrated: bool = False

    # Pre-registration & Manifests
    preregistration_ref: str = ""
    split_manifest_hash: str = ""
    dataset_version: str = ""

    # Epoch Lineage References
    receiver_epoch_ref: str = ""
    geometry_epoch_ref: str = ""
    calibration_epoch_ref: str = ""
    software_epoch_ref: str = ""

    # Status & Signature
    closure_passed: bool = False
    certificate_signature: str = ""
    review_comments: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.withheld_evidence_refs, tuple):
            object.__setattr__(self, "withheld_evidence_refs", tuple(self.withheld_evidence_refs))

        if self.status == ClosureStatus.EVALUATED_PASSED:
            if not self.withheld_evidence_refs or len(self.withheld_evidence_refs) == 0:
                raise ValueError("EVALUATED_PASSED requires authentic withheld physical receiver evidence refs.")
            if not self.preregistration_ref or not self.preregistration_ref.strip():
                raise ValueError("EVALUATED_PASSED requires a non-empty preregistration_ref created before observation access.")
            if not self.split_manifest_hash or len(self.split_manifest_hash.strip()) < 32:
                raise ValueError("EVALUATED_PASSED requires an immutable split_manifest_hash.")
            if not self.receiver_epoch_ref or not self.geometry_epoch_ref or not self.calibration_epoch_ref or not self.software_epoch_ref:
                raise ValueError("EVALUATED_PASSED requires receiver, geometry, calibration, and software epoch refs.")
            if not self.passed_shortcut_checks or not self.shortcut_challenge_receipt_ref:
                raise ValueError("EVALUATED_PASSED requires passed_shortcut_checks=True and a shortcut_challenge_receipt_ref.")
            if not self.incremental_value_demonstrated:
                raise ValueError("EVALUATED_PASSED requires incremental_value_demonstrated=True against non-radio baseline.")
            if not self.evaluated_at:
                raise ValueError("EVALUATED_PASSED requires an evaluated_at timestamp.")
            if not self.closure_passed:
                raise ValueError("EVALUATED_PASSED requires closure_passed=True.")

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for f in self.__dataclass_fields__:
            val = getattr(self, f)
            if isinstance(val, datetime):
                val = val.isoformat()
            elif isinstance(val, Enum):
                val = val.value
            elif isinstance(val, (list, tuple)):
                val = list(val)
            d[f] = val
        return d

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

