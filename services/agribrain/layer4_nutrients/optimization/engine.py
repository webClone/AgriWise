
import math
from typing import Dict, Any, List
from layer4_nutrients.schema import (
    Prescription, NutrientState, ActionId, ApplicationMethod, RiskIfWrong, 
    PrescriptionAudit, Severity, TimingWindow, SplitApplication, Nutrient
)
from layer3_decision.schema import PlotContext
from layer4_nutrients.policy.compliance_gate import ComplianceGate

class OptimizationEngine:
    """
    Layer 4.5: Optimization Engine (Locked v4.0 Hardened)
    Objective: Convert NutrientState -> Prescriptions
    """
    
    def __init__(self):
        self.crop_price_per_ton = 200.0 
        self.urea_cost_per_kg = 0.8
        self.n_content = 0.46
        self.ymax = 12.0
        self.c_coeff = 0.015
        self.n0 = 40.0
        
        self.gate = ComplianceGate()
        
    def optimize(self, 
                 states: Dict[Nutrient, NutrientState], 
                 swb_out: Dict[str, Any],
                 context: PlotContext) -> List[Prescription]:
        
        prescriptions = []
        n_state = states.get(Nutrient.N)
        if not n_state: return []
        
        # 1. Action Decision
        action_id = ActionId.MONITOR
        
        # Logic: High Probability of Deficiency (> 0.6)
        if n_state.probability_deficient > 0.6:
            action_id = ActionId.APPLY_N
        elif n_state.probability_deficient > 0.4:
            # Borderline -> Verify
            action_id = ActionId.VERIFY_ONLY
            
        if action_id == ActionId.MONITOR:
            return []
            
        optimal_rate = 0.0
        risk_level = RiskIfWrong.LOW
        
        # 2. Rate Optimization (if Intervening)
        if action_id == ActionId.APPLY_N:
            # Yield Response
            ratio = self.urea_cost_per_kg / self.crop_price_per_ton
            try:
                term = ratio / (self.ymax * self.c_coeff)
                n_rate = (-1.0 / self.c_coeff) * math.log(term) - self.n0
                n_rate = max(0, n_rate)
            except ValueError:
                n_rate = 0.0
                
            optimal_rate = n_rate / self.n_content
            
            # Confidence Check
            if n_state.confidence < 0.6:
                if n_state.severity == Severity.HIGH:
                     optimal_rate *= 0.5
                     risk_level = RiskIfWrong.HIGH
                else:
                    action_id = ActionId.VERIFY_ONLY
                    optimal_rate = 0.0
                    
        # 3. Compliance Check
        is_allowed = True
        blocked = []
        from layer4_nutrients.schema import EnvironmentalRisk
        env_risks = EnvironmentalRisk(0.0, 0.0, 0.0) 
        
        if optimal_rate > 0:
            allowed, reasons, risks = self.gate.check_compliance(
                "UREA", optimal_rate, ApplicationMethod.BROADCAST, swb_out, context
            )
            is_allowed = allowed
            blocked = reasons
            env_risks = risks
            
            if not is_allowed:
                risk_level = RiskIfWrong.HIGH
                
        # 4. Construct Prescription
        audit = PrescriptionAudit(
            crop_price=self.crop_price_per_ton,
            product_cost=self.urea_cost_per_kg,
            constraints_active=[str(k) for k in context.constraints.keys()],
            response_model="Mitscherlich",
            response_params={"ymax": self.ymax, "c": self.c_coeff, "n0": self.n0},
            objective="ProfitMax"
        )
        
        p = Prescription(
            action_id=action_id,
            rate_kg_ha=round(optimal_rate, 1), # Renamed field
            timing_window=TimingWindow(start_date="2025-06-15", end_date="2025-06-20"),
            splits=[], # Could add SplitApplication objs here
            method=ApplicationMethod.BROADCAST if optimal_rate > 0 else ApplicationMethod.NONE,
            risk_if_wrong=risk_level,
            preconditions=[],
            is_allowed=is_allowed,
            blocked_reason=blocked,
            environmental_risk=env_risks,
            audit=audit
        )
        
        prescriptions.append(p)
        return prescriptions
