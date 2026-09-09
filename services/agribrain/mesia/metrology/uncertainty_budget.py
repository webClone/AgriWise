"""MESIA Metrology — ISO GUM Compliant Uncertainty Budget Framework — R6 §1.6 & §10.4.

Implements Type A (statistical) and Type B (instrument/manufacturer/calibration)
uncertainty evaluation, combined standard uncertainty, Welch-Satterthwaite effective
degrees of freedom, and expanded uncertainty reporting.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DistributionType(str, Enum):
    """Probability distribution assumed for Type B uncertainty evaluation."""
    NORMAL = "NORMAL"                # Divisor = 1.0 (or 2.0 if given as k=2)
    RECTANGULAR = "RECTANGULAR"      # Divisor = sqrt(3) ~= 1.73205
    TRIANGULAR = "TRIANGULAR"        # Divisor = sqrt(6) ~= 2.44949
    U_SHAPED = "U_SHAPED"            # Divisor = sqrt(2) ~= 1.41421 (e.g. thermal/mismatch)


@dataclass(frozen=True)
class UncertaintyComponent:
    """Individual uncertainty contribution source."""

    source_name: str
    evaluation_type: str
    """'TYPE_A' (empirical/statistical) or 'TYPE_B' (calibration cert/datasheet)."""

    distribution: DistributionType
    semi_range: float
    """Value or semi-range (+/- a)."""

    divisor: float = 1.0
    sensitivity_coefficient: float = 1.0
    degrees_of_freedom: Optional[float] = None
    """None or float('inf') for Type B where unknown."""

    unit: str = "dB"
    description: str = ""

    @property
    def standard_uncertainty(self) -> float:
        """Calculate standard uncertainty u_i = semi_range / divisor."""
        d = self.divisor if self.divisor > 0 else 1.0
        return abs(self.semi_range) / d

    @property
    def weighted_uncertainty(self) -> float:
        """Contribution c_i * u_i."""
        return self.sensitivity_coefficient * self.standard_uncertainty

    def to_dict(self) -> Dict[str, Any]:
        dof = self.degrees_of_freedom
        if dof is not None and math.isinf(dof):
            dof = None
        return {
            "source_name": self.source_name,
            "evaluation_type": self.evaluation_type,
            "distribution": self.distribution.value,
            "semi_range": self.semi_range,
            "divisor": self.divisor,
            "standard_uncertainty": self.standard_uncertainty,
            "sensitivity_coefficient": self.sensitivity_coefficient,
            "weighted_uncertainty": self.weighted_uncertainty,
            "degrees_of_freedom": dof,
            "unit": self.unit,
            "description": self.description,
        }


def make_type_b_component(
    source_name: str,
    semi_range: float,
    distribution: DistributionType = DistributionType.RECTANGULAR,
    sensitivity_coefficient: float = 1.0,
    unit: str = "dB",
    description: str = "",
) -> UncertaintyComponent:
    """Factory helper to create a standard Type B uncertainty component."""
    if distribution == DistributionType.RECTANGULAR:
        divisor = math.sqrt(3.0)
    elif distribution == DistributionType.TRIANGULAR:
        divisor = math.sqrt(6.0)
    elif distribution == DistributionType.U_SHAPED:
        divisor = math.sqrt(2.0)
    else:
        divisor = 1.0

    return UncertaintyComponent(
        source_name=source_name,
        evaluation_type="TYPE_B",
        distribution=distribution,
        semi_range=semi_range,
        divisor=divisor,
        sensitivity_coefficient=sensitivity_coefficient,
        degrees_of_freedom=float("inf"),
        unit=unit,
        description=description,
    )


def make_type_a_component(
    source_name: str,
    sample_values: List[float],
    sensitivity_coefficient: float = 1.0,
    unit: str = "dB",
    description: str = "",
) -> UncertaintyComponent:
    """Factory helper to create a statistical Type A uncertainty component from measurements."""
    n = len(sample_values)
    if n < 2:
        raise ValueError("Type A evaluation requires at least 2 sample values.")
    mean = sum(sample_values) / n
    variance = sum((x - mean) ** 2 for x in sample_values) / (n - 1)
    sample_std = math.sqrt(variance)
    std_error = sample_std / math.sqrt(n)

    return UncertaintyComponent(
        source_name=source_name,
        evaluation_type="TYPE_A",
        distribution=DistributionType.NORMAL,
        semi_range=std_error,
        divisor=1.0,
        sensitivity_coefficient=sensitivity_coefficient,
        degrees_of_freedom=float(n - 1),
        unit=unit,
        description=description or f"Mean={mean:.4f}, n={n}, std={sample_std:.4f}",
    )


@dataclass(frozen=True)
class UncertaintyBudget:
    """Complete GUM-compliant uncertainty budget for a measurement."""

    budget_id: str
    measurand_name: str
    components: List[UncertaintyComponent] = field(default_factory=list)
    confidence_level_pct: float = 95.0
    default_coverage_factor: float = 2.0
    unit: str = "dB"

    @property
    def combined_standard_uncertainty(self) -> float:
        """Combined standard uncertainty u_c = sqrt( sum( (c_i * u_i)^2 ) )."""
        if not self.components:
            return 0.0
        sum_sq = sum(c.weighted_uncertainty ** 2 for c in self.components)
        return math.sqrt(sum_sq)

    @property
    def effective_degrees_of_freedom(self) -> float:
        """Welch-Satterthwaite formula: nu_eff = u_c^4 / sum( (c_i*u_i)^4 / nu_i )."""
        u_c = self.combined_standard_uncertainty
        if u_c == 0.0:
            return float("inf")

        u_c_4 = u_c ** 4
        denom = 0.0
        for c in self.components:
            nu_i = c.degrees_of_freedom
            if nu_i is None or math.isinf(nu_i) or nu_i <= 0:
                continue
            denom += (c.weighted_uncertainty ** 4) / nu_i

        if denom == 0.0:
            return float("inf")
        return u_c_4 / denom

    @property
    def coverage_factor(self) -> float:
        """Returns coverage factor k (default 2.0 for normal ~95% confidence)."""
        return self.default_coverage_factor

    @property
    def expanded_uncertainty(self) -> float:
        """Expanded uncertainty U = k * u_c."""
        return self.coverage_factor * self.combined_standard_uncertainty

    def to_dict(self) -> Dict[str, Any]:
        eff_dof = self.effective_degrees_of_freedom
        if math.isinf(eff_dof):
            eff_dof = None
        return {
            "budget_id": self.budget_id,
            "measurand_name": self.measurand_name,
            "combined_standard_uncertainty": self.combined_standard_uncertainty,
            "effective_degrees_of_freedom": eff_dof,
            "coverage_factor": self.coverage_factor,
            "expanded_uncertainty": self.expanded_uncertainty,
            "confidence_level_pct": self.confidence_level_pct,
            "unit": self.unit,
            "components": [c.to_dict() for c in self.components],
        }

    def content_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
