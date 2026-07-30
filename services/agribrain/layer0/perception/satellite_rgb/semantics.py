"""
Satellite RGB Variable Semantics — V1 Frozen Definitions.

  READ THIS BEFORE USING SATELLITE RGB VARIABLES DOWNSTREAM.

This module documents the precise, frozen meaning of every variable
produced by the Satellite RGB V1 engine.

WHY THIS EXISTS
---------------
Semantic drift is the primary risk for V1. Once these variables flow
into Layer 1 fusion prompts and advisory text, later layers will start
treating them as biophysical truth unless their meaning is locked now.

THE RULE
--------
Each variable below has:
  - a precise definition (what it IS)
  - what it is NOT (common misuse to prevent)
  - the observation model it maps to in the Kalman filter
  - its sigma range and reliability ceiling in V1

DO NOT weaken these definitions without updating all downstream consumers.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class VariableSemantics:
    """Frozen semantic definition for one satellite RGB output variable."""
    name: str
    definition: str          # what it IS
    not_definition: str      # common misuse to prevent
    kalman_obs_type: str     # maps to this obs_type in observation_model.py
    base_sigma: float        # before QA inflation
    reliability_ceiling: float  # max Kalman reliability weight from this source
    unit: str
    version_frozen: str = "v1"
    row_detection: bool = False  # deferred to V1.5


VARIABLE_SEMANTICS: dict[str, VariableSemantics] = {

    "vegetation_fraction": VariableSemantics(
        name="vegetation_fraction",
        definition=(
            "Fraction of in-plot pixels (inside polygon, excluding boundary margin) "
            "segmented as vegetation by the Excess Green Index (ExG) threshold. "
            "Value 0–1. 1.0 = all inside pixels appear vegetated."
        ),
        not_definition=(
            "NOT LAI. NOT NDVI. NOT canopy biomass. NOT a biophysical variable. "
            "It is a pixel-counting ratio from RGB thresholding. "
            "It cannot distinguish healthy dense canopy from dense weeds. "
            "It cannot detect sparse but healthy canopy."
        ),
        kalman_obs_type="vegetation_fraction",
        base_sigma=0.12,
        reliability_ceiling=0.85,
        unit="fraction [0, 1]",
    ),

    "bare_soil_fraction": VariableSemantics(
        name="bare_soil_fraction",
        definition=(
            "Fraction of in-plot pixels segmented as bare soil by the Excess Green "
            "Index (ExG) threshold. Value 0–1. 1.0 = all inside pixels appear as bare soil. "
            "Auxiliary variable — not assimilated into Kalman state in V1."
        ),
        not_definition=(
            "NOT a soil type indicator. NOT organic matter. NOT soil moisture. "
            "NOT a fertilizer-need proxy. It is a pixel color ratio that correlates "
            "with exposed soil but cannot diagnose soil condition."
        ),
        kalman_obs_type="none_v1_auxiliary",  # not in Kalman in V1
        base_sigma=0.12,
        reliability_ceiling=0.0,  # not assimilated
        unit="fraction [0, 1]",
    ),

    "rgb_anomaly_score": VariableSemantics(
        name="rgb_anomaly_score",
        definition=(
            "Structural heterogeneity / sparse-canopy anomaly proxy. "
            "Fraction of in-plot pixels whose green-channel value deviates "
            "significantly (> 1.5 × std) from the plot mean green. "
            "High score = high within-plot variability = possible gaps or stress areas."
        ),
        not_definition=(
            "NOT a disease score. NOT a nutrient deficiency indicator. "
            "NOT a water stress score. NOT validated causal evidence. "
            "It is a structural heterogeneity proxy from RGB. "
            "The ValidationGraph must arbitrate this against NDVI / NDMI / SAR / weather "
            "before any advisory inference. Do not use in isolation."
        ),
        kalman_obs_type="rgb_anomaly_score",
        base_sigma=0.40,           # intentionally high — weak proxy
        reliability_ceiling=0.60,  # moderate ceiling; ValidationGraph arbitrates
        unit="score [0, 1]",
    ),

    "coarse_phenology_stage": VariableSemantics(
        name="coarse_phenology_stage",
        definition=(
            "Parcel-scale visual stage hint from green/brightness ratios of the RGB image. "
            "Mapped to the standard phenology scale: "
            "0=dormant, 1=vegetative, 2=flowering, 3=ripening, 4=senescence. "
            "Very coarse — uncertainty sigma = 0.80 by design."
        ),
        not_definition=(
            "NOT authoritative phenology. NOT crop-type-specific. "
            "NOT a replacement for GDD-based phenology from the process model. "
            "It is a visual hint. The Kalman filter weighs it very weakly "
            "(R = sigma² = 0.64) and the process model remains dominant. "
            "Do not display this to users as the crop stage."
        ),
        kalman_obs_type="phenology_stage",
        base_sigma=0.80,           # very high — hint, not measurement
        reliability_ceiling=0.40,  # low ceiling; process model dominates
        unit="stage_float [0, 4]",
    ),

    "boundary_contamination_score": VariableSemantics(
        name="boundary_contamination_score",
        definition=(
            "Fraction of inside-polygon pixels that are within the edge zone "
            "(boundary_width pixels from the polygon boundary). "
            "High score = the analysis is dominated by boundary pixels, "
            "which may include neighboring fields, roads, or hedgerows."
        ),
        not_definition=(
            "NOT a data quality flag (it is a measurement). "
            "NOT a signal of crop health. "
            "High boundary score means results should be interpreted with caution "
            "due to spatial contamination, not crop condition."
        ),
        kalman_obs_type="none_metadata",  # metadata; not assimilated
        base_sigma=0.05,
        reliability_ceiling=0.0,
        unit="fraction [0, 1]",
    ),
}


def get_semantics(variable_name: str) -> Optional[VariableSemantics]:
    """Look up the frozen semantics for a satellite RGB variable."""
    return VARIABLE_SEMANTICS.get(variable_name)


def assert_not_biophysical(variable_name: str) -> None:
    """
    Raise an informative error if someone tries to use a structural proxy
    as a hard biophysical measurement.

    Call this in any downstream code that maps satellite RGB variables
    to user-facing agronomic statements.
    """
    sem = get_semantics(variable_name)
    if sem and sem.reliability_ceiling < 0.70:
        raise ValueError(
            f"Variable '{variable_name}' is a weak structural proxy "
            f"(reliability ceiling={sem.reliability_ceiling}). "
            f"It must not be used as a direct biophysical measurement. "
            f"Definition: {sem.definition}. "
            f"NOT: {sem.not_definition}"
        )
