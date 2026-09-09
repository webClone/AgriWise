"""MESIA Deep Learning Neural Receiver Pipeline.

Implements the RF/CSI -> Instrument Normalization -> Link-Level Encoder -> 
Graph Representation -> Temporal Encoder -> EM-Phenome architecture.

Designed strictly for learning physical EM-phenome representations via self-supervised
masked-link prediction without access to biological ASMAE states.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class InstrumentNormalizer(nn.Module):
    """Normalizes out hardware-specific artifacts (gain, clock drift) using CalibrationState."""
    def __init__(self, num_subcarriers: int):
        super().__init__()
        # Simple learnable scaling layer to handle residual hardware noise
        self.gain_correction = nn.Parameter(torch.ones(num_subcarriers))
        self.phase_correction = nn.Parameter(torch.zeros(num_subcarriers))
        
    def forward(self, csi_mag: torch.Tensor, csi_phase: torch.Tensor) -> torch.Tensor:
        """
        Takes raw magnitude and phase and standardizes them.
        csi_mag, csi_phase: (Batch, NumLinks, SeqLen, NumSubcarriers)
        """
        mag_norm = csi_mag * self.gain_correction
        phase_norm = csi_phase + self.phase_correction
        # Combine back into a real-valued tensor (Batch, Links, SeqLen, Subcarriers * 2)
        return torch.cat([mag_norm, phase_norm], dim=-1)


class LinkLevelEncoder(nn.Module):
    """Encodes subcarrier/IQ data over a single link into a dense representation."""
    def __init__(self, input_dim: int, hidden_dim: int = 128):
        super().__init__()
        # 1D CNN to capture spectral correlations across subcarriers
        self.conv1 = nn.Conv1d(in_channels=input_dim, out_channels=hidden_dim, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(in_channels=hidden_dim, out_channels=hidden_dim, kernel_size=3, padding=1)
        self.fc = nn.Linear(hidden_dim, hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (Batch * NumLinks * SeqLen, InputDim)
        """
        # Reshape for 1D conv: (B, C, L) where L is treated as spatial, but here we only have features.
        # Actually, if input is already flat features per link/time, we just use MLPs.
        # Let's treat the features as sequence for Conv1d.
        x = x.unsqueeze(1) # (B, 1, InputDim)
        x = x.transpose(1, 2) # (B, InputDim, 1)
        
        c = F.relu(self.conv1(x))
        c = F.relu(self.conv2(c))
        c = c.squeeze(2) # (B, HiddenDim)
        return self.fc(c)


class RadioGraphRepresentation(nn.Module):
    """Aggregates link embeddings into a full multi-hop topology graph embedding."""
    def __init__(self, link_dim: int = 128, graph_dim: int = 256):
        super().__init__()
        # Simple Graph Attention or Message Passing stub
        self.attention = nn.MultiheadAttention(embed_dim=link_dim, num_heads=4, batch_first=True)
        self.fc_aggregate = nn.Linear(link_dim, graph_dim)
        
    def forward(self, link_embeddings: torch.Tensor, adjacency_mask: torch.Tensor = None) -> torch.Tensor:
        """
        link_embeddings: (Batch, SeqLen, NumLinks, LinkDim)
        adjacency_mask: (Batch, NumLinks, NumLinks) - optional topology mask
        """
        B, S, L, D = link_embeddings.shape
        x = link_embeddings.view(B * S, L, D)
        
        # Self-attention across links in the graph
        attn_out, _ = self.attention(x, x, x, attn_mask=None)
        
        # Mean pool across nodes/links to get a graph-level embedding
        graph_embed = attn_out.mean(dim=1) # (B * S, D)
        graph_embed = self.fc_aggregate(graph_embed)
        
        return graph_embed.view(B, S, -1)


class TemporalEncoder(nn.Module):
    """Encodes how the radio graph evolves over time (e.g. canopy growth, wind, rain)."""
    def __init__(self, graph_dim: int = 256, temporal_dim: int = 256):
        super().__init__()
        self.lstm = nn.LSTM(input_size=graph_dim, hidden_size=temporal_dim, num_layers=2, batch_first=True)
        
    def forward(self, graph_seq: torch.Tensor) -> torch.Tensor:
        """
        graph_seq: (Batch, SeqLen, GraphDim)
        Returns: (Batch, TemporalDim) - The final hidden state summarizing the time window.
        """
        out, (h_n, c_n) = self.lstm(graph_seq)
        # Take the output of the last time step
        return out[:, -1, :]


class EMPhenomeProjector(nn.Module):
    """Projects the temporal graph embedding into the common AgriBrain latent space."""
    def __init__(self, temporal_dim: int = 256, latent_dim: int = 128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(temporal_dim, temporal_dim),
            nn.LayerNorm(temporal_dim),
            nn.ReLU(),
            nn.Linear(temporal_dim, latent_dim)
        )
        
    def forward(self, temporal_embed: torch.Tensor) -> torch.Tensor:
        """Returns the final EM-Phenome vector."""
        return self.net(temporal_embed)


class NeuralReceiverPipeline(nn.Module):
    """The full End-to-End MESIA Neural Receiver Architecture."""
    def __init__(self, num_subcarriers: int = 64, latent_dim: int = 128):
        super().__init__()
        self.normalizer = InstrumentNormalizer(num_subcarriers)
        # Input dim = subcarriers * 2 (mag + phase)
        self.link_encoder = LinkLevelEncoder(input_dim=num_subcarriers * 2)
        self.graph_encoder = RadioGraphRepresentation(link_dim=128, graph_dim=256)
        self.temporal_encoder = TemporalEncoder(graph_dim=256, temporal_dim=256)
        self.em_phenome = EMPhenomeProjector(temporal_dim=256, latent_dim=latent_dim)
        
    def forward(self, csi_mag: torch.Tensor, csi_phase: torch.Tensor) -> torch.Tensor:
        """
        csi_mag, csi_phase: (Batch, NumLinks, SeqLen, NumSubcarriers)
        Returns: (Batch, LatentDim)
        """
        B, L, S, C = csi_mag.shape
        
        # 1. Normalize
        norm_data = self.normalizer(csi_mag, csi_phase) # (B, L, S, C*2)
        
        # 2. Link Encoding
        norm_flat = norm_data.view(B * L * S, -1)
        link_emb = self.link_encoder(norm_flat)
        link_emb = link_emb.view(B, S, L, -1) # Restoring temporal/link structure (B, S, L, D)
        
        # 3. Graph Encoding
        graph_emb = self.graph_encoder(link_emb) # (B, S, GraphDim)
        
        # 4. Temporal Encoding
        temporal_emb = self.temporal_encoder(graph_emb) # (B, TemporalDim)
        
        # 5. EM-Phenome Projection
        phenome = self.em_phenome(temporal_emb) # (B, LatentDim)
        
        return phenome
