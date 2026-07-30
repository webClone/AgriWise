"""R5.0: Observation event contract.

Design rules:
  1. Observations are asynchronous, source-specific, and independently uncertain.
  2. Each observation has its own spatial support operator and forward model.
  3. Weather and management are NOT observations — they are forcing.
  4. This contract is frozen in R5.0. R5.1 connects it to the temporal engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..state.authority import AuthorityVector


@dataclass(frozen=True)
class ObservationEvent:
    """Immutable contract for a single observation event.

    Represents one source-specific, time-specific measurement with its
    own spatial support, quality, observation operator, and uncertainty model.

    For source family s at acquisition time τ:
        y_(s,τ) = A_(s,τ) h_s(x_τ, θ_s, q_(s,τ)) + ε_(s,τ)
    """
    observation_id: str
    source_family: str      # e.g., "S2_OPTICAL", "S1_SAR", "IOT_SOIL"
    sensor_id: str           # e.g., "S2A", "S1B", "probe_007"
    acquisition_time: datetime
    valid_time: Optional[datetime] = None  # For derived products

    # Spatial and quality context
    spatial_support_ref: str = ""    # Reference to A_(s,τ) operator
    quality_ref: str = ""            # Reference to quality assessment
    observation_operator_ref: str = ""  # Reference to h_s forward model
    uncertainty_model_ref: str = ""  # Reference to ε_(s,τ) model

    # Geometry
    crs_epsg: Optional[int] = None
    native_resolution_m: Optional[float] = None

    # Authority
    authority: AuthorityVector = AuthorityVector(visualization_allowed=True)

    # Provenance
    scene_id: Optional[str] = None
    provider: Optional[str] = None
    processing_level: Optional[str] = None
