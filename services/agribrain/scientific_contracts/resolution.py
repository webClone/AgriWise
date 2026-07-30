"""Scientific Contracts — Resolution Contract.

Isolated from world_model and layer packages.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Dict, Optional

from .exceptions import ContractViolation


class TransformationClass(str, Enum):
    NATIVE_GRID = "NATIVE_GRID"
    RESAMPLED = "RESAMPLED"
    MODEL_ASSISTED_RASTER = "MODEL_ASSISTED_RASTER"
    SUPER_RESOLUTION = "SUPER_RESOLUTION"
    UNCHECKED_INTERPOLATION = "UNCHECKED_INTERPOLATION"


class SupportBasis(str, Enum):
    SINGLE_SENSOR = "SINGLE_SENSOR"
    MULTI_SENSOR_FUSION = "MULTI_SENSOR_FUSION"
    SPATIOTEMPORAL_MODEL = "SPATIOTEMPORAL_MODEL"


class ResolutionAuthority(str, Enum):
    UNVALIDATED = "UNVALIDATED"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    HOLDOUT_VALIDATED = "HOLDOUT_VALIDATED"
    FIELD_APPROVED = "FIELD_APPROVED"


@dataclass(frozen=True)
class ResolutionValidationProof:
    """Typed evidence required before claiming finer scientific resolution."""
    holdout_report_id: str
    registration_report_id: str
    parent_cell_closure_report_id: str
    radiometric_closure_report_id: str
    uncertainty_calibration_report_id: str
    review_decision_id: str

    def validate(self) -> None:
        for name, value in self.__dict__.items():
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"resolution_validation_missing:{name}")

    def to_dict(self) -> Dict[str, str]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ResolutionContract:
    """Resolution contract separating grid spacing, native, effective, and display resolution."""
    grid_spacing_m: float
    native_observation_resolution_m: float
    effective_scientific_resolution_m: float
    display_resolution_m: float
    transformation_class: TransformationClass
    support_basis: SupportBasis = SupportBasis.SPATIOTEMPORAL_MODEL
    resolution_authority: ResolutionAuthority = ResolutionAuthority.UNVALIDATED
    validation_ref: str = ""
    validation_proof: Optional[ResolutionValidationProof] = None
    observed_fraction: float = 1.0
    reconstructed_fraction: float = 0.0
    overlap_allowed: bool = False
    overlap_mask_ref: str = ""

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        resolution_values = (
            self.grid_spacing_m,
            self.native_observation_resolution_m,
            self.effective_scientific_resolution_m,
            self.display_resolution_m,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) <= 0.0
            for value in resolution_values
        ):
            raise ContractViolation("Resolutions must be positive")
        if not isinstance(self.transformation_class, TransformationClass):
            raise ContractViolation("transformation_class must be typed")
        if not isinstance(self.support_basis, SupportBasis):
            raise ContractViolation("support_basis must be typed")
        if not isinstance(self.resolution_authority, ResolutionAuthority):
            raise ContractViolation("resolution_authority must be typed")
        for name in ("observed_fraction", "reconstructed_fraction"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not 0.0 <= float(value) <= 1.0
            ):
                raise ContractViolation(f"{name} out of bounds: {value}")
        if not isinstance(self.overlap_allowed, bool):
            raise ContractViolation("overlap_allowed must be boolean")
        if not isinstance(self.overlap_mask_ref, str):
            raise ContractViolation("overlap_mask_ref must be a string")
        if self.observed_fraction + self.reconstructed_fraction > 1.0 + 1e-9:
            if not self.overlap_allowed:
                raise ContractViolation("observed_and_reconstructed_fractions_overlap")
            if not self.overlap_mask_ref.strip():
                raise ContractViolation("overlap_allowed requires overlap_mask_ref")

        if self.effective_scientific_resolution_m < self.native_observation_resolution_m:
            if self.resolution_authority not in (ResolutionAuthority.HOLDOUT_VALIDATED, ResolutionAuthority.FIELD_APPROVED):
                raise ContractViolation(
                    "effective_scientific_resolution_m finer than native requires "
                    "resolution_authority >= HOLDOUT_VALIDATED"
                )
            if not isinstance(
                self.validation_proof, ResolutionValidationProof
            ):
                raise ContractViolation("finer effective resolution requires ResolutionValidationProof")
            self.validation_proof.validate()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grid_spacing_m": float(self.grid_spacing_m),
            "native_observation_resolution_m": float(
                self.native_observation_resolution_m
            ),
            "effective_scientific_resolution_m": float(
                self.effective_scientific_resolution_m
            ),
            "display_resolution_m": float(self.display_resolution_m),
            "transformation_class": self.transformation_class.value,
            "support_basis": self.support_basis.value,
            "resolution_authority": self.resolution_authority.value,
            "validation_ref": self.validation_ref,
            "validation_proof": (
                self.validation_proof.to_dict()
                if self.validation_proof is not None else None
            ),
            "observed_fraction": float(self.observed_fraction),
            "reconstructed_fraction": float(self.reconstructed_fraction),
            "overlap_allowed": self.overlap_allowed,
            "overlap_mask_ref": self.overlap_mask_ref,
        }


DEFAULT_10M_RESOLUTION = ResolutionContract(
    grid_spacing_m=10.0,
    native_observation_resolution_m=10.0,
    effective_scientific_resolution_m=10.0,
    display_resolution_m=10.0,
    transformation_class=TransformationClass.NATIVE_GRID,
    resolution_authority=ResolutionAuthority.DIAGNOSTIC_ONLY,
)

CURRENT_EXPERIMENTAL_RESOLUTION = ResolutionContract(
    grid_spacing_m=2.5,
    native_observation_resolution_m=10.0,
    effective_scientific_resolution_m=10.0,
    display_resolution_m=2.5,
    transformation_class=TransformationClass.MODEL_ASSISTED_RASTER,
    resolution_authority=ResolutionAuthority.DIAGNOSTIC_ONLY,
)
