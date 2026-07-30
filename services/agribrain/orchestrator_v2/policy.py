
from typing import Dict, Any

def collect_policy_snapshot(
    user_permissions: Dict[str, bool],
    global_constraints: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Builds a canonical dictionary of all policy rules active for this run.
    This dict is Hashed into the Run ID.
    If policy changes, Run ID changes -> Determinism.
    """
    
    # 1. Standardize Permissions
    perms = {k: bool(v) for k, v in user_permissions.items()}
    
    # 2. Extract Key Constraints
    # We only care about constraints that affect logic
    # - strict_compliance (bool)
    # - sustainability_mode (str)
    # - risk_tolerance (float)
    
    policy = {
        "permissions": perms,
        "compliance": {
            "strict_mode": global_constraints.get("strict_compliance", True),
            "region": global_constraints.get("region", "EU"),
            "certifications": global_constraints.get("certifications", [])
        },
        "strategy": {
            "risk_tolerance": global_constraints.get("risk_tolerance", 0.5), # 0.0=Safe, 1.0=Aggressive
            "sustainability_weight": global_constraints.get("sustainability_weight", 0.5)
        }
    }
    
    return policy
