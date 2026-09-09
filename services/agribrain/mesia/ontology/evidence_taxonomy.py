"""MESIA Evidence Taxonomy & Truth Envelope — Scientific Governance (R6 / P-01..P-10).

Provides orthogonal multi-dimensional classification of radio observations, models,
and derived agronomic states to ensure zero false claims of physical measurement.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from .identity_states import IdentityState


class SourceClass(str, Enum):
    """Originating physical or computational source of the data."""

    PHYSICAL_RECEIVER = "PHYSICAL_RECEIVER"
    """Direct physical RF acquisition from authenticated local receiver hardware (SDR, RTK, IoT)."""

    REMOTE_PRODUCT = "REMOTE_PRODUCT"
    """Authenticated satellite/airborne mission product (Sentinel-1, CYGNSS L3) with verified spatio-temporal intersection."""

    GIS_REGISTRY = "GIS_REGISTRY"
    """Geodetic infrastructure database (OpenStreetMap, cadastral registry)."""

    NWP_MODEL = "NWP_MODEL"
    """Numerical Weather Prediction or atmospheric/hydrological reanalysis (ECMWF, Open-Meteo)."""

    SIMULATOR = "SIMULATOR"
    """Analytical physical forward model (Dubois SAR backscatter, 2-ray ground bounce, Yee FDTD)."""


class ProcessingLevel(str, Enum):
    """Algorithmic transformation level from raw inputs to state representations."""

    NATIVE = "NATIVE"
    """Raw byte stream (IQ samples, NMEA sentences, netlink frames, radar ADC cubes)."""

    CALIBRATED = "CALIBRATED"
    """Instrument gain-, phase-, noise-, and antenna-pattern corrected observables."""

    FEATURE = "FEATURE"
    """Intermediate extracted features (SNR arcs, channel frequency response H(k), backscatter sigma_0)."""

    DERIVED = "DERIVED"
    """Inverted physical states (soil dielectric permittivity, volumetric water content, canopy water index)."""

    FUSED = "FUSED"
    """Multi-modal or multi-frequency joint state estimate."""


class AuthorityState(str, Enum):
    """Downstream scientific and agricultural decision eligibility."""

    QUARANTINED = "QUARANTINED"
    """Unverified, suspicious, unauthenticated, or out-of-calibration observation."""

    RESEARCH_ONLY = "RESEARCH_ONLY"
    """Scientifically valid research observation, hypothesis, or model; INELIGIBLE for agricultural action."""

    QUALIFIED = "QUALIFIED"
    """Formally admitted by AgriBrain Layer-0 and verified against capability gates for ASMAE posterior fusion."""

    DEGRADED = "DEGRADED"
    """Calibration stale, excess residual detected, or partial geometric obstruction present."""

    REVOKED = "REVOKED"
    """Authority explicitly withdrawn due to failed independent closure, physical anomaly, or drift."""


class PresentationState(str, Enum):
    """UI and visualization presentation lifecycle state."""

    LIVE = "LIVE"
    """Near-real-time streaming physical measurement from on-parcel or overhead aperture."""

    REPLAY = "REPLAY"
    """Deterministic re-execution of immutable native recorded bytes with verified epoch."""

    SIMULATION = "SIMULATION"
    """Theoretical forward calculation or parameter sweep based on ambient assumptions."""

    DEMO_PLACEHOLDER = "DEMO_PLACEHOLDER"
    """Explicit demonstration visual scaffold. FORBIDDEN from entering evidence store or ASMAE."""


@dataclass(frozen=True)
class TruthEnvelope:
    """Machine-enforced truth container wrapping every displayed and persisted value.
    
    Prevents ambiguity between physical observations, weather models, forward simulations,
    and visual demonstrations via strict cross-field structural validation.
    """

    value: Any
    unit: str
    source_class: SourceClass
    processing_level: ProcessingLevel
    identity_state: IdentityState
    authority_state: AuthorityState
    presentation_state: PresentationState
    native_artifact_ref: Optional[str] = None
    source_receipt_ref: Optional[str] = None
    calibration_state_ref: Optional[str] = None
    software_epoch_ref: str = "mesia-r6.1"
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    valid_for_seconds: float = 3600.0
    uncertainty: Optional[float] = None
    decision_eligible: bool = False
    persist_as_evidence: bool = False
    parent_envelope_refs: Tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = "1.0.0"
    explanation: str = ""

    def __post_init__(self) -> None:
        # Normalize parent_envelope_refs to a tuple if passed as list
        if not isinstance(self.parent_envelope_refs, tuple):
            object.__setattr__(self, "parent_envelope_refs", tuple(self.parent_envelope_refs))

        # 1. Temporal Validity
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware UTC datetime.")
        if self.valid_for_seconds <= 0.0:
            raise ValueError("valid_for_seconds must be strictly positive.")

        # 2. Uncertainty Semantics (Never allow 0.0 to falsely imply perfect certainty)
        if self.uncertainty is not None:
            if math.isnan(self.uncertainty) or math.isinf(self.uncertainty) or self.uncertainty <= 0.0:
                raise ValueError(
                    f"uncertainty must be a strictly positive finite float, or None if unquantified (got {self.uncertainty})."
                )

        # 3. Impossible Combinations: Simulation + Physical Presentation / Qualification
        if self.source_class == SourceClass.SIMULATOR and self.presentation_state == PresentationState.LIVE:
            raise ValueError("SIMULATOR cannot have LIVE presentation state (LIVE is reserved for physical measurements).")

        if self.source_class == SourceClass.NWP_MODEL and self.presentation_state == PresentationState.LIVE:
            raise ValueError("NWP_MODEL cannot have LIVE presentation state (LIVE is reserved for physical measurements).")

        if self.source_class == SourceClass.SIMULATOR and self.authority_state == AuthorityState.QUALIFIED:
            raise ValueError("SIMULATOR cannot have QUALIFIED authority state. Authority must be RESEARCH_ONLY or QUARANTINED.")

        # 4. Impossible Combinations: Demo Placeholders cannot persist as evidence
        if self.presentation_state == PresentationState.DEMO_PLACEHOLDER and self.persist_as_evidence:
            raise ValueError("DEMO_PLACEHOLDER presentation state cannot be persisted as evidence (persist_as_evidence must be False).")

        # 5. Actuation Eligibility Gating
        if self.decision_eligible:
            if self.authority_state != AuthorityState.QUALIFIED:
                raise ValueError("decision_eligible cannot be True unless authority_state is QUALIFIED.")
            if self.source_class == SourceClass.SIMULATOR:
                raise ValueError("decision_eligible cannot be True for SourceClass.SIMULATOR.")
            if self.processing_level not in (ProcessingLevel.CALIBRATED, ProcessingLevel.FEATURE, ProcessingLevel.DERIVED, ProcessingLevel.FUSED):
                raise ValueError("decision_eligible requires CALIBRATED, FEATURE, DERIVED, or FUSED processing level.")

        # 6. Physical Receiver Provenance Gate
        if self.source_class == SourceClass.PHYSICAL_RECEIVER:
            if not self.native_artifact_ref:
                raise ValueError("PHYSICAL_RECEIVER requires non-empty native_artifact_ref.")
            if not self.source_receipt_ref:
                raise ValueError("PHYSICAL_RECEIVER requires non-empty source_receipt_ref.")
            if not self.calibration_state_ref:
                raise ValueError("PHYSICAL_RECEIVER requires non-empty calibration_state_ref.")

        # 7. Lineage Provenance Gate for Derived and Fused Evidence
        if self.processing_level in (ProcessingLevel.DERIVED, ProcessingLevel.FUSED):
            if not self.parent_envelope_refs or len(self.parent_envelope_refs) == 0:
                raise ValueError("DERIVED and FUSED evidence require at least one parent_envelope_ref.")

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Serializes the truth envelope to a deterministic dictionary."""
        return {
            "schema_version": self.schema_version,
            "value": self.value,
            "unit": self.unit,
            "source_class": self.source_class.value,
            "processing_level": self.processing_level.value,
            "identity_state": self.identity_state.value,
            "authority_state": self.authority_state.value,
            "presentation_state": self.presentation_state.value,
            "native_artifact_ref": self.native_artifact_ref,
            "source_receipt_ref": self.source_receipt_ref,
            "calibration_state_ref": self.calibration_state_ref,
            "software_epoch_ref": self.software_epoch_ref,
            "observed_at": self.observed_at.isoformat(),
            "valid_for_seconds": self.valid_for_seconds,
            "uncertainty": self.uncertainty,
            "decision_eligible": self.decision_eligible,
            "persist_as_evidence": self.persist_as_evidence,
            "parent_envelope_refs": list(self.parent_envelope_refs),
            "explanation": self.explanation,
        }

    def canonical_json(self) -> str:
        """Returns deterministic JSON representation."""
        return json.dumps(self.to_canonical_dict(), sort_keys=True, separators=(",", ":"))

    def content_hash(self) -> str:
        """Returns deterministic SHA-256 content hash of canonical JSON."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the truth envelope to a dictionary with ISO timestamps and content hash."""
        d = self.to_canonical_dict()
        d["content_hash"] = self.content_hash()
        return d
