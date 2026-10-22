"""
State Evidence Support Contract
================================
Centralized classification for ASMAE state support ledger entries.
Categorizes evidence into:
  - DIRECTLY_ASSIMILATED
  - PROXY_ASSIMILATED
  - INDIRECTLY_CONSTRAINED
  - PRIOR_CONSTRAINED
  - UNSUPPORTED
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple, List
from .exceptions import ContractViolation
from .state_status import StateSupportStatus


class ObservationRelationship(str, Enum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    PROXY = "proxy"
    NONE = "none"


class StateEvidenceClass(str, Enum):
    DIRECTLY_ASSIMILATED = "directly_assimilated"
    PROXY_ASSIMILATED = "proxy_assimilated"
    INDIRECTLY_CONSTRAINED = "indirectly_constrained"
    PRIOR_CONSTRAINED = "prior_constrained"
    UNSUPPORTED = "unsupported"


@dataclass
class StateSupportRecord:
    state: str
    support_status: StateSupportStatus = StateSupportStatus.PRIOR_CONSTRAINED
    observation_relationship: ObservationRelationship = ObservationRelationship.NONE
    source_feature_ids: Tuple[str, ...] = ()
    accepted_update_count: int = 0
    direct_observation_count: int = 0
    proxy_observation_count: int = 0
    prior_variance: Optional[float] = None
    posterior_variance: Optional[float] = None
    information_gain: Optional[float] = None
    spatial_support: str = "none"
    authority_ceiling: str = "DIAGNOSTIC"
    block_reasons: Tuple[str, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.accepted_update_count, int) or self.accepted_update_count < 0:
            raise ContractViolation(f"nonnegative_integer:{self.state}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "support_status": self.support_status.value if hasattr(self.support_status, "value") else str(self.support_status),
            "observation_relationship": self.observation_relationship.value if hasattr(self.observation_relationship, "value") else str(self.observation_relationship),
            "source_feature_ids": list(self.source_feature_ids),
            "accepted_update_count": self.accepted_update_count,
            "direct_observation_count": self.direct_observation_count,
            "proxy_observation_count": self.proxy_observation_count,
            "prior_variance": self.prior_variance,
            "posterior_variance": self.posterior_variance,
            "information_gain": self.information_gain,
            "spatial_support": self.spatial_support,
            "authority_ceiling": self.authority_ceiling,
            "block_reasons": list(self.block_reasons),
        }


def _attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        val = obj.get(key, default)
    else:
        val = getattr(obj, key, default)
    if hasattr(val, "value"):
        return val.value
    return val


def resolve_state_evidence_class(ledger_entry: Any) -> StateEvidenceClass:
    """Resolve single state support record into standard StateEvidenceClass.

    Checks direct_observation_count, proxy_observation_count, accepted_update_count,
    and support_status.
    """
    if not ledger_entry:
        return StateEvidenceClass.UNSUPPORTED

    support_status = str(_attr(ledger_entry, "support_status", "") or "").lower()
    if support_status in ("unsupported", "blocked", "failed", "revoked", "none"):
        return StateEvidenceClass.UNSUPPORTED

    block_reasons = _attr(ledger_entry, "block_reasons", ()) or ()
    if any(r in ("local_support_revoked", "support_revoked", "evidence_revoked", "blocked") for r in block_reasons):
        return StateEvidenceClass.UNSUPPORTED

    direct_count = int(_attr(ledger_entry, "direct_observation_count", 0) or 0)
    proxy_count = int(_attr(ledger_entry, "proxy_observation_count", 0) or 0)
    accepted_updates = int(_attr(ledger_entry, "accepted_update_count", 0) or 0)
    evidence_kind = str(_attr(ledger_entry, "evidence_kind", "") or "").lower()
    relationship = str(
        _attr(ledger_entry, "observation_relationship", "none") or "none"
    ).lower()

    if accepted_updates > 0 or support_status in ("assimilated", "supported", "active"):
        if (
            relationship == ObservationRelationship.DIRECT.value
            or direct_count > 0
            or evidence_kind == "direct_observation"
        ):
            return StateEvidenceClass.DIRECTLY_ASSIMILATED
        elif (
            relationship == ObservationRelationship.PROXY.value
            or proxy_count > 0
            or evidence_kind == "proxy_observation"
        ):
            return StateEvidenceClass.PROXY_ASSIMILATED
        elif (
            relationship == ObservationRelationship.INDIRECT.value
            or evidence_kind in ("indirect_observation", "model_propagation")
        ):
            return StateEvidenceClass.INDIRECTLY_CONSTRAINED
        else:
            return StateEvidenceClass.PROXY_ASSIMILATED

    if support_status in ("prior_constrained", "prior_only", "baseline"):
        return StateEvidenceClass.PRIOR_CONSTRAINED

    if support_status in (
        "temporally_conditioned",
        "spatially_conditioned",
        "model_propagated",
    ):
        return StateEvidenceClass.INDIRECTLY_CONSTRAINED

    if direct_count == 0 and proxy_count == 0 and accepted_updates == 0:
        return StateEvidenceClass.PRIOR_CONSTRAINED

    return StateEvidenceClass.UNSUPPORTED
