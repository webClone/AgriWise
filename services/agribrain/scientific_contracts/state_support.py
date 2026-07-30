"""Canonical per-state support record shared by temporal and spatial ASMAE."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Dict, Optional, Tuple

from .exceptions import ContractViolation
from .state_status import StateSupportStatus


class ObservationRelationship(str, Enum):
    NONE = "none"
    DIRECT = "direct"
    INDIRECT = "indirect"
    PROXY = "proxy"


@dataclass(frozen=True)
class StateSupportRecord:
    state: str
    support_status: StateSupportStatus
    observation_relationship: ObservationRelationship = ObservationRelationship.NONE
    source_feature_ids: Tuple[str, ...] = ()
    accepted_update_count: int = 0
    prior_variance: Optional[float] = None
    posterior_variance: Optional[float] = None
    information_gain: Optional[float] = None
    spatial_support: str = "none"
    authority_ceiling: str = "DIAGNOSTIC"
    block_reasons: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.state, str) or not self.state.strip():
            raise ContractViolation("state_support_record_requires_state")
        if not isinstance(self.support_status, StateSupportStatus):
            raise ContractViolation("state_support_record_requires_typed_status")
        if not isinstance(
            self.observation_relationship, ObservationRelationship
        ):
            raise ContractViolation(
                "state_support_record_requires_typed_observation_relationship"
            )
        if isinstance(self.accepted_update_count, bool) or not isinstance(
            self.accepted_update_count, int
        ) or self.accepted_update_count < 0:
            raise ContractViolation("accepted_update_count_must_be_nonnegative_integer")
        if self.support_status is StateSupportStatus.ASSIMILATED:
            if self.accepted_update_count == 0:
                raise ContractViolation(
                    "assimilated_support_requires_accepted_update"
                )
            if self.observation_relationship is ObservationRelationship.NONE:
                raise ContractViolation(
                    "assimilated_support_requires_observation_relationship"
                )
        for name in ("prior_variance", "posterior_variance", "information_gain"):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ContractViolation(f"{name}_must_be_finite_number_or_none")
            if not math.isfinite(float(value)):
                raise ContractViolation(f"{name}_must_be_finite_number_or_none")
            if name != "information_gain" and float(value) < 0.0:
                raise ContractViolation(f"{name}_must_be_nonnegative")
        if not isinstance(self.source_feature_ids, tuple):
            raise ContractViolation("source_feature_ids_must_be_tuple")
        if any(not isinstance(item, str) or not item.strip() for item in self.source_feature_ids):
            raise ContractViolation("source_feature_ids_must_be_nonblank_strings")
        if not isinstance(self.spatial_support, str) or not self.spatial_support.strip():
            raise ContractViolation("spatial_support_must_not_be_blank")
        if not isinstance(self.authority_ceiling, str) or not self.authority_ceiling.strip():
            raise ContractViolation("authority_ceiling_must_not_be_blank")
        if not isinstance(self.block_reasons, tuple):
            raise ContractViolation("block_reasons_must_be_tuple")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "support_status": self.support_status.value,
            "observation_relationship": self.observation_relationship.value,
            "source_feature_ids": list(self.source_feature_ids),
            "accepted_update_count": int(self.accepted_update_count),
            "prior_variance": self.prior_variance,
            "posterior_variance": self.posterior_variance,
            "information_gain": self.information_gain,
            "spatial_support": self.spatial_support,
            "authority_ceiling": self.authority_ceiling,
            "block_reasons": list(self.block_reasons),
        }
