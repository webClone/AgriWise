"""
V72: Observation model package.

Forward models h(x_t) for optical and SAR observations,
index-to-state mapping registry, and noise models.
"""

from .index_state_mapping import (
    INDEX_STATE_REGISTRY,
    IndexStateMapping,
    get_mapping,
    get_all_index_names,
    validate_forbidden_state_update,
)
from .s2_forward_model import predict_observation, compute_jacobian
from .s1_sar_model import predict_sar_observation, compute_sar_jacobian
from .observation_noise import compute_observation_noise

__all__ = [
    "INDEX_STATE_REGISTRY",
    "IndexStateMapping",
    "get_mapping",
    "get_all_index_names",
    "validate_forbidden_state_update",
    "predict_observation",
    "compute_jacobian",
    "predict_sar_observation",
    "compute_sar_jacobian",
    "compute_observation_noise",
]
