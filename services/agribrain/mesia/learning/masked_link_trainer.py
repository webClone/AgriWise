"""Self-Supervised Masked-Link Trainer.

Implements the primary learning strategy: hide links, nodes, time-frequency regions,
and force the NeuralReceiverPipeline to reconstruct them.

Crucially, this phase never touches biological ASMAE ground truth.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple

from .neural_receiver import NeuralReceiverPipeline


class ReconstructionHead(nn.Module):
    """Takes the EM-Phenome and tries to reconstruct the masked input."""
    def __init__(self, latent_dim: int, num_subcarriers: int, num_links: int, seq_len: int):
        super().__init__()
        self.num_subcarriers = num_subcarriers
        self.num_links = num_links
        self.seq_len = seq_len
        self.out_dim = num_links * seq_len * num_subcarriers * 2
        
        self.net = nn.Sequential(
            nn.Linear(latent_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 512),
            nn.ReLU(),
            nn.Linear(512, self.out_dim)
        )
        
    def forward(self, phenome: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Returns reconstructed (mag, phase)."""
        B = phenome.size(0)
        out = self.net(phenome)
        out = out.view(B, self.num_links, self.seq_len, self.num_subcarriers * 2)
        
        mag_recon = out[:, :, :, :self.num_subcarriers]
        phase_recon = out[:, :, :, self.num_subcarriers:]
        return mag_recon, phase_recon


class MaskedLinkTrainer(nn.Module):
    def __init__(self, pipeline: NeuralReceiverPipeline, num_links: int, seq_len: int, num_subcarriers: int = 64):
        super().__init__()
        self.pipeline = pipeline
        self.decoder = ReconstructionHead(
            latent_dim=128, 
            num_subcarriers=num_subcarriers, 
            num_links=num_links, 
            seq_len=seq_len
        )
        self.mse_loss = nn.MSELoss()
        
    def apply_mask(self, csi: torch.Tensor, mask_prob: float = 0.15) -> Tuple[torch.Tensor, torch.Tensor]:
        """Randomly masks patches of the CSI (Time-Frequency or Links)."""
        mask = (torch.rand(csi.shape) < mask_prob).float().to(csi.device)
        masked_csi = csi * (1.0 - mask) # Zero out masked regions
        return masked_csi, mask

    def forward_train_step(self, csi_mag: torch.Tensor, csi_phase: torch.Tensor) -> torch.Tensor:
        """
        Executes a single self-supervised forward pass.
        Returns the reconstruction loss.
        """
        # Apply masks
        masked_mag, mask_m = self.apply_mask(csi_mag)
        masked_phase, mask_p = self.apply_mask(csi_phase)
        
        # Forward pass through the main pipeline
        phenome = self.pipeline(masked_mag, masked_phase)
        
        # Reconstruct the original input
        recon_mag, recon_phase = self.decoder(phenome)
        
        # Calculate loss ONLY on the masked regions to force representation learning
        loss_mag = F.mse_loss(recon_mag * mask_m, csi_mag * mask_m, reduction='sum') / (mask_m.sum() + 1e-8)
        loss_phase = F.mse_loss(recon_phase * mask_p, csi_phase * mask_p, reduction='sum') / (mask_p.sum() + 1e-8)
        
        total_loss = loss_mag + loss_phase
        return total_loss
