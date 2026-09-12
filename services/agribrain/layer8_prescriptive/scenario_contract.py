"""
Layer 8 Scenario Contract — Strongly Typed Counterfactual Intervention Candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple


class ScenarioType(str, Enum):
    """Semantic type of candidate scenario evaluated by prescriptive planning."""
    CROP_SELECTION = "CROP_SELECTION"               # Strategic seasonal crop/rotation choice (from L7)
    IRRIGATION_INTERVENTION = "IRRIGATION_INTERVENTION" # Root-zone moisture replenishment
    NUTRIENT_INTERVENTION = "NUTRIENT_INTERVENTION"     # Nitrogen/phosphorus variable-rate application
    DISEASE_TREATMENT = "DISEASE_TREATMENT"         # Fungicide/pesticide canopy spray
    MEASUREMENT_SCOUTING = "MEASUREMENT_SCOUTING"   # Ground sensor/scout dispatch


@dataclass(frozen=True)
class InterventionScenarioCandidate:
    """Strongly typed counterfactual intervention candidate for Layer 8 prescriptive optimization."""
    scenario_id: str
    scenario_type: ScenarioType
    action_type: str                            # e.g. "NO_ACTION", "IRRIGATE", "APPLY_N", "SCOUT"
    assumed_state: Mapping[str, Any]            # State assumed prior to intervention
    weather_scenario: Mapping[str, Any]         # Expected atmospheric conditions / forecast
    management_params: Mapping[str, Any]        # Proposed rates, depths, or timings
    expected_outcomes: Mapping[str, float]      # Projected yield delta, stress reduction, etc.
    constraints: Mapping[str, Any]              # Operational & environmental constraints
    uncertainty: Mapping[str, float]            # Posterior outcome variance or confidence
    is_reversible: bool                         # Whether physical effects can be undone
    required_evidence: Tuple[str, ...]          # Precondition evidence keys
    validity_domain: Mapping[str, Any]          # Soil, crop, or weather applicability domain

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_type": self.scenario_type.value,
            "action_type": self.action_type,
            "assumed_state": dict(self.assumed_state),
            "weather_scenario": dict(self.weather_scenario),
            "management_params": dict(self.management_params),
            "expected_outcomes": dict(self.expected_outcomes),
            "constraints": dict(self.constraints),
            "uncertainty": dict(self.uncertainty),
            "is_reversible": self.is_reversible,
            "required_evidence": list(self.required_evidence),
            "validity_domain": dict(self.validity_domain),
        }

    @classmethod
    def from_crop_planning_option(cls, option: Any, index: int = 0) -> InterventionScenarioCandidate:
        """Convert an upstream Layer 7 crop planning option into a typed CROP_SELECTION candidate."""
        opt_id = getattr(option, "option_id", getattr(option, "crop_type", f"crop_opt_{index}"))
        crop_name = getattr(option, "crop_type", getattr(option, "name", "unknown"))
        expected_yield = float(getattr(option, "expected_yield", getattr(option, "expected_profit", 1.0)))
        return cls(
            scenario_id=f"SCN-CROP-{opt_id}",
            scenario_type=ScenarioType.CROP_SELECTION,
            action_type="SELECT_CROP_ROTATION",
            assumed_state={"target_crop": crop_name},
            weather_scenario={"scenario_source": "seasonal_normal"},
            management_params={"crop_choice": crop_name},
            expected_outcomes={"expected_yield_relative": expected_yield},
            constraints={"seasonal_window": True},
            uncertainty={"outcome_sigma": 0.20},
            is_reversible=False,
            required_evidence=("crop_history", "soil_type"),
            validity_domain={"crop_suitability": True},
        )
