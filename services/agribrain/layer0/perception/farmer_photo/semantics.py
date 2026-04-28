"""
Farmer Photo Variable Semantics — V1 Frozen Definitions.

  READ THIS BEFORE USING FARMER PHOTO VARIABLES DOWNSTREAM.

These definitions lock the precise meaning of every variable
produced by the Farmer Photo V1 engine.

THE RULE: This is a plant recognition + symptom evidence engine.
It is NOT a disease detector. It is NOT a plot-wide canopy sensor.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class VariableSemantics:
    """Frozen semantic definition for one farmer photo output variable."""
    name: str
    definition: str
    not_definition: str
    kalman_obs_type: str
    base_sigma: float
    reliability_ceiling: float
    unit: str
    scope: str = "point"
    version_frozen: str = "v1"


VARIABLE_SEMANTICS: dict[str, VariableSemantics] = {

    "local_canopy_cover": VariableSemantics(
        name="local_canopy_cover",
        definition=(
            "Close-range vegetation fraction from a single photo. "
            "Measures the fraction of green pixels in a close-range "
            "canopy view. Represents approximately 1-10 m² of ground."
        ),
        not_definition=(
            "NOT plot-wide canopy cover. NOT LAI. NOT NDVI. "
            "A single photo of one corner of a field cannot represent "
            "the canopy state of the entire 5-hectare plot. "
            "The Kalman filter treats this as one local observation."
        ),
        kalman_obs_type="canopy_cover",
        base_sigma=0.12,
        reliability_ceiling=0.75,
        unit="fraction [0, 1]",
        scope="point",
    ),

    "disease_symptom_prob": VariableSemantics(
        name="disease_symptom_prob",
        definition=(
            "Probability that the photographed plant tissue shows "
            "visible stress symptoms (chlorosis, necrosis, spots, etc.). "
            "This is a SYMPTOM probability, not a disease diagnosis. "
            "The symptom class and disease candidate are auxiliary metadata."
        ),
        not_definition=(
            "NOT a disease diagnosis. NOT a treatment recommendation. "
            "NOT validated by pathology. A high symptom probability means "
            "the image shows color/texture anomalies consistent with stress. "
            "The actual cause could be disease, nutrient deficiency, water "
            "stress, mechanical damage, or misidentification."
        ),
        kalman_obs_type="stress_proxy",
        base_sigma=0.40,
        reliability_ceiling=0.50,
        unit="probability [0, 1]",
        scope="point",
    ),

    "local_stress_proxy": VariableSemantics(
        name="local_stress_proxy",
        definition=(
            "Symptom severity score from close-range photo. "
            "Derived from color deviation from healthy green. "
            "Zero = no visible stress. One = extreme visible stress."
        ),
        not_definition=(
            "NOT a biophysical stress measurement. NOT water potential. "
            "NOT chlorophyll content. It is a visual color anomaly score "
            "that correlates with stress but cannot identify the cause."
        ),
        kalman_obs_type="stress_proxy",
        base_sigma=0.35,
        reliability_ceiling=0.50,
        unit="score [0, 1]",
        scope="point",
    ),

    "phenology_stage_est": VariableSemantics(
        name="phenology_stage_est",
        definition=(
            "Coarse visual growth stage hint from one photo. "
            "Mapped to 0=dormant, 1=vegetative, 2=flowering, "
            "3=ripening, 4=senescence. Uncertainty sigma=1.0."
        ),
        not_definition=(
            "NOT authoritative phenology. NOT GDD-based. "
            "NOT crop-specific staging. It is a visual color hint "
            "with very high uncertainty. The process model and "
            "satellite-derived phenology are far more reliable."
        ),
        kalman_obs_type="phenology_stage",
        base_sigma=1.0,
        reliability_ceiling=0.35,
        unit="stage_float [0, 4]",
        scope="point",
    ),

    "plant_identity_confidence": VariableSemantics(
        name="plant_identity_confidence",
        definition=(
            "Composite confidence in crop + organ identification. "
            "Weighted average of crop classifier and organ classifier "
            "confidence. Auxiliary metadata — not assimilated into "
            "Kalman state."
        ),
        not_definition=(
            "NOT a crop classification result (that is crop_class). "
            "NOT assimilated. This is metadata about the engine's "
            "confidence in its own plant identification."
        ),
        kalman_obs_type="none_auxiliary",
        base_sigma=0.20,
        reliability_ceiling=0.0,
        unit="confidence [0, 1]",
        scope="point",
    ),
}


def get_semantics(variable_name: str) -> Optional[VariableSemantics]:
    """Look up the frozen semantics for a farmer photo variable."""
    return VARIABLE_SEMANTICS.get(variable_name)
