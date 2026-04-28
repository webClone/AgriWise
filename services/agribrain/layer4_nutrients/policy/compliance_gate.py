
from typing import Dict, Any, Tuple, List
from layer4_nutrients.schema import ApplicationMethod, Prescription, EnvironmentalRisk
from layer3_decision.schema import PlotContext

class ComplianceGate:
    """
    Shared Research-Grade Policy Engine.
    Enforces invariant C: Leaching Risk Gating and Environmental Safety.
    Returns:
        - is_allowed (bool)
        - blocked_reasons (List[str])
        - environmental_risks (EnvironmentalRisk)
    """
    
    def check_compliance(self, 
                         product: str, 
                         rate: float, 
                         method: ApplicationMethod, 
                         swb_out: Dict[str, Any], 
                         context: PlotContext) -> Tuple[bool, List[str], EnvironmentalRisk]:
        
        allowed = True
        reasons = []
        
        leaching_idx = swb_out.get("leaching_risk_index", 0.0)
        
        # 1. Leaching Risk (Invariant C)
        if leaching_idx > 0.6:
            # High Leaching Risk -> Block Heavy Broadcast
            if method == ApplicationMethod.BROADCAST and rate > 50.0:
                allowed = False
                reasons.append("LeachingRisk_BroadcastBlocked")
            elif method == ApplicationMethod.FERTIGATION:
                # Fertigation is safer but reduce rate?
                pass
                
        # 2. Runoff Risk
        # Mock Check
        runoff_risk = 0.0 # Placeholder
        
        # 3. Quota Constraints
        quota_n = context.constraints.get("nitrogen_limit_kg_ha")
        if quota_n is not None:
            if rate > quota_n:
                allowed = False
                reasons.append(f"QuotaExceeded_Limit{quota_n}")
                
        env_risks = EnvironmentalRisk(
            leaching=min(1.0, max(0.0, leaching_idx)),
            runoff=min(1.0, max(0.0, runoff_risk)),
            volatilization=0.0
        )
        
        return allowed, reasons, env_risks
