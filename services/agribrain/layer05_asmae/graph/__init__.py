"""
V71: Microzone graph package — spatial awareness for ASMAE.

Provides graph construction, neighborhood discovery, row alignment,
soil similarity, irrigation connectivity, edge preservation, and
spatial regularization (Laplacian smoothing).
"""

from .microzone_graph import (
    MicrozoneEdge,
    MicrozoneGraph,
    MicrozoneNode,
    build_microzone_graph,
)

__all__ = [
    "MicrozoneEdge",
    "MicrozoneGraph",
    "MicrozoneNode",
    "build_microzone_graph",
]
