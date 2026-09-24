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
from .biophysical_microzones import (
    MicrozoneBiophysicalProfile,
    delineate_biophysical_microzones,
    BIO_CLUSTER_RETENTIVE_FERTILE,
    BIO_CLUSTER_RAPID_DRAINAGE_SAND,
    BIO_CLUSTER_CHRONIC_SALINE,
    BIO_CLUSTER_MODERATE_LOAM,
)

__all__ = [
    "MicrozoneEdge",
    "MicrozoneGraph",
    "MicrozoneNode",
    "build_microzone_graph",
    "MicrozoneBiophysicalProfile",
    "delineate_biophysical_microzones",
    "BIO_CLUSTER_RETENTIVE_FERTILE",
    "BIO_CLUSTER_RAPID_DRAINAGE_SAND",
    "BIO_CLUSTER_CHRONIC_SALINE",
    "BIO_CLUSTER_MODERATE_LOAM",
]

