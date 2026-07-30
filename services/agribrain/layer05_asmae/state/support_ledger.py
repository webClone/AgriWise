"""R5.0: Per-variable evidence support ledger.

Design rules:
  1. Every state variable needs its own support assessment.
  2. The whole vector must NOT receive a single blanket label like ASSIMILATED.
  3. Diagnostic hypotheses cannot acquire direct-observation status.
  4. Metadata cannot enter dimensional uncertainty aggregation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .descriptors import (
    IdentifiabilityClass,
    AuthorityCeiling,
    StateDescriptor,
    STATE_DESCRIPTORS,
)


@dataclass(frozen=True)
class VariableSupport:
    """Evidence support assessment for a single state variable."""
    state_index: int
    canonical_name: str
    units: str

    # Evidence support
    direct_observation_sources: Tuple[str, ...] = ()
    indirect_observation_sources: Tuple[str, ...] = ()
    n_direct_observations: int = 0
    n_indirect_observations: int = 0
    latest_observation_age_days: Optional[float] = None

    # Identifiability and authority
    identifiability_class: IdentifiabilityClass = (
        IdentifiabilityClass.NOT_IDENTIFIED
    )
    authority_ceiling: AuthorityCeiling = AuthorityCeiling.VISUALIZATION
    block_reasons: Tuple[str, ...] = ()

    # Posterior uncertainty (in the variable's own units)
    posterior_mean: Optional[float] = None
    posterior_std: Optional[float] = None
    posterior_interval_80: Optional[Tuple[float, float]] = None

    # Transition model provenance
    transition_model_version: Optional[str] = None


@dataclass
class PerVariableSupportLedger:
    """Complete support ledger for all 13 state variables.

    Must be attached to every belief state snapshot. The ledger
    ensures that per-variable uncertainty is never averaged across
    incompatible units.
    """
    entries: Dict[str, VariableSupport] = field(default_factory=dict)
    schema_version: str = "support_ledger_v1"

    def set_support(self, support: VariableSupport) -> None:
        """Record support for one variable."""
        self.entries[support.canonical_name] = support

    def get_support(self, name: str) -> Optional[VariableSupport]:
        """Retrieve support for a variable by canonical name."""
        return self.entries.get(name)

    def all_supported_variables(self) -> List[str]:
        """Return names of variables with at least one observation source."""
        return [
            name for name, vs in self.entries.items()
            if vs.n_direct_observations > 0 or vs.n_indirect_observations > 0
        ]

    def validate(self) -> List[str]:
        """Check ledger invariants. Returns a list of violation messages."""
        violations = []
        for desc in STATE_DESCRIPTORS:
            entry = self.entries.get(desc.canonical_name)
            if entry is None:
                violations.append(
                    f"Missing support entry for state {desc.canonical_name}"
                )
                continue
            if entry.state_index != desc.index:
                violations.append(
                    f"Index mismatch for {desc.canonical_name}: "
                    f"ledger={entry.state_index}, descriptor={desc.index}"
                )
            if entry.units != desc.units:
                violations.append(
                    f"Unit mismatch for {desc.canonical_name}: "
                    f"ledger={entry.units!r}, descriptor={desc.units!r}"
                )
        return violations

    def to_dict(self) -> dict:
        """Serializable representation."""
        result = {"schema_version": self.schema_version, "entries": {}}
        for name, vs in self.entries.items():
            result["entries"][name] = {
                "state_index": vs.state_index,
                "canonical_name": vs.canonical_name,
                "units": vs.units,
                "direct_observation_sources": list(vs.direct_observation_sources),
                "indirect_observation_sources": list(vs.indirect_observation_sources),
                "n_direct_observations": vs.n_direct_observations,
                "n_indirect_observations": vs.n_indirect_observations,
                "latest_observation_age_days": vs.latest_observation_age_days,
                "identifiability_class": vs.identifiability_class.value,
                "authority_ceiling": vs.authority_ceiling.value,
                "block_reasons": list(vs.block_reasons),
                "posterior_mean": vs.posterior_mean,
                "posterior_std": vs.posterior_std,
                "posterior_interval_80": (
                    list(vs.posterior_interval_80)
                    if vs.posterior_interval_80 else None
                ),
                "transition_model_version": vs.transition_model_version,
            }
        return result
