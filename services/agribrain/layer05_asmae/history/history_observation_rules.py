"""
Historical Observation Rules.
Implements coordinate and physical state updating boundaries.
SAR VV/VH observations are blocked from updating vigor, chlorophyll, phenology, or LAI.
"""
from typing import List
from layer0.state_vector import (
    IDX_LAI,
    IDX_CANOPY_STRESS,
    IDX_PHENO_GDD,
    IDX_PHENO_STAGE,
    IDX_STRESS_THERMAL,
    IDX_PHOTO_EFF
)

class HistoryObservationRules:
    def __init__(self):
        pass

    def apply_rules(self, obs_type: str, H: List[float]) -> List[float]:
        """
        Modifies the observation model mapping vector H to zero-out coefficients
        for state variables that are not allowed to be updated by the given obs_type.
        """
        H_new = list(H)
        
        # SAR VV/VH cannot update vigor, chlorophyll, phenology, or LAI
        if obs_type.lower() in ("vv", "vh"):
            H_new[IDX_LAI] = 0.0
            H_new[IDX_CANOPY_STRESS] = 0.0
            H_new[IDX_PHENO_GDD] = 0.0
            H_new[IDX_PHENO_STAGE] = 0.0
            H_new[IDX_STRESS_THERMAL] = 0.0
            H_new[IDX_PHOTO_EFF] = 0.0
            
        return H_new
