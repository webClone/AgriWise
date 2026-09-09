"""ASMAE Evaluator.

The secondary evaluation phase. Takes a FROZEN pre-trained NeuralReceiverPipeline
and attempts to correlate the EM-Phenome with the ASMAE biological ground truth.

If it fails to correlate robustly, biological interpretation is denied.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

class ASMAEEvaluator(nn.Module):
    """Linear probe to test physical/biological correlations."""
    def __init__(self, latent_dim: int = 128, num_asmae_states: int = 4):
        """
        num_asmae_states: e.g. [SoilMoisture, CanopyDensity, WaterStress, Temperature]
        """
        super().__init__()
        # A simple linear probe. We don't want a deep network here because
        # we want to prove the EM-Phenome ALREADY linearly separates the physical states.
        self.probe = nn.Linear(latent_dim, num_asmae_states)
        
    def forward(self, phenome: torch.Tensor) -> torch.Tensor:
        return self.probe(phenome)

    def evaluate_correlation(self, phenome: torch.Tensor, asmae_truth: torch.Tensor) -> dict:
        """
        Calculates Pearson R^2 correlation between the Phenome predictions
        and the actual ASMAE physical truth.
        """
        predictions = self.forward(phenome)
        
        # Calculate R^2 per state
        results = {}
        for i, state_name in enumerate(["SoilMoisture", "CanopyDensity", "WaterStress", "ManagementIndex"]):
            pred_i = predictions[:, i]
            truth_i = asmae_truth[:, i]
            
            # Simple R^2
            ss_res = torch.sum((truth_i - pred_i) ** 2)
            ss_tot = torch.sum((truth_i - torch.mean(truth_i)) ** 2)
            r2 = 1 - (ss_res / (ss_tot + 1e-8))
            
            results[state_name] = r2.item()
            
        return results
