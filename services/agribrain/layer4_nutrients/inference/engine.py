
import math
from typing import Dict, Any, List
from layer4_nutrients.schema import NutrientState, Severity, EvidenceLogit, Nutrient, Confounder
from layer3_decision.schema import Driver, DegradationMode

class NutrientInferenceEngine:
    """
    Layer 4.4: Inference Engine (Locked v4.0 Hardened)
    Objective: 
    - Probability = Belief from Evidence (Logits)
    - Confidence = Trust from Data Quality (Penalties)
    - Enums Used: Nutrient, Confounder
    """
    
    def _sigmoid(self, logit: float) -> float:
        return 1.0 / (1.0 + math.exp(-logit))

    def infer_states(self, 
                     evidence: Dict[str, Any], 
                     swb_out: Dict[str, Any], 
                     demands: Dict[str, Any],
                     l3_decision: Any) -> Dict[Nutrient, NutrientState]:
        
        states = {}
        
        # --- Nitrogen Inference ---
        # 1. Belief (Logits)
        logit_n = -2.0 # Prior
        trace_logits = []
        drivers_used = []
        
        # Evidence: NDVI Z-Score
        z = evidence.get("ndvi_stage_z", 0.0)
        drivers_used.append(Driver.NDVI)
        
        if z < -3.0:
            delta = 3.0 # Strong evidence for severe deficiency
            logit_n += delta
            trace_logits.append(EvidenceLogit(
                driver=Driver.NDVI, 
                condition=f"Severe Z {z:.2f} < -3.0", 
                logit_delta=delta, 
                weight=2.0,
                source_refs={"feature": "ndvi_stage_z", "value": z}
            ))
        elif z < -1.0:
            delta = 1.5
            logit_n += delta
            trace_logits.append(EvidenceLogit(
                driver=Driver.NDVI, 
                condition=f"Z-Score {z:.2f} < -1.0", 
                logit_delta=delta, 
                weight=1.0,
                source_refs={"feature": "ndvi_stage_z", "value": z}
            ))
        elif z > 0.5:
            delta = -1.0
            logit_n += delta
            trace_logits.append(EvidenceLogit(
                driver=Driver.NDVI, 
                condition=f"High Z {z:.2f}", 
                logit_delta=delta, 
                weight=1.0,
                source_refs={"feature": "ndvi_stage_z", "value": z}
            ))
            
        # Evidence: Growth
        growth = evidence.get("growth_adequacy", 1.0)
        if growth < 0.7:
            delta = 1.2
            logit_n += delta
            trace_logits.append(EvidenceLogit(
                driver=Driver.NDVI, 
                condition=f"Growth Stalled {growth:.2f}", 
                logit_delta=delta, 
                weight=1.0,
                source_refs={"feature": "growth_adequacy", "value": growth}
            ))
            
        # Evidence: Leaching (SWB)
        leaching = swb_out.get("leaching_risk_index", 0.0)
        if leaching > 0.6:
            delta = 0.8
            logit_n += delta
            trace_logits.append(EvidenceLogit(
                driver=Driver.RAIN, 
                condition="High Leaching Risk", 
                logit_delta=delta, 
                weight=1.0,
                source_refs={"feature": "leaching_risk_index", "value": leaching}
            ))
            drivers_used.append(Driver.RAIN)
            
        # Final Probability
        prob_n = self._sigmoid(logit_n)
        
        # 2. Confidence (Trust)
        conf = 1.0
        confounders: List[Confounder] = []
        
        # Confounder: Water Stress
        water_stress = swb_out.get("water_stress_index", 0.0)
        
        l3_water_prob = 0.0
        if l3_decision and hasattr(l3_decision, "diagnoses"):
            for d in l3_decision.diagnoses:
                if d.problem_id == "WATER_STRESS":
                    l3_water_prob = d.probability
        
        effective_water_stress = max(water_stress, l3_water_prob)
        
        if effective_water_stress > 0.4:
            # Water stress acts as a confounded gate on CONFIDENCE
            conf -= 0.4 
            confounders.append(Confounder.WATER_STRESS)
            
        if evidence.get("heterogeneity_flag"):
            conf -= 0.1
            confounders.append(Confounder.SPATIAL_HETEROGENEITY)
            
        conf = max(0.1, conf)
        
        # 3. Severity & State Index
        state_index = -1.0 * prob_n 
        
        severity = Severity.LOW
        if prob_n > 0.6: severity = Severity.MODERATE
        if prob_n > 0.8: severity = Severity.HIGH
        
        # Construct State
        n_state = NutrientState(
            nutrient=Nutrient.N,
            state_index=state_index,
            probability_deficient=prob_n,
            confidence=conf,
            severity=severity,
            drivers_used=drivers_used,
            evidence_trace=trace_logits,
            confounders=confounders,
            notes="Inferred via Bayesian Log-Odds"
        )
        
        states[Nutrient.N] = n_state
        
        # Placeholders
        states[Nutrient.P] = NutrientState(Nutrient.P, 0.0, 0.1, 0.5, Severity.LOW, [], [], [], "Placeholder")
        states[Nutrient.K] = NutrientState(Nutrient.K, 0.0, 0.1, 0.5, Severity.LOW, [], [], [], "Placeholder")
        
        return states
