"""
AgriBrain V56 Ground Truth Schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class GroundTruthEvidence:
    """
    Core schema representing a single piece of ground truth evidence.
    """
    source_id: str
    source_type: str  # drone_orthomosaic | ip_camera | farmer_photo | iot_sensor | farmer_input
    scope: str  # point | zone | plot | raster | event
    timestamp: datetime
    geometry: Optional[Dict[str, Any]] = None
    resolution_m: Optional[float] = None
    confidence: float = 1.0
    validation_targets: List[str] = field(default_factory=list)
    can_boost_1m: bool = False
    can_boost_3cm: bool = False
    can_block_certification: bool = False
    state_update_allowed: bool = False
    payload_ref: Optional[str] = None  # Legacy string-encoded metadata (V56–V59 compat)

    # V60B: Structured drone metadata — replaces payload_ref string-splitting
    # Keys: coverage_pct, rmse_m, tile_count, total_area_m2, crs, width_px, height_px, is_tiled
    drone_metadata: Optional[Dict[str, Any]] = None

    resolution_origin: Optional[str] = None  # satellite_derived | external_ground_truth | fused_validation
    resolution_role: Optional[str] = None  # production_state | advisory_visual | validation_anchor
    asset_origin: Optional[str] = None  # persistent_fixture_file | field_uploaded_file
    asset_generation_mode: Optional[str] = None  # compiled_from_existing_fixture | direct_external_capture
    direct_field_capture: Optional[bool] = None

