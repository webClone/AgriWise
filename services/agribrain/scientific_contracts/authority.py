"""Scientific Contracts — Authority Vector & Scientific Product Envelope.

Isolated from world_model and layer packages.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from .exceptions import ContractViolation


class ProductClass(str, Enum):
    """Scientific product hierarchy class (descriptive, not permissions)."""
    M0_RAW_MEASUREMENT = "M0_RAW_MEASUREMENT"
    C1_CALIBRATED_OBSERVATION = "C1_CALIBRATED_OBSERVATION"
    B1_BELIEF_STATE = "B1_BELIEF_STATE"
    R2_RESOLVED_MAP = "R2_RESOLVED_MAP"
    D3_DIAGNOSTIC_ADVISORY = "D3_DIAGNOSTIC_ADVISORY"
    P3_PRESCRIPTION_DRIVER = "P3_PRESCRIPTION_DRIVER"
    A4_AUTHORIZED_ACTION = "A4_AUTHORIZED_ACTION"


class EpistemicReality(str, Enum):
    PHYSICAL_MEASUREMENT = "PHYSICAL_MEASUREMENT"
    ASSIMILATED_STATE = "ASSIMILATED_STATE"
    MODEL_PROJECTION = "MODEL_PROJECTION"
    EXPERT_HEURISTIC = "EXPERT_HEURISTIC"


class SpatialSupport(str, Enum):
    PIXEL_NATIVE = "PIXEL_NATIVE"
    SUB_GRID = "SUB_GRID"
    PLOT = "PLOT"
    ZONE = "ZONE"
    REGIONAL = "REGIONAL"


class ProductRole(str, Enum):
    STATE = "STATE"
    DIAGNOSTIC = "DIAGNOSTIC"
    PRESCRIPTION = "PRESCRIPTION"
    EXECUTION = "EXECUTION"


class OperationalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    DEPRECATED = "DEPRECATED"
    REJECTED = "REJECTED"


class AuthorityScope(str, Enum):
    """Authority governance scopes differentiating research, shadow, and operational decision rights."""
    RESEARCH_ONLY = "RESEARCH_ONLY"
    OPERATIONAL_SHADOW = "OPERATIONAL_SHADOW"
    OPERATIONAL_DECISION = "OPERATIONAL_DECISION"
    SAFETY_COURT_VERIFIED = "SAFETY_COURT_VERIFIED"


@dataclass(frozen=True)
class AuthorityVector:
    """Pure permission gates object. Monotone non-increasing across transformations."""
    visualization_allowed: bool = False
    state_update_allowed: bool = False
    diagnosis_allowed: bool = False
    training_allowed: bool = False
    prescription_driver_allowed: bool = False
    insurance_allowed: bool = False
    machine_execution_allowed: bool = False

    def demote(
        self,
        *,
        visualization_allowed: Optional[bool] = None,
        state_update_allowed: Optional[bool] = None,
        diagnosis_allowed: Optional[bool] = None,
        training_allowed: Optional[bool] = None,
        prescription_driver_allowed: Optional[bool] = None,
        insurance_allowed: Optional[bool] = None,
        machine_execution_allowed: Optional[bool] = None,
    ) -> "AuthorityVector":
        """Produce a demoted AuthorityVector. Cannot promote any field."""
        new_vis = self.visualization_allowed if visualization_allowed is None else bool(visualization_allowed)
        new_upd = self.state_update_allowed if state_update_allowed is None else bool(state_update_allowed)
        new_diag = self.diagnosis_allowed if diagnosis_allowed is None else bool(diagnosis_allowed)
        new_trn = self.training_allowed if training_allowed is None else bool(training_allowed)
        new_pre = self.prescription_driver_allowed if prescription_driver_allowed is None else bool(prescription_driver_allowed)
        new_ins = self.insurance_allowed if insurance_allowed is None else bool(insurance_allowed)
        new_exe = self.machine_execution_allowed if machine_execution_allowed is None else bool(machine_execution_allowed)

        if new_vis and not self.visualization_allowed:
            raise ContractViolation("Authority promotion not allowed: visualization_allowed")
        if new_upd and not self.state_update_allowed:
            raise ContractViolation("Authority promotion not allowed: state_update_allowed")
        if new_diag and not self.diagnosis_allowed:
            raise ContractViolation("Authority promotion not allowed: diagnosis_allowed")
        if new_trn and not self.training_allowed:
            raise ContractViolation("Authority promotion not allowed: training_allowed")
        if new_pre and not self.prescription_driver_allowed:
            raise ContractViolation("Authority promotion not allowed: prescription_driver_allowed")
        if new_ins and not self.insurance_allowed:
            raise ContractViolation("Authority promotion not allowed: insurance_allowed")
        if new_exe and not self.machine_execution_allowed:
            raise ContractViolation("Authority promotion not allowed: machine_execution_allowed")

        return AuthorityVector(
            visualization_allowed=new_vis,
            state_update_allowed=new_upd,
            diagnosis_allowed=new_diag,
            training_allowed=new_trn,
            prescription_driver_allowed=new_pre,
            insurance_allowed=new_ins,
            machine_execution_allowed=new_exe,
        )


AUTHORITY_BLOCKED = AuthorityVector(
    visualization_allowed=False,
    state_update_allowed=False,
    diagnosis_allowed=False,
    training_allowed=False,
    prescription_driver_allowed=False,
    insurance_allowed=False,
    machine_execution_allowed=False,
)

AUTHORITY_VISUAL_ONLY_NO_DIAGNOSIS = AuthorityVector(
    visualization_allowed=True,
    state_update_allowed=False,
    diagnosis_allowed=False,
    training_allowed=False,
    prescription_driver_allowed=False,
    insurance_allowed=False,
    machine_execution_allowed=False,
)

AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE = AuthorityVector(
    visualization_allowed=True,
    state_update_allowed=False,
    diagnosis_allowed=True,
    training_allowed=False,
    prescription_driver_allowed=False,
    insurance_allowed=False,
    machine_execution_allowed=False,
)

AUTHORITY_ASSIMILATION_INPUT_APPROVED = AuthorityVector(
    visualization_allowed=True,
    state_update_allowed=True,
    diagnosis_allowed=True,
)

AUTHORITY_TRAINING_APPROVED = AuthorityVector(training_allowed=True)

AUTHORITY_PRESCRIPTION_DRIVER_APPROVED = AuthorityVector(
    visualization_allowed=True,
    diagnosis_allowed=True,
    prescription_driver_allowed=True,
)

AUTHORITY_MACHINE_EXECUTION_APPROVED = AuthorityVector(
    visualization_allowed=True,
    diagnosis_allowed=True,
    prescription_driver_allowed=True,
    machine_execution_allowed=True,
)

# Backward-compatible names now carry the narrow permissions their names imply.
AUTHORITY_VISUALIZATION_ONLY = AUTHORITY_VISUAL_ONLY_NO_DIAGNOSIS
AUTHORITY_DIAGNOSTIC = AUTHORITY_DIAGNOSTIC_NO_STATE_UPDATE


@dataclass(frozen=True)
class ScientificProductEnvelope:
    """Combines ProductClass with independent AuthorityVector and support metadata."""
    schema_version: str
    product_class: ProductClass
    epistemic_reality: EpistemicReality
    spatial_support: SpatialSupport
    product_role: ProductRole
    operational_status: OperationalStatus
    authority: AuthorityVector
    resolution_contract: Optional[Any] = None

    def validate(self) -> None:
        if self.authority.machine_execution_allowed and not self.authority.prescription_driver_allowed:
            raise ContractViolation("machine_execution_allowed requires prescription_driver_allowed")
        if self.authority.prescription_driver_allowed and not self.authority.diagnosis_allowed:
            raise ContractViolation("prescription_driver_allowed requires diagnosis_allowed")
