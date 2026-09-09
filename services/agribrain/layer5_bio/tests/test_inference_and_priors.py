import pytest
from layer5_bio.knowledge.dynamic_priors import compute_dynamic_priors
from layer5_bio.engines.inference import BioThreatInferenceEngine
from layer5_bio.schema import (
    ThreatId,
    ThreatClass,
    Severity,
    SpreadPattern,
    EvidenceLogit,
    Confounder,
)
from layer3_decision.schema import Driver


class DummyDiagnosis:
    def __init__(self, problem_id: str, probability: float):
        self.problem_id = problem_id
        self.probability = probability


class DummyL3Decision:
    def __init__(self, diagnoses):
        self.diagnoses = diagnoses


def test_dynamic_priors_phenology_and_climate():
    """Verify dynamic prior calculation across crops, phenology stages, and climate."""
    # Wheat in vegetative vs maturity stage
    priors_veg = compute_dynamic_priors(
        crop_type="wheat",
        phenology_stage="VEGETATIVE",
        climate_indicators={"tmean_7d": 18.0, "rain_sum_7d": 25.0},
        lat=36.0,
    )
    priors_mat = compute_dynamic_priors(
        crop_type="wheat",
        phenology_stage="MATURITY",
        climate_indicators={"tmean_7d": 28.0, "rain_sum_7d": 0.0},
        lat=36.0,
    )
    
    assert ThreatId.FUNGAL_RUST in priors_veg
    assert ThreatId.DOWNY_MILDEW in priors_veg
    # Wet/vegetative conditions elevate fungal priors over hot/dry maturity
    assert priors_veg[ThreatId.FUNGAL_RUST] > priors_mat[ThreatId.FUNGAL_RUST]


def test_biothreat_inference_belief_trust_separation():
    """Verify that probability reflects belief (logits) and confidence reflects trust (penalties)."""
    engine = BioThreatInferenceEngine()
    
    # Evidence with strong positive logit
    evidence = {
        ThreatId.FUNGAL_LEAF_SPOT: [
            EvidenceLogit(
                driver=Driver.NDVI,
                condition="Significant drop in canopy greenness",
                logit_delta=2.5,
                weight=1.0,
                source_refs={"delta_ndvi": -0.15},
            )
        ]
    }
    priors = {ThreatId.FUNGAL_LEAF_SPOT: 0.15}
    
    # Run with clean data and no confounders
    states = engine.infer_states(
        evidence_by_threat=evidence,
        spread={"pattern": SpreadPattern.PATCHY},
        priors=priors,
        l3_decision=None,
        wdp={"lwd_available": True, "lwd_consecutive_wet_days": 2},
        phenology_stage="VEGETATIVE",
        missing_drivers=[],
    )
    
    spot_state = states[ThreatId.FUNGAL_LEAF_SPOT.value]
    assert 0.0 <= spot_state.probability <= 1.0
    assert 0.0 <= spot_state.confidence <= 1.0
    assert spot_state.probability > 0.50  # Strong positive logit elevated probability
    assert spot_state.confidence >= 0.70  # Clean data maintains high trust


def test_inference_l3_confounder_gating():
    """Verify that water stress detected by Layer 3 penalizes confidence and flags confounder."""
    engine = BioThreatInferenceEngine()
    
    evidence = {
        ThreatId.FUNGAL_LEAF_SPOT: [
            EvidenceLogit(
                driver=Driver.NDVI,
                condition="Canopy drop",
                logit_delta=1.5,
                weight=1.0,
                source_refs={},
            )
        ]
    }
    priors = {ThreatId.FUNGAL_LEAF_SPOT: 0.10}
    
    # L3 confirms severe water stress (prob=0.85)
    l3_stressed = DummyL3Decision(diagnoses=[
        DummyDiagnosis("WATER_STRESS", 0.85)
    ])
    
    states = engine.infer_states(
        evidence_by_threat=evidence,
        spread={"pattern": SpreadPattern.UNIFORM},
        priors=priors,
        l3_decision=l3_stressed,
        wdp={"lwd_available": False},
        phenology_stage="VEGETATIVE",
        missing_drivers=[],
    )
    
    spot_state = states[ThreatId.FUNGAL_LEAF_SPOT.value]
    # Water stress must appear in confounders list
    assert Confounder.WATER_STRESS in spot_state.confounders
    # Confidence is penalized by 0.15 due to the confounding drought stress (1.0 - 0.15 = 0.85)
    assert spot_state.confidence <= 0.85
