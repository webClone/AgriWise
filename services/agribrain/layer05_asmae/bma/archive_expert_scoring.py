"""
Archive Expert Scoring for Bayesian Model Averaging (BMA).
Computes diagnostic BMA weights based on retrovalidation RMSE metrics.
Strictly isolates these weights under 'diagnostic' status, preventing promotion to production BMA.
"""
from typing import Dict, Any, List
import numpy as np

class ArchiveExpertScoring:
    def __init__(self):
        pass

    def compute_bma_weights(
        self,
        model_rmses: Dict[str, float],
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """
        Computes BMA expert weights using softmax on negative RMSEs:
        w_i = exp(-RMSE_i / temp) / sum(exp(-RMSE_j / temp))
        """
        if not model_rmses:
            return {"weights": {}, "archive_bma_status": "diagnostic"}

        models = list(model_rmses.keys())
        rmses = np.array([model_rmses[m] for m in models], dtype=np.float32)
        
        # Softmax on negative RMSE values
        # Subtract max negative RMSE for numerical stability
        neg_val = -rmses / max(temperature, 1e-5)
        shifted = neg_val - np.max(neg_val)
        exp_vals = np.exp(shifted)
        
        weights = exp_vals / np.sum(exp_vals)
        
        weights_dict = {models[i]: float(weights[i]) for i in range(len(models))}
        
        # Return weights quarantined with diagnostic status
        return {
            "weights": weights_dict,
            "archive_bma_status": "diagnostic",
            "can_promote_to_production": False, # Enforces quarantine
            "provenance": "computed_from_historical_retrovalidation"
        }

    def merge_into_production_bma(
        self,
        production_bma_config: Dict[str, Any],
        archive_bma_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Guards production BMA config.
        Rejects merging of weights unless status is explicitly 'approved_for_production'.
        """
        status = archive_bma_results.get("archive_bma_status", "diagnostic")
        can_promote = archive_bma_results.get("can_promote_to_production", False)
        
        if status != "approved_for_production" or not can_promote:
            # Enforce zero-effect: return unchanged production config
            return production_bma_config
            
        # If approved (only via external admin tool), merge weights
        new_config = dict(production_bma_config)
        new_config["weights"] = archive_bma_results["weights"]
        new_config["bma_source"] = "archive_bma_promoted"
        return new_config
