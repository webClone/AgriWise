"""
History Diagnostics.
Computes performance metrics and convergence stats for historical runs.
"""
from typing import Dict, Any, List
import numpy as np
from .history_schema import HistoricalSmootherOutput

class HistoryDiagnostics:
    def __init__(self):
        pass

    def compute_run_diagnostics(
        self,
        output: HistoricalSmootherOutput
    ) -> Dict[str, Any]:
        """
        Computes key statistics on the EKS smoothed output.
        """
        states = [np.array(x) for x in output.states_smoothed]
        covs = [np.array(p) for p in output.covariances_smoothed]
        
        if not states:
            return {"status": "empty_run"}

        states_arr = np.array(states) # Shape: (T, N_STATES)
        covs_arr = np.array(covs)     # Shape: (T, N_STATES, N_STATES)

        T = len(states)
        N = states_arr.shape[1]

        # Calculate average values over time per state variable
        mean_states = np.mean(states_arr, axis=0) # Shape: (N_STATES,)
        
        # Calculate uncertainty reduction (sigma = sqrt(P[i,i]))
        # prior (t=0) vs posterior (t=T-1)
        prior_sigmas = np.sqrt(np.diagonal(covs_arr[0]))
        posterior_sigmas = np.sqrt(np.diagonal(covs_arr[-1]))
        
        uncertainty_reduction_pct = []
        for i in range(N):
            prior_val = prior_sigmas[i]
            post_val = posterior_sigmas[i]
            reduction = ((prior_val - post_val) / prior_val) * 100.0 if prior_val > 0 else 0.0
            uncertainty_reduction_pct.append(float(reduction))

        # Check for model drifts or bounds violations
        diverged = False
        for i in range(N):
            # If uncertainty grew infinitely
            if posterior_sigmas[i] > prior_sigmas[i] * 3.0:
                diverged = True

        return {
            "status": "success",
            "time_steps": T,
            "mean_lai": float(mean_states[0]),
            "mean_biomass": float(mean_states[1]),
            "mean_sm_0_10": float(mean_states[2]),
            "mean_sm_10_40": float(mean_states[3]),
            "prior_lai_uncertainty": float(prior_sigmas[0]),
            "posterior_lai_uncertainty": float(posterior_sigmas[0]),
            "lai_uncertainty_reduction_pct": float(uncertainty_reduction_pct[0]),
            "uncertainty_reduction_pct_by_state": [float(x) for x in uncertainty_reduction_pct],
            "divergence_detected": diverged
        }
