"""
Crop Intelligence v6.0A — Feature Extraction Package.

Scientific feature vectors for hierarchical crop classification.
No ML, no accuracy claims. Pure feature extraction.

Modules:
  - phenology_features: Multi-season NDVI phenology metrics
  - red_edge_features: Sentinel-2 red-edge temporal features
  - sar_temporal_features: Sentinel-1 VV/VH temporal dynamics
  - crop_feature_vector: Unified feature vector assembly
"""

from .crop_feature_vector import CropFeatureVector, extract_crop_features, plot_observations_to_crop_feature_input
from .phenology_features import PhenologyFeatures, extract_phenology_features
from .red_edge_features import RedEdgeFeatures, extract_red_edge_features
from .sar_temporal_features import SARTemporalFeatures, extract_sar_temporal_features

__all__ = [
    "CropFeatureVector", "extract_crop_features", "plot_observations_to_crop_feature_input",
    "PhenologyFeatures", "extract_phenology_features",
    "RedEdgeFeatures", "extract_red_edge_features",
    "SARTemporalFeatures", "extract_sar_temporal_features",
]
